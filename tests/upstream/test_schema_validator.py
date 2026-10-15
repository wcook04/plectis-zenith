"""
[PURPOSE]
- Teleology: Validate CP1 and CP2 schema validators deterministically across happy and failure paths.
- Mechanism: Inline fixtures; assert-helper pattern; tmp_path for CP2 target_id-universe tests.
- Non-goal: Engine integration, retry loop, or artifact persistence (covered in later phases).

[INTERFACE]
- Tests: CP1, CP2, cross-correlation, hindsight, critique, oracle-meta, and validation-result contract coverage.
- Reads: system/lib/schema_validator.py validator functions plus tmp_path artifact fixtures for target_id-universe checks.
- Writes: Temporary measurements and SUBSYSTEMS feed artifacts under tmp_path only.

[FLOW]
- Fixture helpers build minimal valid payloads and targeted invalid variants.
- CP1 and CP2 tests assert structural, citation, direction, timing, and universe-validation semantics.
- Downstream tests pin the auxiliary validator surfaces and ValidationResult error ordering and deduplication behavior.

[DEPENDENCIES]
- Couples: system/lib/schema_validator.py owns the validator and ValidationResult behavior exercised here.
- Couples: codex/standards/observe_apply/observe_apply_authority_index.json and related feed/runtime contracts shape the context-dependent CP2 validation expectations.

[CONSTRAINTS]
- All tests use fixed inline fixtures and tmp_path-scoped artifact writes only.
- Orders: Fixture helpers feed the validators directly; the suite never routes through engine or persistence layers.
- When-needed: Open when a server-backend regression needs the fixed-fixture schema expectations for CP1, CP2, or adjacent validator contracts before changing validator logic.
- Escalates-to: system/lib/schema_validator.py; codex/standards/observe_apply/observe_apply_authority_index.json; system/server/tests/test_runtime_contracts.py
- Navigation-group: server_backend
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

import pytest

from system.lib.schema_validator import (
    ValidationResult,
    validate_oracle_cp2_meta,
    validate_cp2_critique,
    validate_cp1,
    validate_cp2,
    validate_cross_corr_v1,
    validate_cross_corr_v2,
    validate_prediction_reconciliation,
    validate_realized_hindsight_brief,
)


# ---------------------------------------------------------------------------
# Assert helpers
# ---------------------------------------------------------------------------

def assert_ok(result: ValidationResult) -> None:
    assert result.ok, f"Expected ok=True but got errors: {result.errors}"
    assert result.errors == []


def assert_has_error(result: ValidationResult, code: str) -> None:
    assert not result.ok, f"Expected ok=False but result was ok"
    matching = [e for e in result.errors if e.startswith(code)]
    assert matching, f"Expected error code {code!r} in {result.errors}"


def assert_errors_exact(result: ValidationResult, codes: List[str]) -> None:
    assert not result.ok
    result_codes = sorted({e.split(":")[0] for e in result.errors})
    assert result_codes == sorted(codes), f"Expected codes {sorted(codes)} got {result_codes}"


# ---------------------------------------------------------------------------
# Fixture builders
# ---------------------------------------------------------------------------

def _words(n: int, cite: str = "") -> str:
    """Generate n whitespace-separated tokens, optionally appending a citation string."""
    base = " ".join(f"word{i}" for i in range(n))
    return f"{base} {cite}".strip() if cite else base


def _minimal_evidence_cp1() -> List[Dict[str, Any]]:
    """Minimal valid evidence with [1] and [2] ref_ids."""
    return [
        {
            "ref_id": "[1]",
            "ledger_id": "M_DEADBEEF",
            "subject": "ENVIRONMENT_REGIME",
            "signal_summary": "A environment signal.",
        },
        {
            "ref_id": "[2]",
            "ledger_id": "S_CAFEBABE",
            "subject": "SUBSYSTEM_C",
            "signal_summary": "SUBSYSTEM_C measurements signal.",
        },
    ]


def _minimal_cp1_payload() -> Dict[str, Any]:
    """Minimal valid CP1 payload: 150+ words, all citations resolved."""
    return {
        "evidence_dictionary": _minimal_evidence_cp1(),
        "epicentre_thesis": _words(148, "[1] [2]"),
    }


def _minimal_cp2_payload() -> Dict[str, Any]:
    """Minimal valid CP2 payload (no subject_run_dir context needed for structure)."""
    base = _minimal_cp1_payload()
    base["predictions_t"] = [{
        "target_id": "SUBSYSTEM_C",
        "direction": "DOWN",
        "unit": "dimensionless", "snapshot_value": 100.0,
        "target_value": 95.0,
        "snapshot_time": "2026-03-04T00:00:00+00:00",
        "target_time_iso": "2026-03-04T21:00:00+00:00",
        "invalidation": "Invalidated if SUBSYSTEM_C reclaims VWAP and holds above 197 by 15:30 ET.",
    }]
    # forecast_rationale: base=75, per_pred=30 × 1 prediction = 105 words minimum
    base["forecast_rationale"] = _words(103, "[1] [2]")
    return base


def _write_measurements_feed(artifacts_dir: Path, target_ids: List[str]) -> None:
    """Write a minimal MEASUREMENTS feed artifact to artifacts_dir/global_measurements_feed.json."""
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    feed = {
        "metadata": {"as_of": "2026-01-01"},
        "data": {
            "topic": {
                "row": {
                    "columns": ["target_id", "Value"],
                    "rows": [[t, "100.0"] for t in target_ids],
                }
            }
        },
    }
    (artifacts_dir / "global_measurements_feed.json").write_text(json.dumps(feed))


def _minimal_cross_corr_v1_payload() -> Dict[str, Any]:
    return {
        "swarms": [
            {
                "id": "sw_1",
                "name": "Energy Cohort",
                "lanes": ["MEASUREMENTS", "SUBSYSTEMS", "EVENTS"],
                "subjects": ["SIGNAL_A", "CVX"],
                "summary": "Multiple lanes align on the same energy cohort.",
            }
        ],
        "bifurcations": [
            {
                "id": "bf_1",
                "name": "Credit Divergence",
                "lanes": ["ENVIRONMENT", "MEASUREMENTS"],
                "subjects": ["HY_OAS", "KRE"],
                "summary": "Environment and observation lanes conflict on credit tone.",
            }
        ],
        "orphans": [
            {
                "id": "or_1",
                "name": "Single-lane Signal",
                "lanes": ["INTERVENTIONS"],
                "subjects": ["event_slug"],
                "summary": "Only one lane carries this signal.",
            }
        ],
        "confidence_asymmetries": [
            {
                "id": "ca_1",
                "name": "Confidence Mix",
                "lanes": ["MEASUREMENTS", "SUBSYSTEMS"],
                "subjects": ["SIGNAL_A"],
                "summary": "Lanes disagree on confidence strength.",
            }
        ],
    }


def _minimal_cross_corr_v2_payload() -> Dict[str, Any]:
    return {
        "target_swarms": [
            {
                "id": "ts_1",
                "name": "Energy Targets",
                "target_ids": ["SIGNAL_A", "CVX"],
                "lanes": ["MEASUREMENTS", "SUBSYSTEMS"],
                "direction_consensus": "INCREASE",
                "summary": "Multiple lanes converge on energy target_ids.",
            }
        ],
        "directional_conflicts": [
            {
                "id": "dc_1",
                "name": "Defense Conflict",
                "target_ids": ["RTX"],
                "lanes": ["MEASUREMENTS", "SUBSYSTEMS"],
                "direction_consensus": "CONTESTED",
                "summary": "Lanes disagree on direction for RTX.",
            }
        ],
        "solo_targets": [
            {
                "id": "so_1",
                "name": "Solo Name",
                "target_ids": ["UAL"],
                "lanes": ["EVENTS"],
                "direction_consensus": "DECREASE",
                "summary": "One lane highlights UAL.",
            }
        ],
        "thesis_stress": [
            {
                "id": "st_1",
                "name": "Stress Check",
                "target_ids": ["NONE"],
                "lanes": ["ENVIRONMENT"],
                "direction_consensus": "N/A",
                "summary": "Environment regime dampens thesis confidence.",
            }
        ],
        "valid_prediction_targets": ["SIGNAL_A", "CVX", "UAL"],
    }


def _minimal_realized_hindsight_brief_payload() -> Dict[str, Any]:
    return {
        "status": "AVAILABLE",
        "realized_dominant_force": "Oil shock continuation with partial residual change.",
        "regime_summary": "Energy led realized upside while residual breadth stayed constrained.",
        "driver_classification": [
            {
                "driver": "Oil shock continuation",
                "classification": "PARTIAL_CHANGE",
                "why": "Continuation was visible at T-n, but the final magnitude still surprised.",
                "supporting_lanes": ["MEASUREMENTS", "SUBSYSTEMS", "ENVIRONMENT"],
                "affected_targets": ["SIGNAL_A", "XLE"],
            }
        ],
        "already_observed_packages": ["Baseline energy continuation"],
        "surprise_packages": ["Residual supply squeeze"],
        "partial_change_packages": ["Oil shock continuation"],
        "prediction_target_outcomes": [
            {
                "target_id": "SIGNAL_A",
                "what_happened": "SIGNAL_A rallied but by less than the forward target implied.",
                "availability_judgement": "PARTIAL_CHANGE",
            }
        ],
    }


def _minimal_cp2_critique_payload() -> Dict[str, Any]:
    return {
        "status": "AVAILABLE",
        "root_failure_mode": "valued_in_continuation_bias",
        "critique_items": [
            {
                "scope": "prediction",
                "target_or_claim": "SIGNAL_A",
                "subject_grounding_refs": ["[1]", "S_CAFEBABE"],
                "realized_refs": ["prediction_reconciliation:SIGNAL_A"],
                "error_class": "PREDICTION_DRIFT",
                "what_was_wrong": "The target level overstated residual upside.",
                "comparison_to_ideal": "Ideal CP2 should have kept the name but narrowed the magnitude.",
            }
        ],
        "comparison_to_ideal_summary": "Lab generally found the right lane but overshot the consequence sizing.",
        "reconstruction_guidance": {
            "dominant_force": "Residual energy continuation",
            "prefer_targets": ["SIGNAL_A"],
            "avoid_targets": ["UAL"],
            "eligible_ledger_ids": ["S_CAFEBABE"],
        },
    }


def _minimal_prediction_reconciliation_payload() -> Dict[str, Any]:
    return {
        "status": "AVAILABLE",
        "subject_run_id": "RUN_SUBJECT",
        "truth_run_id": "RUN_TRUTH",
        "rows": [
            {
                "target_id": "SIGNAL_A",
                "target_kind": "MEASUREMENTS",
                "prediction_direction": "UP",
                "subject_snapshot_value": 100.0,
                "predicted_target_value": 110.0,
                "realized_truth_value": 105.0,
                "absolute_delta": 5.0,
                "percent_delta": 4.545454545,
                "directional_correct": True,
                "rank": 1,
            }
        ],
        "summary": {
            "row_count": 1,
            "directionally_correct_count": 1,
            "directionally_incorrect_count": 0,
            "largest_absolute_miss_target": "SIGNAL_A",
            "largest_percent_miss_target": "SIGNAL_A",
        },
    }


# ---------------------------------------------------------------------------
# CP1 — happy path
# ---------------------------------------------------------------------------

def test_validate_cp1_happy_path() -> None:
    result = validate_cp1(_minimal_cp1_payload())
    assert_ok(result)


def test_validate_cp1_errors_are_sorted_and_deduped() -> None:
    # Two separate errors should be sorted alphabetically
    payload = _minimal_cp1_payload()
    payload.pop("evidence_dictionary")
    payload.pop("epicentre_thesis")
    result = validate_cp1(payload)
    assert not result.ok
    assert result.errors == sorted(set(result.errors))


# ---------------------------------------------------------------------------
# CP1 — missing fields
# ---------------------------------------------------------------------------

def test_validate_cp1_missing_evidence_dictionary() -> None:
    payload = _minimal_cp1_payload()
    payload.pop("evidence_dictionary")
    assert_has_error(validate_cp1(payload), "MISSING_FIELD")


def test_validate_cp1_missing_epicentre_thesis() -> None:
    payload = _minimal_cp1_payload()
    payload.pop("epicentre_thesis")
    assert_has_error(validate_cp1(payload), "MISSING_FIELD")


def test_validate_cp1_not_a_dict() -> None:
    assert_has_error(validate_cp1("not a dict"), "MISSING_FIELD")


def test_validate_cp1_optional_bifurcation_resolutions_validated_when_present() -> None:
    payload = _minimal_cp1_payload()
    payload["bifurcation_resolutions"] = [
        {
            "bifurcation_id": "bf_1",
            "selected_side": "energy_shock",
            "rationale": "Cross-lane evidence is stronger for supply shock.",
            "opposite_side_invalidation": "If environment disinflation persists and crude mean-reverts rapidly.",
        }
    ]
    assert_ok(validate_cp1(payload))


# ---------------------------------------------------------------------------
# CP1 — ref_id validation
# ---------------------------------------------------------------------------

def test_validate_cp1_invalid_ref_id_bare_number() -> None:
    payload = _minimal_cp1_payload()
    payload["evidence_dictionary"][0]["ref_id"] = "1"  # missing brackets
    assert_has_error(validate_cp1(payload), "INVALID_REF_ID")


def test_validate_cp1_invalid_ref_id_zero() -> None:
    payload = _minimal_cp1_payload()
    payload["evidence_dictionary"][0]["ref_id"] = "[0]"
    assert_has_error(validate_cp1(payload), "INVALID_REF_ID")


def test_validate_cp1_invalid_ref_id_leading_zero() -> None:
    payload = _minimal_cp1_payload()
    payload["evidence_dictionary"][0]["ref_id"] = "[01]"
    assert_has_error(validate_cp1(payload), "INVALID_REF_ID")


def test_validate_cp1_duplicate_ref_id() -> None:
    payload = _minimal_cp1_payload()
    payload["evidence_dictionary"][1]["ref_id"] = "[1]"  # same as first entry
    assert_has_error(validate_cp1(payload), "DUPLICATE_REF_ID")


# ---------------------------------------------------------------------------
# CP1 — ledger_id validation
# ---------------------------------------------------------------------------

def test_validate_cp1_invalid_ledger_id_format() -> None:
    payload = _minimal_cp1_payload()
    payload["evidence_dictionary"][0]["ledger_id"] = "DEADBEEF"  # missing prefix
    assert_has_error(validate_cp1(payload), "INVALID_LEDGER_ID")


def test_validate_cp1_invalid_ledger_id_lowercase() -> None:
    payload = _minimal_cp1_payload()
    payload["evidence_dictionary"][0]["ledger_id"] = "M_deadbeef"  # lowercase hex
    assert_has_error(validate_cp1(payload), "INVALID_LEDGER_ID")


def test_validate_cp1_invalid_ledger_id_unknown_prefix() -> None:
    payload = _minimal_cp1_payload()
    payload["evidence_dictionary"][0]["ledger_id"] = "Z_DEADBEEF"  # Z not in allowed set
    assert_has_error(validate_cp1(payload), "INVALID_LEDGER_ID")


def test_validate_cp1_accepts_subsystems_ledger_id_prefix_from_config() -> None:
    payload = _minimal_cp1_payload()
    payload["evidence_dictionary"][0]["ledger_id"] = "E_DEADBEEF"
    assert_ok(validate_cp1(payload))


def test_validate_cp1_ledger_prefixes_follow_config_map(monkeypatch: pytest.MonkeyPatch) -> None:
    import system.lib.schema_validator as schema_validator

    custom_cfg = {
        "epicentre_thesis_min_words": 150,
        "forecast_rationale_base_words": 75,
        "forecast_rationale_per_prediction_words": 30,
        "lane_prefix_map": {
            "Q": "QUANT",
            "S": "MEASUREMENTS",
        },
    }
    monkeypatch.setattr(schema_validator, "_load_config", lambda: custom_cfg)

    payload = _minimal_cp1_payload()
    payload["evidence_dictionary"][0]["ledger_id"] = "Q_DEADBEEF"
    assert_ok(schema_validator.validate_cp1(payload))

    payload["evidence_dictionary"][0]["ledger_id"] = "M_DEADBEEF"
    assert_has_error(schema_validator.validate_cp1(payload), "INVALID_LEDGER_ID")


def test_validate_cp1_duplicate_ledger_id() -> None:
    payload = _minimal_cp1_payload()
    payload["evidence_dictionary"][1]["ledger_id"] = "M_DEADBEEF"  # same as first entry
    assert_has_error(validate_cp1(payload), "DUPLICATE_LEDGER_ID")


# ---------------------------------------------------------------------------
# CP1 — citation validation
# ---------------------------------------------------------------------------

def test_validate_cp1_unresolved_citation() -> None:
    payload = _minimal_cp1_payload()
    # epicentre_thesis cites [3] but evidence only has [1] and [2]
    payload["epicentre_thesis"] = _words(148, "[1] [3]")
    assert_has_error(validate_cp1(payload), "CITATION_UNRESOLVED")


def test_validate_cp1_malformed_citation_range() -> None:
    payload = _minimal_cp1_payload()
    payload["epicentre_thesis"] = _words(148, "[1-3]")
    assert_has_error(validate_cp1(payload), "MALFORMED_CITATION")


def test_validate_cp1_malformed_citation_csv() -> None:
    payload = _minimal_cp1_payload()
    payload["epicentre_thesis"] = _words(148, "[1, 2]")
    assert_has_error(validate_cp1(payload), "MALFORMED_CITATION")


def test_validate_cp1_malformed_citation_leading_zero() -> None:
    payload = _minimal_cp1_payload()
    payload["epicentre_thesis"] = _words(148, "[01]")
    assert_has_error(validate_cp1(payload), "MALFORMED_CITATION")


# ---------------------------------------------------------------------------
# CP1 — word count
# ---------------------------------------------------------------------------

def test_validate_cp1_below_min_words() -> None:
    payload = _minimal_cp1_payload()
    payload["epicentre_thesis"] = _words(10, "[1]")  # way below 150
    assert_has_error(validate_cp1(payload), "BELOW_MIN_WORD_COUNT")


def test_validate_cp1_exactly_min_words() -> None:
    # 148 words + "[1]" + "[2]" = 150 tokens — should pass
    payload = _minimal_cp1_payload()
    payload["epicentre_thesis"] = _words(148, "[1] [2]")
    assert_ok(validate_cp1(payload))


# ---------------------------------------------------------------------------
# CP2 — happy path (no context)
# ---------------------------------------------------------------------------

def test_validate_cp2_happy_path_no_context() -> None:
    # Without subject_run_dir, OUT_OF_UNIVERSE check is skipped
    result = validate_cp2(_minimal_cp2_payload())
    assert_ok(result)


def test_validate_cp2_tolerates_optional_oracle_meta() -> None:
    payload = _minimal_cp2_payload()
    payload["oracle_meta"] = {
        "truth_influence_refs": ["realized_hindsight_brief:oil_shock"],
        "realized_diff_refs": ["prediction_reconciliation:SUBSYSTEM_C"],
        "explicit_exclusions": [
            {
                "kind": "TRUTH_ONLY_SIGNAL",
                "ref": "oracle_explain:1",
                "reason": "Helpful hindsight context but not admissible grounding.",
            }
        ],
        "oracle_hindsight_notes": ["Residual upside was real but smaller than the forward target."],
    }
    result = validate_cp2(payload)
    assert_ok(result)


# ---------------------------------------------------------------------------
# CP2 — happy path (with target_id context)
# ---------------------------------------------------------------------------

def test_validate_cp2_happy_path_with_context(tmp_path: Path) -> None:
    _write_measurements_feed(tmp_path / "artifacts", ["SUBSYSTEM_C", "SUBSYSTEM_A", "SIGNAL_B"])
    result = validate_cp2(_minimal_cp2_payload(), subject_run_dir=tmp_path)
    assert_ok(result)


# ---------------------------------------------------------------------------
# CP2 — missing fields
# ---------------------------------------------------------------------------

def test_validate_cp2_missing_predictions_t() -> None:
    payload = _minimal_cp2_payload()
    payload.pop("predictions_t")
    assert_has_error(validate_cp2(payload), "MISSING_FIELD")


def test_validate_cp2_empty_predictions_t() -> None:
    payload = _minimal_cp2_payload()
    payload["predictions_t"] = []
    assert_has_error(validate_cp2(payload), "MISSING_FIELD")


def test_validate_cp2_missing_forecast_rationale() -> None:
    payload = _minimal_cp2_payload()
    payload.pop("forecast_rationale")
    assert_has_error(validate_cp2(payload), "MISSING_FIELD")


def test_validate_cp2_missing_snapshot_value() -> None:
    payload = _minimal_cp2_payload()
    payload["predictions_t"][0].pop("snapshot_value")
    assert_has_error(validate_cp2(payload), "MISSING_SNAPSHOT_VALUE")


def test_validate_cp2_invalid_snapshot_value() -> None:
    payload = _minimal_cp2_payload()
    payload["predictions_t"][0]["snapshot_value"] = "not-a-number"
    assert_has_error(validate_cp2(payload), "INVALID_FIELD")


def test_validate_cp2_missing_target_value() -> None:
    payload = _minimal_cp2_payload()
    payload["predictions_t"][0].pop("target_value")
    assert_has_error(validate_cp2(payload), "MISSING_TARGET_VALUE")


def test_validate_cp2_invalid_target_value() -> None:
    payload = _minimal_cp2_payload()
    payload["predictions_t"][0]["target_value"] = "not-a-number"
    assert_has_error(validate_cp2(payload), "INVALID_FIELD")


# ---------------------------------------------------------------------------
# CP2 — direction enum
# ---------------------------------------------------------------------------

def test_validate_cp2_invalid_direction_sideways() -> None:
    payload = _minimal_cp2_payload()
    payload["predictions_t"][0]["direction"] = "SIDEWAYS"
    assert_has_error(validate_cp2(payload), "INVALID_FIELD")


def test_validate_cp2_invalid_direction_lowercase() -> None:
    payload = _minimal_cp2_payload()
    payload["predictions_t"][0]["direction"] = "down"  # must be uppercase
    assert_has_error(validate_cp2(payload), "INVALID_FIELD")


def test_validate_cp2_valid_direction_up() -> None:
    payload = _minimal_cp2_payload()
    payload["predictions_t"][0]["direction"] = "UP"
    payload["predictions_t"][0]["target_value"] = 101.0
    result = validate_cp2(payload)
    assert_ok(result)


def test_validate_cp2_invalid_target_direction_up() -> None:
    payload = _minimal_cp2_payload()
    payload["predictions_t"][0]["direction"] = "UP"
    payload["predictions_t"][0]["target_value"] = 99.0
    assert_has_error(validate_cp2(payload), "INVALID_TARGET_DIRECTION")


def test_validate_cp2_invalid_target_direction_down() -> None:
    payload = _minimal_cp2_payload()
    payload["predictions_t"][0]["direction"] = "DOWN"
    payload["predictions_t"][0]["target_value"] = 101.0
    assert_has_error(validate_cp2(payload), "INVALID_TARGET_DIRECTION")


def test_validate_cp2_temporal_order_invalid() -> None:
    payload = _minimal_cp2_payload()
    payload["predictions_t"][0]["snapshot_time"] = "2026-03-04T22:00:00+00:00"
    payload["predictions_t"][0]["target_time_iso"] = "2026-03-04T21:00:00+00:00"
    assert_has_error(validate_cp2(payload), "TEMPORAL_ORDER_INVALID")


def test_validate_cp2_temporal_mismatch_with_expected_runtime_values() -> None:
    payload = _minimal_cp2_payload()
    payload["predictions_t"][0]["snapshot_time"] = "2026-03-04T00:01:00+00:00"
    result = validate_cp2(
        payload,
        expected_snapshot_time="2026-03-04T00:00:00+00:00",
        expected_target_time_iso="2026-03-04T21:00:00+00:00",
    )
    assert_has_error(result, "TEMPORAL_MISMATCH")


# ---------------------------------------------------------------------------
# CP2 — forecast_rationale word count
# ---------------------------------------------------------------------------

def test_validate_cp2_forecast_rationale_below_min() -> None:
    payload = _minimal_cp2_payload()
    # 1 prediction → min = 75 + 30 = 105 words; give only 10
    payload["forecast_rationale"] = _words(8, "[1] [2]")
    assert_has_error(validate_cp2(payload), "BELOW_MIN_WORD_COUNT")


def test_validate_cp2_forecast_rationale_formula_two_predictions() -> None:
    payload = _minimal_cp2_payload()
    # Add second prediction; grounding evidence also needs subject=SUBSYSTEM_A with S_ ledger
    payload["evidence_dictionary"].append({
        "ref_id": "[3]",
        "ledger_id": "S_BADDCAFE",
        "subject": "SUBSYSTEM_A",
        "signal_summary": "SUBSYSTEM_A signal.",
    })
    payload["predictions_t"].append({
        "target_id": "SUBSYSTEM_A",
        "direction": "UP",
        "unit": "dimensionless", "snapshot_value": 101.0,
        "target_value": 105.0,
        "snapshot_time": "2026-03-04T00:00:00+00:00",
        "target_time_iso": "2026-03-04T21:00:00+00:00",
        "invalidation": "Invalidated if SUBSYSTEM_A fails to hold above prior range high.",
    })
    # 2 predictions → min = 75 + 30×2 = 135 words
    payload["forecast_rationale"] = _words(133, "[1] [2]")
    assert_ok(validate_cp2(payload))


# ---------------------------------------------------------------------------
# CP2 — forecast_rationale citation resolution
# ---------------------------------------------------------------------------

def test_validate_cp2_forecast_rationale_citation_unresolved() -> None:
    payload = _minimal_cp2_payload()
    # forecast_rationale cites [5] which doesn't exist in evidence
    payload["forecast_rationale"] = _words(103, "[1] [5]")
    assert_has_error(validate_cp2(payload), "CITATION_UNRESOLVED")


# ---------------------------------------------------------------------------
# CP2 — grounding
# ---------------------------------------------------------------------------

def test_validate_cp2_grounding_wrong_lane() -> None:
    payload = _minimal_cp2_payload()
    # SUBSYSTEM_C's evidence entry has M_ (ENVIRONMENT) ledger instead of S_ (MEASUREMENTS)
    payload["evidence_dictionary"][1]["ledger_id"] = "M_CAFEBABE"
    assert_has_error(validate_cp2(payload), "GROUNDING_FAILED_WRONG_LANE")


def test_validate_cp2_grounding_no_matching_subject() -> None:
    payload = _minimal_cp2_payload()
    # Change prediction to SIGNAL_C which has no evidence entry at all
    payload["predictions_t"][0]["target_id"] = "SIGNAL_C"
    assert_has_error(validate_cp2(payload), "GROUNDING_FAILED_WRONG_LANE")


def test_validate_cp2_grounding_case_insensitive() -> None:
    payload = _minimal_cp2_payload()
    # subject in evidence is lowercase — should still ground correctly
    payload["evidence_dictionary"][1]["subject"] = "subsystem_c"
    payload["predictions_t"][0]["target_id"] = "SUBSYSTEM_C"
    result = validate_cp2(payload)
    assert_ok(result)


def test_validate_cp2_grounding_accepts_subsystems_prefix() -> None:
    payload = _minimal_cp2_payload()
    payload["evidence_dictionary"][1]["ledger_id"] = "E_CAFEBABE"
    result = validate_cp2(payload)
    assert_ok(result)


# ---------------------------------------------------------------------------
# CP2 — out-of-universe checks
# ---------------------------------------------------------------------------

def test_validate_cp2_missing_context_no_artifacts_dir(tmp_path: Path) -> None:
    # subject_run_dir exists but has no artifacts/ subdirectory
    result = validate_cp2(_minimal_cp2_payload(), subject_run_dir=tmp_path)
    assert_has_error(result, "MISSING_CONTEXT")


def test_validate_cp2_missing_context_empty_artifacts_dir(tmp_path: Path) -> None:
    (tmp_path / "artifacts").mkdir()
    result = validate_cp2(_minimal_cp2_payload(), subject_run_dir=tmp_path)
    assert_has_error(result, "MISSING_CONTEXT")


def test_validate_cp2_out_of_universe(tmp_path: Path) -> None:
    # SUBSYSTEM_C is the prediction but feed only has SUBSYSTEM_A and SIGNAL_B
    _write_measurements_feed(tmp_path / "artifacts", ["SUBSYSTEM_A", "SIGNAL_B"])
    result = validate_cp2(_minimal_cp2_payload(), subject_run_dir=tmp_path)
    assert_has_error(result, "OUT_OF_UNIVERSE")


def test_validate_cp2_out_of_universe_case_normalized(tmp_path: Path) -> None:
    # Feed has lowercase target_id; target_id is uppercase — should still pass
    _write_measurements_feed(tmp_path / "artifacts", ["subsystem_c", "SUBSYSTEM_A"])
    result = validate_cp2(_minimal_cp2_payload(), subject_run_dir=tmp_path)
    # "subsystem_c".upper() == "SUBSYSTEM_C" == target "SUBSYSTEM_C".upper() — should be in universe
    assert_ok(result)


def test_validate_cp2_no_subject_run_dir_skips_universe_check() -> None:
    # No subject_run_dir → universe check skipped → only structural validation
    result = validate_cp2(_minimal_cp2_payload(), subject_run_dir=None)
    assert_ok(result)


def test_validate_cp2_engine_audit_snapshot_mismatch() -> None:
    payload = _minimal_cp2_payload()
    payload["_engine_audit_errors"] = [
        "SNAPSHOT_VALUE_MISMATCH: predictions_t[0] target_id=SUBSYSTEM_C snapshot_value=120.0 feed_value=100.0"
    ]
    assert_has_error(validate_cp2(payload), "SNAPSHOT_VALUE_MISMATCH")


# ---------------------------------------------------------------------------
# cross_corr JSON validators
# ---------------------------------------------------------------------------

def test_validate_cross_corr_v1_happy_path() -> None:
    assert_ok(validate_cross_corr_v1(_minimal_cross_corr_v1_payload()))


def test_validate_cross_corr_v1_missing_required_array() -> None:
    payload = _minimal_cross_corr_v1_payload()
    payload.pop("orphans")
    assert_has_error(validate_cross_corr_v1(payload), "MISSING_FIELD")


def test_validate_cross_corr_v1_requires_subjects() -> None:
    payload = _minimal_cross_corr_v1_payload()
    payload["swarms"][0].pop("subjects")
    assert_has_error(validate_cross_corr_v1(payload), "MISSING_FIELD")


def test_validate_cross_corr_v2_happy_path() -> None:
    assert_ok(validate_cross_corr_v2(_minimal_cross_corr_v2_payload()))


def test_validate_cross_corr_v2_rejects_invalid_target_union() -> None:
    payload = _minimal_cross_corr_v2_payload()
    payload["valid_prediction_targets"] = ["SIGNAL_A"]  # incomplete vs union(SIGNAL_A,CVX,UAL)
    assert_has_error(validate_cross_corr_v2(payload), "INVALID_FIELD")


def test_validate_cross_corr_v2_requires_target_ids() -> None:
    payload = _minimal_cross_corr_v2_payload()
    payload["target_swarms"][0].pop("target_ids")
    assert_has_error(validate_cross_corr_v2(payload), "MISSING_FIELD")


# ---------------------------------------------------------------------------
# Oracle artifact JSON validators
# ---------------------------------------------------------------------------

def test_validate_realized_hindsight_brief_happy_path() -> None:
    assert_ok(validate_realized_hindsight_brief(_minimal_realized_hindsight_brief_payload()))


def test_validate_realized_hindsight_brief_requires_mutually_exclusive_package_lists() -> None:
    payload = _minimal_realized_hindsight_brief_payload()
    payload["surprise_packages"] = ["Oil shock continuation"]
    assert_has_error(validate_realized_hindsight_brief(payload), "INVALID_FIELD")


def test_validate_prediction_reconciliation_happy_path() -> None:
    assert_ok(validate_prediction_reconciliation(_minimal_prediction_reconciliation_payload()))


def test_validate_prediction_reconciliation_rejects_duplicate_target_ids() -> None:
    payload = _minimal_prediction_reconciliation_payload()
    payload["rows"].append(dict(payload["rows"][0]))
    payload["summary"]["row_count"] = 2
    payload["summary"]["directionally_correct_count"] = 2
    assert_has_error(validate_prediction_reconciliation(payload), "DUPLICATE_TARGET_ID")


def test_validate_prediction_reconciliation_rejects_summary_mismatch() -> None:
    payload = _minimal_prediction_reconciliation_payload()
    payload["summary"]["largest_percent_miss_target"] = "XLE"
    assert_has_error(validate_prediction_reconciliation(payload), "INVALID_FIELD")


def test_validate_cp2_critique_happy_path() -> None:
    assert_ok(validate_cp2_critique(_minimal_cp2_critique_payload()))


def test_validate_cp2_critique_rejects_invalid_scope() -> None:
    payload = _minimal_cp2_critique_payload()
    payload["critique_items"][0]["scope"] = "all_of_the_above"
    assert_has_error(validate_cp2_critique(payload), "INVALID_FIELD")


def test_validate_cp2_critique_rejects_invalid_realized_handle_format() -> None:
    payload = _minimal_cp2_critique_payload()
    payload["critique_items"][0]["realized_refs"] = ["prediction_reconciliation:SIGNAL_A:extra"]
    assert_has_error(validate_cp2_critique(payload), "INVALID_HANDLE_FORMAT")


def test_validate_oracle_cp2_meta_requires_presence() -> None:
    result = validate_oracle_cp2_meta(_minimal_cp2_payload())
    assert_has_error(result, "MISSING_FIELD")


def test_validate_oracle_cp2_meta_accepts_format_only_handles() -> None:
    payload = _minimal_cp2_payload()
    payload["oracle_meta"] = {
        "truth_influence_refs": ["realized_hindsight_brief:oil_shock"],
        "realized_diff_refs": ["prediction_reconciliation:SIGNAL_A"],
        "explicit_exclusions": [
            {
                "kind": "TRUTH_ONLY_SIGNAL",
                "ref": "oracle_explain:1",
                "reason": "Helpful hindsight context but not admissible grounding.",
            }
        ],
        "oracle_hindsight_notes": ["Residual upside existed but subject support was partial."],
    }
    assert_ok(validate_oracle_cp2_meta(payload))


def test_validate_oracle_cp2_meta_rejects_invalid_handle_format_without_lookup() -> None:
    payload = _minimal_cp2_payload()
    payload["oracle_meta"] = {
        "truth_influence_refs": ["missing_handle"],
        "realized_diff_refs": ["prediction_reconciliation:SIGNAL_A:extra"],
        "explicit_exclusions": [
            {
                "kind": "TRUTH_ONLY_SIGNAL",
                "ref": "bad ref",
                "reason": "Still format-invalid even before any lookup.",
            }
        ],
    }
    result = validate_oracle_cp2_meta(payload)
    assert_has_error(result, "INVALID_HANDLE_FORMAT")


# ---------------------------------------------------------------------------
# ValidationResult contract
# ---------------------------------------------------------------------------

def test_validation_result_success_has_empty_errors() -> None:
    r = ValidationResult.success()
    assert r.ok is True
    assert r.errors == []


def test_validation_result_failure_sorts_errors() -> None:
    r = ValidationResult.failure(["MISSING_FIELD: b", "MISSING_FIELD: a"])
    assert not r.ok
    assert r.errors == sorted(r.errors)


def test_validation_result_failure_deduplicates() -> None:
    r = ValidationResult.failure(["MISSING_FIELD: x", "MISSING_FIELD: x"])
    assert len(r.errors) == 1


# ---------------------------------------------------------------------------
# CP2 — split measurements/SUBSYSTEMS feed universe checks (Locked Decision 13)
# ---------------------------------------------------------------------------

def _write_subsystems_feed(artifacts_dir: Path, target_ids: List[str]) -> None:
    """Write a minimal SUBSYSTEMS feed artifact to artifacts_dir/global_subsystems_feed.json."""
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    feed = {
        "metadata": {"as_of": "2026-01-01"},
        "data": {
            "columns": ["Category", "target_id", "Value"],
            "rows": [["subsystems", t, "100.0"] for t in target_ids],
        },
    }
    (artifacts_dir / "global_subsystems_feed.json").write_text(json.dumps(feed))


def test_validate_cp2_target_in_subsystems_feed_passes(tmp_path: Path) -> None:
    """Target target_id in SUBSYSTEMS feed (not measurements feed) must pass OUT_OF_UNIVERSE check via union."""
    # Measurements feed has unrelated target_ids; SUBSYSTEMS feed has the target SUBSYSTEM_C
    _write_measurements_feed(tmp_path / "artifacts", ["SIGNAL_B", "SIGNAL_A"])
    _write_subsystems_feed(tmp_path / "artifacts", ["SUBSYSTEM_C", "SUBSYSTEM_A"])
    result = validate_cp2(_minimal_cp2_payload(), subject_run_dir=tmp_path)
    assert_ok(result)


def test_validate_cp2_target_in_measurements_feed_only_passes(tmp_path: Path) -> None:
    """Measurements-only universe still passes when target is in the measurements feed."""
    _write_measurements_feed(tmp_path / "artifacts", ["SUBSYSTEM_C", "SIGNAL_B"])
    result = validate_cp2(_minimal_cp2_payload(), subject_run_dir=tmp_path)
    assert_ok(result)


def test_validate_cp2_target_absent_from_both_feeds_fails(tmp_path: Path) -> None:
    """Target not in measurements feed OR SUBSYSTEMS feed must produce OUT_OF_UNIVERSE error."""
    _write_measurements_feed(tmp_path / "artifacts", ["SIGNAL_B", "SIGNAL_A"])
    _write_subsystems_feed(tmp_path / "artifacts", ["SUBSYSTEM_A", "CONTEXT_A"])
    result = validate_cp2(_minimal_cp2_payload(), subject_run_dir=tmp_path)
    assert_has_error(result, "OUT_OF_UNIVERSE")


def test_validate_cp2_subsystems_only_feed_missing_context(tmp_path: Path) -> None:
    """Empty artifacts dir (no observation feeds) still produces MISSING_CONTEXT."""
    (tmp_path / "artifacts").mkdir()
    result = validate_cp2(_minimal_cp2_payload(), subject_run_dir=tmp_path)
    assert_has_error(result, "MISSING_CONTEXT")
