"""
[PURPOSE]
- Teleology: Tab and session lifecycle management for BridgeManager — opening, closing,
  finding existing provider tabs, warming up tabs for first-use, paste input.
- Mechanism: Mixin class TabSessionMixin contributing the tab lifecycle methods.

[INTERFACE]
- Exports: TabSessionMixin

[FLOW]
- BridgeManager inherits from TabSessionMixin alongside provider/CDP mixins.
- warm_provider is called before first use to ensure a tab exists and is interactive.
- _find_existing_provider_tab + _open_tab work together to lazily acquire tabs.

[DEPENDENCIES]
- system.core.bridge: AgentTab, browser/session state (used via self).

[CONSTRAINTS]
- All methods access self.X (BridgeManager state) — works only as a mixin.
- When-needed: Open when provider preflight, tab reuse/open, or tab sweeping behavior needs inspection below the BridgeManager facade.
- Escalates-to: system/core/bridge.py::BridgeManager; codex/doctrine/skills/bridge_runtime/bridge_preflight.md; system/core/bridge_cdp.py::CDPTransportMixin._run_prompt_transport_attempt
- Navigation-group: bridge_runtime
"""
from __future__ import annotations

import json
import platform
import re
import subprocess
import time
from typing import Any, Dict, List, Optional, Tuple

import requests

# Circular-import safe: bridge.py defines these BEFORE its mixin imports.
from system.core.bridge import (  # noqa: E402
    AgentTab,
    NodeFailure,
    _require_bridge_dependencies,
    _utc_now_iso,
)


class TabSessionMixin:
    """
    [ROLE]
    - Teleology: Own tab acquisition, preflight warmup, and provider-tab cleanup for BridgeManager.
    - Mechanism: Reuses idle provider tabs when safe, opens fresh CDP tabs when needed, runs preflight audits, and exposes a provider sweep helper.
    - Ownership: Mixed into BridgeManager; browser process ownership remains with the manager.
    - Mutability: Mutates live browser tab state through `self` and remote CDP endpoints.
    - Concurrency: Assumes provider-level locking is handled by BridgeManager before warmup and prompt submission flows enter these methods.
    - When-needed: Open when bridge preflight or tab lifecycle behavior is the likely source of provider readiness problems.
    - Escalates-to: system/core/bridge.py::BridgeManager; system/core/bridge.py::bridge_preflight
    """

    def _close_agent_tab(self, tab: Optional[AgentTab]) -> None:
        tab_id = getattr(tab, "tab_id", None) if tab is not None else None
        if tab is not None:
            try:
                tab.close()
            except Exception:
                pass
        if tab_id:
            self._close_tab(tab_id)

    def _find_existing_provider_tab(
        self,
        provider: str,
        target_url: str,
        *,
        meta: Optional[Dict[str, Any]] = None,
    ) -> Optional[AgentTab]:
        """
        [ACTION]
        - Teleology: Reuse an existing idle provider tab instead of opening a fresh one.
        - Mechanism: Enumerates CDP pages, matches by URL origin, attaches via WebSocket, checks liveness.
        - Guarantee: Returns an AgentTab if an idle match is found, else None.
        - Fails: Returns None on any error.
        - When-needed: Open when a bridge run reused or skipped a tab unexpectedly and you need the exact idle-tab acceptance criteria.
        - Escalates-to: system/core/bridge_tab.py::TabSessionMixin._open_tab; system/core/bridge.py::bridge_debug_snapshot
        """
        if not self.reuse_existing_tabs:
            return None
        _require_bridge_dependencies()
        try:
            pages = self._list_browser_pages(timeout_s=2.0)
        except Exception:
            return None
        matched = self._match_provider_pages(provider, pages)
        for page in matched:
            ws_url = str(page.get("webSocketDebuggerUrl", "") or "").strip()
            page_id = str(page.get("id", "") or "").strip()
            if not ws_url or not page_id:
                continue
            tab: Optional[AgentTab] = None
            try:
                tab = AgentTab(ws_url, page_id, timeout=5.0)
                # Check if tab is idle: no active generation, no pending input
                compose = self._provider_compose_state(tab, provider)
                editor_length = int(compose.get("editor_length", 0) or 0)
                stop_visible = bool(compose.get("stop_visible"))
                spinner_visible = bool(compose.get("spinner_visible", False))
                conversation_started = bool(compose.get("conversation_started"))
                # Reject tabs that are actively generating, have pending input,
                # or are already inside an existing conversation. Pasting into
                # a /c/<id> tab sends the prompt as a follow-up message instead
                # of starting a fresh conversation — user sees the huge JSON
                # pasted into the Follow-up composer of a Thinking chat.
                # Each distill probe must be a fresh conversation for the
                # bridge dispatch log and the response surface contract.
                if stop_visible or spinner_visible or editor_length > 50 or conversation_started:
                    try:
                        tab.close()
                    except Exception:
                        pass
                    continue
                # Tab is idle — dismiss any overlays and return it
                self._dismiss_provider_overlays(tab, provider, meta=meta)
                self._emit_bridge_event(
                    provider=provider,
                    phase="tab_reused",
                    meta=meta,
                    tab_id=page_id,
                    detail={
                        "target_url": target_url,
                        "reused_url": str(page.get("url", "") or ""),
                        "compose_state": compose,
                    },
                )
                return tab
            except Exception:
                if tab is not None:
                    try:
                        tab.close()
                    except Exception:
                        pass
                continue
        return None

    def _open_tab(
        self,
        url: str,
        *,
        provider: Optional[str] = None,
        readiness_timeout: float = 8.0,
        background: bool = True,
        new_window: bool = False,
    ) -> AgentTab:
        """
        [ACTION]
        - Teleology: Open a fresh CDP tab, navigate it to the provider URL, and optionally wait for provider readiness.
        - Mechanism: Calls the Chrome `/json/new` endpoint, wraps the tab in AgentTab, navigates, waits through hydration for hosted providers, and then runs provider-ready or Cloudflare checks.
        - Reads: Live CDP `/json/new` endpoint, provider URL, readiness timeout, and bridge timing config.
        - Guarantee: Returns an AgentTab whose page has been navigated and passed the requested readiness checks.
        - Fails: Raises NodeFailure when CDP tab creation, navigation, or readiness verification fails.
        - When-needed: Open when provider tabs fail to launch, hang during hydration, or trip readiness checks before prompt submission begins.
        - Escalates-to: system/core/bridge.py::AgentTab; system/core/bridge_tab.py::TabSessionMixin.warm_provider
        """
        _require_bridge_dependencies()
        self._ensure_browser()
        # Strict capability gate before we open a tab: when active-background
        # seat is enabled the running Chrome listener on debug_port must use
        # the configured user_data_dir AND carry every required anti-throttle
        # flag. This is the guard that prevents "validation receipt said it
        # works yesterday but Chrome was relaunched without flags this morning"
        # from silently degrading dispatch.
        if (
            bool(provider)
            and str(provider).strip().lower() == "chatgpt"
            and self._chatgpt_active_background_seat_enabled()
        ):
            self._assert_active_background_browser_process()
        try:
            data: Dict[str, Any]
            used_fallback = False
            # ChatGPT active-background seat: open about:blank first with
            # background=False+focus=False so the new tab is the active tab
            # inside the bridge Chrome instance without changing macOS
            # frontmost. Then install Emulation.setFocusEmulationEnabled,
            # Page.setWebLifecycleState=active, and the Document-prototype
            # visibility patch via Page.addScriptToEvaluateOnNewDocument
            # BEFORE navigating to chatgpt.com — so the patch runs before any
            # ChatGPT app code reads document.hidden / hasFocus / etc.
            chatgpt_active_seat = (
                bool(provider) and str(provider).strip().lower() == "chatgpt"
                and self._chatgpt_active_background_seat_enabled()
            )
            seat_target_url = url
            initial_url = "about:blank" if chatgpt_active_seat else url
            initial_focus: Optional[bool] = False if chatgpt_active_seat else None
            initial_background = (
                False if chatgpt_active_seat else bool(background)
            )
            try:
                data = self._create_browser_target(
                    initial_url,
                    background=initial_background,
                    new_window=bool(new_window),
                    focus=initial_focus,
                )
            except Exception as exc:
                # In active-background-seat mode the about:blank +
                # background=False + focus=False sequence is load-bearing —
                # the visibility/focus-emulation patch HAS to install before
                # the chatgpt.com document loads, and the legacy /json/new
                # endpoint immediately navigates the real URL. Falling back
                # silently would defeat the seat. Fail closed.
                if chatgpt_active_seat:
                    raise NodeFailure(
                        "ChatGPT active-background seat requires Target.createTarget "
                        "(focus=False, background=False); refusing /json/new fallback "
                        f"because that would navigate chatgpt.com before the visibility "
                        f"patch installs. Underlying error: {exc}",
                        category="active_background_target_create_failed",
                        stage="tab_open",
                        provider=provider,
                    ) from exc
                used_fallback = True
                resp = requests.put(f"{self.debug_url}/json/new", timeout=5.0)
                data = resp.json()
            ws_url = str(data.get("webSocketDebuggerUrl", "") or "").strip()
            tab_id = str(data.get("id", "") or "").strip()
            if not ws_url or not tab_id:
                raise NodeFailure(
                    "New browser target is missing websocket or id metadata",
                    category="cdp_unreachable",
                    stage="tab_open",
                    provider=provider,
                )
            agent = AgentTab(ws_url, tab_id, timeout=self.connection_timeout)

            # Active-background seat install must happen BEFORE navigation so
            # addScriptToEvaluateOnNewDocument is in place when chatgpt.com's
            # document is created. After this, Page.navigate to the real URL.
            if chatgpt_active_seat:
                seat_summary = self._apply_chatgpt_active_background_seat(
                    agent, reason="tab_open_pre_navigate"
                )
                self._emit_bridge_event(
                    provider=provider,
                    phase="active_background_seat_installed",
                    meta=None,
                    tab_id=tab_id,
                    detail={"seat_summary": seat_summary, "target_url": seat_target_url},
                )
                try:
                    agent.send("Page.navigate", {"url": seat_target_url})
                except Exception as exc:
                    raise NodeFailure(
                        f"Page.navigate to {seat_target_url} failed after active-background seat install: {exc}",
                        category="cdp_socket_error",
                        stage="tab_open",
                        provider=provider,
                    ) from exc
            elif used_fallback:
                agent.send("Page.navigate", {"url": url})

            # [ZENITH FIX] Wait for redirects/hydration (Race Condition Prevention)
            if "chatgpt" in url or "gemini" in url:
                # [CONFIGURABLE] Use the value from master_config, defaulting to 2.0s
                self._jittered_sleep(self.timings.get("hydration_sleep", 2.0))

            # Reassert the seat once the chatgpt.com document has actually
            # loaded — addScriptToEvaluateOnNewDocument fires the patch on
            # new-document creation, but live tab.evaluate() guarantees the
            # current document is patched even if the install raced the nav.
            if chatgpt_active_seat:
                self._apply_chatgpt_active_background_seat(
                    agent, reason="post_hydration_reassert"
                )

            if provider:
                self._await_provider_ready(agent, provider, timeout_s=readiness_timeout)
            else:
                # [CF SHIELD] Detect Cloudflare challenge before any DOM interaction
                self._check_cloudflare(agent)

            return agent
        except NodeFailure:
            raise
        except Exception as e:
            raise NodeFailure(
                f"Failed to open new tab: {e}",
                category="cdp_unreachable",
                stage="tab_open",
                provider=provider,
            ) from e

    def warm_provider(
        self,
        config: Optional[Dict[str, Any]] = None,
        *,
        provider: Optional[str] = None,
        timeout_s: float = 8.0,
    ) -> Dict[str, Any]:
        """
        [ACTION]
        - Teleology: Warm and audit one provider so the bridge runtime can confirm readiness without sending a real prompt.
        - Mechanism: Resolves provider config, acquires provider interaction ownership, opens a tab, runs focus-policy-gated preflight audit/snapshot routines, records provider success or failure state, and closes the tab.
        - Reads: Bridge config, provider targets, live browser/CDP state, and provider audit JS.
        - Writes: Provider success/failure state and bridge event log entries through manager helpers.
        - Guarantee: Returns a structured readiness payload describing success or the captured failure state for the requested provider.
        - Fails: Internal NodeFailure and unexpected exceptions are converted into structured error payloads rather than escaping.
        - When-needed: Open when bridge preflight, provider readiness, or stale-provider repair flows need the concrete warmup contract.
        - Escalates-to: system/core/bridge.py::bridge_preflight; codex/doctrine/skills/bridge_runtime/bridge_preflight.md
        """
        _require_bridge_dependencies()
        if config is None:
            config = {}
        self.ensure_configured(config)
        resolved_provider = self._resolve_provider(config, provider)
        target_url = self.targets.get(resolved_provider, self.targets.get("chatgpt"))
        status: Dict[str, Any] = {
            "provider": resolved_provider,
            "target_url": target_url,
            "started_at": _utc_now_iso(),
            "ok": False,
            "status": "error",
            "stage": "bootstrap",
        }
        if not target_url:
            message = f"No valid target URL configured for provider: {resolved_provider}"
            persisted = self._record_provider_failure(
                resolved_provider,
                event="preflight",
                category="provider_target_missing",
                stage="config",
                message=message,
            )
            status.update(
                {
                    "error": message,
                    "category": "provider_target_missing",
                    "stage": "config",
                    "provider_state": persisted,
                }
            )
            return status

        tab: Optional[AgentTab] = None
        preflight_meta = {
            "session_id": f"preflight:{resolved_provider}",
            "node_id": f"PREFLIGHT_{resolved_provider.upper()}",
            "lane": "BRIDGE_PREFLIGHT",
            "transport_name": "preflight_audit",
        }
        try:
            with self._provider_interaction_context(
                resolved_provider,
                meta=preflight_meta,
            ) as interaction_slot:
                self._ensure_browser()
                status["stage"] = "provider_open"
                tab = self._open_tab(target_url, provider=resolved_provider, readiness_timeout=timeout_s)
                status["provider_interaction_wait_s"] = float(interaction_slot.get("wait_s", 0.0) or 0.0)
                self._emit_bridge_event(
                    provider=resolved_provider,
                    phase="preflight_open",
                    meta=preflight_meta,
                    tab_id=getattr(tab, "tab_id", None),
                    detail={
                        "target_url": target_url,
                        "provider_interaction_wait_s": status["provider_interaction_wait_s"],
                    },
                )
                host_focus_changed = self._focus_tab(
                    tab,
                    meta=preflight_meta,
                    reason="warm_provider",
                )
                self._wake_provider_input(tab, resolved_provider)
                audit = self._run_preflight_audit(tab, resolved_provider)
                snapshot = self._snapshot_response_state(tab, resolved_provider)
                self._emit_bridge_event(
                    provider=resolved_provider,
                    phase="preflight_audit",
                    meta=preflight_meta,
                    tab_id=getattr(tab, "tab_id", None),
                    detail={
                        "target_url": target_url,
                        "snapshot": snapshot,
                        "audit": audit,
                        "host_focus_changed": bool(host_focus_changed),
                        "host_focus_policy": self._host_focus_policy_snapshot(),
                    },
                )
            persisted = self._record_provider_success(
                resolved_provider,
                event="preflight",
                details={
                    "target_url": target_url,
                    "snapshot": snapshot,
                    "audit": audit,
                    "provider_interaction_wait_s": status.get("provider_interaction_wait_s", 0.0),
                },
            )
            staleness = self._provider_staleness(resolved_provider)
            status.update(
                {
                    "ok": True,
                    "status": "ready",
                    "stage": "provider_ready",
                    "snapshot": snapshot,
                    "audit": audit,
                    "provider_state": persisted,
                    "stale": bool(staleness.get("stale")),
                    "stale_reason": staleness.get("reason"),
                }
            )
            return status
        except NodeFailure as exc:
            persisted = self._record_provider_failure(
                resolved_provider,
                event="preflight",
                category=exc.category,
                stage=exc.stage,
                message=str(exc),
                details=exc.details,
            )
            status.update(
                {
                    "error": str(exc),
                    "category": exc.category,
                    "stage": exc.stage,
                    "provider_state": persisted,
                }
            )
            return status
        except Exception as exc:
            persisted = self._record_provider_failure(
                resolved_provider,
                event="preflight",
                category="bridge_error",
                stage="provider_ready",
                message=str(exc),
            )
            status.update(
                {
                    "error": str(exc),
                    "category": "bridge_error",
                    "stage": "provider_ready",
                    "provider_state": persisted,
                }
            )
            return status
        finally:
            self._emit_bridge_event(
                provider=resolved_provider,
                phase="tab_closed",
                meta=preflight_meta,
                tab_id=getattr(tab, "tab_id", None),
                detail={"target_url": target_url},
            )
            self._close_agent_tab(tab)

    def _close_tab(self, tab_id: str) -> None:
        try:
            requests.get(f"{self.debug_url}/json/close/{tab_id}", timeout=2.0)
        except Exception:
            pass

    def sweep_provider_tabs_with_report(
        self,
        provider: str,
        *,
        protect_shared_windows: bool = True,
    ) -> Dict[str, Any]:
        """
        [ACTION]
        - Teleology: Close stale provider tabs while protecting shared/fullscreen operator windows by default.
        - Mechanism: Builds the bridge window report, derives closable vs protected provider tabs, and issues `/json/close/<id>` only for the allowed subset.
        - Reads: Live CDP tab list plus browser window metadata through `bridge_window_report()`.
        - Writes: Remote tab-close requests to the browser for closable provider tabs only.
        - Guarantee: Returns a structured sweep report with closed and skipped tab ids.
        - Fails: Listing/close errors degrade to a best-effort report rather than raising.
        """
        _require_bridge_dependencies()
        report = self.bridge_window_report(provider=provider, include_media=True)
        requested_ids = [
            str(item or "").strip()
            for item in report.get("requested_provider_tab_ids", [])
            if str(item or "").strip()
        ]
        protected_ids = [
            str(item or "").strip()
            for item in report.get("protected_tab_ids", [])
            if str(item or "").strip()
        ]
        closable_ids = list(requested_ids if not protect_shared_windows else report.get("closable_tab_ids", []))
        closable_ids = [tab_id for tab_id in closable_ids if str(tab_id or "").strip()]
        skipped_ids = list(protected_ids if protect_shared_windows else [])
        closed_ids: List[str] = []
        close_errors: Dict[str, str] = {}
        for page_id in closable_ids:
            try:
                requests.get(f"{self.debug_url}/json/close/{page_id}", timeout=3.0)
                closed_ids.append(page_id)
            except Exception as exc:
                close_errors[page_id] = str(exc)
        result = dict(report)
        result.update(
            {
                "provider": str(provider or "").strip().lower(),
                "protect_shared_windows": bool(protect_shared_windows),
                "requested_tab_count": len(requested_ids),
                "closed_count": len(closed_ids),
                "closed_tab_ids": closed_ids,
                "skipped_tab_ids": skipped_ids,
                "close_errors": close_errors,
            }
        )
        return result

    def sweep_provider_tabs(self, provider: str) -> int:
        """
        [ACTION]
        - Teleology: Remove all open tabs for one provider so the next bridge session starts from a clean slate.
        - Mechanism: Lists CDP pages, filters them with `_match_provider_pages`, and issues `/json/close/<id>` for each match.
        - Reads: Live CDP tab list.
        - Writes: Remote tab-close requests to the browser.
        - Guarantee: Returns the number of provider-matched tabs that were closed successfully.
        - Fails: None — listing or close errors degrade to a best-effort partial count.
        - When-needed: Open when a preflight or dispatch flow wants to eliminate stale provider tabs before running.
        - Escalates-to: system/core/bridge_tab.py::TabSessionMixin._find_existing_provider_tab; system/core/bridge.py::bridge_preflight
        """
        report = self.sweep_provider_tabs_with_report(provider, protect_shared_windows=True)
        return int(report.get("closed_count", 0) or 0)

    def _paste_input(
        self,
        prompt: str,
        hit_enter: bool = False,
        *,
        allow_global_input: bool = False,
    ) -> None:
        if not allow_global_input:
            raise NodeFailure(
                "Native macOS input transport is disabled by bridge.host_focus_policy; use CDP/DOM transport or opt in explicitly.",
                category="host_focus_forbidden",
                stage="provider_input",
            )
        if platform.system().lower() != "darwin":
            raise NodeFailure(
                "Bridge supports macOS paste only.",
                category="provider_selector_failure",
                stage="provider_input",
            )
        try:
            import pyperclip
        except Exception as exc:
            raise NodeFailure(
                "pyperclip missing",
                category="provider_selector_failure",
                stage="provider_input",
            ) from exc

        pyperclip.copy(prompt)
        
        activate_delay = self.timings.get("as_activate_delay", 0.2)
        enter_delay = self.timings.get("as_enter_delay", 0.3)

        script = f'''
        tell application "Google Chrome" to activate
        delay {activate_delay}
        tell application "System Events"
            keystroke "v" using command down
            delay {enter_delay}
        end tell
        '''
        if hit_enter:
            script = f'''
            tell application "Google Chrome" to activate
            delay {activate_delay}
            tell application "System Events"
                keystroke "v" using command down
                delay {enter_delay}
                key code 36
            end tell
            '''

        try:
            subprocess.run(["osascript", "-e", script], check=True)
        except Exception as exc:
            raise NodeFailure(
                f"Prompt injection failed: {exc}",
                category="provider_selector_failure",
                stage="provider_input",
            ) from exc
        time.sleep(1.5)
