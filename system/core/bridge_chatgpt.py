"""
[PURPOSE]
- Teleology: ChatGPT-specific bridge logic — compose state detection, prompt-consumed checks,
  submit-transition waits, and submission priming.
- Mechanism: Mixin class ChatGPTBridgeMixin contributes the _chatgpt_* methods to BridgeManager
  via multiple inheritance.

[INTERFACE]
- Exports: ChatGPTBridgeMixin

[FLOW]
- BridgeManager inherits from ChatGPTBridgeMixin alongside other provider mixins.
- _provider_compose_state and similar dispatch methods in BridgeManager core delegate to
  these provider-specific implementations.

[DEPENDENCIES]
- system.core.bridge: AgentTab, NodeFailure, helpers (used via self).

[CONSTRAINTS]
- All methods access self.X (BridgeManager state) — works only as a mixin.
- When-needed: Open when ChatGPT-specific compose-state, submit-consumption, or provider interrupt handling needs inspection apart from the shared CDP transport layer.
- Escalates-to: system/core/bridge.py::BridgeManager; system/core/bridge_cdp.py::CDPTransportMixin._submit_prompt_with_fallback
- Navigation-group: bridge_runtime
"""
from __future__ import annotations

import json
import re
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

# Circular-import safe: bridge.py defines these BEFORE its mixin imports.
from system.core.bridge import AgentTab, NodeFailure  # noqa: E402


class ChatGPTBridgeMixin:
    """
    [ROLE]
    - Teleology: Provide the ChatGPT-specific readiness and submit-transition logic mixed into BridgeManager.
    - Mechanism: Normalizes composer-state JS output, interprets whether submission consumed the prompt, and primes the provider after click or Enter fallback.
    - Ownership: Mixed into BridgeManager; does not own browser or transport lifecycle state by itself.
    - Mutability: Reads provider state via `self` and transient tab JS evaluation results.
    - Concurrency: Relies on BridgeManager provider locking around shared provider interaction.
    - When-needed: Open when a ChatGPT run stalls after injection or fails to consume the composer even though the shared transport path succeeded.
    - Escalates-to: system/core/bridge.py::BridgeManager; system/core/bridge.py::AgentTab.evaluate
    """

    def _chatgpt_compose_state(self, tab: AgentTab) -> Dict[str, Any]:
        """
        [ACTION]
        - Teleology: Normalize the live ChatGPT composer state into one predictable mapping for downstream readiness and interrupt checks.
        - Mechanism: Evaluates the provider adapter's composer-state JS and coerces expected keys into stable bool/int/str fields, with a zeroed fallback shape on error.
        - Reads: ChatGPT composer-state JS via AgentTab.evaluate().
        - Guarantee: Returns a dict containing the expected compose-state keys even when evaluation fails.
        - Fails: None — evaluation errors degrade to the empty-state mapping.
        - When-needed: Open when a ChatGPT tab looks wrong in diagnostics and the question is how compose-state fields are derived.
        - Escalates-to: system/core/bridge.py::bridge_debug_snapshot; system/core/bridge.py::AgentTab.evaluate
        """
        adapter = self._provider_adapter("chatgpt")
        try:
            state = tab.evaluate(str(adapter.composer_state_js or ""))
            if isinstance(state, dict):
                normalized = dict(state)
                normalized["editor_length"] = int(normalized.get("editor_length", 0) or 0)
                normalized["send_found"] = bool(normalized.get("send_found"))
                normalized["send_enabled"] = bool(normalized.get("send_enabled"))
                normalized["stop_visible"] = bool(normalized.get("stop_visible"))
                normalized["conversation_started"] = bool(normalized.get("conversation_started"))
                normalized["url"] = str(normalized.get("url", "") or "").strip()
                normalized["dialog_visible"] = bool(normalized.get("dialog_visible"))
                normalized["dialog_preview"] = str(normalized.get("dialog_preview", "") or "").strip()
                normalized["got_it_visible"] = bool(normalized.get("got_it_visible"))
                normalized["temporary_limit_interrupt"] = bool(normalized.get("temporary_limit_interrupt"))
                return normalized
        except Exception:
            pass
        return {
            "editor_length": 0,
            "send_found": False,
            "send_enabled": False,
            "stop_visible": False,
            "conversation_started": False,
            "url": "",
            "dialog_visible": False,
            "dialog_preview": "",
            "got_it_visible": False,
            "temporary_limit_interrupt": False,
        }

    @staticmethod
    def _chatgpt_submit_consumed_prompt(state: Mapping[str, Any], expected_chars: int) -> bool:
        """
        [ACTION]
        - Teleology: Decide whether ChatGPT has actually consumed the submitted prompt.
        - Mechanism: Interprets composer-length shrinkage, disabled send state, and generation-start markers against the expected prompt size.
        - Reads: Normalized compose-state fields and the expected prompt character count.
        - Guarantee: Returns `True` only when the compose state indicates the prompt left the editor or generation began.
        - Fails: None.
        - When-needed: Open when ChatGPT submission looks ambiguous and the runtime must distinguish "still in composer" from "provider accepted it."
        - Escalates-to: system/core/bridge_chatgpt.py::ChatGPTBridgeMixin._wait_for_chatgpt_submit_transition; system/core/bridge_chatgpt.py::ChatGPTBridgeMixin._prime_chatgpt_submission
        """
        editor_length = int(state.get("editor_length", 0) or 0)
        if bool(state.get("stop_visible")) or bool(state.get("conversation_started")):
            return True
        clear_threshold = max(1, min(32, int(expected_chars * 0.05))) if expected_chars > 0 else 0
        prompt_cleared = expected_chars > 0 and editor_length <= clear_threshold
        send_consumed = expected_chars > 0 and not bool(state.get("send_enabled")) and editor_length < expected_chars
        return bool(prompt_cleared or send_consumed)

    def _wait_for_chatgpt_submit_transition(
        self,
        tab: AgentTab,
        *,
        expected_chars: int,
        cancel: Optional[threading.Event] = None,
        timeout_s: float = 0.8,
    ) -> Dict[str, Any]:
        """
        [ACTION]
        - Teleology: Wait for ChatGPT to show evidence that a submitted prompt left the composer and entered response generation.
        - Mechanism: Polls normalized compose state until `_chatgpt_submit_consumed_prompt` returns true or the timeout expires.
        - Reads: ChatGPT compose state and cancellation state.
        - Guarantee: Returns the last observed compose-state mapping, successful or timed out.
        - Fails: Raises NodeFailure only if `_sleep_with_cancel` sees cancellation.
        - When-needed: Open when ChatGPT submission timing is suspect and you need to see how long the runtime waits before falling back or failing.
        - Escalates-to: system/core/bridge_chatgpt.py::ChatGPTBridgeMixin._prime_chatgpt_submission; system/core/bridge_cdp.py::CDPTransportMixin._submit_prompt_dom
        """
        deadline = time.time() + max(0.1, float(timeout_s))
        poll_s = min(max(0.1, self.poll_interval_s / 3.0), 0.25)
        last_state: Dict[str, Any] = {}
        while time.time() < deadline:
            state = self._chatgpt_compose_state(tab)
            last_state = state
            if self._chatgpt_submit_consumed_prompt(state, expected_chars):
                return state
            self._sleep_with_cancel(
                poll_s,
                cancel=cancel,
                provider="chatgpt",
                stage="provider_submit",
                message="Aborted while waiting for ChatGPT submit transition",
            )
        return last_state

    def _prime_chatgpt_submission(
        self,
        tab: AgentTab,
        prompt: str,
        *,
        cancel: Optional[threading.Event] = None,
    ) -> Dict[str, Any]:
        """
        [ACTION]
        - Teleology: Confirm that ChatGPT actually consumed the injected prompt, with an Enter-key fallback when the initial submit click does not transition the composer.
        - Mechanism: Waits for submit transition once, retries with `_submit_with_enter_key`, then waits again before raising a structured NodeFailure.
        - Reads: Canonicalized prompt length and live ChatGPT compose state.
        - Guarantee: Returns the compose-state snapshot that confirmed prompt consumption.
        - Fails: Raises NodeFailure when ChatGPT still has not consumed the prompt after click and Enter fallback.
        - When-needed: Open when ChatGPT prompt injection succeeds but the provider never appears to start generating.
        - Escalates-to: system/core/bridge_cdp.py::CDPTransportMixin._submit_with_enter_key; system/core/bridge_chatgpt.py::ChatGPTBridgeMixin._wait_for_chatgpt_submit_transition
        """
        expected_chars = len(self._canonicalize_prompt_text(prompt))
        state = self._wait_for_chatgpt_submit_transition(
            tab,
            expected_chars=expected_chars,
            cancel=cancel,
        )
        if self._chatgpt_submit_consumed_prompt(state, expected_chars):
            return state
        self._submit_with_enter_key(tab, "chatgpt")
        state = self._wait_for_chatgpt_submit_transition(
            tab,
            expected_chars=expected_chars,
            cancel=cancel,
            timeout_s=1.2,
        )
        if self._chatgpt_submit_consumed_prompt(state, expected_chars):
            return state
        raise NodeFailure(
            "chatgpt submit did not consume the composer after click and Enter fallback",
            category="provider_selector_failure",
            stage="provider_submit",
            provider="chatgpt",
            details={
                "expected_prompt_chars": expected_chars,
                "composer_state": state,
            },
        )
