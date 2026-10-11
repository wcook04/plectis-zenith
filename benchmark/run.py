"""Build deterministic scores and frozen predictions from the licensed UCI CSV.

python3 -m benchmark.run --output work/benchmark/benchmark.json
This is a historical pipeline demonstration, not an LLM or trading backtest.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
from datetime import datetime
import hashlib
import io
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data/historical/dow_jones_index.data"
MANIFEST = ROOT / "data/historical/source_manifest.json"
FEATURES = ("stock", "date", "percent_change_price")
FORBIDDEN = ("next_weeks_open", "next_weeks_close", "percent_change_next_weeks_price",
             "days_to_next_dividend", "percent_return_next_dividend")


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def date_iso(value: str) -> str:
    return datetime.strptime(value, "%m/%d/%Y").date().isoformat()


def number(value: str) -> float:
    result = float(value.removeprefix("$"))
    if not math.isfinite(result):
        raise ValueError("Nonfinite source value")
    return result


def load_samples(source: Path = SOURCE, manifest: Path = MANIFEST):
    provenance = json.loads(manifest.read_text())
    expected = next(f["sha256"] for f in provenance["files"] if f["name"] == "dow_jones_index.data")
    raw = source.read_bytes()
    if digest(raw) != expected:
        raise ValueError("Source checksum mismatch: refusing revised or corrupted benchmark data")
    parsed = list(csv.DictReader(io.StringIO(raw.decode("utf-8"))))
    required = set(FEATURES) | {"quarter", "open", "close", *FORBIDDEN}
    if not parsed or not required.issubset(parsed[0]):
        raise ValueError("Source columns do not match the fixed benchmark contract")
    rows = sorted(parsed, key=lambda r: (r["stock"], date_iso(r["date"])))
    keys = {(r["stock"], date_iso(r["date"])) for r in rows}
    if len(keys) != len(rows):
        raise ValueError("Duplicate stock/date source rows")
    counts = Counter(date_iso(r["date"]) for r in rows)
    if len(rows) != 750 or len(counts) != 25 or set(counts.values()) != {30}:
        raise ValueError("Fixed dataset must have 750 rows, 25 weeks, and 30 stocks per week")
    if len({r["stock"] for r in rows}) != 30:
        raise ValueError("Fixed universe must contain 30 stocks")
    for r in rows:
        expected_quarter = "1" if date_iso(r["date"]) < "2011-04-01" else "2"
        if r["quarter"] != expected_quarter:
            raise ValueError("Quarter identity disagrees with issue date")
    samples, excluded = [], []
    for index, row in enumerate(rows):
        next_row = rows[index + 1] if index + 1 < len(rows) else None
        if next_row is None or next_row["stock"] != row["stock"]:
            excluded.append({"stock": row["stock"], "date": date_iso(row["date"]), "reason": "unverifiable_final_horizon"})
            continue
        future_open, future_close = number(next_row["open"]), number(next_row["close"])
        if future_open <= 0 or future_close <= 0:
            raise ValueError("Nonpositive next-week price")
        if number(row["next_weeks_open"]) != future_open or number(row["next_weeks_close"]) != future_close:
            raise ValueError("Future label prices disagree with the following stock/week row")
        realized_return = (future_close / future_open - 1) * 100
        if abs(realized_return - number(row["percent_change_next_weeks_price"])) >= 0.0001:
            raise ValueError("Future return label disagrees with independently reconstructed prices")
        # Explicit whitelist, so no future-valued source column can enter features.
        feature = {"stock": row["stock"], "date": date_iso(row["date"]),
                   "percent_change_price": number(row["percent_change_price"])}
        if row["quarter"] == "1" and next_row["quarter"] == "2":
            excluded.append({"stock": row["stock"], "date": feature["date"], "reason": "purged_cross_quarter_horizon"})
            continue
        samples.append({"features": feature, "event_end": date_iso(next_row["date"]),
                        "outcome": int(future_close > future_open),
                        "split": "train" if row["quarter"] == "1" else "test"})
    train = [r for r in samples if r["split"] == "train"]
    test = [r for r in samples if r["split"] == "test"]
    if len(train) != 330 or len(test) != 360:
        raise ValueError("Fixed purged split must contain 330 training and 360 test samples")
    if max(r["event_end"] for r in train) >= min(r["features"]["date"] for r in test):
        raise ValueError("Training labels overlap the holdout issue period")
    samples.sort(key=lambda r: (r["features"]["date"], r["features"]["stock"]))
    return provenance, samples, excluded, rows


def build(source: Path = SOURCE, manifest: Path = MANIFEST):
    provenance, samples, excluded, raw_rows = load_samples(source, manifest)
    train = [r for r in samples if r["split"] == "train"]
    test = [r for r in samples if r["split"] == "test"]
    empirical = (sum(r["outcome"] for r in train) + 1) / (len(train) + 2)
    specifications = [
        ("neutral", "Neutral 50%", "Constant probability 0.5", {"kind": "constant", "value": 0.5}, lambda f: 0.5),
        ("train_frequency", "Training frequency", "Q1 positive-label frequency with add-one smoothing",
         {"kind": "train_only_frequency", "value": empirical}, lambda f: empirical),
        ("momentum", "Fixed momentum", "Probability 0.6 after a positive current week; otherwise 0.4",
         {"kind": "fixed_rule", "positive_current_week": 0.6, "otherwise": 0.4},
         lambda f: 0.6 if f["percent_change_price"] > 0 else 0.4),
    ]
    models, predictions = [], []
    for model_id, name, description, probability, predictor in specifications:
        scored = []
        for sample in test:
            feature = sample["features"]
            p = predictor(feature)
            row = {"model_id": model_id, "stock": feature["stock"], "issue_date": feature["date"],
                   "event_end": sample["event_end"], "current_week_percent_change": feature["percent_change_price"],
                   "probability": p, "outcome": sample["outcome"], "brier": (p - sample["outcome"]) ** 2}
            scored.append(row)
            predictions.append(row)
        weekly = []
        for date in sorted({r["issue_date"] for r in scored}):
            group = [r for r in scored if r["issue_date"] == date]
            weekly.append({"date": date, "event_end": group[0]["event_end"], "n": len(group),
                           "brier": math.fsum(r["brier"] for r in group) / len(group),
                           "positive_rate": sum(r["outcome"] for r in group) / len(group)})
        brier = math.fsum(r["brier"] for r in weekly) / len(weekly)
        models.append({"id": model_id, "name": name, "description": description, "brier": brier,
                       "skill_vs_neutral": 1 - brier / 0.25, "probability": probability,
                       "predictions": len(scored), "weekly": weekly})
    def period(group):
        dates = sorted({r["features"]["date"] for r in group})
        return {"start": dates[0], "end": dates[-1], "rows": len(group), "weeks": len(dates),
                "last_label_date": max(r["event_end"] for r in group)}
    exclusions = Counter(r["reason"] for r in excluded)
    receipt = {
        "schema_version": "plectis_benchmark_v1",
        "protocol_version": "1",
        "code_hash": digest(Path(__file__).read_bytes()),
        "dataset": {"id": "uci_dow_jones_312", "name": "UCI Dow Jones Index — weekly 2011 sample",
                    "source_url": provenance["source_page"], "doi": provenance["doi"],
                    "license": provenance["data_license"], "license_url": provenance["license_url"],
                    "sha256": digest(source.read_bytes()), "attribution": provenance["attribution"],
                    "rows": 750, "stocks": 30, "weeks": 25,
                    "period": {"start": "2011-01-07", "end": "2011-06-24"},
                    "missing_fields": dict(sorted(Counter(k for r in raw_rows for k, v in r.items() if v == "").items()))},
        "split": {"policy": "fixed_q1_train_q2_test_with_horizon_purge", "train": period(train), "test": period(test),
                  "purged_rows": exclusions["purged_cross_quarter_horizon"],
                  "unverifiable_horizon_rows": exclusions["unverifiable_final_horizon"], "excluded": excluded},
        "target": {"id": "next_week_open_to_close_positive", "description": "Does the following week's closing price exceed that week's opening price? Equal prices count as 0.",
                   "horizon": "following observed week", "price_basis": "unadjusted source prices; corporate-action correctness is not established"},
        "models": models,
        "checks": [{"id": code, "label": label, "status": "passed", "detail": detail} for code, label, detail in [
            ("source_hash", "Source checksum", digest(source.read_bytes())),
            ("labels", "Independent label reconstruction", "720 available horizons checked against next-row open/close, including 30 purged rows"),
            ("feature_boundary", "Future columns excluded", "Models receive only the explicit current-week feature whitelist"),
            ("split_boundary", "Purged temporal split", "All training labels resolve strictly before the first test issue week"),
            ("coverage", "Balanced weekly coverage", "30 stocks in each of 12 test issue weeks"),
        ]],
        "methodology": {"feature_allowlist": list(FEATURES), "prohibited_features": list(FORBIDDEN),
                        "comparison_unit": "week", "score": "Brier = mean((probability - outcome)^2); lower is better",
                        "baseline_fit": "Training frequency is fitted once on the purged Q1 split. Momentum probabilities are fixed without tuning.",
                        "feature_availability_assumption": "Current-week features become available after its last observed close. Exact historical publication timestamps are unavailable.",
                        "limitations": ["Small selected historical sample; no investment performance or generalization claim.",
                                        "30 assets share each market week. There are 12 holdout weeks, not 360 independent trials.",
                                        "No precise historical publication timestamps, vintage data or verified corporate-action adjustment.",
                                        "Historical LLM performance is not evaluated; training-data contamination is uncontrolled.",
                                        "No trading execution, costs, dividends, portfolio returns or significance claims."]},
        "downloads": {"predictions": "data/predictions.csv", "source": provenance["source_url"],
                      "manifest": "data/source_manifest.json", "attribution": "data/ATTRIBUTION.md",
                      "methodology": "docs/methodology.md"},
    }
    return receipt, predictions


def serialize(receipt, predictions):
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=list(predictions[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(predictions)
    csv_raw = stream.getvalue().encode("utf-8")
    receipt = {**receipt, "prediction_artifact": {"rows": len(predictions), "sha256": digest(csv_raw)}}
    return (json.dumps(receipt, indent=2, sort_keys=True, allow_nan=False) + "\n").encode("utf-8"), csv_raw


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "work/benchmark/benchmark.json")
    parser.add_argument("--source", type=Path, default=SOURCE)
    parser.add_argument("--manifest", type=Path, default=MANIFEST)
    args = parser.parse_args(argv)
    try:
        receipt, predictions = build(args.source, args.manifest)
        json_raw, csv_raw = serialize(receipt, predictions)
    except (ValueError, KeyError, StopIteration, OSError) as exc:
        print(f"Benchmark refused: {exc}", file=sys.stderr)
        return 1
    args.output.parent.mkdir(parents=True, exist_ok=True)
    (args.output.parent / "predictions.csv").write_bytes(csv_raw)
    (args.output.parent / "source_manifest.json").write_bytes(args.manifest.read_bytes())
    (args.output.parent / "ATTRIBUTION.md").write_bytes((ROOT / "data/historical/ATTRIBUTION.md").read_bytes())
    # Benchmark output stays local. Arbitrary output folders keep docs inside
    # that folder, rather than writing into an unrelated filesystem parent.
    document_root = args.output.parent.parent if args.output.parent.name == "data" else args.output.parent
    docs = document_root / "docs"
    docs.mkdir(parents=True, exist_ok=True)
    (docs / "methodology.md").write_bytes((ROOT / "benchmark/README.md").read_bytes())
    args.output.write_bytes(json_raw)
    print(f"Wrote {args.output}: 330 train rows, 360 test rows, 12 test weeks; no external calls")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
