"""Bounded transport, source identity, and three-channel temporal leakage tests."""
import copy
from datetime import datetime, timezone
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from benchmarks import finmultitime as fm


class FinMultiTimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.calendar = fm.calendar_for("2024-01-01", "2026-01-01")

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name) / "dataset"
        self.directory.mkdir()
        self.output = Path(self.temp.name) / "snapshot"
        prices = "Date,Open,High,Low,Close,Volume,Dividends,Stock Splits\n2025-04-16 00:00:00-04:00,100,103,99,102,20,0,0\n2025-04-17 00:00:00-04:00,102,104,100,103,30,0,0\n2025-04-21 00:00:00-04:00,103,105,102,104,40,0,0\n"
        (self.directory / "aapl-prices.csv").write_text(prices)
        news = [{"Date": "2025-04-17", "Url": "https://example.invalid/old", "Article": "Older historical article"},
                {"Date": "2025-04-18", "Url": "https://example.invalid/holiday", "Article": "Good Friday article"},
                {"Date": "2025-04-21", "Url": "https://example.invalid/same", "Article": "Same-day unavailable article"},
                {"Date": "2025-04-22", "Url": "https://example.invalid/future", "Article": "Future article"}]
        (self.directory / "aapl-news.jsonl").write_text("".join(json.dumps(row) + "\n" for row in news))
        self.facts = [self.fact("2025-04-17", 100, "0000320193-25-000001"),
                      self.fact("2025-04-21", 900, "0000320193-25-000002")]
        self.write_facts()
        for name in ["aapl-equity.json", "aapl-cash-flows.json"]:
            (self.directory / name).write_text('{"filings": []}')
        self.update_manifest()
        self.patch_hashes = patch.object(fm, "EXPECTED_SOURCE_HASHES", self.hashes)
        self.patch_hashes.start(); self.addCleanup(self.patch_hashes.stop)

    @staticmethod
    def fact(filed, value, accession):
        return {"filed": filed, "end": "2025-03-31", "val": value, "accn": accession, "form": "10-Q", "fy": 2025, "fp": "Q1"}

    def write_facts(self):
        # Future wrapper date must not hide an independently older filed fact.
        root = {"filings": [{"filing_date": "2025-12-31", "facts": {"us-gaap": {"Assets": {"units": {"USD": self.facts}}}}}]}
        (self.directory / "aapl-balance-sheets.json").write_text(json.dumps(root))

    def update_manifest(self):
        records = []
        for name in sorted(fm.EXPECTED_FILES):
            raw = (self.directory / name).read_bytes()
            records.append({"path": name, "bytes": len(raw), "sha256": fm.digest(raw), "archive_url": "https://example.invalid/archive", "member": name})
        self.hashes = {r["path"]: r["sha256"] for r in records}
        manifest = {"dataset": fm.DATASET, "revision": fm.REVISION, "protocol_version": fm.PROTOCOL,
                    "availability_policy": fm.POLICY, "files": records}
        manifest["manifest_sha256"] = fm.canonical_hash(manifest)
        fm.write_json(self.directory / "source-manifest.json", manifest)

    def test_good_friday_news_activates_next_actual_session(self):
        self.assertEqual(fm.next_open("2025-04-18", self.calendar), datetime(2025, 4, 21, 13, 30, tzinfo=timezone.utc))
        cutoff = datetime(2025, 4, 21, 20, tzinfo=timezone.utc)
        records, receipt = fm.news_records(self.directory / "aapl-news.jsonl", self.calendar, cutoff)
        self.assertEqual({r["source_date"] for r in records}, {"2025-04-17", "2025-04-18"})
        self.assertTrue(all(datetime.fromisoformat(r["available_at_utc"]) <= cutoff for r in records))
        self.assertEqual(receipt["retained_rows"], 2)

    def test_same_day_filing_revision_excluded_despite_old_period_end(self):
        cutoff = datetime(2025, 4, 21, 20, tzinfo=timezone.utc)
        records, _ = fm.fundamental_records([self.directory / "aapl-balance-sheets.json"], self.calendar, cutoff)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["value"], 100)
        self.assertEqual(records[0]["filed"], "2025-04-17")
        self.assertEqual(records[0]["outer_filing_date"], "2025-12-31")
        later, _ = fm.fundamental_records([self.directory / "aapl-balance-sheets.json"], self.calendar, datetime(2025, 4, 22, 20, tzinfo=timezone.utc))
        self.assertEqual(later[0]["value"], 900)

    def test_same_day_price_is_not_available_before_close(self):
        rows, _ = fm.price_records(self.directory / "aapl-prices.csv", self.calendar, datetime(2025, 4, 21, 19, 59, tzinfo=timezone.utc))
        self.assertEqual(rows[-1]["session_date"], "2025-04-17")
        rows, _ = fm.price_records(self.directory / "aapl-prices.csv", self.calendar, datetime(2025, 4, 21, 20, tzinfo=timezone.utc))
        self.assertEqual(rows[-1]["session_date"], "2025-04-21")

    def test_malformed_fundamental_structures_are_counted_and_siblings_survive(self):
        cutoff = datetime(2025, 4, 21, 20, tzinfo=timezone.utc)
        path = self.directory / "aapl-balance-sheets.json"
        valid = {"facts": {"us-gaap": {"Assets": {"units": {"USD": [self.facts[0]]}}}}}
        malformed = [None, {"facts": []}, {"facts": {"us-gaap": []}},
                     {"facts": {"us-gaap": {"Assets": None}}},
                     {"facts": {"us-gaap": {"Assets": {"units": []}}}},
                     {"facts": {"us-gaap": {"Assets": {"units": {"USD": {}}}}}},
                     {"facts": {"us-gaap": {"Assets": {"units": {"USD": [None]}}}}}]
        path.write_text(json.dumps({"filings": malformed + [valid]}))
        records, receipt = fm.fundamental_records([path], self.calendar, cutoff)
        self.assertEqual([r["value"] for r in records], [100])
        self.assertEqual(receipt["rejected_facts"], len(malformed))
        self.assertEqual(receipt["eligible_unique_facts"], 1)
        for content in ["null", "[]", '{"filings": null}', '{"filings": {}}', "{"]:
            with self.subTest(content=content):
                path.write_text(content)
                records, receipt = fm.fundamental_records([path], self.calendar, cutoff)
                self.assertEqual(records, [])
                self.assertEqual(receipt["rejected_facts"], 1)

    def test_three_channels_snapshot_and_canonical_partial_native_artifacts(self):
        packet = fm.snapshot(self.directory, "2025-04-21", self.output, self.calendar)
        self.assertEqual({k: v["availability"] for k, v in packet["channels"].items()}, {"prices": "available", "text": "available", "fundamentals": "available"})
        self.assertFalse(packet["truth_side_evidence_included"])
        self.assertIn("MACRO", packet["unavailable_feed_lanes"])
        stock = json.loads((self.output / "artifacts/global_stock_feed.json").read_text())
        self.assertEqual(stock["data"]["rows"][0][3], 104)
        self.assertIsNone(stock["data"]["rows"][0][4])
        self.assertEqual(stock["metadata"]["diagnostics"]["price_observations"]["AAPL"]["provider"], "FinMultiTime")
        self.assertEqual(stock["metadata"]["status"], "partial")
        self.assertNotIn("node_hash", stock)

    def test_after_dataset_end_price_is_explicitly_stale(self):
        packet = fm.snapshot(self.directory, "2025-04-22", self.output, self.calendar)
        prices = packet["channels"]["prices"]
        self.assertEqual(prices["availability"], "partial_stale")
        self.assertFalse(prices["selection_receipt"]["current_issue_price_available"])
        stock = json.loads((self.output / "artifacts/global_stock_feed.json").read_text())
        self.assertIsNone(stock["data"]["rows"][0][3])

    def test_frozen_snapshot_replay_preserves_bytes_and_rejects_changed_issue(self):
        packet = fm.snapshot(self.directory, "2025-04-21", self.output, self.calendar)
        first = {p.relative_to(self.output).as_posix(): p.read_bytes() for p in self.output.rglob("*.json")}
        self.assertEqual(packet, fm.snapshot(self.directory, "2025-04-21", self.output, self.calendar))
        self.assertEqual(first, {p.relative_to(self.output).as_posix(): p.read_bytes() for p in self.output.rglob("*.json")})
        with self.assertRaisesRegex(ValueError, "different frozen"):
            fm.snapshot(self.directory, "2025-04-22", self.output, self.calendar)
        (self.output / "feed-envelopes.json").write_text("{}")
        with self.assertRaisesRegex(ValueError, "artifact drift"):
            fm.snapshot(self.directory, "2025-04-21", self.output, self.calendar)

    def test_source_drift_and_extra_members_rejected(self):
        (self.directory / "aapl-prices.csv").write_text("changed")
        with self.assertRaisesRegex(ValueError, "member-size"):
            fm.verify_dataset(self.directory)

    def test_signed_manifest_cannot_change_audited_source_hash(self):
        manifest = json.loads((self.directory / "source-manifest.json").read_text())
        manifest["files"][0]["sha256"] = "0" * 64
        manifest.pop("manifest_sha256"); manifest["manifest_sha256"] = fm.canonical_hash(manifest)
        fm.write_json(self.directory / "source-manifest.json", manifest)
        with self.assertRaisesRegex(ValueError, "audited pinned"):
            fm.verify_dataset(self.directory)

    def test_zip_crc_and_member_boundaries(self):
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_STORED) as z:
            z.writestr("safe.csv", b"original-data")
            z.writestr("../escape", b"unsafe-name")
        good = stream.getvalue()
        with zipfile.ZipFile(io.BytesIO(good)) as z:
            self.assertEqual(fm.read_member(z, "safe.csv")[1], b"original-data")
            with self.assertRaisesRegex(ValueError, "extraction bounds"):
                fm.read_member(z, "safe.csv", size_limit=3)
        corrupted = good.replace(b"original-data", b"corrupt--data", 1)
        with zipfile.ZipFile(io.BytesIO(corrupted)) as z:
            with self.assertRaises(zipfile.BadZipFile):
                fm.read_member(z, "safe.csv")
        self.assertFalse((Path(self.temp.name) / "escape").exists())

    def test_transport_refuses_full_response_and_transfer_overrun(self):
        class FullResponse:
            status, headers = 200, {}
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def read(self, size): raise AssertionError("Full response body must not be read")
        archive = fm.RemoteArchive("https://example.invalid/data", 100, fm.RangeBudget(), opener=lambda *a, **k: FullResponse())
        with self.assertRaisesRegex(ValueError, "full download refused"):
            archive.read(10)
        archive = fm.RemoteArchive("https://example.invalid/data", 100, fm.RangeBudget(maximum=2), opener=lambda *a, **k: self.fail("Cap must precede network"))
        with self.assertRaisesRegex(ValueError, "transfer cap"):
            archive.read(3)

    def test_non_session_issue_refused(self):
        with self.assertRaisesRegex(ValueError, "not an XNYS session"):
            fm.snapshot(self.directory, "2025-04-18", self.output, self.calendar)


if __name__ == "__main__":
    unittest.main()
