"""
[PURPOSE]
- Teleology: Provide a UI-driven bridge from Zenith to hosted AI web UIs (Gemini/ChatGPT).
- Mechanism: Chrome DevTools Protocol (CDP) automation plus policy-gated OS-level input injection.
- Safety: Serialize same-provider launch steps through prompt submission/start detection, while allowing independent tab wait/extract phases to run concurrently.
- Update: Configuration is mutable at runtime; browser lifecycle is decoupled from engine lifecycle.

[INTERFACE]
- Inputs: prompt (str), configuration (dict)
- Outputs: assistant response (str)
- Exports: BridgeManager, ask_ai, reset, close

[DEPENDENCIES]
- system.chrome: binary_execution (browser automation)
- pypi.websocket-client: CDP connection (port 9222)
- pypi.requests: HTTP tab management
- pypi.pyperclip: clipboard injection
- config.master_config.json: chrome_bin (browser path)

[FLOW]
- Hydrate configuration (ensure_configured).
- Ensure a Chrome instance is reachable with CDP enabled (_ensure_browser).
- Open a fresh provider tab (_open_tab).
- Focus provider editor via CDP/DOM and insert prompt (provider-specific).
- Submit prompt (provider-specific).
- Poll until generation completes (_wait_until_done).
- Extract assistant text (_extract_text) and close the tab.

[CONSTRAINTS]
- Atomicity: Prompt injection is a single serialized critical section only when policy permits global input; CDP/DOM transports remain provider-scoped without host focus.
- Determinism: Command sequencing and timeouts are deterministic; model output is externally non-deterministic.
- Single Browser Instance: Only one Chrome process should be managed per BridgeManager.
- Thread Safety: Same-provider launch steps are serialized per provider, and global-input injection is serialized via `_input_lock`.
- OS Dependency: macOS-specific paste support exists only behind explicit global-input opt-in.
- When-needed: Open when a caller needs the bridge runtime's singleton entrypoints, provider diagnostics, or event-log helpers without expanding the provider-specific mixins first.
- Escalates-to: system/core/bridge_cdp.py::CDPTransportMixin._run_prompt_transport_attempt; system/core/bridge_tab.py::TabSessionMixin.warm_provider; system/core/bridge_chatgpt.py::ChatGPTBridgeMixin._prime_chatgpt_submission; system/core/bridge_gemini.py::GeminiBridgeMixin._prime_gemini_submission
- Navigation-group: bridge_runtime

"""

import json
import logging
from collections import deque
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
import hashlib
import os
import random
import re
import subprocess
import time
import threading
import shutil
import platform
import unicodedata
import uuid
from contextlib import contextmanager, nullcontext
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Mapping, Optional, Sequence, cast
from urllib.parse import parse_qs, urlparse


# Module-level executor for wall-clock-bounded CDP evaluates.
# pychrome's websocket recv can block past its socket timeout when Chrome stalls
# server-side; a leaked thread is acceptable since each distill child process is
# short-lived per cohort.
_BRIDGE_EVAL_EXECUTOR = ThreadPoolExecutor(max_workers=8, thread_name_prefix="bridge-eval")
_BRIDGE_EVAL_TIMEOUT_S = float(os.environ.get("BRIDGE_EVAL_TIMEOUT_S", "20") or "20")


class BridgeEvaluateStuck(Exception):
    """Raised when a CDP tab.evaluate exceeds the per-call wall-clock budget."""

try:
    import requests
except ImportError:
    requests = None

try:
    import websocket
except ImportError:
    websocket = None

try:
    import fcntl
except ImportError:
    fcntl = None


class NodeFailure(Exception):
    """
    [ROLE]
    - Teleology: Represent a failure in the Browser/CDP bridge layer.
    - Mechanism: Raised when CDP control, tab management, or provider automation fails.
    - Ownership: Raised by BridgeManager/AgentTab; handled by engine/tool callers.
    - Mutability: Immutable exception payload.
    - Concurrency: Safe to raise across threads; no shared state.
    
    """
    def __init__(
        self,
        message: str,
        *,
        category: str = "bridge_error",
        stage: Optional[str] = None,
        provider: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message)
        self.category = category
        self.stage = stage
        self.provider = provider
        self.details = dict(details or {})


DEFAULT_BRIDGE_STALE_AFTER_S = 15.0 * 60.0
DEFAULT_TRANSPORT_ORDER = ["cdp_input", "dom_inject_click"]
DEFAULT_HOST_FOCUS_POLICY = {
    "allow_host_focus": False,
    "allow_global_input_transport": False,
    "visual_preflight": False,
    "transport_order": list(DEFAULT_TRANSPORT_ORDER),
    "chatgpt_background_mode": "active_background_seat",
}
CHATGPT_BACKGROUND_MODES = {"active_background_seat", "off"}
GLOBAL_INPUT_TRANSPORTS = {"native_macos_input"}
SUPPORTED_TRANSPORTS = {"cdp_input", "dom_inject_click", "native_macos_input"}
# Single-shot CDP Input.insertText with 100k+ chars often stalls or trips devtools sockets; DOM inject tolerates bulk better.
CHATGPT_LARGE_PROMPT_DOM_FIRST_CHARS = 32768
_CDP_INSERT_TEXT_CHUNK_CHARS = 8192

# Safe button labels that _dismiss_provider_overlays is allowed to click.
_OVERLAY_SAFE_DISMISS_LABELS = {"got it", "dismiss", "ok", "close", "i understand"}


# ==========================================
# 藤 OVERLAY DISMISS PAYLOAD
# ==========================================

JS_DISMISS_OVERLAYS = """
(function() {
    var safeLabels = %SAFE_LABELS_JSON%;
    var dialogs = Array.from(document.querySelectorAll('[role="dialog"], [aria-modal="true"]'));
    var visible = dialogs.filter(function(d) {
        var style = window.getComputedStyle ? window.getComputedStyle(d) : null;
        if (!style) return d.offsetParent !== null;
        return style.visibility !== 'hidden' && style.display !== 'none' && (d.offsetParent !== null || style.position === 'fixed');
    });
    if (visible.length === 0) return { dismissed: false, button_text: null, dialog_count: 0 };
    for (var i = 0; i < visible.length; i++) {
        var dialog = visible[i];
        var buttons = Array.from(dialog.querySelectorAll('button'));
        for (var j = 0; j < buttons.length; j++) {
            var btn = buttons[j];
            var label = ((btn.innerText || btn.textContent || '').replace(/\\s+/g, ' ').trim()).toLowerCase();
            if (safeLabels.indexOf(label) >= 0 && !btn.disabled) {
                btn.click();
                return { dismissed: true, button_text: label, dialog_count: visible.length };
            }
        }
    }
    var preview = ((visible[0].innerText || visible[0].textContent || '').replace(/\\s+/g, ' ').trim()).slice(0, 200);
    return { dismissed: false, button_text: null, dialog_count: visible.length, dialog_preview: preview };
})();
"""


# ==========================================
# 藤 SUBSTRATE SCHEDULER (MULTI-ACCOUNT)
# ==========================================

class SubstrateScheduler:
    """
    [ROLE]
    - Teleology: Distribute bridge requests across multiple provider accounts via weighted round-robin.
    - Mechanism: Thread-safe cycling through configured account entries per provider.
    - Ownership: Owned by BridgeManager; accounts loaded from config.
    - Mutability: Mutable internal counters; account list is replaced on reconfiguration.
    - Concurrency: Thread-safe via internal threading.Lock.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        # provider -> list of {id, url, weight}
        self._accounts: Dict[str, list[Dict[str, Any]]] = {}
        # provider -> index into the expanded (weighted) schedule
        self._indices: Dict[str, int] = {}
        # provider -> expanded schedule (account ids repeated by weight)
        self._schedules: Dict[str, list[int]] = {}
        # provider -> per-account stats
        self._stats: Dict[str, Dict[str, Dict[str, Any]]] = {}

    def configure(self, accounts_config: Dict[str, Any]) -> None:
        """
        [ACTION]
        - Teleology: Load and index account definitions from the bridge config into the scheduler.
        - Guarantee: Internal account lists, schedules, and stats are populated for each valid provider entry.
        - Fails: Invalid or empty entries are silently skipped; no exception is raised.
        """
        with self._lock:
            for provider, entries in accounts_config.items():
                provider_key = str(provider or "").strip().lower()
                if not provider_key or not isinstance(entries, list):
                    continue
                valid: list[Dict[str, Any]] = []
                for entry in entries:
                    if not isinstance(entry, dict):
                        continue
                    account_id = str(entry.get("id") or "").strip()
                    url = str(entry.get("url") or "").strip()
                    if not url:
                        continue
                    weight = max(1, int(entry.get("weight", 1) or 1))
                    valid.append({"id": account_id or url, "url": url, "weight": weight})
                if valid:
                    self._accounts[provider_key] = valid
                    # Build expanded schedule: repeat each index by weight
                    schedule: list[int] = []
                    for idx, acct in enumerate(valid):
                        schedule.extend([idx] * acct["weight"])
                    self._schedules[provider_key] = schedule
                    self._indices[provider_key] = 0
                    if provider_key not in self._stats:
                        self._stats[provider_key] = {}
                    for acct in valid:
                        if acct["id"] not in self._stats[provider_key]:
                            self._stats[provider_key][acct["id"]] = {
                                "request_count": 0,
                                "last_used_at": None,
                                "last_error_at": None,
                            }

    def has_accounts(self, provider: str) -> bool:
        """
        [ACTION]
        - Teleology: Report whether at least one account is configured for the given provider.
        - Guarantee: Returns True if any accounts exist for the provider, False otherwise.
        - Fails: None.
        """
        key = str(provider or "").strip().lower()
        with self._lock:
            return bool(self._accounts.get(key))

    def next_account(self, provider: str) -> Optional[Dict[str, Any]]:
        """
        [ACTION]
        - Teleology: Advance and return the next account for a provider via weighted round-robin.
        - Guarantee: Increments the usage counter and last_used_at timestamp for the selected account.
        - Fails: Returns None if no accounts are configured for the provider.
        """
        key = str(provider or "").strip().lower()
        with self._lock:
            accounts = self._accounts.get(key)
            schedule = self._schedules.get(key)
            if not accounts or not schedule:
                return None
            idx = self._indices.get(key, 0) % len(schedule)
            account_idx = schedule[idx]
            self._indices[key] = (idx + 1) % len(schedule)
            account = dict(accounts[account_idx])
            stats = self._stats.setdefault(key, {}).setdefault(
                account["id"], {"request_count": 0, "last_used_at": None, "last_error_at": None}
            )
            stats["request_count"] = int(stats.get("request_count", 0) or 0) + 1
            stats["last_used_at"] = _utc_now_iso()
            account["_stats"] = dict(stats)
            return account

    def record_error(self, provider: str, account_id: str) -> None:
        """
        [ACTION]
        - Teleology: Stamp the last_error_at timestamp for a specific provider account.
        - Guarantee: The account's last_error_at field is updated to the current UTC time.
        - Fails: None; silently creates a stats entry if the account was not previously tracked.
        """
        key = str(provider or "").strip().lower()
        aid = str(account_id or "").strip()
        with self._lock:
            stats = self._stats.setdefault(key, {}).setdefault(
                aid, {"request_count": 0, "last_used_at": None, "last_error_at": None}
            )
            stats["last_error_at"] = _utc_now_iso()

    def snapshot(self, provider: Optional[str] = None) -> Dict[str, Any]:
        """
        [ACTION]
        - Teleology: Return a serializable snapshot of account configuration and usage stats.
        - Guarantee: Returns a dict scoped to one provider if specified, or all providers otherwise.
        - Fails: None.
        """
        with self._lock:
            if provider:
                key = str(provider or "").strip().lower()
                return {
                    "provider": key,
                    "account_count": len(self._accounts.get(key, [])),
                    "accounts": [dict(a) for a in self._accounts.get(key, [])],
                    "stats": dict(self._stats.get(key, {})),
                }
            return {
                "providers": {
                    k: {
                        "account_count": len(v),
                        "accounts": [dict(a) for a in v],
                        "stats": dict(self._stats.get(k, {})),
                    }
                    for k, v in self._accounts.items()
                }
            }


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _bridge_repo_root() -> Path:
    current = Path(__file__).resolve()
    for parent in [current] + list(current.parents):
        if (parent / "master_config.json").exists():
            return parent
    return Path.cwd().resolve()


def _bridge_state_path() -> Path:
    return _bridge_repo_root() / "tools" / "meta" / "apply" / "observe_history" / "bridge_state.json"


def _bridge_event_log_path() -> Path:
    return _bridge_repo_root() / "tools" / "meta" / "apply" / "observe_history" / "bridge_events.jsonl"


def _bridge_locks_dir() -> Path:
    return _bridge_repo_root() / "tools" / "meta" / "apply" / "observe_history" / "bridge_locks"


def _read_bridge_state() -> Dict[str, Any]:
    path = _bridge_state_path()
    if not path.exists():
        return {"providers": {}}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"providers": {}}
    if not isinstance(payload, dict):
        return {"providers": {}}
    providers = payload.get("providers")
    if not isinstance(providers, dict):
        payload["providers"] = {}
    return payload


def _int_or_zero(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _bridge_lane_mode(value: Any) -> str:
    text = str(value or "").strip().lower()
    if any(token in text for token in ("join", "synthesis", "evaluation")):
        return "join"
    return "probe"


def _bridge_active_progress_priority(progress: Mapping[str, Any]) -> int:
    phase = str(progress.get("phase") or "").strip().lower()
    wait_status = str(progress.get("wait_status") or "").strip().lower()
    response_started = bool(progress.get("response_started"))
    response_chars = _int_or_zero(progress.get("response_chars"))
    if phase == "provider_wait":
        if wait_status == "stabilizing":
            return 90
        if wait_status == "receiving" or response_started or response_chars > 0:
            return 85
        return 80
    if phase == "done":
        return 70
    if phase == "extract":
        return 65
    if phase == "submit":
        return 60
    if phase == "baseline":
        return 50
    if phase == "wake":
        return 40
    if phase == "focus":
        return 30
    if phase == "tab_open":
        return 20
    if phase == "provider_queue":
        return 10
    return 0


def _format_bridge_char_count(value: Any) -> str:
    count = max(0, _int_or_zero(value))
    if count >= 1_000_000:
        return f"{count / 1_000_000:.1f}m chars"
    if count >= 1_000:
        return f"{count / 1_000:.1f}k chars"
    return f"{count} chars"


def _summarize_bridge_active_progress(progress: Mapping[str, Any]) -> str:
    node_id = str(progress.get("node_id") or "unknown").strip() or "unknown"
    lane_mode = _bridge_lane_mode(progress.get("lane"))
    phase = str(progress.get("phase") or "").strip().lower()
    wait_status = str(progress.get("wait_status") or "").strip().lower()
    response_started = bool(progress.get("response_started"))
    response_chars = _int_or_zero(progress.get("response_chars"))
    if phase == "provider_wait":
        if wait_status == "stabilizing":
            state = "stabilizing"
        elif wait_status == "receiving" or response_started or response_chars > 0:
            state = "receiving"
        else:
            state = "thinking"
        return f"running {lane_mode}: {node_id}, {state}, {_format_bridge_char_count(response_chars)}"
    if phase:
        return f"running {lane_mode}: {node_id}, {phase}"
    return f"running {lane_mode}: {node_id}"


def _select_active_runtime_progress(
    state: Mapping[str, Any],
    *,
    provider: str | None = None,
) -> dict[str, Any] | None:
    runtime = state.get("runtime")
    if not isinstance(runtime, Mapping):
        return None
    sessions = runtime.get("sessions")
    if not isinstance(sessions, Mapping):
        return None
    provider_key = str(provider or "").strip().lower() or None
    best_progress: dict[str, Any] | None = None
    best_key: tuple[float, int] | None = None

    for session_id, session_payload in sessions.items():
        if not isinstance(session_payload, Mapping):
            continue
        providers = session_payload.get("providers")
        if not isinstance(providers, Mapping):
            continue
        for provider_name, provider_payload in providers.items():
            current_provider = str(provider_name or "").strip().lower()
            if provider_key and current_provider != provider_key:
                continue
            if not isinstance(provider_payload, Mapping):
                continue
            tabs = provider_payload.get("tabs")
            if not isinstance(tabs, Mapping):
                continue
            for tab_id, tab_payload in tabs.items():
                if not isinstance(tab_payload, Mapping):
                    continue
                phase = str(tab_payload.get("phase") or "").strip().lower()
                if phase == "tab_closed":
                    continue
                updated_at = (
                    str(tab_payload.get("updated_at") or "").strip()
                    or str(provider_payload.get("updated_at") or "").strip()
                    or str(session_payload.get("updated_at") or "").strip()
                    or str(session_payload.get("started_at") or "").strip()
                )
                updated_ts = _parse_iso_timestamp(updated_at) or datetime.fromtimestamp(0, tz=timezone.utc)
                progress = {
                    "session_id": str(session_id or "").strip() or None,
                    "provider": current_provider or None,
                    "tab_id": str(tab_id or "").strip() or None,
                    "node_id": str(tab_payload.get("node_id") or "").strip() or None,
                    "lane": str(tab_payload.get("lane") or "").strip() or None,
                    "phase": phase or None,
                    "status": str(tab_payload.get("status") or "ok").strip() or "ok",
                    "wait_status": str(tab_payload.get("wait_status") or "").strip() or None,
                    "response_chars": _int_or_zero(tab_payload.get("response_chars")),
                    "response_count": _int_or_zero(tab_payload.get("response_count")),
                    "response_started": bool(tab_payload.get("response_started")),
                    "transport": str(tab_payload.get("transport") or "").strip() or None,
                    "updated_at": updated_at or None,
                    "run_kind": str(session_payload.get("run_kind") or "").strip() or None,
                }
                progress["summary"] = _summarize_bridge_active_progress(progress)
                candidate_key = (
                    updated_ts.timestamp(),
                    _bridge_active_progress_priority(progress),
                )
                if best_key is None or candidate_key > best_key:
                    best_key = candidate_key
                    best_progress = progress
    return best_progress


def _write_bridge_state(payload: Dict[str, Any]) -> None:
    path = _bridge_state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _append_bridge_event(payload: Dict[str, Any]) -> None:
    path = _bridge_event_log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False))
        handle.write("\n")


def snapshot_bridge_events_for_session(
    *,
    session_id: str,
    out_path: Path,
    source_path: Optional[Path] = None,
) -> int:
    """
    [ACTION]
    - Teleology: Materialize one session's bridge event slice into a standalone artifact for post-run review.
    - Mechanism: Streams the event log, keeps only JSON lines whose normalized session_id matches, and writes the filtered lines to `out_path`.
    - Reads: source_path or the default bridge event log from _bridge_event_log_path().
    - Writes: `out_path` when matching events exist.
    - Guarantee: Returns the number of persisted matching lines; leaves no file behind when no session events are found.
    - Fails: None — malformed lines, missing files, and IO errors degrade to a zero-count result.
    - When-needed: Open when an observe dump or bridge audit needs a per-session event extract instead of the full shared log.
    - Escalates-to: system/core/bridge.py::read_recent_bridge_events; system/core/bridge.py::_append_bridge_event
    """
    sid = str(session_id or "").strip()
    if not sid:
        return 0
    events_path = source_path or _bridge_event_log_path()
    if not events_path.exists():
        return 0
    events: list[str] = []
    try:
        with events_path.open("r", encoding="utf-8") as handle:
            for raw_line in handle:
                line = raw_line.strip()
                if not line or sid not in line:
                    continue
                try:
                    payload = json.loads(line)
                except Exception:
                    continue
                if str(payload.get("session_id") or "").strip() == sid:
                    events.append(line)
    except Exception:
        return 0
    if not events:
        return 0
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(events) + "\n", encoding="utf-8")
    return len(events)


def read_recent_bridge_events(*, limit: int = 40) -> list[Dict[str, Any]]:
    """
    [ACTION]
    - Teleology: Expose a bounded tail of parsed bridge runtime events for diagnostics surfaces.
    - Mechanism: Reads the shared event log into a fixed-size deque, parses JSON rows, and returns the surviving objects oldest-first within the requested window.
    - Reads: The bridge event log at _bridge_event_log_path().
    - Guarantee: Returns at most `limit` dict payloads and drops malformed lines silently.
    - Fails: None — missing logs or read errors return an empty list.
    - When-needed: Open when a status or diagnostics surface needs the recent bridge event tail without snapshotting a specific session.
    - Escalates-to: system/core/bridge.py::snapshot_bridge_events_for_session; system/core/bridge.py::_bridge_event_log_path
    """
    path = _bridge_event_log_path()
    if not path.exists() or limit <= 0:
        return []
    buf: deque[str] = deque(maxlen=limit)
    try:
        with path.open("r", encoding="utf-8") as handle:
            for raw_line in handle:
                line = raw_line.strip()
                if line:
                    buf.append(line)
    except OSError:
        return []
    out: list[Dict[str, Any]] = []
    for raw in buf:
        try:
            parsed = json.loads(raw)
        except Exception:
            continue
        if isinstance(parsed, dict):
            out.append(parsed)
    return out


def _parse_iso_timestamp(value: Any) -> Optional[datetime]:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _require_bridge_dependencies() -> None:
    """
    [ACTION]
    - Teleology: Fail fast when the runtime is about to use bridge features without the optional browser dependencies installed.
    - Mechanism: Checks the lazily imported `requests` and `websocket` modules and raises NodeFailure listing missing packages.
    - Guarantee: Returns only when the runtime has the dependency set needed for live browser/CDP work.
    - Fails: Raises NodeFailure when required bridge packages are unavailable.
    - When-needed: Open when bridge status, preflight, or tab lifecycle calls fail before browser work begins and the cause may be missing optional dependencies.
    - Escalates-to: system/core/bridge.py::NodeFailure; system/core/bridge_tab.py::TabSessionMixin.warm_provider
    """
    missing = []
    if requests is None:
        missing.append("requests")
    if websocket is None:
        missing.append("websocket-client")
    if missing:
        missing_csv = ", ".join(missing)
        raise NodeFailure(
            f"Missing bridge dependencies ({missing_csv}). "
            "Install with: pip install websocket-client requests pyperclip"
        )


# ==========================================
# 藤 SONAR PAYLOADS (THE EYES)
# ==========================================

# [NEW] Identity Injection Script (Template)
JS_INJECT_IDENTITY = """
(function(nodeId, lane, color) {
  function clamp(value, min, max) {
    return Math.min(max, Math.max(min, value));
  }
  function tint(hex, amount) {
    const raw = String(hex || '').replace('#', '').trim();
    const full = raw.length === 3 ? raw.split('').map(ch => ch + ch).join('') : raw;
    if (!/^[0-9a-fA-F]{6}$/.test(full)) return hex || '#111827';
    const channels = [0, 2, 4].map(offset => parseInt(full.slice(offset, offset + 2), 16));
    const shifted = channels.map(channel => {
      const next = amount >= 0
        ? channel + (255 - channel) * amount
        : channel * (1 + amount);
      return clamp(Math.round(next), 0, 255);
    });
    return '#' + shifted.map(channel => channel.toString(16).padStart(2, '0')).join('');
  }
  function initials(raw) {
    const tokens = String(raw || '')
      .replace(/[_-]+/g, ' ')
      .trim()
      .split(/\\s+/)
      .filter(Boolean);
    if (!tokens.length) return 'Z';
    return tokens
      .slice(0, 2)
      .map(token => token.charAt(0).toUpperCase())
      .join('')
      .slice(0, 2);
  }
  function laneMode(raw) {
    const text = String(raw || '').toLowerCase();
    if (text.includes('join') || text.includes('synthesis') || text.includes('evaluation')) return 'join';
    return 'probe';
  }
  // --- 0. PREPARE THE ASSETS ---
  const size = 64;
  const canvas = document.createElement('canvas');
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext('2d');
  const hi = tint(color, 0.30);
  const lo = tint(color, -0.30);
  const ink = laneMode(lane) === 'join' ? '#1f1300' : '#07111d';
  const sigil = initials(nodeId);

  const gradient = ctx.createLinearGradient(0, 0, size, size);
  gradient.addColorStop(0, hi);
  gradient.addColorStop(1, lo);
  ctx.fillStyle = gradient;
  ctx.fillRect(0, 0, size, size);

  ctx.globalAlpha = 0.18;
  ctx.fillStyle = '#ffffff';
  ctx.beginPath();
  ctx.arc(size * 0.20, size * 0.18, size * 0.28, 0, Math.PI * 2);
  ctx.fill();
  ctx.globalAlpha = 1.0;

  ctx.fillStyle = 'rgba(255, 255, 255, 0.14)';
  ctx.fillRect(0, 0, size, 10);

  ctx.fillStyle = laneMode(lane) === 'join' ? '#fff4cf' : '#dff4ff';
  if (laneMode(lane) === 'join') {
    ctx.save();
    ctx.translate(size - 11, 11);
    ctx.rotate(Math.PI / 4);
    ctx.fillRect(-4, -4, 8, 8);
    ctx.restore();
  } else {
    ctx.beginPath();
    ctx.arc(size - 11, 11, 4, 0, Math.PI * 2);
    ctx.fill();
  }

  ctx.strokeStyle = 'rgba(255, 255, 255, 0.92)';
  ctx.lineWidth = 5;
  ctx.strokeRect(0, 0, size, size);

  ctx.fillStyle = '#ffffff';
  ctx.font = 'bold 24px -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif';
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.fillText(sigil, size / 2, size / 2 + 5);

  ctx.globalAlpha = 0.16;
  ctx.fillStyle = ink;
  ctx.fillRect(0, size - 14, size, 14);
  ctx.globalAlpha = 1.0;

  const dataUrl = canvas.toDataURL('image/png');

  // --- 1. THE TITLE LOCK (Try/Catch for Re-entry) ---
  try {
      let _title = nodeId;
      Object.defineProperty(document, 'title', {
          get: function() { return _title; },
          set: function(val) { }, // Swallow updates
          configurable: false,     // Hard Lock
          enumerable: true
      });
  } catch(e) {
      // If we are here, it means we ALREADY locked it in a previous run.
      // That's fine. Just force the value visually.
      document.title = nodeId;
  }

  // --- 2. THE ENFORCER (Idempotent) ---
  function enforce() {
      // A. Force Title (Just in case)
      if (document.title !== nodeId) document.title = nodeId;

      // B. Force Icon
      const icons = document.querySelectorAll('link[rel*="icon"]');
      let oursFound = false;
      
      icons.forEach(n => {
          if (n.href === dataUrl) {
              oursFound = true;
          } else {
              n.remove(); // Destroy competitors
          }
      });

      if (!oursFound) {
          const link = document.createElement('link');
          link.rel = 'icon';
          link.type = 'image/png';
          link.href = dataUrl;
          document.head.appendChild(link);
      }
  }

  // --- 3. MUTATION OBSERVER (Stealthy) ---
  // Reacts only when something actually changes title/favicon.
  // No polling loop = no detectable JS activity pattern for Turnstile.
  if (window.__zenith_observer__) window.__zenith_observer__.disconnect();
  window.__zenith_observer__ = new MutationObserver(enforce);
  window.__zenith_observer__.observe(document.head, { childList: true, subtree: true, characterData: true });

  // Run immediately once
  enforce();

  return "OK";
})(%NODE_ID_JSON%, %LANE_JSON%, %COLOR_JSON%);
"""

_BRIDGE_COMPOSER_HELPERS = """
    const BRIDGE_COMPOSER_ATTR = 'data-zenith-bridge-composer';
    const BRIDGE_BLOCK_TAGS = new Set(['P', 'DIV', 'LI', 'PRE', 'BLOCKQUOTE', 'H1', 'H2', 'H3', 'H4', 'H5', 'H6']);

    function bridgeCanonicalText(value) {
        let text = String(value || '').replace(/\\r\\n?/g, '\\n');
        text = text.replace(/[\\u00A0\\u202F\\u2007]/g, ' ');
        text = text.replace(/[\\u200B\\u200C\\u200D\\u2060\\uFEFF]/g, '');
        text = text.replace(/\\n+$/g, '');
        try {
            text = text.normalize('NFC');
        } catch (_ignored) {}
        return text;
    }

    function bridgeContenteditableText(root) {
        if (!root) return '';
        let out = '';

        function walk(node) {
            if (!node) return;
            if (node.nodeType === Node.TEXT_NODE) {
                out += node.nodeValue || '';
                return;
            }
            if (node.nodeType !== Node.ELEMENT_NODE) return;
            const tag = String(node.tagName || '').toUpperCase();
            if (tag === 'BR') {
                out += '\\n';
                return;
            }
            const isBlock = BRIDGE_BLOCK_TAGS.has(tag);
            const before = out.length;
            for (const child of Array.from(node.childNodes || [])) {
                walk(child);
            }
            if (isBlock && out.length > before && !out.endsWith('\\n')) {
                out += '\\n';
            }
        }

        for (const child of Array.from(root.childNodes || [])) {
            walk(child);
        }
        if (!out && root.textContent) {
            out = String(root.textContent || '');
        }
        return out.replace(/\\n+$/g, '');
    }

    function bridgeTextOf(el) {
        if (!el) return '';
        const tag = String(el.tagName || '').toUpperCase();
        if (tag === 'TEXTAREA') {
            return bridgeCanonicalText(el.value || '');
        }
        if (el.getAttribute && el.getAttribute('contenteditable') === 'true') {
            return bridgeCanonicalText(bridgeContenteditableText(el));
        }
        return bridgeCanonicalText(el.innerText || el.textContent || '');
    }

    function bridgeIsEditable(el) {
        if (!el) return false;
        const tag = String(el.tagName || '').toUpperCase();
        return tag === 'TEXTAREA' || el.getAttribute('contenteditable') === 'true';
    }

    function bridgeVisible(el) {
        if (!el) return false;
        const style = window.getComputedStyle ? window.getComputedStyle(el) : null;
        if (!style) return el.offsetParent !== null;
        return style.visibility !== 'hidden' && style.display !== 'none' && (el.offsetParent !== null || style.position === 'fixed');
    }

    function bridgeLabelOf(el) {
        if (!el) return '';
        const tag = String(el.tagName || '').toLowerCase();
        const id = el.id ? `#${el.id}` : '';
        const role = el.getAttribute('role') ? `[role="${el.getAttribute('role')}"]` : '';
        const editable = el.getAttribute('contenteditable') === 'true' ? '[contenteditable="true"]' : '';
        return `${tag}${id}${role}${editable}`;
    }

    function bridgeEditableAncestor(node) {
        if (!node) return null;
        if (bridgeIsEditable(node)) return node;
        return node.closest ? node.closest('textarea, [contenteditable="true"]') : null;
    }

    function bridgeComposerRoots(editor) {
        const roots = [];
        const seen = new Set();

        function push(node) {
            if (!node || seen.has(node)) return;
            seen.add(node);
            roots.push(node);
        }

        if (editor) {
            push(editor.closest && editor.closest('form'));
            push(editor.closest && editor.closest('[data-testid="composer"]'));
            push(editor.closest && editor.closest('#composer-background'));
            push(editor.closest && editor.closest('[role="main"]'));
            push(editor.parentElement);
        }

        push(document.querySelector('form'));
        push(document.querySelector('#composer-background'));
        push(document.querySelector('[role="main"]'));
        push(document.body);

        return roots;
    }

    function bridgeFindSendButton(provider, editor) {
        const roots = bridgeComposerRoots(editor);

        if (provider === 'chatgpt') {
            // Voice-mode exclusion: ChatGPT now shows a voice button (gold circle)
            // instead of Send when the input is empty. We must never click it.
            const VOICE_LABELS = ['start voice', 'voice', 'start voice mode',
                                  'start voice input', 'listen', 'microphone',
                                  'dictate', 'record voice', 'voice input'];
            function isVoiceButton(btn) {
                const aria = String(btn.getAttribute('aria-label') || '').toLowerCase().trim();
                const testId = String(btn.getAttribute('data-testid') || '').toLowerCase();
                const title = String(btn.getAttribute('title') || '').toLowerCase().trim();
                const cls = String(btn.className || '').toLowerCase();
                return VOICE_LABELS.some(v => aria.includes(v) || testId.includes(v) || title.includes(v))
                    || cls.includes('voice') || cls.includes('microphone') || cls.includes('dictat');
            }
            function isSendButton(btn) {
                if (!btn || isVoiceButton(btn)) return false;
                const aria = String(btn.getAttribute('aria-label') || '').toLowerCase();
                const testId = String(btn.getAttribute('data-testid') || '').toLowerCase();
                const title = String(btn.getAttribute('title') || '').toLowerCase();
                const text = String(btn.innerText || btn.textContent || '').replace(/\\s+/g, ' ').trim().toLowerCase();
                return testId === 'send-button'
                    || testId.includes('send')
                    || aria === 'send prompt'
                    || aria === 'send message'
                    || title === 'send prompt'
                    || title === 'send message'
                    || text === 'send'
                    || text === 'send prompt'
                    || text === 'send message';
            }
            for (const root of roots) {
                if (!root || !root.querySelectorAll) continue;
                let target = root.querySelector('button[data-testid="send-button"]');
                if (!target) {
                    target = root.querySelector('button[aria-label="Send prompt"]');
                }
                if (!target) {
                    target = root.querySelector('button[aria-label="Send message"]');
                }
                if (!target) {
                    const buttons = Array.from(root.querySelectorAll('button'))
                        .filter(bridgeVisible)
                        .filter(b => !isVoiceButton(b));
                    target = buttons.find(isSendButton) || null;
                }
                // Final guard: never return a voice button or arbitrary composer action.
                if (target && !bridgeVisible(target)) target = null;
                if (target && !isSendButton(target)) target = null;
                if (target) return target;
            }
            return null;
        }

        for (const root of roots) {
            if (!root || !root.querySelectorAll) continue;
            let target = root.querySelector('button[aria-label="Send message"]');
            if (!target) {
                target = root.querySelector('button.send-button');
            }
            if (!target) {
                const buttons = Array.from(root.querySelectorAll('button, div[role="button"]'));
                target = buttons.find(candidate => {
                    const icon = candidate.querySelector('.material-icons, .google-symbols, mat-icon');
                    return icon && icon.innerText.trim().toLowerCase() === 'send';
                }) || null;
            }
            if (target) return target;
        }

        return null;
    }

    function bridgeCandidateSelectors(provider) {
        if (provider === 'chatgpt') {
            return [
                '#prompt-textarea',
                'form textarea',
                'textarea',
                'form [contenteditable="true"]',
                'div[contenteditable="true"][role="textbox"]',
                '[contenteditable="true"]',
                '.ql-editor'
            ];
        }
        if (provider === 'gemini') {
            return [
                'div[contenteditable="true"][role="textbox"]',
                'div[contenteditable="true"]',
                'textarea',
                '[contenteditable="true"]'
            ];
        }
        return ['textarea', '[contenteditable="true"]'];
    }

    function bridgeMarkComposer(editor, provider) {
        document.querySelectorAll(`[${BRIDGE_COMPOSER_ATTR}]`).forEach(node => node.removeAttribute(BRIDGE_COMPOSER_ATTR));
        if (editor) {
            editor.setAttribute(BRIDGE_COMPOSER_ATTR, provider);
        }
    }

    function bridgeScoreComposerCandidate(el, provider, expectedChars) {
        const text = bridgeTextOf(el);
        let score = 0;
        const tag = String(el.tagName || '').toUpperCase();
        const role = String(el.getAttribute && el.getAttribute('role') || '').toLowerCase();
        const sendBtn = bridgeFindSendButton(provider, el);

        if (provider === 'chatgpt' && el.id === 'prompt-textarea') score += 6000;
        if (provider === 'chatgpt' && el.closest && el.closest('form')) score += 1200;
        if (provider === 'gemini' && tag === 'DIV' && el.getAttribute && el.getAttribute('contenteditable') === 'true') score += 2600;
        if (tag === 'TEXTAREA') score += 1800;
        if (el.getAttribute && el.getAttribute('contenteditable') === 'true') score += 1400;
        if (role === 'textbox') score += 800;
        if (bridgeVisible(el)) score += 600;
        if (document.activeElement === el || (document.activeElement && el.contains && el.contains(document.activeElement))) score += 500;
        if (sendBtn) {
            score += 1200;
            if (bridgeVisible(sendBtn)) score += 250;
            if (!(sendBtn.disabled || sendBtn.getAttribute('aria-disabled') === 'true')) score += 250;
        }
        if (expectedChars > 0) {
            const distance = Math.abs(text.length - expectedChars);
            score += Math.max(0, 4000 - Math.min(4000, distance));
        } else if (text.length > 0) {
            score += Math.min(text.length, 400);
        }
        try {
            const rect = el.getBoundingClientRect();
            if (rect.width >= 120 && rect.height >= 20) score += 150;
            if (rect.bottom > window.innerHeight * 0.45) score += 100;
            if (rect.top < window.innerHeight) score += 50;
        } catch (_ignored) {}

        return score;
    }

    function bridgeCollectComposerCandidates(provider) {
        const seen = new Set();
        const candidates = [];

        function push(node) {
            const editable = bridgeEditableAncestor(node);
            if (!editable || seen.has(editable)) return;
            seen.add(editable);
            candidates.push(editable);
        }

        push(document.querySelector(`[${BRIDGE_COMPOSER_ATTR}="${provider}"]`));
        push(document.activeElement);

        for (const selector of bridgeCandidateSelectors(provider)) {
            for (const node of Array.from(document.querySelectorAll(selector))) {
                push(node);
            }
        }

        return candidates;
    }

    function bridgeResolveComposer(provider, expectedChars) {
        const marked = document.querySelector(`[${BRIDGE_COMPOSER_ATTR}="${provider}"]`);
        if (bridgeIsEditable(marked) && document.contains(marked)) {
            return marked;
        }

        const candidates = bridgeCollectComposerCandidates(provider);
        if (candidates.length === 0) return null;

        const ranked = candidates
            .map(el => ({
                el,
                score: bridgeScoreComposerCandidate(el, provider, expectedChars),
                textLength: bridgeTextOf(el).length,
            }))
            .sort((left, right) => {
                if (right.score !== left.score) return right.score - left.score;
                if (right.textLength !== left.textLength) return right.textLength - left.textLength;
                return bridgeLabelOf(left.el).localeCompare(bridgeLabelOf(right.el));
            });

        const selected = ranked[0].el;
        bridgeMarkComposer(selected, provider);
        return selected;
    }

    function bridgePlaceCursorAtEnd(editor) {
        if (!editor) return;
        const tag = String(editor.tagName || '').toUpperCase();
        if (tag === 'TEXTAREA') {
            try {
                const text = editor.value || '';
                editor.selectionStart = text.length;
                editor.selectionEnd = text.length;
            } catch (_ignored) {}
            return;
        }
        try {
            const selection = window.getSelection ? window.getSelection() : null;
            const range = document.createRange();
            range.selectNodeContents(editor);
            range.collapse(false);
            if (selection) {
                selection.removeAllRanges();
                selection.addRange(range);
            }
        } catch (_ignored) {}
    }

    function bridgeClearContenteditable(editor) {
        if (!editor) return;
        try {
            const selection = window.getSelection ? window.getSelection() : null;
            const range = document.createRange();
            range.selectNodeContents(editor);
            range.deleteContents();
            if (selection) {
                selection.removeAllRanges();
                selection.addRange(range);
            }
        } catch (_ignored) {}
        try {
            editor.innerHTML = '';
            editor.innerText = '';
            editor.textContent = '';
        } catch (_ignored) {}
        bridgePlaceCursorAtEnd(editor);
    }

    function bridgeSetContenteditableText(editor, text) {
        if (!editor) return;
        const prompt = String(text || '').replace(/\\r\\n?/g, '\\n');
        bridgeClearContenteditable(editor);
        let inserted = false;
        try {
            if (document.execCommand) {
                inserted = document.execCommand('insertText', false, prompt);
            }
        } catch (_ignored) {}
        if (bridgeCanonicalText(bridgeContenteditableText(editor)) !== bridgeCanonicalText(prompt)) {
            inserted = false;
        }
        if (!inserted) {
            bridgeClearContenteditable(editor);
            if (prompt.length > 0) {
                const fragment = document.createDocumentFragment();
                for (const line of prompt.split('\\n')) {
                    const block = document.createElement('p');
                    if (line.length > 0) {
                        block.textContent = line;
                    } else {
                        block.appendChild(document.createElement('br'));
                    }
                    fragment.appendChild(block);
                }
                editor.appendChild(fragment);
            }
        }
        bridgePlaceCursorAtEnd(editor);
    }

    function bridgeFocusComposer(provider, expectedChars) {
        const editor = bridgeResolveComposer(provider, expectedChars);
        if (!editor) return null;
        try {
            editor.scrollIntoView({ block: 'nearest', inline: 'nearest' });
        } catch (_ignored) {}
        try {
            editor.click();
        } catch (_ignored) {}
        try {
            editor.focus();
        } catch (_ignored) {}
        bridgePlaceCursorAtEnd(editor);
        return editor;
    }
"""

JS_WAKE_GEMINI = (
    """
(function() {
"""
    + _BRIDGE_COMPOSER_HELPERS
    + """
    const editor = bridgeFocusComposer('gemini', 0);
    if (editor) {
        return "OK";
    }
    return "ERROR: Editor not found";
})();
"""
)

JS_CLEAR_GEMINI_INPUT = (
    """
(function() {
"""
    + _BRIDGE_COMPOSER_HELPERS
    + """
    const editor = bridgeFocusComposer('gemini', 0);
    if (!editor) return "ERROR: Gemini editor not found";
    try {
        if (document.queryCommandSupported && document.queryCommandSupported('selectAll')) {
            document.execCommand('selectAll', false, null);
            document.execCommand('delete', false, null);
        }
    } catch (_ignored) {}
    try {
        if (editor.tagName === 'TEXTAREA') {
            const setter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value')?.set;
            if (setter) {
                setter.call(editor, '');
            } else {
                editor.value = '';
            }
        } else {
            const selection = window.getSelection ? window.getSelection() : null;
            const range = document.createRange();
            range.selectNodeContents(editor);
            range.deleteContents();
            if (selection) {
                selection.removeAllRanges();
                selection.addRange(range);
            }
            editor.innerHTML = '';
            editor.innerText = '';
            editor.textContent = '';
        }
    } catch (e) {
        try {
            editor.value = '';
        } catch (_ignored) {
            editor.innerHTML = '';
            editor.innerText = '';
        }
    }
    try {
        editor.dispatchEvent(new InputEvent('beforeinput', { bubbles: true, inputType: 'deleteByCut', data: '' }));
    } catch (_ignored) {}
    try {
        editor.dispatchEvent(new InputEvent('input', { bubbles: true, inputType: 'deleteByCut', data: '' }));
    } catch (_ignored) {
        editor.dispatchEvent(new Event('input', { bubbles: true }));
    }
    editor.dispatchEvent(new Event('change', { bubbles: true }));
    return "OK";
})();
"""
)

JS_FLUSH_GEMINI_INPUT = (
    """
(function() {
"""
    + _BRIDGE_COMPOSER_HELPERS
    + """
    const editor = bridgeResolveComposer('gemini', 0);
    if (editor) {
        try {
            const text = bridgeTextOf(editor);
            editor.dispatchEvent(new InputEvent('input', { bubbles: true, inputType: 'insertText', data: text }));
        } catch (_ignored) {
            editor.dispatchEvent(new Event('input', { bubbles: true }));
        }
        return "OK";
    }
    return "ERROR";
})();
"""
)

JS_INJECT_GEMINI = (
    """
(function(prompt) {
"""
    + _BRIDGE_COMPOSER_HELPERS
    + """
    const editor = bridgeFocusComposer('gemini', 0);
    if (!editor) return "ERROR: Gemini editor not found";
    try {
        if (editor.tagName === 'TEXTAREA') {
            const setter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value')?.set;
            if (setter) {
                setter.call(editor, prompt);
            } else {
                editor.value = prompt;
            }
        } else {
            const selection = window.getSelection ? window.getSelection() : null;
            const range = document.createRange();
            range.selectNodeContents(editor);
            range.deleteContents();
            if (selection) {
                selection.removeAllRanges();
                selection.addRange(range);
            }
            let inserted = false;
            try {
                if (document.execCommand) {
                    inserted = document.execCommand('insertText', false, prompt);
                }
            } catch (_ignored) {}
            if (!inserted) {
                editor.innerText = prompt;
                editor.textContent = prompt;
            }
        }
    } catch (e) {
        try {
            editor.value = prompt;
        } catch (_ignored) {
            editor.innerText = prompt;
        }
    }
    try {
        editor.dispatchEvent(new InputEvent('beforeinput', { bubbles: true, inputType: 'insertText', data: prompt }));
    } catch (_ignored) {}
    try {
        editor.dispatchEvent(new InputEvent('input', { bubbles: true, inputType: 'insertText', data: prompt }));
    } catch (_ignored) {
        editor.dispatchEvent(new Event('input', { bubbles: true }));
    }
    editor.dispatchEvent(new Event('change', { bubbles: true }));
    return "OK";
})(PROMPT);
"""
)

JS_SUBMIT_GEMINI = (
    """
(function() {
"""
    + _BRIDGE_COMPOSER_HELPERS
    + """
    const editor = bridgeResolveComposer('gemini', 0);
    const target = bridgeFindSendButton('gemini', editor);
    if (!target) return "ERROR: Send button not found (all 3 strategies failed)";
    if (target.disabled || target.getAttribute('aria-disabled') === 'true') {
        return "ERROR: Button found but disabled (input may not have registered)";
    }
    target.click();
    return "OK";
})();
"""
)

_GEMINI_EXTRACTABLE_RESPONSE_HELPERS = """
    function cleanText(raw) {
        const stripped = (raw || "")
            .replace(/\\b(gemini|chatgpt)\\s+said:?\\b/gi, " ")
            .replace(/\\byou said:?\\b/gi, " ")
            .replace(/\\byou stopped this response\\b/gi, " ")
            .replace(/\\bshow thinking\\b/gi, " ")
            .replace(/\\banswer now\\b/gi, " ");
        const lines = stripped.split(/\\r?\\n/).map(l => l.trim());
        const filtered = lines.filter(l => l.length > 0);
        return filtered.join("\\n").trim();
    }
    function rawTextWithoutThoughts(node) {
        const thoughts = node ? Array.from(node.querySelectorAll('model-thoughts')) : [];
        const oldDisplays = thoughts.map(t => t.style.display);
        thoughts.forEach(t => {
            t.style.display = 'none';
        });
        const raw = node ? ((node.innerText || "").trim()) : "";
        thoughts.forEach((t, idx) => {
            t.style.display = oldDisplays[idx];
        });
        return raw;
    }
    function collectExtractableResponses(selector) {
        return Array.from(document.querySelectorAll(selector))
            .map(node => cleanText(rawTextWithoutThoughts(node)))
            .filter(text => text.length > 0);
    }
"""

JS_CHECK_GEMINI_STARTED = (
    """
(function() {
"""
    + _GEMINI_EXTRACTABLE_RESPONSE_HELPERS
    + """
    const stopBtn = document.querySelector('button[aria-label="Stop generating"], button[aria-label="Stop"]');
    if (stopBtn) return true;
    const spinner = document.querySelector('.loading-spinner, mat-progress-bar');
    if (spinner) return true;
    const texts = collectExtractableResponses('model-response');
    return texts.length > 0;
})();
"""
)

JS_CHECK_GEMINI_CANCELLED = (
    """
(function() {
"""
    + _BRIDGE_COMPOSER_HELPERS
    + """
    const bodyText = ((document.body && document.body.innerText) || "").replace(/\\s+/g, " ").trim().toLowerCase();
    if (!bodyText.includes("you stopped this response")) return false;
    const stopBtn = document.querySelector('button[aria-label="Stop generating"], button[aria-label="Stop"]');
    if (stopBtn) return false;
    const spinner = document.querySelector('.loading-spinner, mat-progress-bar');
    if (spinner) return false;
    const candidates = Array.from(document.querySelectorAll('message-content, model-response'));
    const last = candidates.length ? candidates[candidates.length - 1] : null;
    const lastText = last ? ((last.innerText || "").replace(/\\s+/g, " ").trim().toLowerCase()) : "";
    if (lastText && !/^(gemini|chatgpt)\\s+said:?$/.test(lastText) && !lastText.includes("you stopped this response")) {
        return false;
    }
    const editor = bridgeResolveComposer('gemini', 0);
    const editorText = bridgeTextOf(editor);
    return editorText.length > 0;
})();
"""
)

JS_CHECK_GEMINI_DONE = (
    """
(function() {
"""
    + _GEMINI_EXTRACTABLE_RESPONSE_HELPERS
    + """
    const stopBtn = document.querySelector('button[aria-label="Stop generating"], button[aria-label="Stop"]');
    if (stopBtn) return false;
    const spinner = document.querySelector('.loading-spinner, mat-progress-bar');
    if (spinner) return false;
    const texts = collectExtractableResponses('model-response');
    return texts.length > 0;
})();
"""
)

JS_SNAPSHOT_GEMINI = (
    """
(function() {
"""
    + _GEMINI_EXTRACTABLE_RESPONSE_HELPERS
    + """
    const cleaned = collectExtractableResponses('model-response');
    if (cleaned.length === 0) return { count: 0, last: "" };
    return { count: cleaned.length, last: cleaned[cleaned.length - 1] };
})();
"""
)

JS_GEMINI_COMPOSER_STATE = (
    """
(function() {
"""
    + _BRIDGE_COMPOSER_HELPERS
    + _GEMINI_EXTRACTABLE_RESPONSE_HELPERS
    + """
    const editor = bridgeResolveComposer('gemini', 0);
    const editorText = bridgeTextOf(editor);
    const sendBtn = bridgeFindSendButton('gemini', editor);
    const stopBtn = document.querySelector('button[aria-label="Stop generating"], button[aria-label="Stop"]');
    const spinner = document.querySelector('.loading-spinner, mat-progress-bar');
    const bodyText = ((document.body && document.body.innerText) || "").replace(/\\s+/g, " ").trim();
    const modelTexts = collectExtractableResponses('model-response');
    const pathname = location.pathname || "";
    return {
        editor_length: editorText.length,
        send_found: !!sendBtn,
        send_enabled: !!sendBtn && !(sendBtn.disabled || sendBtn.getAttribute('aria-disabled') === 'true'),
        stop_visible: !!stopBtn,
        spinner_visible: !!spinner,
        url: location.href || "",
        conversation_started: /\\/app\\/[^/?#]+/.test(pathname),
        has_you_said: /\\byou said\\b/i.test(bodyText),
        body_has_stopped: bodyText.toLowerCase().includes("you stopped this response"),
        model_count: modelTexts.length,
        model_last: modelTexts.length ? modelTexts[modelTexts.length - 1] : ""
    };
})();
"""
)

JS_EXTRACT_GEMINI = (
    """
(function() {
"""
    + _GEMINI_EXTRACTABLE_RESPONSE_HELPERS
    + """
    const extracted = collectExtractableResponses('message-content, model-response');
    if (extracted.length > 0) return extracted[extracted.length - 1];
    const candidates = Array.from(document.querySelectorAll('message-content, model-response'));
    if (candidates.length === 0) return "ERROR: No Content Found";
    return "ERROR: Found containers but they only contained provider label placeholders";
})();
"""
)

# JS payload for the ChatGPT active-background seat. Installed via
# Page.addScriptToEvaluateOnNewDocument BEFORE navigation so it patches
# Document.prototype before any chatgpt.com app code reads visibility/focus
# signals. Also re-evaluable on the live document for reassertion at
# pre-submit and post-click moments. Captures+stops the blur/visibilitychange/
# freeze events so framework code that listens at the capture phase sees a
# steady "page is visible+focused" view of the world.
JS_CHATGPT_BACKGROUND_VISIBILITY_PATCH = """
(function() {
  try {
    Object.defineProperty(Document.prototype, 'hidden', {
      configurable: true,
      get: function() { return false; }
    });
  } catch (_) {}
  try {
    Object.defineProperty(Document.prototype, 'visibilityState', {
      configurable: true,
      get: function() { return 'visible'; }
    });
  } catch (_) {}
  try {
    Object.defineProperty(Document.prototype, 'webkitHidden', {
      configurable: true,
      get: function() { return false; }
    });
  } catch (_) {}
  try {
    Object.defineProperty(Document.prototype, 'webkitVisibilityState', {
      configurable: true,
      get: function() { return 'visible'; }
    });
  } catch (_) {}
  try {
    document.hasFocus = function() { return true; };
  } catch (_) {}
  try {
    window.addEventListener('blur', function(e) { e.stopImmediatePropagation(); }, true);
  } catch (_) {}
  try {
    document.addEventListener('visibilitychange', function(e) { e.stopImmediatePropagation(); }, true);
  } catch (_) {}
  try {
    document.addEventListener('freeze', function(e) { e.stopImmediatePropagation(); }, true);
  } catch (_) {}
})();
"""


JS_WAKE_CHATGPT = (
    """
(function() {
"""
    + _BRIDGE_COMPOSER_HELPERS
    + """
    var input = bridgeFocusComposer('chatgpt', 0);
    if (input) {
        return "OK";
    }
    return "ERROR: ChatGPT input not found";
})();
"""
)

JS_CLEAR_CHATGPT_INPUT = (
    """
(function() {
"""
    + _BRIDGE_COMPOSER_HELPERS
    + """
    var input = bridgeFocusComposer('chatgpt', 0);
    if (!input) return "ERROR: ChatGPT input not found";
    try {
        if (document.queryCommandSupported && document.queryCommandSupported('selectAll')) {
            document.execCommand('selectAll', false, null);
            document.execCommand('delete', false, null);
        }
    } catch (e) {}
    try {
        var setter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value')?.set;
        if (setter && input.tagName === 'TEXTAREA') {
            setter.call(input, '');
        } else if ('value' in input) {
            input.value = '';
        } else {
            bridgeClearContenteditable(input);
        }
    } catch (e) {
        if ('value' in input) {
            input.value = '';
        } else {
            bridgeClearContenteditable(input);
        }
    }
    ['input', 'change', 'keydown', 'keyup'].forEach(function(name) {
        input.dispatchEvent(new Event(name, { bubbles: true }));
    });
    return "OK";
})();
"""
)

JS_INJECT_CHATGPT = (
    """
(function(prompt) {
"""
    + _BRIDGE_COMPOSER_HELPERS
    + """
    var input = bridgeFocusComposer('chatgpt', 0);
    if (!input) return "ERROR: ChatGPT input not found";
    try {
        var setter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value')?.set;
        if (setter && input.tagName === 'TEXTAREA') {
            setter.call(input, prompt);
        } else if ('value' in input) {
            input.value = prompt;
        } else {
            bridgeSetContenteditableText(input, prompt);
        }
    } catch (e) {
        if ('value' in input) {
            input.value = prompt;
        } else {
            bridgeSetContenteditableText(input, prompt);
        }
    }
    ['input', 'change', 'keydown', 'keyup'].forEach(function(name) {
        input.dispatchEvent(new Event(name, { bubbles: true }));
    });
    return "OK";
})(PROMPT);
"""
)

JS_CLICK_CHATGPT = (
    """
(function() {
"""
    + _BRIDGE_COMPOSER_HELPERS
    + """
    var editor = bridgeResolveComposer('chatgpt', 0);
    var editorText = bridgeTextOf(editor);
    if (!editorText || editorText.trim().length === 0) {
        return "ERROR: ChatGPT editor is empty — text must be pasted before clicking send (voice button would activate otherwise)";
    }
    var btn = bridgeFindSendButton('chatgpt', editor);
    var strategy = 'bridgeFindSendButton(chatgpt)';
    if (!btn) return "RETRY: ChatGPT send button not found (text present but send button not yet rendered — voice button may be showing instead)";
    if (btn.disabled || btn.getAttribute('aria-disabled') === 'true') {
        return "RETRY: ChatGPT send button found but disabled — UI may still be transitioning from voice to send";
    }
    btn.click();
    return "OK:" + strategy;
})();
"""
)

JS_CHATGPT_COMPOSER_STATE = (
    """
(function() {
"""
    + _BRIDGE_COMPOSER_HELPERS
    + """
    var editor = bridgeResolveComposer('chatgpt', 0);
    var editorText = bridgeTextOf(editor);
    var sendBtn = bridgeFindSendButton('chatgpt', editor);
    var stopBtn = document.querySelector('button[data-testid="stop-button"], button[aria-label="Stop generating"], button[aria-label="Stop streaming"]');
    var dialogs = Array.from(document.querySelectorAll('[role="dialog"], [aria-modal="true"]')).filter(bridgeVisible);
    var dialog = dialogs.find(function(candidate) {
        var text = ((candidate.innerText || candidate.textContent || '')).replace(/\\s+/g, ' ').trim();
        return text.length > 0;
    }) || null;
    var dialogText = dialog ? ((dialog.innerText || dialog.textContent || '').replace(/\\s+/g, ' ').trim()) : '';
    var normalizedDialog = dialogText.toLowerCase();
    var gotItBtn = dialog ? Array.from(dialog.querySelectorAll('button')).find(function(candidate) {
        return ((candidate.innerText || candidate.textContent || '').replace(/\\s+/g, ' ').trim().toLowerCase()) === 'got it';
    }) : null;
    var pathname = location.pathname || "";
    return {
        editor_length: editorText.length,
        send_found: !!sendBtn,
        send_enabled: !!sendBtn && !(sendBtn.disabled || sendBtn.getAttribute('aria-disabled') === 'true'),
        stop_visible: !!stopBtn,
        url: location.href || "",
        conversation_started: /\\/c\\//.test(pathname),
        dialog_visible: !!dialog,
        dialog_preview: dialogText.slice(0, 220),
        got_it_visible: !!gotItBtn,
        temporary_limit_interrupt: normalizedDialog.includes('requests too quickly')
            || normalizedDialog.includes('temporarily limited access to your conversations')
            || normalizedDialog.includes('please wait a few minutes before trying again'),
    };
})();
"""
)

JS_CHECK_CHATGPT_STARTED = """
(function() {
    const stop = document.querySelector('button[data-testid="stop-button"], button[aria-label="Stop generating"], button[aria-label="Stop streaming"]');
    if (stop) return true;
    const messages = Array.from(document.querySelectorAll('[data-message-author-role="assistant"]'));
    if (messages.length === 0) return false;
    return messages[messages.length - 1].innerText.trim().length > 0;
})();
"""

JS_CHECK_CHATGPT_DONE = """
(function() {
    const stop = document.querySelector('button[data-testid="stop-button"]');
    if (stop) return false;
    const messages = Array.from(document.querySelectorAll('[data-message-author-role="assistant"]'));
    if (messages.length === 0) return false;
    return messages[messages.length - 1].innerText.trim().length > 0;
})();
"""

JS_DISABLE_CHATGPT_THINKING = """
(function() {
    var btns = Array.from(document.querySelectorAll('button, [role="button"]'));
    var thinking_btn = btns.find(function(b) {
        var aria = (b.getAttribute('aria-label') || '').toLowerCase();
        return aria.includes('thinking') && aria.includes('remove');
    });
    if (thinking_btn) {
        thinking_btn.click();
        return 'disabled_thinking';
    }
    return 'no_thinking_toggle';
})();
"""

JS_SNAPSHOT_CHATGPT = """
(function() {
    const messages = Array.from(document.querySelectorAll('[data-message-author-role="assistant"]'));
    if (messages.length === 0) return { count: 0, last: "" };
    const last = messages[messages.length - 1];
    return { count: messages.length, last: (last.innerText || "").trim() };
})();
"""

JS_EXTRACT_CHATGPT = """
(function() {
    const messages = Array.from(document.querySelectorAll('[data-message-author-role="assistant"]'));
    if (messages.length === 0) return "ERROR";
    return messages[messages.length - 1].innerText.trim();
})();
"""


JS_PREFLIGHT_GEMINI_AUDIT = """
(function() {
    const report = { input: null, send: null, composer: null, warnings: [] };
    const editor = document.querySelector('div[contenteditable="true"]') || document.querySelector('textarea');
    if (!editor) {
        report.warnings.push("INPUT_NOT_FOUND");
        return report;
    }
    editor.focus();
    editor.click();
    if (document.queryCommandSupported && document.queryCommandSupported('insertText')) {
        document.execCommand('insertText', false, '⚡ PREFLIGHT PROBE');
    } else if ('value' in editor) {
        editor.value = '⚡ PREFLIGHT PROBE';
    } else {
        editor.innerText = '⚡ PREFLIGHT PROBE';
    }
    ['beforeinput', 'input', 'change', 'keydown', 'keyup'].forEach(function(name) {
        editor.dispatchEvent(new Event(name, { bubbles: true }));
    });
    const send = document.querySelector('button[aria-label="Send message"]')
        || document.querySelector('button.send-button')
        || Array.from(document.querySelectorAll('button, div[role="button"]')).find(function(candidate) {
            const icon = candidate.querySelector('.material-icons, .google-symbols, mat-icon');
            return icon && icon.innerText.trim().toLowerCase() === 'send';
        });
    report.input = {
        tagName: editor.tagName,
        selector: editor.tagName === 'TEXTAREA' ? 'textarea' : 'div[contenteditable="true"]',
        visible: editor.offsetParent !== null,
    };
    if (!send) {
        report.warnings.push("SEND_NOT_FOUND");
    } else {
        report.send = {
            tagName: send.tagName,
            ariaLabel: send.getAttribute('aria-label') || '',
            disabled: !!send.disabled || send.getAttribute('aria-disabled') === 'true',
            visible: send.offsetParent !== null,
        };
    }
    const modelResponses = Array.from(document.querySelectorAll('model-response, [data-response-index]'));
    report.composer = {
        editor_length: ((editor.value || editor.innerText || editor.textContent || '').trim()).length,
        response_count: modelResponses.length,
    };
    return report;
})();
"""


JS_PREFLIGHT_CHATGPT_AUDIT = (
    """
(function() {
"""
    + _BRIDGE_COMPOSER_HELPERS
    + """
    const report = { input: null, send: null, composer: null, warnings: [] };
    const editor = document.getElementById('prompt-textarea')
        || document.querySelector('textarea')
        || document.querySelector('div[contenteditable="true"]');
    if (!editor) {
        report.warnings.push("INPUT_NOT_FOUND");
        return report;
    }
    editor.focus();
    editor.click();
    try {
        const textareaSetter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value');
        if (textareaSetter && textareaSetter.set && editor.tagName === 'TEXTAREA') {
            textareaSetter.set.call(editor, '⚡ PREFLIGHT PROBE');
        } else if ('value' in editor) {
            editor.value = '⚡ PREFLIGHT PROBE';
        } else {
            editor.innerText = '⚡ PREFLIGHT PROBE';
        }
    } catch (_error) {
        if ('value' in editor) {
            editor.value = '⚡ PREFLIGHT PROBE';
        } else {
            editor.innerText = '⚡ PREFLIGHT PROBE';
        }
    }
    editor.dispatchEvent(new Event('input', { bubbles: true }));
    editor.dispatchEvent(new Event('change', { bubbles: true }));
    const send = bridgeFindSendButton('chatgpt', editor);
    report.input = {
        tagName: editor.tagName,
        visible: editor.offsetParent !== null,
        selector: editor.id ? '#' + editor.id : editor.tagName.toLowerCase(),
    };
    if (!send) {
        report.warnings.push("SEND_NOT_FOUND");
    } else {
        report.send = {
            tagName: send.tagName,
            ariaLabel: send.getAttribute('aria-label') || '',
            disabled: !!send.disabled || send.getAttribute('aria-disabled') === 'true',
            visible: send.offsetParent !== null,
        };
    }
    report.composer = {
        editor_length: ((editor.value || editor.innerText || editor.textContent || '').trim()).length,
        response_count: document.querySelectorAll('[data-message-author-role="assistant"]').length,
    };
    return report;
})();
"""
)


@dataclass(frozen=True)
class ProviderAdapter:
    """
    [ROLE]
    - Teleology: Bundle all provider-specific JavaScript snippets and metadata into a single immutable record.
    - Ownership: Owned by PROVIDER_ADAPTERS registry; consumed by BridgeSession dispatch logic.
    - Mutability: Immutable (frozen dataclass).
    - Concurrency: Safe to share across threads; no mutable state.
    """
    name: str
    target_hint: str
    wake_js: str
    clear_js: str
    dom_inject_js: str
    submit_js: str
    start_js: str
    done_js: str
    snapshot_js: str
    extract_js: str
    composer_state_js: Optional[str] = None
    preflight_audit_js: Optional[str] = None
    target_hosts: tuple[str, ...] = ()


PROVIDER_ADAPTERS: Dict[str, ProviderAdapter] = {
    "gemini": ProviderAdapter(
        name="gemini",
        target_hint="gemini.google.com",
        wake_js=JS_WAKE_GEMINI,
        clear_js=JS_CLEAR_GEMINI_INPUT,
        dom_inject_js=JS_INJECT_GEMINI,
        submit_js=JS_SUBMIT_GEMINI,
        start_js=JS_CHECK_GEMINI_STARTED,
        done_js=JS_CHECK_GEMINI_DONE,
        snapshot_js=JS_SNAPSHOT_GEMINI,
        extract_js=JS_EXTRACT_GEMINI,
        composer_state_js=JS_GEMINI_COMPOSER_STATE,
        preflight_audit_js=JS_PREFLIGHT_GEMINI_AUDIT,
        target_hosts=("gemini.google.com",),
    ),
    "chatgpt": ProviderAdapter(
        name="chatgpt",
        target_hint="chatgpt.com",
        wake_js=JS_WAKE_CHATGPT,
        clear_js=JS_CLEAR_CHATGPT_INPUT,
        dom_inject_js=JS_INJECT_CHATGPT,
        submit_js=JS_CLICK_CHATGPT,
        start_js=JS_CHECK_CHATGPT_STARTED,
        done_js=JS_CHECK_CHATGPT_DONE,
        snapshot_js=JS_SNAPSHOT_CHATGPT,
        extract_js=JS_EXTRACT_CHATGPT,
        composer_state_js=JS_CHATGPT_COMPOSER_STATE,
        preflight_audit_js=JS_PREFLIGHT_CHATGPT_AUDIT,
        target_hosts=("chatgpt.com", "chat.openai.com"),
    ),
}

# ==========================================
# 肌 CDP CLIENT
# ==========================================

class AgentTab:
    """
    [ROLE]
    - Teleology: Encapsulate a single Chrome browser tab controlled via WebSocket.
    - Mechanism: Sends CDP commands and enforces socket-level timeouts to prevent infinite blocking.
    - Ownership: Owns one WebSocket connection and tab identifier for its lifetime.
    - Mutability: Mutable connection state; no global state mutation.
    - Concurrency: Not thread-safe per tab; callers must serialize use of a single tab instance.
    - When-needed: Open when bridge debugging needs the raw CDP tab contract used by prompt transport, provider audits, or tab inspection helpers.
    - Escalates-to: system/core/bridge.py::BridgeManager; system/core/bridge_cdp.py::CDPTransportMixin._run_prompt_transport_attempt
    """
    def __init__(self, ws_url: str, tab_id: str, timeout: float = 15.0) -> None:
        _require_bridge_dependencies()
        self.ws_url = ws_url
        self.ws = websocket.create_connection(ws_url, timeout=timeout)
        self.tab_id = tab_id
        self.msg_id = 0
        self.timeout = timeout

    def _reconnect(self) -> None:
        try:
            self.ws.close()
        except Exception:
            pass
        self.ws = websocket.create_connection(self.ws_url, timeout=self.timeout)

    def send(self, method: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        [ACTION]
        - Teleology: Transmit a raw CDP command over WebSocket.
        - Fails: Raises NodeFailure on socket timeout/error.
        - Guarantee: Returns response dict.
        - When-needed: Open when a bridge failure needs the lowest-level CDP request or reconnect behavior instead of the higher transport orchestration.
        - Escalates-to: system/core/bridge.py::AgentTab.evaluate; system/core/bridge_cdp.py::CDPTransportMixin._run_prompt_transport_attempt
        """
        self.msg_id += 1
        payload = {"id": self.msg_id, "method": method, "params": params or {}}
        encoded_payload = json.dumps(payload)

        last_error: Optional[BaseException] = None
        for attempt in range(2):
            try:
                self.ws.send(encoded_payload)
                response = self.ws.recv()
                return cast(Dict[str, Any], json.loads(response))
            except (
                websocket.WebSocketTimeoutException,
                websocket.WebSocketConnectionClosedException,
                OSError,
            ) as exc:
                last_error = exc
                if attempt == 0:
                    try:
                        self._reconnect()
                        continue
                    except Exception as reconnect_exc:
                        last_error = reconnect_exc
                break
        raise NodeFailure(
            f"CDP Socket Timeout/Error: {last_error}",
            category="cdp_socket_error",
            stage="cdp_command",
        ) from last_error

    def evaluate(self, expression: str, *, await_promise: bool = False) -> Any:
        """
        [ACTION]
        - Teleology: Execute JavaScript in the context of the tab.
        - Fails: Raises NodeFailure on protocol error.
        - Guarantee: Returns the result value.
        - When-needed: Open when provider compose-state or extract JS returns unexpected data and the issue may be in Runtime.evaluate handling rather than provider selectors.
        - Escalates-to: system/core/bridge_chatgpt.py::ChatGPTBridgeMixin._chatgpt_compose_state; system/core/bridge_gemini.py::GeminiBridgeMixin._gemini_compose_state
        """
        res = self.send(
            "Runtime.evaluate",
            {
                "expression": expression,
                "returnByValue": True,
                "awaitPromise": bool(await_promise),
            },
        )
        if "error" in res:
             raise NodeFailure(f"CDP Protocol Error: {res['error']}")
        return res.get("result", {}).get("result", {}).get("value")

    def focus(self) -> None:
        """
        [ACTION]
        - Teleology: Bring the tab to the foreground.
        - Fails: Raises NodeFailure if socket is dead.
        - Guarantee: Tab is focused.
        """
        self.send("Page.bringToFront")

    def close(self) -> None:
        """
        [ACTION]
        - Teleology: Terminate the WebSocket connection.
        - Mechanism: Close socket and release local resources best-effort.
        - Guarantee: Connection is closed or scheduled for closure; subsequent sends are unsafe.
        - Fails: None (swallows errors).
        
        """
        try:
            self.ws.close()
        except Exception:
            pass

# ==========================================
# ｧ HELPER
# ==========================================

def _rv(val: Any, default: Any = None) -> Any:
    """
    Resolve config value wrappers.
    
    Unwraps `{value, desc}` objects if present; passes primitives through.
    
    """
    if isinstance(val, dict) and "value" in val:
        return val["value"]
    return val if val is not None else default


# ==========================================
# ｧ BRIDGE MANAGER
# ==========================================

# Provider-specific mixins (deferred import — these reference BridgeManager state via self,
# so they can only be imported after the bridge.py module-level helpers exist).
from system.core.bridge_cdp import CDPTransportMixin  # noqa: E402
from system.core.bridge_chatgpt import ChatGPTBridgeMixin  # noqa: E402
from system.core.bridge_gemini import GeminiBridgeMixin  # noqa: E402
from system.core.bridge_tab import TabSessionMixin  # noqa: E402


class BridgeManager(CDPTransportMixin, ChatGPTBridgeMixin, GeminiBridgeMixin, TabSessionMixin):
    """
    [ROLE]
    - Teleology: Singleton conductor for Chrome automation.
    - Mechanism: Configuration-driven CDP lifecycle + provider-specific prompt injection.
    - Ownership: Owns the managed Chrome process handle (if launched), locks, and runtime configuration cache.
    - Mutability: Mutable configuration and browser/tab state over time.
    - Concurrency: Thread-safe at the manager level; serializes same-provider launch steps, global input via `_input_lock`, and config/browser mutations via `_manager_lock`.
    - When-needed: Open when the bridge runtime needs the authoritative owner of Chrome lifecycle, provider serialization, and mixin composition.
    - Escalates-to: system/core/bridge_cdp.py::CDPTransportMixin; system/core/bridge_tab.py::TabSessionMixin; system/core/bridge.py::bridge_diagnostics
    """
    def __init__(self) -> None:
        self._manager_lock = threading.RLock()
        self._input_lock = threading.Lock()
        self._bridge_event_lock = threading.Lock()
        self._provider_interaction_locks: Dict[str, threading.Lock] = {}
        self._provider_interaction_waiters: Dict[str, int] = {}
        self._provider_interaction_active: Dict[str, Dict[str, Any]] = {}
        
        self.logger = logging.getLogger("system.bridge")
        self._is_configured = False
        self._browser_process: Optional[subprocess.Popen] = None

        self.debug_port = 9222
        self.debug_url = "http://localhost:9222"
        self.chrome_bin = "google-chrome"
        self.profile_path = os.path.expanduser("~/.config/zenith_profile")
        self.connection_timeout = 15.0
        # Backstop for the _wait_until_done loop. Per-call evaluate is bounded by
        # _BRIDGE_EVAL_TIMEOUT_S; this monitor cap is the outer wall for one ask.
        # Override via bridge_cfg.monitor_timeout_s or env BRIDGE_MONITOR_TIMEOUT_S.
        self.monitor_timeout_s = float(
            os.environ.get("BRIDGE_MONITOR_TIMEOUT_S", "600") or "600"
        )
        self.poll_interval_s = 1.2
        self.jitter_ratio = 0.25
        self.stale_after_s = DEFAULT_BRIDGE_STALE_AFTER_S
        self.retryable_session_attempts = 2
        self.allow_extensions = False
        self.reuse_existing_tabs = True
        self.allow_host_focus = bool(DEFAULT_HOST_FOCUS_POLICY["allow_host_focus"])
        self.allow_global_input_transport = bool(DEFAULT_HOST_FOCUS_POLICY["allow_global_input_transport"])
        self.visual_preflight = bool(DEFAULT_HOST_FOCUS_POLICY["visual_preflight"])
        self.transport_order = list(DEFAULT_HOST_FOCUS_POLICY["transport_order"])
        self.chatgpt_background_mode = str(DEFAULT_HOST_FOCUS_POLICY["chatgpt_background_mode"])
        self.targets = {}
        self.substrate_scheduler = SubstrateScheduler()
        
        self.timings = {
            "init_focus_sleep": 3.0,
            "wake_sleep": 1.5,
            "flush_sleep": 1.0,
            "post_paste_sleep": 2.5,
            "start_timeout_s": 12.0,
            "start_timeout_per_100k_chars_s": 8.0,
            "start_timeout_max_s": 45.0,
            "composer_ready_timeout_s": 6.0,
            "composer_ready_per_100k_chars_s": 6.0,
            "composer_ready_max_s": 30.0,
            "cancel_stable_polls": 3.0,
            "transport_retry_sleep": 1.5,
            "session_retry_sleep": 2.0,
            "provider_lock_poll_s": 0.25,
            "as_activate_delay": 0.5,
            "as_enter_delay": 0.5,
            "hydration_sleep": 4.0,
        }

        # --- Focus coordinator: track waiting tabs, focus oldest first ---
        self._waiting_tabs: list[tuple[float, AgentTab, Dict[str, Any]]] = []
        self._waiting_tabs_lock = threading.Lock()

    def _configure_host_focus_policy(self, policy: Optional[Mapping[str, Any]]) -> None:
        """
        Apply bridge.host_focus_policy. Defaults are focus-safe: no host focus
        changes and no global clipboard/keyboard transport.
        """
        raw_policy = policy if isinstance(policy, Mapping) else {}
        self.allow_host_focus = bool(
            _rv(raw_policy.get("allow_host_focus"), DEFAULT_HOST_FOCUS_POLICY["allow_host_focus"])
        )
        self.allow_global_input_transport = bool(
            _rv(
                raw_policy.get("allow_global_input_transport"),
                DEFAULT_HOST_FOCUS_POLICY["allow_global_input_transport"],
            )
        )
        self.visual_preflight = bool(
            _rv(raw_policy.get("visual_preflight"), DEFAULT_HOST_FOCUS_POLICY["visual_preflight"])
        )

        raw_mode = _rv(
            raw_policy.get("chatgpt_background_mode"),
            DEFAULT_HOST_FOCUS_POLICY["chatgpt_background_mode"],
        )
        mode_token = str(raw_mode or "").strip().lower()
        if mode_token not in CHATGPT_BACKGROUND_MODES:
            mode_token = str(DEFAULT_HOST_FOCUS_POLICY["chatgpt_background_mode"])
        self.chatgpt_background_mode = mode_token

        raw_order = _rv(raw_policy.get("transport_order"), DEFAULT_HOST_FOCUS_POLICY["transport_order"])
        source = raw_order if isinstance(raw_order, list) else DEFAULT_HOST_FOCUS_POLICY["transport_order"]
        normalized: list[str] = []
        for item in source:
            name = str(item).strip()
            if not name or name in normalized or name not in SUPPORTED_TRANSPORTS:
                continue
            if name in GLOBAL_INPUT_TRANSPORTS and not self.allow_global_input_transport:
                continue
            normalized.append(name)
        self.transport_order = normalized or list(DEFAULT_TRANSPORT_ORDER)

    def _host_focus_policy_snapshot(self) -> Dict[str, Any]:
        return {
            "allow_host_focus": bool(self.allow_host_focus),
            "allow_global_input_transport": bool(self.allow_global_input_transport),
            "visual_preflight": bool(self.visual_preflight),
            "transport_order": list(self.transport_order),
            "chatgpt_background_mode": str(self.chatgpt_background_mode),
        }

    def _chatgpt_active_background_seat_enabled(self) -> bool:
        """
        Predicate: should ChatGPT bridge tabs use the active-background seat
        (CDP focus emulation + page lifecycle reassertion + visibility patch +
        Chrome anti-throttling launch flags)? Returns True only when the
        host_focus_policy.chatgpt_background_mode token is 'active_background_seat'
        and allow_host_focus is False (because the seat IS the non-invasive
        path; if the operator explicitly opted into host focus, that path runs
        instead).
        """
        return (
            str(getattr(self, "chatgpt_background_mode", "")).strip().lower() == "active_background_seat"
            and not bool(getattr(self, "allow_host_focus", False))
        )

    def _apply_chatgpt_active_background_seat(
        self,
        tab: "AgentTab",
        *,
        reason: str = "",
    ) -> Dict[str, Any]:
        """
        Install / reassert the ChatGPT active-background seat on a CDP tab.

        Three CDP commands plus a live-document patch evaluation:
          1. Emulation.setFocusEmulationEnabled(enabled=true) — spoof
             document.hasFocus().
          2. Page.setWebLifecycleState(state="active") — keep the page out
             of Chrome's frozen lifecycle state.
          3. Page.addScriptToEvaluateOnNewDocument(VISIBILITY_PATCH,
             runImmediately=true) — patch Document.prototype.hidden /
             .visibilityState / .hasFocus / capture-stop blur+visibilitychange+
             freeze on every new document and re-run on the live one.
          4. tab.evaluate(VISIBILITY_PATCH) — belt-and-suspenders reassertion
             on the current document, so reassertion calls (pre-submit,
             post-click) refresh the patched state even when no navigation
             happened.

        All four steps are best-effort (each wrapped in try/except). Returns a
        small dict summarising which steps succeeded so callers can record it
        on validation receipts.
        """
        result: Dict[str, Any] = {
            "reason": str(reason or ""),
            "focus_emulation_enabled": False,
            "lifecycle_active": False,
            "script_on_new_document_id": None,
            "live_patch_evaluated": False,
            "errors": [],
        }
        try:
            tab.send("Emulation.setFocusEmulationEnabled", {"enabled": True})
            result["focus_emulation_enabled"] = True
        except Exception as exc:
            result["errors"].append(f"setFocusEmulationEnabled: {exc}")
        try:
            tab.send("Page.setWebLifecycleState", {"state": "active"})
            result["lifecycle_active"] = True
        except Exception as exc:
            result["errors"].append(f"setWebLifecycleState: {exc}")
        try:
            payload = {
                "source": JS_CHATGPT_BACKGROUND_VISIBILITY_PATCH,
                "runImmediately": True,
            }
            response = tab.send("Page.addScriptToEvaluateOnNewDocument", payload)
            identifier = (
                response.get("result", {}).get("identifier")
                if isinstance(response, dict)
                else None
            )
            result["script_on_new_document_id"] = identifier
        except Exception as exc:
            result["errors"].append(f"addScriptToEvaluateOnNewDocument: {exc}")
        try:
            tab.evaluate(JS_CHATGPT_BACKGROUND_VISIBILITY_PATCH)
            result["live_patch_evaluated"] = True
        except Exception as exc:
            result["errors"].append(f"live_patch_evaluate: {exc}")
        return result

    def _probe_chatgpt_visibility_state(self, tab: "AgentTab") -> Dict[str, Any]:
        """
        Read the current visibility/focus signals seen by JS on the tab.
        Used by validation receipts to confirm the active-background seat is
        actually fooling page-side checks.
        """
        try:
            value = tab.evaluate(
                "JSON.stringify({"
                "visibility: document.visibilityState,"
                "hidden: document.hidden,"
                "hasFocus: document.hasFocus()"
                "})"
            )
        except Exception as exc:
            return {"error": str(exc)}
        try:
            return json.loads(value) if isinstance(value, str) else (value or {})
        except Exception:
            return {"raw": value}

    def _require_chatgpt_active_background_seat(
        self,
        tab: "AgentTab",
        *,
        reason: str,
    ) -> Dict[str, Any]:
        """
        Strict capability gate. Apply the seat AND verify it took, raising a
        structured NodeFailure if focus emulation, lifecycle reactivation,
        live-document patch, or visibility probe disagree with what the seat
        is supposed to do. Caller can then drop the dispatch instead of
        sleepwalking through a backgrounded throttled tab.
        """
        seat_summary = self._apply_chatgpt_active_background_seat(tab, reason=reason)
        probe = self._probe_chatgpt_visibility_state(tab)
        ok = (
            seat_summary.get("focus_emulation_enabled") is True
            and seat_summary.get("lifecycle_active") is True
            and seat_summary.get("live_patch_evaluated") is True
            and probe.get("visibility") == "visible"
            and probe.get("hidden") is False
            and probe.get("hasFocus") is True
        )
        if not ok:
            raise NodeFailure(
                "ChatGPT active-background seat did not verify "
                f"(reason={reason!r}, summary={seat_summary!r}, probe={probe!r})",
                category="active_background_seat_not_verified",
                stage="active_background_seat",
                provider="chatgpt",
                details={"seat_summary": seat_summary, "visibility_probe": probe, "reason": reason},
            )
        return {"seat_summary": seat_summary, "visibility_probe": probe, "reason": reason}

    def _required_active_background_chrome_flags(self) -> set[str]:
        """Set of Chrome launch flags the active-background seat depends on."""
        if not self._chatgpt_active_background_seat_enabled():
            return set()
        return {
            "--disable-background-timer-throttling",
            "--disable-renderer-backgrounding",
            "--disable-backgrounding-occluded-windows",
            "--disable-features=IntensiveWakeUpThrottling",
        }

    def _expected_profile_path(self) -> str:
        """Resolve the configured bridge user-data-dir to an absolute path."""
        try:
            return str(Path(str(getattr(self, "profile_path", "") or "")).expanduser().resolve())
        except Exception:
            return str(getattr(self, "profile_path", "") or "")

    def _browser_listener_pid(self, debug_port: int | None = None) -> int | None:
        """Return the PID of the Chrome process listening on debug_port via lsof."""
        port = int(debug_port if debug_port is not None else self.debug_port)
        try:
            result = subprocess.run(
                ["lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN", "-t"],
                capture_output=True,
                text=True,
                timeout=3,
            )
        except Exception:
            return None
        for line in (result.stdout or "").splitlines():
            line = line.strip()
            if line.isdigit():
                return int(line)
        return None

    def _browser_listener_cmdline(self, debug_port: int | None = None) -> str:
        """Get the full command line of the Chrome process listening on debug_port."""
        pid = self._browser_listener_pid(debug_port=debug_port)
        if pid is None:
            return ""
        try:
            result = subprocess.run(
                ["ps", "-p", str(pid), "-o", "command="],
                capture_output=True,
                text=True,
                timeout=3,
            )
        except Exception:
            return ""
        return (result.stdout or "").strip()

    def _assert_active_background_browser_process(self) -> None:
        """
        Validate the running bridge Chrome listener has the user_data_dir we
        expect AND every required active-background flag. Raises NodeFailure
        on mismatch so callers can refuse to dispatch through a degraded
        Chrome (the failure mode that produced the recent stale-validation
        ambiguity: receipts said active-bg passed, but the live listener was
        launched on a different profile with no anti-throttle flags).
        """
        if not self._chatgpt_active_background_seat_enabled():
            return
        cmdline = self._browser_listener_cmdline()
        if not cmdline:
            raise NodeFailure(
                f"No Chrome listener found on debug port {self.debug_port}",
                category="active_background_chrome_listener_missing",
                stage="browser_launch",
                provider="chatgpt",
            )
        expected_profile = self._expected_profile_path()
        if expected_profile and expected_profile not in cmdline:
            raise NodeFailure(
                f"Bridge Chrome profile mismatch: expected {expected_profile!r} "
                f"in listener cmdline, got: {cmdline!r}",
                category="active_background_profile_mismatch",
                stage="browser_launch",
                provider="chatgpt",
                details={"expected_profile": expected_profile, "listener_cmdline": cmdline},
            )
        required = self._required_active_background_chrome_flags()
        missing = sorted(flag for flag in required if flag not in cmdline)
        if missing:
            raise NodeFailure(
                f"Bridge Chrome missing required active-background flags: {missing}",
                category="active_background_chrome_flags_missing",
                stage="browser_launch",
                provider="chatgpt",
                details={"missing_flags": missing, "listener_cmdline": cmdline},
            )

    def _allow_host_focus(self, meta: Optional[Mapping[str, Any]] = None) -> bool:
        if isinstance(meta, Mapping) and "allow_host_focus" in meta:
            return bool(_rv(meta.get("allow_host_focus"), False))
        return bool(self.allow_host_focus)

    def _allow_global_input_transport(self, meta: Optional[Mapping[str, Any]] = None) -> bool:
        if isinstance(meta, Mapping):
            if "allow_global_input_transport" in meta:
                return bool(_rv(meta.get("allow_global_input_transport"), False))
            if "allow_native_fallback" in meta:
                return bool(_rv(meta.get("allow_native_fallback"), False))
        return bool(self.allow_global_input_transport)

    def _focus_tab(
        self,
        tab: AgentTab,
        *,
        meta: Optional[Mapping[str, Any]] = None,
        reason: str = "",
    ) -> bool:
        """
        Route all host-visible tab focusing through the bridge policy.
        Returns True only when Page.bringToFront was intentionally called.
        """
        if not self._allow_host_focus(meta):
            return False
        try:
            tab.focus()
            return True
        except Exception:
            raise

    def _provider_adapter(self, provider: str) -> ProviderAdapter:
        key = str(provider or "").strip().lower()
        adapter = PROVIDER_ADAPTERS.get(key)
        if adapter is None:
            raise NodeFailure(
                f"Unsupported bridge provider: {provider}",
                category="provider_target_missing",
                stage="config",
                provider=key or None,
            )
        return adapter

    @staticmethod
    def _normalize_provider_host(value: Any) -> str:
        text = str(value or "").strip()
        if not text:
            return ""
        candidate = text if "://" in text else f"https://{text}"
        try:
            parsed = urlparse(candidate)
        except Exception:
            return ""
        host = str(parsed.hostname or "").strip().lower()
        if host.startswith("www."):
            host = host[4:]
        return host

    def _provider_hosts(self, provider: str) -> tuple[str, ...]:
        adapter = self._provider_adapter(provider)
        ordered_hosts: list[str] = []

        configured_target = self._normalize_provider_host(self.targets.get(provider))
        if configured_target:
            ordered_hosts.append(configured_target)

        for raw_host in adapter.target_hosts:
            host = self._normalize_provider_host(raw_host)
            if host:
                ordered_hosts.append(host)

        hint_host = self._normalize_provider_host(adapter.target_hint)
        if hint_host:
            ordered_hosts.append(hint_host)

        deduped: list[str] = []
        seen: set[str] = set()
        for host in ordered_hosts:
            if host and host not in seen:
                deduped.append(host)
                seen.add(host)
        return tuple(deduped)

    def _provider_page_matches(self, provider: str, page: Mapping[str, Any]) -> bool:
        page_url = str(page.get("url", "") or "").strip()
        if not page_url:
            return False
        lower_page_url = page_url.lower()
        page_host = self._normalize_provider_host(page_url)
        if not page_host:
            return False

        for expected_host in self._provider_hosts(provider):
            if page_host == expected_host or page_host.endswith(f".{expected_host}"):
                return True
            if (
                provider == "gemini"
                and page_host == "accounts.google.com"
                and "rotatecookiespage" in lower_page_url
            ):
                origin_values = parse_qs(urlparse(page_url).query).get("origin", [])
                for origin_value in origin_values:
                    origin_host = self._normalize_provider_host(origin_value)
                    if origin_host == expected_host or origin_host.endswith(f".{expected_host}"):
                        return True

        adapter = self._provider_adapter(provider)
        target_hint = str(adapter.target_hint or "").strip().lower()
        return bool(target_hint) and target_hint in lower_page_url

    def _match_provider_pages(self, provider: str, pages: Sequence[Mapping[str, Any]]) -> list[Dict[str, Any]]:
        matched: list[Dict[str, Any]] = []
        for page in pages:
            if not isinstance(page, Mapping):
                continue
            if self._provider_page_matches(provider, page):
                matched.append(dict(page))
        return matched

    def _known_provider_names(self) -> tuple[str, ...]:
        ordered: list[str] = []
        for name in PROVIDER_ADAPTERS.keys():
            label = str(name or "").strip().lower()
            if label and label not in ordered:
                ordered.append(label)
        for raw_name in self.targets.keys():
            label = str(raw_name or "").strip().lower()
            if label and label in PROVIDER_ADAPTERS and label not in ordered:
                ordered.append(label)
        return tuple(ordered)

    @staticmethod
    def _is_browser_utility_page(url: str) -> bool:
        lower_url = str(url or "").strip().lower()
        return lower_url.startswith(
            (
                "chrome://",
                "chrome-untrusted://",
                "devtools://",
                "about:blank",
                "chrome-extension://",
                "edge://",
                "brave://",
            )
        )

    def _classify_browser_page(self, page: Mapping[str, Any]) -> Dict[str, Any]:
        page_type = str(page.get("type", "") or "").strip().lower() or "page"
        url = str(page.get("url", "") or "").strip()
        role = "external"
        provider_name: Optional[str] = None
        if page_type != "page":
            role = "auxiliary"
        else:
            for name in self._known_provider_names():
                try:
                    if self._provider_page_matches(name, page):
                        role = "provider"
                        provider_name = name
                        break
                except Exception:
                    continue
            if role != "provider" and self._is_browser_utility_page(url):
                role = "utility"
        return {
            "_page_type": page_type,
            "_role_kind": role,
            "_role_provider": provider_name,
        }

    def _browser_cdp_command(
        self,
        method: str,
        params: Optional[Dict[str, Any]] = None,
        *,
        timeout_s: float = 5.0,
    ) -> Dict[str, Any]:
        _require_bridge_dependencies()
        self._ensure_browser()
        try:
            version_resp = requests.get(f"{self.debug_url}/json/version", timeout=timeout_s)
            version_payload = version_resp.json()
        except Exception as exc:
            raise NodeFailure(
                f"Failed to load browser debug metadata: {exc}",
                category="cdp_unreachable",
                stage="browser_connect",
            ) from exc
        ws_url = str(version_payload.get("webSocketDebuggerUrl", "") or "").strip()
        if not ws_url:
            raise NodeFailure(
                "Browser debug metadata is missing webSocketDebuggerUrl",
                category="cdp_unreachable",
                stage="browser_connect",
            )
        ws = None
        try:
            ws = websocket.create_connection(ws_url, timeout=timeout_s)
            payload = {"id": 1, "method": method, "params": params or {}}
            ws.send(json.dumps(payload))
            while True:
                raw = ws.recv()
                response = json.loads(raw)
                if response.get("id") == 1:
                    return cast(Dict[str, Any], response)
        except Exception as exc:
            raise NodeFailure(
                f"Browser CDP command failed for {method}: {exc}",
                category="cdp_socket_error",
                stage="cdp_command",
            ) from exc
        finally:
            try:
                if ws is not None:
                    ws.close()
            except Exception:
                pass

    def _list_browser_pages(self, *, timeout_s: float = 2.0) -> list[Dict[str, Any]]:
        _require_bridge_dependencies()
        self._ensure_browser()
        response = requests.get(f"{self.debug_url}/json/list", timeout=timeout_s)
        pages = response.json()
        if not isinstance(pages, list):
            raise NodeFailure(
                "CDP /json/list did not return a page list",
                category="cdp_unreachable",
                stage="browser_connect",
            )
        return [dict(page) for page in pages if isinstance(page, Mapping)]

    def _find_browser_page_by_id(
        self,
        target_id: str,
        *,
        attempts: int = 12,
        sleep_s: float = 0.15,
    ) -> Optional[Dict[str, Any]]:
        target = str(target_id or "").strip()
        if not target:
            return None
        for attempt in range(max(1, int(attempts or 1))):
            try:
                pages = self._list_browser_pages(timeout_s=2.0)
            except Exception:
                pages = []
            for page in pages:
                if str(page.get("id", "") or "").strip() == target:
                    return page
            if attempt < attempts - 1:
                time.sleep(max(0.0, float(sleep_s or 0.0)))
        return None

    def _create_browser_target(
        self,
        url: str,
        *,
        background: bool = True,
        new_window: bool = False,
        focus: Optional[bool] = None,
    ) -> Dict[str, Any]:
        # CDP Target.createTarget gained an experimental `focus` parameter
        # (Chrome ~120+) that lets us open a tab without bringing the browser
        # window to the front. Combined with `background=False`, the tab
        # becomes the active tab inside the bridge Chrome window without
        # changing macOS frontmost-app — exactly what the active-background
        # seat needs. Older Chrome versions ignore unknown params, so this
        # extra field is forward-compatible. We only emit `focus` when the
        # caller explicitly asks for it.
        params: Dict[str, Any] = {
            "url": url,
            "background": bool(background),
            "newWindow": bool(new_window),
        }
        if focus is not None:
            params["focus"] = bool(focus)
        response = self._browser_cdp_command(
            "Target.createTarget",
            params,
            timeout_s=max(5.0, self.connection_timeout),
        )
        target_id = str(((response.get("result") or {}).get("targetId")) or "").strip()
        if not target_id:
            raise NodeFailure(
                f"Target.createTarget returned no targetId for {url}",
                category="cdp_unreachable",
                stage="tab_open",
            )
        page = self._find_browser_page_by_id(target_id)
        if page is None:
            raise NodeFailure(
                f"Target.createTarget created {target_id}, but the page never appeared in /json/list",
                category="cdp_unreachable",
                stage="tab_open",
            )
        return page

    def _inspect_page_media_state(self, page: Mapping[str, Any]) -> Dict[str, Any]:
        ws_url = str(page.get("webSocketDebuggerUrl", "") or "").strip()
        page_id = str(page.get("id", "") or "").strip()
        if not ws_url or not page_id:
            return {
                "_media_playing": False,
                "_has_video": False,
                "_has_audio": False,
                "_media_error": "missing_websocket",
            }
        tab: Optional[AgentTab] = None
        try:
            tab = AgentTab(ws_url, page_id, timeout=4.0)
            media = tab.evaluate(
                """
                (function() {
                    const videos = Array.from(document.querySelectorAll('video'));
                    const audios = Array.from(document.querySelectorAll('audio'));
                    const videoPlaying = videos.some(function(node) {
                        return !!node && !node.paused && !node.ended && (node.readyState || 0) >= 2;
                    });
                    const audioPlaying = audios.some(function(node) {
                        return !!node && !node.paused && !node.ended;
                    });
                    return {
                        has_video: videos.length > 0,
                        has_audio: audios.length > 0,
                        media_playing: videoPlaying || audioPlaying,
                        visibility: document.visibilityState || "",
                        active: document.hasFocus()
                    };
                })();
                """
            )
            if isinstance(media, dict):
                return {
                    "_media_playing": bool(media.get("media_playing")),
                    "_has_video": bool(media.get("has_video")),
                    "_has_audio": bool(media.get("has_audio")),
                    "_page_visibility": str(media.get("visibility") or "").strip(),
                    "_page_active": bool(media.get("active")),
                }
        except Exception as exc:
            return {
                "_media_playing": False,
                "_has_video": False,
                "_has_audio": False,
                "_media_error": str(exc),
            }
        finally:
            try:
                if tab is not None:
                    tab.close()
            except Exception:
                pass
        return {
            "_media_playing": False,
            "_has_video": False,
            "_has_audio": False,
        }

    def _build_window_report(
        self,
        pages: Sequence[Mapping[str, Any]],
        *,
        requested_provider: Optional[str] = None,
    ) -> Dict[str, Any]:
        requested = str(requested_provider or "").strip().lower() or None
        windows: Dict[str, Dict[str, Any]] = {}
        provider_tab_ids: list[str] = []
        protected_tab_ids: list[str] = []

        for raw_page in pages:
            if not isinstance(raw_page, Mapping):
                continue
            page_type = str(raw_page.get("_page_type") or raw_page.get("type") or "page").strip().lower()
            if page_type != "page":
                continue
            page_id = str(raw_page.get("id", "") or "").strip()
            role_kind = str(raw_page.get("_role_kind") or "external").strip().lower() or "external"
            role_provider = str(raw_page.get("_role_provider") or "").strip().lower() or None
            window_id = str(raw_page.get("_window_id") or raw_page.get("window_id") or "unknown").strip() or "unknown"
            bounds = raw_page.get("_window_bounds") or raw_page.get("window_bounds") or {}
            if not isinstance(bounds, Mapping):
                bounds = {}
            window = windows.setdefault(
                window_id,
                {
                    "window_id": window_id,
                    "window_state": str(bounds.get("windowState", "") or "").strip().lower() or "unknown",
                    "bounds": dict(bounds),
                    "pages": [],
                },
            )
            page_payload = {
                "id": page_id,
                "title": str(raw_page.get("title", "") or "").strip(),
                "url": str(raw_page.get("url", "") or "").strip(),
                "role": role_kind,
                "provider": role_provider,
                "media_playing": bool(raw_page.get("_media_playing")),
                "has_video": bool(raw_page.get("_has_video")),
                "has_audio": bool(raw_page.get("_has_audio")),
                "visibility": str(raw_page.get("_page_visibility", "") or "").strip() or None,
                "active": bool(raw_page.get("_page_active")),
                "window_lookup_error": str(raw_page.get("_window_error", "") or "").strip() or None,
                "media_error": str(raw_page.get("_media_error", "") or "").strip() or None,
            }
            window["pages"].append(page_payload)

        window_rows: list[Dict[str, Any]] = []
        for window in windows.values():
            pages_in_window = list(window.get("pages", []))
            pages_in_window.sort(
                key=lambda item: (
                    0 if item.get("role") == "provider" else 1,
                    0 if item.get("role") == "external" else 1,
                    str(item.get("title") or ""),
                    str(item.get("id") or ""),
                )
            )
            provider_pages = [item for item in pages_in_window if item.get("role") == "provider"]
            external_pages = [item for item in pages_in_window if item.get("role") == "external"]
            utility_pages = [item for item in pages_in_window if item.get("role") == "utility"]
            if requested:
                requested_pages = [item for item in provider_pages if item.get("provider") == requested]
            else:
                requested_pages = list(provider_pages)
            protection_reasons: list[str] = []
            if requested_pages:
                if external_pages:
                    protection_reasons.append("shared_with_external_page")
                if str(window.get("window_state") or "").strip().lower() == "fullscreen":
                    protection_reasons.append("fullscreen_window")
                if any(bool(item.get("media_playing")) for item in external_pages):
                    protection_reasons.append("external_media_playing")
            protected = bool(protection_reasons)
            requested_ids = [str(item.get("id") or "").strip() for item in requested_pages if str(item.get("id") or "").strip()]
            provider_tab_ids.extend(requested_ids)
            if protected:
                protected_tab_ids.extend(requested_ids)
            window_rows.append(
                {
                    "window_id": window.get("window_id"),
                    "window_state": window.get("window_state"),
                    "bounds": dict(window.get("bounds", {})),
                    "page_count": len(pages_in_window),
                    "provider_page_count": len(provider_pages),
                    "external_page_count": len(external_pages),
                    "utility_page_count": len(utility_pages),
                    "requested_provider_page_count": len(requested_pages),
                    "protected": protected,
                    "protection_reasons": protection_reasons,
                    "pages": pages_in_window,
                }
            )

        window_rows.sort(
            key=lambda item: (
                -int(item.get("requested_provider_page_count", 0) or 0),
                -int(item.get("external_page_count", 0) or 0),
                0 if item.get("protected") else 1,
                str(item.get("window_id") or ""),
            )
        )
        protected_ids = sorted(set(protected_tab_ids))
        all_provider_ids = sorted(set(provider_tab_ids))
        closable_ids = [tab_id for tab_id in all_provider_ids if tab_id not in protected_ids]
        return {
            "captured_at": _utc_now_iso(),
            "requested_provider": requested,
            "profile_path": self.profile_path,
            "debug_url": self.debug_url,
            "window_count": len(window_rows),
            "windows": window_rows,
            "requested_provider_tab_ids": all_provider_ids,
            "protected_tab_ids": protected_ids,
            "closable_tab_ids": closable_ids,
            "protected_window_count": sum(1 for item in window_rows if item.get("protected")),
        }

    def bridge_window_report(
        self,
        *,
        provider: Optional[str] = None,
        include_media: bool = True,
    ) -> Dict[str, Any]:
        report: Dict[str, Any] = {
            "captured_at": _utc_now_iso(),
            "requested_provider": str(provider or "").strip().lower() or None,
            "profile_path": self.profile_path,
            "debug_url": self.debug_url,
            "window_count": 0,
            "windows": [],
            "requested_provider_tab_ids": [],
            "protected_tab_ids": [],
            "closable_tab_ids": [],
            "protected_window_count": 0,
        }
        try:
            pages = self._list_browser_pages(timeout_s=2.0)
        except Exception as exc:
            report["error"] = f"tab_list_failed: {exc}"
            return report

        annotated_pages: list[Dict[str, Any]] = []
        for page in pages:
            item = dict(page)
            item.update(self._classify_browser_page(item))
            page_id = str(item.get("id", "") or "").strip()
            if page_id:
                try:
                    window_result = self._browser_cdp_command(
                        "Browser.getWindowForTarget",
                        {"targetId": page_id},
                        timeout_s=2.5,
                    )
                    result_payload = window_result.get("result") or {}
                    item["_window_id"] = str(result_payload.get("windowId") or "").strip() or "unknown"
                    bounds = result_payload.get("bounds")
                    if isinstance(bounds, Mapping):
                        item["_window_bounds"] = dict(bounds)
                except Exception as exc:
                    item["_window_id"] = "unknown"
                    item["_window_error"] = str(exc)
            if include_media and item.get("_role_kind") == "external":
                item.update(self._inspect_page_media_state(item))
            annotated_pages.append(item)

        built = self._build_window_report(
            annotated_pages,
            requested_provider=str(provider or "").strip().lower() or None,
        )
        report.update(built)
        return report

    # --- Focus coordinator: first-tab-first navigation ---

    def _register_waiting_tab(self, tab: AgentTab, *, meta: Optional[Mapping[str, Any]] = None) -> None:
        """Register a tab as waiting for response. Host focus changes remain policy-gated."""
        with self._waiting_tabs_lock:
            tab_meta = dict(meta or {})
            self._waiting_tabs.append((time.time(), tab, tab_meta))
            self._waiting_tabs.sort(key=lambda x: x[0])
            # If explicitly opted in, focus the oldest waiting tab (first dispatched = most likely to complete).
            oldest_tab = self._waiting_tabs[0][1]
            oldest_meta = self._waiting_tabs[0][2]
            if oldest_tab is tab:
                try:
                    self._focus_tab(tab, meta=oldest_meta, reason="waiting_tab_registered")
                except Exception:
                    pass

    def _unregister_waiting_tab(self, tab: AgentTab) -> None:
        """Unregister a completed tab and focus the next oldest only when policy allows it."""
        with self._waiting_tabs_lock:
            self._waiting_tabs = [(t, tb, meta) for t, tb, meta in self._waiting_tabs if tb is not tab]
            if self._waiting_tabs:
                try:
                    self._focus_tab(
                        self._waiting_tabs[0][1],
                        meta=self._waiting_tabs[0][2],
                        reason="waiting_tab_unregistered",
                    )
                except Exception:
                    pass

    # --- Prompt fidelity verification: exact readback hash over canonicalized text ---

    _PASTE_VERIFY_JS = (
        """(async () => {
        const expectedChars = %EXPECTED_CHARS%;
        const provider = %PROVIDER_JSON%;
"""
        + _BRIDGE_COMPOSER_HELPERS
        + """
        async function sha256Hex(text) {
            const bytes = new TextEncoder().encode(text);
            const digest = await crypto.subtle.digest('SHA-256', bytes);
            return Array.from(new Uint8Array(digest), chunk => chunk.toString(16).padStart(2, '0')).join('');
        }

        const candidates = bridgeCollectComposerCandidates(provider);
        const selectedEl = bridgeResolveComposer(provider, expectedChars);
        if (!selectedEl) {
            return { ok: false, reason: 'no_input_element', length: 0, head: '', middle: '', tail: '', sha256: '' };
        }

        const text = bridgeTextOf(selectedEl);
        const len = text.length;
        const span = Math.min(80, len);
        const middleStart = span > 0 ? Math.max(0, Math.floor((len - span) / 2)) : 0;
        return {
            ok: true,
            reason: 'ok',
            length: len,
            head: text.slice(0, span),
            middle: text.slice(middleStart, middleStart + span),
            tail: text.slice(-span),
            sha256: await sha256Hex(text),
            candidate_count: candidates.length,
            candidate_label: bridgeLabelOf(selectedEl),
            visible: bridgeVisible(selectedEl),
        };
    })()"""
    )

    @staticmethod
    def _canonicalize_prompt_text(text: str) -> str:
        normalized = unicodedata.normalize("NFC", str(text or "").replace("\r\n", "\n").replace("\r", "\n"))
        normalized = normalized.replace("\u00A0", " ").replace("\u202F", " ").replace("\u2007", " ")
        normalized = re.sub(r"[\u200B\u200C\u200D\u2060\uFEFF]", "", normalized)
        return re.sub(r"\n+$", "", normalized)

    @classmethod
    def _prompt_sha256(cls, text: str) -> str:
        canonical = cls._canonicalize_prompt_text(text)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def _evaluate_tab(self, tab: AgentTab, expression: str, *, await_promise: bool = False) -> Any:
        try:
            return tab.evaluate(expression, await_promise=await_promise)
        except TypeError:
            return tab.evaluate(expression)

    def _evaluate_with_timeout(
        self,
        tab: AgentTab,
        expression: str,
        *,
        timeout_s: float = _BRIDGE_EVAL_TIMEOUT_S,
        await_promise: bool = False,
    ) -> Any:
        # Bound a single tab.evaluate by wall-clock so a wedged CDP recv cannot
        # freeze the outer monitor deadline. On timeout, raise BridgeEvaluateStuck;
        # callers in poll loops should treat it as a transient and re-check the
        # outer deadline.
        future = _BRIDGE_EVAL_EXECUTOR.submit(
            self._evaluate_tab, tab, expression, await_promise=await_promise
        )
        try:
            return future.result(timeout=max(1.0, float(timeout_s)))
        except FutureTimeoutError:
            raise BridgeEvaluateStuck(
                f"tab.evaluate exceeded {timeout_s:.1f}s wall-clock budget"
            )

    def _build_paste_verify_js(self, *, provider: str, expected_chars: int) -> str:
        return (
            self._PASTE_VERIFY_JS
            .replace("%EXPECTED_CHARS%", str(max(0, int(expected_chars))))
            .replace("%PROVIDER_JSON%", json.dumps(str(provider or "").strip().lower()))
        )

    def _verify_paste_fidelity(
        self,
        tab: AgentTab,
        prompt: str,
        *,
        provider: str,
        sample_chars: int = 80,
    ) -> Dict[str, Any]:
        """
        After injecting a prompt, read back the input field and verify the canonicalized
        composer text matches the exact intended payload end-to-end.
        """
        canonical_prompt = self._canonicalize_prompt_text(prompt)
        prompt_len = len(canonical_prompt)
        prompt_sha256 = self._prompt_sha256(canonical_prompt)
        span = min(max(20, sample_chars), max(prompt_len, 1))
        middle_start = max(0, (prompt_len - span) // 2)
        expected_head = canonical_prompt[:span]
        expected_middle = canonical_prompt[middle_start : middle_start + span]
        expected_tail = canonical_prompt[-span:] if prompt_len >= span else canonical_prompt
        try:
            result = self._evaluate_tab(
                tab,
                self._build_paste_verify_js(provider=provider, expected_chars=prompt_len),
                await_promise=True,
            )
        except Exception:
            return {
                "verified": False,
                "reason": "js_eval_failed",
                "prompt_len": prompt_len,
                "input_len": 0,
                "match": False,
            }

        if not isinstance(result, dict) or not result.get("ok"):
            return {
                "verified": False,
                "reason": result.get("reason", "unknown") if isinstance(result, dict) else "unknown",
                "prompt_len": prompt_len,
                "input_len": 0,
                "match": False,
            }

        input_len = int(result.get("length", 0) or 0)
        actual_head = str(result.get("head", "") or "")
        actual_middle = str(result.get("middle", "") or "")
        actual_tail = str(result.get("tail", "") or "")
        actual_sha256 = str(result.get("sha256", "") or "").strip().lower()
        head_match = expected_head == actual_head
        middle_match = expected_middle == actual_middle
        tail_match = expected_tail == actual_tail
        matched_segments = sum((head_match, middle_match, tail_match))
        length_match = input_len == prompt_len
        sha256_match = actual_sha256 == prompt_sha256
        # Tolerate small length differences (±10 chars) when the SHA256
        # matches.  ChatGPT's editor often adds a trailing newline or
        # zero-width character that changes the reported length but not
        # the canonical content hash.  Requiring exact length when the
        # hash already proves content integrity caused repeated
        # provider_submit_failed_fast on large prompts.
        length_close = abs(input_len - prompt_len) <= 10
        match = bool(sha256_match and (length_match or length_close))

        return {
            "verified": True,
            "prompt_len": prompt_len,
            "input_len": input_len,
            "match": match,
            "length_ratio": round(input_len / max(prompt_len, 1), 3),
            "length_match": length_match,
            "sha256_match": sha256_match,
            "prompt_sha256": prompt_sha256,
            "input_sha256": actual_sha256,
            "head_match": head_match,
            "middle_match": middle_match,
            "tail_match": tail_match,
            "matched_segments": matched_segments,
            "candidate_count": int(result.get("candidate_count", 0) or 0),
            "candidate_label": str(result.get("candidate_label", "") or ""),
            "visible": bool(result.get("visible")),
        }

    def _ensure_prompt_fidelity(
        self,
        tab: AgentTab,
        prompt: str,
        *,
        provider: str,
        transport_name: str,
    ) -> Dict[str, Any]:
        """
        Verify that the provider composer still contains the intended prompt after a
        transport step. A persistent mismatch is treated as a transport failure so
        callers can retry on a fresh tab with a safer transport.
        """
        paste_check = self._verify_paste_fidelity(tab, prompt, provider=provider)
        if paste_check.get("verified") and paste_check.get("match"):
            return paste_check

        extra_wait = min(5.0, max(0.5, len(prompt) / 200_000))
        self._jittered_sleep(extra_wait)
        paste_check = self._verify_paste_fidelity(tab, prompt, provider=provider)
        if paste_check.get("verified") and paste_check.get("match"):
            return paste_check

        raise NodeFailure(
            (
                f"{provider} prompt transport {transport_name} failed fidelity check "
                f"(prompt={paste_check.get('prompt_len', len(prompt))}, "
                f"input={paste_check.get('input_len', 0)}, "
                f"ratio={paste_check.get('length_ratio', 0)}, "
                f"sha_match={paste_check.get('sha256_match', False)})"
            ),
            category="provider_input_corrupt",
            stage="provider_input",
            provider=provider,
            details={
                "transport": transport_name,
                **paste_check,
            },
        )

    def _transport_specs(
        self,
        preferred_order: Optional[list[str]] = None,
        *,
        allow_global_input_transport: Optional[bool] = None,
    ) -> list[tuple[str, Callable[[AgentTab, str, str], None]]]:
        transport_map: Dict[str, Callable[[AgentTab, str, str], None]] = {
            "cdp_input": self._submit_prompt_cdp_input,
            "dom_inject_click": self._submit_prompt_dom,
            "native_macos_input": self._submit_prompt_native,
        }
        allow_global = (
            bool(self.allow_global_input_transport)
            if allow_global_input_transport is None
            else bool(allow_global_input_transport)
        )
        order = preferred_order if isinstance(preferred_order, list) else list(self.transport_order)
        normalized: list[tuple[str, Callable[[AgentTab, str, str], None]]] = []
        for item in order:
            name = str(item).strip()
            if not name or name in {entry[0] for entry in normalized}:
                continue
            if name in GLOBAL_INPUT_TRANSPORTS and not allow_global:
                continue
            transport_fn = transport_map.get(name)
            if transport_fn is not None:
                normalized.append((name, transport_fn))
        return normalized

    def _emit_bridge_event(
        self,
        *,
        provider: str,
        phase: str,
        meta: Optional[Dict[str, Any]] = None,
        tab_id: Optional[str] = None,
        status: str = "ok",
        detail: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        timestamp = _utc_now_iso()
        event_meta = dict(meta or {})
        session_id = str(event_meta.get("session_id") or "").strip() or f"adhoc:{provider}"
        payload_detail = dict(detail or {})
        node_id = str(event_meta.get("node_id") or "").strip() or None
        lane = str(event_meta.get("lane") or "").strip() or None
        transport = str(event_meta.get("transport_name") or "").strip() or None
        run_kind = str(event_meta.get("run_kind") or "").strip().lower() or None
        resume_of_observe_id = str(event_meta.get("resume_of_observe_id") or "").strip() or None
        resume_manifest_path = str(event_meta.get("resume_manifest_path") or "").strip() or None

        with self._bridge_event_lock:
            state = _read_bridge_state()
            runtime = state.get("runtime")
            if not isinstance(runtime, dict):
                runtime = {}
            sessions = runtime.get("sessions")
            if not isinstance(sessions, dict):
                sessions = {}
            session_state = sessions.get(session_id)
            if not isinstance(session_state, dict):
                session_state = {
                    "session_id": session_id,
                    "started_at": timestamp,
                    "updated_at": timestamp,
                    "providers": {},
                }
                sessions[session_id] = session_state
            if run_kind:
                session_state["run_kind"] = run_kind
            if resume_of_observe_id:
                session_state["resume_of_observe_id"] = resume_of_observe_id
            if resume_manifest_path:
                session_state["resume_manifest_path"] = resume_manifest_path
            providers = session_state.get("providers")
            if not isinstance(providers, dict):
                providers = {}
                session_state["providers"] = providers
            provider_state = providers.get(provider)
            if not isinstance(provider_state, dict):
                provider_state = {"tabs": {}, "recent_events": []}
                providers[provider] = provider_state
            tabs = provider_state.get("tabs")
            if not isinstance(tabs, dict):
                tabs = {}
                provider_state["tabs"] = tabs
            recent_events = provider_state.get("recent_events")
            if not isinstance(recent_events, list):
                recent_events = []
            started_at = _parse_iso_timestamp(session_state.get("started_at")) or datetime.now(timezone.utc)
            elapsed_ms = max(0.0, (datetime.now(timezone.utc) - started_at).total_seconds() * 1000.0)

            event_payload = {
                "event_id": str(uuid.uuid4()),
                "timestamp": timestamp,
                "session_id": session_id,
                "provider": provider,
                "tab_id": tab_id,
                "phase": phase,
                "status": status,
                "node_id": node_id,
                "lane": lane,
                "transport": transport,
                "run_kind": run_kind,
                "resume_of_observe_id": resume_of_observe_id,
                "resume_manifest_path": resume_manifest_path,
                "elapsed_ms": round(elapsed_ms, 1),
                "detail": payload_detail,
            }
            _append_bridge_event(event_payload)

            if tab_id:
                if phase == "tab_closed":
                    tabs.pop(tab_id, None)
                else:
                    tab_state = tabs.get(tab_id)
                    if not isinstance(tab_state, dict):
                        tab_state = {"id": tab_id}
                    tab_state.update(
                        {
                            "id": tab_id,
                            "phase": phase,
                            "status": status,
                            "updated_at": timestamp,
                            "node_id": node_id,
                            "lane": lane,
                            "transport": transport,
                        }
                    )
                    for key in (
                        "editor_length",
                        "response_chars",
                        "response_count",
                        "response_started",
                        "start_signal",
                        "provider_interaction_wait_s",
                        "composer_state",
                        "wait_state",
                        "wait_status",
                        "attempt_id",
                        "category",
                        "stage",
                    ):
                        if key in payload_detail:
                            tab_state[key] = payload_detail[key]
                    if "message" in payload_detail:
                        tab_state["message"] = payload_detail["message"]
                    tabs[tab_id] = tab_state

            recent_event = {
                "timestamp": timestamp,
                "phase": phase,
                "status": status,
                "tab_id": tab_id,
                "node_id": node_id,
                "lane": lane,
                "transport": transport,
                "run_kind": run_kind,
                "resume_of_observe_id": resume_of_observe_id,
            }
            for key in (
                "response_chars",
                "response_count",
                "response_started",
                "editor_length",
                "wait_status",
                "wait_state",
                "category",
                "stage",
            ):
                if key in payload_detail:
                    recent_event[key] = payload_detail[key]
            if "message" in payload_detail:
                recent_event["message"] = payload_detail["message"]
            recent_events.append(recent_event)
            provider_state["recent_events"] = recent_events[-25:]
            provider_state["updated_at"] = timestamp
            session_state["updated_at"] = timestamp
            runtime["sessions"] = sessions

            overall_recent = runtime.get("recent_events")
            if not isinstance(overall_recent, list):
                overall_recent = []
            overall_event = {
                "timestamp": timestamp,
                "session_id": session_id,
                "provider": provider,
                "phase": phase,
                "status": status,
                "tab_id": tab_id,
                "node_id": node_id,
                "lane": lane,
                "transport": transport,
                "run_kind": run_kind,
                "resume_of_observe_id": resume_of_observe_id,
            }
            for key in (
                "response_chars",
                "response_count",
                "response_started",
                "wait_status",
                "category",
                "stage",
            ):
                if key in payload_detail:
                    overall_event[key] = payload_detail[key]
            if "message" in payload_detail:
                overall_event["message"] = payload_detail["message"]
            overall_recent.append(overall_event)
            runtime["recent_events"] = overall_recent[-100:]
            state["runtime"] = runtime
            state["updated_at"] = timestamp
            _write_bridge_state(state)
        return event_payload

    def _recent_bridge_events(
        self,
        *,
        provider: Optional[str] = None,
        session_id: Optional[str] = None,
        limit: int = 25,
    ) -> list[Dict[str, Any]]:
        path = _bridge_event_log_path()
        if not path.exists():
            return []
        events: list[Dict[str, Any]] = []
        try:
            for line in path.read_text(encoding="utf-8").splitlines():
                raw = line.strip()
                if not raw:
                    continue
                payload = json.loads(raw)
                if not isinstance(payload, dict):
                    continue
                if provider and str(payload.get("provider") or "").strip() != str(provider).strip():
                    continue
                if session_id and str(payload.get("session_id") or "").strip() != str(session_id).strip():
                    continue
                events.append(dict(payload))
        except Exception:
            return []
        return events[-max(1, int(limit or 25)) :]

    def _provider_interaction_lock(self, provider: str) -> threading.Lock:
        key = str(provider or "").strip().lower()
        with self._manager_lock:
            lock = self._provider_interaction_locks.get(key)
            if lock is None:
                lock = threading.Lock()
                self._provider_interaction_locks[key] = lock
            return lock

    def _provider_process_lock_path(self, provider: str) -> Path:
        key = str(provider or "").strip().lower() or "default"
        return _bridge_locks_dir() / f"{key}.lock"

    def _read_provider_process_owner(self, provider: str) -> Optional[Dict[str, Any]]:
        path = self._provider_process_lock_path(provider)
        if not path.exists():
            return None
        try:
            raw = path.read_text(encoding="utf-8").strip()
        except Exception:
            return None
        if not raw:
            return None
        try:
            payload = json.loads(raw)
        except Exception:
            return None
        return dict(payload) if isinstance(payload, dict) else None

    @staticmethod
    def _pid_is_live(pid: Any) -> bool:
        try:
            value = int(pid)
        except (TypeError, ValueError):
            return False
        if value <= 0:
            return False
        try:
            os.kill(value, 0)
        except OSError:
            return False
        return True

    def _provider_interaction_snapshot(self, provider: Optional[str] = None) -> Dict[str, Any]:
        with self._manager_lock:
            if provider is not None:
                key = str(provider or "").strip().lower()
                active = self._provider_interaction_active.get(key)
                process_owner = self._read_provider_process_owner(key)
                process_owner_live = self._pid_is_live((process_owner or {}).get("process_id"))
                owner = dict(active) if isinstance(active, dict) else (
                    dict(process_owner) if isinstance(process_owner, dict) and process_owner_live else None
                )
                return {
                    "provider": key,
                    "serialized": True,
                    "queued": int(self._provider_interaction_waiters.get(key, 0) or 0),
                    "active": bool(active) or bool(process_owner_live),
                    "owner": owner,
                    "cross_process_active": bool(process_owner_live),
                    "cross_process_owner": (
                        dict(process_owner) if isinstance(process_owner, dict) and process_owner_live else None
                    ),
                    "cross_process_stale_owner": (
                        dict(process_owner) if isinstance(process_owner, dict) and not process_owner_live else None
                    ),
                }
            providers = set(self._provider_interaction_locks.keys()) | set(self._provider_interaction_waiters.keys()) | set(self._provider_interaction_active.keys())
            return {
                "serialized": True,
                "providers": {
                    key: {
                        "queued": int(self._provider_interaction_waiters.get(key, 0) or 0),
                        "active": bool(self._provider_interaction_snapshot(key).get("active")),
                        "owner": self._provider_interaction_snapshot(key).get("owner"),
                    }
                    for key in sorted(providers)
                },
            }

    @contextmanager
    def _provider_process_interaction_context(
        self,
        provider: str,
        *,
        cancel: Optional[threading.Event] = None,
        owner: Optional[Dict[str, Any]] = None,
    ):
        key = str(provider or "").strip().lower()
        if not key or fcntl is None:
            yield {"lock_path": None, "cross_process_owner": None}
            return

        lock_path = self._provider_process_lock_path(key)
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        poll_s = max(0.05, float(self.timings.get("provider_lock_poll_s", 0.25) or 0.25))
        handle = lock_path.open("a+", encoding="utf-8")
        acquired = False
        try:
            while not acquired:
                if cancel and cancel.is_set():
                    raise NodeFailure(
                        "Aborted while waiting for provider interaction slot",
                        category="provider_timeout",
                        stage="provider_queue",
                        provider=key,
                        details={
                            "provider_interaction": self._provider_interaction_snapshot(key),
                        },
                    )
                try:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    acquired = True
                except BlockingIOError:
                    time.sleep(poll_s)
            owner_payload = dict(owner or {})
            owner_payload.setdefault("process_id", os.getpid())
            owner_payload.setdefault("lock_path", str(lock_path))
            handle.seek(0)
            handle.truncate()
            handle.write(json.dumps(owner_payload, ensure_ascii=False, indent=2))
            handle.flush()
            try:
                os.fsync(handle.fileno())
            except OSError:
                pass
            yield {"lock_path": str(lock_path), "cross_process_owner": owner_payload}
        finally:
            if acquired:
                try:
                    handle.seek(0)
                    handle.truncate()
                    handle.flush()
                    try:
                        os.fsync(handle.fileno())
                    except OSError:
                        pass
                except Exception:
                    pass
                try:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
                except Exception:
                    pass
            try:
                handle.close()
            except Exception:
                pass

    @contextmanager
    def _provider_interaction_context(
        self,
        provider: str,
        *,
        cancel: Optional[threading.Event] = None,
        meta: Optional[Dict[str, Any]] = None,
    ):
        key = str(provider or "").strip().lower()
        if not key:
            yield {"wait_s": 0.0, "provider_interaction": None}
            return

        lock = self._provider_interaction_lock(key)
        poll_s = max(0.05, float(self.timings.get("provider_lock_poll_s", 0.25) or 0.25))
        wait_started = time.monotonic()
        waiter_registered = False
        acquired = False
        owner: Optional[Dict[str, Any]] = None
        try:
            with self._manager_lock:
                self._provider_interaction_waiters[key] = int(self._provider_interaction_waiters.get(key, 0) or 0) + 1
                waiter_registered = True
            while not acquired:
                if cancel and cancel.is_set():
                    raise NodeFailure(
                        "Aborted while waiting for provider interaction slot",
                        category="provider_timeout",
                        stage="provider_queue",
                        provider=key,
                        details={
                            "provider_interaction_wait_s": max(0.0, time.monotonic() - wait_started),
                            "provider_interaction": self._provider_interaction_snapshot(key),
                        },
                    )
                acquired = lock.acquire(timeout=poll_s)
            wait_s = max(0.0, time.monotonic() - wait_started)
            owner = {
                "node_id": str((meta or {}).get("node_id") or "").strip() or None,
                "lane": str((meta or {}).get("lane") or "").strip() or None,
                "transport": str((meta or {}).get("transport_name") or "").strip() or None,
                "process_id": os.getpid(),
                "thread_id": threading.get_ident(),
                "thread_name": threading.current_thread().name,
                "acquired_at": _utc_now_iso(),
                "wait_s": wait_s,
            }
            with self._manager_lock:
                if waiter_registered:
                    self._provider_interaction_waiters[key] = max(0, int(self._provider_interaction_waiters.get(key, 0) or 0) - 1)
                    waiter_registered = False
                self._provider_interaction_active[key] = dict(owner)
            with self._provider_process_interaction_context(
                key,
                cancel=cancel,
                owner=owner,
            ) as process_slot:
                with self._manager_lock:
                    active_owner = self._provider_interaction_active.get(key)
                    if isinstance(active_owner, dict):
                        active_owner["cross_process_lock_path"] = process_slot.get("lock_path")
                yield {
                    "wait_s": wait_s,
                    "provider_interaction": self._provider_interaction_snapshot(key),
                    "cross_process_lock_path": process_slot.get("lock_path"),
                }
        finally:
            if acquired:
                with self._manager_lock:
                    active = self._provider_interaction_active.get(key)
                    if not isinstance(active, dict) or not isinstance(owner, dict) or active.get("thread_id") == owner.get("thread_id"):
                        self._provider_interaction_active.pop(key, None)
                lock.release()
            elif waiter_registered:
                with self._manager_lock:
                    self._provider_interaction_waiters[key] = max(0, int(self._provider_interaction_waiters.get(key, 0) or 0) - 1)

    def _resolve_provider(self, config: Optional[Dict[str, Any]], provider: Optional[str] = None) -> str:
        candidate = str(provider or "").strip().lower()
        if candidate:
            return candidate
        bridge_cfg = config.get("bridge", config) if isinstance(config, dict) else {}
        default_target = str(_rv(bridge_cfg.get("default_target"), "") or "").strip().lower()
        if default_target:
            return default_target
        return "chatgpt"

    def _load_provider_state(self, provider: str) -> Dict[str, Any]:
        payload = _read_bridge_state()
        providers = payload.get("providers", {})
        if not isinstance(providers, dict):
            providers = {}
        state = providers.get(provider, {})
        return dict(state) if isinstance(state, dict) else {}

    def _save_provider_state(self, provider: str, provider_state: Dict[str, Any]) -> Dict[str, Any]:
        payload = _read_bridge_state()
        providers = payload.get("providers")
        if not isinstance(providers, dict):
            providers = {}
        providers[provider] = dict(provider_state)
        payload["providers"] = providers
        payload["updated_at"] = _utc_now_iso()
        _write_bridge_state(payload)
        return dict(provider_state)

    def _provider_staleness(self, provider: str) -> Dict[str, Any]:
        state = self._load_provider_state(provider)
        last_success = _parse_iso_timestamp(state.get("last_ready_at") or state.get("last_successful_run_at") or state.get("last_successful_preflight_at"))
        last_failure = _parse_iso_timestamp(state.get("last_failure_at"))
        if last_success is None:
            return {
                "stale": True,
                "reason": "no_success_recorded",
                "provider_state": state,
                "last_success_age_s": None,
            }
        if last_failure is not None and last_failure > last_success:
            return {
                "stale": True,
                "reason": "last_failure_after_success",
                "provider_state": state,
                "last_success_age_s": max(0.0, (datetime.now(timezone.utc) - last_success).total_seconds()),
            }
        age_s = max(0.0, (datetime.now(timezone.utc) - last_success).total_seconds())
        if age_s > self.stale_after_s:
            return {
                "stale": True,
                "reason": f"stale_after_{int(self.stale_after_s)}s",
                "provider_state": state,
                "last_success_age_s": age_s,
            }
        return {
            "stale": False,
            "reason": "fresh",
            "provider_state": state,
            "last_success_age_s": age_s,
        }

    def _record_provider_success(self, provider: str, *, event: str, details: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        with self._manager_lock:
            state = self._load_provider_state(provider)
            now = _utc_now_iso()
            state["last_checked_at"] = now
            state["last_ready_at"] = now
            state["last_status"] = "ready"
            state["last_event"] = event
            state["last_error"] = None
            state["last_failure_category"] = None
            state["last_failure_stage"] = None
            if event == "preflight":
                state["last_successful_preflight_at"] = now
            elif event == "run":
                state["last_successful_run_at"] = now
            if details:
                state["last_success_details"] = dict(details)
            return self._save_provider_state(provider, state)

    def _record_provider_failure(
        self,
        provider: str,
        *,
        event: str,
        category: str,
        stage: Optional[str],
        message: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        # Active-background seat failure tagging: when the ChatGPT bridge runs
        # in active_background_seat mode and we hit provider_timeout in the
        # provider_wait stage, decorate the recorded category with
        # _background_mode_failed so downstream consumers (the validation
        # receipt, metabolismd reaction policy, the trickle drain loop) can
        # distinguish "page-not-streaming-while-backgrounded" from generic
        # provider timeout. We do NOT silently fall back to a foreground
        # focus pulse — that's the operator's explicit choice if they want
        # it. The failure is surfaced as-is for explicit handling.
        normalized_category = str(category or "")
        if (
            str(provider or "").strip().lower() == "chatgpt"
            and normalized_category == "provider_timeout"
            and str(stage or "") == "provider_wait"
            and self._chatgpt_active_background_seat_enabled()
        ):
            normalized_category = "provider_timeout_background_mode_failed"
        with self._manager_lock:
            state = self._load_provider_state(provider)
            now = _utc_now_iso()
            state["last_checked_at"] = now
            state["last_failure_at"] = now
            state["last_status"] = "error"
            state["last_event"] = event
            state["last_error"] = message
            state["last_failure_category"] = normalized_category
            state["last_failure_stage"] = stage
            if details:
                state["last_failure_details"] = dict(details)
            return self._save_provider_state(provider, state)

    def get_status(self, config: Optional[Dict[str, Any]] = None, provider: Optional[str] = None) -> Dict[str, Any]:
        """
        [ACTION]
        - Teleology: Report health status of the Bridge.
        - Guarantee: Returns a dictionary with at least 'configured' and 'browser_running'.
        - Fails: None.
        
        """
        _require_bridge_dependencies()
        with self._manager_lock:
            if config is not None:
                self.ensure_configured(config)
            # 1. Internal Process Check
            internal_alive = self._browser_process is not None and self._browser_process.poll() is None
            
            # 2. External Port Check (Adoption)
            external_alive = False
            try:
                requests.get(f"{self.debug_url}/json/version", timeout=0.15)
                external_alive = True
            except Exception:
                pass

            is_alive = internal_alive or external_alive
            state_path = _bridge_state_path()
            try:
                state_file = str(state_path.relative_to(_bridge_repo_root()))
            except ValueError:
                state_file = str(state_path)

            status: Dict[str, Any] = {
                "configured": self._is_configured or is_alive,
                "browser_running": is_alive,
                "managed_browser_running": internal_alive,
                "cdp_reachable": external_alive,
                "debug_url": self.debug_url,
                "state_file": state_file,
            }
            runtime_state = _read_bridge_state()
            known_providers = set(self.targets.keys())
            persisted = runtime_state.get("providers", {})
            if isinstance(persisted, dict):
                known_providers.update(str(key).strip() for key in persisted.keys() if str(key).strip())
            runtime = runtime_state.get("runtime")
            if isinstance(runtime, dict):
                sessions = runtime.get("sessions")
                if isinstance(sessions, dict):
                    for session_payload in sessions.values():
                        if not isinstance(session_payload, Mapping):
                            continue
                        providers = session_payload.get("providers")
                        if not isinstance(providers, Mapping):
                            continue
                        known_providers.update(
                            str(key).strip()
                            for key in providers.keys()
                            if str(key).strip()
                        )
            provider_states: Dict[str, Any] = {}
            for name in sorted(known_providers):
                staleness = self._provider_staleness(name)
                state = dict(staleness.get("provider_state", {}))
                interaction = self._provider_interaction_snapshot(name)
                active_progress = _select_active_runtime_progress(runtime_state, provider=name)
                state["stale"] = bool(staleness.get("stale"))
                state["stale_reason"] = staleness.get("reason")
                state["last_success_age_s"] = staleness.get("last_success_age_s")
                state["target_url"] = self.targets.get(name)
                state["interaction_serialized"] = bool(interaction.get("serialized"))
                state["interaction_active"] = bool(interaction.get("active"))
                state["interaction_waiters"] = int(interaction.get("queued", 0) or 0)
                state["interaction_owner"] = interaction.get("owner")
                state["active_progress"] = dict(active_progress) if isinstance(active_progress, Mapping) else None
                provider_states[name] = state
            status["providers"] = provider_states
            resolved_provider = self._resolve_provider(config or {}, provider)
            if resolved_provider:
                provider_status = provider_states.get(resolved_provider, {})
                status["provider"] = resolved_provider
                status["provider_status"] = provider_status
                status["stale"] = provider_status.get("stale")
                status["stale_reason"] = provider_status.get("stale_reason")
                status["active_progress"] = provider_status.get("active_progress")
            return status

    def ensure_configured(self, config: Dict[str, Any]) -> None:
        """
        [ACTION]
        - Teleology: Lazy initialization of Bridge settings from config.
        - Mechanism: Updates timeouts, paths, and targets under `_manager_lock`.
        - Guarantee: BridgeManager runtime configuration reflects the provided config.
        - Fails: None.
        
        """
        with self._manager_lock:
            bridge_cfg = config.get("bridge", config) if isinstance(config, dict) else {}

            if not self._is_configured:
                # [FIX] Use _rv to safely unwrap {value, desc} objects if present
                self.debug_port = int(_rv(bridge_cfg.get("debug_port"), self.debug_port))
                self.debug_url = f"http://localhost:{self.debug_port}"
                self.chrome_bin = str(_rv(bridge_cfg.get("chrome_bin"), self.chrome_bin))
                
                # [CRITICAL] Use profile from config if available, else default
                raw_path = str(_rv(bridge_cfg.get("user_data_dir"), self.profile_path))
                self.profile_path = os.path.expanduser(raw_path)

                raw_ext = _rv(bridge_cfg.get("allow_extensions"), self.allow_extensions)
                self.allow_extensions = bool(raw_ext)
                
                self._is_configured = True

            self.connection_timeout = float(_rv(bridge_cfg.get("connection_timeout"), self.connection_timeout))
            self.monitor_timeout_s = float(_rv(bridge_cfg.get("monitor_timeout_s"), self.monitor_timeout_s))
            self.poll_interval_s = float(_rv(bridge_cfg.get("poll_interval_s"), self.poll_interval_s))
            self.jitter_ratio = float(_rv(bridge_cfg.get("jitter_ratio"), self.jitter_ratio))
            self.stale_after_s = float(_rv(bridge_cfg.get("stale_after_s"), self.stale_after_s))
            self.retryable_session_attempts = max(
                1,
                int(_rv(bridge_cfg.get("retryable_session_attempts"), self.retryable_session_attempts)),
            )

            # [STRICT] targets is a flat map, do not unwrap
            if "targets" in bridge_cfg:
                self.targets.update(bridge_cfg["targets"])
            
            # [FIX] timings must be unwrapped individually
            if "timings" in bridge_cfg:
                for k, v in bridge_cfg["timings"].items():
                    self.timings[k] = float(_rv(v, self.timings.get(k, 0)))

            policy_cfg = bridge_cfg.get("host_focus_policy")
            if isinstance(policy_cfg, Mapping):
                self._configure_host_focus_policy(policy_cfg)

            # [NEW] Multi-account substrate scheduler
            accounts_cfg = bridge_cfg.get("accounts")
            if isinstance(accounts_cfg, dict):
                self.substrate_scheduler.configure(accounts_cfg)

            # [NEW] Tab reuse toggle
            raw_reuse = _rv(bridge_cfg.get("reuse_existing_tabs"), None)
            if raw_reuse is not None:
                self.reuse_existing_tabs = bool(raw_reuse)

    def _resolve_macos_chrome_app(self, chrome_bin: str) -> Optional[str]:
        """
        Resolve a Chrome app bundle path on macOS so LaunchServices can own startup.
        """
        expanded = os.path.expanduser(chrome_bin)
        if expanded.endswith(".app") and os.path.exists(expanded):
            return expanded

        marker = ".app/Contents/MacOS/"
        marker_index = expanded.find(marker)
        if marker_index >= 0:
            app_bundle = expanded[: marker_index + len(".app")]
            if os.path.exists(app_bundle):
                return app_bundle

        if chrome_bin == "google-chrome":
            default_app = "/Applications/Google Chrome.app"
            if os.path.exists(default_app):
                return default_app
        return None

    def _build_chrome_launch_command(self) -> tuple[list[str], bool]:
        """
        Build the browser launch command and signal whether LaunchServices is used.
        """
        chrome_bin = self.chrome_bin
        is_macos = platform.system().lower() == "darwin"

        if is_macos and not os.path.exists(chrome_bin):
            mac_default = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
            if os.path.exists(mac_default):
                chrome_bin = mac_default
                self.chrome_bin = mac_default

        mac_app = self._resolve_macos_chrome_app(chrome_bin) if is_macos else None
        if shutil.which(chrome_bin) is None and not os.path.exists(chrome_bin) and mac_app is None:
            raise NodeFailure(
                f"Chrome binary not found: {chrome_bin}",
                category="browser_launch_failed",
                stage="browser_launch",
            )

        chrome_args = [
            f"--remote-debugging-port={self.debug_port}",
            f"--user-data-dir={self.profile_path}",
            "--no-first-run",
            "--no-default-browser-check",
            "--remote-allow-origins=*",
        ]
        if not self.allow_extensions:
            chrome_args += [
                "--disable-extensions",
                "--disable-component-extensions-with-background-pages",
            ]
        # ChatGPT active-background seat: when this bridge profile is in
        # active_background_seat mode, Chrome itself must NOT throttle the
        # backgrounded tab's timers, freeze the renderer, or treat the window
        # as occluded. The visibility-patch JS makes the page-side checks
        # report "visible/focused"; these flags address Chrome's own
        # renderer-level throttling, which the JS patch cannot reach.
        if self._chatgpt_active_background_seat_enabled():
            chrome_args += [
                "--disable-background-timer-throttling",
                "--disable-renderer-backgrounding",
                "--disable-backgrounding-occluded-windows",
                "--disable-features=IntensiveWakeUpThrottling",
            ]
        if is_macos and mac_app and self.allow_host_focus:
            return (["open", "-n", "-a", mac_app, "--args", *chrome_args], True)
        if is_macos and mac_app and chrome_bin.endswith(".app"):
            app_executable = os.path.join(mac_app, "Contents", "MacOS", Path(mac_app).stem)
            if os.path.exists(app_executable):
                chrome_bin = app_executable
                self.chrome_bin = app_executable
        return ([chrome_bin, *chrome_args], False)

    def _ensure_browser(self) -> None:
        """
        [ACTION]
        - Teleology: Guarantee a reachable Chrome CDP endpoint (launch or adopt).
        """
        _require_bridge_dependencies()
        with self._manager_lock:
            if not self._is_configured:
                self.ensure_configured({})

            # 1. Check if already running (Adoption)
            try:
                requests.get(f"{self.debug_url}/json/version", timeout=1.5)
                return
            except Exception:
                self.logger.info(f"Chrome not found at {self.debug_port}. Launching...")

            # 2. Validate Binary
            os.makedirs(self.profile_path, exist_ok=True)
            args, launched_via_open = self._build_chrome_launch_command()

            # 3. Launch
            popen_kwargs: Dict[str, Any] = {
                "stdout": subprocess.DEVNULL,
                "stderr": subprocess.DEVNULL,
            }
            if platform.system().lower() != "darwin" and hasattr(os, "setsid"):
                popen_kwargs["preexec_fn"] = os.setsid
            try:
                self._browser_process = subprocess.Popen(args, **popen_kwargs)
            except Exception as e:
                raise NodeFailure(
                    f"Failed to launch Chrome: {e}",
                    category="browser_launch_failed",
                    stage="browser_launch",
                ) from e

            # 4. Wait
            time.sleep(2.0 if launched_via_open else 4.0)
            deadline = time.time() + max(8.0, self.connection_timeout)
            while time.time() < deadline:
                if self._browser_process is not None:
                    returncode = self._browser_process.poll()
                    if returncode is not None and not launched_via_open:
                        raise NodeFailure(
                            f"Chrome launcher exited before CDP endpoint became ready (exit code {returncode})",
                            category="browser_launch_failed",
                            stage="browser_launch",
                        )
                try:
                    requests.get(f"{self.debug_url}/json/version", timeout=1.0)
                    return
                except Exception:
                    time.sleep(0.35)
            raise NodeFailure(
                "Chrome launched but CDP endpoint did not become ready",
                category="cdp_unreachable",
                stage="browser_connect",
            )

    def _jittered_sleep(self, base: float) -> None:
        """Sleep for base ± jitter_ratio*base seconds. Makes timing look human."""
        jitter = self.jitter_ratio
        time.sleep(base * (1 + random.uniform(-jitter, jitter)))

    def _sleep_with_cancel(
        self,
        base: float,
        *,
        cancel: Optional[threading.Event] = None,
        provider: Optional[str] = None,
        stage: str = "provider_wait",
        message: str = "Aborted while waiting",
    ) -> None:
        delay = max(0.0, float(base or 0.0))
        if cancel is None:
            if delay > 0:
                self._jittered_sleep(delay)
            return
        if cancel.is_set():
            raise NodeFailure(
                message,
                category="provider_timeout",
                stage=stage,
                provider=provider,
            )
        jitter = self.jitter_ratio
        delay *= 1 + random.uniform(-jitter, jitter)
        deadline = time.time() + max(0.0, delay)
        while True:
            if cancel.is_set():
                raise NodeFailure(
                    message,
                    category="provider_timeout",
                    stage=stage,
                    provider=provider,
                )
            remaining = deadline - time.time()
            if remaining <= 0:
                return
            time.sleep(min(0.1, remaining))

    def _check_provider_js_result(self, provider: str, result: Any, *, stage: str) -> None:
        text = str(result or "").strip()
        if text and not text.startswith("ERROR"):
            return
        raise NodeFailure(
            f"{provider} UI interaction failed: {text or 'missing success signal'}",
            category="provider_selector_failure",
            stage=stage,
            provider=provider,
        )

    @staticmethod
    def _prompt_char_count(prompt: str) -> int:
        return max(0, len(str(prompt or "")))

    def _scaled_timeout(
        self,
        prompt: str,
        *,
        base_key: str,
        default_base: float,
        per_100k_key: str,
        default_per_100k: float,
        cap_key: str,
        default_cap: float,
    ) -> float:
        prompt_chars = self._prompt_char_count(prompt)
        base = float(self.timings.get(base_key, default_base) or default_base)
        per_100k = float(self.timings.get(per_100k_key, default_per_100k) or default_per_100k)
        cap = float(self.timings.get(cap_key, default_cap) or default_cap)
        extra = (prompt_chars / 100000.0) * per_100k
        return max(1.0, min(cap, base + extra))

    def _dom_inject_settle_seconds(self, prompt: str) -> float:
        """Extra sleep after DOM inject so huge prompts hydrate before fidelity/submit."""
        base = float(self.timings.get("flush_sleep", 0.5) or 0.5)
        pc = self._prompt_char_count(prompt)
        if pc <= 0:
            return base
        # Up to +15s for very large observe dumps (ProseMirror/React lag behind innerText).
        extra = min(15.0, pc / 35_000.0)
        return base + extra

    def _provider_compose_state(self, tab: AgentTab, provider: str) -> Dict[str, Any]:
        if provider == "gemini":
            return self._gemini_compose_state(tab)
        if provider == "chatgpt":
            return self._chatgpt_compose_state(tab)
        return {}

    def _provider_start_baseline(self, tab: AgentTab, provider: str) -> Dict[str, Any]:
        baseline = self._snapshot_response_state(tab, provider)
        adapter = self._provider_adapter(provider)
        if adapter.composer_state_js:
            baseline.update(self._provider_compose_state(tab, provider))
        return baseline

    def _run_preflight_audit(self, tab: AgentTab, provider: str) -> Dict[str, Any]:
        adapter = self._provider_adapter(provider)
        audit_js = adapter.preflight_audit_js
        if not audit_js:
            return {"warnings": ["AUDIT_NOT_CONFIGURED"]}
        report = tab.evaluate(audit_js)
        normalized = dict(report) if isinstance(report, dict) else {"warnings": ["AUDIT_RETURN_INVALID"]}
        if adapter.composer_state_js:
            normalized["composer_state"] = self._provider_compose_state(tab, provider)
        try:
            self._clear_provider_input(tab, provider)
        except Exception as exc:
            warnings = normalized.get("warnings")
            if not isinstance(warnings, list):
                warnings = []
            warnings.append(f"CLEAR_FAILED:{exc}")
            normalized["warnings"] = warnings
        return normalized

    def _wake_provider_input(self, tab: AgentTab, provider: str) -> None:
        adapter = self._provider_adapter(provider)
        self._check_provider_js_result(provider, tab.evaluate(adapter.wake_js), stage="provider_wake")

    def _disable_chatgpt_thinking_if_active(self, tab: AgentTab) -> str:
        try:
            result = str(tab.evaluate(JS_DISABLE_CHATGPT_THINKING) or "").strip()
            if result == "disabled_thinking":
                self._emit_bridge_event(
                    provider="chatgpt",
                    phase="thinking_mode_disabled",
                    detail={"action": "clicked_thinking_remove_button"},
                )
            return result
        except Exception:
            return "error"

    def _clear_provider_input(self, tab: AgentTab, provider: str) -> None:
        adapter = self._provider_adapter(provider)
        self._check_provider_js_result(provider, tab.evaluate(adapter.clear_js), stage="provider_clear")

    def _generation_started(self, tab: AgentTab, provider: str, baseline: Optional[Dict[str, Any]] = None) -> tuple[bool, str]:
        baseline = baseline or {"count": 0, "last": ""}
        if provider == "gemini":
            state = self._gemini_compose_state(tab)
            if state.get("stop_visible") or state.get("spinner_visible"):
                return True, "provider_start_signal"
            base_url = str(baseline.get("url", "") or "").strip()
            base_has_you_said = bool(baseline.get("has_you_said"))
            base_conversation_started = bool(baseline.get("conversation_started"))
            accepted_submission = bool(
                state.get("conversation_started")
                and (
                    not base_conversation_started
                    or str(state.get("url", "") or "").strip() != base_url
                    or (bool(state.get("has_you_said")) and not base_has_you_said)
                )
            )
            if not accepted_submission and self._gemini_submit_consumed_prompt(
                state,
                int(baseline.get("editor_length", 0) or 0),
            ):
                accepted_submission = True
            if accepted_submission:
                return True, "submission_accepted"
        adapter = self._provider_adapter(provider)
        start_js = adapter.start_js
        try:
            if bool(tab.evaluate(start_js)):
                return True, "provider_start_signal"
        except Exception:
            pass
        snap = self._snapshot_response_state(tab, provider)
        base_count = int(baseline.get("count", 0) or 0)
        base_last = str(baseline.get("last", "") or "").strip()
        current_count = int(snap.get("count", 0) or 0)
        current_last = str(snap.get("last", "") or "").strip()
        changed = len(current_last) > 0 and (
            current_count > base_count or current_last != base_last
        )
        if changed:
            return True, "response_delta"
        return False, "no_generation_signal"

    def _wait_for_generation_start(
        self,
        tab: AgentTab,
        provider: str,
        baseline: Optional[Dict[str, Any]] = None,
        *,
        cancel: Optional[threading.Event] = None,
        timeout_s: Optional[float] = None,
        prompt: Optional[str] = None,
    ) -> str:
        effective_timeout = float(
            timeout_s
            or self._scaled_timeout(
                prompt or "",
                base_key="start_timeout_s",
                default_base=8.0,
                per_100k_key="start_timeout_per_100k_chars_s",
                default_per_100k=6.0,
                cap_key="start_timeout_max_s",
                default_cap=32.0,
            )
        )
        pc = self._prompt_char_count(prompt or "")
        if pc > 80_000:
            # Default cap (32s) is too tight for 100k+ char bridge payloads: UI stays on composer.
            effective_timeout = max(effective_timeout, min(180.0, 14.0 + pc / 10_000.0))
        deadline = time.time() + max(1.0, effective_timeout)
        quick_poll_s = min(max(0.25, self.poll_interval_s), 0.6)
        while time.time() < deadline:
            if cancel and cancel.is_set():
                raise NodeFailure(
                    "Aborted during provider start detection",
                    category="provider_timeout",
                    stage="provider_submit",
                    provider=provider,
                )
            started, signal = self._generation_started(tab, provider, baseline)
            if started:
                return signal
            self._sleep_with_cancel(
                quick_poll_s,
                cancel=cancel,
                provider=provider,
                stage="provider_submit",
                message="Aborted during provider start detection",
            )
        raise NodeFailure(
            f"{provider} submission did not start generating within {effective_timeout:.1f}s",
            category="provider_submit_failed_fast",
            stage="provider_submit",
            provider=provider,
            details={
                "baseline": dict(baseline or {}),
                "timeout_s": effective_timeout,
            },
        )

    def _inject_tab_identity(self, tab: AgentTab, meta: Dict[str, Any]) -> None:
        node_id = meta.get("node_id", "ZENITH")
        lane = meta.get("lane", "UNKNOWN")
        lane_color = meta.get("lane_color", "#000000")
        try:
            tab.evaluate(self._get_identity_script(node_id, lane, lane_color))
        except Exception as exc:
            self.logger.warning(f"Identity injection failed: {exc}")

    def _check_cloudflare(self, tab: AgentTab) -> None:
        """
        [ACTION]
        - Teleology: Detect Cloudflare Turnstile challenge pages and fail fast.
        - Mechanism: Checks document.title and challenge-specific DOM markers.
        - Fails: Raises NodeFailure with CF_CHALLENGE prefix on detection.
        - Guarantee: Returns silently if page is clean.
        """
        try:
            result = tab.evaluate("""
            (function() {
                if (document.title === 'Just a moment...' ||
                    document.querySelector('#challenge-running, #challenge-stage, .cf-turnstile, #cf-challenge-running')) {
                    return 'BLOCKED';
                }
                return 'OK';
            })();
            """)
            if result == 'BLOCKED':
                raise NodeFailure(
                    "CF_CHALLENGE: Cloudflare interstitial detected — provider is blocking automated access",
                    category="provider_challenge",
                    stage="provider_open",
                )
        except NodeFailure:
            raise
        except Exception:
            # If JS execution itself is sandboxed (allow-scripts removed), that IS the block
            pass

    def _await_provider_ready(self, tab: AgentTab, provider: str, *, timeout_s: float = 8.0) -> None:
        deadline = time.time() + max(1.0, timeout_s)
        last_challenge: Optional[NodeFailure] = None
        while time.time() < deadline:
            try:
                self._check_cloudflare(tab)
                if provider == "gemini":
                    self._check_provider_js_result(provider, tab.evaluate(JS_WAKE_GEMINI), stage="provider_wake")
                else:
                    self._check_provider_js_result(provider, tab.evaluate(JS_WAKE_CHATGPT), stage="provider_wake")
                return
            except NodeFailure as exc:
                if exc.category == "provider_challenge":
                    last_challenge = exc
                    time.sleep(0.5)
                    continue
                raise
        if last_challenge is not None:
            raise last_challenge
        raise NodeFailure(
            f"{provider} provider did not become ready before timeout",
            category="provider_timeout",
            stage="provider_ready",
            provider=provider,
        )

    def _dismiss_provider_overlays(
        self,
        tab: AgentTab,
        provider: str,
        *,
        meta: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        [ACTION]
        - Teleology: Detect and auto-dismiss safe, non-destructive UI overlays (e.g. "Got it" modals).
        - Mechanism: Evaluates JS_DISMISS_OVERLAYS which clicks buttons in the safe allowlist.
        - Guarantee: Returns a report dict {dismissed: bool, button_text: str|None}.
        - Fails: Swallows JS errors; returns {dismissed: False} on failure.
        """
        safe_labels_json = json.dumps(sorted(_OVERLAY_SAFE_DISMISS_LABELS))
        js = JS_DISMISS_OVERLAYS.replace("%SAFE_LABELS_JSON%", safe_labels_json)
        report: Dict[str, Any] = {"dismissed": False, "button_text": None, "dialog_count": 0}
        try:
            result = tab.evaluate(js)
            if isinstance(result, dict):
                report.update(result)
        except Exception as exc:
            report["error"] = str(exc)
        if report.get("dismissed"):
            self._emit_bridge_event(
                provider=provider,
                phase="overlay_dismissed",
                meta=meta,
                tab_id=getattr(tab, "tab_id", None),
                detail=report,
            )
            # Let the DOM settle after dismissing an overlay
            time.sleep(0.5)
        return report

    def _get_identity_script(self, node_id: str, lane: str, color: str) -> str:
        """
        Populates the JS_INJECT_IDENTITY template with actual values.
        """
        script = JS_INJECT_IDENTITY
        script = script.replace("%NODE_ID_JSON%", json.dumps(node_id))
        script = script.replace("%LANE_JSON%", json.dumps(lane))
        script = script.replace("%COLOR_JSON%", json.dumps(color))
        return script

    def ask_ai(self, prompt: str, config: Optional[Dict[str, Any]] = None, cancel: Optional[threading.Event] = None) -> str:
        """
        [ACTION]
        - Teleology: Submit a prompt to the configured provider (ChatGPT or Gemini) and return assistant text.
        - Mechanism: Ensures configuration, opens a fresh tab, injects prompt, waits for completion, extracts text, then closes the tab.
        - Guarantee: Returns assistant response text on success.
        - Fails: Raises NodeFailure on configuration/CDP/provider automation errors, or if `cancel` is set.
        
        """
        _require_bridge_dependencies()
        if config is None:
            config = {}
        self.ensure_configured(config)
        
        # [FIX] Pre-flight Check
        if cancel and cancel.is_set():
            raise NodeFailure("Aborted before browser interaction")

        provider = config.get("bridge", {}).get("default_target", "chatgpt")
        if config.get("url") and "gemini" in config["url"]:
            provider = "gemini"
        elif str(config.get("platform", "")).lower() == "gemini":
            provider = "gemini"
        elif str(config.get("platform", "")).lower() == "chatgpt":
            provider = "chatgpt"

        meta = dict(config.get("meta", {})) if isinstance(config.get("meta"), dict) else {}
        meta.setdefault("host_focus_policy", self._host_focus_policy_snapshot())
        allow_account_rotation = bool(meta.get("allow_account_rotation", True))

        target_url = self.targets.get(provider, self.targets.get("chatgpt"))
        selected_account: Optional[Dict[str, Any]] = None

        # [NEW] Multi-account substrate scheduler: rotate across accounts when configured
        if allow_account_rotation and self.substrate_scheduler.has_accounts(provider):
            selected_account = self.substrate_scheduler.next_account(provider)
            if selected_account and selected_account.get("url"):
                target_url = selected_account["url"]
                meta["account_id"] = selected_account.get("id")
                self._emit_bridge_event(
                    provider=provider,
                    phase="account_selected",
                    meta=meta,
                    detail={
                        "account_id": selected_account.get("id"),
                        "account_url": selected_account.get("url"),
                        "account_stats": selected_account.get("_stats"),
                    },
                )

        if not target_url:
            err = NodeFailure(
                f"No valid target URL configured for provider: {provider}",
                category="provider_target_missing",
                stage="config",
                provider=provider,
            )
            self._record_provider_failure(
                provider,
                event="run",
                category=err.category,
                stage=err.stage,
                message=str(err),
                details=err.details,
            )
            raise err

        preferred_transport_order = (
            [str(item).strip() for item in meta.get("preferred_transport_order", []) if str(item).strip()]
            if isinstance(meta.get("preferred_transport_order"), list)
            else list(self.transport_order)
        )
        meta_specified_transport_list = isinstance(meta.get("preferred_transport_order"), list)
        allow_global_input_transport = self._allow_global_input_transport(meta)
        retryable_session_attempts = meta.get("retryable_session_attempts", self.retryable_session_attempts)
        try:
            retryable_session_attempts = max(1, int(retryable_session_attempts))
        except (TypeError, ValueError):
            retryable_session_attempts = self.retryable_session_attempts
        transport_order = self._normalized_transport_order(
            preferred_transport_order,
            allow_global_input_transport=allow_global_input_transport,
        )
        if (
            provider == "chatgpt"
            and not meta_specified_transport_list
            and len(prompt) >= CHATGPT_LARGE_PROMPT_DOM_FIRST_CHARS
        ):
            transport_order = self._normalized_transport_order(
                ["dom_inject_click", "cdp_input"],
                allow_global_input_transport=allow_global_input_transport,
            )
        aggregated_attempts: list[dict[str, Any]] = []

        try:
            for session_attempt in range(1, retryable_session_attempts + 1):
                try:
                    extracted, submit_summary = self._run_prompt_transport_attempt(
                        provider=provider,
                        target_url=target_url,
                        prompt=prompt,
                        transport_names=transport_order,
                        meta=meta,
                        cancel=cancel,
                    )
                    transport_attempts = self._annotate_attempts(
                        list(submit_summary.get("attempts", []))
                        if isinstance(submit_summary, dict)
                        else [],
                        session_attempt,
                    )
                    aggregated_attempts.extend(transport_attempts)
                    self._record_provider_success(
                        provider,
                        event="run",
                        details={
                            "target_url": target_url,
                            "response_chars": len(extracted),
                            "submission_transport": (
                                submit_summary.get("transport")
                                if isinstance(submit_summary, dict)
                                else transport_order[0] if transport_order else None
                            ),
                            "submission_attempts": aggregated_attempts,
                            "session_attempts_executed": session_attempt,
                        },
                    )
                    return extracted
                except NodeFailure as exc:
                    exc_attempts = self._annotate_attempts(
                        list(exc.details.get("attempts", []))
                        if isinstance(exc.details, dict) and isinstance(exc.details.get("attempts"), list)
                        else [],
                        session_attempt,
                    )
                    if exc_attempts:
                        aggregated_attempts.extend(exc_attempts)
                    else:
                        aggregated_attempts.append(
                            {
                                "transport": ",".join(transport_order) if transport_order else "",
                                "status": "error",
                                "category": exc.category,
                                "stage": exc.stage,
                                "message": str(exc),
                                "session_attempt": session_attempt,
                            }
                        )
                    if cancel and cancel.is_set():
                        raise
                    retryable_failure = self._should_retry_transport_failure(exc)
                    has_more_sessions = session_attempt < retryable_session_attempts
                    if has_more_sessions and retryable_failure:
                        self._sleep_with_cancel(
                            self.timings.get("session_retry_sleep", 1.0),
                            cancel=cancel,
                            provider=provider,
                            stage="provider_submit",
                            message="Aborted before retrying on a fresh tab",
                        )
                        continue
                    failure_details: Dict[str, Any] = {
                        "attempts": aggregated_attempts,
                        "session_attempts_executed": session_attempt,
                    }
                    if isinstance(exc.details, dict):
                        for key, value in exc.details.items():
                            if key == "attempts" or key in failure_details:
                                continue
                            failure_details[key] = value
                    session_phrase = (
                        f" across {session_attempt} session attempts"
                        if session_attempt > 1
                        else ""
                    )
                    raise NodeFailure(
                        f"{provider} prompt submission failed after {len(aggregated_attempts)} transport attempts{session_phrase}",
                        category=exc.category or "provider_submit_failed_fast",
                        stage=exc.stage or "provider_submit",
                        provider=provider,
                        details=failure_details,
                    ) from exc
            raise NodeFailure(
                f"{provider} prompt submission exhausted configured transports",
                category="provider_submit_failed_fast",
                stage="provider_submit",
                provider=provider,
                details={
                    "attempts": aggregated_attempts,
                    "session_attempts_executed": retryable_session_attempts,
                },
            )

        except NodeFailure as exc:
            if selected_account and selected_account.get("id"):
                self.substrate_scheduler.record_error(provider, str(selected_account.get("id") or ""))
            self._record_provider_failure(
                provider,
                event="run",
                category=exc.category,
                stage=exc.stage,
                message=str(exc),
                details=exc.details,
            )
            raise
        except Exception as exc:
            if selected_account and selected_account.get("id"):
                self.substrate_scheduler.record_error(provider, str(selected_account.get("id") or ""))
            self._record_provider_failure(
                provider,
                event="run",
                category="bridge_error",
                stage="provider_run",
                message=str(exc),
            )
            raise

    def _snapshot_response_state(self, tab: AgentTab, provider: str) -> Dict[str, Any]:
        adapter = self._provider_adapter(provider)
        snapshot_js = adapter.snapshot_js
        try:
            raw = tab.evaluate(snapshot_js)
            if isinstance(raw, dict):
                count = int(raw.get("count", 0) or 0)
                last = str(raw.get("last", "") or "").strip()
                if provider == "gemini" and self._looks_like_gemini_shell_text(last):
                    return {"count": 0, "last": ""}
                return {"count": max(0, count), "last": last}
        except Exception:
            pass
        return {"count": 0, "last": ""}

    def _inspect_provider_tab(self, tab: AgentTab, provider: str) -> Dict[str, Any]:
        adapter = self._provider_adapter(provider)
        snapshot = self._snapshot_response_state(tab, provider)
        compose_state = self._provider_compose_state(tab, provider)
        started = False
        done = False
        cancelled = False
        gemini_wait_state: Dict[str, Any] = {}
        try:
            started = bool(tab.evaluate(adapter.start_js))
        except Exception:
            pass
        try:
            done = bool(tab.evaluate(adapter.done_js))
        except Exception:
            pass
        if provider == "gemini" and adapter.composer_state_js:
            try:
                gemini_wait_state = self._gemini_wait_state(tab)
                cancelled = bool(gemini_wait_state.get("cancelled"))
            except Exception:
                pass
        inspect_js = (
            """
        (function() {
            const provider = %PROVIDER_JSON%;
"""
            + _BRIDGE_COMPOSER_HELPERS
            + """
            const editor = bridgeResolveComposer(provider, 0);
            const editorText = bridgeTextOf(editor);
            const bodyText = ((document.body && document.body.innerText) || "").replace(/\\s+/g, " ").trim();
            return {
                title: document.title || "",
                url: location.href || "",
                active: document.hasFocus(),
                visibility: document.visibilityState || "",
                editor_exists: !!editor,
                editor_length: editorText.length,
                editor_preview: editorText.slice(0, 220),
                body_preview: bodyText.slice(0, 500),
            };
        })();
        """
        ).replace("%PROVIDER_JSON%", json.dumps(str(provider or "").strip().lower()))
        result: Dict[str, Any] = {
            "tab_id": getattr(tab, "tab_id", None),
            "snapshot": snapshot,
            "started": started,
            "done": done,
            "cancelled": cancelled,
        }
        if compose_state:
            result["compose_state"] = compose_state
        if gemini_wait_state:
            result["wait_state"] = gemini_wait_state
        if provider == "chatgpt":
            interrupt_active = bool(compose_state.get("temporary_limit_interrupt"))
            result["provider_interrupt_active"] = interrupt_active
            result["provider_interrupt_kind"] = "chatgpt_temporary_limit" if interrupt_active else None
            result["provider_interrupt_preview"] = str(compose_state.get("dialog_preview", "") or "").strip() or None
        try:
            inspect = tab.evaluate(inspect_js)
            if isinstance(inspect, dict):
                result.update(inspect)
        except Exception as exc:
            result["inspect_error"] = str(exc)
        return result

    def _provider_cancelled_during_wait(self, tab: AgentTab, provider: str) -> bool:
        if provider != "gemini":
            return False
        return bool(self._gemini_wait_state(tab).get("cancelled"))

    def _wait_until_done(
        self,
        tab: AgentTab,
        done_js: str,
        provider: str,
        baseline: Optional[Dict[str, Any]] = None,
        cancel: Optional[threading.Event] = None,
        on_progress: Optional[Callable[[Dict[str, Any]], None]] = None,
        meta: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        deadline = time.time() + self.monitor_timeout_s
        baseline = baseline or {"count": 0, "last": ""}
        base_count = int(baseline.get("count", 0) or 0)
        base_last = str(baseline.get("last", "") or "").strip()
        stable_required = int(self.timings.get("completion_stable_polls", 1))
        stable_required = max(1, stable_required)
        seen_change = False
        stable_hits = 0
        last_signature = None
        cancel_hits = 0
        last_progress_signature: Optional[str] = None
        last_progress_emit_s = 0.0

        cf_check_interval = 10  # Check Cloudflare every N polls (not every cycle)
        poll_count = 0
        consecutive_stuck_evaluates = 0
        stuck_evaluate_threshold = 3
        empty_done_hits = 0
        empty_done_threshold = max(stable_required + 2, 4)

        while time.time() < deadline:
            # [CF SHIELD] Periodic Cloudflare check (every N polls to avoid overhead)
            poll_count += 1
            if poll_count % cf_check_interval == 0:
                self._check_cloudflare(tab)
                # [NEW] Auto-dismiss overlays that appear mid-generation (e.g. ChatGPT "Got it")
                if provider == "chatgpt":
                    self._dismiss_provider_overlays(tab, provider, meta=meta)

            done = False
            try:
                done = bool(self._evaluate_with_timeout(tab, done_js))
                consecutive_stuck_evaluates = 0
            except BridgeEvaluateStuck:
                consecutive_stuck_evaluates += 1
                if consecutive_stuck_evaluates >= stuck_evaluate_threshold:
                    raise NodeFailure(
                        f"Bridge tab.evaluate wedged for {consecutive_stuck_evaluates} consecutive polls",
                        category="provider_timeout",
                        stage="provider_wait",
                        provider=provider,
                    )
                # transient: re-check the outer deadline next loop
                self._jittered_sleep(self.poll_interval_s)
                continue
            except Exception:
                pass

            snap = self._snapshot_response_state(tab, provider)
            current_count = int(snap.get("count", 0) or 0)
            current_last = str(snap.get("last", "") or "").strip()
            changed = (current_count > base_count) or (current_last != base_last and len(current_last) > 0)
            if changed:
                seen_change = True

            wait_state: Dict[str, Any] = {}
            if provider == "gemini":
                wait_state = self._gemini_wait_state(tab)

            if done and seen_change:
                wait_status = "stabilizing"
            elif changed and len(current_last) > 0:
                wait_status = "receiving"
            else:
                wait_status = "thinking"

            if on_progress is not None:
                now_s = time.time()
                progress_signature = (
                    f"{wait_status}:{int(done)}:{current_count}:{len(current_last)}:{int(bool(wait_state.get('cancelled')))}"
                )
                if (
                    progress_signature != last_progress_signature
                    or now_s - last_progress_emit_s >= max(4.0, float(self.poll_interval_s) * 2.0)
                ):
                    progress_payload: Dict[str, Any] = {
                        "response_count": current_count,
                        "response_chars": len(current_last),
                        "response_started": changed,
                        "wait_status": wait_status,
                    }
                    if wait_state:
                        progress_payload["wait_state"] = wait_state
                        progress_payload["composer_state"] = wait_state
                        progress_payload["editor_length"] = int(wait_state.get("editor_length", 0) or 0)
                    try:
                        on_progress(progress_payload)
                    except Exception:
                        pass
                    last_progress_signature = progress_signature
                    last_progress_emit_s = now_s

            if cancel and cancel.is_set() and done and changed:
                return {
                    "completed_despite_cancel": True,
                    "response_count": current_count,
                    "response_chars": len(current_last),
                }

            # Do not accept "done" until assistant output has changed from baseline.
            if done and seen_change:
                # Empty-assistant guard: if the provider marks generation complete
                # but the assistant message remains empty for several stable polls,
                # treat it as a failed turn so the drain loop can retry on the next
                # cohort instead of hanging or accepting a 0-char "completion".
                if len(current_last) == 0:
                    empty_done_hits += 1
                    if empty_done_hits >= empty_done_threshold:
                        raise NodeFailure(
                            f"Provider marked generation complete with empty assistant output after {empty_done_hits} polls",
                            category="provider_empty_response",
                            stage="provider_wait",
                            provider=provider,
                            details={"snapshot": snap},
                        )
                else:
                    empty_done_hits = 0

                signature = f"{current_count}:{len(current_last)}:{current_last[-120:]}"
                if signature == last_signature:
                    stable_hits += 1
                else:
                    last_signature = signature
                    stable_hits = 0

                if stable_hits >= stable_required and len(current_last) > 0:
                    return {
                        "completed_despite_cancel": False,
                        "response_count": current_count,
                        "response_chars": len(current_last),
                    }
            elif cancel and cancel.is_set():
                abort_snapshot = snap
                partial_output = current_last
                err = NodeFailure(
                    "Aborted by Engine Signal",
                    category="provider_timeout",
                    stage="provider_wait",
                    provider=provider,
                )
                if partial_output:
                    setattr(err, "bridge_partial_output", partial_output)
                    setattr(err, "bridge_partial_count", int(abort_snapshot.get("count", 0) or 0))
                raise err
            else:
                if provider == "gemini":
                    if bool(wait_state.get("cancelled")):
                        cancel_hits += 1
                        cancel_required = max(1, int(self.timings.get("cancel_stable_polls", 3) or 3))
                        if bool(wait_state.get("placeholder_only")):
                            cancel_required = max(cancel_required, 4)
                        if cancel_hits >= cancel_required:
                            raise NodeFailure(
                                "Provider response was cancelled before completion",
                                category="provider_cancelled",
                                stage="provider_wait",
                                provider=provider,
                                details={"snapshot": snap, "cancel_state": wait_state},
                            )
                    else:
                        cancel_hits = 0
                elif self._provider_cancelled_during_wait(tab, provider):
                    raise NodeFailure(
                        "Provider response was cancelled before completion",
                        category="provider_cancelled",
                        stage="provider_wait",
                        provider=provider,
                        details={"snapshot": snap},
                    )
                stable_hits = 0
                last_signature = None
            self._jittered_sleep(self.poll_interval_s)
        raise NodeFailure(
            f"Timeout waiting for AI response (> {self.monitor_timeout_s}s)",
            category="provider_timeout",
            stage="provider_wait",
            provider=provider,
        )

    def _extract_text(self, tab: AgentTab, extract_js: str, *, provider: Optional[str] = None) -> str:
        effective_js = extract_js
        if provider:
            try:
                effective_js = self._provider_adapter(provider).extract_js
            except NodeFailure:
                effective_js = extract_js
        text = tab.evaluate(effective_js)
        if not isinstance(text, str):
            raise NodeFailure(
                f"Invalid extraction: {text}",
                category="provider_selector_failure",
                stage="provider_extract",
            )

        cleaned = text.strip()
        if cleaned.startswith("ERROR:"):
            raise NodeFailure(
                cleaned,
                category="provider_selector_failure",
                stage="provider_extract",
            )

        normalized = re.sub(r"\s+", " ", cleaned).strip().lower()
        if re.fullmatch(r"(gemini|chatgpt)\s+said:?", normalized):
            err = NodeFailure(
                "BRIDGE_EXTRACTION_PLACEHOLDER: Extracted provider label without response content",
                category="provider_selector_failure",
                stage="provider_extract",
            )
            setattr(err, "bridge_partial_output", cleaned)
            raise err
        if provider == "gemini" and self._looks_like_gemini_shell_text(cleaned):
            err = NodeFailure(
                "BRIDGE_EXTRACTION_GEMINI_SHELL: Extracted Gemini shell text without response content",
                category="provider_selector_failure",
                stage="provider_extract",
                provider="gemini",
            )
            setattr(err, "bridge_partial_output", cleaned)
            raise err
        if "you stopped this response" in normalized:
            err = NodeFailure(
                "BRIDGE_EXTRACTION_CANCELLED_SHELL: Extracted provider cancellation shell without response content",
                category="provider_cancelled",
                stage="provider_extract",
                provider="gemini",
            )
            setattr(err, "bridge_partial_output", cleaned)
            raise err
        if re.fullmatch(r"(answer now\\s*)?(gemini|chatgpt)\\s+said:?\\s*", normalized):
            err = NodeFailure(
                "BRIDGE_EXTRACTION_UI_SHELL: Extracted provider UI shell without response content",
                category="provider_selector_failure",
                stage="provider_extract",
            )
            setattr(err, "bridge_partial_output", cleaned)
            raise err

        return cleaned

    def reset(self) -> None:
        """
        [ACTION]
        - Teleology: Force re-configuration on next call.
        - Mechanism: Clears the configured flag under `_manager_lock`.
        - Guarantee: `_is_configured` is False after return.
        - Fails: None.
        
        """
        with self._manager_lock:
            self._is_configured = False

    def close(self, terminate_browser: bool = False) -> None:
        """
        [ACTION]
        - Teleology: Teardown Bridge resources.
        - Mechanism: Closes any active tab/session and optionally terminates the browser process.
        - Guarantee: Bridge resources are released best-effort; manager remains usable for future re-init.
        - Fails: None.
        
        """
        with self._manager_lock:
            if terminate_browser and self._browser_process:
                try:
                    self._browser_process.terminate()
                except Exception:
                    pass
                self._browser_process = None
            self._is_configured = False


_BRIDGE = BridgeManager()


def ask_ai(prompt: str, config: Optional[Dict[str, Any]] = None, cancel: Optional[threading.Event] = None) -> str:
    """
    [ACTION]
    - Teleology: Public API to query AI via the singleton Bridge.
    - Mechanism: Delegates to `_BRIDGE.ask_ai`.
    - Guarantee: Returns assistant response text on success.
    - Fails: Raises NodeFailure on bridge/provider errors.
    - When-needed: Open when a caller needs the repo-level bridge submission entrypoint rather than the underlying BridgeManager implementation.
    - Escalates-to: system/core/bridge.py::BridgeManager; system/core/bridge_cdp.py::CDPTransportMixin._run_prompt_transport_attempt
    """
    return _BRIDGE.ask_ai(prompt, config, cancel=cancel)


def bridge_status(config: Optional[Dict[str, Any]] = None, provider: Optional[str] = None) -> Dict[str, Any]:
    """
    [ACTION]
    - Teleology: Provide the lightweight bridge/browser/provider status surface consumed by kernel and operator tooling.
    - Mechanism: Delegates to `_BRIDGE.get_status`.
    - Guarantee: Returns a structured status mapping without opening provider tabs.
    - Fails: Propagates bridge dependency or configuration failures from the manager.
    - When-needed: Open when a caller needs quick bridge health or provider staleness data without the heavier live-tab inspection path.
    - Escalates-to: system/core/bridge.py::bridge_debug_snapshot; system/core/bridge.py::bridge_diagnostics
    """
    return _BRIDGE.get_status(config=config, provider=provider)


def bridge_debug_snapshot(
    config: Optional[Dict[str, Any]] = None,
    *,
    provider: Optional[str] = None,
    limit: int = 10,
) -> Dict[str, Any]:
    """
    [ACTION]
    - Teleology: Inspect live provider tabs through CDP for bridge debugging surfaces.
    - Mechanism: Resolves the provider, reads status, enumerates matching tabs, and augments each tab with compose-state and body/editor previews.
    - Reads: Live CDP tab list, provider compose-state JS, and bridge event tail.
    - Guarantee: Returns a provider-scoped snapshot payload even when live inspection partially fails.
    - Fails: Dependency/configuration failures propagate before inspection begins; per-tab inspect failures are recorded in the returned payload.
    - When-needed: Open when diagnosing live provider tab state, editor contents, or inspect errors instead of the normalized multi-provider summary.
    - Escalates-to: system/core/bridge.py::bridge_diagnostics; system/core/bridge.py::_normalize_bridge_tab_snapshot
    """
    _require_bridge_dependencies()
    if config is None:
        config = {}
    _BRIDGE.ensure_configured(config)
    resolved_provider = _BRIDGE._resolve_provider(config, provider)  # noqa: SLF001 - kernel diagnostics need the resolved bridge target
    status = _BRIDGE.get_status(config=config, provider=resolved_provider)
    payload: Dict[str, Any] = {
        "provider": resolved_provider,
        "debug_url": _BRIDGE.debug_url,
        "browser_running": bool(status.get("browser_running")),
        "cdp_reachable": bool(status.get("cdp_reachable")),
        "provider_interaction": _BRIDGE._provider_interaction_snapshot(resolved_provider),  # noqa: SLF001 - debug payload must expose live bridge queue state
        "active_progress": (
            dict((status.get("provider_status") or {}).get("active_progress"))
            if isinstance((status.get("provider_status") or {}).get("active_progress"), Mapping)
            else None
        ),
        "recent_events": _BRIDGE._recent_bridge_events(provider=resolved_provider, limit=10),  # noqa: SLF001 - diagnostics need bridge event tail
        "tabs": [],
    }
    if not payload["cdp_reachable"]:
        payload["error"] = "cdp_unreachable"
        return payload

    max_tabs = max(1, int(limit or 10))
    try:
        response = requests.get(f"{_BRIDGE.debug_url}/json/list", timeout=2.0)
        pages = response.json()
    except Exception as exc:
        payload["error"] = f"tab_list_failed: {exc}"
        return payload

    if not isinstance(pages, list):
        payload["error"] = "tab_list_invalid"
        return payload

    matched_pages = _BRIDGE._match_provider_pages(resolved_provider, pages)  # noqa: SLF001 - diagnostics should share runtime provider matching logic
    payload["tab_count"] = len(matched_pages)
    inspect_js = (
        """
    (function() {
        const provider = %PROVIDER_JSON%;
"""
        + _BRIDGE_COMPOSER_HELPERS
        + """
        const editor = bridgeResolveComposer(provider, 0);
        const editorText = bridgeTextOf(editor);
        const bodyText = ((document.body && document.body.innerText) || "").replace(/\\s+/g, " ").trim();
        return {
            title: document.title || "",
            active: document.hasFocus(),
            visibility: document.visibilityState || "",
            editor_exists: !!editor,
            editor_length: editorText.length,
            editor_preview: editorText.slice(0, 220),
            body_preview: bodyText.slice(0, 500),
        };
    })();
    """
    ).replace("%PROVIDER_JSON%", json.dumps(str(resolved_provider or "").strip().lower()))
    for page in matched_pages[:max_tabs]:
        tab_payload: Dict[str, Any] = {
            "id": str(page.get("id", "") or ""),
            "title": str(page.get("title", "") or ""),
            "url": str(page.get("url", "") or ""),
        }
        ws_url = str(page.get("webSocketDebuggerUrl", "") or "").strip()
        if not ws_url:
            tab_payload["inspect_error"] = "missing_websocket"
            payload["tabs"].append(tab_payload)
            continue
        tab: Optional[AgentTab] = None
        try:
            tab = AgentTab(ws_url, tab_payload["id"], timeout=5.0)
            tab_payload.update(_BRIDGE._inspect_provider_tab(tab, resolved_provider))  # noqa: SLF001 - debug surface should mirror bridge runtime inspection
            inspect = tab.evaluate(inspect_js)
            if isinstance(inspect, dict):
                tab_payload.update(inspect)
        except Exception as exc:
            tab_payload["inspect_error"] = str(exc)
        finally:
            try:
                if tab is not None:
                    tab.close()
            except Exception:
                pass
        payload["tabs"].append(tab_payload)
    return payload


def _normalize_bridge_tab_snapshot(tab_payload: Dict[str, Any]) -> Dict[str, Any]:
    raw = dict(tab_payload or {})
    snapshot = raw.get("snapshot")
    if not isinstance(snapshot, dict):
        snapshot = {}
    wait_state = raw.get("wait_state")
    if not isinstance(wait_state, dict):
        wait_state = {}
    compose_state = raw.get("compose_state")
    if not isinstance(compose_state, dict):
        compose_state = {}

    provider_interrupt_active = bool(
        raw.get("provider_interrupt_active")
        or compose_state.get("temporary_limit_interrupt")
    )
    provider_interrupt_kind = str(raw.get("provider_interrupt_kind") or "").strip() or None
    provider_interrupt_preview = (
        str(raw.get("provider_interrupt_preview") or compose_state.get("dialog_preview") or "").strip() or None
    )

    if raw.get("inspect_error"):
        phase = "inspect_error"
    elif raw.get("cancelled"):
        phase = "cancelled"
    elif provider_interrupt_active:
        phase = "provider_interrupt"
    elif raw.get("done"):
        phase = "done"
    elif raw.get("started"):
        phase = "running"
    elif wait_state.get("conversation_started") or wait_state.get("has_you_said"):
        phase = "submitted"
    elif raw.get("editor_exists") and int(raw.get("editor_length", 0) or 0) > 0:
        phase = "composing"
    elif raw.get("editor_exists"):
        phase = "ready"
    else:
        phase = "idle"

    return {
        "id": str(raw.get("id") or raw.get("tab_id") or "").strip(),
        "title": str(raw.get("title") or "").strip(),
        "url": str(raw.get("url") or "").strip(),
        "phase": phase,
        "active": bool(raw.get("active")),
        "visibility": str(raw.get("visibility") or "").strip(),
        "started": bool(raw.get("started")),
        "done": bool(raw.get("done")),
        "cancelled": bool(raw.get("cancelled")),
        "editor_exists": bool(raw.get("editor_exists")),
        "editor_length": int(raw.get("editor_length", 0) or 0),
        "editor_preview": str(raw.get("editor_preview") or "").strip(),
        "body_preview": str(raw.get("body_preview") or "").strip(),
        "response_count": int(snapshot.get("count", 0) or 0),
        "response_preview": str(snapshot.get("last") or "").strip(),
        "wait_state": dict(wait_state),
        "compose_state": dict(compose_state),
        "provider_interrupt_active": provider_interrupt_active,
        "provider_interrupt_kind": provider_interrupt_kind,
        "provider_interrupt_preview": provider_interrupt_preview,
        "inspect_error": str(raw.get("inspect_error") or "").strip() or None,
    }


def bridge_diagnostics(
    config: Optional[Dict[str, Any]] = None,
    *,
    providers: Optional[list[str]] = None,
    limit_per_provider: int = 6,
) -> Dict[str, Any]:
    """
    [ACTION]
    - Teleology: Produce the normalized multi-provider observability snapshot shared by kernel, server, and UI surfaces.
    - Mechanism: Combines bridge_status with per-provider bridge_debug_snapshot output, then derives normalized tab phases and per-phase counts.
    - Reads: Bridge status, provider tab snapshots, and live CDP availability.
    - Guarantee: Returns one payload shape for all requested providers with normalized tab summaries when live inspection succeeds.
    - Fails: Dependency/configuration failures propagate before status collection; per-provider live inspection errors are preserved in the returned payload.
    - When-needed: Open when an operator surface needs the canonical bridge observability payload rather than the raw status or single-provider debug view.
    - Escalates-to: system/core/bridge.py::bridge_debug_snapshot; system/core/bridge.py::bridge_status
    """
    _require_bridge_dependencies()
    if config is None:
        config = {}
    _BRIDGE.ensure_configured(config)
    status = _BRIDGE.get_status(config=config)
    status_providers = status.get("providers")
    if not isinstance(status_providers, dict):
        status_providers = {}

    provider_names = [
        str(name).strip()
        for name in (providers or list(status_providers.keys()) or list(_BRIDGE.targets.keys()))
        if str(name).strip()
    ]
    if not provider_names:
        provider_names = ["chatgpt"]

    payload: Dict[str, Any] = {
        "captured_at": _utc_now_iso(),
        "configured": bool(status.get("configured")),
        "browser_running": bool(status.get("browser_running")),
        "cdp_reachable": bool(status.get("cdp_reachable")),
        "debug_url": status.get("debug_url"),
        "providers": {},
    }

    max_tabs = max(1, int(limit_per_provider or 6))
    for name in provider_names:
        provider_state = dict(status_providers.get(name, {}))
        tabs: list[Dict[str, Any]] = []
        live_error: Optional[str] = None
        live: Dict[str, Any] = {}
        if payload["cdp_reachable"]:
            live = bridge_debug_snapshot(config=config, provider=name, limit=max_tabs)
            live_error = str(live.get("error") or "").strip() or None
            raw_tabs = live.get("tabs")
            if isinstance(raw_tabs, list):
                tabs = [_normalize_bridge_tab_snapshot(item) for item in raw_tabs if isinstance(item, dict)]
        else:
            live_error = "cdp_unreachable"

        phase_counts: Dict[str, int] = {}
        for tab in tabs:
            phase = str(tab.get("phase") or "idle")
            phase_counts[phase] = int(phase_counts.get(phase, 0) or 0) + 1

        provider_payload: Dict[str, Any] = {
            "provider": name,
            "target_url": provider_state.get("target_url"),
            "stale": provider_state.get("stale"),
            "stale_reason": provider_state.get("stale_reason"),
            "last_success_age_s": provider_state.get("last_success_age_s"),
            "interaction_active": bool(provider_state.get("interaction_active")),
            "interaction_waiters": int(provider_state.get("interaction_waiters", 0) or 0),
            "interaction_owner": provider_state.get("interaction_owner"),
            "active_progress": (
                dict(provider_state.get("active_progress"))
                if isinstance(provider_state.get("active_progress"), Mapping)
                else None
            ),
            "tab_count": len(tabs),
            "phase_counts": phase_counts,
            "tabs": tabs,
            "provider_state": provider_state,
            "recent_events": live.get("recent_events", []) if isinstance(live, dict) else [],
        }
        if live_error:
            provider_payload["live_error"] = live_error
        payload["providers"][name] = provider_payload

    return payload


def bridge_preflight(
    config: Optional[Dict[str, Any]] = None,
    *,
    provider: Optional[str] = None,
    timeout_s: float = 8.0,
) -> Dict[str, Any]:
    """
    [ACTION]
    - Teleology: Run the bridge runtime's warmup and audit path for one provider without sending a prompt.
    - Mechanism: Delegates to `_BRIDGE.warm_provider`.
    - Guarantee: Returns the provider readiness/audit payload produced by the manager.
    - Fails: Propagates bridge dependency or configuration failures from the manager.
    - When-needed: Open when bridge preflight tooling or operator flows need the public warm-and-audit entrypoint.
    - Escalates-to: system/core/bridge_tab.py::TabSessionMixin.warm_provider; codex/doctrine/skills/bridge_runtime/bridge_preflight.md
    """
    return _BRIDGE.warm_provider(config=config, provider=provider, timeout_s=timeout_s)


def reset() -> None:
    """
    [ACTION]
    - Teleology: Public API to reset the singleton Bridge.
    - Mechanism: Delegates to the process-global BridgeManager instance.
    - Guarantee: Next Bridge usage re-hydrates configuration.
    - Fails: None.
    
    """
    _BRIDGE.reset()


def close(terminate_browser: bool = False) -> None:
    """
    [ACTION]
    - Teleology: Public API to close the singleton Bridge.
    - Mechanism: Delegates to the process-global BridgeManager instance.
    - Guarantee: Bridge resources are released best-effort.
    - Fails: None.
    
    """
    _BRIDGE.close(terminate_browser=terminate_browser)


# ==========================================================
# [NEW] Engine Wrapper (Double Bridge / Zombie Prevention)
# ==========================================================

class Bridge:
    """
    [ROLE]
    - Teleology: Engine-compatible wrapper bound to the process-global BridgeManager singleton.
    - Mechanism: Provides an instance-shaped API around the singleton.
    - Ownership: Holds references to the global manager; does not own browser processes itself.
    - Mutability: Mutable wrapper fields (root_dir reference); manager state is shared.
    - Concurrency: Thread-safe to construct; concurrent calls serialize provider interaction inside the manager while allowing concurrent wait/poll phases.
    - When-needed: Open when legacy engine call sites still expect a Bridge instance instead of the module-level singleton functions.
    - Escalates-to: system/core/bridge.py::ask_ai; system/core/bridge.py::BridgeManager
    """
    def __init__(self, root_dir: Optional[str] = None) -> None:
        """
        [ACTION]
        - Teleology: Engine-compatible wrapper around the process-global BridgeManager singleton.
        - Mechanism: Optionally hydrates the singleton from `master_config.json` under `root_dir`.
        - Guarantee: `self.manager` references the global BridgeManager; wrapper is ready for use.
        - Fails: None (auto-hydration errors are swallowed).
        - When-needed: Open when a server or engine bootstrap path needs to know how Bridge instances hydrate the singleton from disk config.
        - Escalates-to: system/core/bridge.py::BridgeManager; system/core/bridge.py::ask_ai
        """
        self.root_dir = root_dir
        self.manager = _BRIDGE
        
        # Auto-Hydration
        # If the Server initializes this, we must ensure the Singleton knows the config
        # so it checks the correct port (9222 vs custom).
        if root_dir and not self.manager._is_configured:
            try:
                cfg_path = os.path.join(root_dir, "master_config.json")
                if os.path.exists(cfg_path):
                    with open(cfg_path, 'r') as f:
                        cfg = json.load(f)
                    self.manager.ensure_configured(cfg)
            except Exception:
                pass 

    def close(self, terminate_browser: bool = False) -> None:
        """
        [ACTION]
        - Teleology: Proxy the close call to the singleton manager.
        - Mechanism: Delegates to `BridgeManager.close`.
        - Guarantee: Bridge resources are released best-effort.
        - Fails: None.
        - When-needed: Open when an instance-shaped bridge consumer needs the shutdown surface without dropping into BridgeManager directly.
        - Escalates-to: system/core/bridge.py::close; system/core/bridge.py::BridgeManager.close
        """
        self.manager.close(terminate_browser=terminate_browser)
