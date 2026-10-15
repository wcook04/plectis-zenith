"""
[PURPOSE]
- Teleology: Verifies the backend lab-contract audit catches the hard-fail patterns operators care about before lab artifacts are treated as coherent runtime state.
- Mechanism: Writes minimal artifact sets that express known contradiction and annotation-collapse failures, then asserts the audit report classifies them correctly.
- When-needed: Open when lab artifacts look internally inconsistent and a debugger needs the narrow regression suite that proves which hard-fail codes should fire.
- Escalates-to: system/lib/lab_contract_audit.py
- Navigation-group: server_backend

[INTERFACE]
- Inputs: Temporary artifact directories containing synthetic lab node outputs.
- Outputs: Assertion-only verdicts over the audit report returned by `compute_lab_contract_audit`.

[FLOW]
- Teleology: Keep audit-policy regressions attached to the smallest artifact sets that reproduce them.
- Reads: `system.lib.lab_contract_audit.compute_lab_contract_audit` plus JSON or string payloads written into temporary artifact files.
- Writes: Temporary `<node_id>.json` artifacts inside a test-local directory.
- Couples: The test fixtures mirror the artifact schema expected by the audit implementation, so renamed fail codes or node contracts must be updated together.

[DEPENDENCIES]
- Required: system.lib.lab_contract_audit (contract audit implementation under test).

[CONSTRAINTS]
- Forbid: Treating these fixtures as production artifact examples; they are intentionally minimal reproductions of audit-edge cases.
- Orders: Artifact files must be written before the audit runs, and each scenario must isolate its own temp directory.
- Non-goal: Full lab workflow coverage; the cohort is scoped to operator-visible audit failures.
"""
from __future__ import annotations

import json
from pathlib import Path

from system.lib.lab_contract_audit import compute_lab_contract_audit


def _write_artifact(artifacts_dir: Path, node_id: str, data) -> None:
    """
    [ACTION]
    - Teleology: Normalize the temporary audit-fixture shape so each test can express one contract failure without repeating file-write boilerplate.
    - Reads: The provided node id and synthetic data payload.
    - Writes: `<artifacts_dir>/<node_id>.json` containing the audit-friendly `{id, data}` envelope.
    - Guarantee: Creates the artifact directory if needed and persists one node payload in the structure `compute_lab_contract_audit` expects.
    - Fails: OSError if the temporary directory cannot be created or written.
    - When-needed: Open when a debugger needs to confirm the exact on-disk envelope these audit tests hand to `compute_lab_contract_audit`.
    - Escalates-to: system/lib/lab_contract_audit.py::compute_lab_contract_audit
    - Navigation-group: server_backend
    """
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    (artifacts_dir / f"{node_id}.json").write_text(
        json.dumps({"id": node_id, "data": data}),
        encoding="utf-8",
    )


def test_contract_audit_flags_contradiction_amnesia(tmp_path: Path) -> None:
    """
    [ACTION]
    - Teleology: Lock the audit rule that detects when cross-correlation artifacts encode a conflict the director layer later behaves as if it never existed.
    - Reads: The contradiction-bearing synthetic artifacts written in the test body and the audit result returned from them.
    - Writes: None beyond the temporary fixtures.
    - Guarantee: Confirms contradiction amnesia is promoted to a red audit with the `CONTRADICTION_AMNESIA` hard-fail code.
    - Fails: AssertionError if the audit stops surfacing the contradiction-amnesia condition.
    - When-needed: Open when lab cross-correlation outputs disagree with downstream director behavior and operators need the exact audit regression that should catch it.
    - Escalates-to: system/lib/lab_contract_audit.py::compute_lab_contract_audit
    """
    artifacts = tmp_path / "artifacts"
    _write_artifact(
        artifacts,
        "lab_cross_corr_v1",
        {
            "swarms": [],
            "bifurcations": [
                {
                    "id": "bf_1",
                    "name": "credit split",
                    "lanes": ["ENVIRONMENT", "MEASUREMENTS"],
                    "summary": "Conflict exists.",
                }
            ],
            "orphans": [],
            "confidence_asymmetries": [],
        },
    )
    _write_artifact(
        artifacts,
        "lab_cross_corr_v2",
        {
            "target_swarms": [],
            "directional_conflicts": [],
            "solo_targets": [],
            "thesis_stress": [],
            "valid_prediction_targets": ["SIGNAL_A"],
        },
    )
    _write_artifact(artifacts, "lab_decide", {"epicentre_thesis": "locked thesis"})
    _write_artifact(
        artifacts,
        "lab_director",
        {"epicentre_thesis": "locked thesis", "predictions_t": [{"target_id": "SIGNAL_A"}]},
    )

    audit = compute_lab_contract_audit(artifacts)
    assert audit["status"] == "red"
    assert "CONTRADICTION_AMNESIA" in audit["hard_fails"]


def test_contract_audit_flags_phase2_annotation_collapse(tmp_path: Path) -> None:
    artifacts = tmp_path / "artifacts"
    _write_artifact(
        artifacts,
        "lab_miner_v2_measurements",
        "{SIGNAL_A, +2.1%, Momentum is strong. Momentum is strong., C:HIGH}",
    )
    _write_artifact(
        artifacts,
        "lab_cross_corr_v2",
        {
            "target_swarms": [],
            "directional_conflicts": [],
            "solo_targets": [],
            "thesis_stress": [],
            "valid_prediction_targets": [],
        },
    )
    _write_artifact(artifacts, "lab_decide", {"epicentre_thesis": "same"})
    _write_artifact(artifacts, "lab_director", {"epicentre_thesis": "same", "predictions_t": []})

    audit = compute_lab_contract_audit(artifacts)
    assert audit["status"] == "red"
    assert "ANNOTATION_COLLAPSE" in audit["hard_fails"]


def test_contract_audit_question_mark_scan_excludes_director_output(tmp_path: Path) -> None:
    artifacts = tmp_path / "artifacts"
    _write_artifact(
        artifacts,
        "lab_cross_corr_v1",
        {
            "swarms": [],
            "bifurcations": [],
            "orphans": [],
            "confidence_asymmetries": [],
        },
    )
    _write_artifact(
        artifacts,
        "lab_cross_corr_v2",
        {
            "target_swarms": [],
            "directional_conflicts": [],
            "solo_targets": [],
            "thesis_stress": [],
            "valid_prediction_targets": ["SIGNAL_A"],
        },
    )
    _write_artifact(artifacts, "lab_decide", {"epicentre_thesis": "locked thesis"})
    _write_artifact(
        artifacts,
        "lab_director",
        {
            "epicentre_thesis": "locked thesis",
            "predictions_t": [{"target_id": "SIGNAL_A"}],
            "forecast_rationale": "Question in semantic prose is allowed here?",
        },
    )

    audit = compute_lab_contract_audit(artifacts)
    assert "QUESTION_MARK_OUTPUT" not in audit["hard_fails"]


def test_contract_audit_refuses_system_fusion_candidate_claims(tmp_path: Path) -> None:
    artifacts = tmp_path / "artifacts"
    _write_artifact(
        artifacts,
        "lab_director",
        {
            "epicentre_thesis": "same",
            "predictions_t": [],
            "candidate_situation_claims": [
                {
                    "claim_id": "c1",
                    "situation_id": "environment_event_x_observation_response",
                    "lanes": ["ENVIRONMENT", "MEASUREMENTS"],
                    "attempted_claim": "Environment event validates observation response.",
                },
                {
                    "claim_id": "c2",
                    "situation_id": "subsystems_value_move_x_nav_basket_claim",
                    "lanes": ["SUBSYSTEMS"],
                    "attempted_claim": "SUBSYSTEMS value move implies NAV basket pressure.",
                },
                {
                    "claim_id": "c3",
                    "situation_id": "interventions_expectation_x_environment_observation_situation",
                    "lanes": ["INTERVENTIONS", "ENVIRONMENT", "MEASUREMENTS"],
                    "attempted_claim": "Prediction system expectation validates environment observation situation.",
                },
            ],
        },
    )

    audit = compute_lab_contract_audit(artifacts)

    assert audit["status"] == "red"
    assert "SYSTEM_FUSION_READINESS_REFUSAL" in audit["hard_fails"]
    refusals = audit["details"]["system_fusion_readiness_refusals"]
    assert [row["claim_id"] for row in refusals] == ["c1", "c2", "c3"]
    assert all(row["consumer_name"] == "lab_director" for row in refusals)
    assert "observation_expected_return_event_window_missing" in refusals[0][
        "refusal_reasons"
    ]
    assert "subsystems_nav_provider_gap" in refusals[1]["refusal_reasons"]
    assert "interventions_resolved_archive_target_pairing_missing" in refusals[2][
        "refusal_reasons"
    ]
