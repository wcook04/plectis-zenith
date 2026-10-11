#!/usr/bin/env python3
"""
[PURPOSE]
- Teleology: Summarize finance evaluation evidence by maturity, common support,
  truth-session semantics, and effective event-window independence before any
  model-selection result is interpreted as a mutation signal.
- Mechanism: Consume existing historical replay, variant-gate, and
  model-selection receipts; compute horizon-level counts plus conservative
  de-duplicated sensitivity over the family loss matrix.
- Navigation-group: market_intelligence
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from system.lib import feed_envelope
from tools.finance import variant_registry


TOOL_NAME = "finance_effective_evidence"
DATA_SCHEMA_VERSION = "finance_effective_evidence_receipt_v0"
EXPANSION_PLAN_SCHEMA_VERSION = "finance_effective_evidence_expansion_plan_v0"
DEFAULT_OUTPUT = Path("state/finance_eval/views/finance_effective_evidence.json")
DEFAULT_MINIMUM_INFERENCE_SAMPLE = 30
DEFAULT_PLANNING_HORIZONS = ("5d", "10d", "20d")
REQUIRED_SUBJECT_FEEDS = (
    "global_stock_feed.json",
    "global_macro_feed.json",
    "global_etf_feed.json",
    "global_calculator_feed.json",
)
TRUTH_TAPE_GAP_REASONS = {
    "missing_event_start_price",
    "missing_event_end_price",
    "missing_event_start_and_end_price",
}


def _as_text(value: Any) -> str:
    return str(value or "").strip()


def _as_float(value: Any) -> Optional[float]:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _as_int(value: Any) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    return 0


def _read_json(path: Path) -> Dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object at {path}")
    return payload


def _data(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    data = payload.get("data")
    return data if isinstance(data, Mapping) else payload


def _receipt(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    data = _data(payload)
    receipt = data.get("receipt")
    return receipt if isinstance(receipt, Mapping) else data


def _parse_dt(value: Any) -> Optional[datetime]:
    text = _as_text(value)
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def _date_key(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).date().isoformat()


def _horizon_days(horizon: str) -> Optional[int]:
    text = _as_text(horizon).lower()
    if not text.endswith("d"):
        return None
    try:
        days = int(text[:-1])
    except ValueError:
        return None
    return days if days > 0 else None


def _single_horizon(scorecards: Sequence[Mapping[str, Any]]) -> str:
    horizons = {
        _as_text(((card.get("event_contract") or {}) if isinstance(card.get("event_contract"), Mapping) else {}).get("horizon"))
        for card in scorecards
    }
    horizons.discard("")
    return next(iter(horizons)) if len(horizons) == 1 else "combined"


def _status_counts(scorecards: Sequence[Mapping[str, Any]]) -> Dict[str, int]:
    return dict(sorted(Counter(_as_text(card.get("status") or "unknown") for card in scorecards).items()))


def _mature_count(scorecards: Sequence[Mapping[str, Any]]) -> int:
    immature = {"pending_truth", "not_admissible_missing_event_binding"}
    return sum(1 for card in scorecards if _as_text(card.get("status")) not in immature)


def _experiment_summary(path: Path, payload: Mapping[str, Any]) -> Dict[str, Any]:
    data = _data(payload)
    ledger = data.get("experiment_ledger") if isinstance(data.get("experiment_ledger"), Mapping) else {}
    scorecards = [card for card in data.get("scorecards", []) if isinstance(card, Mapping)]
    horizon = _single_horizon(scorecards)
    claim_counts = ledger.get("claim_counts") if isinstance(ledger.get("claim_counts"), Mapping) else {}
    calibration = data.get("calibration_summary") if isinstance(data.get("calibration_summary"), Mapping) else {}
    return {
        "path": str(path),
        "experiment_id": ledger.get("experiment_id"),
        "variant_id": ledger.get("generator_variant_id"),
        "horizon": horizon,
        "raw_scorecard_count": len(scorecards),
        "mature_count": _mature_count(scorecards),
        "resolved_count": claim_counts.get("resolved", calibration.get("resolved_count", 0)),
        "pending_count": claim_counts.get("pending", calibration.get("pending_count", 0)),
        "status_counts": _status_counts(scorecards),
        "claim_counts": dict(claim_counts),
        "mean_brier": calibration.get("mean_brier"),
        "price_match_status_counts": dict(data.get("price_match_status_counts") or {}),
        "price_match_reason_counts": dict(data.get("price_match_reason_counts") or {}),
    }


def _model_selection_horizon(receipt: Mapping[str, Any]) -> str:
    rows = (((receipt.get("family_loss_matrix") or {}) if isinstance(receipt.get("family_loss_matrix"), Mapping) else {}).get("rows") or [])
    horizons = {_as_text(row.get("horizon")) for row in rows if isinstance(row, Mapping)}
    horizons.discard("")
    return next(iter(horizons)) if len(horizons) == 1 else "combined"


def _event_window_key(row: Mapping[str, Any]) -> str:
    return "|".join(
        [
            _as_text(row.get("subject_as_of")),
            _as_text(row.get("horizon")),
            _as_text(row.get("event_start")),
            _as_text(row.get("event_end")),
        ]
    )


def _window_groups(rows: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    groups: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        key = _event_window_key(row)
        if key not in groups:
            groups[key] = {
                "key": key,
                "subject_as_of": _as_text(row.get("subject_as_of")),
                "horizon": _as_text(row.get("horizon")),
                "event_start": _as_text(row.get("event_start")),
                "event_end": _as_text(row.get("event_end")),
                "row_count": 0,
                "loss_sums": defaultdict(float),
                "loss_counts": defaultdict(int),
            }
        group = groups[key]
        group["row_count"] += 1
        losses = row.get("losses")
        if isinstance(losses, Mapping):
            for variant_id, value in losses.items():
                loss = _as_float(value)
                if loss is None:
                    continue
                group["loss_sums"][_as_text(variant_id)] += loss
                group["loss_counts"][_as_text(variant_id)] += 1

    normalized: List[Dict[str, Any]] = []
    for group in groups.values():
        averaged_losses = {
            variant_id: round(total / max(group["loss_counts"][variant_id], 1), 10)
            for variant_id, total in group["loss_sums"].items()
        }
        normalized.append(
            {
                "key": group["key"],
                "subject_as_of": group["subject_as_of"],
                "horizon": group["horizon"],
                "event_start": group["event_start"],
                "event_end": group["event_end"],
                "row_count": group["row_count"],
                "losses": averaged_losses,
            }
        )
    normalized.sort(key=lambda group: (group["event_end"], group["event_start"], group["key"]))
    return normalized


def _greedy_non_overlapping(groups: Sequence[Mapping[str, Any]]) -> List[Mapping[str, Any]]:
    selected: List[Mapping[str, Any]] = []
    selected_intervals: List[Tuple[datetime, datetime]] = []
    for group in groups:
        start = _parse_dt(group.get("event_start"))
        end = _parse_dt(group.get("event_end"))
        if start is None or end is None:
            continue
        overlaps = any(start < other_end and other_start < end for other_start, other_end in selected_intervals)
        if overlaps:
            continue
        selected.append(group)
        selected_intervals.append((start, end))
    return selected


def _group_interval(group: Mapping[str, Any]) -> Optional[Tuple[datetime, datetime]]:
    start = _parse_dt(group.get("event_start"))
    end = _parse_dt(group.get("event_end"))
    if start is None or end is None:
        return None
    return (start, end)


def _overlaps_any(start: datetime, end: datetime, intervals: Sequence[Tuple[datetime, datetime]]) -> bool:
    return any(start < other_end and other_start < end for other_start, other_end in intervals)


def _mean_losses(groups: Sequence[Mapping[str, Any]]) -> Dict[str, float]:
    sums: Dict[str, float] = defaultdict(float)
    counts: Dict[str, int] = defaultdict(int)
    for group in groups:
        losses = group.get("losses")
        if not isinstance(losses, Mapping):
            continue
        for variant_id, value in losses.items():
            loss = _as_float(value)
            if loss is None:
                continue
            sums[_as_text(variant_id)] += loss
            counts[_as_text(variant_id)] += 1
    return {variant_id: round(total / max(counts[variant_id], 1), 10) for variant_id, total in sorted(sums.items())}


def _dedupe_sensitivity(
    rows: Sequence[Mapping[str, Any]],
    *,
    baseline_variant_id: str,
    minimum_sample: int,
) -> Dict[str, Any]:
    groups = _window_groups(rows)
    selected = _greedy_non_overlapping(groups)
    means = _mean_losses(selected)
    baseline_loss = means.get(baseline_variant_id)
    deltas = {
        variant_id: round(loss - baseline_loss, 10)
        for variant_id, loss in means.items()
        if baseline_loss is not None and variant_id != baseline_variant_id
    }
    best_variant = min(deltas, key=deltas.get) if deltas else None
    return {
        "dedupe_rule": "average_rows_by_subject_horizon_event_window_then_greedy_non_overlapping_windows",
        "unique_event_window_count": len(groups),
        "selected_non_overlapping_window_count": len(selected),
        "selected_row_count_before_window_averaging": sum(_as_int(group.get("row_count")) for group in selected),
        "selected_window_keys": [group["key"] for group in selected],
        "mean_losses": means,
        "mean_deltas_vs_baseline": deltas,
        "best_mean_delta_variant_id": best_variant,
        "best_mean_delta": deltas.get(best_variant) if best_variant else None,
        "inference_status": "computed" if len(selected) >= minimum_sample else "sample_gated",
        "sample_gate_reason": None if len(selected) >= minimum_sample else "deduplicated_window_count_below_minimum_sample",
        "minimum_sample": minimum_sample,
        "effective_sample_deficit": max(minimum_sample - len(selected), 0),
    }


def _effective_independence(receipt: Mapping[str, Any]) -> Dict[str, Any]:
    matrix = receipt.get("family_loss_matrix") if isinstance(receipt.get("family_loss_matrix"), Mapping) else {}
    rows = [row for row in matrix.get("rows", []) if isinstance(row, Mapping)]
    coverage = matrix.get("coverage") if isinstance(matrix.get("coverage"), Mapping) else {}
    dependence = matrix.get("dependence_diagnostics") if isinstance(matrix.get("dependence_diagnostics"), Mapping) else {}
    subject_as_of_values = {_as_text(row.get("subject_as_of")) for row in rows}
    subject_dates = {value[:10] for value in subject_as_of_values if value}
    overlap_count = _as_int(dependence.get("event_window_overlap_count"))
    pair_count = len(rows) * (len(rows) - 1) // 2
    minimum_sample = _as_int(((receipt.get("bootstrap") or {}) if isinstance(receipt.get("bootstrap"), Mapping) else {}).get("minimum_sample")) or DEFAULT_MINIMUM_INFERENCE_SAMPLE
    return {
        "raw_shared_event_count": coverage.get("shared_event_count", len(rows)),
        "event_window_overlap_count": overlap_count,
        "event_window_overlap_density": round(overlap_count / pair_count, 6) if pair_count else 0.0,
        "unique_subject_as_of_count": len(subject_as_of_values),
        "unique_subject_date_count": len(subject_dates),
        "unique_event_window_count": len(_window_groups(rows)),
        "recommended_block_length": dependence.get("recommended_block_length"),
        "horizon_days_for_dependence": dependence.get("horizon_days"),
        "deduplicated_sensitivity": _dedupe_sensitivity(
            rows,
            baseline_variant_id=_as_text(receipt.get("baseline_variant_id") or variant_registry.BASELINE_VARIANT_ID),
            minimum_sample=minimum_sample,
        ),
    }


def _price_dates(price_history_payload: Optional[Mapping[str, Any]], benchmark: str) -> List[str]:
    if not price_history_payload:
        return []
    data = _data(price_history_payload)
    prices = data.get("prices") if isinstance(data.get("prices"), Mapping) else {}
    series = prices.get(benchmark) if isinstance(prices.get(benchmark), Mapping) else {}
    return sorted(str(key) for key in series.keys())


def _market_session_reason(date_text: str) -> str:
    try:
        weekday = datetime.fromisoformat(date_text).weekday()
    except ValueError:
        return "session_unknown"
    return "weekend" if weekday >= 5 else "expected_trading_day"


def _match_price_date(
    requested_date: str,
    available_dates: Sequence[str],
    *,
    max_roll_days: int,
) -> Dict[str, Any]:
    available = set(available_dates)
    if requested_date in available:
        return {
            "status": "covered",
            "requested_date": requested_date,
            "actual_date": requested_date,
            "roll_days": 0,
            "match_status": "exact",
            "match_reason": "exact_trading_session",
            "requested_session_reason": _market_session_reason(requested_date),
        }
    try:
        requested = datetime.fromisoformat(requested_date).date()
    except ValueError:
        return {
            "status": "missing",
            "requested_date": requested_date,
            "actual_date": None,
            "roll_days": None,
            "match_status": "missing",
            "match_reason": "invalid_requested_date",
            "requested_session_reason": "invalid_requested_date",
        }
    for days in range(1, max_roll_days + 1):
        candidate = (requested + timedelta(days=days)).isoformat()
        if candidate in available:
            session_reason = _market_session_reason(requested_date)
            return {
                "status": "covered",
                "requested_date": requested_date,
                "actual_date": candidate,
                "roll_days": days,
                "match_status": "rolled_forward",
                "match_reason": (
                    "rolled_forward_market_closed"
                    if session_reason == "weekend"
                    else "rolled_forward_provider_missing"
                ),
                "requested_session_reason": session_reason,
            }
    return {
        "status": "missing",
        "requested_date": requested_date,
        "actual_date": None,
        "roll_days": None,
        "match_status": "missing",
        "match_reason": "refused_outside_roll_window",
        "requested_session_reason": _market_session_reason(requested_date),
    }


def _candidate_run_dirs(paths: Sequence[Path], roots: Sequence[Path]) -> List[Path]:
    candidates = {path for path in paths}
    for root in roots:
        if not root.exists():
            continue
        for child in root.iterdir():
            if (child / "artifacts" / "global_calculator_feed.json").exists():
                candidates.add(child)
    return sorted(candidates, key=lambda path: path.name)


def _artifact_metadata(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    metadata = payload.get("metadata")
    return metadata if isinstance(metadata, Mapping) else {}


def _artifact_is_usable(path: Path) -> bool:
    if not path.exists():
        return False
    try:
        payload = _read_json(path)
    except ValueError:
        return False
    metadata = _artifact_metadata(payload)
    status = _as_text(metadata.get("status") or payload.get("status")).lower()
    # Legacy fixtures and older success artifacts may omit status entirely.
    return status != "failure"


def _subject_as_of_resolution_from_run_dir(run_dir: Path) -> Dict[str, Any]:
    context_path = run_dir / "runtime_context.json"
    if context_path.exists():
        try:
            context = _read_json(context_path)
        except ValueError:
            context = {}
        for key in ("as_of", "original_as_of", "target_time_iso"):
            parsed = _parse_dt(context.get(key))
            if parsed is not None:
                return {
                    "status": "resolved",
                    "subject_as_of": parsed,
                    "source": f"runtime_context.json:{key}",
                }
    calculator_path = run_dir / "artifacts" / "global_calculator_feed.json"
    if _artifact_is_usable(calculator_path):
        try:
            artifact = _read_json(calculator_path)
        except ValueError:
            artifact = {}
        for key in ("as_of", "timestamp"):
            metadata = _artifact_metadata(artifact)
            parsed = _parse_dt(metadata.get(key) if metadata else artifact.get(key))
            if parsed is not None:
                return {
                    "status": "resolved",
                    "subject_as_of": parsed,
                    "source": f"artifacts/global_calculator_feed.json:metadata.{key}",
                }
    artifacts = run_dir / "artifacts"
    for feed_name in REQUIRED_SUBJECT_FEEDS:
        if feed_name == "global_calculator_feed.json":
            continue
        feed_path = artifacts / feed_name
        if not _artifact_is_usable(feed_path):
            continue
        try:
            artifact = _read_json(feed_path)
        except ValueError:
            continue
        metadata = _artifact_metadata(artifact)
        for key in ("as_of", "original_as_of", "target_time_iso"):
            parsed = _parse_dt(metadata.get(key))
            if parsed is not None:
                return {
                    "status": "recovered_from_feed_metadata",
                    "subject_as_of": parsed,
                    "source": f"artifacts/{feed_name}:metadata.{key}",
                }
    return {
        "status": "missing",
        "subject_as_of": None,
        "source": None,
    }


def _subject_as_of_from_run_dir(run_dir: Path) -> Optional[datetime]:
    resolved = _subject_as_of_resolution_from_run_dir(run_dir)
    value = resolved.get("subject_as_of")
    return value if isinstance(value, datetime) else None


def _feed_presence(run_dir: Path) -> Dict[str, bool]:
    artifacts = run_dir / "artifacts"
    return {name: _artifact_is_usable(artifacts / name) for name in REQUIRED_SUBJECT_FEEDS}


def _truth_coverage(
    *,
    event_start: datetime,
    event_end: datetime,
    benchmark_dates: Sequence[str],
    max_roll_days: int,
) -> Dict[str, Any]:
    start = _match_price_date(_date_key(event_start), benchmark_dates, max_roll_days=max_roll_days)
    end = _match_price_date(_date_key(event_end), benchmark_dates, max_roll_days=max_roll_days)
    covered = start["status"] == "covered" and end["status"] == "covered"
    if covered:
        reason = "truth_tape_covers_event_boundaries"
    elif start["status"] != "covered" and end["status"] != "covered":
        reason = "missing_event_start_and_end_price"
    elif start["status"] != "covered":
        reason = "missing_event_start_price"
    else:
        reason = "missing_event_end_price"
    return {
        "status": "covered" if covered else "missing",
        "reason": reason,
        "event_start_price_match": start,
        "event_end_price_match": end,
    }


def _current_window_state(model_selection_payloads: Sequence[Tuple[Path, Mapping[str, Any]]]) -> Dict[str, Any]:
    combined_receipt: Optional[Mapping[str, Any]] = None
    fallback_receipt: Optional[Mapping[str, Any]] = None
    for _path, payload in model_selection_payloads:
        receipt = _receipt(payload)
        if not isinstance(receipt, Mapping):
            continue
        fallback_receipt = receipt
        if _model_selection_horizon(receipt) == "combined":
            combined_receipt = receipt
            break
    receipt = combined_receipt or fallback_receipt or {}
    matrix = receipt.get("family_loss_matrix") if isinstance(receipt.get("family_loss_matrix"), Mapping) else {}
    rows = [row for row in matrix.get("rows", []) if isinstance(row, Mapping)]
    groups = _window_groups(rows)
    selected = _greedy_non_overlapping(groups)
    selected_intervals = [interval for group in selected if (interval := _group_interval(group)) is not None]
    return {
        "raw_window_keys": {_event_window_key(row) for row in rows},
        "selected_window_keys": [group["key"] for group in selected],
        "selected_intervals": selected_intervals,
        "current_effective_count": len(selected),
        "current_raw_window_count": len(groups),
    }


def _planned_candidate_windows(
    *,
    run_dir: Path,
    subject_as_of: datetime,
    horizons: Sequence[str],
    truth_as_of: datetime,
    benchmark_dates: Sequence[str],
    max_roll_days: int,
    current_raw_window_keys: set[str],
    current_effective_intervals: Sequence[Tuple[datetime, datetime]],
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for horizon in horizons:
        days = _horizon_days(horizon)
        if days is None:
            rows.append(
                {
                    "horizon": horizon,
                    "status": "do_not_run",
                    "reason": "invalid_horizon",
                    "marginal_effective_candidate": False,
                }
            )
            continue
        event_start = subject_as_of
        event_end = subject_as_of + timedelta(days=days)
        key = "|".join([_iso(subject_as_of), horizon, _iso(event_start), _iso(event_end)])
        maturity_status = "mature" if event_end <= truth_as_of else "pending_maturity"
        coverage = _truth_coverage(
            event_start=event_start,
            event_end=event_end,
            benchmark_dates=benchmark_dates,
            max_roll_days=max_roll_days,
        )
        overlaps_current = _overlaps_any(event_start, event_end, current_effective_intervals)
        already_current = key in current_raw_window_keys
        runnable = maturity_status == "mature" and coverage["status"] == "covered" and not already_current
        marginal = runnable and not overlaps_current
        if already_current:
            reason = "already_in_current_raw_family"
        elif maturity_status != "mature":
            reason = "pending_maturity"
        elif coverage["status"] != "covered":
            reason = coverage["reason"]
        elif overlaps_current:
            reason = "overlaps_current_effective_window"
        else:
            reason = "adds_non_overlapping_effective_window"
        rows.append(
            {
                "window_key": key,
                "run_dir": str(run_dir),
                "run_id": run_dir.name,
                "subject_as_of": _iso(subject_as_of),
                "horizon": horizon,
                "event_start": _iso(event_start),
                "event_end": _iso(event_end),
                "maturity_status": maturity_status,
                "truth_coverage_status": coverage["status"],
                "truth_coverage_reason": coverage["reason"],
                "event_start_price_match": coverage["event_start_price_match"],
                "event_end_price_match": coverage["event_end_price_match"],
                "already_in_current_raw_family": already_current,
                "overlaps_current_effective_window": overlaps_current,
                "marginal_effective_candidate": marginal,
                "status": "candidate" if marginal else "do_not_run",
                "reason": reason,
            }
        )
    return rows


def _greedy_candidate_window_selection(
    candidates: Sequence[Mapping[str, Any]],
    current_intervals: Sequence[Tuple[datetime, datetime]],
    *,
    limit: int,
) -> List[Mapping[str, Any]]:
    selected: List[Mapping[str, Any]] = []
    intervals = list(current_intervals)
    candidate_windows: List[Mapping[str, Any]] = []
    for candidate in candidates:
        for window in candidate.get("window_plan", []):
            if isinstance(window, Mapping) and window.get("marginal_effective_candidate"):
                candidate_windows.append(window)
    candidate_windows.sort(key=lambda row: (_as_text(row.get("event_end")), _as_text(row.get("event_start")), _as_text(row.get("run_id")), _as_text(row.get("horizon"))))
    for window in candidate_windows:
        interval = _group_interval(window)
        if interval is None:
            continue
        if _overlaps_any(interval[0], interval[1], intervals):
            continue
        selected.append(window)
        intervals.append(interval)
        if len(selected) >= limit:
            break
    return selected


def _blocker_category(reason: str) -> str:
    if reason == "subject_as_of_missing":
        return "metadata_history_debt"
    if reason == "missing_required_feeds":
        return "feed_history_debt"
    if reason in TRUTH_TAPE_GAP_REASONS:
        return "truth_tape_gap"
    if reason == "pending_maturity":
        return "future_maturity"
    if reason == "already_in_current_raw_family":
        return "already_in_family"
    if reason == "overlaps_current_effective_window":
        return "dependence_overlap"
    if reason in {"adds_marginal_effective_windows", "marginal_effective"}:
        return "marginal_effective"
    return "other"


def _run_family(row: Mapping[str, Any]) -> str:
    run_id = _as_text(row.get("run_id"))
    if run_id.startswith("FEEDS_"):
        return "FEEDS"
    if run_id.startswith("RUN_"):
        return "RUN"
    return "other"


def _subject_month(row: Mapping[str, Any]) -> str:
    subject_as_of = _as_text(row.get("subject_as_of"))
    if len(subject_as_of) >= 7:
        return subject_as_of[:7]
    run_id = _as_text(row.get("run_id"))
    if run_id.startswith("RUN_") and len(run_id) >= 11:
        return run_id[4:11]
    if run_id.startswith("FEEDS_") and len(run_id) >= 12:
        raw = run_id[6:12]
        if len(raw) == 6 and raw.isdigit():
            return f"{raw[:4]}-{raw[4:]}"
        return raw
    return "unknown"


def _window_unlockable_after_maturity(window: Mapping[str, Any]) -> bool:
    return (
        window.get("reason") == "pending_maturity"
        and window.get("truth_coverage_status") == "covered"
        and not bool(window.get("already_in_current_raw_family"))
        and not bool(window.get("overlaps_current_effective_window"))
    )


def _build_deficit_blocker_summary(
    candidates: Sequence[Mapping[str, Any]],
    *,
    horizons: Sequence[str],
    minimum_sample: int,
    current_count: int,
) -> Dict[str, Any]:
    run_reason_counts: Counter[str] = Counter()
    run_category_counts: Counter[str] = Counter()
    run_family_counts: Dict[str, Counter[str]] = defaultdict(Counter)
    subject_month_counts: Dict[str, Counter[str]] = defaultdict(Counter)
    horizon_category_counts: Dict[str, Dict[str, int]] = {}
    truth_tape_candidates: List[Dict[str, Any]] = []
    pending_windows: List[Dict[str, Any]] = []
    subject_as_of_recovery_counts: Counter[str] = Counter()
    feed_missing_counts: Counter[str] = Counter()

    for candidate in candidates:
        reason = _as_text(candidate.get("reason") or candidate.get("status") or "unknown")
        category = _blocker_category(reason)
        run_reason_counts[reason] += 1
        run_category_counts[category] += 1
        run_family_counts[_run_family(candidate)][reason] += 1
        subject_month_counts[_subject_month(candidate)][reason] += 1
        subject_as_of_recovery_counts[_as_text(candidate.get("subject_as_of_source_status") or "unknown")] += 1
        for feed in candidate.get("missing_required_feeds", []) if isinstance(candidate.get("missing_required_feeds"), list) else []:
            feed_missing_counts[_as_text(feed)] += 1

        if not candidate.get("missing_required_feeds") and reason in TRUTH_TAPE_GAP_REASONS:
            missing_horizons = []
            requested_dates = []
            for window in candidate.get("window_plan", []):
                if not isinstance(window, Mapping):
                    continue
                if window.get("reason") in TRUTH_TAPE_GAP_REASONS:
                    missing_horizons.append(_as_text(window.get("horizon")))
                    start_match = window.get("event_start_price_match") if isinstance(window.get("event_start_price_match"), Mapping) else {}
                    end_match = window.get("event_end_price_match") if isinstance(window.get("event_end_price_match"), Mapping) else {}
                    requested_dates.extend(
                        [
                            _as_text(start_match.get("requested_date")),
                            _as_text(end_match.get("requested_date")),
                        ]
                    )
            truth_tape_candidates.append(
                {
                    "run_id": candidate.get("run_id"),
                    "run_dir": candidate.get("run_dir"),
                    "subject_as_of": candidate.get("subject_as_of"),
                    "missing_horizons": sorted({value for value in missing_horizons if value}),
                    "requested_dates": sorted({value for value in requested_dates if value}),
                    "actionability": "extend_truth_tape_then_rerun_planner",
                }
            )

        for window in candidate.get("window_plan", []):
            if not isinstance(window, Mapping):
                continue
            if window.get("reason") == "pending_maturity":
                pending_windows.append(
                    {
                        "run_id": window.get("run_id"),
                        "run_dir": window.get("run_dir"),
                        "subject_as_of": window.get("subject_as_of"),
                        "horizon": window.get("horizon"),
                        "event_start": window.get("event_start"),
                        "event_end": window.get("event_end"),
                        "truth_coverage_status": window.get("truth_coverage_status"),
                        "truth_coverage_reason": window.get("truth_coverage_reason"),
                        "potential_effective_after_maturity": _window_unlockable_after_maturity(window),
                    }
                )

    for horizon in horizons:
        rows = [
            window
            for candidate in candidates
            for window in candidate.get("window_plan", [])
            if isinstance(window, Mapping) and window.get("horizon") == horizon
        ]
        horizon_category_counts[horizon] = dict(Counter(_blocker_category(_as_text(row.get("reason") or row.get("status") or "unknown")) for row in rows))

    pending_windows.sort(key=lambda row: (_as_text(row.get("event_end")), _as_text(row.get("run_id")), _as_text(row.get("horizon"))))
    potential_pending = [row for row in pending_windows if row.get("potential_effective_after_maturity")]
    return {
        "schema_version": "finance_effective_evidence_deficit_blockers_v0",
        "current_effective_non_overlapping_window_count": current_count,
        "minimum_sample": minimum_sample,
        "effective_sample_deficit": max(minimum_sample - current_count, 0),
        "candidate_run_count": len(candidates),
        "run_reason_counts": dict(run_reason_counts),
        "run_category_counts": dict(run_category_counts),
        "horizon_category_counts": horizon_category_counts,
        "run_family_reason_counts": {key: dict(value) for key, value in sorted(run_family_counts.items())},
        "subject_month_reason_counts": {key: dict(value) for key, value in sorted(subject_month_counts.items())},
        "subject_as_of_recovery_status_counts": dict(subject_as_of_recovery_counts),
        "missing_required_feed_counts": dict(feed_missing_counts),
        "unlockability": {
            "truth_tape_gap_candidate_count": len(truth_tape_candidates),
            "feed_history_debt_candidate_count": run_reason_counts.get("missing_required_feeds", 0),
            "metadata_history_debt_candidate_count": run_reason_counts.get("subject_as_of_missing", 0),
            "future_maturity_candidate_count": run_reason_counts.get("pending_maturity", 0),
            "dependence_overlap_candidate_count": run_reason_counts.get("overlaps_current_effective_window", 0),
            "already_in_family_candidate_count": run_reason_counts.get("already_in_current_raw_family", 0),
        },
        "truth_tape_extension": {
            "candidate_count": len(truth_tape_candidates),
            "candidate_preview": truth_tape_candidates[:20],
            "policy": "only extend price history for candidates with required feeds and subject_as_of present",
        },
        "maturity_calendar": {
            "pending_window_count": len(pending_windows),
            "potential_effective_window_gain_after_maturity": len(potential_pending),
            "next_pending_windows": pending_windows[:20],
        },
    }


def _build_expansion_plan(
    *,
    model_selection_payloads: Sequence[Tuple[Path, Mapping[str, Any]]],
    candidate_run_dirs: Sequence[Path],
    price_history_payload: Optional[Mapping[str, Any]],
    truth_as_of: datetime,
    horizons: Sequence[str],
    benchmark: str,
    minimum_sample: int,
    max_roll_days: int,
    max_candidates: int,
) -> Dict[str, Any]:
    if not candidate_run_dirs:
        return {
            "schema_version": EXPANSION_PLAN_SCHEMA_VERSION,
            "status": "not_requested",
            "reason": "no_candidate_run_dirs_supplied",
        }
    current = _current_window_state(model_selection_payloads)
    current_count = _as_int(current.get("current_effective_count"))
    deficit = max(minimum_sample - current_count, 0)
    benchmark_dates = _price_dates(price_history_payload, benchmark)
    candidates: List[Dict[str, Any]] = []
    for run_dir in candidate_run_dirs:
        feeds = _feed_presence(run_dir)
        subject_as_of_resolution = _subject_as_of_resolution_from_run_dir(run_dir)
        subject_as_of = subject_as_of_resolution.get("subject_as_of")
        if not isinstance(subject_as_of, datetime):
            subject_as_of = None
        missing_feeds = [name for name, present in feeds.items() if not present]
        if subject_as_of is None:
            candidates.append(
                {
                    "run_dir": str(run_dir),
                    "run_id": run_dir.name,
                    "status": "do_not_run",
                    "reason": "subject_as_of_missing",
                    "subject_as_of_source_status": subject_as_of_resolution.get("status"),
                    "subject_as_of_source": subject_as_of_resolution.get("source"),
                    "missing_required_feeds": missing_feeds,
                    "marginal_effective_window_count": 0,
                    "window_plan": [],
                }
            )
            continue
        windows = _planned_candidate_windows(
            run_dir=run_dir,
            subject_as_of=subject_as_of,
            horizons=horizons,
            truth_as_of=truth_as_of,
            benchmark_dates=benchmark_dates,
            max_roll_days=max_roll_days,
            current_raw_window_keys=current["raw_window_keys"],
            current_effective_intervals=current["selected_intervals"],
        )
        if missing_feeds:
            windows = [
                {
                    **window,
                    "marginal_effective_candidate": False,
                    "status": "do_not_run",
                    "reason": "missing_required_feeds",
                }
                for window in windows
            ]
        eligible_windows = [window for window in windows if window.get("marginal_effective_candidate")]
        if missing_feeds:
            status = "do_not_run"
            reason = "missing_required_feeds"
            marginal_count = 0
        elif not eligible_windows:
            status = "do_not_run"
            reason_counts = Counter(_as_text(window.get("reason")) for window in windows)
            reason = reason_counts.most_common(1)[0][0] if reason_counts else "no_marginal_effective_windows"
            marginal_count = 0
        else:
            selected_for_run = _greedy_non_overlapping(eligible_windows)
            status = "candidate"
            reason = "adds_marginal_effective_windows"
            marginal_count = len(selected_for_run)
        candidates.append(
            {
                "run_dir": str(run_dir),
                "run_id": run_dir.name,
                "subject_as_of": _iso(subject_as_of),
                "subject_as_of_source_status": subject_as_of_resolution.get("status"),
                "subject_as_of_source": subject_as_of_resolution.get("source"),
                "status": status,
                "reason": reason,
                "missing_required_feeds": missing_feeds,
                "marginal_effective_window_count": marginal_count,
                "mature_truth_covered_horizons": [
                    _as_text(window.get("horizon"))
                    for window in windows
                    if window.get("maturity_status") == "mature" and window.get("truth_coverage_status") == "covered"
                ],
                "window_plan": windows,
            }
        )
    candidates.sort(
        key=lambda row: (
            -_as_int(row.get("marginal_effective_window_count")),
            _as_text(row.get("subject_as_of")),
            _as_text(row.get("run_id")),
        )
    )
    selected_windows = _greedy_candidate_window_selection(
        candidates,
        current["selected_intervals"],
        limit=deficit if deficit else len(candidates),
    )
    horizon_counts: Dict[str, Dict[str, int]] = {}
    for horizon in horizons:
        rows = [
            window
            for candidate in candidates
            for window in candidate.get("window_plan", [])
            if isinstance(window, Mapping) and window.get("horizon") == horizon
        ]
        horizon_counts[horizon] = dict(
            Counter(
                (
                    "marginal_effective"
                    if row.get("marginal_effective_candidate")
                    else _as_text(row.get("reason") or row.get("status"))
                )
                for row in rows
            )
        )
    return {
        "schema_version": EXPANSION_PLAN_SCHEMA_VERSION,
        "status": "available",
        "benchmark": benchmark,
        "truth_as_of": _iso(truth_as_of),
        "match_policy": {
            "kind": "exact_or_next_available",
            "max_roll_days": max_roll_days,
            "benchmark_price_date_count": len(benchmark_dates),
            "first_benchmark_price_date": benchmark_dates[0] if benchmark_dates else None,
            "last_benchmark_price_date": benchmark_dates[-1] if benchmark_dates else None,
        },
        "horizons": list(horizons),
        "current_effective_non_overlapping_window_count": current_count,
        "minimum_sample": minimum_sample,
        "effective_sample_deficit": deficit,
        "current_raw_window_count": current.get("current_raw_window_count", 0),
        "current_selected_window_keys": current.get("selected_window_keys", []),
        "candidate_run_count": len(candidates),
        "candidate_runs_with_marginal_windows": sum(1 for row in candidates if _as_int(row.get("marginal_effective_window_count")) > 0),
        "horizon_candidate_reason_counts": horizon_counts,
        "deficit_blockers": _build_deficit_blocker_summary(
            candidates,
            horizons=horizons,
            minimum_sample=minimum_sample,
            current_count=current_count,
        ),
        "recommended_window_count": len(selected_windows),
        "expected_effective_count_after_recommended": current_count + len(selected_windows),
        "remaining_deficit_after_recommended": max(minimum_sample - current_count - len(selected_windows), 0),
        "recommended_windows": [
            {
                "run_id": window.get("run_id"),
                "run_dir": window.get("run_dir"),
                "subject_as_of": window.get("subject_as_of"),
                "horizon": window.get("horizon"),
                "event_start": window.get("event_start"),
                "event_end": window.get("event_end"),
                "truth_coverage_reason": window.get("truth_coverage_reason"),
            }
            for window in selected_windows
        ],
        "candidate_ranking": candidates[:max_candidates],
        "guardrails": {
            "projection_only": True,
            "calculator_mutation_permission": False,
            "optimizer_permission": False,
            "live_calibrator_permission": False,
            "calibration_prior_benchmark_variant_id": variant_registry.SHADOW_PROB_SHRINK_VARIANT_ID,
        },
    }


def _model_selection_summary(path: Path, payload: Mapping[str, Any]) -> Dict[str, Any]:
    receipt = _receipt(payload)
    stats = receipt.get("family_statistics") if isinstance(receipt.get("family_statistics"), Mapping) else {}
    mcs = stats.get("model_confidence_set") if isinstance(stats.get("model_confidence_set"), Mapping) else {}
    bootstrap = receipt.get("bootstrap") if isinstance(receipt.get("bootstrap"), Mapping) else {}
    sample = receipt.get("sample") if isinstance(receipt.get("sample"), Mapping) else {}
    horizon = _model_selection_horizon(receipt)
    return {
        "path": str(path),
        "selection_id": receipt.get("selection_id"),
        "horizon": horizon,
        "sample": dict(sample),
        "best_mean_delta_variant_id": stats.get("best_mean_delta_variant_id"),
        "best_mean_delta": stats.get("best_mean_delta"),
        "family_level_inference_status": stats.get("family_level_inference_status"),
        "bootstrap_status": bootstrap.get("status"),
        "spa_status": (stats.get("spa") or {}).get("status") if isinstance(stats.get("spa"), Mapping) else None,
        "model_confidence_set_status": mcs.get("status"),
        "model_confidence_set_retained_variants": mcs.get("retained_variants", []),
        "sample_gate_reason": mcs.get("reason") or (None if mcs.get("status") == "computed_bootstrap" else mcs.get("status")),
        "effective_independence": _effective_independence(receipt),
    }


def _horizon_counts(
    experiments: Sequence[Mapping[str, Any]],
    model_selections: Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    by_horizon: Dict[str, Dict[str, Any]] = {}
    for experiment in experiments:
        horizon = _as_text(experiment.get("horizon") or "combined")
        variant_id = _as_text(experiment.get("variant_id"))
        row = by_horizon.setdefault(
            horizon,
            {
                "raw_scorecards": 0,
                "mature_count": 0,
                "resolved_count": 0,
                "pending_count": 0,
                "match_status_counts": {},
                "match_reason_counts": {},
                "variant_counts": {},
            },
        )
        row["variant_counts"][variant_id] = {
            "raw_scorecards": experiment["raw_scorecard_count"],
            "mature_count": experiment["mature_count"],
            "resolved_count": experiment["resolved_count"],
            "pending_count": experiment["pending_count"],
            "status_counts": experiment["status_counts"],
            "mean_brier": experiment.get("mean_brier"),
        }
        if variant_id == variant_registry.BASELINE_VARIANT_ID:
            row["raw_scorecards"] = experiment["raw_scorecard_count"]
            row["mature_count"] = experiment["mature_count"]
            row["resolved_count"] = experiment["resolved_count"]
            row["pending_count"] = experiment["pending_count"]
            row["match_status_counts"] = experiment["price_match_status_counts"]
            row["match_reason_counts"] = experiment["price_match_reason_counts"]
    for selection in model_selections:
        horizon = _as_text(selection.get("horizon") or "combined")
        row = by_horizon.setdefault(horizon, {})
        sample = selection.get("sample") if isinstance(selection.get("sample"), Mapping) else {}
        row["paired_event_count"] = sample.get("shared_event_count", sample.get("pairwise_shared_event_count", 0))
        row["dropped_unshared_event_count"] = sample.get("dropped_unshared_event_count", 0)
        row["model_selection"] = {
            "selection_id": selection.get("selection_id"),
            "best_mean_delta_variant_id": selection.get("best_mean_delta_variant_id"),
            "best_mean_delta": selection.get("best_mean_delta"),
            "family_level_inference_status": selection.get("family_level_inference_status"),
            "bootstrap_status": selection.get("bootstrap_status"),
            "spa_status": selection.get("spa_status"),
            "model_confidence_set_status": selection.get("model_confidence_set_status"),
            "model_confidence_set_retained_variants": selection.get("model_confidence_set_retained_variants"),
            "sample_gate_reason": selection.get("sample_gate_reason"),
        }
        row["effective_independence"] = selection.get("effective_independence")
    return dict(sorted(by_horizon.items()))


def _variant_taxonomy() -> Dict[str, Any]:
    rows = {}
    for row in variant_registry.variant_rows():
        variant_id = _as_text(row.get("generator_variant_id"))
        rows[variant_id] = {
            "status": row.get("status"),
            "variant_family": row.get("variant_family", "unspecified"),
            "evidence_role": row.get("evidence_role", "unspecified"),
            "calibrator_id": row.get("calibrator_id"),
            "calibration_policy": row.get("calibration_policy"),
            "optimizer_permission": bool(row.get("optimizer_permission")),
            "calculator_mutation_permission": bool(row.get("calculator_mutation_permission")),
            "predeclared_design_note": row.get("predeclared_design_note"),
        }
    benchmark_id = variant_registry.SHADOW_PROB_SHRINK_VARIANT_ID
    return {
        "registry_ref": variant_registry.REGISTRY_REF,
        "baseline_variant_id": variant_registry.BASELINE_VARIANT_ID,
        "calibration_prior_benchmark_variant_id": benchmark_id,
        "calibration_prior_benchmark": rows.get(benchmark_id),
        "variants": rows,
    }


def build_effective_evidence_receipt(
    *,
    experiment_payloads: Sequence[Tuple[Path, Mapping[str, Any]]],
    model_selection_payloads: Sequence[Tuple[Path, Mapping[str, Any]]],
    variant_gate_paths: Sequence[Path],
    candidate_run_dirs: Sequence[Path] = (),
    price_history_path: Optional[Path] = None,
    price_history_payload: Optional[Mapping[str, Any]] = None,
    truth_as_of: Optional[datetime] = None,
    planning_horizons: Sequence[str] = DEFAULT_PLANNING_HORIZONS,
    benchmark: str = "SPY",
    minimum_sample: int = DEFAULT_MINIMUM_INFERENCE_SAMPLE,
    max_roll_days: int = 3,
    max_plan_candidates: int = 20,
    source_note: Optional[str] = None,
) -> Dict[str, Any]:
    experiments = [_experiment_summary(path, payload) for path, payload in experiment_payloads]
    model_selections = [_model_selection_summary(path, payload) for path, payload in model_selection_payloads]
    combined = next((selection for selection in model_selections if selection.get("horizon") == "combined"), None)
    resolved_truth_as_of = truth_as_of or feed_envelope.utc_now().dt
    expansion_plan = _build_expansion_plan(
        model_selection_payloads=model_selection_payloads,
        candidate_run_dirs=candidate_run_dirs,
        price_history_payload=price_history_payload,
        truth_as_of=resolved_truth_as_of,
        horizons=planning_horizons,
        benchmark=benchmark,
        minimum_sample=minimum_sample,
        max_roll_days=max_roll_days,
        max_candidates=max_plan_candidates,
    )
    gates_closed = {
        "calculator_mutation_permission": False,
        "optimizer_permission": False,
        "live_calibrator_permission": False,
    }
    for selection in model_selections:
        # Model-selection receipts are evidence-only; these fields are repeated
        # here so the effective-evidence receipt can be read standalone.
        gates_closed["calculator_mutation_permission"] = gates_closed["calculator_mutation_permission"] or False
        gates_closed["optimizer_permission"] = gates_closed["optimizer_permission"] or False
    return {
        "schema_version": DATA_SCHEMA_VERSION,
        "source_note": source_note,
        "source_refs": {
            "experiment_artifacts": [str(path) for path, _payload in experiment_payloads],
            "variant_gate_artifacts": [str(path) for path in variant_gate_paths],
            "model_selection_artifacts": [str(path) for path, _payload in model_selection_payloads],
            "candidate_run_dirs": [str(path) for path in candidate_run_dirs],
            "price_history_artifact": str(price_history_path) if price_history_path else None,
        },
        "variant_taxonomy": _variant_taxonomy(),
        "horizons": _horizon_counts(experiments, model_selections),
        "combined_summary": {
            "selection_id": combined.get("selection_id") if combined else None,
            "paired_event_count": ((combined.get("sample") or {}).get("shared_event_count") if combined else 0),
            "best_mean_delta_variant_id": combined.get("best_mean_delta_variant_id") if combined else None,
            "best_mean_delta": combined.get("best_mean_delta") if combined else None,
            "model_confidence_set_retained_variants": combined.get("model_confidence_set_retained_variants") if combined else [],
            "effective_independence": combined.get("effective_independence") if combined else {},
        },
        "gate_status": {
            "calculator_mutation_permission": False,
            "optimizer_permission": False,
            "live_calibrator_permission": False,
            "reason": "effective evidence receipt is observational and cannot admit mutation",
        },
        "interpretation_guard": {
            "status": "evidence_only",
            "primary_caution": "raw paired rows are not independent when event windows overlap",
            "calibration_prior_rule": (
                "shadow_prob_shrink is a fixed probability-map benchmark; learned calibrators must beat it "
                "on the same common-support, maturity-gated event set before any calibration promotion."
            ),
        },
        "expansion_plan": expansion_plan,
    }


def _failure_envelope(error: str, *, run_dir: Optional[Path] = None) -> Dict[str, Any]:
    now = feed_envelope.utc_now()
    compact = now.dt.strftime("%Y%m%dT%H%M%SZ")
    diagnostics = feed_envelope.new_diagnostics(error=error)
    metadata = feed_envelope.build_metadata(
        tool=TOOL_NAME,
        status="failure",
        now=now,
        run_id=f"finance_effective_evidence_failure_{compact}",
        as_of=now.iso,
        items_count=0,
        diagnostics=diagnostics,
        data_schema_version=DATA_SCHEMA_VERSION,
        timestamp=now.iso,
    )
    return {"metadata": metadata, "data": {"error": error, "run_dir": str(run_dir) if run_dir else None}}


def run(config: Dict[str, Any], run_dir: Optional[Path] = None) -> Dict[str, Any]:
    try:
        experiment_paths = [Path(path) for path in config.get("experiments", [])]
        model_selection_paths = [Path(path) for path in config.get("model_selections", [])]
        variant_gate_paths = [Path(path) for path in config.get("variant_gates", [])]
        if not experiment_paths:
            raise ValueError("at least one --experiments path is required")
        if not model_selection_paths:
            raise ValueError("at least one --model-selections path is required")
        now = feed_envelope.utc_now()
        runtime = config.get("runtime", {}) if isinstance(config.get("runtime"), Mapping) else {}
        raw_horizons = config.get("planning_horizons") or DEFAULT_PLANNING_HORIZONS
        if isinstance(raw_horizons, str):
            planning_horizons = [raw_horizons]
        else:
            planning_horizons = [_as_text(horizon) for horizon in raw_horizons if _as_text(horizon)]
        if not planning_horizons:
            planning_horizons = list(DEFAULT_PLANNING_HORIZONS)
        candidate_run_dirs = _candidate_run_dirs(
            [Path(path) for path in config.get("candidate_run_dirs", [])],
            [Path(path) for path in config.get("candidate_run_roots", [])],
        )
        price_history_path = Path(config["price_history"]) if config.get("price_history") else None
        price_history_payload = _read_json(price_history_path) if price_history_path else None
        truth_as_of = _parse_dt(config.get("truth_as_of") or runtime.get("truth_as_of") or runtime.get("as_of") or now.iso)
        receipt = build_effective_evidence_receipt(
            experiment_payloads=[(path, _read_json(path)) for path in experiment_paths],
            model_selection_payloads=[(path, _read_json(path)) for path in model_selection_paths],
            variant_gate_paths=variant_gate_paths,
            candidate_run_dirs=candidate_run_dirs,
            price_history_path=price_history_path,
            price_history_payload=price_history_payload,
            truth_as_of=truth_as_of or now.dt,
            planning_horizons=planning_horizons,
            benchmark=_as_text(config.get("benchmark") or "SPY"),
            minimum_sample=_as_int(config.get("minimum_sample")) or DEFAULT_MINIMUM_INFERENCE_SAMPLE,
            max_roll_days=_as_int(config.get("max_roll_days")) or 3,
            max_plan_candidates=_as_int(config.get("max_plan_candidates")) or 20,
            source_note=_as_text(config.get("source_note")),
        )
        compact = now.dt.strftime("%Y%m%dT%H%M%SZ")
        run_id = _as_text(runtime.get("run_id") or f"fin_eff_evidence_{compact}")
        diagnostics = feed_envelope.new_diagnostics(
            input_rows=len(experiment_paths) + len(model_selection_paths) + len(variant_gate_paths),
            output_rows=1,
            dropped_rows=0,
            horizon_count=len(receipt["horizons"]),
            combined_paired_event_count=receipt["combined_summary"].get("paired_event_count"),
            expansion_plan_status=receipt.get("expansion_plan", {}).get("status"),
            expansion_candidate_run_count=receipt.get("expansion_plan", {}).get("candidate_run_count", 0),
        )
        metadata = feed_envelope.build_metadata(
            tool=TOOL_NAME,
            status="success",
            now=now,
            run_id=run_id,
            as_of=_as_text(runtime.get("as_of") or now.iso),
            items_count=1,
            diagnostics=diagnostics,
            data_schema_version=DATA_SCHEMA_VERSION,
            timestamp=now.iso,
        )
        return {"metadata": metadata, "data": {"receipt": receipt}}
    except Exception as exc:
        return _failure_envelope(str(exc), run_dir=run_dir)


def write_payload(payload: Mapping[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build a finance effective-evidence receipt.")
    parser.add_argument("--experiments", action="append", default=[], help="finance_historical_replay envelope. Repeatable.")
    parser.add_argument("--variant-gates", action="append", default=[], help="finance_variant_admission receipt. Repeatable.")
    parser.add_argument("--model-selections", action="append", default=[], help="finance_model_selection receipt. Repeatable.")
    parser.add_argument("--candidate-run-dir", action="append", default=[], help="Candidate subject run directory. Repeatable.")
    parser.add_argument("--candidate-run-root", action="append", default=[], help="Root containing subject run directories. Repeatable.")
    parser.add_argument("--price-history", default="", help="Resolver-compatible finance_price_history tape for truth coverage planning.")
    parser.add_argument("--truth-as-of", default="", help="UTC timestamp used for horizon maturity planning.")
    parser.add_argument("--planning-horizon", action="append", default=[], help="Planning horizon such as 5d, 10d, 20d. Repeatable.")
    parser.add_argument("--benchmark", default="SPY", help="Benchmark symbol to use for truth-tape boundary coverage.")
    parser.add_argument("--minimum-sample", type=int, default=DEFAULT_MINIMUM_INFERENCE_SAMPLE, help="Effective non-overlap sample threshold.")
    parser.add_argument("--max-roll-days", type=int, default=3, help="Maximum date roll days for price-tape coverage planning.")
    parser.add_argument("--max-plan-candidates", type=int, default=20, help="Maximum candidate run rows to include in the ranking.")
    parser.add_argument("--source-note", default="", help="Optional note describing the evidence slice.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Output JSON path.")
    parser.add_argument("--json", action="store_true", help="Print JSON envelope.")
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    payload = run(
        {
            "experiments": args.experiments,
            "variant_gates": args.variant_gates,
            "model_selections": args.model_selections,
            "candidate_run_dirs": args.candidate_run_dir,
            "candidate_run_roots": args.candidate_run_root,
            "price_history": args.price_history,
            "truth_as_of": args.truth_as_of,
            "planning_horizons": args.planning_horizon,
            "benchmark": args.benchmark,
            "minimum_sample": args.minimum_sample,
            "max_roll_days": args.max_roll_days,
            "max_plan_candidates": args.max_plan_candidates,
            "source_note": args.source_note,
        }
    )
    write_payload(payload, Path(args.output))
    text = json.dumps(payload, indent=2, sort_keys=True)
    print(text if args.json else text)
    return 0 if payload.get("metadata", {}).get("status") == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
