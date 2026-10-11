"""
[PURPOSE]
- Teleology: CDP/transport layer for BridgeManager — text insertion, submission paths
  (CDP input, native keystroke, DOM event), fallback orchestration, retry policy.
- Mechanism: Mixin class CDPTransportMixin contributing the _cdp_*, _submit_prompt_*,
  and transport policy methods. These methods coordinate prompt delivery to provider
  tabs through Chrome DevTools Protocol.

[INTERFACE]
- Exports: CDPTransportMixin

[FLOW]
- BridgeManager inherits from CDPTransportMixin alongside provider mixins.
- _submit_prompt_with_fallback orchestrates the transport attempt sequence:
  CDP input → DOM event by default; native keystroke is explicit opt-in.
- _run_prompt_transport_attempt is the per-attempt engine called by ask_ai.

[DEPENDENCIES]
- system.core.bridge: AgentTab, NodeFailure, _cdp_send (helpers, used via self).

[CONSTRAINTS]
- All methods access self.X (BridgeManager state) — works only as a mixin.
- Transport methods are coupled to provider readiness checks; do not move them
  without also moving _wait_for_generation_start and _await_provider_ready.
- When-needed: Open when prompt delivery, transport fallback, or wait-and-extract orchestration needs inspection below the BridgeManager facade.
- Escalates-to: system/core/bridge.py::BridgeManager; system/core/bridge_tab.py::TabSessionMixin._open_tab; system/core/bridge_chatgpt.py::ChatGPTBridgeMixin._prime_chatgpt_submission; system/core/bridge_gemini.py::GeminiBridgeMixin._prime_gemini_submission
- Navigation-group: bridge_runtime
"""
from __future__ import annotations

import json
import re
import threading
import time
import uuid
from contextlib import nullcontext
from typing import Any, Dict, List, Optional, Tuple

# Circular-import safe: bridge.py defines these BEFORE its mixin imports.
from system.core.bridge import (  # noqa: E402
    AgentTab,
    DEFAULT_TRANSPORT_ORDER,
    GLOBAL_INPUT_TRANSPORTS,
    JS_FLUSH_GEMINI_INPUT,
    NodeFailure,
    SUPPORTED_TRANSPORTS,
    _CDP_INSERT_TEXT_CHUNK_CHARS,
)


class CDPTransportMixin:
    """
    [ROLE]
    - Teleology: Own the prompt-transport and response-wait portion of the bridge runtime for BridgeManager.
    - Mechanism: Supplies transport-specific submission methods plus the orchestration path that opens/reuses a tab, submits via fallback order, waits for completion, and extracts text.
    - Ownership: Mixed into BridgeManager; does not own browser lifecycle state outside the manager.
    - Mutability: Reads and updates BridgeManager runtime state through `self`.
    - Concurrency: Assumes provider-level locking is handled by BridgeManager and only uses `_input_lock` for global input transports.
    - When-needed: Open when transport ordering, retry rules, or response wait/extract sequencing are the likely source of bridge failures.
    - Escalates-to: system/core/bridge.py::BridgeManager; system/core/bridge.py::AgentTab.send
    """

    def _submit_with_enter_key(self, tab: AgentTab, provider: str) -> None:
        """
        [ACTION]
        - Teleology: Trigger the provider's Enter-key submit path when click-based submission did not take.
        - Mechanism: Dispatches raw-key-down, char, and key-up CDP events for Enter against the active tab.
        - Reads: Active provider tab handle and provider identity for error reporting.
        - Guarantee: Either emits the full Enter key sequence or raises a structured NodeFailure.
        - Fails: Raises NodeFailure when CDP key dispatch fails.
        - When-needed: Open when prompt injection succeeded but the provider still needs a keyboard-style submit fallback.
        - Escalates-to: system/core/bridge_cdp.py::CDPTransportMixin._submit_prompt_with_fallback; system/core/bridge.py::AgentTab.send
        """
        enter_event = {
            "key": "Enter",
            "code": "Enter",
            "windowsVirtualKeyCode": 13,
            "nativeVirtualKeyCode": 13,
        }
        try:
            tab.send("Input.dispatchKeyEvent", {"type": "rawKeyDown", **enter_event})
            tab.send("Input.dispatchKeyEvent", {"type": "char", "text": "\r", "unmodifiedText": "\r", **enter_event})
            tab.send("Input.dispatchKeyEvent", {"type": "keyUp", **enter_event})
        except Exception as exc:
            raise NodeFailure(
                f"{provider} submit fallback keypress failed: {exc}",
                category="provider_selector_failure",
                stage="provider_submit",
                provider=provider,
            ) from exc

    def _cdp_insert_text_chunked(
        self,
        tab: AgentTab,
        prompt: str,
        *,
        cancel: Optional[threading.Event] = None,
        provider: Optional[str] = None,
    ) -> None:
        """
        [ACTION]
        - Teleology: Insert long prompts into a provider composer without overrunning CDP input limits.
        - Mechanism: Splits the prompt into bounded chunks, keeps the composer awake between chunks, and honors cancellation during insertion sleeps.
        - Reads: Prompt text, bridge timing knobs, provider identity, and cancellation state.
        - Guarantee: Writes the full prompt text via `Input.insertText` unless cancellation interrupts the attempt.
        - Fails: Raises NodeFailure when cancellation fires mid-insert.
        - When-needed: Open when large prompt delivery truncates, stalls, or appears to lose focus partway through insertion.
        - Escalates-to: system/core/bridge_cdp.py::CDPTransportMixin._submit_prompt_cdp_input; system/core/bridge.py::AgentTab.send
        """
        chunk = max(256, int(_CDP_INSERT_TEXT_CHUNK_CHARS))
        if provider and hasattr(tab, "evaluate"):
            self._wake_provider_input(tab, provider)
        if len(prompt) <= chunk:
            if cancel and cancel.is_set():
                raise NodeFailure(
                    "Aborted during prompt insertion",
                    category="provider_timeout",
                    stage="provider_input",
                    provider=provider,
                )
            tab.send("Input.insertText", {"text": prompt})
            return
        gap = float(self.timings.get("cdp_insert_chunk_sleep_s", 0.02) or 0.0)
        for offset in range(0, len(prompt), chunk):
            if cancel and cancel.is_set():
                raise NodeFailure(
                    "Aborted during prompt insertion",
                    category="provider_timeout",
                    stage="provider_input",
                    provider=provider,
                )
            if offset > 0 and provider and hasattr(tab, "evaluate"):
                self._wake_provider_input(tab, provider)
            tab.send("Input.insertText", {"text": prompt[offset : offset + chunk]})
            if offset + chunk < len(prompt) and gap > 0:
                self._sleep_with_cancel(
                    gap,
                    cancel=cancel,
                    provider=provider,
                    stage="provider_input",
                    message="Aborted during chunked prompt insertion",
                )

    def _submit_prompt_cdp_input(
        self,
        tab: AgentTab,
        provider: str,
        prompt: str,
        *,
        cancel: Optional[threading.Event] = None,
    ) -> None:
        """
        [ACTION]
        - Teleology: Submit a prompt through the pure CDP-input transport path.
        - Mechanism: Inserts the prompt chunk-wise, waits for flush, verifies prompt fidelity, then runs the provider-specific submit and priming steps.
        - Reads: Provider adapter JS hooks, prompt text, bridge timings, and cancellation state.
        - Guarantee: Leaves the provider in post-submit priming once the CDP input path succeeds.
        - Fails: Propagates NodeFailure from fidelity, readiness, or provider-submit checks.
        - When-needed: Open when the CDP-first transport path is the suspected failure point instead of native paste or DOM injection.
        - Escalates-to: system/core/bridge_cdp.py::CDPTransportMixin._cdp_insert_text_chunked; system/core/bridge_chatgpt.py::ChatGPTBridgeMixin._prime_chatgpt_submission; system/core/bridge_gemini.py::GeminiBridgeMixin._prime_gemini_submission
        """
        adapter = self._provider_adapter(provider)
        self._cdp_insert_text_chunked(tab, prompt, cancel=cancel, provider=provider)
        self._sleep_with_cancel(
            self.timings.get("flush_sleep", 0.5),
            cancel=cancel,
            provider=provider,
            stage="provider_input",
            message="Aborted while waiting for prompt flush",
        )
        self._ensure_prompt_fidelity(
            tab,
            prompt,
            provider=provider,
            transport_name="cdp_input",
        )
        if provider == "gemini":
            self._wait_for_gemini_submit_ready(tab, prompt, cancel=cancel)
        if provider == "chatgpt" and self._chatgpt_active_background_seat_enabled():
            self._apply_chatgpt_active_background_seat(tab, reason="pre_submit_reassert_cdp_input")
        self._check_provider_js_result(provider, tab.evaluate(adapter.submit_js), stage="provider_submit")
        if provider == "chatgpt" and self._chatgpt_active_background_seat_enabled():
            self._apply_chatgpt_active_background_seat(tab, reason="post_click_reassert_cdp_input")
        if provider == "gemini":
            self._prime_gemini_submission(tab, prompt, cancel=cancel)
        elif provider == "chatgpt":
            self._prime_chatgpt_submission(tab, prompt, cancel=cancel)

    def _submit_prompt_native(
        self,
        tab: AgentTab,
        provider: str,
        prompt: str,
        *,
        cancel: Optional[threading.Event] = None,
    ) -> None:
        """
        [ACTION]
        - Teleology: Submit a prompt through the native clipboard-and-keystroke transport path.
        - Mechanism: Pastes provider text via OS input, waits for provider-specific settle conditions, verifies fidelity, then invokes the provider submit and priming path.
        - Reads: Provider adapter hooks, prompt text, bridge timings, and cancellation state.
        - Guarantee: Runs the native transport path through to provider priming when the clipboard flow succeeds.
        - Fails: Propagates NodeFailure from fidelity, readiness, or provider-submit checks.
        - When-needed: Open when native paste is the only reliable path on a flaky provider tab and you need to inspect its exact settle/submit logic.
        - Escalates-to: system/core/bridge_cdp.py::CDPTransportMixin._submit_prompt_with_fallback; system/core/bridge_chatgpt.py::ChatGPTBridgeMixin._prime_chatgpt_submission; system/core/bridge_gemini.py::GeminiBridgeMixin._prime_gemini_submission
        """
        adapter = self._provider_adapter(provider)
        if provider == "gemini":
            self._paste_input(prompt, hit_enter=False, allow_global_input=True)
            self._check_provider_js_result(provider, tab.evaluate(JS_FLUSH_GEMINI_INPUT), stage="provider_flush")
            self._sleep_with_cancel(
                self.timings.get("flush_sleep", 1.0),
                cancel=cancel,
                provider=provider,
                stage="provider_input",
                message="Aborted while waiting for Gemini clipboard flush",
            )
            self._ensure_prompt_fidelity(
                tab,
                prompt,
                provider=provider,
                transport_name="native_macos_input",
            )
            self._wait_for_gemini_submit_ready(tab, prompt, cancel=cancel)
            self._check_provider_js_result(provider, tab.evaluate(adapter.submit_js), stage="provider_submit")
            self._prime_gemini_submission(tab, prompt, cancel=cancel)
            return
        # For ChatGPT: paste first, wait for content to settle, then submit
        self._paste_input(prompt, hit_enter=False, allow_global_input=True)
        self._sleep_with_cancel(
            self.timings.get("post_paste_sleep", 2.5),
            cancel=cancel,
            provider=provider,
            stage="provider_input",
            message="Aborted while waiting for ChatGPT clipboard settle",
        )
        self._ensure_prompt_fidelity(
            tab,
            prompt,
            provider=provider,
            transport_name="native_macos_input",
        )
        # Use JS submit button click instead of Enter keystroke for reliability
        try:
            self._check_provider_js_result(provider, tab.evaluate(adapter.submit_js), stage="provider_submit")
        except Exception:
            # Fallback: paste with Enter via AppleScript
            self._paste_input("", hit_enter=True, allow_global_input=True)
        self._prime_chatgpt_submission(tab, prompt, cancel=cancel)

    def _submit_prompt_dom(
        self,
        tab: AgentTab,
        provider: str,
        prompt: str,
        *,
        cancel: Optional[threading.Event] = None,
    ) -> None:
        """
        [ACTION]
        - Teleology: Submit a prompt through the DOM-injection transport path when direct input is not preferred.
        - Mechanism: Injects prompt text with provider JS, waits for DOM settle, verifies fidelity, then performs provider-specific submit retries and priming.
        - Reads: Provider adapter DOM hooks, prompt text, bridge timings, and cancellation state.
        - Guarantee: Completes the DOM-inject submit path through provider priming when the provider accepts injected text.
        - Fails: Propagates NodeFailure from provider JS checks, readiness waits, or submit retries.
        - When-needed: Open when DOM injection is the active transport and the question is whether the provider accepted, rendered, or submitted the injected text.
        - Escalates-to: system/core/bridge_cdp.py::CDPTransportMixin._submit_prompt_with_fallback; system/core/bridge_chatgpt.py::ChatGPTBridgeMixin._prime_chatgpt_submission; system/core/bridge_gemini.py::GeminiBridgeMixin._prime_gemini_submission
        """
        adapter = self._provider_adapter(provider)
        if provider == "gemini":
            inject_js = adapter.dom_inject_js.replace("PROMPT", json.dumps(prompt))
            self._check_provider_js_result(provider, tab.evaluate(inject_js), stage="provider_input")
            self._sleep_with_cancel(
                self._dom_inject_settle_seconds(prompt),
                cancel=cancel,
                provider=provider,
                stage="provider_input",
                message="Aborted while waiting for Gemini DOM flush",
            )
            self._ensure_prompt_fidelity(
                tab,
                prompt,
                provider=provider,
                transport_name="dom_inject_click",
            )
            self._wait_for_gemini_submit_ready(tab, prompt, cancel=cancel)
            self._check_provider_js_result(provider, tab.evaluate(adapter.submit_js), stage="provider_submit")
            self._prime_gemini_submission(tab, prompt, cancel=cancel)
            return
        inject_js = adapter.dom_inject_js.replace("PROMPT", json.dumps(prompt))
        self._check_provider_js_result(provider, tab.evaluate(inject_js), stage="provider_input")
        self._sleep_with_cancel(
            self._dom_inject_settle_seconds(prompt),
            cancel=cancel,
            provider=provider,
            stage="provider_input",
            message="Aborted while waiting for DOM injection flush",
        )
        self._ensure_prompt_fidelity(
            tab,
            prompt,
            provider=provider,
            transport_name="dom_inject_click",
        )
        # ChatGPT voice-button workaround: the send button may not appear
        # immediately after text injection because React needs a render cycle
        # to swap the voice button for the send button. Retry up to 10 times
        # with 200ms gaps when the JS returns a RETRY: prefix.
        if provider == "chatgpt":
            # Active-background seat reassertion: refresh focus emulation,
            # lifecycle=active, and the visibility patch on the live document
            # immediately before clicking send. The page may have processed
            # framework events that re-cached document.hidden between hydration
            # and now; reasserting here means the click happens with a
            # known-patched view of the world.
            if self._chatgpt_active_background_seat_enabled():
                self._apply_chatgpt_active_background_seat(tab, reason="pre_submit_reassert")
            submit_result = None
            for _attempt in range(10):
                submit_result = tab.evaluate(adapter.submit_js)
                result_str = str(submit_result or "").strip()
                if result_str.startswith("OK"):
                    break
                if result_str.startswith("RETRY"):
                    self._sleep_with_cancel(
                        0.2, cancel=cancel, provider=provider,
                        stage="provider_submit",
                        message="Aborted while waiting for ChatGPT send button",
                    )
                    continue
                # Anything else (ERROR) — fail immediately
                break
            self._check_provider_js_result(provider, submit_result, stage="provider_submit")
            # Active-background seat reassertion immediately after click-send:
            # the SSE response stream lifecycle handlers (visibilitychange,
            # focus, etc.) get registered between submit and first response
            # token. Reasserting here keeps Chrome from re-throttling timers
            # used by the response-renderer.
            if self._chatgpt_active_background_seat_enabled():
                self._apply_chatgpt_active_background_seat(tab, reason="post_click_reassert")
            self._prime_chatgpt_submission(tab, prompt, cancel=cancel)
        else:
            self._check_provider_js_result(provider, tab.evaluate(adapter.submit_js), stage="provider_submit")

    def _submit_prompt_with_fallback(
        self,
        tab: AgentTab,
        provider: str,
        prompt: str,
        baseline: Optional[Dict[str, Any]] = None,
        *,
        cancel: Optional[threading.Event] = None,
        preferred_order: Optional[list[str]] = None,
        allow_global_input_transport: Optional[bool] = None,
        focus_meta: Optional[Dict[str, Any]] = None,
        allow_same_tab_retry: bool = False,
    ) -> Dict[str, Any]:
        """
        [ACTION]
        - Teleology: Submit a prompt through one or more transport paths until one produces a generation-start signal or the configured retries are exhausted.
        - Mechanism: Normalizes the transport order, optionally truncates it for fail-fast mode, clears provider input before each attempt, and records a structured attempt ledger.
        - Reads: Provider transport specs, prompt text, baseline response state, and cancellation state.
        - Guarantee: Returns the winning transport name, start signal, and attempt summary when one transport succeeds.
        - Fails: Raises NodeFailure when no transport is usable or all allowed transports fail.
        - When-needed: Open when a bridge run fails during prompt submission and the question is whether fallback sequencing or fail-fast policy caused the outcome.
        - Escalates-to: system/core/bridge_cdp.py::CDPTransportMixin._run_prompt_transport_attempt; system/core/bridge.py::BridgeManager._wait_for_generation_start
        """
        attempts: list[dict[str, Any]] = []
        allow_global_input = (
            self._allow_global_input_transport()
            if allow_global_input_transport is None
            else bool(allow_global_input_transport)
        )
        transports = self._transport_specs(
            preferred_order,
            allow_global_input_transport=allow_global_input,
        )
        if not transports:
            raise NodeFailure(
                f"{provider} prompt submission has no usable transports configured",
                category="provider_submit_failed_fast",
                stage="provider_submit",
                provider=provider,
            )
        if not allow_same_tab_retry:
            transports = transports[:1]
        if provider == "chatgpt":
            self._disable_chatgpt_thinking_if_active(tab)
        for idx, (transport_name, transport_fn) in enumerate(transports):
            try:
                self._clear_provider_input(tab, provider)
                transport_fn(tab, provider, prompt, cancel=cancel)
                signal = self._wait_for_generation_start(
                    tab,
                    provider,
                    baseline,
                    cancel=cancel,
                    prompt=prompt,
                )
                attempts.append(
                    {
                        "transport": transport_name,
                        "status": "success",
                        "start_signal": signal,
                    }
                )
                return {
                    "transport": transport_name,
                    "start_signal": signal,
                    "attempts": attempts,
                }
            except NodeFailure as exc:
                if cancel and cancel.is_set():
                    raise
                attempts.append(
                    {
                        "transport": transport_name,
                        "status": "error",
                        "category": exc.category,
                        "stage": exc.stage,
                        "message": str(exc),
                    }
                )
                if idx >= len(transports) - 1:
                    raise NodeFailure(
                        f"{provider} prompt submission failed fast after {len(attempts)} transport attempts",
                        category="provider_submit_failed_fast",
                        stage="provider_submit",
                        provider=provider,
                        details={"attempts": attempts},
                    ) from exc
                if allow_same_tab_retry:
                    try:
                        self._focus_tab(tab, meta=focus_meta, reason="transport_retry")
                    except Exception:
                        pass
                    self._wake_provider_input(tab, provider)
                    self._sleep_with_cancel(
                        self.timings.get("transport_retry_sleep", 0.75),
                        cancel=cancel,
                        provider=provider,
                        stage="provider_submit",
                        message="Aborted while preparing the next transport attempt",
                    )
        raise NodeFailure(
            f"{provider} prompt submission exhausted available transports",
            category="provider_submit_failed_fast",
            stage="provider_submit",
            provider=provider,
            details={"attempts": attempts},
        )

    def _normalized_transport_order(
        self,
        preferred_order: Optional[list[str]],
        *,
        allow_global_input_transport: bool,
    ) -> list[str]:
        """
        [ACTION]
        - Teleology: Canonicalize a caller-provided transport preference list into a usable bridge transport order.
        - Mechanism: Deduplicates names, drops unsupported or disallowed global-input transports, then falls back to defaults when needed.
        - Reads: Preferred transport names and the global transport allow/deny posture for the current attempt.
        - Guarantee: Returns a non-empty ordered list of transport names.
        - Fails: None — always falls back to a default transport order.
        - When-needed: Open when a run used an unexpected transport order and you need to see how preferences were normalized.
        - Escalates-to: system/core/bridge_cdp.py::CDPTransportMixin._submit_prompt_with_fallback; system/core/bridge.py::DEFAULT_TRANSPORT_ORDER
        """
        default_order = list(getattr(self, "transport_order", DEFAULT_TRANSPORT_ORDER))
        source = preferred_order if isinstance(preferred_order, list) else default_order
        normalized: list[str] = []
        for item in source:
            name = str(item).strip()
            if not name or name in normalized:
                continue
            if name in GLOBAL_INPUT_TRANSPORTS and not allow_global_input_transport:
                continue
            if name in SUPPORTED_TRANSPORTS:
                normalized.append(name)
        if not normalized:
            normalized = [name for name in default_order if allow_global_input_transport or name not in GLOBAL_INPUT_TRANSPORTS]
        if not normalized:
            normalized = [name for name in DEFAULT_TRANSPORT_ORDER if allow_global_input_transport or name not in GLOBAL_INPUT_TRANSPORTS]
        if not normalized:
            normalized = ["dom_inject_click"]
        return normalized

    def _should_retry_transport_failure(self, exc: NodeFailure) -> bool:
        """
        [ACTION]
        - Teleology: Decide whether a transport failure is retryable inside the bridge fallback loop.
        - Mechanism: Classifies the failure by normalized stage and category, allowing retries only for known transient transport phases.
        - Reads: Structured `NodeFailure.stage` and `NodeFailure.category`.
        - Guarantee: Returns a deterministic retry boolean for the given bridge failure.
        - Fails: None.
        - When-needed: Open when fallback behavior looks too eager or too conservative after a provider-side failure.
        - Escalates-to: system/core/bridge_cdp.py::CDPTransportMixin._submit_prompt_with_fallback; system/core/bridge.py::NodeFailure
        """
        stage = str(exc.stage or "").strip().lower()
        category = str(exc.category or "").strip().lower()
        return stage in {
            "provider_focus",
            "provider_input",
            "provider_submit",
            "provider_wake",
        } or (stage == "provider_wait" and category == "provider_cancelled")

    @staticmethod
    def _annotate_attempts(attempts: list[dict[str, Any]], session_attempt: int) -> list[dict[str, Any]]:
        """
        [ACTION]
        - Teleology: Stamp each recorded transport attempt with its enclosing session-attempt number.
        - Mechanism: Normalizes each attempt record into a dict and fills the `session_attempt` field when absent.
        - Reads: Raw transport-attempt ledger rows and the current session-attempt counter.
        - Guarantee: Returns a new list of attempt dicts with `session_attempt` populated.
        - Fails: None.
        - When-needed: Open when transport ledgers need correlation across retries in one bridge session.
        - Escalates-to: system/core/bridge_cdp.py::CDPTransportMixin._run_prompt_transport_attempt; system/core/bridge_cdp.py::CDPTransportMixin._submit_prompt_with_fallback
        """
        annotated: list[dict[str, Any]] = []
        for attempt in attempts:
            item = dict(attempt) if isinstance(attempt, dict) else {"status": "error", "message": str(attempt)}
            item.setdefault("session_attempt", session_attempt)
            annotated.append(item)
        return annotated

    def _run_prompt_transport_attempt(
        self,
        *,
        provider: str,
        target_url: str,
        prompt: str,
        transport_names: Sequence[str],
        meta: Dict[str, Any],
        cancel: Optional[threading.Event] = None,
    ) -> tuple[str, Dict[str, Any]]:
        """
        [ACTION]
        - Teleology: Execute one full bridge transport attempt from tab acquisition through extracted response text.
        - Mechanism: Acquires provider interaction ownership, reuses or opens a provider tab, runs the configured transport stack, emits bridge events for each phase, waits for completion, and extracts text.
        - Reads: Provider target URL, transport names, cancellation state, bridge timings, and live provider tab state.
        - Writes: Bridge event log entries via `_emit_bridge_event`.
        - Guarantee: Returns `(response_text, submit_summary)` when the attempt reaches extraction successfully.
        - Fails: Raises NodeFailure when tab open, prompt submission, wait, or extraction fails.
        - When-needed: Open when a live bridge session needs end-to-end transport-phase debugging, including tab reuse/open, wait progress, and emitted event phases.
        - Escalates-to: system/core/bridge_tab.py::TabSessionMixin._find_existing_provider_tab; system/core/bridge.py::bridge_debug_snapshot
        """
        adapter = self._provider_adapter(provider)
        tab: Optional[AgentTab] = None
        provider_baseline = {"count": 0, "last": ""}
        interaction_wait_s = 0.0
        submit_summary: Dict[str, Any] = {}
        attempt_id = str(uuid.uuid4())
        raw_names = [str(n).strip() for n in transport_names if str(n).strip()]
        allow_global_input_transport = self._allow_global_input_transport(meta)
        names = self._normalized_transport_order(
            raw_names,
            allow_global_input_transport=allow_global_input_transport,
        )
        if not names:
            raise NodeFailure(
                f"{provider} prompt submission has no transports configured",
                category="provider_submit_failed_fast",
                stage="provider_submit",
                provider=provider,
            )
        transport_joined = ",".join(names)
        use_global_input = any(n in GLOBAL_INPUT_TRANSPORTS for n in names)
        lock_ctx = self._input_lock if use_global_input else nullcontext()

        def _wait_extract(
            *,
            tab_obj: AgentTab,
            current_meta: Dict[str, Any],
            submit_transport: str,
        ) -> tuple[str, Dict[str, Any]]:
            def _emit_wait_progress(progress: Dict[str, Any]) -> None:
                detail = {
                    "attempt_id": attempt_id,
                    "transport": submit_transport,
                    "provider_interaction_wait_s": interaction_wait_s,
                    **dict(progress or {}),
                }
                self._emit_bridge_event(
                    provider=provider,
                    phase="provider_wait",
                    meta=current_meta,
                    tab_id=getattr(tab_obj, "tab_id", None),
                    detail=detail,
                    status=str(detail.get("wait_status") or "ok"),
                )

            self._emit_bridge_event(
                provider=provider,
                phase="provider_wait",
                meta=current_meta,
                tab_id=getattr(tab_obj, "tab_id", None),
                detail={
                    "attempt_id": attempt_id,
                    "transport": submit_transport,
                    "provider_interaction_wait_s": interaction_wait_s,
                },
            )
            self._register_waiting_tab(tab_obj, meta=current_meta)
            try:
                wait_summary = self._wait_until_done(
                    tab_obj,
                    adapter.done_js,
                    provider=provider,
                    baseline=provider_baseline,
                    cancel=cancel,
                    on_progress=_emit_wait_progress,
                    meta=current_meta,
                )
            finally:
                self._unregister_waiting_tab(tab_obj)
            wait_summary = dict(wait_summary) if isinstance(wait_summary, dict) else {}
            if wait_summary:
                wait_detail = dict(wait_summary)
                wait_detail.setdefault("attempt_id", attempt_id)
                self._emit_bridge_event(
                    provider=provider,
                    phase="done",
                    meta=current_meta,
                    tab_id=getattr(tab_obj, "tab_id", None),
                    detail=wait_detail,
                    status="warning" if bool(wait_summary.get("completed_despite_cancel")) else "ok",
                )
            extracted = self._extract_text(
                tab_obj,
                adapter.extract_js,
                provider=provider,
            )
            self._emit_bridge_event(
                provider=provider,
                phase="extract",
                meta=current_meta,
                tab_id=getattr(tab_obj, "tab_id", None),
                detail={
                    "attempt_id": attempt_id,
                    "response_chars": len(extracted),
                    "transport": submit_transport,
                },
            )
            return extracted, submit_summary
        try:
            interaction_meta = dict(meta) if isinstance(meta, dict) else {}
            interaction_meta["transport_name"] = transport_joined
            self._emit_bridge_event(
                provider=provider,
                phase="provider_queue",
                meta=interaction_meta,
                status="pending",
                detail={"attempt_id": attempt_id, "target_url": target_url, "transport_names": names},
            )
            with self._provider_interaction_context(provider, cancel=cancel, meta=interaction_meta) as interaction_slot:
                interaction_wait_s = float(interaction_slot.get("wait_s", 0.0) or 0.0)

                # [NEW] Try to reuse an existing idle provider tab before opening a fresh one
                tab = self._find_existing_provider_tab(provider, target_url, meta=interaction_meta)
                if tab is None:
                    tab = self._open_tab(target_url, provider=provider)
                self._emit_bridge_event(
                    provider=provider,
                    phase="tab_open",
                    meta=interaction_meta,
                    tab_id=getattr(tab, "tab_id", None),
                    detail={
                        "attempt_id": attempt_id,
                        "target_url": target_url,
                        "provider_interaction_wait_s": interaction_wait_s,
                    },
                )
                with lock_ctx:
                    if cancel and cancel.is_set():
                        raise NodeFailure(
                            "Aborted during focus acquisition",
                            category="provider_timeout",
                            stage="provider_focus",
                            provider=provider,
                        )
                    host_focus_changed = self._focus_tab(
                        tab,
                        meta=interaction_meta,
                        reason="prompt_transport",
                    )
                    self._inject_tab_identity(tab, meta)
                    self._emit_bridge_event(
                        provider=provider,
                        phase="focus",
                        meta=interaction_meta,
                        tab_id=getattr(tab, "tab_id", None),
                        detail={
                            "attempt_id": attempt_id,
                            "host_focus_changed": bool(host_focus_changed),
                            "host_focus_policy": self._host_focus_policy_snapshot(),
                        },
                    )
                    if use_global_input:
                        self._sleep_with_cancel(
                            self.timings.get("init_focus_sleep", 2.5),
                            cancel=cancel,
                            provider=provider,
                            stage="provider_focus",
                            message="Aborted while waiting for global input focus",
                        )
                    self._wake_provider_input(tab, provider)
                    self._emit_bridge_event(
                        provider=provider,
                        phase="wake",
                        meta=interaction_meta,
                        tab_id=getattr(tab, "tab_id", None),
                        detail={"attempt_id": attempt_id},
                    )
                    # [NEW] Auto-dismiss any blocking overlays before prompt injection
                    self._dismiss_provider_overlays(tab, provider, meta=interaction_meta)
                    self._sleep_with_cancel(
                        self.timings.get("wake_sleep", 1.0),
                        cancel=cancel,
                        provider=provider,
                        stage="provider_wake",
                        message="Aborted while waiting for provider wake",
                    )
                    provider_baseline = self._provider_start_baseline(tab, provider)
                    self._emit_bridge_event(
                        provider=provider,
                        phase="baseline",
                        meta=interaction_meta,
                        tab_id=getattr(tab, "tab_id", None),
                        detail={
                            "attempt_id": attempt_id,
                            "response_count": int(provider_baseline.get("count", 0) or 0),
                            "editor_length": int(provider_baseline.get("editor_length", 0) or 0),
                        },
                    )
                    submit_summary = dict(
                        self._submit_prompt_with_fallback(
                            tab,
                            provider,
                            prompt,
                            provider_baseline,
                            cancel=cancel,
                            preferred_order=list(names),
                            allow_global_input_transport=allow_global_input_transport,
                            focus_meta=interaction_meta,
                            allow_same_tab_retry=True,
                        )
                    )
                    submit_summary.setdefault("provider_interaction_wait_s", interaction_wait_s)
                    submit_summary.setdefault("attempt_id", attempt_id)
                    self._emit_bridge_event(
                        provider=provider,
                        phase="submit",
                        meta=interaction_meta,
                        tab_id=getattr(tab, "tab_id", None),
                        detail=dict(submit_summary),
                    )
                    if use_global_input:
                        self._sleep_with_cancel(
                            self.timings.get("post_paste_sleep", 1.5),
                            cancel=cancel,
                            provider=provider,
                            stage="provider_submit",
                            message="Aborted while waiting after global input submit",
                        )

            if tab is None:
                raise NodeFailure("Provider tab failed to open", category="provider_open", stage="provider_open")
            winning_transport = str(submit_summary.get("transport") or names[0] or "")
            return _wait_extract(
                tab_obj=tab,
                current_meta=interaction_meta,
                submit_transport=winning_transport,
            )
        except NodeFailure as exc:
            details = dict(exc.details) if isinstance(exc.details, dict) else {}
            details.setdefault("transport", transport_joined)
            details.setdefault("target_url", target_url)
            details.setdefault("node_id", str(meta.get("node_id", "") or "").strip() or None)
            details.setdefault("provider_interaction_wait_s", interaction_wait_s)
            details.setdefault("attempt_id", attempt_id)
            if tab is not None:
                details.setdefault("failure_tab_state", self._inspect_provider_tab(tab, provider))
            else:
                details.setdefault("failure_tab_state", {"active": False})
            self._emit_bridge_event(
                provider=provider,
                phase=exc.stage or "error",
                meta=interaction_meta if 'interaction_meta' in locals() else meta,
                tab_id=getattr(tab, "tab_id", None),
                status="error",
                detail={
                    "attempt_id": attempt_id,
                    "message": str(exc),
                    "category": exc.category,
                    "stage": exc.stage,
                    "transport": transport_joined,
                    "failure_tab_state": details.get("failure_tab_state"),
                },
            )
            raise NodeFailure(
                str(exc),
                category=exc.category,
                stage=exc.stage,
                provider=exc.provider or provider,
                details=details,
            ) from exc
        finally:
            self._emit_bridge_event(
                provider=provider,
                phase="tab_closed",
                meta=meta,
                tab_id=getattr(tab, "tab_id", None),
                detail={"attempt_id": attempt_id, "transport": transport_joined},
                status="ok" if tab is not None else "pending",
            )
            self._close_agent_tab(tab)
