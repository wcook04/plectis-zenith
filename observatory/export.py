"""Export allowlisted operational aggregates without executing the source repo.

Prediction receipts count model attempts; their claims count individual forecasts.
A separate immutable score supersedes a prediction's pending status. Missing or
invalid sources produce null counts, never plausible-looking zero totals.
"""
from __future__ import annotations

import argparse
import ast
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import re
import tempfile

SCHEMA = "observatory_operations_v1"
LANES = {
    "global_stock_feed": "stocks", "global_etf_feed": "etfs",
    "global_macro_feed": "macro", "global_news_feed": "news",
    "global_polymarket_feed": "prediction_markets",
    "global_stockgrid_feed": "stockgrid", "global_calculator_feed": "calculator",
}
FEED_STATUSES = {"success", "loaded", "failed", "error", "blocked", "skipped", "pending"}
MODEL_STATUSES = {"pending_truth", "model_failed", "attempt_started", "scored"}
PROVIDERS = {"openrouter", "google", "poolside", "openai", "anthropic", "meta-llama",
             "mistralai", "qwen", "deepseek", "nvidia", "arcee-ai", "stepfun",
             "z-ai", "x-ai", "moonshotai", "minimax", "allenai", "amazon", "cohere"}


class InvalidSource(ValueError):
    """Intentionally contains no source-derived error text."""


def _reject_constant(_value):
    raise InvalidSource()


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise InvalidSource()
        result[key] = value
    return result


def _read(path: Path) -> dict:
    # Do not follow source symlinks or accept non-object/NaN/duplicate-key JSON.
    if path.is_symlink():
        raise InvalidSource()
    try:
        data = json.loads(path.read_text(encoding="utf-8"), parse_constant=_reject_constant,
                          object_pairs_hook=_unique_object)
    except (OSError, ValueError, UnicodeError):
        raise InvalidSource() from None
    if not isinstance(data, dict):
        raise InvalidSource()
    return data


def _count(value):
    return value if type(value) is int and 0 <= value <= 10**12 else None


def _time(value):
    if not isinstance(value, str) or len(value) > 50:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            return None
        return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    except (ValueError, OverflowError):
        return None


def _model(value):
    if not isinstance(value, str) or len(value) > 160:
        return None
    if not re.fullmatch(r"[a-z0-9-]+/[a-zA-Z0-9][a-zA-Z0-9._:-]*", value):
        return None
    return value if value.split("/", 1)[0] in PROVIDERS else None


def _instant(value):
    # ISO strings with differing fractional precision do not sort by time.
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _cost(value):
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
        return None
    return value


def _clock(root: Path | None):
    result = {"timezone": None, "open": None, "close": None, "capture_window_minutes": None}
    if root is None:
        return result
    path = root / "system/lib/metabolism_market_clock.py"
    try:
        if path.is_symlink():
            return result
        tree = ast.parse(path.read_text(encoding="utf-8"))
        # Literal policy extraction, never import or execute private source code.
        for node in tree.body:
            name = None
            if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                name = node.targets[0].id
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                name = node.target.id
            if name == "DEFAULT_TIMEZONE":
                value = ast.literal_eval(node.value)
                if value == "America/New_York":
                    result["timezone"] = value
            if name == "DEFAULT_FIRE_POINTS":
                for point in ast.literal_eval(node.value):
                    if point.get("name") in ("open", "close") and re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", point.get("local_time", "")):
                        result[point["name"]] = point["local_time"]
            if isinstance(node, ast.FunctionDef) and node.name == "capture_window_receipt":
                for arg, default in zip(node.args.kwonlyargs, node.args.kw_defaults):
                    if arg.arg == "max_delay_seconds":
                        seconds = _count(ast.literal_eval(default))
                        if seconds is not None and seconds <= 86400:
                            result["capture_window_minutes"] = seconds / 60
    except (OSError, ValueError, TypeError, SyntaxError, KeyError, AttributeError):
        return {key: None for key in result}
    return result


def _collection(root: Path | None):
    result = {"last_run_id": None, "acquired_at": None, "readiness": "unavailable",
              "schedule_kind": "unknown", "lanes": [], "clock": _clock(root)}
    if root is None:
        return result
    runs = root / "state/runs"
    candidates = sorted((p for p in runs.glob("FEEDS_*") if p.is_dir() and not p.is_symlink()
                         and re.fullmatch(r"FEEDS_\d{8}_(?:open|close|validation|hour_\d{2}_\d{2})", p.name)), key=lambda p: p.name)
    if not candidates:
        return result
    # A same-day open sorts lexically after close. Use actual acquisition,
    # never publication time or the human run suffix, to rank those receipts.
    # Unknown acquisition wins conservatively: do not silently hide a newest
    # incomplete run behind an earlier successful bundle.
    latest_date = max(p.name[6:14] for p in candidates)
    same_day = [p for p in candidates if p.name[6:14] == latest_date]
    def acquisition_order(candidate):
        timestamps = []
        try:
            for node_id in LANES:
                path = candidate / "artifacts" / f"{node_id}.json"
                if not path.exists():
                    continue
                timestamp = _time(_read(path).get("metadata", {}).get("timestamp_iso"))
                if timestamp:
                    timestamps.append(timestamp)
            if not timestamps:
                ready = _read(candidate / "artifacts/feed_readiness_summary.json")
                timestamp = _time(ready.get("runtime_context", {}).get("started_at"))
                if timestamp:
                    timestamps.append(timestamp)
        except (InvalidSource, AttributeError, TypeError):
            timestamps = []
        latest = max(timestamps, key=_instant) if timestamps else None
        return (not bool(timestamps), _instant(latest) if latest else datetime.min.replace(tzinfo=timezone.utc), candidate.name)
    run = max(same_day, key=acquisition_order)
    result["last_run_id"] = run.name
    try:
        ready = _read(run / "artifacts/feed_readiness_summary.json")
        if ready.get("schema_version") != "feed_readiness_summary.v1" or ready.get("run_id") != run.name or type(ready.get("ready")) is not bool:
            raise InvalidSource()
        context = ready.get("runtime_context", {})
        if not isinstance(context, dict) or not isinstance(ready.get("feeds"), list):
            raise InvalidSource()
        schedule = context.get("schedule", {})
        point = schedule.get("fire_point") if isinstance(schedule, dict) else None
        result["schedule_kind"] = point if point in ("open", "close") else ("scheduled_other" if point else "manual_or_unspecified")
        feed_ids = {item.get("node_id") for item in ready["feeds"] if isinstance(item, dict)}
        times = []
        for node_id, name in LANES.items():
            if node_id not in feed_ids:
                continue
            artifact = _read(run / "artifacts" / f"{node_id}.json")
            metadata = artifact.get("metadata", {})
            if not isinstance(metadata, dict):
                raise InvalidSource()
            status = artifact.get("status")
            lane = {"name": name, "status": status if status in FEED_STATUSES else "unknown",
                    "rows": _count(metadata.get("items_count"))}
            # Price coverage is a row count, never a ticker/price export. Provider
            # fetch counts for news count sources, so must not be used as rows.
            data = artifact.get("data", {})
            if name in ("stocks", "etfs") and isinstance(data, dict) and isinstance(data.get("rows"), list):
                rows, columns = data["rows"], data.get("columns", [])
                prices = []
                for row in rows:
                    if isinstance(row, dict):
                        prices.append(row.get("Price"))
                    elif isinstance(row, list) and isinstance(columns, list) and "Price" in columns:
                        index = columns.index("Price")
                        prices.append(row[index] if index < len(row) else None)
                    else:
                        prices.append(None)
                valid = sum(type(p) in (int, float) and math.isfinite(p) and p > 0 for p in prices)
                lane.update(valid_price_rows=valid, missing_price_rows=len(rows) - valid)
            acquired = _time(metadata.get("timestamp_iso"))
            if acquired:
                times.append(acquired)
            result["lanes"].append(lane)
        result["readiness"] = "ready" if ready["ready"] else "not_ready"
        # Publication generated_at and logical as_of are never acquisition times.
        result["acquired_at"] = max(times, key=_instant) if times else _time(context.get("started_at"))
    except (InvalidSource, TypeError, ValueError, OSError, OverflowError):
        result.update(acquired_at=None, readiness="invalid_source", schedule_kind="unknown", lanes=[])
    return result


def _experiments(root: Path | None):
    result = {"source_status": "unavailable", "count_unit": "model_attempts", "pending_count": None,
              "scored_count": None, "failed_count": None, "forecast_count": None,
              "models": [], "first_truth_due_at": None}
    if root is None:
        return result
    base = root / "state/finance_eval/market_experiments"
    predictions = base / "predictions"
    if not predictions.is_dir() or predictions.is_symlink():
        return result
    try:
        receipts, scores = {}, {}
        for path in sorted(predictions.glob("*.json")):
            receipt = _read(path)
            identity = receipt.get("experiment_id")
            if receipt.get("schema") != "market_model_experiment_v1" or not isinstance(identity, str) or not re.fullmatch(r"[a-f0-9]{24}", identity) or identity in receipts or receipt.get("status") not in MODEL_STATUSES - {"scored"}:
                raise InvalidSource()
            if not isinstance(receipt.get("claims"), list):
                raise InvalidSource()
            if receipt["status"] == "pending_truth" and _time(receipt.get("event_end")) is None:
                raise InvalidSource()
            receipts[identity] = receipt
        score_dir = base / "scores"
        if score_dir.is_symlink():
            raise InvalidSource()
        for path in sorted(score_dir.glob("*.json")):
            score = _read(path)
            identity = score.get("experiment_id")
            if score.get("schema") != "market_experiment_score_v1" or identity not in receipts or identity in scores or score.get("status", "scored") != "scored" or not isinstance(score.get("evaluation"), dict) or _time(score.get("scored_at")) is None:
                raise InvalidSource()
            scores[identity] = score
        result.update(source_status="available", pending_count=0, scored_count=0, failed_count=0, forecast_count=0)
        due = []
        for identity in sorted(receipts):
            receipt = receipts[identity]
            status = "scored" if identity in scores else receipt["status"]
            packet = receipt.get("model_receipt", {})
            if not isinstance(packet, dict):
                raise InvalidSource()
            usage = packet.get("usage", {})
            if not isinstance(usage, dict):
                raise InvalidSource()
            model = {"requested": _model(receipt.get("requested_model")),
                     "actual": _model(packet.get("model")), "status": status,
                     "cost": _cost(usage.get("cost"))}
            result["models"].append(model)
            result["forecast_count"] += len(receipt["claims"])
            if status == "pending_truth":
                result["pending_count"] += 1
                due.append(_time(receipt["event_end"]))
            elif status == "scored":
                result["scored_count"] += 1
            elif status == "model_failed":
                result["failed_count"] += 1
        result["first_truth_due_at"] = min(due, key=_instant) if due else None
    except (InvalidSource, TypeError, ValueError, OSError, OverflowError):
        result = {**_experiments(None), "source_status": "invalid_source"}
    return result


def build_operations(source_root: Path | str | None = None, *, now: datetime | None = None) -> dict:
    """Build only the public allowlist; never copy source objects into output."""
    root = Path(source_root) if source_root is not None else None
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("Export time requires a timezone")
    return {"schema": SCHEMA, "generated_at": _time(now.isoformat()),
            "collection": _collection(root), "experiments": _experiments(root),
            "public_boundary": {"mode": "aggregate_research",
                "note": "Operational aggregates only. Paper forecasts are research, not trading advice or a tradable return backtest."}}


def write_operations(output: Path | str, payload: dict) -> None:
    """Publish a complete JSON file using an atomic same-directory replacement."""
    output = Path(output)
    body = json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n"
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=output.parent,
                                         prefix=".operations-", suffix=".tmp", delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(body)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, output)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, help="Optional private source checkout; never exported")
    parser.add_argument("--output", type=Path, default=Path("web/data/operations.json"))
    args = parser.parse_args()
    try:
        write_operations(args.output, build_operations(args.source_root))
    except (OSError, ValueError, TypeError):
        parser.exit(1, "Aggregate export could not be written.\n")
    print("Aggregate operations receipt exported.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
