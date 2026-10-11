"""Synthetic forward/hindsight boundaries; no historical outcome scoring."""
import copy
import json
from pathlib import Path
import tempfile
from unittest.mock import patch

import pytest

from benchmarks import finmultitime as fm
from benchmarks import finmultitime_trading as rich
from benchmarks.trading_task import public_projection


@pytest.fixture
def dataset():
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        cal = fm.calendar_for("2024-01-01", "2024-04-01")
        sessions = [s.date().isoformat() for s in cal.sessions]
        prices = "Date,Open,High,Low,Close,Volume\n" + "".join(
            f"{day},100,103,99,102,20\n" for day in sessions)
        (root / "aapl-prices.csv").write_text(prices)
        news = [{"Date": day, "Url": f"https://example.invalid/{day}", "Article": f"Article {day}"} for day in sessions]
        (root / "aapl-news.jsonl").write_text("".join(json.dumps(r) + "\n" for r in news))
        facts = {"filings": [{"filing_date": "2025-12-31", "facts": {"us-gaap": {"Assets": {"units": {"USD": [
            {"filed": "2024-01-02", "end": "2023-12-31", "val": 100, "accn": "0000320193-24-000001"},
            {"filed": "2024-03-01", "end": "2023-12-31", "val": 900, "accn": "0000320193-24-000002"}]}}}}}]}
        (root / "aapl-balance-sheets.json").write_text(json.dumps(facts))
        for name in ("aapl-equity.json", "aapl-cash-flows.json"):
            (root / name).write_text('{"filings": []}')
        files = [{"path": name, "sha256": fm.digest((root / name).read_bytes())} for name in sorted(fm.EXPECTED_FILES)]
        manifest = {"files": files, "rights": "synthetic fixture"}
        (root / "source-manifest.json").write_text(json.dumps(manifest))
        with patch.object(fm, "verify_dataset", return_value=manifest):
            yield root, manifest


SPLITS = {"fit": ("2024-02-01", "2024-02-08"), "training": ("2024-02-08", "2024-02-16"),
          "validation": ("2024-02-16", "2024-03-01"), "test": ("2024-03-01", "2024-03-15")}
COUNTS = {"training": 2, "validation": 2, "test": 2}


def test_rich_forward_and_hindsight_boundaries(dataset):
    root, _ = dataset
    result = rich.build_dataset(root, SPLITS, COUNTS)
    assert len(result["splits"]["fit"]) == 4
    assert all(len(result["splits"][p]) == 2 for p in COUNTS)
    for phase, rows in result["splits"].items():
        for row in rows:
            assert len(row["history20"]) == 20
            assert len(row["features"]) == 8
            assert all(e["available_at"] <= row["issue_at"] for e in row["context_evidence"])
            assert all(len(e["content"]) <= 1200 for e in row["context_evidence"])
            if phase != "training":
                assert row["review_evidence"] == []
    last = result["splits"]["training"][-1]
    assert last["context_selection_receipt"]["review"]["partial_window"]
    assert last["review_evidence"]
    assert all(last["issue_at"] < e["available_at"] < "2024-02-16" for e in last["review_evidence"])
    filing = next(e for e in last["context_evidence"] if e["kind"] == "filing")
    assert json.loads(filing["content"])["value"] == 100
    assert "2025-12-31" not in filing["content"]
    projected = public_projection(last)
    assert projected["context_evidence"] == last["context_evidence"]
    assert projected["history20"] == last["history20"]
    changed = copy.deepcopy(last)
    changed.update(truth_open=-99, truth_close=-99, actual_return=-99,
                   review_evidence=[{"content": "future outcome"}])
    assert public_projection(changed) == projected
    projected["context_evidence"][0]["content"] = "mutated"
    assert last["context_evidence"][0]["content"] != "mutated"


def test_missing_target_does_not_change_calendar_selection(dataset):
    root, manifest = dataset
    before = rich.build_dataset(root, SPLITS, COUNTS)
    missing = before["splits"]["test"][-1]["target_date"]
    path = root / "aapl-prices.csv"
    path.write_text("\n".join(line for line in path.read_text().splitlines() if not line.startswith(missing)) + "\n")
    next(r for r in manifest["files"] if r["path"] == path.name)["sha256"] = fm.digest(path.read_bytes())
    (root / "source-manifest.json").write_text(json.dumps(manifest))
    after = rich.build_dataset(root, SPLITS, COUNTS)
    assert after["selected_dates"] == before["selected_dates"]
    assert after["splits"]["test"][-1]["actual_return"] is None


def test_admitted_source_drift_rejected(dataset):
    root, _ = dataset
    (root / "aapl-news.jsonl").write_text("changed")
    with pytest.raises(ValueError, match="Admitted source bytes changed"):
        rich.build_dataset(root, SPLITS, COUNTS)


def test_frozen_source_helpers_never_reopen_path(dataset):
    root, _ = dataset
    original = rich._read
    def read_and_replace(path, limit):
        raw = original(path, limit)
        if path.name == "aapl-news.jsonl":
            path.write_text("not the admitted source")
        return raw
    with patch.object(rich, "_read", side_effect=read_and_replace):
        result = rich.build_dataset(root, SPLITS, COUNTS)
    assert result["coverage"]["training"]["context_news_rows"] > 0
