"""Import pinned StockNet raw-price objects and run an explicit price-only protocol."""
from __future__ import annotations

import argparse
from collections import defaultdict
import csv
from datetime import date
import hashlib
import io
import json
import math
from pathlib import Path
import re
import subprocess
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_PATH = Path(__file__).with_name("stocknet_protocol.json")
FIELDS = ["Date", "Open", "High", "Low", "Close", "Adj Close", "Volume"]
FEATURES = ["return_1", "return_5", "return_20", "intraday_range", "open_gap", "intraday_return", "volume_relative_20", "close_range_position"]


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_digest(value: Any) -> str:
    return digest(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode())


def protocol() -> dict[str, Any]:
    return json.loads(PROTOCOL_PATH.read_text())


def _git(repo: Path, *arguments: str) -> bytes:
    return subprocess.check_output(["git", "-C", str(repo), *arguments], timeout=180)


def _batch_objects(repo: Path, commit: str, paths: list[str]) -> dict[str, bytes]:
    """Only request explicit safe text paths; never deserialize executable formats."""
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("A full pinned Git commit is required")
    if any(not re.fullmatch(r"(?:price/raw/[A-Z0-9-]+\.csv|StockTable|README\.md|LICENSE|src/config\.yml|src/DataPipe\.py)", path) for path in paths):
        raise ValueError("Unapproved dataset object path")
    request = "".join(f"{commit}:{path}\n" for path in paths).encode()
    process = subprocess.run(["git", "-C", str(repo), "cat-file", "--batch"], input=request, capture_output=True, timeout=240)
    if process.returncode:
        raise ValueError("Pinned source object fetch failed: " + process.stderr.decode(errors="replace")[-1000:])
    if len(process.stdout) > 64 * 1024 * 1024:
        raise ValueError("Dataset exceeds bounded text import size")
    cursor = 0
    result = {}
    for path in paths:
        newline = process.stdout.index(b"\n", cursor)
        header = process.stdout[cursor:newline].decode().split()
        if len(header) != 3 or header[1] != "blob":
            raise ValueError(f"Missing/non-blob pinned source: {path}")
        size = int(header[2])
        if size > 4 * 1024 * 1024:
            raise ValueError(f"Oversize CSV/source object: {path}")
        cursor = newline + 1
        content = process.stdout[cursor:cursor + size]
        if len(content) != size:
            raise ValueError("Truncated Git object batch")
        result[path] = content
        cursor += size + 1
    return result


def verify_split_sources(config: bytes, pipeline: bytes, specification: dict[str, Any]) -> None:
    text = config.decode("utf-8")
    names = {"train": "train", "dev": "dev", "test": "test"}
    for split, source_name in names.items():
        for endpoint, expected in zip(("start", "end"), specification["splits"][split]):
            match = re.search(rf"^\s+{source_name}_{endpoint}_date:\s*'([^']+)'", text, flags=re.MULTILINE)
            if not match or match.group(1) != expected:
                raise ValueError("Pinned StockNet split config differs from this protocol")
    if "start_date <= main_target_date_str < end_date" not in pipeline.decode("utf-8"):
        raise ValueError("Pinned source does not establish the expected half-open split semantics")


def parse_prices(content: bytes):
    reader = csv.DictReader(io.StringIO(content.decode("utf-8-sig")))
    if reader.fieldnames != FIELDS:
        raise ValueError("Unexpected raw StockNet price fields")
    rows, rejected = [], []
    seen = set()
    for line, raw in enumerate(reader, 2):
        try:
            stamp = date.fromisoformat(raw["Date"]).isoformat()
            values = {field: float(raw[field]) for field in FIELDS[1:]}
            if any(not math.isfinite(value) for value in values.values()):
                raise ValueError("nonfinite numeric field")
            if any(values[field] <= 0 for field in FIELDS[1:-1]) or values["Volume"] < 0:
                raise ValueError("nonpositive price or negative volume")
            if stamp in seen:
                raise ValueError("duplicate date")
            seen.add(stamp)
            rows.append({"Date": stamp, **values})
        except (ValueError, TypeError, KeyError) as error:
            rejected.append({"line": line, "date": raw.get("Date"), "reason": str(error)})
    rows.sort(key=lambda row: row["Date"])
    if not rows:
        raise ValueError("No admissible numeric price rows")
    return rows, rejected


def import_dataset(dataset_repo: Path, code_repo: Path, output: Path) -> dict[str, Any]:
    spec = protocol()
    paths = _git(dataset_repo, "ls-tree", "-r", "--name-only", spec["dataset_commit"], "price/raw").decode().splitlines()
    if len(paths) != 88 or any(not path.endswith(".csv") for path in paths):
        raise ValueError("Pinned StockNet raw universe must contain exactly 88 CSV files")
    objects = _batch_objects(dataset_repo, spec["dataset_commit"], ["README.md", "LICENSE", "StockTable", *paths])
    code = _batch_objects(code_repo, spec["code_commit"], ["src/config.yml", "src/DataPipe.py", "README.md", "LICENSE"])
    verify_split_sources(code["src/config.yml"], code["src/DataPipe.py"], spec)
    table = list(csv.DictReader(io.StringIO(objects["StockTable"].decode()), delimiter="\t"))
    symbols = {row["Symbol"].lstrip("$") for row in table}
    if symbols != {Path(path).stem for path in paths}:
        raise ValueError("StockTable and raw price universe differ")
    output.mkdir(parents=True, exist_ok=True)
    records = []
    for path, content in objects.items():
        destination = output / path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)
        record = {"path": path, "sha256": digest(content), "bytes": len(content)}
        if path.startswith("price/raw/"):
            rows, rejected = parse_prices(content)
            record.update(symbol=Path(path).stem, valid_rows=len(rows), rejected_rows=rejected,
                          first_date=rows[0]["Date"], last_date=rows[-1]["Date"], fields=FIELDS)
        records.append(record)
    source = output / "protocol-source"
    source.mkdir(exist_ok=True)
    code_records = []
    for path, content in code.items():
        destination = source / path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)
        code_records.append({"path": path, "sha256": digest(content), "bytes": len(content)})
    manifest = {"schema_version": "stocknet_local_import_v1", "dataset_repository": spec["dataset_repository"],
                "dataset_commit": spec["dataset_commit"], "code_repository": spec["code_repository"],
                "code_commit": spec["code_commit"], "code_files": code_records, "files": records,
                "stock_count": len(paths), "protocol_sha256": canonical_digest(spec),
                "rights_boundary": spec["data_distribution"], "paper_score_reproduction": False}
    (output / "source-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def features(rows: list[dict[str, Any]], index: int):
    if index < 20:
        return None
    current, previous = rows[index], rows[index - 1]
    close = current["Close"]
    volume_mean = math.fsum(row["Volume"] for row in rows[index - 19:index + 1]) / 20
    spread = current["High"] - current["Low"]
    return [close / rows[index - lag]["Close"] - 1 for lag in (1, 5, 20)] + [
        spread / close, current["Open"] / previous["Close"] - 1,
        close / current["Open"] - 1, current["Volume"] / volume_mean - 1 if volume_mean else 0,
        (close - current["Low"]) / spread if spread else 0.5]


def build_samples(rows: list[dict[str, Any]], horizon: int, spec: dict[str, Any]):
    if horizon not in spec["horizons_observed_rows"]:
        raise ValueError("Undeclared observed-row horizon")
    result = {split: [] for split in spec["splits"]}
    counts = {split: {"eligible_issue_rows": 0, "purged_unmatured_labels": 0, "embargoed_issue_rows": 0, "insufficient_history": 0} for split in result}
    for split, (start, end) in spec["splits"].items():
        indices = [index for index, row in enumerate(rows) if start <= row["Date"] < end]
        for ordinal, index in enumerate(indices):
            counts[split]["eligible_issue_rows"] += 1
            if split != "train" and ordinal < horizon:
                counts[split]["embargoed_issue_rows"] += 1
                continue
            if index + horizon >= len(rows) or rows[index + horizon]["Date"] >= end:
                counts[split]["purged_unmatured_labels"] += 1
                continue
            vector = features(rows, index)
            if vector is None:
                counts[split]["insufficient_history"] += 1
                continue
            current, target = rows[index], rows[index + horizon]
            result[split].append({"issue_date": current["Date"], "target_date": target["Date"],
                                  "horizon_observed_rows": horizon, "issue_price": current["Close"],
                                  "target_price": target["Close"], "actual_return": target["Close"] / current["Close"] - 1,
                                  "momentum_return": current["Close"] / rows[index - horizon]["Close"] - 1,
                                  "observed_ohlcv": {field: current[field] for field in spec["feature_fields"]},
                                  "feature_context_start_date": rows[index - 20]["Date"],
                                  "features": vector})
    return result, counts


def _sign(value):
    return (value > 0) - (value < 0)


def summarize(samples: list[dict[str, Any]], predictions: list[float]):
    by_day = defaultdict(list)
    for sample, predicted in zip(samples, predictions, strict=True):
        if not math.isfinite(predicted):
            raise ValueError("Nonfinite prediction")
        return_error = predicted - sample["actual_return"]
        price_error = sample["issue_price"] * (1 + predicted) - sample["target_price"]
        by_day[sample["issue_date"]].append({"return_abs": abs(return_error), "return_sq": return_error ** 2,
            "price_abs": abs(price_error), "price_sq": price_error ** 2,
            "direction_correct": int(_sign(predicted) == _sign(sample["actual_return"])),
            "nonzero_prediction": int(predicted != 0)})
    days = []
    for stamp, rows in sorted(by_day.items()):
        days.append({"issue_date": stamp, "stock_count": len(rows), **{key: math.fsum(row[key] for row in rows) / len(rows) for key in rows[0]}})
    if not days:
        return {"forecast_count": 0, "issue_day_count": 0, "metrics": None, "daily_metrics": []}
    average = {key: math.fsum(day[key] for day in days) / len(days) for key in days[0] if key not in {"issue_date", "stock_count"}}
    metrics = {"normalized_return_mae": average["return_abs"], "normalized_return_rmse": math.sqrt(average["return_sq"]),
               "price_mae": average["price_abs"], "price_rmse": math.sqrt(average["price_sq"]),
               "three_way_direction_accuracy": average["direction_correct"], "nonzero_prediction_fraction": average["nonzero_prediction"]}
    return {"forecast_count": len(samples), "issue_day_count": len(days), "metrics": metrics, "daily_metrics": days}


def fit_ridge(train: list[dict[str, Any]]):
    """One prespecified penalty; standardization and fit use matured train labels only."""
    import numpy as np
    if len(train) < len(FEATURES) + 1:
        raise ValueError("Insufficient train samples for the fixed ridge baseline")
    matrix = np.asarray([sample["features"] for sample in train], dtype=float)
    target = np.asarray([sample["actual_return"] for sample in train], dtype=float)
    mean, scale = matrix.mean(axis=0), matrix.std(axis=0)
    scale[scale == 0] = 1
    design = np.column_stack((np.ones(len(matrix)), (matrix - mean) / scale))
    penalty = np.eye(design.shape[1])
    penalty[0, 0] = 0
    coefficients = np.linalg.solve(design.T @ design + penalty, design.T @ target)
    return {"mean": mean.tolist(), "scale": scale.tolist(), "coefficients": coefficients.tolist(), "lambda": 1,
            "fit_sample_count": len(train), "fit_issue_end": max(sample["issue_date"] for sample in train),
            "fit_label_maturity_end": max(sample["target_date"] for sample in train), "feature_names": FEATURES}


def ridge_predict(sample, fit):
    return fit["coefficients"][0] + math.fsum(coefficient * (value - mean) / scale for coefficient, value, mean, scale in zip(fit["coefficients"][1:], sample["features"], fit["mean"], fit["scale"], strict=True))


def run_benchmark(dataset: Path, output: Path, *, ridge: bool = False):
    spec = protocol()
    manifest = json.loads((dataset / "source-manifest.json").read_text())
    if manifest["dataset_commit"] != spec["dataset_commit"] or manifest["protocol_sha256"] != canonical_digest(spec):
        raise ValueError("Dataset/protocol provenance mismatch")
    all_samples = {horizon: {split: [] for split in spec["splits"]} for horizon in spec["horizons_observed_rows"]}
    exclusions = {horizon: defaultdict(lambda: defaultdict(int)) for horizon in all_samples}
    for record in manifest["files"]:
        if not record["path"].startswith("price/raw/"):
            continue
        content = (dataset / record["path"]).read_bytes()
        if digest(content) != record["sha256"]:
            raise ValueError("Raw dataset source drift")
        rows, rejected = parse_prices(content)
        for horizon in all_samples:
            samples, counts = build_samples(rows, horizon, spec)
            for split, values in samples.items():
                all_samples[horizon][split].extend({**sample, "symbol": record["symbol"], "source_csv_sha256": record["sha256"]} for sample in values)
                for key, count in counts[split].items():
                    exclusions[horizon][split][key] += count
    models = list(spec["baseline_models"]) + ([spec["optional_model"]] if ridge else [])
    frozen_spec = {**spec, "executed_models": models, "ridge_lambda": 1 if ridge else None}
    frozen_protocol_sha256 = canonical_digest(frozen_spec)
    output.mkdir(parents=True, exist_ok=True)
    # Freeze provider-visible predictors separately from subsequently admissible truth.
    from system.lib.feed_envelope import build_envelope
    issue_groups = defaultdict(list)
    with (output / "predictor-rows.jsonl").open("w") as predictors, (output / "truth-rows.jsonl").open("w") as truths:
        for horizon, splits in all_samples.items():
            for split, samples in splits.items():
                for sample in sorted(samples, key=lambda row: (row["issue_date"], row["symbol"])):
                    sample_id = canonical_digest({"protocol_sha256": frozen_protocol_sha256, "symbol": sample["symbol"], "issue_date": sample["issue_date"], "horizon_observed_rows": horizon})
                    predictor = {"schema_version": "stocknet_frozen_predictor_v1", "sample_id": sample_id,
                        "symbol": sample["symbol"], "issue_date": sample["issue_date"], "split": split,
                        "horizon_observed_rows": horizon, "issue_price": sample["issue_price"],
                        "observed_ohlcv": sample["observed_ohlcv"], "feature_names": FEATURES, "feature_values": sample["features"],
                        "feature_context_start_date": sample["feature_context_start_date"], "source_csv_sha256": sample["source_csv_sha256"],
                        "protocol_sha256": frozen_protocol_sha256}
                    truth = {"schema_version": "stocknet_dated_truth_v1", "sample_id": sample_id,
                        "symbol": sample["symbol"], "issue_date": sample["issue_date"], "horizon_observed_rows": horizon,
                        "target_date": sample["target_date"], "target_price": sample["target_price"], "realized_return": sample["actual_return"],
                        "source_csv_sha256": sample["source_csv_sha256"], "status": "realized_historical_truth"}
                    predictors.write(json.dumps(predictor, sort_keys=True, separators=(",", ":")) + "\n")
                    truths.write(json.dumps(truth, sort_keys=True, separators=(",", ":")) + "\n")
                    issue_groups[(horizon, split, sample["issue_date"])].append(predictor)
    with (output / "issue-packets.jsonl").open("w") as stream:
        for (horizon, split, stamp), rows in sorted(issue_groups.items()):
            data = {"columns": ["Ticker", "Price", *spec["feature_fields"], *FEATURES],
                    "rows": [[row["symbol"], row["issue_price"], *[row["observed_ohlcv"][field] for field in spec["feature_fields"]], *row["feature_values"]] for row in rows]}
            context = build_envelope({"tool": "stocknet_price_only", "status": "success", "as_of_date": stamp,
                                     "availability_precision": "daily close assumption; intraday clock/vintage unverified",
                                     "protocol_sha256": frozen_protocol_sha256, "context_class": "subject_side_evidence"}, data)
            packet = {"schema_version": "stocknet_forward_issue_packet_v1", "issue_date": stamp, "split": split,
                      "horizon_observed_rows": horizon, "sample_ids": [row["sample_id"] for row in rows],
                      "context": context, "unavailable_feed_lanes": ["ETF", "MACRO", "NEWS", "POLYMARKET", "STOCKGRID"],
                      "truth_side_evidence_included": False}
            stream.write(json.dumps(packet, sort_keys=True, separators=(",", ":")) + "\n")
    results = []
    prediction_rows = []
    for horizon, splits in all_samples.items():
        fit = fit_ridge(splits["train"]) if ridge else None
        for model in models:
            for split, samples in splits.items():
                ordered = sorted(samples, key=lambda sample: (sample["issue_date"], sample["symbol"]))
                predicted = [0.0 if model == "no_change" else sample["momentum_return"] if model == "past_horizon_momentum" else ridge_predict(sample, fit) for sample in ordered]
                summary = summarize(ordered, predicted)
                issue_dates = sorted({sample["issue_date"] for sample in ordered})
                windows = []
                for start in range(0, len(issue_dates), spec["window_issue_days"]):
                    window_dates = set(issue_dates[start:start + spec["window_issue_days"]])
                    selection = [(sample, prediction) for sample, prediction in zip(ordered, predicted, strict=True) if sample["issue_date"] in window_dates]
                    window = summarize([item[0] for item in selection], [item[1] for item in selection])
                    windows.append({"window_id": f"{split}_h{horizon}_{start // spec['window_issue_days']:03d}",
                                    "issue_start": min(window_dates), "issue_end": max(window_dates),
                                    "target_maturity_end": max(item[0]["target_date"] for item in selection), **window})
                results.append({"model": model, "horizon_observed_rows": horizon, "split": split,
                                "frozen_train_fit": fit if model == spec["optional_model"] else None,
                                "exclusions": dict(exclusions[horizon][split]), "windows": windows, **summary})
                prediction_rows.extend({key: sample[key] for key in ["symbol", "issue_date", "target_date", "horizon_observed_rows", "issue_price", "target_price", "actual_return"]} | {"model": model, "split": split, "predicted_return": prediction, "predicted_price": sample["issue_price"] * (1 + prediction)} for sample, prediction in zip(ordered, predicted, strict=True))
    report = {"schema_version": "stocknet_price_only_benchmark_v1", "protocol": frozen_spec,
              "protocol_sha256": frozen_protocol_sha256, "source_manifest_sha256": digest((dataset / "source-manifest.json").read_bytes()),
              "dataset_commit": spec["dataset_commit"], "code_commit": spec["code_commit"], "stock_count": manifest["stock_count"],
              "trial_count": len(models) * len(all_samples), "split_evaluation_count": len(results),
              "holdout_used_for_fit_or_selection": False, "paper_score_reproduction": False,
              "comparison_boundary": spec["comparison_conditions"], "results": results}
    with (output / "predictions.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(prediction_rows[0]))
        writer.writeheader()
        writer.writerows(prediction_rows)
    report["predictions_sha256"] = digest((output / "predictions.csv").read_bytes())
    report["frozen_artifacts"] = {name: digest((output / name).read_bytes()) for name in ["predictor-rows.jsonl", "truth-rows.jsonl", "issue-packets.jsonl"]}
    (output / "results.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    (output / "frozen-protocol.json").write_text(json.dumps(frozen_spec, indent=2) + "\n")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    importer = commands.add_parser("import")
    importer.add_argument("--dataset-repo", type=Path, required=True)
    importer.add_argument("--code-repo", type=Path, required=True)
    importer.add_argument("--output", type=Path, default=ROOT / "work/datasets/stocknet")
    runner = commands.add_parser("run")
    runner.add_argument("--dataset", type=Path, default=ROOT / "work/datasets/stocknet")
    runner.add_argument("--output", type=Path, default=ROOT / "work/stocknet-results")
    runner.add_argument("--ridge", action="store_true", help="add a fixed penalty train-only OHLCV ridge baseline")
    args = parser.parse_args()
    result = import_dataset(args.dataset_repo, args.code_repo, args.output) if args.command == "import" else run_benchmark(args.dataset, args.output, ridge=args.ridge)
    print(json.dumps({key: result[key] for key in ("schema_version", "stock_count", "dataset_commit", "code_commit", "protocol_sha256") if key in result} | ({"trial_count": result["trial_count"]} if "trial_count" in result else {}), indent=2))


if __name__ == "__main__":
    main()
