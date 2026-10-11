"""Dated StockNet decision states and deterministic next-session trading ledger.

No inference or fitting. Historical Yahoo marks simulate fractional long/cash
orders; source adjustments and original availability are not authenticated.
Every fixed-universe allowance survives missing data, forecasts and fills.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
import math
from pathlib import Path
import json

from benchmarks.stocknet import canonical_digest, digest, parse_prices, protocol
from benchmarks.finmultitime import calendar_for

FEATURES = ["return_1", "return_5", "return_20", "intraday_mean_20",
            "realized_vol_20", "volume_ratio_20", "range_mean_20", "close_range_position"]
TASK = "stocknet_next_session_open_close_long_cash_v1"
STATE_KEYS = ("sample_id", "symbol", "issue_date", "target_date", "issue_at", "entry_at", "exit_at",
              "features", "feature_names", "history20", "preceding_close", "info_status", "source_ref", "source_sha256",
              "availability_basis", "history_lookback", "price_basis", "anchor_return", "forecast_units", "task")


def _read(path, maximum):
    with path.open("rb") as source:
        raw = source.read(maximum + 1)
    if len(raw) > maximum:
        raise ValueError("Source exceeds bounded read")
    return raw


def state_features(history, preceding_close):
    """Exactly 20 bars plus one preceding close, no extra future observations."""
    if len(history) != 20 or preceding_close <= 0:
        raise ValueError("Need twenty bars and preceding close")
    closes = [preceding_close, *[row["Close"] for row in history]]
    returns = [closes[i + 1] / closes[i] - 1 for i in range(20)]
    intraday = [row["Close"] / row["Open"] - 1 for row in history]
    mean = math.fsum(returns) / 20
    volume_mean = math.fsum(row["Volume"] for row in history) / 20
    current = history[-1]
    spread = current["High"] - current["Low"]
    return [closes[-1] / closes[-1 - lag] - 1 for lag in (1, 5, 20)] + [
        math.fsum(intraday) / 20,
        math.sqrt(math.fsum((r - mean) ** 2 for r in returns) / 20),
        current["Volume"] / volume_mean if volume_mean else 0.0,
        math.fsum((row["High"] - row["Low"]) / row["Close"] for row in history) / 20,
        (current["Close"] - current["Low"]) / spread if spread else 0.5]


def public_projection(sample):
    """Positive forward allowlist; excludes realized returns and execution prices."""
    projected = {key: sample[key] for key in STATE_KEYS}
    if "context_evidence" in sample:
        projected["context_evidence"] = sample["context_evidence"]
    return json.loads(json.dumps(projected, allow_nan=False))


def build_dataset(datasetdir, splits, symbols=None):
    """Build all scheduled date/asset rows, separating forward state from truth.

    Splits are half-open issue intervals; exit date must be strictly inside the
    same interval. Daily bars are assumed available one minute after XNYS close.
    Missing history and missing future price rows are retained, not sampled away.
    """
    directory = Path(datasetdir).resolve()
    manifest_raw = _read(directory / "source-manifest.json", 1024 * 1024)
    manifest = json.loads(manifest_raw)
    if manifest.get("dataset_commit") != protocol()["dataset_commit"]:
        raise ValueError("StockNet source pin mismatch")
    records = [r for r in manifest["files"] if r.get("symbol")]
    references = {r["symbol"]: r for r in records}
    if len(references) != len(records) or len(records) != 88:
        raise ValueError("Expected pinned 88-stock universe with unique source refs")
    universe = sorted(references) if symbols is None else sorted(symbols)
    if not universe or len(universe) != len(set(universe)) or any(s not in references for s in universe):
        raise ValueError("Invalid fixed universe")
    intervals = sorted((date.fromisoformat(a), date.fromisoformat(b), name) for name, (a, b) in splits.items())
    if not intervals or any(a >= b for a, b, _ in intervals) or any(intervals[i][1] > intervals[i + 1][0] for i in range(len(intervals) - 1)):
        raise ValueError("Split intervals must be nonempty and disjoint")
    prices, rejected = {}, {}
    for symbol in universe:
        ref = references[symbol]
        path = (directory / ref["path"]).resolve()
        if not path.is_relative_to(directory):
            raise ValueError("Price source escapes dataset")
        raw = _read(path, 4 * 1024 * 1024)
        if digest(raw) != ref["sha256"]:
            raise ValueError("Price source hash mismatch")
        rows, rejected[symbol] = parse_prices(raw)
        prices[symbol] = {r["Date"]: r for r in rows}
    earliest = min(date.fromisoformat(min(rows)) for rows in prices.values())
    cal = calendar_for(str(min(earliest, intervals[0][0]) - timedelta(days=60)), str(intervals[-1][1] + timedelta(days=15)))
    sessions = [session.date().isoformat() for session in cal.sessions]
    output, coverage = {}, {}
    for start, end, name in intervals:
        samples = []
        counts = defaultdict(int)
        for i, stamp in enumerate(sessions[:-1]):
            target = sessions[i + 1]
            if not start.isoformat() <= stamp < end.isoformat() or target >= end.isoformat():
                continue
            issue_at = cal.session_close(stamp).to_pydatetime() + timedelta(minutes=1)
            entry_at = cal.session_open(target).to_pydatetime()
            exit_at = cal.session_close(target).to_pydatetime()
            if not issue_at < entry_at < exit_at:
                raise ValueError("Issue clock must precede executable interval")
            for symbol in universe:
                lookup, ref = prices[symbol], references[symbol]
                history_dates = sessions[i - 19:i + 1] if i >= 19 else []
                previous = lookup.get(sessions[i - 20]) if i >= 20 else None
                history = [lookup.get(d) for d in history_dates]
                available = len(history) == 20 and all(history) and previous is not None
                bars = [{key: row[key] for key in ("Date", "Open", "High", "Low", "Close", "Volume")} for row in history] if available else []
                features = state_features(bars, previous["Close"]) if available else None
                truth = lookup.get(target)
                sample = {"task": TASK, "symbol": symbol, "split": name, "issue_date": stamp, "target_date": target,
                          "issue_at": issue_at.isoformat(), "entry_at": entry_at.isoformat(), "exit_at": exit_at.isoformat(),
                          "features": features, "feature_names": FEATURES[:], "history20": bars,
                          "preceding_close": previous["Close"] if available else None,
                          "history_lookback": "20 contiguous XNYS OHLCV sessions plus preceding-session Close for return20",
                          "info_status": "available" if available else "missing_history",
                          "availability_basis": "historical_daily_bar_assumed_available_at_session_close_plus_1_minute; original_ingest_unverified",
                          "source_ref": ref["path"], "source_sha256": ref["sha256"],
                          "price_basis": "StockNet Yahoo Open/Close as supplied; exclude Adj Close; original adjustment vintage unverified",
                          "forecast_units": "conditional_expected_arithmetic_next_session_open_to_close_return",
                          "anchor_return": features[3] if available else None,
                          "truth_open": truth["Open"] if truth else None, "truth_close": truth["Close"] if truth else None,
                          "actual_return": truth["Close"] / truth["Open"] - 1 if truth else None}
                sample["sample_id"] = canonical_digest({k: v for k, v in sample.items() if k not in {"truth_open", "truth_close", "actual_return", "history20", "preceding_close"}})
                samples.append(sample)
                counts["scheduled_allowances"] += 1
                counts["available_information"] += bool(available)
                counts["missing_truth"] += truth is None
            counts["issue_dates"] += 1
        output[name], coverage[name] = samples, dict(counts)
    return {"task": TASK, "feature_names": FEATURES[:], "symbols": universe, "splits": output,
            "coverage": coverage, "rejected_source_rows": rejected, "source_manifest_sha256": digest(manifest_raw),
            "source_csv_sha256": {s: references[s]["sha256"] for s in universe},
            "dataset_commit": manifest["dataset_commit"], "rights_boundary": manifest["rights_boundary"]}


def evaluate_predictions(samples, predictions, *, capital=1.0, fee_bps=1.0, slippage_bps=4.0):
    """Fully funded equal long/cash allowances; zero cash interest, daily liquidation.

    Scalar compiled forecasts are precommitted at issue. Timestamped accepted
    forecasts must arrive strictly before opening entry. Missing/failed forecasts
    stay cash. A requested trade with an unknown fill makes the daily P&L unknown.
    Gross P&L uses actual quantity and unslipped marks; fees and slippage reconcile.
    """
    if any(isinstance(x, bool) or not math.isfinite(x) for x in (capital, fee_bps, slippage_bps)) or capital <= 0 or not 0 <= fee_bps < 10000 or not 0 <= slippage_bps < 10000:
        raise ValueError("Invalid capital or costs")
    if not samples or len({s["sample_id"] for s in samples}) != len(samples):
        raise ValueError("Samples must be nonempty with unique identities")
    symbols = sorted({s["symbol"] for s in samples})
    grouped = defaultdict(list)
    for sample in samples:
        grouped[sample["issue_date"]].append(sample)
    fee, slip = fee_bps / 10000, slippage_bps / 10000
    threshold = (1 + fee) * (1 + slip) / ((1 - fee) * (1 - slip)) - 1

    def valid_price(x):
        return not isinstance(x, bool) and isinstance(x, (int, float)) and math.isfinite(x) and x > 0

    daily, asset_rows = [], []
    for stamp, group in sorted(grouped.items()):
        if sorted(s["symbol"] for s in group) != symbols or len({s["target_date"] for s in group}) != 1:
            raise ValueError("Daily fixed-universe support differs")
        ledger = []
        for sample in sorted(group, key=lambda s: s["symbol"]):
            allowance = capital / len(symbols)
            forecast, status = predictions.get(sample["sample_id"]), "accepted"
            if isinstance(forecast, dict):
                status = forecast.get("status", "invalid")
                issued = forecast.get("issued_at")
                if issued is not None:
                    try:
                        received = datetime.fromisoformat(issued)
                        if received.tzinfo is None or received >= datetime.fromisoformat(sample["entry_at"]):
                            status = "late"
                    except (ValueError, TypeError):
                        status = "invalid_timestamp"
                forecast = forecast.get("expected_return")
            if isinstance(forecast, bool) or not isinstance(forecast, (int, float)) or not math.isfinite(forecast):
                status, forecast = "missing_or_invalid_forecast", None
            if sample["info_status"] != "available":
                status = "missing_information"
            go_long = status == "accepted" and forecast > threshold
            opening, closing = sample["truth_open"], sample["truth_close"]
            row = {"sample_id": sample["sample_id"], "symbol": sample["symbol"], "issue_date": stamp,
                   "target_date": sample["target_date"], "issue_at": sample["issue_at"],
                   "entry_at": sample["entry_at"], "exit_at": sample["exit_at"],
                   "predicted_return": forecast, "forecast_status": status, "decision": "long" if go_long else "cash",
                   "actual_return": closing / opening - 1 if valid_price(opening) and valid_price(closing) else None,
                   "source_ref": sample["source_ref"],
                   "source_sha256": sample["source_sha256"], "price_basis": sample["price_basis"],
                   "threshold_return": threshold, "allowance": allowance, "quantity": 0.0,
                   "entry_mark": sample["truth_open"], "exit_mark": sample["truth_close"],
                   "entry_fill": None, "exit_fill": None, "entry_fee": 0.0, "exit_fee": 0.0,
                   "entry_slippage_cost": 0.0, "exit_slippage_cost": 0.0,
                   "gross_return": 0.0, "cost_return": 0.0, "net_return": 0.0,
                   "ending_cash": allowance, "operational_status": "cash"}
            if go_long:
                if not valid_price(opening):
                    row.update(operational_status="unknown_fill", quantity=None, gross_return=None, cost_return=None, net_return=None, ending_cash=None)
                else:
                    entry = opening * (1 + slip)
                    quantity = allowance / (entry * (1 + fee))
                    entry_fee, entry_slip = quantity * entry * fee, quantity * (entry - opening)
                    row.update(quantity=quantity, entry_fill=entry, entry_fee=entry_fee, entry_slippage_cost=entry_slip)
                    if not valid_price(closing):
                        row.update(operational_status="unknown_fill", exit_fee=None, exit_slippage_cost=None,
                                   gross_return=None, cost_return=None, net_return=None, ending_cash=None)
                    else:
                        exit = closing * (1 - slip)
                        exit_fee, exit_slip = quantity * exit * fee, quantity * (closing - exit)
                        end = quantity * exit - exit_fee
                        row.update(exit_fill=exit, exit_fee=exit_fee, exit_slippage_cost=exit_slip,
                                   gross_return=quantity * (closing - opening) / allowance,
                                   cost_return=(entry_fee + exit_fee + entry_slip + exit_slip) / allowance,
                                   net_return=end / allowance - 1, ending_cash=end, operational_status="filled")
            ledger.append(row)
        unknown = any(r["operational_status"] == "unknown_fill" for r in ledger)
        result = {"issue_date": stamp, "target_date": group[0]["target_date"], "status": "unknown_fill" if unknown else "complete",
                  "starting_capital": capital, "ending_capital": None if unknown else math.fsum(r["ending_cash"] for r in ledger),
                  "gross_return": None if unknown else math.fsum(r["gross_return"] for r in ledger) / len(symbols),
                  "cost_return": None if unknown else math.fsum(r["cost_return"] for r in ledger) / len(symbols),
                  "net_return": None if unknown else math.fsum(r["net_return"] for r in ledger) / len(symbols),
                  "invested_allowances": sum(r["decision"] == "long" for r in ledger),
                  "cash_allowances": sum(r["decision"] == "cash" for r in ledger),
                  "forecast_failure_count": sum(r["forecast_status"] != "accepted" for r in ledger),
                  "unknown_allowances": sum(r["operational_status"] == "unknown_fill" for r in ledger),
                  "total_fees": None if unknown else math.fsum(r["entry_fee"] + r["exit_fee"] for r in ledger),
                  "total_slippage_cost": None if unknown else math.fsum(r["entry_slippage_cost"] + r["exit_slippage_cost"] for r in ledger)}
        daily.append(result)
        asset_rows.extend(ledger)
    complete = all(d["status"] == "complete" for d in daily)
    return {"task": TASK, "daily": daily, "asset_rows": asset_rows,
            "summary": {"status": "complete" if complete else "unknown_fill", "issue_dates": len(daily),
                        "asset_allowances": len(asset_rows), "mean_net_return": math.fsum(d["net_return"] for d in daily) / len(daily) if complete else None,
                        "compounded_return": math.prod(1 + d["net_return"] for d in daily) - 1 if complete else None,
                        "capital_per_simulated_day": capital, "cash_return": 0.0, "fee_bps_per_side": fee_bps,
                        "slippage_bps_per_side": slippage_bps, "break_even_return": threshold}}
