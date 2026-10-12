"""Forecast-feedback regressions. Every price/model observation is synthetic."""
from datetime import datetime, timedelta, timezone
import hashlib
import importlib.metadata
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from feedback import engine
from feedback.demo import fixture_policy, fixture_run
from zenith.providers import write_json


class FeedbackTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.store = self.directory / "ledger"
        self.policy = fixture_policy(self.directory / "policy.json")
        self.issue = datetime(2026, 1, 5, 20, tzinfo=timezone.utc)
        self.horizon = self.issue + timedelta(days=1)
        self.source = fixture_run(self.directory / "LAB_0", self.issue, self.horizon)

    def register(self, source=None, horizon="24h"):
        return engine.register(self.store, source or self.source, self.policy, horizon)

    def truth(self, rows=None, *, basis="synthetic_point_quote", currency="USD", fetch_time=None):
        path = self.directory / "truth.json"
        write_json(path, {"metadata": {"status": "success", "price_basis": basis,
            "currency": currency, "as_of": fetch_time}, "data": {"rows": rows or [
            {"target_id": "XOM", "timestamp": self.horizon.isoformat(), "price": 99.0}]}})
        return path

    def score(self, truth=None, as_of="2026-03-01T00:00:00+00:00"):
        return engine.score(self.store, truth or self.truth(), as_of)

    def test_source_refs_preserve_external_identity_and_relative_local_paths(self):
        root = self.directory / "repository"
        internal = root / "artifacts/lab_director.json"
        external = [self.directory / name / "lab_director.json" for name in ("first", "second")]
        for index, path in enumerate([internal, *external]):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({"fixture": index}))
        local = engine.source_ref(internal, root=root, pointer="/data/predictions_t/0")
        self.assertEqual(local["path"], "artifacts/lab_director.json")
        self.assertEqual(local["pointer"], "/data/predictions_t/0")
        refs = [engine.source_ref(path, root=root) for path in external]
        self.assertNotEqual(refs[0]["path"], refs[1]["path"])
        for path, ref in zip([internal, *external], [local, *refs]):
            self.assertEqual(ref["sha256"], hashlib.sha256(path.read_bytes()).hexdigest())
        for path, ref in zip(external, refs):
            self.assertEqual(ref["path"], str(path.resolve()))
            self.assertEqual(Path(ref["path"]).read_bytes(), path.read_bytes())
            self.assertEqual(ref, engine.source_ref(path, root=root))

    def test_xshg_numeric_cny_target_uses_actual_close_not_packet_availability(self):
        issue = datetime(2023, 9, 28, 7, 1, tzinfo=timezone.utc)
        horizon = datetime(2023, 10, 9, 7, tzinfo=timezone.utc)
        run = fixture_run(self.directory/'LAB_CNY', issue, horizon)
        for path in (run/'artifacts').glob('*.json'):
            path.write_text(path.read_text().replace('XOM', '600438').replace('USD', 'CNY'))
        policy = engine.read_object(self.policy)
        policy.update(currency='CNY', observation_precision='session_close', calendar_id='XSHG',
                      calendar_version=importlib.metadata.version('exchange_calendars'))
        write_json(self.policy, policy)
        feed_path = run/'artifacts/global_stock_feed.json'
        feed = engine.read_object(feed_path)
        feed['data'] = {'columns': ['Ticker', 'Price', 'date'], 'rows': [['600438', 100., '2023-09-28']]}
        write_json(feed_path, feed)
        engine.register(self.store, run, self.policy, 'next_xshg_close')
        truth = self.truth([{'target_id': '600438', 'date': '2023-10-09', 'price': 99.}], currency='CNY',
                           fetch_time='2023-10-09T07:01:00+00:00')
        result = engine.score(self.store, truth, '2023-10-09T07:01:00+00:00')['evaluations'][0]
        self.assertEqual(result['status'], 'scored')
        self.assertEqual(result['metrics']['target_price_absolute_error'], 2.)
        self.assertEqual(engine.observation_time('2023-10-09', policy), horizon)
        wrong = fixture_run(self.directory/'LAB_WRONG_CLOSE', issue, horizon+timedelta(days=1))
        with self.assertRaisesRegex(ValueError, 'next_xshg_close horizon_id disagrees'):
            engine.register(self.directory/'wrong-ledger', wrong, self.policy, 'next_xshg_close')

    def test_pending_truth_never_becomes_a_model_miss(self):
        self.register()
        result = self.score(as_of=self.issue.isoformat())["evaluations"][0]
        self.assertEqual(result["status"], "pending")
        self.assertIsNone(result["metrics"])
        self.assertEqual(result["error_classes"], [])
        resolved = self.score()["evaluations"][0]
        self.assertEqual(resolved["status"], "scored")
        self.assertEqual(resolved["metrics"]["target_price_absolute_error"], 2.0)
        self.assertAlmostEqual(resolved["metrics"]["target_price_relative_error"], 2 / 99)
        self.assertFalse(resolved["metrics"]["direction_hit"])
        self.assertEqual(resolved["metrics"]["no_change_absolute_error"], 1.0)

    def test_finite_nonpositive_target_outlier_is_not_selected_away(self):
        path = self.source / "artifacts/lab_director.json"
        cp2 = engine.read_object(path)
        cp2["data"]["predictions_t"][0].update(direction="DOWN", target_price=0.0)
        write_json(path, cp2)
        self.register()
        result = self.score()["evaluations"][0]
        self.assertEqual(result["status"], "scored")
        self.assertEqual(result["metrics"]["target_price_absolute_error"], 99.0)
        self.assertEqual(result["metrics"]["target_price_relative_error"], 1.0)
        self.assertIn("target_worse_than_no_change", result["error_classes"])

    def test_exact_horizon_and_row_time_not_fetch_time(self):
        self.register()
        truth = self.truth([{ "target_id": "XOM", "timestamp": (self.horizon + timedelta(hours=1)).isoformat(), "price": 99.0}],
                           fetch_time=self.horizon.isoformat())
        result = self.score(truth)["evaluations"][0]
        self.assertEqual(result["status"], "data_gap")
        self.assertIn("missing_exact_horizon_observation", result["data_gaps"])
        self.assertEqual(result["error_classes"], [])

    def test_missing_bar_timestamp_cannot_borrow_envelope_as_of(self):
        self.register()
        truth = self.truth([{ "target_id": "XOM", "price": 99.0}], fetch_time=self.horizon.isoformat())
        result = self.score(truth)["evaluations"][0]
        self.assertIn("truth_bar_observation_time_unverified", result["data_gaps"])
        self.assertIsNone(result["metrics"])

    def test_price_basis_and_currency_mismatch_are_data_gaps(self):
        self.register()
        result = self.score(self.truth(basis="adjusted_daily_close"))["evaluations"][0]
        self.assertIn("truth_price_basis_or_currency_mismatch", result["data_gaps"])
        self.assertEqual(result["error_classes"], [])
        result = self.score(self.truth(currency="EUR"))["evaluations"][0]
        self.assertEqual(result["status"], "data_gap")

    def test_ambiguous_price_columns_and_boolean_mapping_refused(self):
        self.register()
        truth = self.truth([{ "target_id": "XOM", "timestamp": self.horizon.isoformat(), "close": 99.0, "adj_close": 95.0}])
        result = self.score(truth)["evaluations"][0]
        self.assertEqual(result["status"], "data_gap")
        self.assertIn("invalid_truth_artifact", result["data_gaps"])
        write_json(truth, {"metadata": {"price_basis": "synthetic_point_quote", "currency": "USD"},
                           "data": {"prices": {"XOM": {self.horizon.isoformat(): True}}}})
        result = self.score(truth)["evaluations"][0]
        self.assertEqual(result["status"], "data_gap")

    def test_native_provider_bar_metadata_replaces_no_fetch_timestamp(self):
        policy = engine.read_object(self.policy)
        policy.update(observation_precision="session_close", calendar_id="XNYS",
                      calendar_version=importlib.metadata.version("exchange_calendars"))
        write_json(self.policy, policy)
        feed_path = self.source / "artifacts/global_stock_feed.json"
        feed = engine.read_object(feed_path)
        feed["data"] = {"columns": ["Ticker", "Price"], "rows": [["XOM", 100.0]]}
        feed["metadata"]["diagnostics"] = {"price_observations": {"XOM": {"session_date": "2026-01-05", "interval": "1d", "auto_adjust": False}}}
        write_json(feed_path, feed)
        # Jan 5, 2026 closes at 21 UTC; move issue to the actual session close.
        source = fixture_run(self.directory / "BAR_METADATA", self.issue + timedelta(hours=1), self.horizon + timedelta(hours=1))
        write_json(source / "artifacts/global_stock_feed.json", feed)
        self.register(source)
        truth = self.directory / "truth-run/artifacts/global_stock_feed.json"
        write_json(truth, {"status": "success", "metadata": {"status": "success", "price_basis": "synthetic_point_quote", "currency": "USD",
            "as_of": "2026-01-08T10:00:00+00:00", "diagnostics": {"price_observations": {"XOM": {"session_date": "2026-01-06", "interval": "1d", "auto_adjust": False}}}},
            "data": {"columns": ["Ticker", "Price"], "rows": [["XOM", 99.0]]}})
        result = self.score(truth.parent.parent)["evaluations"][0]
        self.assertEqual(result["status"], "scored")
        self.assertEqual(result["truth"]["observed_time"], "2026-01-06T21:00:00+00:00")

    def test_declared_duration_horizon_cannot_disagree_with_target_time(self):
        with self.assertRaisesRegex(ValueError, "duration horizon_id"):
            self.register(horizon="48h")

    def test_historical_imports_and_prospective_pending_are_separate(self):
        self.register()
        now = datetime.now(timezone.utc)
        issue = now - timedelta(hours=1)
        source = fixture_run(self.directory / "PROSPECTIVE_FIXTURE", issue, issue + timedelta(days=1))
        self.register(source)
        report = engine.summary(self.store, now.isoformat(), window_days=365)
        self.assertEqual({g["evaluation_posture"] for g in report["groups"]}, {"historical_import", "prospective_pending"})

    def test_duplicate_truth_is_not_last_row_wins(self):
        self.register()
        rows = [{"target_id": "XOM", "timestamp": self.horizon.isoformat(), "price": price} for price in (99, 150)]
        result = self.score(self.truth(rows))["evaluations"][0]
        self.assertIn("duplicate_truth_observation", result["data_gaps"])
        self.assertIsNone(result["metrics"])

    def test_registration_idempotent_and_changed_forecast_refused(self):
        first = self.register()
        self.assertEqual(first, self.register())
        with sqlite3.connect(self.store / "feedback.sqlite3") as db:
            self.assertEqual(db.execute("SELECT count(*) FROM forecasts").fetchone()[0], 1)
        with self.assertRaisesRegex(ValueError, "provenance changed"):
            self.register(horizon="another-label-for-the-same-horizon")
        path = self.source / "artifacts/lab_director.json"
        cp2 = engine.read_object(path)
        cp2["data"]["predictions_t"][0]["target_price"] = 102
        write_json(path, cp2)
        with self.assertRaisesRegex(ValueError, "provenance changed"):
            self.register()

    def test_resolved_truth_cannot_be_replaced_by_later_revisions(self):
        self.register()
        truth = self.truth()
        first = self.score(truth)
        second = self.score(truth)
        self.assertEqual(first, second)
        self.truth([{ "target_id": "XOM", "timestamp": self.horizon.isoformat(), "price": 500}])
        revised = self.score(truth)["evaluations"][0]
        self.assertEqual(revised, first["evaluations"][0])
        with sqlite3.connect(self.store / "feedback.sqlite3") as db:
            self.assertEqual(db.execute("SELECT count(*) FROM evaluations").fetchone()[0], 1)
        earlier = self.score(truth, as_of=self.issue.isoformat())["evaluations"][0]
        self.assertEqual(earlier["status"], "pending")
        self.assertIsNone(earlier["metrics"])

    def test_schema_snapshot_and_forward_only_guards(self):
        path = self.source / "artifacts/lab_director.json"
        cp2 = engine.read_object(path)
        cp2["data"]["predictions_t"][0]["snapshot_price"] = 98
        write_json(path, cp2)
        with self.assertRaisesRegex(ValueError, "equity baseline"):
            self.register()
        cp2["data"]["predictions_t"][0]["snapshot_price"] = 100
        cp2["data"]["oracle_meta"] = {}
        write_json(path, cp2)
        with self.assertRaisesRegex(ValueError, "forward Lab"):
            self.register()
        del cp2["data"]["oracle_meta"]
        cp2["data"]["predictions_t"][0]["target_time_iso"] = "2026-01-06T20:00:00"
        write_json(path, cp2)
        with self.assertRaisesRegex(ValueError, "explicit timezone"):
            self.register()

    def test_frozen_ancestry_hash_mismatch_refused(self):
        path = self.source / "zenith_run.json"
        manifest = engine.read_object(path)
        manifest["node_hashes"]["lab_director"] = "f" * 64
        write_json(path, manifest)
        with self.assertRaisesRegex(ValueError, "ancestor graph"):
            self.register()

    def test_separate_horizons_and_rolling_issue_window(self):
        self.register()
        horizon2 = self.issue + timedelta(days=2)
        source2 = fixture_run(self.directory / "LAB_48H", self.issue, horizon2)
        self.register(source2, "48h")
        rows = [{"target_id": "XOM", "timestamp": h.isoformat(), "price": 101.0} for h in (self.horizon, horizon2)]
        self.score(self.truth(rows))
        report = engine.summary(self.store, "2026-03-01T00:00:00+00:00", window_days=90)
        self.assertEqual({g["horizon_id"] for g in report["groups"]}, {"24h", "48h"})
        self.assertTrue(all(g["distinct_issue_times"] == 1 for g in report["groups"]))
        self.assertEqual(engine.summary(self.store, "2026-03-01T00:00:00+00:00", window_days=7)["groups"], [])
        self.assertEqual(engine.propose(self.store, "2026-03-01T00:00:00+00:00")["proposals"], [])

    def batch(self, *, count=20, failing=(0, 7, 14), same_issue=False):
        rows = []
        for index in range(count):
            issue = self.issue if same_issue else self.issue + timedelta(days=2 * index)
            horizon = issue + timedelta(days=1)
            source = fixture_run(self.directory / f"BATCH_{index}", issue, horizon)
            self.register(source)
            row = {"target_id": "XOM", "timestamp": horizon.isoformat(), "price": 99.0 if index in failing else 101.0}
            if not same_issue:
                rows.append(row)
        if same_issue:
            rows = [{"target_id": "XOM", "timestamp": self.horizon.isoformat(), "price": 99.0}]
        self.score(self.truth(rows))

    def test_large_batch_feedback_keeps_successes_and_exact_lineage(self):
        self.batch()
        result = engine.propose(self.store, "2026-03-01T00:00:00+00:00")
        proposals = result["proposals"]
        self.assertEqual({p["candidate_error_class"] for p in proposals}, {"direction_miss", "target_worse_than_no_change"})
        for proposal in proposals:
            self.assertEqual(proposal["total_resolved"], 20)
            self.assertEqual(proposal["total_failures"], 3)
            self.assertEqual(proposal["support_fraction"], 3 / 20)
            self.assertEqual(proposal["distinct_resolved_issue_times"], 20)
            self.assertFalse(proposal["live_mutation_permission"])
            self.assertEqual(len(proposal["evidence"]), 20)
            self.assertEqual(sum(e["supports_candidate_class"] for e in proposal["evidence"]), 3)
            self.assertTrue(all(e["forecast_ref"]["sha256"] and e["truth_ref"]["sha256"] and e["truth_row_sha256"] for e in proposal["evidence"]))
            self.assertIn("lab_director", {p["node_id"] for p in proposal["participating_ancestors"]})
        self.assertEqual(proposals, engine.propose(self.store, "2026-03-01T00:00:00+00:00")["proposals"])

    def test_single_miss_or_small_batch_never_generates_feedback(self):
        self.batch(failing=(0,))
        self.assertEqual(engine.propose(self.store, "2026-03-01T00:00:00+00:00")["proposals"], [])
        with self.assertRaisesRegex(ValueError, "at least 20"):
            engine.propose(self.store, "2026-03-01T00:00:00+00:00", minimum_issue_times=1)

    def test_repeated_same_issue_runs_do_not_inflate_batch(self):
        self.batch(same_issue=True)
        result = engine.propose(self.store, "2026-03-01T00:00:00+00:00")
        self.assertEqual(result["proposals"], [])
        self.assertEqual(result["eligibility"][0]["resolved"], 20)
        self.assertEqual(result["eligibility"][0]["distinct_issue_times"], 1)

    def test_session_close_uses_actual_bar_date_and_native_early_close(self):
        policy = engine.read_object(self.policy)
        policy.update(observation_precision="session_close", calendar_id="XNYS",
                      calendar_version=importlib.metadata.version("exchange_calendars"))
        write_json(self.policy, policy)
        issue = datetime(2025, 11, 26, 21, tzinfo=timezone.utc)
        horizon = datetime(2025, 11, 28, 18, tzinfo=timezone.utc)
        source = fixture_run(self.directory / "EARLY_CLOSE", issue, horizon)
        path = source / "artifacts/global_stock_feed.json"
        feed = engine.read_object(path)
        feed["data"]["columns"] = ["Ticker", "Price", "date"]
        feed["data"]["rows"] = [["XOM", 100.0, "2025-11-26"]]
        write_json(path, feed)
        self.register(source, "next_us_close")
        truth = self.truth([{ "target_id": "XOM", "date": "2025-11-28", "price": 99.0}],
                           fetch_time="2025-12-01T10:00:00+00:00")
        result = self.score(truth)["evaluations"][0]
        self.assertEqual(result["status"], "scored")
        self.assertEqual(result["truth"]["observed_time"], "2025-11-28T18:00:00+00:00")


if __name__ == "__main__":
    unittest.main()
