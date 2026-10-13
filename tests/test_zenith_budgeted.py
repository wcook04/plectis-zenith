"""Shared paid budgets use synthetic prices, fake credentials and mock HTTP only."""
import copy
import hashlib
from decimal import Decimal
import json
import os
import tempfile
import threading
import time
import traceback
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import Mock, patch

from zenith.budgeted import (OpenRouterBudgetedProvider, ENDPOINT, budget_options, verified_model,
                             normalize_provider_slug, recover_budget)
from zenith.providers import digest
from zenith.cli import parser

SECRET = "sk-or-v1-FAKE_BUDGETED_SECRET_NEVER_PERSIST"
MODEL = "synthetic/paid-text"
ROW = {"id": MODEL, "context_length": 131072,
       "architecture": {"input_modalities": ["text"], "output_modalities": ["text"]},
       "pricing": {"prompt": "0.000001", "completion": "0.000002", "request": "0"},
       "supported_parameters": ["max_tokens", "temperature"],
       "top_provider": {"context_length": 131072, "max_completion_tokens": 4096}}
SLUG = "synthetic-host/fp8"
PINNED = {"model_id": MODEL, "tag": SLUG, "provider_name": "Synthetic Host", "status": 0,
          "context_length": 131072, "max_completion_tokens": 4096, "max_prompt_tokens": None,
          "supported_parameters": ["max_tokens", "temperature"],
          "pricing": {"prompt": ".0000005", "completion": ".000001", "input_cache_read": ".0000001", "discount": .5}}


def reply(cost="0.0001", **extra):
    return {"model": "synthetic/actual-alias", "id": "synthetic-generation", "usage": {
        "prompt_tokens": 10, "completion_tokens": 3, "total_tokens": 13, "cost": cost},
        "choices": [{"message": {"content": "valid synthetic output"}}], **extra}


class BudgetedTests(unittest.TestCase):
    def setUp(self):
        # These legacy tests deliberately stress arbitrary synthetic rates and
        # aliases. Real model/price admission is exercised without these mocks
        # in test_provider_policy.py; here the independent budget is the unit.
        for name in ("require_model", "require_prices"):
            admission = patch("zenith.budgeted." + name)
            admission.start()
            self.addCleanup(admission.stop)
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.env = patch.dict(os.environ, {"OPENROUTER_API_KEY": SECRET}, clear=True)
        self.env.start()
        self.addCleanup(self.env.stop)
        self.addCleanup(self.tmp.cleanup)

    def provider(self, run="RUN", caller=None, row=None, **limits):
        seen = []
        def catalogue(url, headers, timeout):
            self.assertEqual(url, "https://openrouter.ai/api/v1/models")
            self.assertNotIn("Authorization", headers)
            seen.append(url)
            return {"data": [row or ROW]}
        provider = OpenRouterBudgetedProvider(self.root / run, MODEL,
             limits.get("max_cost_usd", "0.25"), limits.get("max_calls", 40),
             limits.get("max_output_tokens", 1024), self.root / "shared",
             caller=caller or Mock(return_value=reply()), catalogue_get=catalogue)
        provider.catalogue_seen = seen
        return provider

    def ask(self, provider, node="case1", prompt="hello"):
        return provider.ask_ai(prompt, {"meta": {"session_id": provider.run_dir.name, "node_id": node}})

    def ledger(self):
        return json.loads((self.root / "shared" / "budget.json").read_text())

    def pinned_provider(self, run="PIN", *, endpoint=None, row=None, caller=None, slug=SLUG):
        seen = []
        def catalogue(url, headers, timeout):
            self.assertNotIn("Authorization", headers)
            seen.append(url)
            if url == "https://openrouter.ai/api/v1/models":
                return {"data": [row or ROW]}
            self.assertEqual(url, f"https://openrouter.ai/api/v1/models/{MODEL}/endpoints")
            return {"data": {"id": MODEL, "endpoints": [endpoint or PINNED]}}
        provider = OpenRouterBudgetedProvider(self.root / run, MODEL, ".25", 40, 1024,
            self.root / "shared", caller=caller or Mock(return_value=reply(provider="Synthetic Host")),
            catalogue_get=catalogue, provider_slug=slug)
        provider.catalogue_seen = seen
        return provider

    def recovery_evidence(self, call_id=None):
        raw = (self.root / "shared/budget.json").read_bytes()
        ledger = json.loads(raw)
        call_id = call_id or next(k for k, e in ledger["entries"].items() if e["status"] == "failed")
        return {"schema": "zenith_budget_recovery_evidence_v1", "prior_ledger_sha256": hashlib.sha256(raw).hexdigest(),
                "failed_call_id": call_id, "failed_call_sha256": digest(ledger["entries"][call_id]),
                "authorization_ref": "synthetic-human-instruction-1", "reason": "explicitly retain unknown 429 reservation",
                "accept_unknown_cost": True}

    def unknown_429(self, run="rate-limited"):
        provider = self.provider(run, caller=Mock(side_effect=RuntimeError("OpenRouter HTTP 429: capacity unavailable")))
        with self.assertRaisesRegex(RuntimeError, "HTTP 429"):
            self.ask(provider)
        return provider

    def test_structured_output_is_bound_transmitted_and_accounted_without_search(self):
        row=copy.deepcopy(ROW)
        row['supported_parameters'] += ['response_format','structured_outputs']
        row['pricing']['web_search']='.01'
        caller=Mock(return_value=reply())
        provider=self.provider(row=row,caller=caller)
        shape={'type':'json_schema','json_schema':{'name':'test','strict':True,'schema':{'type':'object','properties':{},'required':[],'additionalProperties':False}}}
        provider.ask_ai('hello',{'meta':{'session_id':'RUN','node_id':'structured'},'response_format':shape,'system_prompt':'Execute only your current task.'})
        payload=caller.call_args.args[2]
        self.assertEqual(payload['response_format'],shape)
        self.assertEqual(payload['messages'][0],{'role':'system','content':'Execute only your current task.'})
        self.assertIn('system_prompt_sha256',next(iter(self.ledger()['entries'].values())))
        self.assertNotIn('plugins',payload)
        record=next(iter(self.ledger()['entries'].values()))
        self.assertEqual(record['response_format_sha256'],digest(shape))
        self.assertGreater(record['input_token_bound'],4096+len('hello'))
        unsupported=self.provider(run='UNSUPPORTED',caller=Mock())
        with self.assertRaisesRegex(RuntimeError,'structured output'):
            unsupported.ask_ai('hi',{'meta':{'session_id':'UNSUPPORTED','node_id':'s'},'response_format':shape})
        unsupported.caller.assert_not_called()

    def test_reasoning_is_explicit_bound_and_within_existing_output_budget(self):
        row=copy.deepcopy(ROW)
        row['supported_parameters'].append('reasoning')
        caller=Mock(return_value=reply())
        provider=self.provider(row=row,caller=caller)
        provider.ask_ai('hello',{'meta':{'session_id':'RUN','node_id':'reason'},'reasoning_effort':'medium'})
        payload=caller.call_args.args[2]
        self.assertEqual(payload['reasoning'],{'effort':'medium','exclude':True})
        self.assertEqual(payload['max_tokens'],1024)
        self.assertEqual(next(iter(self.ledger()['entries'].values()))['reasoning_effort'],'medium')
        unsupported=self.provider(run='UNSUPPORTED',caller=Mock())
        with self.assertRaisesRegex(RuntimeError,'reasoning support'):
            unsupported.ask_ai('hello',{'meta':{'session_id':'UNSUPPORTED','node_id':'reason'},'reasoning_effort':'medium'})
        unsupported.caller.assert_not_called()

    def test_provider_slug_is_explicit_and_run_binding_is_immutable(self):
        self.assertIsNone(normalize_provider_slug(None))
        self.assertEqual(normalize_provider_slug("deepinfra/fp8"), "deepinfra/fp8")
        for slug in ("", "DeepInfra", "deepinfra/", "/fp8", "a/b/c", " a", "a?token=x", False):
            with self.subTest(slug=slug), self.assertRaises(ValueError):
                normalize_provider_slug(slug)
        plain = self.provider()
        self.ask(plain)
        binding = json.loads((plain.run_dir / "handoff/budgeted_binding.json").read_text())
        self.assertNotIn("provider_slug", binding)
        changed = self.pinned_provider(plain.run_dir.name, caller=Mock())
        with self.assertRaisesRegex(RuntimeError, "binding is immutable"):
            self.ask(changed)
        changed.caller.assert_not_called()
        self.assertEqual(changed.catalogue_seen, [])

    def test_pin_checks_public_metadata_and_actual_provider_with_full_rate_reservation(self):
        def post(url, headers, payload, timeout):
            self.assertEqual(payload["provider"]["only"], [SLUG])
            self.assertFalse(payload["provider"]["allow_fallbacks"])
            self.assertEqual(payload["provider"]["max_price"]["prompt"], 1.0)
            self.assertEqual(next(iter(self.ledger()["entries"].values()))["reserved_cost_usd"], "0.006149")
            return reply(provider="Synthetic Host")
        provider = self.pinned_provider(caller=post)
        self.ask(provider)
        self.assertEqual(len(provider.catalogue_seen), 2)
        ledger = self.ledger()
        self.assertNotIn("provider_slug", ledger["limits"])
        entry = next(iter(ledger["entries"].values()))
        self.assertEqual(entry["endpoint_metadata_sha256"], digest(PINNED))
        self.assertEqual(entry["requested_provider_slug"], SLUG)
        self.assertEqual(entry["actual_provider"], "Synthetic Host")
        self.assertEqual(entry["verified_provider_name"], "Synthetic Host")
        os.environ.pop("OPENROUTER_API_KEY")
        cached = self.pinned_provider(caller=Mock(side_effect=AssertionError("must not send")))
        self.ask(cached)
        self.assertEqual(cached.catalogue_seen, [])
        receipts = [json.loads(p.read_text()) for p in (provider.run_dir / "handoff/receipts").glob("*.json")]
        for receipt in receipts:
            self.assertEqual(receipt["requested_provider_slug"], SLUG)
            self.assertEqual(receipt["verified_provider_name"], "Synthetic Host")
            if receipt["status"] != "attempt_started":
                self.assertEqual(receipt["actual_provider"], "Synthetic Host")

    def test_unverified_pin_parameters_prices_or_bounds_never_send(self):
        changes = [{"tag": "other"}, {"status": 1}, {"status": False}, {"model_id": "other/model"},
                   {"provider_name": ""}, {"supported_parameters": ["max_tokens"]},
                   {"context_length": 4500}, {"max_prompt_tokens": 4096}, {"max_completion_tokens": 1000}]
        changes += [{"pricing": {**PINNED["pricing"], key: value}} for key, value in (
            ("input_cache_read", ".0000006"), ("input_cache_write", ".0000001"),
            ("discount", 1.1), ("prompt", "NaN"))]
        for index, change in enumerate(changes):
            provider = self.pinned_provider(str(index), endpoint={**PINNED, **change}, caller=Mock())
            with self.subTest(change=change), self.assertRaises((RuntimeError, ValueError)):
                self.ask(provider)
            provider.caller.assert_not_called()
        row = {**ROW, "supported_parameters": ROW["supported_parameters"] + ["reasoning"]}
        provider = self.pinned_provider("reasoning", row=row, caller=Mock())
        with self.assertRaisesRegex(RuntimeError, "parameter support"):
            self.ask(provider)
        provider.caller.assert_not_called()
        self.assertFalse((self.root / "shared/budget.json").exists())

    def test_wrong_or_missing_actual_provider_halts_and_cached_pin_cannot_be_forged(self):
        provider = self.pinned_provider(caller=Mock(return_value=reply(provider="Other Host")))
        with self.assertRaisesRegex(RuntimeError, "provider differs"):
            self.ask(provider)
        ledger = self.ledger()
        self.assertTrue(ledger["halted"])
        entry = next(iter(ledger["entries"].values()))
        self.assertEqual(entry["cost"], "0.0001")
        self.assertEqual(entry["actual_provider"], "Other Host")
        self.assertEqual(entry["status"], "failed")
        # In a separate synthetic batch, an altered cached receipt cannot become
        # an accepted provider match without any new network request.
        provider = self.pinned_provider("cached")
        provider.budget_dir = self.root / "cached-budget"
        provider.options["budget_dir"] = str(provider.budget_dir)
        self.ask(provider)
        path = provider.budget_dir / "budget.json"
        ledger = json.loads(path.read_text())
        next(iter(ledger["entries"].values()))["provider_receipt"]["actual_provider"] = "Other Host"
        path.write_text(json.dumps(ledger))
        provider.caller.reset_mock()
        with self.assertRaisesRegex(RuntimeError, "stored budgeted response differs"):
            self.ask(provider)
        provider.caller.assert_not_called()

    def test_explicit_recovery_retains_unknown_cost_full_reservation_and_blocks_resend(self):
        failed = self.unknown_429()
        before = self.ledger()
        evidence = self.recovery_evidence()
        receipt = recover_budget(self.root / "shared", evidence)
        after = self.ledger()
        self.assertFalse(after["halted"])
        self.assertEqual(after["entries"], before["entries"])
        self.assertEqual(after["limits"], before["limits"])
        self.assertEqual(after["total_reserved_usd"], before["total_reserved_usd"])
        self.assertEqual(after["total_reported_cost_usd"], before["total_reported_cost_usd"])
        self.assertEqual(after["recoveries"], [receipt])
        self.assertIsNone(receipt["failed_actual_cost"])
        with self.assertRaisesRegex(RuntimeError, "cannot be resent"):
            self.ask(failed)
        self.assertEqual(failed.caller.call_count, 1)
        self.ask(self.pinned_provider())
        self.assertEqual(len(self.ledger()["entries"]), 2)
        self.assertEqual(self.ledger()["total_reserved_usd"], "0.012298")
        self.assertEqual(self.ledger()["total_reported_cost_usd"], "0.0001")

    def test_recovery_is_atomic_once_per_failed_call_and_can_record_a_later_authorized_429(self):
        self.unknown_429()
        evidence = self.recovery_evidence()
        def recover(_):
            try:
                recover_budget(self.root / "shared", evidence)
                return True
            except RuntimeError:
                return False
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sum(pool.map(recover, range(2))), 1)
        self.unknown_429("second-failure")
        ids = [k for k, e in self.ledger()["entries"].items() if e["status"] == "failed"]
        with self.assertRaisesRegex(RuntimeError, "already recovered"):
            recover_budget(self.root / "shared", self.recovery_evidence(ids[0]))
        recover_budget(self.root / "shared", self.recovery_evidence(ids[1]))
        ledger = self.ledger()
        self.assertEqual(len(ledger["recoveries"]), 2)
        self.assertEqual(ledger["total_reserved_usd"], "0.012298")
        self.assertEqual(ledger["total_reported_cost_usd"], "0")
        self.assertTrue(all(e["cost"] is None for e in ledger["entries"].values()))

    def test_recovery_rejects_stale_bindings_missing_authorization_and_other_failure_types(self):
        self.unknown_429()
        evidence = self.recovery_evidence()
        before = (self.root / "shared/budget.json").read_bytes()
        for change in ({"prior_ledger_sha256": "0" * 64}, {"failed_call_sha256": "0" * 64},
                       {"authorization_ref": ""}, {"reason": ""}, {"accept_unknown_cost": False},
                       {"extra": "not accepted"}):
            with self.subTest(change=change), self.assertRaises((RuntimeError, ValueError)):
                recover_budget(self.root / "shared", {**evidence, **change})
            self.assertEqual((self.root / "shared/budget.json").read_bytes(), before)
        ledger = self.ledger()
        entry = next(iter(ledger["entries"].values()))
        entry["error"] = ledger["halt_reason"] = "synthetic timeout with unknown cost"
        (self.root / "shared/budget.json").write_text(json.dumps(ledger))
        with self.assertRaisesRegex(RuntimeError, "restricted"):
            recover_budget(self.root / "shared", self.recovery_evidence())

    def test_recovery_rejects_inflight_overcost_or_malformed_accounting_without_mutation(self):
        self.unknown_429()
        original = self.ledger()
        cases = []
        for change in ({"status": "attempt_started"}, {"cost": "0.1"}, {"reserved_cost_usd": "NaN"}, {"schema": "wrong"}):
            ledger = copy.deepcopy(original)
            next(iter(ledger["entries"].values())).update(change)
            if change.get("cost"):
                ledger["total_reported_cost_usd"] = change["cost"]
            cases.append(ledger)
        for field, value in (("total_reserved_usd", "0"), ("total_reported_cost_usd", "0.1"), ("recoveries", [None])):
            cases.append({**copy.deepcopy(original), field: value})
        for index, ledger in enumerate(cases):
            path = self.root / "shared/budget.json"
            path.write_text(json.dumps(ledger))
            evidence = self.recovery_evidence(next(iter(original["entries"])))
            before = path.read_bytes()
            with self.subTest(index=index), self.assertRaises((RuntimeError, ValueError)):
                recover_budget(self.root / "shared", evidence)
            self.assertEqual(path.read_bytes(), before)

    def test_explicit_caps_and_model_required_and_cli_flags(self):
        for model, cost, calls, tokens, directory in [
            (None, ".25", 40, 100, self.root), (MODEL, None, 40, 100, self.root),
            (MODEL, "NaN", 40, 100, self.root), (MODEL, "5.000001", 40, 100, self.root),
            (MODEL, 0, 40, 100, self.root), (MODEL, ".25", 0, 100, self.root),
            (MODEL, ".25", True, 100, self.root), (MODEL, ".25", 40, 0, self.root),
            (MODEL, ".25", 40, 100, None), ("openrouter/auto", ".25", 40, 100, self.root)]:
            with self.subTest(model=model, cost=cost, calls=calls), self.assertRaises(ValueError):
                budget_options(model, cost, calls, tokens, directory)
        args = parser().parse_args(["run", "lab", "--run-id", "R", "--provider", "openrouter_budgeted",
            "--model", MODEL, "--max-cost-usd", "0.25", "--max-calls", "40", "--max-output-tokens", "1024", "--budget-dir", str(self.root)])
        self.assertEqual(args.max_calls, 40)
        self.assertEqual(args.max_cost_usd, "0.25")
        for cost in ("0.25", "0.251", "5", "5.00"):
            with self.subTest(accepted_cost=cost):
                self.assertEqual(budget_options(MODEL, cost, 40, 100, self.root)["max_cost_usd"], cost)

    def test_atomic_reservation_before_post_and_alias_receipts(self):
        observed = []
        def post(url, headers, payload, timeout):
            ledger = self.ledger()
            self.assertEqual(len(ledger["entries"]), 1)
            self.assertEqual(next(iter(ledger["entries"].values()))["status"], "attempt_started")
            self.assertEqual(url, ENDPOINT)
            self.assertEqual(headers["Authorization"], "Bearer " + SECRET)
            self.assertFalse(payload["provider"]["allow_fallbacks"])
            self.assertTrue(payload["provider"]["require_parameters"])
            self.assertEqual(payload["provider"]["max_price"], {"prompt": 1.0, "completion": 2.0, "request": 0.0, "image": 0})
            self.assertEqual(payload["max_tokens"], 1024)
            self.assertNotIn("plugins", payload)
            self.assertNotIn("models", payload)
            observed.append(payload)
            return reply()
        provider = self.provider(caller=post)
        self.assertEqual(self.ask(provider, prompt="€"), "valid synthetic output")
        entry = next(iter(self.ledger()["entries"].values()))
        self.assertEqual(entry["input_token_bound"], 4099)
        self.assertEqual(entry["reserved_cost_usd"], "0.006147")
        self.assertEqual(entry["cost"], "0.0001")
        self.assertEqual(entry["provider_receipt"]["requested_model"], MODEL)
        self.assertEqual(entry["provider_receipt"]["model"], "synthetic/actual-alias")
        self.assertFalse(self.ledger()["halted"])

    def test_cache_no_key_no_network_and_no_second_node_attempt(self):
        post = Mock(return_value=reply())
        provider = self.provider(caller=post)
        self.ask(provider)
        os.environ.pop("OPENROUTER_API_KEY")
        reloaded = self.provider(caller=Mock(side_effect=AssertionError("must not send")))
        self.assertEqual(self.ask(reloaded), "valid synthetic output")
        self.assertFalse(reloaded.catalogue_seen)
        with self.assertRaisesRegex(RuntimeError, "single attempt"):
            self.ask(reloaded, prompt="repair this output")
        self.assertEqual(post.call_count, 1)
        self.assertEqual(len(self.ledger()["entries"]), 1)

    def test_native_execution_kind_is_explicit_for_new_cached_and_failed_receipts(self):
        provider = self.provider()
        self.ask(provider)
        os.environ.pop("OPENROUTER_API_KEY")
        self.ask(provider)
        receipts = [json.loads(p.read_text()) for p in (provider.run_dir / "handoff/receipts").glob("*.json")]
        self.assertEqual({r["status"] for r in receipts},
                         {"attempt_started", "response_supplied", "loaded_previous_response"})
        self.assertTrue(all(r.get("execution_kind") == "openrouter_budgeted" for r in receipts))
        self.assertEqual(next(iter(self.ledger()["entries"].values()))["execution_kind"], "openrouter_budgeted")
        os.environ["OPENROUTER_API_KEY"] = SECRET
        failed = self.provider("failed", caller=Mock(side_effect=RuntimeError("synthetic failure")))
        with self.assertRaises(RuntimeError):
            self.ask(failed)
        receipts = [json.loads(p.read_text()) for p in (failed.run_dir / "handoff/receipts").glob("*.json")]
        self.assertEqual({r["status"] for r in receipts}, {"attempt_started", "failed"})
        self.assertTrue(all(r.get("execution_kind") == "openrouter_budgeted" for r in receipts))

    def test_shared_run_budget_max_calls_and_immutable_limits(self):
        first, second = self.provider("A", max_calls=1), self.provider("B", max_calls=1)
        self.ask(first)
        with self.assertRaisesRegex(RuntimeError, "max_calls"):
            self.ask(second)
        second.caller.assert_not_called()
        changed = self.provider("C", max_calls=2)
        with self.assertRaisesRegex(RuntimeError, "immutable"):
            self.ask(changed)
        changed.caller.assert_not_called()

    def test_reservation_limit_rejects_before_transport(self):
        provider = self.provider(max_cost_usd="0.006", caller=Mock())
        with self.assertRaisesRegex(RuntimeError, "reservation"):
            self.ask(provider)
        provider.caller.assert_not_called()
        self.assertFalse((self.root / "shared" / "budget.json").exists())

    def test_bad_catalogue_price_context_and_modality_do_not_charge(self):
        rows = []
        for pricing in [None, {}, {"prompt": "1"}, {"prompt": "NaN", "completion": "0"},
                        {"prompt": True, "completion": "0"}, {"prompt": "-1", "completion": "0"},
                        {"prompt": "0", "completion": "Infinity"}, {"prompt": "0", "completion": "0", "image": ".01"}]:
            rows.append({**ROW, "pricing": pricing})
        rows += [{**ROW, "context_length": 100}, {**ROW, "supported_parameters": []},
                 {**ROW, "architecture": {"input_modalities": ["text"], "output_modalities": ["audio"]}}]
        for row in rows:
            with self.subTest(row=row):
                provider = self.provider(row=row, caller=Mock())
                with self.assertRaises((ValueError, RuntimeError)):
                    self.ask(provider)
                provider.caller.assert_not_called()
        with self.assertRaisesRegex(RuntimeError, "exactly once"):
            verified_model(MODEL, http_get=lambda *args: {"data": [ROW, ROW]})

    def test_discounted_or_equal_cache_read_still_reserves_every_input_at_full_price(self):
        for index, read_price in enumerate(("0", "0.00000025", ROW["pricing"]["prompt"])):
            row = {**ROW, "pricing": {**ROW["pricing"], "input_cache_read": read_price}}
            def post(url, headers, payload, timeout):
                entry = list(self.ledger()["entries"].values())[-1]
                self.assertEqual(entry["reserved_cost_usd"], "0.006149")
                self.assertEqual(Decimal(entry["catalogue_pricing"]["input_cache_read"]), Decimal(read_price))
                self.assertEqual(payload["provider"]["max_price"]["prompt"], 1.0)
                self.assertNotIn("cache_control", payload)
                result = reply()
                result["usage"]["prompt_tokens_details"] = {"cached_tokens": 10}
                return result
            provider = self.provider(run=f"cache-{index}", row=row, caller=post)
            with self.subTest(read_price=read_price):
                self.assertEqual(self.ask(provider), "valid synthetic output")
        self.assertEqual(self.ledger()["total_reserved_usd"], "0.018447")
        self.assertEqual(len(self.ledger()["entries"]), 3)

    def test_unsupported_or_invalid_cache_pricing_rejects_before_inference(self):
        for key, value in [("input_cache_read", "0.00000101"), ("input_cache_read", "NaN"),
                           ("input_cache_read", "Infinity"), ("input_cache_read", "-0.1"),
                           ("input_cache_read", None), ("input_cache_read", True),
                           ("input_cache_write", "0.0000001"), ("input_cache_write_1h", "0.0000001"),
                           ("unknown_cache_fee", "0.0000001"), ("image", "0.0000001")]:
            row = {**ROW, "pricing": {**ROW["pricing"], key: value}}
            provider = self.provider(row=row, caller=Mock())
            with self.subTest(key=key, value=value), self.assertRaises((ValueError, RuntimeError)):
                self.ask(provider)
            provider.caller.assert_not_called()
        self.assertFalse((self.root / "shared/budget.json").exists())

    def test_unknown_cost_halts_entire_batch_without_retry(self):
        data = reply()
        data["usage"].pop("cost")
        provider = self.provider(caller=Mock(return_value=data))
        with self.assertRaisesRegex(RuntimeError, "actual cost"):
            self.ask(provider)
        for node in ("case1", "case2"):
            with self.assertRaises(RuntimeError):
                self.ask(provider, node=node)
        self.assertEqual(provider.caller.call_count, 1)
        self.assertTrue(self.ledger()["halted"])
        self.assertIsNone(next(iter(self.ledger()["entries"].values()))["cost"])
        self.assertEqual(len(self.ledger()["entries"]), 1)

    def test_over_cost_nonfinite_cost_and_over_tokens_are_audited_and_halt(self):
        for index, data in enumerate([reply(cost=".1"), reply(cost=float("nan")), reply(cost=-1), reply()]):
            with self.subTest(index=index):
                if index == 3:
                    data["usage"]["completion_tokens"] = 1025
                provider = self.provider(run=str(index), caller=Mock(return_value=data))
                provider.budget_dir = self.root / f"batch-{index}"
                provider.options["budget_dir"] = str(provider.budget_dir)
                with self.assertRaises((ValueError, RuntimeError)):
                    self.ask(provider)
                ledger = json.loads((provider.budget_dir / "budget.json").read_text())
                self.assertTrue(ledger["halted"])
                entry = next(iter(ledger["entries"].values()))
                self.assertEqual(entry["status"], "failed")
                self.assertIn("provider_response", entry)

    def test_transport_secret_failure_no_resend_or_secret_storage(self):
        post = Mock(side_effect=RuntimeError("Bearer " + SECRET + " upstream failure"))
        provider = self.provider(caller=post)
        try:
            self.ask(provider)
        except RuntimeError:
            trace = traceback.format_exc()
        self.assertNotIn(SECRET, trace)
        with self.assertRaises(RuntimeError):
            self.ask(provider)
        self.assertEqual(post.call_count, 1)
        for path in self.root.rglob("*.json"):
            self.assertNotIn(SECRET, path.read_text())
        self.assertTrue(self.ledger()["halted"])

    def test_successful_response_secrets_redacted(self):
        data = reply()
        data["choices"][0]["message"]["content"] = "result " + SECRET
        data["usage"]["api_key"] = SECRET
        provider = self.provider(caller=Mock(return_value=data))
        self.assertNotIn(SECRET, self.ask(provider))
        for path in self.root.rglob("*.json"):
            self.assertNotIn(SECRET, path.read_text())

    def test_concurrent_instances_reserve_atomically_under_shared_cap(self):
        count = []
        lock = threading.Lock()
        def post(*args):
            with lock:
                count.append(1)
            time.sleep(.02)
            return reply()
        def execute(index):
            provider = self.provider(str(index), caller=post, max_cost_usd="0.020", max_calls=40)
            try:
                self.ask(provider)
                return True
            except RuntimeError:
                return False
        with ThreadPoolExecutor(max_workers=10) as pool:
            results = list(pool.map(execute, range(20)))
        self.assertEqual(sum(results), 3)
        self.assertEqual(len(count), 3)
        self.assertEqual(len(self.ledger()["entries"]), 3)
        self.assertEqual(self.ledger()["total_reserved_usd"], "0.018447")
        self.assertFalse(self.ledger()["halted"])

    def test_five_dollar_ceiling_is_shared_across_concurrent_models_and_runs(self):
        # A known $1 request fee makes the exact shared ceiling observable;
        # cheaper actual billing must never release successful reservations.
        rows = [{**ROW, "id": model, "pricing": {"prompt": "0", "completion": "0", "request": "1"}}
                for model in (MODEL, "synthetic/second-text")]
        barrier = threading.Barrier(8)
        posted = []
        lock = threading.Lock()
        def post(url, headers, payload, timeout):
            with lock:
                posted.append(payload["model"])
            time.sleep(.02)
            return reply(cost="0.1")
        def execute(index):
            row = rows[index % 2]
            provider = OpenRouterBudgetedProvider(self.root / str(index), row["id"], "5", 20, 1024,
                self.root / "shared", caller=post, catalogue_get=lambda *args: {"data": [row]})
            if index >= 2:
                barrier.wait(timeout=5)
            try:
                self.ask(provider)
                return True
            except RuntimeError as exc:
                self.assertIn("reservation", str(exc))
                return False
        results = [execute(0), execute(1)]
        with ThreadPoolExecutor(max_workers=8) as pool:
            results += list(pool.map(execute, range(2, 10)))
        ledger = self.ledger()
        self.assertEqual(sum(results), 5)
        self.assertEqual(len(posted), 5)
        self.assertEqual(set(posted), {row["id"] for row in rows})
        self.assertEqual(len(ledger["entries"]), 5)
        self.assertEqual(ledger["total_reserved_usd"], "5")
        self.assertEqual(ledger["total_reported_cost_usd"], "0.5")
        self.assertFalse(ledger["halted"])

    def test_new_ceiling_cannot_raise_existing_batch_or_run_caps(self):
        first = self.provider()
        self.ask(first)
        batch = self.root / "shared/budget.json"
        binding = first.run_dir / "handoff/budgeted_binding.json"
        original_batch, original_binding = batch.read_bytes(), binding.read_bytes()
        for run in (first.run_dir.name, "another_run"):
            changed = self.provider(run, max_cost_usd="5", caller=Mock())
            with self.subTest(run=run), self.assertRaisesRegex(RuntimeError, "immutable"):
                self.ask(changed, node="new_case")
            changed.caller.assert_not_called()
            self.assertFalse(changed.catalogue_seen)
        self.assertEqual(batch.read_bytes(), original_batch)
        self.assertEqual(binding.read_bytes(), original_binding)

    def test_five_dollar_batch_halts_all_new_models_on_unknown_cost(self):
        data = reply()
        data["usage"].pop("cost")
        first = self.provider("first", max_cost_usd="5", caller=Mock(return_value=data))
        with self.assertRaisesRegex(RuntimeError, "actual cost"):
            self.ask(first)
        second = OpenRouterBudgetedProvider(self.root / "second", "synthetic/second-text", "5", 40, 1024,
            self.root / "shared", caller=Mock(), catalogue_get=Mock())
        with self.assertRaisesRegex(RuntimeError, "halted"):
            self.ask(second)
        second.caller.assert_not_called()
        second.catalogue_get.assert_not_called()
        ledger = self.ledger()
        self.assertEqual(len(ledger["entries"]), 1)
        self.assertEqual(ledger["total_reserved_usd"], "0.006149")
        self.assertIsNone(next(iter(ledger["entries"].values()))["cost"])

    def test_interruption_keeps_reservation_and_halts(self):
        provider = self.provider(caller=Mock(side_effect=KeyboardInterrupt()))
        with self.assertRaises(RuntimeError):
            self.ask(provider)
        self.assertTrue(self.ledger()["halted"])
        entry = next(iter(self.ledger()["entries"].values()))
        self.assertEqual(entry["reserved_cost_usd"], "0.006149")
        self.assertIsNone(entry["cost"])
        with self.assertRaises(RuntimeError):
            self.ask(provider, node="different")
        self.assertEqual(provider.caller.call_count, 1)

    def test_official_host_guard_before_key_transport(self):
        provider = self.provider(caller=Mock())
        os.environ["OPENROUTER_BASE_URL"] = "https://evil.invalid"
        with self.assertRaisesRegex(RuntimeError, "official"):
            self.ask(provider)
        self.assertFalse(provider.catalogue_seen)
        provider.caller.assert_not_called()

    def test_fresh_provider_cannot_escape_failed_attempt_using_new_budget(self):
        first = self.provider(caller=Mock(side_effect=RuntimeError("synthetic transport failure")))
        with self.assertRaises(RuntimeError):
            self.ask(first)
        fresh = OpenRouterBudgetedProvider(first.run_dir, MODEL, ".25", 40, 1024,
                    self.root / "escape-ledger", caller=Mock(), catalogue_get=Mock())
        with self.assertRaisesRegex(RuntimeError, "binding is immutable"):
            self.ask(fresh, node="different")
        fresh.caller.assert_not_called()
        fresh.catalogue_get.assert_not_called()

    def test_crashed_reservation_blocks_fresh_provider_and_different_node(self):
        provider = self.provider()
        self.ask(provider)
        path = self.root / "shared" / "budget.json"
        ledger = self.ledger()
        entry = next(iter(ledger["entries"].values()))
        entry.update(status="attempt_started", cost=None, owner_pid=99999999)
        ledger["total_reported_cost_usd"] = "0"
        path.write_text(json.dumps(ledger))
        fresh = self.provider(caller=Mock())
        with patch("zenith.budgeted.os.kill", side_effect=ProcessLookupError):
            with self.assertRaisesRegex(RuntimeError, "halted"):
                self.ask(fresh, node="different_after_crash")
        fresh.caller.assert_not_called()
        self.assertFalse(fresh.catalogue_seen)
        self.assertTrue(self.ledger()["halted"])
        self.assertEqual(len(self.ledger()["entries"]), 1)

    def test_missing_content_still_logs_actual_usage_and_cost_and_halts(self):
        data = reply()
        data["choices"] = []
        provider = self.provider(caller=Mock(return_value=data))
        with self.assertRaisesRegex(RuntimeError, "content"):
            self.ask(provider)
        entry = next(iter(self.ledger()["entries"].values()))
        self.assertEqual(entry["cost"], "0.0001")
        self.assertEqual(entry["provider_response"]["usage"]["total_tokens"], 13)
        self.assertTrue(self.ledger()["halted"])

    def test_upstream_byok_unknown_external_cost_halts(self):
        data = reply(cost="0")
        data["usage"]["is_byok"] = True
        provider = self.provider(caller=Mock(return_value=data))
        with self.assertRaisesRegex(RuntimeError, "upstream BYOK"):
            self.ask(provider)
        self.assertTrue(self.ledger()["halted"])


if __name__ == "__main__":
    unittest.main()
