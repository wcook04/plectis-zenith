"""Explicit, shared-budget OpenRouter calls; the free adapter stays zero-only."""
from __future__ import annotations

import contextlib
import fcntl
import json
import math
import os
from decimal import Decimal, InvalidOperation
from pathlib import Path

from system.lib import openrouter_free_runtime as api
from .providers import Provider, digest, now, text_digest, write_json

ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"
INPUT_OVERHEAD_TOKENS = 4096
MAX_BATCH_USD = Decimal("5")


def durable(value):
    """Keep malformed nonfinite provider values auditable without invalid JSON."""
    if isinstance(value, float) and not math.isfinite(value):
        return str(value)
    if isinstance(value, dict):
        return {k: durable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [durable(v) for v in value]
    return value


def amount(value, label="amount") -> Decimal:
    if isinstance(value, bool) or value in (None, ""):
        raise ValueError(f"{label} must be a known finite nonnegative number")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise ValueError(f"{label} must be a known finite nonnegative number") from None
    if not result.is_finite() or result < 0:
        raise ValueError(f"{label} must be a known finite nonnegative number")
    return result


def positive_int(value, label):
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{label} must be a positive integer")
    return value


def budget_options(model, max_cost_usd, max_calls, max_output_tokens, budget_dir):
    if not isinstance(model, str) or "/" not in model or any(c.isspace() for c in model):
        raise ValueError("openrouter_budgeted requires an explicit namespace/model ID")
    if model.startswith("openrouter/") or ":" in model:
        raise ValueError("budgeted inference requires a concrete catalogue model, without routing variants")
    limit = amount(max_cost_usd, "max_cost_usd")
    if not 0 < limit <= MAX_BATCH_USD:
        raise ValueError(f"max_cost_usd must be positive and at most {MAX_BATCH_USD} for this bounded trial")
    if budget_dir is None:
        raise ValueError("openrouter_budgeted requires an explicit shared budget_dir")
    return {"max_cost_usd": str(limit), "max_calls": positive_int(max_calls, "max_calls"),
            "max_output_tokens": positive_int(max_output_tokens, "max_output_tokens"),
            "budget_dir": str(Path(budget_dir).resolve())}


def verified_model(model: str, *, http_get=None):
    matches = [row for row in api._catalogue_rows(http_get=http_get) if row.get("id") == model]
    if len(matches) != 1:
        raise RuntimeError("budgeted model must exist exactly once in the current public catalogue")
    row = matches[0]
    pricing = row.get("pricing")
    if not isinstance(pricing, dict) or not {"prompt", "completion"} <= pricing.keys():
        raise RuntimeError("budgeted model lacks known prompt/completion pricing")
    prices = {key: amount(value, "catalogue pricing") for key, value in pricing.items()}
    for key, value in prices.items():
        if key not in ("prompt", "completion", "request") and value != 0:
            raise RuntimeError("budgeted adapter rejects ancillary charges")
    architecture = row.get("architecture", {})
    if architecture.get("output_modalities") != ["text"] or "text" not in architecture.get("input_modalities", []):
        raise RuntimeError("budgeted adapter requires a catalogue-verified text output model")
    contexts = [positive_int(row.get("context_length"), "catalogue context_length")]
    top = row.get("top_provider") or {}
    if top.get("context_length") is not None:
        contexts.append(positive_int(top["context_length"], "provider context_length"))
    parameters = row.get("supported_parameters")
    if not isinstance(parameters, list) or "max_tokens" not in parameters:
        raise RuntimeError("budgeted adapter requires advertised max_tokens support")
    return row, prices, min(contexts)


class OpenRouterBudgetedProvider(Provider):
    """One paid attempt per run/node, with atomic worst-case batch reservations.

    ``caller`` is the existing HTTP POST protocol (url, headers, payload, timeout).
    ``catalogue_get`` is its metadata-only GET counterpart. Both are injection
    seams for tests; default transports accept only the official HTTPS host.
    """
    def __init__(self, run_dir: Path, model: str, max_cost_usd, max_calls: int,
                 max_output_tokens: int = 4096, budget_dir: Path | None = None,
                 caller=None, catalogue_get=None):
        super().__init__(run_dir)
        self.options = budget_options(model, max_cost_usd, max_calls, max_output_tokens, budget_dir)
        self.model = model
        self.budget_dir = Path(self.options["budget_dir"])
        self.caller = caller or api._default_http_post
        self.catalogue_get = catalogue_get

    def _bind_run(self):
        handoff = self.run_dir / "handoff"
        handoff.mkdir(parents=True, exist_ok=True)
        binding = {"schema": "zenith_paid_run_binding_v1", "model": self.model, "limits": self.options}
        with self._lock, (handoff / ".budgeted.lock").open("a+") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            try:
                path = handoff / "budgeted_binding.json"
                if path.exists():
                    if json.loads(path.read_text()) != binding:
                        raise RuntimeError("paid run budget/model binding is immutable; a fresh ledger cannot resend this run")
                else:
                    if any((handoff / "api_calls" / "openrouter_budgeted").glob("*.json")):
                        raise RuntimeError("paid run binding is missing while attempt receipts exist")
                    write_json(path, binding)
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)

    @contextlib.contextmanager
    def _ledger(self):
        self.budget_dir.mkdir(parents=True, exist_ok=True)
        with self._lock, (self.budget_dir / ".budget.lock").open("a+") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            try:
                path = self.budget_dir / "budget.json"
                ledger = json.loads(path.read_text()) if path.exists() else {
                    "schema": "zenith_shared_budget_v1", "limits": self.options,
                    "entries": {}, "halted": False, "total_reserved_usd": "0", "total_reported_cost_usd": "0"}
                if ledger.get("schema") != "zenith_shared_budget_v1" or ledger.get("limits") != self.options:
                    raise RuntimeError("shared budget limits are immutable; all runs must use the same limits")
                entries = ledger.get("entries")
                if not isinstance(entries, dict):
                    raise RuntimeError("shared budget ledger is malformed")
                reserved = sum((amount(e.get("reserved_cost_usd"), "stored reservation") for e in entries.values()), Decimal(0))
                reported = sum((amount(e["cost"], "stored cost") for e in entries.values() if e.get("cost") is not None), Decimal(0))
                if (reserved != amount(ledger.get("total_reserved_usd")) or
                        reported != amount(ledger.get("total_reported_cost_usd")) or
                        reserved > amount(self.options["max_cost_usd"]) or len(entries) > self.options["max_calls"]):
                    raise RuntimeError("shared budget ledger accounting is inconsistent")
                for entry in entries.values():
                    if entry.get("status") == "attempt_started":
                        try:
                            os.kill(positive_int(entry.get("owner_pid"), "attempt owner_pid"), 0)
                        except (ProcessLookupError, ValueError):
                            ledger["halted"] = True
                            ledger["halt_reason"] = "interrupted process; actual cost is unknown"
                            write_json(path, ledger)
                            break
                yield ledger, path
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)

    def _previous(self, ledger, call_id, identity):
        previous = ledger["entries"].get(call_id)
        if previous:
            if previous.get("status") == "response_supplied":
                packet = previous["provider_receipt"]
                if text_digest(packet["response_text"]) != previous["response_sha256"]:
                    raise RuntimeError("stored budgeted response hash mismatch")
                self.receipt(identity, provider="openrouter_budgeted", status="loaded_previous_response",
                             execution_kind="openrouter_budgeted",
                             requested_model=self.model, actual_model=packet.get("model"),
                             usage=packet.get("usage"), cost=packet.get("cost"), endpoint=ENDPOINT,
                             budget_dir=str(self.budget_dir))
                return packet["response_text"]
            if previous.get("status") == "attempt_started":
                ledger["halted"] = True
                ledger["halt_reason"] = "unfinished exact attempt; actual cost is unknown"
                write_json(self.budget_dir / "budget.json", ledger)
            raise RuntimeError("this exact paid attempt failed or was interrupted; it cannot be resent")
        if ledger.get("halted"):
            raise RuntimeError("shared paid budget is halted because actual cost or transport outcome is uncertain")
        if any(e["run_id"] == identity["run_id"] and e["node_id"] == identity["node_id"] for e in ledger["entries"].values()):
            raise RuntimeError("a paid node already had its single attempt; repair prompts and retries are disabled")
        return None

    def ask_ai(self, prompt: str, config: dict | None = None, cancel=None) -> str:
        identity = self.identity(prompt, config)
        self._bind_run()
        call_id = digest({**identity, "provider": "openrouter_budgeted", "requested_model": self.model})
        call_path = self.run_dir / "handoff" / "api_calls" / "openrouter_budgeted" / (call_id + ".json")
        with self._ledger() as (ledger, _):
            cached = self._previous(ledger, call_id, identity)
            if cached is not None:
                return cached
        if cancel is not None and cancel.is_set():
            raise RuntimeError("paid call cancelled before reservation")
        api._official_base_url()
        token = api._resolve_api_key(None)
        row, prices, context_length = verified_model(self.model, http_get=self.catalogue_get)
        # One token per UTF8 byte plus a disclosed conservative framing allowance.
        input_bound = len(prompt.encode("utf-8")) + INPUT_OVERHEAD_TOKENS
        output_bound = self.options["max_output_tokens"]
        if input_bound + output_bound > context_length:
            raise RuntimeError("conservative UTF8 input bound plus output cap exceeds verified model context")
        top_output = (row.get("top_provider") or {}).get("max_completion_tokens")
        if top_output is not None and output_bound > positive_int(top_output, "max_completion_tokens"):
            raise RuntimeError("output cap exceeds verified provider maximum")
        reservation = prices["prompt"] * input_bound + prices["completion"] * output_bound + prices.get("request", Decimal(0))
        record = {"schema": "zenith_api_call_v1", **identity, "call_id": call_id,
                  "provider": "openrouter_budgeted", "requested_model": self.model,
                  "execution_kind": "openrouter_budgeted",
                  "endpoint": ENDPOINT, "recorded_at": now(), "status": "attempt_started", "cost": None,
                  "owner_pid": os.getpid(),
                  "reserved_cost_usd": str(reservation), "input_token_bound": input_bound,
                  "input_bound_method": "UTF8 bytes plus 4096 framing tokens",
                  "max_output_tokens": output_bound, "context_length": context_length,
                  "catalogue_pricing": {k: str(v) for k, v in prices.items()},
                  "catalogue_sha256": digest(row), "budget_dir": str(self.budget_dir)}
        with self._ledger() as (ledger, path):
            cached = self._previous(ledger, call_id, identity)
            if cached is not None:
                return cached
            if len(ledger["entries"]) >= self.options["max_calls"]:
                raise RuntimeError("shared paid budget max_calls reached")
            if amount(ledger["total_reserved_usd"]) + reservation > amount(self.options["max_cost_usd"]):
                raise RuntimeError("worst-case reservation would exceed the shared paid budget")
            ledger["entries"][call_id] = record
            ledger["total_reserved_usd"] = str(amount(ledger["total_reserved_usd"]) + reservation)
            write_json(path, api.redact(ledger, secrets=(token,)))
            write_json(call_path, api.redact(record, secrets=(token,)))
        self.receipt(identity, **{k: v for k, v in record.items() if k not in identity})
        try:
            if cancel is not None and cancel.is_set():
                raise RuntimeError("paid call cancelled after reservation; no request sent")
            payload = {"model": self.model, "messages": [{"role": "user", "content": prompt}],
                       "stream": False, "temperature": 0, "max_tokens": output_bound,
                       "provider": {"allow_fallbacks": False, "require_parameters": True,
                                    "sort": "price", "max_price": {
                                        "prompt": float(prices["prompt"] * 1000000),
                                        "completion": float(prices["completion"] * 1000000),
                                        "request": float(prices.get("request", Decimal(0))), "image": 0}}}
            if "reasoning" in row["supported_parameters"]:
                payload["reasoning"] = {"enabled": False}
            data = self.caller(ENDPOINT, {"Authorization": "Bearer " + token,
                                       "Content-Type": "application/json", "Accept": "application/json"}, payload, 120)
            data = api.redact(durable(data), secrets=(token,))
            record["provider_response"] = data
            usage = data.get("usage")
            if not isinstance(usage, dict):
                raise RuntimeError("paid response has no known usage and actual cost")
            cost = amount(usage.get("cost"), "actual cost")
            record["cost"] = str(cost)
            if usage.get("is_byok") is True:
                raise RuntimeError("upstream BYOK billing is outside the verified OpenRouter cost budget")
            if cost > reservation:
                raise RuntimeError("reported actual cost exceeds the conservative reservation; budget halted")
            for key, bound in (("prompt_tokens", input_bound), ("completion_tokens", output_bound)):
                count = usage.get(key)
                if isinstance(count, bool) or not isinstance(count, int) or count < 0 or count > bound:
                    raise RuntimeError("reported token usage is unknown or exceeds the reserved bounds")
            choices = data.get("choices")
            content = choices[0].get("message", {}).get("content") if isinstance(choices, list) and choices and isinstance(choices[0], dict) else None
            if not isinstance(content, str) or not content.strip():
                raise RuntimeError("paid response has no nonempty assistant content")
            actual_model = data.get("model")
            if not isinstance(actual_model, str) or not actual_model.strip():
                raise RuntimeError("paid response omitted actual model identity")
            packet = {"response_text": content, "requested_model": self.model, "model": actual_model,
                      "usage": usage, "cost": str(cost), "endpoint": ENDPOINT, "generation_id": data.get("id")}
            record.update(status="response_supplied", provider_receipt=packet, response_sha256=text_digest(content))
            self._settle(call_id, record, call_path)
            self.receipt(identity, provider="openrouter_budgeted", status="response_supplied",
                         execution_kind="openrouter_budgeted",
                         requested_model=self.model, actual_model=actual_model, usage=usage, cost=str(cost),
                         reserved_cost_usd=str(reservation), endpoint=ENDPOINT, budget_dir=str(self.budget_dir),
                         response_sha256=text_digest(content))
            return content
        except BaseException as exc:
            message = api.safe_error(exc, secrets=(token,))
            record.update(status="failed", error=message)
            self._settle(call_id, record, call_path, halt=True)
            self.receipt(identity, provider="openrouter_budgeted", status="failed", requested_model=self.model,
                         execution_kind="openrouter_budgeted",
                         actual_model=record.get("provider_response", {}).get("model"),
                         usage=record.get("provider_response", {}).get("usage"), cost=record.get("cost"),
                         reserved_cost_usd=str(reservation), error=message, endpoint=ENDPOINT)
            raise RuntimeError(message) from None

    def _settle(self, call_id, record, call_path, *, halt=False):
        with self._ledger() as (ledger, path):
            ledger["entries"][call_id] = api.redact(record)
            ledger["total_reported_cost_usd"] = str(sum((amount(e["cost"]) for e in ledger["entries"].values() if e.get("cost") is not None), Decimal(0)))
            if halt:
                ledger["halted"] = True
                ledger["halt_reason"] = record["error"]
            write_json(path, ledger)
            write_json(call_path, api.redact(record))

    def budget_status(self):
        with self._ledger() as (ledger, _):
            return {k: v for k, v in ledger.items() if k != "entries"} | {"attempt_count": len(ledger["entries"])}
