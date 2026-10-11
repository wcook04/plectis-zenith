"""Price-only protocol regressions use synthetic rows, not paper-score fixtures."""
from copy import deepcopy
import csv
from datetime import date, timedelta
import io
import json
from pathlib import Path
import tempfile
import unittest

from benchmarks.stocknet import FIELDS, build_samples, canonical_digest, digest, features, fit_ridge, parse_prices, protocol, run_benchmark, summarize, verify_split_sources


def rows(count=800):
    first = date(2013, 11, 1)
    result = []
    for index in range(count):
        close = 100 + index * 0.05 + (index % 7) * 0.1
        result.append({"Date": (first + timedelta(days=index)).isoformat(), "Open": close - 0.2,
                       "High": close + 0.5, "Low": close - 0.5, "Close": close,
                       "Adj Close": close * 0.9, "Volume": 1000 + index % 31})
    return result


def csv_bytes(data):
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=FIELDS)
    writer.writeheader()
    writer.writerows(data)
    return stream.getvalue().encode()


class StockNetProtocolTests(unittest.TestCase):
    def test_features_use_only_issued_prefix_and_exclude_adjusted_close(self):
        data = rows()
        baseline = features(data, 100)
        changed = deepcopy(data)
        for row in changed[101:]:
            row["Close"] *= 100
            row["Volume"] *= 100
        for row in changed:
            row["Adj Close"] *= 100
        self.assertEqual(features(changed, 100), baseline)

    def test_label_maturity_and_embargo_for_all_horizons(self):
        data, spec = rows(), protocol()
        for horizon in [1, 5, 20]:
            samples, exclusions = build_samples(data, horizon, spec)
            for split, values in samples.items():
                start, end = spec["splits"][split]
                self.assertTrue(values)
                for sample in values:
                    self.assertLess(sample["target_date"], end)
                    self.assertLess(sample["issue_date"], sample["target_date"])
                if split != "train":
                    self.assertEqual(exclusions[split]["embargoed_issue_rows"], horizon)
                self.assertGreater(exclusions[split]["purged_unmatured_labels"], 0)

    def test_issue_days_have_equal_weight(self):
        samples = [{"issue_date": stamp, "issue_price": 100, "target_price": 100, "actual_return": 0}
                   for stamp in ["2015-01-01", "2015-01-01", "2015-01-02"]]
        summary = summarize(samples, [1, 1, 3])
        self.assertEqual(summary["metrics"]["normalized_return_mae"], 2)
        self.assertEqual(summary["issue_day_count"], 2)

    def test_pinned_split_source_verification(self):
        spec = protocol()
        config = "\n".join(f"  {split}_{endpoint}_date: '{value}'" for split, values in spec["splits"].items() for endpoint, value in zip(["start", "end"], values)).encode()
        pipeline = b"start_date <= main_target_date_str < end_date"
        verify_split_sources(config, pipeline, spec)
        with self.assertRaises(ValueError):
            verify_split_sources(config.replace(b"2015-08-01", b"2015-08-02"), pipeline, spec)

    def test_nonfinite_raw_rows_reported(self):
        data = rows(3)
        data[1]["Volume"] = float("nan")
        parsed, rejected = parse_prices(csv_bytes(data))
        self.assertEqual(len(parsed), 2)
        self.assertIn("nonfinite", rejected[0]["reason"])

    def test_ridge_fit_uses_only_matured_train(self):
        data = rows()
        samples, _ = build_samples(data, 20, protocol())
        fit = fit_ridge(samples["train"])
        self.assertLess(fit["fit_label_maturity_end"], protocol()["splits"]["train"][1])
        self.assertEqual(fit["lambda"], 1)
        changed = deepcopy(samples)
        for split in ["dev", "test"]:
            for sample in changed[split]:
                sample["actual_return"] = 1e9
                sample["features"] = [1e9] * 8
        self.assertEqual(fit_ridge(changed["train"]), fit)

    def test_real_runner_freezes_separate_predictors_truth_and_hashes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            dataset = root / "dataset"
            (dataset / "price/raw").mkdir(parents=True)
            content = csv_bytes(rows())
            path = dataset / "price/raw/TEST.csv"
            path.write_bytes(content)
            spec = protocol()
            manifest = {"dataset_commit": spec["dataset_commit"], "protocol_sha256": canonical_digest(spec), "stock_count": 1,
                        "files": [{"path": "price/raw/TEST.csv", "symbol": "TEST", "sha256": digest(content)}]}
            (dataset / "source-manifest.json").write_text(json.dumps(manifest))
            report = run_benchmark(dataset, root / "results", ridge=True)
            self.assertEqual(report["trial_count"], 9)
            self.assertFalse(report["paper_score_reproduction"])
            self.assertFalse(report["holdout_used_for_fit_or_selection"])
            predictor = json.loads((root / "results/predictor-rows.jsonl").read_text().splitlines()[0])
            truth = json.loads((root / "results/truth-rows.jsonl").read_text().splitlines()[0])
            self.assertEqual(predictor["sample_id"], truth["sample_id"])
            for key in ["actual_return", "target_price", "target_date", "realized_return"]:
                self.assertNotIn(key, predictor)
            self.assertLess(predictor["issue_date"], truth["target_date"])
            packet = json.loads((root / "results/issue-packets.jsonl").read_text().splitlines()[0])
            self.assertFalse(packet["truth_side_evidence_included"])
            self.assertEqual(packet["context"]["metadata"]["context_class"], "subject_side_evidence")
            path.write_bytes(content + b"source drift")
            with self.assertRaisesRegex(ValueError, "source drift"):
                run_benchmark(dataset, root / "drift")
