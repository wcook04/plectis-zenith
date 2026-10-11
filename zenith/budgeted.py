"""Explicit, shared-budget OpenRouter calls; the free adapter stays zero-only."""
from __future__ import annotations

import contextlib
import fcntl
import hashlib
import json
import math
import os
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path

from system.lib import openrouter_free_runtime as api
from .providers import Provider, digest, now, text_digest, write_json

ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"
INPUT_OVERHEAD_TOKENS = 4096
MAX_BATCH_USD = Decimal("5")


def normalize_provider_slug(value):
    """An explicit endpoint slug; never infer a provider from a model ID."""
    if value is None:
        return None
    if not isinstance(value, str) or not re.fullmatch(r"[a-z0-9]+(?:[.-][a-z0-9]+)*(?:/[a-z0-9]+(?:[.-][a-z0-9]+)*)?", value):
        raise ValueError("provider_slug must be an exact lowercase OpenRouter endpoint slug")
    return value


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
    if prices.get("input_cache_read", Decimal(0)) > prices["prompt"]:
        raise RuntimeError("cached input read price must not exceed the full prompt price")
    for key, value in prices.items():
        if key not in ("prompt", "completion", "request", "input_cache_read") and value != 0:
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


def verified_endpoint(model, slug, prices, *, parameters, http_get=None):
    """Public endpoint metadata constrains routing; it is not a quota promise."""
    slug = normalize_provider_slug(slug)
    url = api._official_base_url() + "/api/v1/models/" + model + "/endpoints"
    data = (http_get or api._default_http_get)(url, {"Accept": "application/json"}, 30).get("data")
    if not isinstance(data, dict) or data.get("id") != model or not isinstance(data.get("endpoints"), list):
        raise RuntimeError("pinned provider endpoint metadata is malformed or for another model")
    matches = [e for e in data["endpoints"] if isinstance(e, dict) and e.get("tag") == slug]
    if len(matches) != 1:
        raise RuntimeError("pinned provider must exist exactly once in current endpoint metadata")
    endpoint = matches[0]
    if endpoint.get("model_id") != model or type(endpoint.get("status")) is not int or endpoint["status"] != 0:
        raise RuntimeError("pinned provider endpoint is not an active endpoint for this model")
    name = endpoint.get("provider_name")
    supported = endpoint.get("supported_parameters")
    if not isinstance(name, str) or not name.strip() or not isinstance(supported, list) or not set(parameters) <= set(supported):
        raise RuntimeError("pinned endpoint lacks provider identity or required parameter support")
    pricing = endpoint.get("pricing")
    if not isinstance(pricing, dict) or not {"prompt", "completion"} <= pricing.keys():
        raise RuntimeError("pinned endpoint lacks known prompt/completion pricing")
    # OpenRouter's endpoint discount is descriptive metadata, not a fee.
    rates = {k: amount(v, "endpoint pricing") for k, v in pricing.items() if k != "discount"}
    if "discount" in pricing and amount(pricing["discount"], "endpoint discount") > 1:
        raise RuntimeError("pinned endpoint discount metadata is invalid")
    if rates.get("input_cache_read", Decimal(0)) > rates["prompt"]:
        raise RuntimeError("pinned endpoint cached input price exceeds full prompt price")
    if any(v != 0 for k, v in rates.items() if k not in ("prompt", "completion", "request", "input_cache_read")):
        raise RuntimeError("pinned endpoint has unsupported ancillary charges")
    if any(rates.get(k, Decimal(0)) > prices.get(k, Decimal(0)) for k in ("prompt", "completion", "request")):
        raise RuntimeError("pinned endpoint pricing exceeds model catalogue reservation rates")
    positive_int(endpoint.get("context_length"), "endpoint context_length")
    positive_int(endpoint.get("max_completion_tokens"), "endpoint max_completion_tokens")
    if endpoint.get("max_prompt_tokens") is not None:
        positive_int(endpoint["max_prompt_tokens"], "endpoint max_prompt_tokens")
    return endpoint


def _strict_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate JSON key in budget ledger")
            result[key] = value
        return result
    def nonfinite(value):
        raise ValueError("nonfinite JSON in budget ledger")
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=nonfinite)


def recover_budget(budget_dir, evidence):
    """Explicit operator continuation after one unknown-cost HTTP 429.

    No network calls, retries, released reservations, or changed failed entries.
    ``authorization_ref`` records a caller-declared human authorization; it is
    not independently authenticated by this local file operation.
    """
    required = {"schema", "prior_ledger_sha256", "failed_call_id", "failed_call_sha256",
                "authorization_ref", "reason", "accept_unknown_cost"}
    if not isinstance(evidence, dict) or set(evidence) != required or evidence.get("schema") != "zenith_budget_recovery_evidence_v1":
        raise ValueError("recovery requires exact documented evidence fields")
    for key in ("prior_ledger_sha256", "failed_call_id", "failed_call_sha256"):
        if not isinstance(evidence[key], str) or not re.fullmatch(r"[0-9a-f]{64}", evidence[key]):
            raise ValueError("recovery requires exact SHA256 ledger/call bindings")
    if evidence["accept_unknown_cost"] is not True or any(
            not isinstance(evidence[k], str) or not evidence[k].strip() or len(evidence[k]) > 2048
            for k in ("authorization_ref", "reason")):
        raise ValueError("explicit authorization and acceptance of retained unknown cost are required")
    if api.redact(evidence) != evidence:
        raise ValueError("recovery evidence must not contain credentials")
    directory = Path(budget_dir).resolve()
    with (directory / ".budget.lock").open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            path = directory / "budget.json"
            raw = path.read_bytes()
            if hashlib.sha256(raw).hexdigest() != evidence["prior_ledger_sha256"]:
                raise RuntimeError("recovery prior ledger digest differs; re-observe before authorizing")
            ledger = _strict_json(raw)
            if not isinstance(ledger, dict):
                raise RuntimeError("recovery budget ledger must be an object")
            limits, entries = ledger.get("limits"), ledger.get("entries")
            if ledger.get("schema") != "zenith_shared_budget_v1" or ledger.get("halted") is not True or not isinstance(limits, dict) or not isinstance(entries, dict) or not entries:
                raise RuntimeError("recovery requires an existing halted shared budget")
            if limits != budget_options("validation/model", limits.get("max_cost_usd"), limits.get("max_calls"), limits.get("max_output_tokens"), directory):
                raise RuntimeError("recovery budget limits are malformed or bound to another directory")
            reserved = reported = Decimal(0)
            for call_id, entry in entries.items():
                if not isinstance(call_id, str) or not re.fullmatch(r"[0-9a-f]{64}", call_id) or not isinstance(entry, dict) or entry.get("schema") != "zenith_api_call_v1" or entry.get("call_id") != call_id or entry.get("status") not in ("failed", "response_supplied", "attempt_started") or "cost" not in entry:
                    raise RuntimeError("recovery ledger attempt is malformed")
                if entry["status"] == "attempt_started":
                    raise RuntimeError("recovery cannot proceed with an in-flight or unfinished attempt")
                bound = amount(entry.get("reserved_cost_usd"), "stored reservation")
                reserved += bound
                if entry["cost"] is not None:
                    cost = amount(entry["cost"], "stored cost")
                    if cost > bound:
                        raise RuntimeError("recovery rejects reported cost exceeding its reservation")
                    reported += cost
                elif entry["status"] == "response_supplied":
                    raise RuntimeError("recovery successful attempt lacks known cost")
                response = entry.get("provider_response")
                usage = response.get("usage") if isinstance(response, dict) else None
                if isinstance(usage, dict) and usage.get("cost") is not None and (
                        entry["cost"] is None or amount(usage["cost"], "recorded response cost") != amount(entry["cost"])):
                    raise RuntimeError("recovery stored cost differs from reported response accounting")
            if reserved != amount(ledger.get("total_reserved_usd")) or reported != amount(ledger.get("total_reported_cost_usd")) or reserved > amount(limits["max_cost_usd"]) or len(entries) > limits["max_calls"]:
                raise RuntimeError("recovery ledger accounting is inconsistent")
            history = ledger.get("recoveries", [])
            if not isinstance(history, list):
                raise RuntimeError("recovery history is malformed")
            recovered = set()
            for event in history:
                previous = event.get("evidence", {}) if isinstance(event, dict) else {}
                if not isinstance(previous, dict):
                    raise RuntimeError("recovery history evidence is malformed")
                key = previous.get("failed_call_id")
                if not isinstance(event, dict) or event.get("schema") != "zenith_budget_recovery_receipt_v1" or key in recovered or key not in entries or previous.get("failed_call_sha256") != digest(entries[key]):
                    raise RuntimeError("recovery history has duplicate or changed failed attempts")
                recovered.add(key)
            call_id = evidence["failed_call_id"]
            failed = entries.get(call_id)
            if call_id in recovered or not isinstance(failed, dict) or digest(failed) != evidence["failed_call_sha256"]:
                raise RuntimeError("recovery failed call differs or was already recovered")
            error = failed.get("error")
            if failed.get("status") != "failed" or failed.get("cost") is not None or not isinstance(error, str) or not re.search(r"(?:HTTPError: 429 Client Error\b|OpenRouter HTTP 429:)", error) or ledger.get("halt_reason") != error:
                raise RuntimeError("recovery is restricted to the exact unknown-cost HTTP 429 halt")
            if any(k != call_id and k not in recovered and e["status"] == "failed" for k, e in entries.items()):
                raise RuntimeError("recovery cannot waive another unrecovered failed attempt")
            receipt = {"schema": "zenith_budget_recovery_receipt_v1", "recorded_at": now(), "evidence": dict(evidence),
                       "prior_halt_reason": ledger["halt_reason"], "retained_reserved_usd": ledger["total_reserved_usd"],
                       "known_reported_cost_usd": ledger["total_reported_cost_usd"],
                       "failed_reservation_usd": failed["reserved_cost_usd"], "failed_actual_cost": None}
            ledger.update(halted=False, recoveries=history + [receipt])
            write_json(path, ledger)
            return receipt
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


class OpenRouterBudgetedProvider(Provider):
    """One paid attempt per run/node, with atomic worst-case batch reservations.

    ``caller`` is the existing HTTP POST protocol (url, headers, payload, timeout).
    ``catalogue_get`` is its metadata-only GET counterpart. Both are injection
    seams for tests; default transports accept only the official HTTPS host.
    """
    def __init__(self, run_dir: Path, model: str, max_cost_usd, max_calls: int,
                 max_output_tokens: int = 4096, budget_dir: Path | None = None,
                 caller=None, catalogue_get=None, provider_slug=None):
        super().__init__(run_dir)
        self.options = budget_options(model, max_cost_usd, max_calls, max_output_tokens, budget_dir)
        self.model = model
        self.provider_slug = normalize_provider_slug(provider_slug)
        self.budget_dir = Path(self.options["budget_dir"])
        self.caller = caller or api._default_http_post
        self.catalogue_get = catalogue_get

    def _bind_run(self):
        handoff = self.run_dir / "handoff"
        handoff.mkdir(parents=True, exist_ok=True)
        binding = {"schema": "zenith_paid_run_binding_v1", "model": self.model, "limits": self.options}
        if self.provider_slug is not None:
            binding["provider_slug"] = self.provider_slug
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
                if self.provider_slug is not None and (previous.get("requested_provider_slug") != self.provider_slug or
                        not previous.get("verified_provider_name") or packet.get("actual_provider") != previous["verified_provider_name"]):
                    raise RuntimeError("stored budgeted response differs from the pinned provider")
                self.receipt(identity, provider="openrouter_budgeted", status="loaded_previous_response",
                             execution_kind="openrouter_budgeted",
                             requested_model=self.model, actual_model=packet.get("model"),
                             usage=packet.get("usage"), cost=packet.get("cost"), endpoint=ENDPOINT,
                             budget_dir=str(self.budget_dir), requested_provider_slug=self.provider_slug,
                             verified_provider_name=previous.get("verified_provider_name"), actual_provider=packet.get("actual_provider"))
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
        call_binding = {**identity, "provider": "openrouter_budgeted", "requested_model": self.model}
        if self.provider_slug is not None:
            call_binding["provider_slug"] = self.provider_slug
        call_id = digest(call_binding)
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
        endpoint = None
        if self.provider_slug is not None:
            parameters = ["max_tokens", "temperature"] + (["reasoning"] if "reasoning" in row["supported_parameters"] else [])
            endpoint = verified_endpoint(self.model, self.provider_slug, prices, parameters=parameters,
                                         http_get=self.catalogue_get)
            context_length = min(context_length, endpoint["context_length"])
        # One token per UTF8 byte plus a disclosed conservative framing allowance.
        input_bound = len(prompt.encode("utf-8")) + INPUT_OVERHEAD_TOKENS
        output_bound = self.options["max_output_tokens"]
        if input_bound + output_bound > context_length:
            raise RuntimeError("conservative UTF8 input bound plus output cap exceeds verified model context")
        top_output = (row.get("top_provider") or {}).get("max_completion_tokens")
        if top_output is not None and output_bound > positive_int(top_output, "max_completion_tokens"):
            raise RuntimeError("output cap exceeds verified provider maximum")
        if endpoint is not None and (output_bound > endpoint["max_completion_tokens"] or
                endpoint.get("max_prompt_tokens") is not None and input_bound > endpoint["max_prompt_tokens"]):
            raise RuntimeError("conservative prompt or output cap exceeds pinned endpoint maximum")
        # Cached reads are discounted alternatives, never an assumed cache hit.
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
        if endpoint is not None:
            record.update(requested_provider_slug=self.provider_slug, verified_provider_name=endpoint["provider_name"],
                          endpoint_metadata_sha256=digest(endpoint), endpoint_metadata=endpoint)
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
            if self.provider_slug is not None:
                payload["provider"]["only"] = [self.provider_slug]
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
            actual_provider = data.get("provider")
            record["actual_provider"] = actual_provider
            if endpoint is not None and actual_provider != endpoint["provider_name"]:
                raise RuntimeError("paid response provider differs from the verified pinned endpoint")
            packet = {"response_text": content, "requested_model": self.model, "model": actual_model,
                      "usage": usage, "cost": str(cost), "endpoint": ENDPOINT, "generation_id": data.get("id"),
                      "actual_provider": actual_provider}
            record.update(status="response_supplied", provider_receipt=packet, response_sha256=text_digest(content))
            self._settle(call_id, record, call_path)
            self.receipt(identity, provider="openrouter_budgeted", status="response_supplied",
                         execution_kind="openrouter_budgeted",
                         requested_model=self.model, actual_model=actual_model, usage=usage, cost=str(cost),
                         reserved_cost_usd=str(reservation), endpoint=ENDPOINT, budget_dir=str(self.budget_dir),
                         response_sha256=text_digest(content), requested_provider_slug=self.provider_slug,
                         verified_provider_name=record.get("verified_provider_name"), actual_provider=actual_provider)
            return content
        except BaseException as exc:
            message = api.safe_error(exc, secrets=(token,))
            record.update(status="failed", error=message)
            self._settle(call_id, record, call_path, halt=True)
            self.receipt(identity, provider="openrouter_budgeted", status="failed", requested_model=self.model,
                         execution_kind="openrouter_budgeted",
                         actual_model=record.get("provider_response", {}).get("model"),
                         usage=record.get("provider_response", {}).get("usage"), cost=record.get("cost"),
                         reserved_cost_usd=str(reservation), error=message, endpoint=ENDPOINT,
                         requested_provider_slug=self.provider_slug, verified_provider_name=record.get("verified_provider_name"),
                         actual_provider=record.get("provider_response", {}).get("provider"))
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
