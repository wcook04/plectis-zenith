"""Bounded AAPL rich episodes from the existing five pinned FinMultiTime leaves.

Reuse dated selection and long/cash accounting, with forward article/filing
context and explicitly separate training-only hindsight. No acquisition or LLM.
"""
from datetime import date, datetime, timedelta, timezone
import csv
import io
import json
from pathlib import Path

from benchmarks import finmultitime as fm
from benchmarks.trading_task import FEATURES, TASK, _read, state_features, evaluate_predictions


class _FrozenText:
    """Helpers read the exact admitted bytes instead of reopening live files."""
    def __init__(self, name, raw):
        self.name, self.text = name, raw.decode("utf-8-sig")

    def open(self):
        return io.StringIO(self.text)

    def read_text(self):
        return self.text


def _prices(source):
    rows, rejected = {}, 0
    with source.open() as stream:
        for raw in csv.DictReader(stream):
            try:
                stamp = datetime.fromisoformat(raw["Date"]).date().isoformat()
                values = {k: fm.finite(raw[k]) for k in ("Open", "High", "Low", "Close", "Volume")}
                if min(values[k] for k in ("Open", "High", "Low", "Close")) <= 0 or values["Volume"] < 0:
                    raise ValueError("Invalid price values")
            except (ValueError, KeyError, TypeError):
                rejected += 1
                continue
            if stamp in rows:
                raise ValueError("Duplicate price session")
            rows[stamp] = {"Date": stamp, **values}
    if not rows:
        raise ValueError("No valid source prices")
    return rows, rejected


def _context(news, facts):
    result = []
    for row in news:
        result.append({"ref_id": "news_" + row["id"][:24], "kind": "news",
                       "available_at": row["available_at_utc"], "content": row["text"],
                       "source_sha256": row["original_text_sha256"], "availability_basis": "date_only_approximate"})
    for row in facts:
        source = {k: row[k] for k in ("concept", "unit", "value", "start", "end", "filed", "accession", "form", "fiscal_year", "fiscal_period")}
        identity = fm.canonical_hash(source)
        result.append({"ref_id": "filing_" + identity[:24], "kind": "filing",
                       "available_at": row["available_at_utc"], "content": json.dumps(source, sort_keys=True),
                       "source_sha256": identity, "availability_basis": "date_only_approximate"})
    return result


def _spacing(values, count):
    if isinstance(count, bool) or not isinstance(count, int) or count < 1 or count > len(values):
        raise ValueError("Insufficient dates for declared count")
    return [values[0]] if count == 1 else [values[(i * (len(values) - 1)) // (count - 1)] for i in range(count)]


def build_dataset(directory, splits, counts):
    """All fit rows; fixed calendar-spaced train/validation/test rows only.

    Counts select dates before reading target prices or constructing rich
    evidence. No date is selected by news volume, fundamentals or returns.
    Review windows never extend into validation and never enter forward context.
    """
    directory = Path(directory)
    manifest = fm.verify_dataset(directory)
    manifest_raw = _read(directory / "source-manifest.json", 1024 * 1024)
    if json.loads(manifest_raw) != manifest:
        raise ValueError("Source manifest changed after verification")
    refs = {r["path"]: r for r in manifest["files"]}
    frozen = {}
    for name, ref in refs.items():
        raw = _read(directory / name, fm.MAX_MEMBER_BYTES)
        if fm.digest(raw) != ref["sha256"]:
            raise ValueError("Admitted source bytes changed")
        frozen[name] = _FrozenText(name, raw)
    prices, rejected = _prices(frozen["aapl-prices.csv"])
    last_price = max(prices)
    intervals = sorted((date.fromisoformat(a), date.fromisoformat(b), name) for name, (a, b) in splits.items())
    if not intervals or any(a >= b for a, b, _ in intervals) or any(intervals[i][1] > intervals[i + 1][0] for i in range(len(intervals) - 1)):
        raise ValueError("Split intervals must be disjoint")
    if set(counts) != set(splits) - {"fit"}:
        raise ValueError("Counts must declare every non-fit phase")
    calendar = fm.calendar_for(str(date.fromisoformat(min(prices)) - timedelta(days=60)),
                               str(max(intervals[-1][1], date.fromisoformat(last_price)) + timedelta(days=60)))
    sessions = [s.date().isoformat() for s in calendar.sessions]
    facts = [frozen[name] for name in sorted(fm.EXPECTED_FILES) if name.endswith(".json")]
    output, coverage, selected = {}, {}, {}
    for start, end, phase in intervals:
        indices = [i for i, stamp in enumerate(sessions[:-1]) if start.isoformat() <= stamp < end.isoformat()
                   and sessions[i + 1] < end.isoformat() and sessions[i + 1] <= last_price]
        indices = indices if phase == "fit" else _spacing(indices, counts[phase])
        selected[phase] = [sessions[i] for i in indices]
        samples = []
        for i in indices:
            stamp, target = sessions[i], sessions[i + 1]
            issue = calendar.session_close(stamp).to_pydatetime() + timedelta(minutes=1)
            entry = calendar.session_open(target).to_pydatetime()
            exit_at = calendar.session_close(target).to_pydatetime()
            history = [prices.get(s) for s in sessions[i - 19:i + 1]] if i >= 19 else []
            previous = prices.get(sessions[i - 20]) if i >= 20 else None
            available = len(history) == 20 and all(history) and previous is not None
            features = state_features(history, previous["Close"]) if available else None
            truth = prices.get(target)
            context, receipts, review = [], {}, []
            if phase != "fit":
                news, nr = fm.news_records(frozen["aapl-news.jsonl"], calendar, issue)
                filings, fr = fm.fundamental_records(facts, calendar, issue)
                context = _context(news, filings)
                receipts = {"news": nr, "filings": fr}
                if phase == "training":
                    desired = calendar.session_close(sessions[i + 6]).to_pydatetime()
                    split_limit = datetime.combine(end, datetime.min.time(), tzinfo=timezone.utc)
                    cutoff = min(desired, split_limit - timedelta(microseconds=1))
                    later, rr = fm.news_records(frozen["aapl-news.jsonl"], calendar, cutoff)
                    review = [r for r in _context(later, []) if issue < datetime.fromisoformat(r["available_at"]) <= cutoff]
                    receipts["review"] = {"cutoff": cutoff.isoformat(), "desired_cutoff": desired.isoformat(),
                                          "partial_window": cutoff < desired, "selection": rr,
                                          "boundary": "training_only_hindsight; latest5 in rolling7days; not causal proof"}
            sample = {"task": TASK, "symbol": "AAPL", "split": phase, "issue_date": stamp, "target_date": target,
                      "issue_at": issue.isoformat(), "entry_at": entry.isoformat(), "exit_at": exit_at.isoformat(),
                      "features": features, "feature_names": FEATURES[:], "history20": history if available else [],
                      "preceding_close": previous["Close"] if available else None,
                      "history_lookback": "20 contiguous XNYS OHLCV sessions plus preceding-session Close",
                      "info_status": "available" if available else "missing_history",
                      "availability_basis": "daily_price_close_plus1minute_assumed; text_and_filing_date_only_approximate",
                      "source_ref": "aapl-prices.csv", "source_sha256": refs["aapl-prices.csv"]["sha256"],
                      "source_dataset": fm.DATASET, "source_revision": fm.REVISION,
                      "context_source_sha256": {name: ref["sha256"] for name, ref in refs.items() if name != "aapl-prices.csv"},
                      "price_basis": "FinMultiTime AAPL Yahoo OHLC as supplied; historical split/dividend adjustment vintage unverified",
                      "forecast_units": "conditional_expected_arithmetic_next_session_open_to_close_return",
                      "anchor_return": features[3] if available else None,
                      "context_evidence": context, "context_selection_receipt": receipts,
                      "review_evidence": review,
                      "truth_open": truth["Open"] if truth else None, "truth_close": truth["Close"] if truth else None,
                      "actual_return": truth["Close"] / truth["Open"] - 1 if truth else None}
            excluded = {"truth_open", "truth_close", "actual_return", "review_evidence", "context_selection_receipt"}
            sample["sample_id"] = fm.canonical_hash({k: v for k, v in sample.items() if k not in excluded})
            samples.append(sample)
        output[phase] = samples
        coverage[phase] = {"issue_dates": len(samples), "scheduled_allowances": len(samples),
                           "available_information": sum(r["features"] is not None for r in samples),
                           "missing_truth": sum(r["actual_return"] is None for r in samples),
                           "context_news_rows": sum(sum(e["kind"] == "news" for e in r["context_evidence"]) for r in samples),
                           "context_filing_rows": sum(sum(e["kind"] == "filing" for e in r["context_evidence"]) for r in samples)}
    return {"task": TASK, "feature_names": FEATURES[:], "symbols": ["AAPL"], "splits": output,
            "coverage": coverage, "selected_dates": selected, "rejected_source_rows": {"AAPL": rejected},
            "source_manifest_sha256": fm.digest(manifest_raw), "source_csv_sha256": {"AAPL": refs["aapl-prices.csv"]["sha256"]},
            "dataset_commit": fm.REVISION, "rights_boundary": manifest["rights"],
            "unavailable_lanes": ["ETF", "MACRO", "POLYMARKET", "STOCKGRID"],
            "review_boundary": "training only; separate hindsight, forbidden from forward projection"}
