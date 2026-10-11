# SPDX-FileCopyrightText: 2026 Will Cook
# SPDX-License-Identifier: Apache-2.0
"""Project existing native study receipts; never execute, score, select or seal.

Uses only Python's standard library. The output excludes prompts, responses,
market observations and forecast text. Native reports remain score authority.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
import math
from pathlib import Path


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def finite_json(token):
    raise ValueError(f"nonfinite JSON constant: {token}")


class Snapshot:
    def __init__(self, root):
        self.root, self.seen = root.resolve(), {}

    def read(self, path):
        path = path.resolve()
        if not path.is_relative_to(self.root):
            raise ValueError("source must be within the standalone repository")
        raw = path.read_bytes()
        self.seen[path] = sha(raw)
        return json.loads(raw, parse_constant=finite_json)

    def bind(self, path):
        path = path.resolve()
        return {"path": str(path.relative_to(self.root)), "sha256": self.seen[path]}

    def check(self):
        for path, expected in self.seen.items():
            if sha(path.read_bytes()) != expected:
                raise ValueError("source changed during export; rerun after receipt settles")


def report_projection(report, spec, phase):
    """Validate reported common support; do not reconstruct missing scores."""
    fields = ("state", "phase", "scores", "issue_count", "per_issue_scores",
              "paired_issue_deltas", "per_issue_coverage", "pending_support",
              "decision", "decisions", "development_selected_candidate",
              "paired_delta_interpretation", "interpretation", "synthetic_fixture",
              "metric", "identity_basis", "evaluation_posture", "clustered_weeks",
              "live_mutation_permission")
    out = {key: report[key] for key in fields if key in report}
    if report.get("state") != "complete":
        if report.get("scores") is not None or report.get("paired_issue_deltas") is not None:
            raise ValueError("incomplete native report must not expose accepted scores")
        out.update(scores=None, per_issue_scores=None, paired_issue_deltas=None)
        return out
    issues = {row["issue_id"]: row for row in spec["issues"] if row["split"] == phase}
    registered = {row["candidate_id"] for row in spec["candidates"]}
    expected = registered
    if phase == "holdout":
        expected = {"baseline", report["development_selected_candidate"]}
    if not expected <= registered:
        raise ValueError("reported final candidate was not preregistered")
    scores, per_issue = report["scores"], report["per_issue_scores"]
    if set(scores) != expected or set(per_issue) != expected or report["issue_count"] != len(issues):
        raise ValueError("complete report differs from frozen comparison support")
    for candidate in expected:
        values = per_issue[candidate]
        if set(values) != set(issues):
            raise ValueError("complete report lacks exact issue support")
        for issue_id, value in values.items():
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
                raise ValueError("reported loss must be finite and nonnegative")
            targets = sorted(issues[issue_id]["target_ids"])
            coverage = report["per_issue_coverage"][candidate][issue_id]
            if (coverage["status"] != "complete" or coverage["expected_target_ids"] != targets
                    or coverage["scored_target_ids"] != targets or coverage["missing_target_ids"]
                    or coverage["expected_target_count"] != len(targets)
                    or coverage["scored_target_count"] != len(targets)
                    or coverage["forecast_target_count"] != len(targets)):
                raise ValueError("complete report lacks exact target support")
            delta = report["paired_issue_deltas"][candidate][issue_id]
            if not math.isclose(delta, value - per_issue["baseline"][issue_id], rel_tol=1e-12, abs_tol=1e-12):
                raise ValueError("reported paired delta differs from native issue scores")
        if not math.isclose(scores[candidate], sum(values.values()) / len(values), rel_tol=1e-12, abs_tol=1e-12):
            raise ValueError("reported aggregate does not preserve equal issue weighting")
    return out


def accounting(entries):
    known = [row for row in entries if row.get("cost") is not None]
    return {"attempts": len(entries),
            "responses": sum(row.get("provider_receipt") is not None for row in entries),
            "known_reported_cost_usd": str(sum((Decimal(row["cost"]) for row in known), Decimal(0))),
            "unknown_cost_count": len(entries) - len(known),
            "in_flight_count": sum(row["status"] == "attempt_started" for row in entries),
            "failed_count": sum(row["status"] == "failed" for row in entries),
            "requested_models": sorted({row["requested_model"] for row in entries}),
            "actual_models": sorted({row["provider_receipt"]["model"] for row in entries if row.get("provider_receipt")}),
            "requested_provider_slugs": sorted({row["requested_provider_slug"] for row in entries if row.get("requested_provider_slug")}),
            "actual_providers": sorted({row["actual_provider"] for row in entries if row.get("actual_provider")})}


def export(root, study, budget):
    snapshot = Snapshot(root)
    prep_path, spec_path = study / "preparation.json", study / "cohort/cohort.json"
    state_path = study / "cohort/cohort-state.json"
    prep, spec, state = (snapshot.read(path) for path in (prep_path, spec_path, state_path))
    spec_hash = snapshot.bind(spec_path)["sha256"]
    if prep["cohort_sha256"] != spec_hash or state["spec_hash"] != spec_hash:
        raise ValueError("preparation/state differ from frozen cohort")
    for base, mapping in ((root, spec["authorities"]), (study / "cohort", spec["frozen_hashes"])):
        for relative, expected in mapping.items():
            path = (base / relative).resolve()
            if not path.is_relative_to(root.resolve()) or sha(path.read_bytes()) != expected:
                raise ValueError("native authority or frozen input changed")
    ledger = snapshot.read(budget)
    phases = {}
    for phase in ("development", "holdout"):
        issues = [row for row in spec["issues"] if row["split"] == phase]
        arms = {}
        for candidate in spec["candidates"]:
            name = candidate["candidate_id"]
            keys = [f"{name}/{row['issue_id']}" for row in issues]
            attached = [state["attachments"][key] for key in keys if key in state["attachments"]]
            runs = {f"COHORT_{spec_hash[:12]}_{name}_{row['issue_id']}" for row in issues}
            entries = [row for row in ledger["entries"].values() if row["run_id"] in runs]
            arms[name] = {"expected_issue_count": len(issues),
                          "expected_target_count": sum(len(row["target_ids"]) for row in issues),
                          "attached_issue_count": len(attached),
                          "complete_native_issue_count": sum(row["state"] == "complete" for row in attached),
                          "accounting": accounting(entries)}
        report_path = study / "cohort" / ("development-comparison.json" if phase == "development" else "final-comparison.json")
        projection = {"state": "not_recorded", "scores": None, "paired_issue_deltas": None}
        source = None
        if report_path.exists():
            projection = report_projection(snapshot.read(report_path), spec, phase)
            source = snapshot.bind(report_path)
            if phase == "holdout" and (not state.get("final") or state["final"]["receipt"] != snapshot.read(report_path)):
                raise ValueError("final report differs from sealed native receipt")
        phases[phase] = {"native_execution_support": arms, "comparison": projection, "comparison_source": source}
    reference_path = study / "reference-baselines.json"
    reference = snapshot.read(reference_path)
    if snapshot.bind(reference_path)["sha256"] != prep["reference_baselines_sha256"]:
        raise ValueError("deterministic reference identity differs from preparation")
    snapshot.check()
    return {"schema": "zenith_paper_study_evidence_v1",
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "sources": [snapshot.bind(path) for path in (prep_path, spec_path, state_path, budget, reference_path)],
            "protocol": {"source_commit": prep["source_commit"], "cohort_sha256": spec_hash,
                         "profile": prep["profile"], "historical_exposure": prep["historical_exposure"],
                         "issues": [{key: row[key] for key in ("issue_id", "split", "time_anchor", "target_time", "horizon_id", "target_ids")} for row in spec["issues"]],
                         "candidates": [{key: row.get(key) for key in ("candidate_id", "model", "actual_model", "provider", "provider_slug", "execution_kind", "node_hashes")} for row in spec["candidates"]],
                         "authorities": spec["authorities"], "frozen_hashes": spec["frozen_hashes"],
                         "policy_hashes": {row["candidate_id"]: row["reasoning_policy_payload"]["policy_sha256"] for row in spec["candidates"]}},
            "phases": phases, "final_seal_recorded": state.get("final") is not None,
            "deterministic_references": {key: reference[key] for key in ("metric", "model_arms", "scope", "scores")},
            "shared_budget_snapshot": {**{key: ledger.get(key) for key in ("halted", "total_reported_cost_usd", "total_reserved_usd")},
                                       "limits": {key: ledger["limits"][key] for key in ("max_cost_usd", "max_calls", "max_output_tokens")},
                                       "accounting": accounting(list(ledger["entries"].values()))},
            "claim_boundary": "Read-only projection of native receipts. Native completion is not truth-score completion. Unknown costs are not zero; in-flight reservations are not charges. References are not model arms. Missing comparisons remain unavailable; no new evaluation, selection, seal, significance or causal attribution is performed."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--study", type=Path, required=True)
    parser.add_argument("--budget", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path(__file__).with_name("study-evidence.json"))
    args = parser.parse_args()
    root = Path(__file__).resolve().parent.parent
    output = args.output.resolve()
    if not output.is_relative_to(root / "paper"):
        raise ValueError("paper evidence output must remain within paper/")
    result = export(root, args.study.resolve(), args.budget.resolve())
    output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"output": str(output), "cohort_sha256": result["protocol"]["cohort_sha256"],
                      "comparison_states": {key: value["comparison"]["state"] for key, value in result["phases"].items()}}))


if __name__ == "__main__":
    main()
