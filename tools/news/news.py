"""
[PURPOSE]
- Teleology: Fetches recent Telegram channel posts and emits a normalized Phase-2 `ArtifactEnvelope` for downstream news ingestion.
- Mechanism: Uses an async Telethon (MTProto) client, applies regex-based spam filtering, orders newest-first, then truncates to a cap.
- Optimization: Compresses timestamps relative to a UTC “baseline date” to reduce artifact size without losing recency ordering.
[INTERFACE]
- Inputs: Dict `config` (either raw or wrapped under `config["data"]`) containing:
  - `auth`: {api_id, api_hash} (optional if provided via env)
  - `channels`: List[str] or Dict[str, Any] (dict keys are treated as channel identifiers)
  - `spam_filter`: {patterns: List[str]} (optional)
  - `fetch`: {new_limit: int} (messages per channel, default 60)
  - `config` or root: {max_items: int} (artifact cap, default 100)
  - `runtime`: {run_id, run_dir} (optional provenance)
- Outputs: `ArtifactEnvelope`
  - `metadata.status`: "success" | "failure"
  - `data.items`: List[{"text": str, "time": str, "url": str}]
- Exports: `StandardActor`, `run`
[FLOW]
- Reads: `config`, env (`TELEGRAM_API_ID`, `TELEGRAM_API_HASH`), Telegram network via MTProto, local session state on disk.
- Writes: Ensures `state/auth/telegram/` exists; reads/writes Telethon session file `news_session.session`.
- Orders: Items are globally sorted by message UTC datetime (newest first), then truncated to `max_items`.
- Schema: Each item contains:
  - `text`: sanitized message text (whitespace normalized)
  - `time`: UTC timestamp (HH:MM:SS if same-day as baseline, else "YYYY-MM-DD HH:MM:SS")
  - `url`: permalink `https://t.me/<channel>/<msg_id>` (acts as unique identifier)
[DEPENDENCIES]
- pypi.telethon: telegram_client
- data.state/auth/telegram: session_persistence
[CONSTRAINTS]
- Forbid: Missing Telegram credentials (`api_id`/`api_hash`) -> immediate failure envelope.
- Forbid: Unauthorized session (no user auth) -> immediate failure envelope.
- Warns: `FloodWaitError` per-channel -> channel skipped with warning log; pipeline continues.
- Determinism: Given identical Telegram message sets, spam patterns, and caps, output order and truncation are deterministic.
- Atomicity: Artifact emission is “all-or-nothing” at the envelope level (no partial success items on hard failure); soft failures only skip affected channels.
- Compression Rule: Baseline date is UTC `now().date()` captured once per run; same-day items store only time-of-day.
- When-needed: Open when a market-intelligence workflow needs the Telegram/MTProto news lane, including session auth, spam filtering, and normalized envelope emission.
- Escalates-to: tools/oracle/subject_index.py::run; tools/calculator/calculator.py::run
- Navigation-group: market_intelligence
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, TypedDict

from telethon import TelegramClient
from telethon.errors import FloodWaitError

from system.lib import feed_envelope
from system.lib.types import TOOL_METADATA_SCHEMA_VERSION, ArtifactEnvelope  # noqa: F401 (kept for compat)

logger = logging.getLogger(__name__)

SESSION_DIR = Path("state/auth/telegram")
SESSION_NAME = "news_session"
TOOL_NAME = "news"
DATA_SCHEMA_VERSION = "news.1"


class StandardActor:
    """
    [ROLE]
    Orchestrator for Telegram news ingestion.

    - Ownership: Owns the Telethon session path selection and fetch/filter/transform orchestration.
    - Mutability: Only creates/uses session directory and manages transient in-memory item buffers per run.
    - Concurrency: Not thread-safe if shared; each run uses its own event loop via `asyncio.run(...)`.
    - Couples: Output schema is constrained to `ArtifactEnvelope`; callers should not assume Telethon message objects.
    """

    def __init__(self, session_dir: Path = SESSION_DIR, session_name: str = SESSION_NAME):
        self.session_dir = session_dir
        self.session_name = session_name

    def run(self, config: Dict[str, Any]) -> ArtifactEnvelope:
        """
        [ACTION]
        - Teleology: Fetch recent Telegram channel messages into the normalized news envelope consumed by downstream market-intelligence tools.
        - Mechanism: Unwrap config/runtime provenance, resolve auth and channel specs, run the async Telethon fetch/filter/sort pipeline, and collapse the result into success or failure envelope helpers.
        - Reads: Config, env vars, Telegram network, and session state file.
        - Writes: Ensures session directory exists; Telethon may update its session file.
        - Guarantee: Returns a success envelope with newest-first sanitized items or a failure envelope carrying diagnostics and error text.
        - Warns: Flood waits and per-channel fetch errors become logged warnings and skipped channels.
        - Fails: Missing credentials, unauthorized session, or runtime crashes become failure envelopes rather than raised exceptions.
        - When-needed: Open when verifying how credentials, channel specs, flood waits, and timestamp compression affect the emitted news lane output.
        - Escalates-to: tools/news/news.py::run; tools/oracle/subject_index.py::run
        """

        # --- CONFIG UNWRAP (supports Phase-2 style `{metadata,data}` wrappers) ---
        cfg = config.get("data", config)

        # --- RUNTIME CONTEXT / PROVENANCE ---
        runtime = cfg.get("runtime", {})
        run_dir_path = runtime.get("run_dir")
        run_id = runtime.get("run_id")
        if not run_id and run_dir_path:
            run_id = Path(run_dir_path).name
        if not run_id:
            run_id = "unknown_run"

        # Capture logical "as_of" from runtime.time_anchor when supplied.
        anchor_raw = runtime.get("time_anchor")
        if isinstance(anchor_raw, str) and anchor_raw.strip():
            try:
                anchor_dt = datetime.fromisoformat(anchor_raw.strip().replace("Z", "+00:00"))
                if anchor_dt.tzinfo is None:
                    anchor_dt = anchor_dt.replace(tzinfo=timezone.utc)
                logical_now_utc = anchor_dt.astimezone(timezone.utc)
            except ValueError:
                logger.warning("Invalid runtime.time_anchor=%r; falling back to current UTC", anchor_raw)
                logical_now_utc = datetime.now(timezone.utc)
        else:
            logical_now_utc = datetime.now(timezone.utc)

        as_of = logical_now_utc.replace(microsecond=0).isoformat()
        baseline_date = logical_now_utc.date()
        # Keep execution timing real for diagnostics/perf telemetry.
        timestamp_epoch_s = datetime.now(timezone.utc).timestamp()

        # --- AUTH RESOLUTION ---
        auth = cfg.get("auth", {})
        api_id = auth.get("api_id") or os.environ.get("TELEGRAM_API_ID")
        api_hash = auth.get("api_hash") or os.environ.get("TELEGRAM_API_HASH")

        if not api_id or not api_hash:
            return self._fail(
                "Missing api_id/api_hash. Env check failed.",
                run_id,
                as_of,
                timestamp_epoch_s=timestamp_epoch_s,
            )

        # --- CHANNELS ---
        raw_channels = cfg.get("channels", [])
        channel_specs: List[Tuple[str, Optional[str]]] = []
        if isinstance(raw_channels, dict):
            for channel_handle, alias_cfg in raw_channels.items():
                alias: Optional[str] = None
                if isinstance(alias_cfg, str):
                    alias = alias_cfg.strip() or None
                elif isinstance(alias_cfg, dict):
                    for alias_key in ("alias", "label", "name"):
                        candidate = alias_cfg.get(alias_key)
                        if isinstance(candidate, str) and candidate.strip():
                            alias = candidate.strip()
                            break
                channel_specs.append((str(channel_handle), alias))
        else:
            for raw_entry in list(raw_channels):
                if isinstance(raw_entry, str):
                    channel_specs.append((raw_entry, None))
                    continue
                if isinstance(raw_entry, dict):
                    handle = raw_entry.get("handle") or raw_entry.get("channel") or raw_entry.get("id")
                    if not isinstance(handle, str) or not handle.strip():
                        continue
                    alias_candidate = raw_entry.get("alias") or raw_entry.get("label") or raw_entry.get("name")
                    alias = alias_candidate.strip() if isinstance(alias_candidate, str) and alias_candidate.strip() else None
                    channel_specs.append((handle.strip(), alias))

        if not channel_specs:
            return self._success([], run_id, as_of, str(baseline_date), timestamp_epoch_s)

        # --- FETCH + LIMITS ---
        fetch_limit = int(cfg.get("fetch", {}).get("new_limit", 60))

        spam_config = cfg.get("spam_filter", {})
        spam_patterns = spam_config.get("patterns", []) if isinstance(spam_config, dict) else []

        node_config = cfg.get("config", {})
        max_items = node_config.get("max_items")
        if max_items is None:
            max_items = cfg.get("max_items", 100)
        max_items = int(max_items)

        self.session_dir.mkdir(parents=True, exist_ok=True)

        async def _fetch_and_process() -> ArtifactEnvelope:
            items: List[Dict[str, Any]] = []
            input_rows = 0
            warning_messages: List[str] = []
            # Per-channel observability counters; merged into the final diagnostics
            # block at envelope-build time. Kept separate from `warning_messages`
            # so the existing plain-string `warnings[]` shape is untouched.
            channel_diag: Dict[str, Any] = {}

            # Compile spam regexes; invalid patterns become literal matches via escaping
            regexes: List[re.Pattern[str]] = []
            for pat in spam_patterns:
                try:
                    regexes.append(re.compile(pat, flags=re.IGNORECASE))
                except re.error:
                    regexes.append(re.compile(re.escape(pat), flags=re.IGNORECASE))

            client = TelegramClient(
                str(self.session_dir / self.session_name),
                int(api_id),
                str(api_hash),
            )

            try:
                await client.connect()
                if not await client.is_user_authorized():
                    return self._fail("Session unauthorized.", run_id, as_of, timestamp_epoch_s=timestamp_epoch_s)

                for channel_handle, channel_alias in channel_specs:
                    handle = str(channel_handle).strip()
                    if not handle:
                        continue
                    source_handle = handle.lstrip("@")
                    source_label = channel_alias or source_handle
                    try:
                        msgs = await client.get_messages(handle, limit=fetch_limit)
                        feed_envelope.record_fetch_outcome(channel_diag, ok=True)
                        for m in msgs:
                            input_rows += 1
                            if not m.text:
                                continue

                            text_clean = re.sub(r"\s+", " ", m.text).strip()
                            if any(r.search(text_clean) for r in regexes):
                                continue

                            m_date = m.date.astimezone(timezone.utc)

                            # Timestamp compression relative to baseline date (UTC)
                            if m_date.date() == baseline_date:
                                time_str = m_date.strftime("%H:%M:%S")
                            else:
                                time_str = m_date.strftime("%Y-%m-%d %H:%M:%S")

                            items.append(
                                {
                                    "_sort_date": m_date.isoformat(),
                                    "text": text_clean,
                                    "time": time_str,
                                    "url": f"https://t.me/{source_handle}/{m.id}",
                                    "source_handle": source_handle,
                                    "source_label": source_label,
                                    "category": None,
                                }
                            )

                    except FloodWaitError as e:
                        warning = f"FloodWait {e.seconds}s for {handle}. Skipping."
                        warning_messages.append(warning)
                        logger.warning(warning)
                        feed_envelope.record_fetch_outcome(channel_diag, ok=False)
                        feed_envelope.append_partial_failure(
                            channel_diag,
                            feed_envelope.warning_event(
                                code="news_flood_wait",
                                lane="news",
                                exc=e,
                                channel=source_handle,
                                extra={"flood_wait_seconds": int(getattr(e, "seconds", 0) or 0)},
                            ),
                        )
                    except Exception as e:
                        warning = f"Failed to fetch {handle}: {feed_envelope.redact_secret_values(str(e))}"
                        warning_messages.append(warning)
                        logger.warning("Failed to fetch %s: %s", handle, type(e).__name__)
                        feed_envelope.record_fetch_outcome(channel_diag, ok=False)
                        feed_envelope.append_partial_failure(
                            channel_diag,
                            feed_envelope.warning_event(
                                code="news_channel_fetch_failed",
                                lane="news",
                                exc=e,
                                channel=source_handle,
                            ),
                        )

                # Global newest-first ordering and truncation
                items.sort(key=lambda x: x["_sort_date"], reverse=True)
                if max_items > 0:
                    items = items[:max_items]

                # Remove internal sort key
                final_items: List[Dict[str, str]] = []
                for i in items:
                    i.pop("_sort_date", None)
                    final_items.append(i)  # type: ignore[arg-type]

                diagnostics = self._canonical_diagnostics(
                    input_rows=input_rows,
                    output_rows=len(final_items),
                    dropped_rows=max(0, input_rows - len(final_items)),
                    warnings=warning_messages,
                )
                # Merge per-channel observability in. Existing plain-string
                # `warnings[]` untouched; new fields are additive per the
                # envelope contract in system/lib/feed_envelope.py.
                for key in ("fetch_success_count", "fetch_failure_count", "fetch_success_rate"):
                    if key in channel_diag:
                        diagnostics[key] = channel_diag[key]
                if channel_diag.get("partial_failures"):
                    diagnostics["partial_failures"] = list(channel_diag["partial_failures"])
                return self._success(final_items, run_id, as_of, str(baseline_date), timestamp_epoch_s, diagnostics)

            except Exception as e:
                return self._fail(str(e), run_id, as_of, timestamp_epoch_s=timestamp_epoch_s)
            finally:
                await client.disconnect()

        try:
            return asyncio.run(_fetch_and_process())
        except Exception as e:
            return self._fail(f"Runtime Crash: {e}", run_id, as_of, timestamp_epoch_s=timestamp_epoch_s)

    def _get_legend(self) -> Dict[str, str]:
        return {
            "text": "Sanitized message content (whitespace normalized)",
            "time": "UTC timestamp (HH:MM:SS if baseline-day, else YYYY-MM-DD HH:MM:SS)",
            "url": "Permalink (unique identifier)",
            "note": "Sorted newest first; truncated to max_items.",
        }

    def _canonical_diagnostics(
        self,
        *,
        input_rows: int = 0,
        output_rows: int = 0,
        dropped_rows: int = 0,
        warnings: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        clean_warnings = [str(w) for w in (warnings or []) if str(w).strip()]
        return {
            "input_rows": max(0, int(input_rows)),
            "output_rows": max(0, int(output_rows)),
            "dropped_rows": max(0, int(dropped_rows)),
            "warnings": clean_warnings,
        }

    def _success(
        self,
        items: List[Dict[str, Any]],
        run_id: str,
        as_of: str,
        baseline: str,
        timestamp_epoch_s: float,
        diagnostics: Optional[Dict[str, Any]] = None,
    ) -> ArtifactEnvelope:
        diag = diagnostics or self._canonical_diagnostics(
            input_rows=len(items),
            output_rows=len(items),
            dropped_rows=0,
            warnings=[],
        )
        # news couples timestamp_iso to as_of (logical time), not wall-clock; preserve that.
        now = feed_envelope.UtcNow(
            iso=as_of,
            epoch=timestamp_epoch_s,
            dt=datetime.fromtimestamp(timestamp_epoch_s, tz=timezone.utc),
        )
        metadata = feed_envelope.build_metadata(
            tool=TOOL_NAME,
            status="success",
            now=now,
            run_id=run_id,
            as_of=as_of,
            items_count=len(items),
            diagnostics=diag,
            data_schema_version=DATA_SCHEMA_VERSION,
            timestamp=timestamp_epoch_s,
            legend=self._get_legend(),
            always_include_error=True,
            error=None,
            extra={"date_baseline": baseline},
        )
        return {"metadata": metadata, "data": {"items": items}}  # type: ignore[return-value]

    def _fail(
        self,
        err: str,
        run_id: str,
        as_of: str,
        *,
        timestamp_epoch_s: Optional[float] = None,
    ) -> ArtifactEnvelope:
        if timestamp_epoch_s is None:
            timestamp_epoch_s = datetime.now(timezone.utc).timestamp()
        diag = self._canonical_diagnostics(
            input_rows=0,
            output_rows=0,
            dropped_rows=0,
            warnings=[err] if err else [],
        )
        now = feed_envelope.UtcNow(
            iso=as_of,
            epoch=timestamp_epoch_s,
            dt=datetime.fromtimestamp(timestamp_epoch_s, tz=timezone.utc),
        )
        metadata = feed_envelope.build_metadata(
            tool=TOOL_NAME,
            status="failure",
            now=now,
            run_id=run_id,
            as_of=as_of,
            items_count=0,
            diagnostics=diag,
            data_schema_version=DATA_SCHEMA_VERSION,
            timestamp=timestamp_epoch_s,
            legend=self._get_legend(),
            error=err,
        )
        return {"metadata": metadata, "data": {"items": []}}  # type: ignore[return-value]


def run(config: Dict[str, Any], run_dir: Optional[str] = None) -> ArtifactEnvelope:
    """
    [ACTION]
    - Teleology: Provide the module-level entrypoint that wires run_dir provenance into the Telegram news actor.
    - Mechanism: Inject run_dir into the runtime config when supplied, then delegate execution to StandardActor.run.
    - Reads: Provided config and optional run_dir.
    - Writes: Mutates the provided config dict to attach runtime.run_dir when run_dir is set.
    - Guarantee: Returns the ArtifactEnvelope produced by StandardActor().run(config).
    - Fails: None; StandardActor.run converts operational failures into failure envelopes.
    - Orders: None (delegated).
    - When-needed: Open when wiring the news lane into a runner that passes provenance without needing the full actor internals.
    - Escalates-to: tools/news/news.py::StandardActor.run; tools/oracle/subject_index.py::run
    """

    if run_dir:
        if "data" in config:
            config["data"].setdefault("runtime", {})["run_dir"] = run_dir
        else:
            config.setdefault("runtime", {})["run_dir"] = run_dir

    return StandardActor().run(config)
