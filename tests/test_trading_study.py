"""Actual study flow with a fake provider; no external inference."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from benchmarks.trading_task import FEATURES
from research import trading_study as s, trading_protocol as c


def sample(stamp, symbol, n=1):
    target = stamp[:-2] + f"{int(stamp[-2:]) + 1:02}"
    bar = {"Date": stamp, "Open": 100, "High": 102, "Low": 99, "Close": 101, "Volume": 1000}
    return {"sample_id": stamp + symbol, "symbol": symbol, "issue_date": stamp, "target_date": target,
        "issue_at": stamp + "T20:01:00+00:00", "entry_at": target + "T14:30:00+00:00", "exit_at": target + "T21:00:00+00:00",
        "features": [n / 10000] * 8, "feature_names": FEATURES[:], "info_status": "available",
        "source_ref": "synthetic.csv", "source_sha256": "a" * 64, "availability_basis": "synthetic",
        "price_basis": "synthetic", "forecast_units": "return", "task": "synthetic",
        "history_lookback": "synthetic", "history20": [bar.copy() for _ in range(20)],
        "preceding_close": 100, "anchor_return": .001, "truth_open": 100, "truth_close": 101, "actual_return": .01}


def dataset():
    symbols = ["AAPL", "GOOG", "MSFT"]
    ranges = {"fit": [f"2013-01-{i:02}" for i in range(2, 12)], "training": ["2015-01-02", "2015-01-05"],
              "validation": ["2016-01-04", "2016-01-07"], "test": ["2017-01-03", "2017-01-06"]}
    return {"feature_names": FEATURES[:], "symbols": symbols, "coverage": {}, "source_manifest_sha256": "b" * 64,
        "splits": {phase: [sample(d, symbol, i + 1) for i, d in enumerate(dates) for symbol in symbols]
                   for phase, dates in ranges.items()}}


def fake_ask(study, key, prompt, spec):
    evidence = json.loads(prompt.split("\nEVIDENCE_JSON\n", 1)[1])
    if key.startswith("interpret_"):
        return json.dumps({"schema": "zenith_trading_interpretation_v1", "packet_sha256": evidence["packet_sha256"],
            "interpretations": [{"asset_id": a["asset_id"], "summary": "Limited numerical evidence.", "evidence_refs": a["evidence_refs"][:1]} for a in evidence["assets"]]})
    if key.startswith("proposal_"):
        return json.dumps({"schema": "zenith_trading_skill_v1", "skill": "Retain a cautious mean estimate.",
                           "rationale": "Synthetic proposal.", "evidence_refs": []})
    return json.dumps({"schema": "zenith_trading_forecast_v1", "packet_sha256": evidence["packet_sha256"],
        "interpretation_sha256": evidence["interpretation_sha256"],
        "forecasts": [{"asset_id": a["asset_id"], "mean_expected_return": .002, "evidence_refs": a["evidence_refs"][:1],
                       "reasoning": "Synthetic forecast.", "abstain": False} for a in evidence["assets"]]})


class TradingStudyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.study = Path(self.temp.name) / "study"
        with patch.object(s, "build_dataset", return_value=dataset()), patch.object(s, "COUNTS", dict.fromkeys(s.COUNTS, 2)):
            s.freeze(Path("unused"), self.study, budget={}, authorization={"synthetic": True})

    def test_complete_two_round_flow_selects_unchanged_on_ties_and_seals(self):
        with patch.object(s, "ask", side_effect=fake_ask) as mocked:
            self.assertEqual(s.learn(self.study)["attempts"], 6)
            selected = s.select(self.study)
            self.assertTrue(all(r["candidate_id"] == "baseline" for r in selected["selected"].values()))
            result = s.final(self.study)
            self.assertEqual(result["date_count"], 2)
            self.assertEqual(result["unchanged_aliases"], dict.fromkeys(s.ARMS, "baseline"))
            for arm in s.ARMS:
                self.assertEqual(result["paired_updates"][arm]["interval"], [0, 0])
                self.assertFalse((self.study / "forecasts" / arm).exists())
            count = mocked.call_count
            self.assertEqual(s.final(self.study), result)
            self.assertEqual(mocked.call_count, count)
        with self.assertRaisesRegex(ValueError, "closed"):
            s.learn(self.study)

    def test_truth_mutation_cannot_change_prediction_packet(self):
        d = dataset(); rows = d["splits"]["training"][:3]
        fit = s.fit_anchor(d["splits"]["fit"], FEATURES)
        before = s.packet_from_rows(rows, fit, d["symbols"], FEATURES)
        for row in rows:
            row.update(actual_return=-.999, truth_open=10000, truth_close=1)
        self.assertEqual(before, s.packet_from_rows(rows, fit, d["symbols"], FEATURES))
        self.assertEqual(len(c.validate_packet(before)), 3)

    def test_rich_projection_never_admits_review_and_price_control_retains_numbers(self):
        d = dataset(); rows = d["splits"]["training"][:3]
        fit = s.fit_anchor(d["splits"]["fit"], FEATURES)
        for row in rows:
            row["context_evidence"] = [{"ref_id": "news_1", "kind": "news",
                "available_at": "2015-01-02T14:30:00+00:00", "content": "Contemporaneous report.",
                "source_sha256": "f" * 64, "availability_basis": "date_only_approximate"}]
            row["review_evidence"] = [{"content": "Future outcome explanation"}]
        rich = s.packet_from_rows(rows, fit, d["symbols"], FEATURES)
        self.assertEqual(len(c.validate_packet(rich)), 3)
        self.assertNotIn("Future outcome", json.dumps(rich))
        reduced = s.price_packet(rich)
        self.assertEqual(len(c.validate_packet(reduced)), 3)
        for a, b in zip(rich["assets"], reduced["assets"]):
            for key in ("history20", "features", "anchor_mean_return"):
                self.assertEqual(a[key], b[key])
            self.assertNotIn("context_evidence", b)

    def test_frozen_source_and_input_drift_are_rejected(self):
        with patch.object(s, "source_hashes", return_value={"changed": "yes"}):
            with self.assertRaisesRegex(ValueError, "source changed"):
                s.load(self.study)
        p = self.study / "inputs.json"
        value = s.read_json(p); value["test"][0]["actual_return"] = 99
        s.write_json(p, value)
        with self.assertRaisesRegex(ValueError, "data changed"):
            s.load(self.study)

    def test_test_inference_cannot_precede_selection(self):
        with self.assertRaisesRegex(ValueError, "selection"):
            s.run_forecasts(self.study, "test", {"baseline": s.BASE_SKILL})

    def test_rejected_proposal_remains_in_denominator_and_second_round_runs(self):
        def reject_one(study, key, prompt, spec):
            return "bad" if key == "proposal_trace_feedback_r1" else fake_ask(study, key, prompt, spec)
        with patch.object(s, "ask", side_effect=reject_one):
            self.assertEqual(s.learn(self.study)["attempts"], 6)
            self.assertEqual(s.read_json(self.study / "candidates/trace_feedback_r1.json")["status"], "rejected")
            s.select(self.study)

    def test_missing_forecasts_keep_complete_cash_denominator_and_no_partial_mse(self):
        rows = dataset()["splits"]["test"]
        result = s.evaluate(rows, {}, ["AAPL", "GOOG", "MSFT"])
        self.assertEqual(len(result["asset_rows"]), 6)
        self.assertEqual(s.mean_net(result), 0)
        self.assertIsNone(result["summary"]["mean_squared_return_error"])
        self.assertEqual(result["summary"]["numeric_forecasts"], 0)

    def test_paired_dates_and_complete_support_required(self):
        a = [{"issue_date": "a", "net_return": .1}]
        with self.assertRaisesRegex(ValueError, "dates differ"):
            s.paired_interval(a, [{"issue_date": "b", "net_return": .1}])
        with self.assertRaisesRegex(ValueError, "incomplete"):
            s.mean_net({"daily": [{"net_return": None}]})
        self.assertEqual(s.paired_interval(a, a)["interval"], [0, 0])

    def test_date_choice_is_independent_of_outcomes(self):
        rows = dataset()["splits"]["training"]
        selected = s.choose_dates(rows, 2)
        for row in rows:
            row["actual_return"] = 999
        self.assertEqual(selected, s.choose_dates(rows, 2))


if __name__ == "__main__":
    unittest.main()
