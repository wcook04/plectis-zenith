"""
[PURPOSE]
- Teleology: Emit deterministic subject-vs-truth measurements+SUBSYSTEMS comparison for Oracle v1.
- Mechanism: Reuse shared run-compare primitives to compute top movers and realized grading tables.

[INTERFACE]
- Inputs: `config.runtime.oracle_subject_run_dir`, `config.runtime.oracle_truth_run_dir`.
- Outputs: Success envelope carrying reconciliation rows, grading tables, movers, feed-health readiness, and summary diagnostics.
- Exports: `run`.

[FLOW]
- Resolve subject and truth run directories.
- Compare shared measurements/SUBSYSTEMS values and grade subject predictions against truth values.
- Surface whether every Lab CP2 target has subject and truth values before interpretation.
- Rank reconciliation rows and summarize grading misses.
- Emit metadata plus the comparison payload for downstream Oracle reads.

[DEPENDENCIES]
- system.lib.run_compare: Reuse shared observation comparison, grading, and feed-loading helpers.

[CONSTRAINTS]
- Read-only and deterministic for stable subject/truth artifacts.
- Missing optional artifact content degrades to empty comparison tables through helper defaults.
- When-needed: Open when Oracle needs the realized measurements and SUBSYSTEMS truth comparison between subject and truth runs, including graded targets and reconciliation rows.
- Escalates-to: tools/oracle/truth_diff_observations.py::run; system/lib/run_compare.py::compare_observation_runs; system/lib/run_compare.py::grade_predictions
- Navigation-group: system_intelligence
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from system.lib.run_compare import (
    compare_observation_runs,
    observation_feed_health,
    grade_predictions,
    load_feed_values,
)
from system.lib.artifacts import load_artifact
from system.lib.schema_validator import validate_cp2


def _require_run_dir(config: Dict[str, Any], key: str) -> Path:
    runtime = config.get("runtime", {}) if isinstance(config, dict) else {}
    raw = runtime.get(key)
    if not raw:
        raise ValueError(f"{key} is required for oracle_truth_diff_observations")
    run_dir = Path(str(raw))
    if not run_dir.exists():
        raise ValueError(f"{key} does not exist: {run_dir}")
    return run_dir


def _load_as_of(run_dir: Path) -> Any:
    ctx_path = run_dir / "runtime_context.json"
    if not ctx_path.exists():
        return None
    try:
        ctx = json.loads(ctx_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(ctx, dict):
        return None
    return ctx.get("as_of") or ctx.get("time_anchor") or ctx.get("timestamp")


def _build_prediction_reconciliation_rows(
    subject_run_dir: Path,
    grading: Dict[str, Any],
) -> List[Dict[str, Any]]:
    measurements_rows = load_feed_values(subject_run_dir, "global_measurements_feed")
    subsystems_rows = load_feed_values(subject_run_dir, "global_subsystems_feed")
    rows: List[Dict[str, Any]] = []

    for result in grading.get("results", []):
        if not isinstance(result, dict) or result.get("status") != "GRADED":
            continue
        target_id = str(result.get("target_id") or "").upper().strip()
        if not target_id:
            continue

        target_kind = None
        if target_id in measurements_rows:
            target_kind = "MEASUREMENTS"
        elif target_id in subsystems_rows:
            target_kind = "SUBSYSTEMS"
        if target_kind is None:
            continue

        snapshot_value = result.get("snapshot_value")
        predicted_value = result.get("predicted_value")
        realized_value = result.get("realized_value")
        abs_error = result.get("abs_error")
        pred_error_pct = result.get("pred_error_pct")
        direction_hit = result.get("direction_hit")

        numeric_fields = (snapshot_value, predicted_value, realized_value, abs_error, pred_error_pct)
        if not all(isinstance(value, (int, float)) for value in numeric_fields):
            continue
        if not isinstance(direction_hit, bool):
            continue

        rows.append(
            {
                "target_id": target_id,
                "target_kind": target_kind,
                "unit": result.get("unit"),
                "prediction_direction": str(result.get("predicted_direction") or "").upper().strip(),
                "subject_snapshot_value": float(snapshot_value),
                "predicted_target_value": float(predicted_value),
                "realized_truth_value": float(realized_value),
                "absolute_delta": float(abs_error),
                "percent_delta": float(pred_error_pct),
                "directional_correct": direction_hit,
                **({key: result[key] for key in ('forecast_quantiles', 'realized_simple_return',
                    'quantile_pinball_losses', 'mean_quantile_pinball_loss', 'interval_80_covered',
                    'interval_80_width', 'quantile_units', 'calibration_status')}
                   if 'forecast_quantiles' in result else {}),
            }
        )

    rows.sort(
        key=lambda item: (
            -abs(float(item.get("absolute_delta", 0.0))),
            -abs(float(item.get("percent_delta", 0.0))),
            str(item.get("target_id") or ""),
        )
    )
    for index, row in enumerate(rows, start=1):
        row["rank"] = index
    return rows


def _build_prediction_reconciliation_summary(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    summary: Dict[str, Any] = {
        "row_count": len(rows),
        "directionally_correct_count": sum(1 for row in rows if row.get("directional_correct") is True),
        "directionally_incorrect_count": sum(1 for row in rows if row.get("directional_correct") is False),
    }
    if rows:
        summary["largest_absolute_miss_target"] = rows[0]["target_id"]
        largest_percent = max(
            rows,
            key=lambda item: abs(float(item.get("percent_delta", 0.0))),
        )
        summary["largest_percent_miss_target"] = largest_percent["target_id"]
    return summary


def run(config: Dict[str, Any], run_dir: str | None = None) -> Dict[str, Any]:
    """
    [ACTION]
    - Teleology: Build the Oracle observation truth-diff envelope from paired subject and truth runs.
    - Mechanism: Resolve the required run directories, compute shared comparison and grading views, derive ranked reconciliation rows and summaries, and attach provenance metadata.
    - Reads: `config.runtime.oracle_subject_run_dir`, `config.runtime.oracle_truth_run_dir`, runtime context files, and shared run-compare helpers.
    - Writes: None.
    - Guarantee: Returns a success envelope with top movers, realized target tables, ranked reconciliation rows, feed-health readiness, and summary metadata.
    - Fails: Raises ValueError when required run directories are missing or invalid; helper read gaps degrade to empty comparison tables.
    - When-needed: Open when a caller needs the exact ranking and payload contract for Oracle observation truth diffs.
    - Escalates-to: system/lib/run_compare.py::compare_observation_runs; system/lib/run_compare.py::grade_predictions; tools/oracle/subject_index.py::run
    """
    subject_run_dir = _require_run_dir(config, "oracle_subject_run_dir")
    truth_run_dir = _require_run_dir(config, "oracle_truth_run_dir")
    comparison = compare_observation_runs(subject_run_dir, truth_run_dir, top_n=25)
    grading = grade_predictions(subject_run_dir, truth_run_dir)
    reconciliation_rows = _build_prediction_reconciliation_rows(subject_run_dir, grading)
    reconciliation_summary = _build_prediction_reconciliation_summary(reconciliation_rows)
    feed_health = observation_feed_health(subject_run_dir, truth_run_dir)
    subject_envelope = load_artifact(subject_run_dir, "lab_director") or {}
    subject_cp2 = subject_envelope.get("data", {})
    if subject_cp2.get('forecast_basis','CAUSAL') != 'CAUSAL' or 'forecast_quantiles' in subject_cp2:
        raise ValueError('Unsupported forecast contract cannot become scored reconciliation')
    abstained = subject_cp2.get("decision_status") == "ABSTAIN"
    if abstained and (subject_envelope.get("status") not in {"success", "loaded"}
                      or not validate_cp2(subject_cp2, subject_run_dir=subject_run_dir).ok):
        raise ValueError("Invalid subject abstention cannot become a successful reconciliation")
    if abstained and feed_health.get("common_target_id_count", 0) > 0:
        feed_health = {**feed_health, "status": "ABSTAINED",
                       "diagnostics": ["Valid subject no-call; common values support review, not forecast scoring."]}
    data = {
        "status": "ABSTAINED" if abstained else "AVAILABLE",
        "subject_decision_status": "ABSTAIN" if abstained else "FORECAST",
        "subject_forecast_basis": subject_cp2.get('forecast_basis', 'CAUSAL'),
        "subject_run_id": subject_run_dir.name,
        "truth_run_id": truth_run_dir.name,
        "subject_as_of": _load_as_of(subject_run_dir),
        "truth_as_of": _load_as_of(truth_run_dir),
        "rows": reconciliation_rows,
        "summary": reconciliation_summary,
        "prediction_targets": comparison.get("prediction_targets", []),
        "top_movers": comparison.get("top_movers", []),
        "realized_target_table": grading.get("results", []),
        "grading_summary": grading.get("summary", {}),
        "comparison_summary": {
            "common_target_id_count": comparison.get("common_target_id_count", 0),
            "prediction_target_count": len(comparison.get("prediction_target_moves", [])),
        },
        "subject_prior_availability_assessment": grading.get("prior_availability_assessment"),
        "subject_dominant_evidence_track": grading.get("dominant_evidence_track"),
        "feed_health": feed_health,
    }
    return {
        "metadata": {
            "tool": "oracle_truth_diff_observations",
            "status": "success",
            "subject_run_id": subject_run_dir.name,
            "truth_run_id": truth_run_dir.name,
            "diagnostics": {
                "input_rows": 0,
                "output_rows": len(data["top_movers"]) + len(data["rows"]),
                "dropped_rows": 0,
                "warnings": feed_health.get("diagnostics", []),
            },
        },
        "data": data,
    }
