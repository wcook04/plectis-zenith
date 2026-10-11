"""
[PURPOSE]
- Teleology: Pin the finance comparison-event key as a shared evaluator
  primitive rather than per-module helper drift.
- Mechanism: Build canonical event-key vectors, then verify admission, replay
  fallback, and variant-comparison fallback all resolve to the same key.
- Navigation-group: server_backend

[INTERFACE]
- Fixtures: Canonical event vectors and admission/replay/variant candidate cards.

[FLOW]
- Compare all fallback keys; verify member order/case/direction invariance and key changes for semantic event fields.

[DEPENDENCIES]
- tools.finance.event_keys plus admission, replay and variant-comparison owner helpers.

[CONSTRAINTS]
- Guarantee: Key tests use supplied vectors; no market input is fetched or finance ledger persisted.
"""

from __future__ import annotations

from dataclasses import replace

from tools.finance import admit_forecasts, compare_variants, eval_replay
from tools.finance.event_keys import (
    COMPARISON_EVENT_KEY_AUTHORITY,
    COMPARISON_EVENT_KEY_SCHEMA,
    build_comparison_event_key,
    comparison_event_key_payload,
    normalize_key_parts,
)


def _candidate_card(*, forecast_id: str = "calc_fc_key_baseline", direction: str = "UP") -> dict:
    return {
        "schema_version": "forecast_claim_card_v0",
        "identity": {
            "forecast_id": forecast_id,
            "run_id": "subject_run",
            "generator_variant_id": "calculator:calculator.6:default",
            "as_of": "2026-03-10T00:00:00+00:00",
        },
        "target": {
            "universe": "stock",
            "entity_or_group": "indices",
            "members": ["QQQ", "SPY"],
            "horizon": "5d",
            "event_definition": "group_directional_continuation_relative_to_configured_benchmark",
            "direction": direction,
            "benchmark_definition": "not_bound_until_cp1_commitment",
        },
        "belief": {"event_probability": 0.7, "confidence": "MEDIUM"},
    }


def _canonical_parts():
    return normalize_key_parts(
        subject_as_of="2026-03-10T00:00:00+00:00",
        lane="stock",
        group="indices",
        members=["QQQ", "SPY"],
        event_start="2026-03-10T00:00:00+00:00",
        event_end="2026-03-15T00:00:00+00:00",
        horizon="5d",
        benchmark="IWM",
        event_type="group_return_direction_vs_benchmark",
        outcome_basis="equal_weight_group_return_direction",
        benchmark_member_policy="reject_if_benchmark_is_member",
    )


def test_canonical_key_is_shared_by_admission_replay_and_compare_fallbacks() -> None:
    expected_key = build_comparison_event_key(_canonical_parts())
    assert expected_key.startswith("fin_evt_")

    claim = admit_forecasts.admit_card(
        _candidate_card(),
        horizon="5d",
        benchmark="IWM",
        cp1_ref="cp1:test_policy",
    )
    assert claim is not None
    assert claim["comparison_event_key"] == expected_key
    assert claim["comparison_event_key_schema"] == COMPARISON_EVENT_KEY_SCHEMA
    assert claim["comparison_event_key_authority"] == COMPARISON_EVENT_KEY_AUTHORITY

    replay_claim = dict(claim)
    replay_claim.pop("comparison_event_key")
    replay_claim["truth_binding"] = dict(claim["truth_binding"])
    replay_claim["truth_binding"].pop("comparison_event_key")
    replay_contract = eval_replay._event_contract(replay_claim)
    assert replay_contract["comparison_event_key"] == expected_key
    assert replay_contract["comparison_event_key_authority"] == COMPARISON_EVENT_KEY_AUTHORITY

    scorecard = {
        "event_contract": {
            **replay_contract,
            "comparison_event_key": "",
            "comparison_event_key_schema": COMPARISON_EVENT_KEY_SCHEMA,
        },
        "target": claim["subject"],
        "proper_score": {"brier_score": 0.09},
    }
    assert compare_variants._pair_key(scorecard) == expected_key


def test_member_order_case_identity_and_direction_do_not_change_key() -> None:
    baseline = _canonical_parts()
    member_case_variant = normalize_key_parts(
        subject_as_of="2026-03-10T00:00:00Z",
        lane="STOCK",
        group="INDICES",
        members=["spy", "qqq"],
        event_start="2026-03-10T00:00:00Z",
        event_end="2026-03-15T00:00:00Z",
        horizon="5D",
        benchmark="iwm",
        event_type="GROUP_RETURN_DIRECTION_VS_BENCHMARK",
        outcome_basis="EQUAL_WEIGHT_GROUP_RETURN_DIRECTION",
        benchmark_member_policy="REJECT_IF_BENCHMARK_IS_MEMBER",
    )
    assert build_comparison_event_key(baseline) == build_comparison_event_key(member_case_variant)

    up_claim = admit_forecasts.admit_card(_candidate_card(forecast_id="calc_fc_up", direction="UP"), horizon="5d", benchmark="IWM", cp1_ref="cp1:test_policy")
    down_claim = admit_forecasts.admit_card(_candidate_card(forecast_id="calc_fc_down", direction="DOWN"), horizon="5d", benchmark="IWM", cp1_ref="cp1:test_policy")
    assert up_claim is not None
    assert down_claim is not None
    assert up_claim["forecast_id"] != down_claim["forecast_id"]
    assert up_claim["candidate_ref"] != down_claim["candidate_ref"]
    assert up_claim["comparison_event_key"] == down_claim["comparison_event_key"]


def test_semantic_event_fields_change_key() -> None:
    baseline = _canonical_parts()
    baseline_key = build_comparison_event_key(baseline)
    variants = [
        replace(baseline, members=("DIA", "SPY")),
        replace(baseline, event_end="2026-03-16T00:00:00+00:00"),
        replace(baseline, horizon="20d"),
        replace(baseline, benchmark="SPY"),
        replace(baseline, outcome_basis="mean_member_binary_hit"),
        replace(baseline, benchmark_member_policy="include_as_zero_excess"),
    ]
    for variant in variants:
        assert build_comparison_event_key(variant) != baseline_key


def test_key_payload_names_schema_and_authority() -> None:
    payload = comparison_event_key_payload(_canonical_parts())
    assert payload["comparison_event_key_schema"] == COMPARISON_EVENT_KEY_SCHEMA
    assert payload["comparison_event_key_authority"] == COMPARISON_EVENT_KEY_AUTHORITY
    assert payload["comparison_event_key_parts"]["members_signature"] == "QQQ,SPY"
