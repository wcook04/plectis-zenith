"""Contract tests for provenance, temporal leakage, truth binding, and replay."""
import copy
import csv
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from benchmark import run


class BenchmarkTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "source.csv"
        self.manifest = self.root / "manifest.json"
        self.source.write_bytes(run.SOURCE.read_bytes())
        self.manifest.write_bytes(run.MANIFEST.read_bytes())

    def rewrite_rows(self, mutate):
        rows = list(csv.DictReader(io.StringIO(self.source.read_text())))
        mutate(rows)
        output = io.StringIO(newline="")
        writer = csv.DictWriter(output, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
        self.source.write_text(output.getvalue())
        manifest = json.loads(self.manifest.read_text())
        for record in manifest["files"]:
            if record["name"] == "dow_jones_index.data":
                record["sha256"] = hashlib.sha256(self.source.read_bytes()).hexdigest()
        self.manifest.write_text(json.dumps(manifest))

    def test_corrupted_source_rejected_before_output(self):
        self.source.write_bytes(self.source.read_bytes() + b"corruption")
        output = self.root / "result.json"
        self.assertEqual(run.main(["--source", str(self.source), "--manifest", str(self.manifest), "--output", str(output)]), 1)
        self.assertFalse(output.exists())
        self.assertFalse((self.root / "predictions.csv").exists())

    def test_forged_checksum_does_not_hide_corrupted_label(self):
        # Repair the hash deliberately, testing label reconstruction independently.
        self.rewrite_rows(lambda rows: rows[0].update(next_weeks_close="$999.00"))
        with self.assertRaisesRegex(ValueError, "Future label prices"):
            run.load_samples(self.source, self.manifest)

    def test_return_label_reconstructed_from_prices(self):
        self.rewrite_rows(lambda rows: rows[0].update(percent_change_next_weeks_price="99"))
        with self.assertRaisesRegex(ValueError, "Future return label"):
            run.load_samples(self.source, self.manifest)

    def test_exact_split_and_no_training_label_overlap(self):
        receipt, predictions = run.build()
        self.assertEqual(receipt["split"]["train"], {"start": "2011-01-07", "end": "2011-03-18", "rows": 330, "weeks": 11, "last_label_date": "2011-03-25"})
        self.assertEqual(receipt["split"]["test"], {"start": "2011-04-01", "end": "2011-06-17", "rows": 360, "weeks": 12, "last_label_date": "2011-06-24"})
        self.assertEqual(receipt["split"]["purged_rows"], 30)
        self.assertEqual(receipt["split"]["unverifiable_horizon_rows"], 30)
        self.assertLess(receipt["split"]["train"]["last_label_date"], receipt["split"]["test"]["start"])
        self.assertEqual(len(predictions), 1080)
        self.assertTrue(all(w["n"] == 30 for m in receipt["models"] for w in m["weekly"]))

    def test_future_metadata_cannot_influence_features_or_scores(self):
        _, before_samples, _, _ = run.load_samples()
        before_receipt, before_predictions = run.build()
        def mutate(rows):
            for row in rows:
                row["days_to_next_dividend"] = "999999"
                row["percent_return_next_dividend"] = "-999999"
                row["unapproved_future_signal"] = "SECRET_FUTURE"
        self.rewrite_rows(mutate)
        _, samples, _, _ = run.load_samples(self.source, self.manifest)
        receipt, predictions = run.build(self.source, self.manifest)
        self.assertEqual(samples, before_samples)
        self.assertEqual(predictions, before_predictions)
        self.assertEqual(receipt["models"], before_receipt["models"])
        self.assertTrue(all(set(r["features"]) == {"stock", "date", "percent_change_price"} for r in samples))

    def test_quarter_misclassification_rejected(self):
        self.rewrite_rows(lambda rows: rows[0].update(quarter="2"))
        with self.assertRaisesRegex(ValueError, "Quarter identity"):
            run.load_samples(self.source, self.manifest)

    def test_holdout_outcomes_cannot_change_fitted_probabilities(self):
        receipt, predictions = run.build()
        loaded = run.load_samples()
        provenance, samples, excluded, raw_rows = copy.deepcopy(loaded)
        for sample in samples:
            if sample["split"] == "test":
                sample["outcome"] = 1 - sample["outcome"]
        with patch.object(run, "load_samples", return_value=(provenance, samples, excluded, raw_rows)):
            revised, revised_predictions = run.build()
        self.assertEqual([r["probability"] for r in predictions], [r["probability"] for r in revised_predictions])
        self.assertEqual(receipt["models"][1]["probability"], revised["models"][1]["probability"])
        self.assertNotEqual([r["outcome"] for r in predictions], [r["outcome"] for r in revised_predictions])

    def test_duplicate_source_identity_rejected(self):
        self.rewrite_rows(lambda rows: rows.__setitem__(1, copy.deepcopy(rows[0])))
        with self.assertRaisesRegex(ValueError, "Duplicate stock/date"):
            run.load_samples(self.source, self.manifest)

    def test_brier_scores_and_downloaded_predictions_match(self):
        receipt, predictions = run.build()
        expected = {"neutral": 0.25, "train_frequency": 0.26001818519056086, "momentum": 0.2627777777777778}
        for model in receipt["models"]:
            self.assertAlmostEqual(model["brier"], expected[model["id"]], places=12)
            own = [p for p in predictions if p["model_id"] == model["id"]]
            recomputed = sum((p["probability"] - p["outcome"]) ** 2 for p in own) / len(own)
            self.assertAlmostEqual(model["brier"], recomputed, places=12)
        raw, csv_raw = run.serialize(receipt, predictions)
        artifact = json.loads(raw)["prediction_artifact"]
        self.assertEqual(artifact["sha256"], hashlib.sha256(csv_raw).hexdigest())
        self.assertEqual(len(list(csv.DictReader(io.StringIO(csv_raw.decode())))), artifact["rows"])

    def test_cli_rerun_is_byte_identical(self):
        output = self.root / "web/data/benchmark.json"
        args = ["--output", str(output)]
        self.assertEqual(run.main(args), 0)
        artifacts = [output, output.parent / "predictions.csv", output.parent / "source_manifest.json",
                     output.parent / "ATTRIBUTION.md", self.root / "web/docs/methodology.md"]
        first = [p.read_bytes() for p in artifacts]
        self.assertEqual((output.parent / "source_manifest.json").read_bytes(), run.MANIFEST.read_bytes())
        self.assertEqual((self.root / "web/docs/methodology.md").read_bytes(), (run.ROOT / "benchmark/README.md").read_bytes())
        receipt = json.loads(output.read_text())
        self.assertEqual(receipt["protocol_version"], "1")
        self.assertEqual(receipt["code_hash"], hashlib.sha256(Path(run.__file__).read_bytes()).hexdigest())
        self.assertEqual(receipt["downloads"]["manifest"], "data/source_manifest.json")
        self.assertEqual(run.main(args), 0)
        self.assertEqual(first, [p.read_bytes() for p in artifacts])


if __name__ == "__main__":
    unittest.main()
