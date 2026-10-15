"""
[PURPOSE]
- Teleology: Provide reusable deterministic subject-vs-truth comparison helpers for Oracle v1
  and kernel cross-run diagnostics.
- Mechanism: Pure artifact reads over paired run directories; normalize measurements+SUBSYSTEMS value tables,
  Lab CP2 predictions, and compact grading/comparison summaries.

[INTERFACE]
- Reads: run_dir/artifacts/{global_measurements_feed.json, global_subsystems_feed.json, lab_director.json}
- Writes: None.
- Exports: load_feed_values, load_predictions, load_director_meta, combined_values,
  observation_feed_health, compare_observation_runs, grade_predictions.

[FLOW]
- load_feed_values(), load_predictions(), and load_director_meta() normalize run artifacts -> combined_values() unions measurements and SUBSYSTEMS tables -> compare_observation_runs() and grade_predictions() emit deterministic subject-vs-truth summaries for kernel or Oracle diagnostics.
- When-needed: Open when Oracle or kernel diagnostics need deterministic subject-vs-truth run comparison without re-implementing artifact readers.
- Escalates-to: system/lib/artifacts.py; system/lib/schema_validator.py; system/lib/citations.py
- Navigation-group: kernel_lib

[DEPENDENCIES]
- Reads: Existing run artifact JSON; no provider or external binary calls.
- Missing feed/prediction data is normalized by local artifact loaders.

[CONSTRAINTS]
- Read-only and deterministic: no writes, no network, no runtime side effects.
- Value comparisons are observation-wide: measurements + SUBSYSTEMS union.
- Missing artifacts degrade to empty dict/list rather than raising.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List


def _coerce_scalar(value: Any) -> Any:
    if isinstance(value, str):
        token = value.strip()
        if not token:
            return value
        try:
            return float(token)
        except Exception:
            return value
    return value


def _load_json(path: Path) -> Dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _iter_tables(node: Any):
    if isinstance(node, dict):
        columns = node.get("columns")
        rows = node.get("rows")
        if isinstance(columns, list) and isinstance(rows, list):
            yield columns, rows
        for value in node.values():
            yield from _iter_tables(value)
    elif isinstance(node, list):
        for item in node:
            yield from _iter_tables(item)


def load_feed_values(run_dir: Path | str, feed_name: str) -> Dict[str, Dict[str, Any]]:
    """
    [ACTION]
    - Teleology: Load one observation feed artifact from a run directory into a target_id-keyed value dict.
    - Guarantee: Returns a dict mapping uppercase target_id strings to their full row record, or an empty dict when the artifact is missing or unreadable.
    - Fails: None — missing or malformed artifacts degrade to an empty dict.
    """
    run_dir = Path(run_dir)
    path = run_dir / "artifacts" / f"{feed_name}.json"
    if not path.exists():
        return {}

    payload = _load_json(path)
    data = payload.get("data", {})
    result: Dict[str, Dict[str, Any]] = {}
    if isinstance(data, dict) and isinstance(data.get("observations"), list):
        for record in data["observations"]:
            if not isinstance(record, dict) or not isinstance(record.get("target_id"), str):
                continue
            target = record["target_id"].upper().strip()
            if target in result:
                raise ValueError("duplicate observation target in snapshot")
            result[target] = {**record, "Value": record.get("value"), "__observation_contract":True}
        return result
    for columns, rows in _iter_tables(data):
        if not all(isinstance(col, str) for col in columns):
            continue
        for row in rows:
            if not isinstance(row, list):
                continue
            record = {
                # Issuer identifiers are opaque strings, including leading-zero
                # A-share codes. Numeric coercion belongs to measurements only.
                str(col): (row[idx] if str(col).lower() == 'target_id' else _coerce_scalar(row[idx])) if idx < len(row) else None
                for idx, col in enumerate(columns)
            }
            target_id = record.get("target_id") or record.get("target_id")
            if not target_id:
                continue
            result[str(target_id).upper().strip()] = record
    return result


def load_predictions(run_dir: Path | str, artifact_id: str = "lab_director") -> List[Dict[str, Any]]:
    """
    [ACTION]
    - Teleology: Load the predictions_t list from a Lab CP2 artifact in a run directory.
    - Guarantee: Returns a list of prediction dicts, or an empty list when the artifact is missing, unreadable, or contains no predictions.
    - Fails: None — missing or malformed artifacts degrade to an empty list.
    """
    run_dir = Path(run_dir)
    path = run_dir / "artifacts" / f"{artifact_id}.json"
    if not path.exists():
        return []
    payload = _load_json(path)
    data = payload.get("data", {})
    predictions = data.get("predictions_t", []) if isinstance(data, dict) else []
    if not isinstance(predictions, list):
        return []
    return [item for item in predictions if isinstance(item, dict)]


def load_director_meta(run_dir: Path | str, artifact_id: str = "lab_director") -> Dict[str, Any]:
    """
    [ACTION]
    - Teleology: Load compact Lab CP2 metadata and selected top-level fields from a run directory artifact.
    - Guarantee: Returns a dict with dominant_evidence_track, prior_availability_assessment, forecast_rationale, target_time_iso, horizon_label, and as_of fields, or an empty dict when the artifact is missing or unreadable.
    - Fails: None — missing or malformed artifacts degrade to an empty dict.
    """
    run_dir = Path(run_dir)
    path = run_dir / "artifacts" / f"{artifact_id}.json"
    if not path.exists():
        return {}
    payload = _load_json(path)
    data = payload.get("data", {})
    meta = payload.get("metadata", {})
    if not isinstance(data, dict):
        data = {}
    if not isinstance(meta, dict):
        meta = {}
    return {
        "dominant_evidence_track": data.get("dominant_evidence_track"),
        "prior_availability_assessment": data.get("prior_availability_assessment"),
        "forecast_rationale": data.get("forecast_rationale"),
        "target_time_iso": meta.get("target_time_iso"),
        "horizon_label": meta.get("horizon_label"),
        "as_of": meta.get("as_of"),
    }


def combined_values(run_dir: Path | str) -> Dict[str, Dict[str, Any]]:
    """
    [ACTION]
    - Teleology: Union measurements and SUBSYSTEMS value tables for a run into one target_id-keyed dict.
    - Guarantee: Returns a merged dict covering both global_measurements_feed and global_subsystems_feed target_ids, with SUBSYSTEMS rows overwriting measurements rows on key collision.
    - Fails: None — missing feed artifacts degrade gracefully to empty contributions.
    """
    values: Dict[str, Dict[str, Any]] = {}
    values.update(load_feed_values(run_dir, "global_measurements_feed"))
    values.update(load_feed_values(run_dir, "global_subsystems_feed"))
    return values


def _is_numeric_value(row: Dict[str, Any] | None) -> bool:
    if not isinstance(row, dict):
        return False
    return isinstance(row.get("Value"), (int, float))


def _value_count(rows: Dict[str, Dict[str, Any]]) -> int:
    return sum(1 for row in rows.values() if _is_numeric_value(row))


def observation_feed_health(subject_run_dir: Path | str, truth_run_dir: Path | str) -> Dict[str, Any]:
    """
    [ACTION]
    - Teleology: Summarize whether a paired subject/truth run has enough observation feed data to grade Lab CP2 targets.
    - Mechanism: Load subject and truth measurements/SUBSYSTEMS value maps, intersect their target_id universes, then compare Lab prediction targets against available numeric values.
    - Guarantee: Returns READY when all prediction targets have subject and truth values, DEGRADED when only some targets are comparable, and BLOCKED when no deterministic observation grading target is available.
    - Fails: None — missing artifacts degrade into counts, missing target lists, and diagnostics.
    - When-needed: Open when Oracle or Evolve needs to distinguish a real miss from missing subject/truth feed coverage.
    - Escalates-to: system/lib/run_compare.py::load_feed_values; system/lib/run_compare.py::load_predictions
    - Navigation-group: kernel_lib
    """
    subject_run_dir = Path(subject_run_dir)
    truth_run_dir = Path(truth_run_dir)

    subject_measurements = load_feed_values(subject_run_dir, "global_measurements_feed")
    subject_subsystems = load_feed_values(subject_run_dir, "global_subsystems_feed")
    truth_measurements = load_feed_values(truth_run_dir, "global_measurements_feed")
    truth_subsystems = load_feed_values(truth_run_dir, "global_subsystems_feed")
    subject_values = {**subject_measurements, **subject_subsystems}
    truth_values = {**truth_measurements, **truth_subsystems}
    prediction_targets = sorted(
        {
            str(item.get("target_id")).upper().strip()
            for item in load_predictions(subject_run_dir)
            if item.get("target_id")
        }
    )

    missing_subject = sorted(
        target
        for target in prediction_targets
        if not _is_numeric_value(subject_values.get(target))
    )
    missing_truth = sorted(
        target
        for target in prediction_targets
        if not _is_numeric_value(truth_values.get(target))
    )
    comparable = sorted(
        target
        for target in prediction_targets
        if target not in missing_subject and target not in missing_truth
    )

    diagnostics: List[str] = []
    if not prediction_targets:
        diagnostics.append("no Lab CP2 prediction targets found")
    if not subject_values:
        diagnostics.append("subject measurements+SUBSYSTEMS value universe is empty")
    if not truth_values:
        diagnostics.append("truth measurements+SUBSYSTEMS value universe is empty")
    if missing_subject:
        diagnostics.append(
            "missing subject values for targets: " + ", ".join(missing_subject)
        )
    if missing_truth:
        diagnostics.append(
            "missing truth values for targets: " + ", ".join(missing_truth)
        )

    if not prediction_targets or not comparable:
        status = "BLOCKED"
    elif missing_subject or missing_truth:
        status = "DEGRADED"
    else:
        status = "READY"

    return {
        "status": status,
        "subject": {
            "measurements_target_id_count": len(subject_measurements),
            "subsystems_target_id_count": len(subject_subsystems),
            "measurements_value_count": _value_count(subject_measurements),
            "subsystems_value_count": _value_count(subject_subsystems),
            "target_id_count": len(subject_values),
        },
        "truth": {
            "measurements_target_id_count": len(truth_measurements),
            "subsystems_target_id_count": len(truth_subsystems),
            "measurements_value_count": _value_count(truth_measurements),
            "subsystems_value_count": _value_count(truth_subsystems),
            "target_id_count": len(truth_values),
        },
        "common_target_id_count": len(set(subject_values.keys()) & set(truth_values.keys())),
        "prediction_target_count": len(prediction_targets),
        "comparable_prediction_targets": comparable,
        "missing_subject_value_targets": missing_subject,
        "missing_truth_value_targets": missing_truth,
        "diagnostics": diagnostics,
    }


def compare_observation_runs(
    subject_run_dir: Path | str,
    truth_run_dir: Path | str,
    *,
    top_n: int = 20,
) -> Dict[str, Any]:
    """[ACTION]
    - Teleology: Summarize realized value movement between a subject run and a truth run across the shared observation universe.
    - Mechanism: Load measurements and SUBSYSTEMS tables for both runs, intersect target_ids, compute absolute/percent deltas, and highlight which movers were explicit prediction targets.
    - Guarantee: Returns a deterministic comparison mapping ordered by descending absolute percent move.
    - Fails: None — missing artifacts degrade to empty tables and therefore empty summaries.
    - When-needed: Open when cross-run diagnostics need the canonical top-mover and prediction-target delta summary for paired observation runs.
    - Escalates-to: system/lib/artifacts.py; system/lib/schema_validator.py::validate_prediction_reconciliation
    - Navigation-group: kernel_lib
    """
    subject_run_dir = Path(subject_run_dir)
    truth_run_dir = Path(truth_run_dir)

    subject_values = combined_values(subject_run_dir)
    truth_values = combined_values(truth_run_dir)
    predictions = load_predictions(subject_run_dir)
    prediction_targets = sorted(
        {
            str(item.get("target_id")).upper().strip()
            for item in predictions
            if item.get("target_id")
        }
    )

    deltas: List[Dict[str, Any]] = []
    for target_id in sorted(set(subject_values.keys()) & set(truth_values.keys())):
        subject_value = subject_values[target_id].get("Value")
        truth_value = truth_values[target_id].get("Value")
        if not isinstance(subject_value, (int, float)) or not isinstance(truth_value, (int, float)):
            continue
        if subject_value == 0:
            continue
        abs_delta = truth_value - subject_value
        pct_delta = (abs_delta / subject_value) * 100
        deltas.append(
            {
                "target_id": target_id,
                "subject_value": subject_value,
                "truth_value": truth_value,
                "abs_delta": abs_delta,
                "pct_delta": pct_delta,
                "is_prediction_target": target_id in prediction_targets,
            }
        )

    deltas.sort(key=lambda item: abs(float(item.get("pct_delta", 0.0))), reverse=True)
    return {
        "subject_run_id": subject_run_dir.name,
        "truth_run_id": truth_run_dir.name,
        "prediction_targets": prediction_targets,
        "common_target_id_count": len(deltas),
        "top_movers": deltas[: max(0, int(top_n))],
        "prediction_target_moves": [item for item in deltas if item["is_prediction_target"]],
    }


def grade_predictions(subject_run_dir: Path | str, truth_run_dir: Path | str) -> Dict[str, Any]:
    """[ACTION]
    - Teleology: Grade Lab CP2 predictions against realized truth-run values and return hit/miss/ungraded outcomes.
    - Mechanism: Load predictions plus truth values, compare predicted direction and value against realized movement, and aggregate per-target rows with compact summary metrics.
    - Guarantee: Returns a deterministic grading payload with per-target results and aggregate hit-rate metadata.
    - Fails: None — missing predictions or values degrade to ungraded rows and empty summaries instead of raising.
    - When-needed: Open when Oracle hindsight or kernel diagnostics need the canonical grading pass for CP2 predictions against a truth run.
    - Escalates-to: system/lib/schema_validator.py::validate_prediction_reconciliation; system/lib/artifacts.py
    - Navigation-group: kernel_lib
    """
    subject_run_dir = Path(subject_run_dir)
    truth_run_dir = Path(truth_run_dir)

    predictions = load_predictions(subject_run_dir)
    truth_values = combined_values(truth_run_dir)
    meta = load_director_meta(subject_run_dir)
    cp2 = (_load_json(subject_run_dir/'artifacts/lab_director.json') if (subject_run_dir/'artifacts/lab_director.json').exists() else {}).get('data', {})
    if cp2.get('forecast_basis', 'CAUSAL') != 'CAUSAL' or 'forecast_quantiles' in cp2:
        raise ValueError('Unsupported forecast contract cannot be graded')
    results: List[Dict[str, Any]] = []
    hits = 0
    misses = 0
    ungraded = 0

    for prediction in predictions:
        target_id = str(prediction.get("target_id", "")).upper().strip()
        pred_dir = str(prediction.get("direction", "")).upper().strip()
        snapshot_value = prediction.get("snapshot_value")
        pred_value = prediction.get("target_value")
        row = truth_values.get(target_id)

        base = {
            "target_id": target_id,
            "predicted_direction": pred_dir,
            "snapshot_value": snapshot_value,
            "predicted_value": pred_value,
            "unit": prediction.get("unit"),
        }
        if not row or not isinstance(snapshot_value, (int, float)):
            results.append({**base, "status": "UNGRADED"})
            ungraded += 1
            continue

        if row.get("__observation_contract") or "observed_at" in row:
            from datetime import datetime
            try:
                observed=datetime.fromisoformat(row["observed_at"].replace("Z","+00:00"))
                target_time=datetime.fromisoformat(prediction["target_time_iso"].replace("Z","+00:00"))
                available=datetime.fromisoformat(row["available_at"].replace("Z","+00:00"))
                if observed != target_time or row.get("unit") != prediction.get("unit") or available < observed:
                    raise ValueError("incompatible truth observation")
            except (ValueError,KeyError,TypeError):
                results.append({**base,"status":"UNGRADED"})
                ungraded += 1
                continue
        realized_value = row.get("Value")
        if not isinstance(realized_value, (int, float)):
            results.append({**base, "status": "UNGRADED"})
            ungraded += 1
            continue

        realized_delta = realized_value - snapshot_value
        realized_direction = "UP" if realized_delta > 0 else "DOWN" if realized_delta < 0 else "FLAT"
        direction_hit = pred_dir == realized_direction
        pred_error_pct = None
        abs_error = None
        realized_pct_move = None
        realized_pct_move = (realized_delta / max(abs(snapshot_value), 1.0)) * 100
        if isinstance(pred_value, (int, float)):
            abs_error = abs(pred_value - realized_value)
            pred_error_pct = ((pred_value - realized_value) / max(abs(snapshot_value), 1.0)) * 100

        if direction_hit:
            hits += 1
        else:
            misses += 1

        results.append(
            {
                **base,
                "status": "GRADED",
                "realized_value": realized_value,
                "realized_direction": realized_direction,
                "direction_hit": direction_hit,
                "pred_error_pct": pred_error_pct,
                "abs_error": abs_error,
                "realized_pct_move": realized_pct_move,

            }
        )

    total_graded = hits + misses
    hit_rate = (hits / total_graded) if total_graded else None
    return {
        "subject_run_id": subject_run_dir.name,
        "truth_run_id": truth_run_dir.name,
        "horizon_label": meta.get("horizon_label"),
        "target_time_iso": meta.get("target_time_iso"),
        "dominant_evidence_track": meta.get("dominant_evidence_track"),
        "prior_availability_assessment": meta.get("prior_availability_assessment"),
        "results": results,
        "summary": {
            "hits": hits,
            "misses": misses,
            "ungraded": ungraded,
            "graded": total_graded,
            "hit_rate": hit_rate,
        },
    }
