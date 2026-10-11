"""
[PURPOSE]
- Teleology: Aggregate diff and trace results into a single deterministic ObservationReport
  sidecar artifact per run. For Oracle, this is additive support over the primary four-artifact
  surface rather than the main deliverable.
- Mechanism: Calls diff_evidence + diff_predictions (observer_diff) and trace_all (observer_trace)
  for every missed/extra ID; combines into ObservationReport; persists as observation_report.json.

[INTERFACE]
- Reads: lab_cp2 and oracle_cp2 dicts (parsed CP2 JSON objects); run_dir for artifact loading.
- Writes: run_dir/artifacts/observation_report.json (sorted keys, 2-space indent).
- Exports: ObservationReport, generate_observation_report.

[FLOW]
- generate_observation_report: extract evidence+predictions from both CP2 dicts; call diff funcs;
  collect missed+extra ledger_ids; trace all of them; build ObservationReport; persist; return.
- Summary counts must reconcile exactly with diff output lengths (verified before writing).

[DEPENDENCIES]
- Internal: system.lib.observer_diff (diff_evidence, diff_predictions).
- Internal: system.lib.observer_trace (trace_all).

[CONSTRAINTS]
- Output is written exclusively to run_dir/artifacts/observation_report.json.
- JSON output uses sort_keys=True and indent=2 for byte-stable ordering.
- summary counts must reconcile: summary['missed'] == len(evidence_diff.missed_ledger_ids), etc.
- No K-classes, no semantic blame, no automated routing — pure factual aggregation.
- generate_observation_report never raises; on IO failure it returns the report without writing.
- run_id is derived from run_dir.name.
- timestamp is UTC ISO-8601 (datetime.now(timezone.utc).isoformat(), +00:00 → Z).
- When-needed: Open when runtime or diff tooling needs the canonical observation_report sidecar contract that aggregates evidence diffs, prediction diffs, and ledger traces.
- Escalates-to: system/lib/observer_diff.py::diff_evidence; system/lib/observer_trace.py::trace_all; tools/diff/observer_diff_master.py
- Navigation-group: kernel_lib
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from system.lib.observer_diff import (
    EvidenceDiffResult,
    PredictionDiffResult,
    diff_evidence,
    diff_predictions,
)
from system.lib.observer_trace import TraceResult, trace_all


# ---------------------------------------------------------------------------
# ObservationReport
# ---------------------------------------------------------------------------

@dataclass
class ObservationReport:
    """
    [ROLE]
    - Deterministic diff + trace sidecar without semantic interpretation.
    - Contains evidence_diff, prediction_diff, per-ID traces, and reconciled summary counts.
    """
    run_id: str
    timestamp: str
    evidence_diff: EvidenceDiffResult
    prediction_diff: PredictionDiffResult
    traces: List[TraceResult]
    summary: Dict[str, int]
    oracle_v1: Optional[Dict[str, Any]] = None

    def to_json_dict(self) -> Dict[str, Any]:
        """
        [ACTION]
        - Return a fully JSON-serializable dict representation of this ObservationReport.
        - All nested objects are serialized via their own to_json_dict methods.
        """
        payload = {
            "run_id": self.run_id,
            "timestamp": self.timestamp,
            "evidence_diff": self.evidence_diff.to_json_dict(),
            "prediction_diff": self.prediction_diff.to_json_dict(),
            "traces": [t.to_json_dict() for t in self.traces],
            "summary": dict(sorted(self.summary.items())),
        }
        if isinstance(self.oracle_v1, dict):
            payload["oracle_v1"] = _stable_json_copy(self.oracle_v1)
        return payload


def _stable_json_copy(value: Any) -> Any:
    """Recursively sort mapping keys while preserving list order."""
    if isinstance(value, dict):
        return {
            str(key): _stable_json_copy(val)
            for key, val in sorted(value.items(), key=lambda item: str(item[0]))
        }
    if isinstance(value, list):
        return [_stable_json_copy(item) for item in value]
    return value


# ---------------------------------------------------------------------------
# Generator
# ---------------------------------------------------------------------------

def generate_observation_report(
    lab_cp2: Dict[str, Any],
    oracle_cp2: Dict[str, Any],
    run_dir: Path,
    *,
    persist: bool = True,
    report_run_id: Optional[str] = None,
    oracle_v1: Optional[Dict[str, Any]] = None,
) -> ObservationReport:
    """
    [ACTION]
    - Teleology: Build the deterministic observation-report sidecar for one Lab-versus-Oracle comparison run.
    - Mechanism: Extract evidence and prediction arrays from the CP2 payloads, compute observer diffs, trace every missed or extra ledger_id through Lab artifacts, reconcile summary counts, and optionally persist the resulting ObservationReport.
    - Guarantee: Returns an ObservationReport even when persistence fails, and never raises.
    - Fails: None.
    - When-needed: Open when engine or diff tooling needs the exact observation_report generation contract instead of coordinating diff and trace helpers manually.
    - Escalates-to: system/lib/observer_diff.py::diff_evidence; system/lib/observer_trace.py::trace_all; tools/diff/observer_diff_master.py
    """
    run_dir = Path(run_dir)

    lab_evidence: List[Dict] = (
        lab_cp2.get("evidence_dictionary", [])
        if isinstance(lab_cp2.get("evidence_dictionary"), list)
        else []
    )
    oracle_evidence: List[Dict] = (
        oracle_cp2.get("evidence_dictionary", [])
        if isinstance(oracle_cp2.get("evidence_dictionary"), list)
        else []
    )
    lab_preds: List[Dict] = (
        lab_cp2.get("predictions_t", [])
        if isinstance(lab_cp2.get("predictions_t"), list)
        else []
    )
    oracle_preds: List[Dict] = (
        oracle_cp2.get("predictions_t", [])
        if isinstance(oracle_cp2.get("predictions_t"), list)
        else []
    )

    evidence_diff = diff_evidence(lab_evidence, oracle_evidence)
    prediction_diff = diff_predictions(lab_preds, oracle_preds)

    ids_to_trace: Set[str] = (
        set(evidence_diff.missed_ledger_ids) | set(evidence_diff.extra_ledger_ids)
    )
    traces = trace_all(run_dir, ids_to_trace)

    summary: Dict[str, int] = {
        "missed": len(evidence_diff.missed_ledger_ids),
        "extra": len(evidence_diff.extra_ledger_ids),
        "overlap": len(evidence_diff.overlap_ledger_ids),
        "pred_diverge": len(prediction_diff.divergent),
        "pred_extra": len(prediction_diff.extra_targets),
        "pred_match": len(prediction_diff.matching),
        "pred_missing": len(prediction_diff.missing_targets),
        "traces": len(traces),
    }

    run_id = str(report_run_id).strip() if report_run_id else run_dir.name
    timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    report = ObservationReport(
        run_id=run_id,
        timestamp=timestamp,
        evidence_diff=evidence_diff,
        prediction_diff=prediction_diff,
        traces=traces,
        summary=summary,
        oracle_v1=_stable_json_copy(oracle_v1) if isinstance(oracle_v1, dict) else None,
    )

    # Persist to artifacts/observation_report.json
    if persist:
        try:
            artifacts_dir = run_dir / "artifacts"
            artifacts_dir.mkdir(parents=True, exist_ok=True)
            output_path = artifacts_dir / "observation_report.json"
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(report.to_json_dict(), f, indent=2, sort_keys=True)
        except Exception:
            pass  # Return report even if write fails

    return report
