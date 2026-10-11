"""Temporal invariants using synthetic XLSX cells matching reviewed RUC schema."""
from datetime import datetime, timezone
import hashlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipFile

from benchmarks import macro_vintage as mv


class MacroVintageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.calendar = mv.calendar_for("2015-01-01", "2016-01-01")

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "ruc.xlsx"
        self.write_workbook()
        self.data = self.load()

    def write_workbook(self, *, duplicate_column=False, duplicate_period=False):
        ns = mv.NS["m"]
        shared = ["DATE", "RUC15Q2", "RUC15Q2" if duplicate_column else "RUC15Q3", "2015:04", "2015:07", "#N/A"]
        rows = '<row r="1"><c r="A1" t="s"><v>0</v></c><c r="B1" t="s"><v>1</v></c><c r="C1" t="s"><v>2</v></c></row>'
        rows += '<row r="2"><c r="A2" t="s"><v>3</v></c><c r="B2"><v>5.4</v></c><c r="C2" t="s"><v>5</v></c></row>'
        rows += f'<row r="3"><c r="A3" t="s"><v>{3 if duplicate_period else 4}</v></c><c r="B3" t="s"><v>5</v></c><c r="C3"><v>5.3</v></c></row><row r="4" ht="13"/>'
        with ZipFile(self.path, "w") as z:
            z.writestr("xl/workbook.xml", f'<workbook xmlns="{ns}"><sheets><sheet name="ruc"/></sheets></workbook>')
            z.writestr("xl/sharedStrings.xml", f'<sst xmlns="{ns}">'+''.join(f'<si><t>{s}</t></si>' for s in shared)+'</sst>')
            z.writestr("xl/worksheets/sheet1.xml", f'<worksheet xmlns="{ns}"><sheetData>{rows}</sheetData></worksheet>')

    def load(self):
        return mv.load_workbook(self.path, acquired_at=datetime(2026, 10, 11, tzinfo=timezone.utc),
                                expected_sha256=hashlib.sha256(self.path.read_bytes()).hexdigest(),
                                calendar=self.calendar, source_basis="synthetic_regression_fixture")

    def observation(self, stamp, period="2015-07"):
        return mv.observation(self.data, issue_at=datetime.fromisoformat(stamp), period=period)

    def test_future_vintage_cannot_backfill_old_observation(self):
        early = self.observation("2015-08-14T20:00:00+00:00")
        self.assertEqual(early["vintage_id"], "RUC15Q2")
        self.assertIsNone(early["value"])
        self.assertEqual(early["status"], "missing_observation")
        late = self.observation("2015-08-17T13:30:01+00:00")
        self.assertEqual((late["vintage_id"], late["value"]), ("RUC15Q3", 5.3))

    def test_boundary_equality_is_strict_and_weekend_opens_monday(self):
        boundary = self.data["vintages"]["RUC15Q3"]["available_at"]
        self.assertEqual(boundary, "2015-08-17T13:30:00+00:00")
        self.assertEqual(self.observation(boundary)["vintage_id"], "RUC15Q2")

    def test_latest_missing_never_borrows_old_nonmissing_revision(self):
        late = self.observation("2015-08-17T20:00:00+00:00", "2015-04")
        self.assertIsNone(late["value"])
        self.assertEqual(late["vintage_id"], "RUC15Q3")

    def test_no_eligible_vintage_is_distinct_from_missing_cell(self):
        result = self.observation("2015-05-14T20:00:00+00:00", "2015-04")
        self.assertEqual(result["status"], "no_eligible_vintage")
        self.assertIsNone(result["vintage_id"])

    def test_hash_and_source_basis_survive_selection(self):
        result = self.observation("2015-08-18T20:00:00+00:00")
        self.assertEqual(result["source_sha256"], hashlib.sha256(self.path.read_bytes()).hexdigest())
        self.assertEqual(result["source_basis"], "synthetic_regression_fixture")
        self.assertIn("not_original_delivery", result["availability_basis"])
        self.assertEqual(result["units"], "percent")
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            mv.load_workbook(self.path, acquired_at=datetime.now(timezone.utc))

    def test_naive_clock_and_future_period_rejected(self):
        with self.assertRaisesRegex(ValueError, "timezone"):
            mv.observation(self.data, issue_at=datetime(2015, 8, 18), period="2015-07")
        with self.assertRaisesRegex(ValueError, "future"):
            self.observation("2015-08-18T20:00:00+00:00", "2015-09")

    def test_source_change_after_read_cannot_change_hashed_parsing(self):
        original = self.path.read_bytes()
        real_open = Path.open
        path = self.path

        class ReplacingStream(io.BytesIO):
            def read(self, size=-1):
                result = super().read(size)
                with real_open(path, "wb") as replacement:
                    replacement.write(b"changed after admitted read")
                return result

        with patch.object(Path, "open", return_value=ReplacingStream(original)) as opened:
            loaded = mv.load_workbook(self.path, acquired_at=datetime.now(timezone.utc),
                                      expected_sha256=hashlib.sha256(original).hexdigest(),
                                      calendar=self.calendar, source_basis="synthetic_regression_fixture")
        opened.assert_called_once_with("rb")
        self.assertEqual(loaded["vintages"]["RUC15Q3"]["values"]["2015-07"], 5.3)
        self.assertEqual(loaded["source_sha256"], hashlib.sha256(original).hexdigest())
        self.assertNotEqual(self.path.read_bytes(), original)

    def test_oversized_stream_is_bounded_before_hash_or_zip_parsing(self):
        requests = []

        class GrowingStream(io.BytesIO):
            def read(self, size=-1):
                requests.append(size)
                return super().read(size)

        # The on-disk fixture is small; its opened stream has grown beyond limit.
        stream = GrowingStream(b"x" * (mv.MAX_COMPRESSED_BYTES + 100))
        with patch.object(Path, "open", return_value=stream):
            with self.assertRaisesRegex(ValueError, "compressed size bound"):
                mv.load_workbook(self.path, acquired_at=datetime.now(timezone.utc),
                                  expected_sha256="not a matching hash", calendar=self.calendar)
        self.assertEqual(requests, [mv.MAX_COMPRESSED_BYTES + 1])

    def test_duplicate_columns_and_periods_rejected(self):
        for kwargs in ({"duplicate_column": True}, {"duplicate_period": True}):
            with self.subTest(kwargs=kwargs):
                self.write_workbook(**kwargs)
                with self.assertRaisesRegex(ValueError, "Duplicate"):
                    self.load()


if __name__ == "__main__":
    unittest.main()
