"""Shared paid budgets use synthetic prices, fake credentials and mock HTTP only."""
import copy
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

from zenith.budgeted import OpenRouterBudgetedProvider, ENDPOINT, budget_options, verified_model
from zenith.cli import parser

SECRET = "sk-or-v1-FAKE_BUDGETED_SECRET_NEVER_PERSIST"
MODEL = "synthetic/paid-text"
ROW = {"id": MODEL, "context_length": 131072,
       "architecture": {"input_modalities": ["text"], "output_modalities": ["text"]},
       "pricing": {"prompt": "0.000001", "completion": "0.000002", "request": "0"},
       "supported_parameters": ["max_tokens", "temperature"],
       "top_provider": {"context_length": 131072, "max_completion_tokens": 4096}}


def reply(cost="0.0001", **extra):
    return {"model": "synthetic/actual-alias", "id": "synthetic-generation", "usage": {
        "prompt_tokens": 10, "completion_tokens": 3, "total_tokens": 13, "cost": cost},
        "choices": [{"message": {"content": "valid synthetic output"}}], **extra}


class BudgetedTests(unittest.TestCase):
    def setUp(self):
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
                        {"prompt": "0", "completion": "Infinity"}, {"prompt": "0", "completion": "0", "web_search": ".01"}]:
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
