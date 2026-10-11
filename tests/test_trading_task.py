"""Synthetic accounting and calendar contracts; no financial-performance claims."""
from copy import deepcopy
from datetime import datetime
import json
from pathlib import Path
import tempfile
import unittest

from benchmarks import trading_task as tt


class TradingTaskTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        calendar = tt.calendar_for("2025-03-01", "2025-05-01")
        dates = [d.date().isoformat() for d in calendar.sessions if "2025-03-03" <= d.date().isoformat() <= "2025-04-22"]
        csv = "Date,Open,High,Low,Close,Adj Close,Volume\n" + "".join(
            f"{stamp},100,111,99,110,80,1000\n" for stamp in dates)
        self.symbols = ["AAPL", "MSFT", "GOOG"]
        records = []
        for symbol in self.symbols + [f"T{i:02}" for i in range(85)]:
            path = f"price/raw/{symbol}.csv"
            target = self.directory / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(csv)
            records.append({"symbol": symbol, "path": path, "sha256": tt.digest(csv.encode())})
        self.manifest = {"dataset_commit": tt.protocol()["dataset_commit"], "files": records,
                         "rights_boundary": "synthetic regression fixture only"}
        self.write_manifest()
        self.splits = {"validation": ["2025-04-17", "2025-04-23"]}
        self.data = tt.build_dataset(self.directory, self.splits, self.symbols)

    def write_manifest(self):
        (self.directory / "source-manifest.json").write_text(json.dumps(self.manifest))

    def samples(self):
        return self.data["splits"]["validation"][:3]

    def test_good_friday_next_open_clock_and_prior_close_information(self):
        sample = self.samples()[0]
        self.assertEqual(sample["issue_date"], "2025-04-17")
        self.assertEqual(sample["target_date"], "2025-04-21")
        self.assertEqual(sample["issue_at"], "2025-04-17T20:01:00+00:00")
        self.assertEqual(sample["entry_at"], "2025-04-21T13:30:00+00:00")
        self.assertEqual(sample["exit_at"], "2025-04-21T20:00:00+00:00")
        self.assertEqual(len(sample["history20"]), 20)
        self.assertEqual(sample["history20"][-1]["Date"], "2025-04-17")
        self.assertEqual(sample["preceding_close"], 110)
        self.assertAlmostEqual(sample["actual_return"], .1)

    def test_forward_projection_ignores_truth_and_is_independent_copy(self):
        sample = self.samples()[0]
        public = tt.public_projection(sample)
        changed = deepcopy(sample)
        changed.update(truth_open=10, truth_close=10000, actual_return=999)
        self.assertEqual(public, tt.public_projection(changed))
        self.assertFalse({"truth_open", "truth_close", "actual_return", "entry_mark", "exit_mark"} & set(public))
        self.assertEqual(public["history20"], sample["history20"])
        self.assertEqual(public["preceding_close"], sample["preceding_close"])
        public["history20"][0]["Close"] = 999
        self.assertNotEqual(public["history20"], sample["history20"])
        public["features"][0] = 999
        self.assertNotEqual(public["features"], sample["features"])

    def test_exact_twenty_session_features_and_adjusted_close_exclusion(self):
        sample = self.samples()[0]
        self.assertEqual(sample["feature_names"], tt.FEATURES)
        self.assertEqual(len(sample["features"]), 8)
        self.assertEqual(sample["features"][:3], [0, 0, 0])
        self.assertAlmostEqual(sample["features"][3], .1)
        self.assertEqual(sample["features"][4:6], [0, 1])
        self.assertNotIn("Adj Close", sample["history20"][0])

    def test_equal_allowances_no_renormalization_and_exact_cost_reconciliation(self):
        samples = self.samples()
        predictions = {samples[0]["sample_id"]: .02}
        result = tt.evaluate_predictions(samples, predictions, capital=300)
        day = result["daily"][0]
        self.assertEqual(day["cash_allowances"], 2)
        self.assertEqual(day["forecast_failure_count"], 2)
        self.assertAlmostEqual(day["gross_return"] - day["cost_return"], day["net_return"])
        rows = result["asset_rows"]
        self.assertTrue(all(r["allowance"] == 100 for r in rows))
        self.assertAlmostEqual(sum(r["ending_cash"] for r in rows), day["ending_capital"])
        filled = next(r for r in rows if r["decision"] == "long")
        self.assertAlmostEqual(filled["quantity"] * filled["entry_fill"] + filled["entry_fee"], 100)
        self.assertAlmostEqual(filled["gross_return"] - filled["cost_return"], filled["net_return"])
        self.assertEqual(filled["actual_return"], samples[0]["actual_return"])

    def test_missing_requested_long_fill_is_unknown_not_cash_or_favorable_skip(self):
        samples = self.samples()
        samples[0]["truth_close"] = None
        result = tt.evaluate_predictions(samples, {samples[0]["sample_id"]: .1})
        self.assertEqual(result["daily"][0]["status"], "unknown_fill")
        self.assertIsNone(result["daily"][0]["net_return"])
        self.assertIsNone(result["summary"]["mean_net_return"])
        self.assertEqual(len(result["asset_rows"]), 3)
        pending = next(r for r in result["asset_rows"] if r["decision"] == "long")
        self.assertIsNotNone(pending["entry_fill"])
        self.assertGreater(pending["quantity"], 0)
        self.assertGreater(pending["entry_fee"], 0)
        self.assertIsNone(pending["exit_fill"])
        self.assertIsNone(pending["exit_fee"])
        self.assertIsNone(pending["actual_return"])

    def test_late_rejected_and_missing_information_forecasts_stay_cash(self):
        samples = self.samples()
        samples[2]["info_status"] = "missing_history"
        predictions = {samples[0]["sample_id"]: {"status": "accepted", "expected_return": .1, "issued_at": samples[0]["entry_at"]},
                       samples[1]["sample_id"]: {"status": "rejected", "expected_return": .1}, samples[2]["sample_id"]: .1}
        result = tt.evaluate_predictions(samples, predictions)
        self.assertEqual(result["daily"][0]["net_return"], 0)
        self.assertEqual(result["daily"][0]["forecast_failure_count"], 3)

    def test_target_unavailability_does_not_remove_scheduled_row(self):
        path = self.directory / "price/raw/AAPL.csv"
        text = path.read_text()
        path.write_text("\n".join(line for line in text.splitlines() if not line.startswith("2025-04-21,")) + "\n")
        next(r for r in self.manifest["files"] if r["symbol"] == "AAPL")["sha256"] = tt.digest(path.read_bytes())
        self.write_manifest()
        data = tt.build_dataset(self.directory, self.splits, self.symbols)
        missing = next(s for s in data["splits"]["validation"] if s["symbol"] == "AAPL" and s["issue_date"] == "2025-04-17")
        self.assertEqual(missing["info_status"], "available")
        self.assertIsNone(missing["truth_open"])
        self.assertEqual(data["coverage"]["validation"]["scheduled_allowances"], self.data["coverage"]["validation"]["scheduled_allowances"])

    def test_support_or_source_drift_rejected(self):
        samples = self.samples() + self.data["splits"]["validation"][3:5]
        with self.assertRaisesRegex(ValueError, "support differs"):
            tt.evaluate_predictions(samples, {})
        (self.directory / "price/raw/AAPL.csv").write_text("changed")
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            tt.build_dataset(self.directory, self.splits, self.symbols)


if __name__ == "__main__":
    unittest.main()
