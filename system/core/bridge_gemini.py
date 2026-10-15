"""
[PURPOSE]
- Teleology: Gemini-specific bridge logic — compose state detection, submit-ready waits,
  prompt-consumed checks, submit-transition waits, priming, wait-state, and shell-text recognition.
- Mechanism: Mixin class GeminiBridgeMixin contributes the _gemini_* methods to BridgeManager
  via multiple inheritance. Each method takes (self, tab: AgentTab, ...) and operates on
  the Gemini web UI through Chrome DevTools Protocol.

[INTERFACE]
- Exports: GeminiBridgeMixin

[FLOW]
- BridgeManager inherits from GeminiBridgeMixin alongside other provider mixins.
- _provider_compose_state and similar dispatch methods in BridgeManager core delegate to
  these provider-specific implementations.

[DEPENDENCIES]
- system.core.bridge: AgentTab, NodeFailure, helpers (deferred via partial-module imports).

[CONSTRAINTS]
- All methods access self.X (BridgeManager state) — works only as a mixin.
- Must not import the BridgeManager class itself (circular).
- When-needed: Open when Gemini-specific compose-state, readiness, submit-consumption, or cancelled-response detection needs inspection apart from shared transport logic.
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


class GeminiBridgeMixin:
    """
    [ROLE]
    - Teleology: Provide the Gemini-specific readiness, submit-transition, and wait-state logic mixed into BridgeManager.
    - Mechanism: Normalizes Gemini composer state, waits for the provider to register prompt text, interprets prompt consumption, and classifies shell-like placeholder text during waits.
    - Ownership: Mixed into BridgeManager; provider lifecycle ownership remains with the manager.
    - Mutability: Reads transient provider state through `self` and tab JS evaluation results.
    - Concurrency: Relies on BridgeManager provider locking around shared Gemini interaction.
    - When-needed: Open when Gemini behaves differently from ChatGPT and the issue is likely in provider-specific readiness or placeholder-response handling.
    - Escalates-to: system/core/bridge.py::BridgeManager; system/core/bridge.py::AgentTab.evaluate
    """

    def _gemini_compose_state(self, tab: AgentTab) -> Dict[str, Any]:
        """
        [ACTION]
        - Teleology: Normalize live Gemini composer state into a stable mapping for readiness, submit, and wait-state decisions.
        - Mechanism: Evaluates the provider adapter's composer-state JS and coerces expected fields into stable bool/int/str values, with an empty fallback shape on error.
        - Reads: Gemini composer-state JS via AgentTab.evaluate().
        - Guarantee: Returns a dict containing the expected compose-state keys even when evaluation fails.
        - Fails: None — evaluation errors degrade to the empty-state mapping.
        - When-needed: Open when Gemini diagnostics show surprising editor or spinner state and you need the normalization contract.
        - Escalates-to: system/core/bridge.py::bridge_debug_snapshot; system/core/bridge.py::AgentTab.evaluate
        """
        adapter = self._provider_adapter("gemini")
        try:
            state = tab.evaluate(str(adapter.composer_state_js or ""))
            if isinstance(state, dict):
                normalized = dict(state)
                normalized["editor_length"] = int(normalized.get("editor_length", 0) or 0)
                normalized["send_found"] = bool(normalized.get("send_found"))
                normalized["send_enabled"] = bool(normalized.get("send_enabled"))
                normalized["stop_visible"] = bool(normalized.get("stop_visible"))
                normalized["spinner_visible"] = bool(normalized.get("spinner_visible"))
                normalized["conversation_started"] = bool(normalized.get("conversation_started"))
                normalized["has_you_said"] = bool(normalized.get("has_you_said"))
                normalized["body_has_stopped"] = bool(normalized.get("body_has_stopped"))
                normalized["model_count"] = int(normalized.get("model_count", 0) or 0)
                normalized["model_last"] = str(normalized.get("model_last", "") or "").strip()
                normalized["url"] = str(normalized.get("url", "") or "").strip()
                return normalized
        except Exception:
            pass
        return {
            "editor_length": 0,
            "send_found": False,
            "send_enabled": False,
            "stop_visible": False,
            "spinner_visible": False,
            "conversation_started": False,
            "has_you_said": False,
            "body_has_stopped": False,
            "model_count": 0,
            "model_last": "",
            "url": "",
        }

    def _wait_for_gemini_submit_ready(
        self,
        tab: AgentTab,
        prompt: str,
        *,
        cancel: Optional[threading.Event] = None,
    ) -> Dict[str, Any]:
        """
        [ACTION]
        - Teleology: Wait until Gemini has registered enough of the prompt and enabled submission.
        - Mechanism: Computes a size-scaled timeout, polls normalized compose state, and checks both editor-length registration and send-button readiness.
        - Reads: Canonicalized prompt length, Gemini compose state, bridge timing config, and cancellation state.
        - Guarantee: Returns the compose-state snapshot that proved Gemini was ready to submit.
        - Fails: Raises NodeFailure when Gemini never registers the prompt within the scaled timeout or when cancellation fires during the wait.
        - When-needed: Open when Gemini rejects or ignores large prompt injection and you need the exact readiness threshold logic.
        - Escalates-to: system/core/bridge_gemini.py::GeminiBridgeMixin._gemini_compose_state; system/core/bridge_cdp.py::CDPTransportMixin._submit_prompt_cdp_input
        """
        expected_chars = len(self._canonicalize_prompt_text(prompt))
        effective_timeout = self._scaled_timeout(
            prompt,
            base_key="composer_ready_timeout_s",
            default_base=4.0,
            per_100k_key="composer_ready_per_100k_chars_s",
            default_per_100k=4.0,
            cap_key="composer_ready_max_s",
            default_cap=20.0,
        )
        deadline = time.time() + effective_timeout
        poll_s = min(max(0.2, self.poll_interval_s / 2.0), 0.6)
        last_state: Dict[str, Any] = {}
        min_registered = 0
        if expected_chars > 0:
            if expected_chars <= 4096:
                min_registered = expected_chars
            else:
                min_registered = max(4096, int(expected_chars * 0.92))
        while time.time() < deadline:
            state = self._gemini_compose_state(tab)
            last_state = state
            editor_length = int(state.get("editor_length", 0) or 0)
            length_tolerance = max(64, int(expected_chars * 0.03)) if expected_chars > 0 else 0
            length_ready = (
                expected_chars <= 0
                or editor_length >= min_registered
                or abs(editor_length - expected_chars) <= length_tolerance
            )
            if length_ready and bool(state.get("send_enabled")):
                return state
            self._sleep_with_cancel(
                poll_s,
                cancel=cancel,
                provider="gemini",
                stage="provider_input",
                message="Aborted while waiting for Gemini composer readiness",
            )
        raise NodeFailure(
            f"gemini composer did not register the prompt within {effective_timeout:.1f}s",
            category="provider_selector_failure",
            stage="provider_input",
            provider="gemini",
            details={
                "expected_prompt_chars": expected_chars,
                "composer_state": last_state,
                "timeout_s": effective_timeout,
            },
        )

    @staticmethod
    def _gemini_submit_consumed_prompt(state: Mapping[str, Any], expected_chars: int) -> bool:
        """
        [ACTION]
        - Teleology: Decide whether Gemini has actually consumed the submitted prompt.
        - Mechanism: Interprets spinner/stop markers, conversation-start markers, and editor-length reduction against the expected prompt size.
        - Reads: Normalized Gemini compose-state fields and the expected prompt character count.
        - Guarantee: Returns `True` only when Gemini's compose state indicates prompt consumption or response generation.
        - Fails: None.
        - When-needed: Open when Gemini submit behavior is ambiguous and the runtime must tell "prompt still staged" from "prompt accepted."
        - Escalates-to: system/core/bridge_gemini.py::GeminiBridgeMixin._wait_for_gemini_submit_transition; system/core/bridge_gemini.py::GeminiBridgeMixin._prime_gemini_submission
        """
        editor_length = int(state.get("editor_length", 0) or 0)
        if bool(state.get("stop_visible")) or bool(state.get("spinner_visible")):
            return True
        if bool(state.get("conversation_started")) or bool(state.get("has_you_said")):
            return True
        clear_threshold = max(1, min(32, int(expected_chars * 0.05))) if expected_chars > 0 else 0
        prompt_cleared = expected_chars > 0 and editor_length <= clear_threshold
        send_consumed = expected_chars > 0 and not bool(state.get("send_enabled")) and editor_length < expected_chars
        return bool(prompt_cleared or send_consumed)

    def _wait_for_gemini_submit_transition(
        self,
        tab: AgentTab,
        *,
        expected_chars: int,
        cancel: Optional[threading.Event] = None,
        timeout_s: float = 0.8,
    ) -> Dict[str, Any]:
        """
        [ACTION]
        - Teleology: Wait for Gemini to show that the submitted prompt has left the composer and moved into response generation.
        - Mechanism: Polls normalized Gemini compose state until `_gemini_submit_consumed_prompt` returns true or the timeout expires.
        - Reads: Gemini compose state and cancellation state.
        - Guarantee: Returns the last observed compose-state mapping, successful or timed out.
        - Fails: Raises NodeFailure only when `_sleep_with_cancel` observes cancellation.
        - When-needed: Open when Gemini submission timing is suspect and you need the post-click wait contract before fallback.
        - Escalates-to: system/core/bridge_gemini.py::GeminiBridgeMixin._prime_gemini_submission; system/core/bridge_cdp.py::CDPTransportMixin._submit_prompt_dom
        """
        deadline = time.time() + max(0.1, float(timeout_s))
        poll_s = min(max(0.1, self.poll_interval_s / 3.0), 0.25)
        last_state: Dict[str, Any] = {}
        while time.time() < deadline:
            state = self._gemini_compose_state(tab)
            last_state = state
            if self._gemini_submit_consumed_prompt(state, expected_chars):
                return state
            self._sleep_with_cancel(
                poll_s,
                cancel=cancel,
                provider="gemini",
                stage="provider_submit",
                message="Aborted while waiting for Gemini submit transition",
            )
        return last_state

    def _prime_gemini_submission(
        self,
        tab: AgentTab,
        prompt: str,
        *,
        cancel: Optional[threading.Event] = None,
    ) -> Dict[str, Any]:
        """
        [ACTION]
        - Teleology: Confirm that Gemini consumed the injected prompt, with an Enter-key fallback if the initial submit did not move the composer.
        - Mechanism: Waits once for submit transition, retries with `_submit_with_enter_key`, then waits again before raising a structured NodeFailure.
        - Reads: Canonicalized prompt length and live Gemini compose state.
        - Guarantee: Returns the compose-state snapshot that confirmed Gemini consumed the prompt.
        - Fails: Raises NodeFailure when Gemini still has not consumed the prompt after click and Enter fallback.
        - When-needed: Open when Gemini prompt injection appears successful but response generation never starts.
        - Escalates-to: system/core/bridge_cdp.py::CDPTransportMixin._submit_with_enter_key; system/core/bridge_gemini.py::GeminiBridgeMixin._wait_for_gemini_submit_transition
        """
        expected_chars = len(self._canonicalize_prompt_text(prompt))
        state = self._wait_for_gemini_submit_transition(
            tab,
            expected_chars=expected_chars,
            cancel=cancel,
        )
        if self._gemini_submit_consumed_prompt(state, expected_chars):
            return state
        self._submit_with_enter_key(tab, "gemini")
        state = self._wait_for_gemini_submit_transition(
            tab,
            expected_chars=expected_chars,
            cancel=cancel,
            timeout_s=1.2,
        )
        if self._gemini_submit_consumed_prompt(state, expected_chars):
            return state
        raise NodeFailure(
            "gemini submit did not consume the composer after click and Enter fallback",
            category="provider_selector_failure",
            stage="provider_submit",
            provider="gemini",
            details={
                "expected_prompt_chars": expected_chars,
                "composer_state": state,
            },
        )

    def _gemini_wait_state(self, tab: AgentTab) -> Dict[str, Any]:
        """
        [ACTION]
        - Teleology: Classify Gemini's response-progress state into meaningful-response, placeholder-only, and cancelled signals for wait loops and diagnostics.
        - Mechanism: Starts from normalized compose state, inspects the last model text, applies shell-text heuristics, and annotates the returned mapping with derived booleans.
        - Reads: Gemini compose state and shell-text heuristics.
        - Guarantee: Returns the compose-state mapping augmented with `placeholder_only`, `meaningful_response`, and `cancelled`.
        - Fails: None — upstream compose-state errors already degrade to the empty-state mapping.
        - When-needed: Open when Gemini shows "Show thinking" or similar shell text and you need to know why the runtime treated the response as placeholder-only or cancelled.
        - Escalates-to: system/core/bridge_gemini.py::GeminiBridgeMixin._looks_like_gemini_shell_text; system/core/bridge.py::bridge_diagnostics
        """
        state = self._gemini_compose_state(tab)
        raw_last = str(state.get("model_last", "") or "").strip()
        normalized_last = re.sub(r"\s+", " ", raw_last).strip().lower()
        shell_like_last = self._looks_like_gemini_shell_text(raw_last)
        placeholder_only = bool(state.get("model_count")) and (
            shell_like_last
            or normalized_last in {
                "",
                "show thinking",
                "answer now",
                "show thinking answer now",
            }
        )
        meaningful_response = bool(state.get("model_count")) and not placeholder_only and "you stopped this response" not in normalized_last
        cancelled = bool(
            state.get("body_has_stopped")
            and not state.get("stop_visible")
            and not state.get("spinner_visible")
            and not meaningful_response
            and (int(state.get("editor_length", 0) or 0) > 0 or state.get("conversation_started"))
        )
        state["placeholder_only"] = placeholder_only
        state["meaningful_response"] = meaningful_response
        state["cancelled"] = cancelled
        return state

    @staticmethod
    def _looks_like_gemini_shell_text(text: str) -> bool:
        """
        [ACTION]
        - Teleology: Recognize Gemini placeholder or shell-like text that should not count as a meaningful model answer.
        - Mechanism: Normalizes whitespace, strips measurements shell phrases, then checks short-title and shell-token heuristics against the remaining text.
        - Reads: Raw Gemini model text.
        - Guarantee: Returns `True` only for text patterns that look like Gemini shell or placeholder output.
        - Fails: None.
        - When-needed: Open when Gemini surfaced short UI-like text and the runtime treated it as placeholder-only or cancelled output.
        - Escalates-to: system/core/bridge_gemini.py::GeminiBridgeMixin._gemini_wait_state; system/core/bridge.py::bridge_diagnostics
        """
        normalized = re.sub(r"\s+", " ", str(text or "")).strip()
        if not normalized:
            return False
        sanitized = re.sub(
            r"\b(?:answer now|show thinking|gemini said|chatgpt said)\b",
            " ",
            normalized,
            flags=re.IGNORECASE,
        )
        sanitized = re.sub(r"\s+", " ", sanitized).strip()
        lowered = sanitized.lower()
        if "you stopped this response" in lowered:
            return True
        if lowered in {"show thinking", "answer now", "gemini said", "chatgpt said"}:
            return True
        stripped = sanitized.rstrip(":").strip()
        if stripped:
            tokens = stripped.split(" ")
            if 2 <= len(tokens) <= 8 and re.fullmatch(r"[A-Z][A-Za-z0-9'’-]*ing", tokens[0]):
                connector_tokens = {
                    "a",
                    "an",
                    "the",
                    "and",
                    "or",
                    "to",
                    "for",
                    "of",
                    "in",
                    "on",
                    "with",
                    "by",
                    "via",
                    "&",
                    "/",
                    "+",
                }

                def _shell_token(candidate: str) -> bool:
                    cleaned = candidate.strip("()[]{}\"'")
                    if not cleaned:
                        return False
                    if cleaned.lower() in connector_tokens:
                        return True
                    if re.fullmatch(r"[A-Z][A-Za-z0-9'’-]*", cleaned):
                        return True
                    if re.fullmatch(r"[A-Z0-9]{1,6}", cleaned):
                        return True
                    return False

                if all(_shell_token(token) for token in tokens[1:]):
                    return True
        return bool(
            len(sanitized) <= 120
            and re.fullmatch(
                r"[A-Z][a-z]+(?: (?:[A-Z][a-z]+|of|the|and|to|for|in|on|with)){1,6}",
                sanitized,
            )
        )
