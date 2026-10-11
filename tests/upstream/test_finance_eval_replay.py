"""
[PURPOSE]
- Teleology: Verify finance forecasts require event-bound admission before production replay.
- Mechanism: Create tiny calculator/admission/reconciliation/scorecard artifacts under tmp_path and invoke finance tool entrypoints.

[INTERFACE]
- Exports: Collected test functions/classes; no runtime API.

[FLOW]
- Mechanism: Check candidate-smoke compatibility, CP1 event binding, matching horizons/truth, Brier outcome basis, matured/weekend/closed-date resolution, benchmark/member policy and failure envelopes.

[DEPENDENCIES]
- Couples: admit_forecasts, resolve_forecasts, eval_replay and build_eval_operating_picture.

[CONSTRAINTS]
- Guarantee: No live market fetch or calculator promotion occurs; unbound/immature/insufficient-coverage claims remain unscored or explicitly inadmissible.
"""

from __future__ import annotations

import json
from pathlib import Path

from tools.finance import admit_forecasts, build_eval_operating_picture, eval_replay, resolve_forecasts


def _forecast_artifact() -> dict:
    return {
        "metadata": {"tool": "calculator", "data_schema_version": "calculator.6"},
        "data": {
            "candidate_forecast_cards": [
                {
                    "schema_version": "forecast_claim_card_v0",
                    "identity": {
                        "forecast_id": "calc_fc_test",
                        "run_id": "subject_run",
                        "generator_variant_id": "calculator:calculator.6:default",
                        "source_artifact_refs": [{"artifact_id": "global_stock_feed", "quality_tone": "ok"}],
                        "as_of": "2026-03-10T00:00:00+00:00",
                    },
                    "target": {
                        "universe": "stock",
                        "entity_or_group": "indices",
                        "members": ["SPY", "QQQ"],
                        "horizon": "5d",
                        "event_definition": "group_directional_continuation_relative_to_configured_benchmark",
                        "direction": "UP",
                        "benchmark_definition": "not_bound_until_cp1_commitment",
                    },
                    "belief": {"event_probability": 0.7, "confidence": "MEDIUM"},
                    "admissibility": {
                        "candidate_only_not_cp1_commitment": True,
                        "no_trade_advice_flag": True,
                        "leakage_guard": "subject_time_only_calculator_inputs",
                    },
                }
            ]
        },
    }


def _write(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_candidate_smoke_mode_still_scores_calculator_cards_against_legacy_reconciliation(tmp_path: Path) -> None:
    forecast_path = tmp_path / "calculator.json"
    reconciliation_path = tmp_path / "prediction_reconciliation.json"
    _write(forecast_path, _forecast_artifact())
    _write(
        reconciliation_path,
        {
            "metadata": {"tool": "oracle_truth_diff_equity"},
            "data": {
                "rows": [
                    {
                        "target_id": "SPY",
                        "subject_snapshot_price": 100.0,
                        "realized_truth_price": 110.0,
                    },
                    {
                        "target_id": "QQQ",
                        "subject_snapshot_price": 100.0,
                        "realized_truth_price": 90.0,
                    },
                ]
            },
        },
    )

    payload = eval_replay.run(
        {
            "forecast_cards": str(forecast_path),
            "prediction_reconciliation": str(reconciliation_path),
            "mode": "candidate_smoke_test",
            "runtime": {"run_id": "replay_test", "as_of": "2026-03-20T00:00:00+00:00"},
        },
        run_dir=tmp_path,
    )

    assert payload["metadata"]["tool"] == "finance_eval_replay"
    assert payload["metadata"]["data_schema_version"] == "finance_eval_replay.3"
    assert payload["data"]["aggregate"]["resolved_forecast_count"] == 1
    assert payload["data"]["aggregate"]["pending_forecast_count"] == 0
    assert payload["data"]["aggregate"]["mean_brier_score"] == 0.29
    scorecard = payload["data"]["scorecards"][0]
    assert scorecard["forecast_id"] == "calc_fc_test"
    assert scorecard["status"] == "resolved"
    assert scorecard["proper_score"]["score_rule"] == "brier_score_binary_directional_event"
    assert scorecard["calibration"]["resolved_member_count"] == 2
    assert scorecard["data_quality"]["truth_match_status"] == "matched_contract_rows"


def test_default_replay_refuses_unadmitted_calculator_candidates(tmp_path: Path) -> None:
    forecast_path = tmp_path / "calculator.json"
    _write(forecast_path, _forecast_artifact())

    payload = eval_replay.run(
        {
            "forecast_cards": str(forecast_path),
            "runtime": {"run_id": "replay_test", "as_of": "2026-03-20T00:00:00+00:00"},
        },
        run_dir=tmp_path,
    )

    assert payload["metadata"]["status"] == "success"
    assert payload["data"]["aggregate"]["resolved_forecast_count"] == 0
    assert payload["data"]["aggregate"]["not_admissible_forecast_count"] == 1
    assert payload["data"]["scorecards"][0]["status"] == "not_admissible_missing_event_binding"
    assert "event_contract_unbound" in payload["data"]["scorecards"][0]["residual_diagnosis"]["tags"]


def test_admission_binds_event_contract_and_cp1_replay_scores_only_matching_truth(tmp_path: Path) -> None:
    forecast_path = tmp_path / "calculator.json"
    admitted_path = tmp_path / "admitted.json"
    truth_path = tmp_path / "prediction_reconciliation.json"
    _write(forecast_path, _forecast_artifact())

    admitted = admit_forecasts.run(
        {
            "calculator_artifact": str(forecast_path),
            "horizon": "5d",
            "benchmark": "IWM",
            "cp1_ref": "cp1:test_policy",
            "max_cards": 3,
            "runtime": {"run_id": "admission_test", "as_of": "2026-03-10T00:00:00+00:00"},
        },
        run_dir=tmp_path,
    )
    _write(admitted_path, admitted)

    claim = admitted["data"]["admitted_claims"][0]
    truth_join_key = claim["truth_binding"]["truth_join_key"]
    event = claim["event"]
    assert claim["schema_version"] == "finance_forecast_claim_v1"
    assert claim["admissibility"]["cp1_commitment"] is True
    assert claim["belief"]["directional_hit_probability"] == 0.7
    assert event["event_start"] == "2026-03-10T00:00:00+00:00"
    assert event["event_end"] == "2026-03-15T00:00:00+00:00"

    truth_rows = []
    for target_id, member_return in (("SPY", 0.06), ("QQQ", -0.03)):
        truth_rows.append(
            {
                "target_id": target_id,
                "truth_join_key": truth_join_key,
                "subject_as_of": claim["subject"]["as_of"],
                "event_start": event["event_start"],
                "event_end": event["event_end"],
                "horizon": event["horizon"],
                "benchmark": event["benchmark"],
                "event_type": event["event_type"],
                "outcome_basis": event["outcome_basis"],
                "benchmark_member_policy": event["benchmark_member_policy"],
                "member_return": member_return,
                "benchmark_return": 0.0,
            }
        )
    _write(truth_path, {"metadata": {"tool": "oracle_truth_diff_equity"}, "data": {"rows": truth_rows}})

    replay = eval_replay.run(
        {
            "forecast_cards": str(admitted_path),
            "prediction_reconciliation": str(truth_path),
            "horizon": "5d",
            "mode": "cp1_admitted_only",
            "runtime": {"run_id": "replay_test", "as_of": "2026-03-20T00:00:00+00:00"},
        },
        run_dir=tmp_path,
    )

    assert replay["metadata"]["status"] == "success"
    assert replay["data"]["aggregate"]["resolved_forecast_count"] == 1
    assert replay["data"]["aggregate"]["mean_brier_score"] == 0.09
    assert replay["data"]["calibration_summary"]["resolved_count"] == 1
    assert replay["data"]["calibration_summary"]["base_rate"] == 1.0
    assert replay["data"]["generator_variants"][0]["generator_variant_id"] == "calculator:calculator.6:default"
    scorecard = replay["data"]["scorecards"][0]
    assert scorecard["status"] == "resolved"
    assert scorecard["comparison_event_key"].startswith("fin_evt_")
    assert scorecard["comparison_event_key_authority"] == "tools/finance/event_keys.py"
    assert scorecard["event_contract"]["comparison_event_key"] == scorecard["comparison_event_key"]
    assert scorecard["pair_audit"]["truth_join_key"] == truth_join_key
    assert scorecard["event_contract"]["truth_join_key"] == truth_join_key
    assert scorecard["finance_validation"]["benchmark"] == "IWM"
    assert scorecard["proper_score"]["outcome_basis"] == "equal_weight_group_return_direction"
    assert scorecard["proper_score"]["benchmark_member_policy"] == "reject_if_benchmark_is_member"
    assert scorecard["proper_score"]["event_outcome"] == 1.0
    assert scorecard["proper_score"]["group_excess_return"] == 0.015
    assert scorecard["member_diagnostics"]["member_hit_rate"] == 0.5
    assert scorecard["truth_coverage"]["coverage_ratio"] == 1.0


def test_mean_member_binary_hit_basis_preserves_legacy_member_average_brier(tmp_path: Path) -> None:
    forecast_path = tmp_path / "calculator.json"
    admitted_path = tmp_path / "admitted.json"
    truth_path = tmp_path / "prediction_reconciliation.json"
    _write(forecast_path, _forecast_artifact())

    admitted = admit_forecasts.run(
        {
            "calculator_artifact": str(forecast_path),
            "horizon": "5d",
            "benchmark": "SPY",
            "outcome_basis": "mean_member_binary_hit",
            "runtime": {"run_id": "admission_test", "as_of": "2026-03-10T00:00:00+00:00"},
        },
        run_dir=tmp_path,
    )
    _write(admitted_path, admitted)

    claim = admitted["data"]["admitted_claims"][0]
    event = claim["event"]
    truth_rows = []
    for target_id, member_return in (("SPY", 0.06), ("QQQ", -0.03)):
        truth_rows.append(
            {
                "target_id": target_id,
                "truth_join_key": claim["truth_binding"]["truth_join_key"],
                "subject_as_of": claim["subject"]["as_of"],
                "event_start": event["event_start"],
                "event_end": event["event_end"],
                "horizon": event["horizon"],
                "benchmark": event["benchmark"],
                "event_type": event["event_type"],
                "outcome_basis": event["outcome_basis"],
                "benchmark_member_policy": event["benchmark_member_policy"],
                "member_return": member_return,
                "benchmark_return": 0.0,
            }
        )
    _write(truth_path, {"metadata": {"tool": "oracle_truth_diff_equity"}, "data": {"rows": truth_rows}})

    replay = eval_replay.run(
        {
            "forecast_cards": str(admitted_path),
            "prediction_reconciliation": str(truth_path),
            "horizon": "5d",
            "mode": "cp1_admitted_only",
            "runtime": {"run_id": "replay_test", "as_of": "2026-03-20T00:00:00+00:00"},
        },
        run_dir=tmp_path,
    )

    scorecard = replay["data"]["scorecards"][0]
    assert scorecard["status"] == "resolved"
    assert scorecard["proper_score"]["outcome_basis"] == "mean_member_binary_hit"
    assert scorecard["proper_score"]["brier_score"] == 0.29
    assert scorecard["proper_score"]["event_outcome"] == 0.5


def test_cp1_replay_refuses_horizon_mismatch(tmp_path: Path) -> None:
    forecast_path = tmp_path / "calculator.json"
    admitted_path = tmp_path / "admitted.json"
    _write(forecast_path, _forecast_artifact())
    admitted = admit_forecasts.run(
        {
            "calculator_artifact": str(forecast_path),
            "horizon": "5d",
            "benchmark": "IWM",
            "runtime": {"run_id": "admission_test"},
        },
        run_dir=tmp_path,
    )
    _write(admitted_path, admitted)

    replay = eval_replay.run(
        {
            "forecast_cards": str(admitted_path),
            "horizon": "20d",
            "runtime": {"run_id": "replay_test"},
        },
        run_dir=tmp_path,
    )

    assert replay["metadata"]["status"] == "success"
    assert replay["data"]["scorecards"][0]["status"] == "not_admissible_horizon_mismatch"
    assert "horizon_mismatch" in replay["data"]["scorecards"][0]["residual_diagnosis"]["tags"]


def test_cp1_replay_does_not_score_legacy_truth_rows_without_event_binding(tmp_path: Path) -> None:
    forecast_path = tmp_path / "calculator.json"
    admitted_path = tmp_path / "admitted.json"
    truth_path = tmp_path / "legacy_truth.json"
    _write(forecast_path, _forecast_artifact())
    admitted = admit_forecasts.run(
        {
            "calculator_artifact": str(forecast_path),
            "horizon": "5d",
            "benchmark": "IWM",
            "runtime": {"run_id": "admission_test"},
        },
        run_dir=tmp_path,
    )
    _write(admitted_path, admitted)
    _write(
        truth_path,
        {
            "metadata": {"tool": "oracle_truth_diff_equity"},
            "data": {
                "rows": [
                    {
                        "target_id": "SPY",
                        "subject_snapshot_price": 100.0,
                        "realized_truth_price": 110.0,
                    }
                ]
            },
        },
    )

    replay = eval_replay.run(
        {
            "forecast_cards": str(admitted_path),
            "prediction_reconciliation": str(truth_path),
            "runtime": {"run_id": "replay_test"},
        },
        run_dir=tmp_path,
    )

    assert replay["metadata"]["status"] == "success"
    assert replay["data"]["aggregate"]["resolved_forecast_count"] == 0
    assert replay["data"]["scorecards"][0]["status"] == "matured_truth_missing"
    assert replay["data"]["scorecards"][0]["proper_score"]["brier_score"] is None


def test_resolver_materializes_event_window_truth_rows_for_matured_claim(tmp_path: Path) -> None:
    forecast_path = tmp_path / "calculator.json"
    admitted_path = tmp_path / "admitted.json"
    price_path = tmp_path / "price_history.json"
    truth_path = tmp_path / "resolved_truth.json"
    _write(forecast_path, _forecast_artifact())
    admitted = admit_forecasts.run(
            {
                "calculator_artifact": str(forecast_path),
                "horizon": "5d",
                "benchmark": "IWM",
                "runtime": {"run_id": "admission_test", "as_of": "2026-03-10T00:00:00+00:00"},
            },
            run_dir=tmp_path,
    )
    _write(admitted_path, admitted)
    _write(
        price_path,
        {
            "data": {
                    "prices": {
                        "SPY": {"2026-03-10": 100.0, "2026-03-15": 106.0},
                        "QQQ": {"2026-03-10": 100.0, "2026-03-15": 97.0},
                        "IWM": {"2026-03-10": 100.0, "2026-03-15": 100.0},
                    }
                }
            },
    )

    resolved = resolve_forecasts.run(
        {
            "admitted_claims": str(admitted_path),
            "price_history": str(price_path),
            "as_of": "2026-03-20T00:00:00+00:00",
            "runtime": {"run_id": "resolution_test", "as_of": "2026-03-20T00:00:00+00:00"},
        },
        run_dir=tmp_path,
    )
    _write(truth_path, resolved)

    assert resolved["metadata"]["status"] == "success"
    assert resolved["data"]["summary"]["status_counts"] == {"truth_materialized": 1}
    assert len(resolved["data"]["rows"]) == 2
    assert resolved["data"]["rows"][0]["outcome_basis"] == "equal_weight_group_return_direction"
    assert resolved["data"]["rows"][0]["benchmark_member_policy"] == "reject_if_benchmark_is_member"

    replay = eval_replay.run(
        {
            "forecast_cards": str(admitted_path),
            "prediction_reconciliation": str(truth_path),
            "horizon": "5d",
            "runtime": {"run_id": "replay_test", "as_of": "2026-03-20T00:00:00+00:00"},
        },
        run_dir=tmp_path,
    )

    scorecard = replay["data"]["scorecards"][0]
    assert scorecard["status"] == "resolved"
    assert scorecard["proper_score"]["brier_score"] == 0.09
    assert scorecard["member_diagnostics"]["member_hit_rate"] == 0.5


def test_resolver_rolls_weekend_event_end_to_next_available_close(tmp_path: Path) -> None:
    forecast_path = tmp_path / "calculator.json"
    admitted_path = tmp_path / "admitted.json"
    price_path = tmp_path / "price_history.json"
    _write(forecast_path, _forecast_artifact())
    admitted = admit_forecasts.run(
        {
            "calculator_artifact": str(forecast_path),
            "horizon": "5d",
            "benchmark": "IWM",
            "runtime": {"run_id": "admission_test", "as_of": "2026-03-10T00:00:00+00:00"},
        },
        run_dir=tmp_path,
    )
    _write(admitted_path, admitted)
    _write(
        price_path,
        {
            "data": {
                "prices": {
                    "SPY": {"2026-03-10": 100.0, "2026-03-16": 106.0},
                    "QQQ": {"2026-03-10": 100.0, "2026-03-16": 97.0},
                    "IWM": {"2026-03-10": 100.0, "2026-03-16": 100.0},
                }
            },
        },
    )

    resolved = resolve_forecasts.run(
        {
            "admitted_claims": str(admitted_path),
            "price_history": str(price_path),
            "as_of": "2026-03-20T00:00:00+00:00",
            "runtime": {"run_id": "resolution_test", "as_of": "2026-03-20T00:00:00+00:00"},
        },
        run_dir=tmp_path,
    )

    assert resolved["data"]["summary"]["status_counts"] == {"truth_materialized": 1}
    assert resolved["data"]["summary"]["date_match_policy"] == "exact_or_next_available"
    assert resolved["data"]["summary"]["price_match_status_counts"] == {"exact": 4, "rolled_forward": 4}
    assert resolved["data"]["summary"]["price_match_reason_counts"] == {
        "exact_trading_session": 4,
        "rolled_forward_market_closed": 4,
    }
    row = resolved["data"]["rows"][0]
    assert row["event_end_requested_date"] == "2026-03-15"
    assert row["event_end_price_date"] == "2026-03-16"
    assert row["event_end_price_match_status"] == "rolled_forward"
    assert row["event_end_price_match_reason"] == "rolled_forward_market_closed"
    assert row["event_end_requested_session_status"] == "market_closed"
    assert row["event_end_requested_session_reason"] == "weekend"
    assert row["event_end_price_roll_days"] == 1
    assert row["benchmark_end_price_match_status"] == "rolled_forward"
    assert row["benchmark_end_price_match_reason"] == "rolled_forward_market_closed"

    exact_only = resolve_forecasts.run(
        {
            "admitted_claims": str(admitted_path),
            "price_history": str(price_path),
            "as_of": "2026-03-20T00:00:00+00:00",
            "date_match_policy": "exact",
            "runtime": {"run_id": "resolution_exact_test", "as_of": "2026-03-20T00:00:00+00:00"},
        },
        run_dir=tmp_path,
    )

    assert exact_only["data"]["rows"] == []
    assert exact_only["data"]["claim_resolutions"][0]["status"] == "not_admissible_missing_benchmark_truth"
    assert exact_only["data"]["claim_resolutions"][0]["benchmark_price_matches"]["end"]["match_status"] == "missing"
    assert exact_only["data"]["claim_resolutions"][0]["benchmark_price_matches"]["end"]["match_reason"] == "refused_exact_policy"


def test_resolver_marks_provider_missing_trading_day_roll_separately(tmp_path: Path) -> None:
    forecast_path = tmp_path / "calculator.json"
    admitted_path = tmp_path / "admitted.json"
    price_path = tmp_path / "price_history.json"
    _write(forecast_path, _forecast_artifact())
    admitted = admit_forecasts.run(
        {
            "calculator_artifact": str(forecast_path),
            "horizon": "5d",
            "benchmark": "IWM",
            "runtime": {"run_id": "admission_test", "as_of": "2026-03-10T00:00:00+00:00"},
        },
        run_dir=tmp_path,
    )
    _write(admitted_path, admitted)
    _write(
        price_path,
        {
            "data": {
                "prices": {
                    "SPY": {"2026-03-11": 101.0, "2026-03-16": 106.0},
                    "QQQ": {"2026-03-11": 99.0, "2026-03-16": 97.0},
                    "IWM": {"2026-03-11": 100.0, "2026-03-16": 100.0},
                }
            },
        },
    )

    resolved = resolve_forecasts.run(
        {
            "admitted_claims": str(admitted_path),
            "price_history": str(price_path),
            "as_of": "2026-03-20T00:00:00+00:00",
            "runtime": {"run_id": "resolution_test", "as_of": "2026-03-20T00:00:00+00:00"},
        },
        run_dir=tmp_path,
    )

    assert resolved["data"]["summary"]["status_counts"] == {"truth_materialized": 1}
    assert resolved["data"]["summary"]["price_match_status_counts"] == {"rolled_forward": 8}
    assert resolved["data"]["summary"]["price_match_reason_counts"] == {
        "rolled_forward_market_closed": 4,
        "rolled_forward_provider_missing": 4,
    }
    row = resolved["data"]["rows"][0]
    assert row["event_start_price_match_reason"] == "rolled_forward_provider_missing"
    assert row["event_start_requested_session_status"] == "expected_trading_session"
    assert row["event_start_requested_session_reason"] == "weekday_expected_open"
    assert row["benchmark_start_price_match_reason"] == "rolled_forward_provider_missing"


def test_resolver_uses_declared_closed_date_as_market_closed_roll_reason(tmp_path: Path) -> None:
    forecast_path = tmp_path / "calculator.json"
    admitted_path = tmp_path / "admitted.json"
    price_path = tmp_path / "price_history.json"
    _write(forecast_path, _forecast_artifact())
    admitted = admit_forecasts.run(
        {
            "calculator_artifact": str(forecast_path),
            "horizon": "5d",
            "benchmark": "IWM",
            "runtime": {"run_id": "admission_test", "as_of": "2026-03-10T00:00:00+00:00"},
        },
        run_dir=tmp_path,
    )
    _write(admitted_path, admitted)
    _write(
        price_path,
        {
            "metadata": {
                "coverage": {
                    "market_calendar": {
                        "policy_id": "fixture_calendar",
                        "calendar_id": "XNYS_fixture",
                        "calendar_source": "unit_test_declared_closed_dates",
                        "closed_dates": ["2026-03-10"],
                    }
                }
            },
            "data": {
                "prices": {
                    "SPY": {"2026-03-11": 101.0, "2026-03-16": 106.0},
                    "QQQ": {"2026-03-11": 99.0, "2026-03-16": 97.0},
                    "IWM": {"2026-03-11": 100.0, "2026-03-16": 100.0},
                }
            },
        },
    )

    resolved = resolve_forecasts.run(
        {
            "admitted_claims": str(admitted_path),
            "price_history": str(price_path),
            "as_of": "2026-03-20T00:00:00+00:00",
            "runtime": {"run_id": "resolution_test", "as_of": "2026-03-20T00:00:00+00:00"},
        },
        run_dir=tmp_path,
    )

    assert resolved["data"]["summary"]["status_counts"] == {"truth_materialized": 1}
    assert resolved["data"]["summary"]["truth_session_policy"]["calendar_id"] == "XNYS_fixture"
    assert resolved["data"]["summary"]["price_match_reason_counts"] == {"rolled_forward_market_closed": 8}
    row = resolved["data"]["rows"][0]
    assert row["event_start_price_match_reason"] == "rolled_forward_market_closed"
    assert row["event_start_requested_session_reason"] == "declared_closed_date"
    assert row["event_start_market_calendar_id"] == "XNYS_fixture"


def test_benchmark_member_policy_default_rejects_self_benchmark_group_claim(tmp_path: Path) -> None:
    forecast_path = tmp_path / "calculator.json"
    admitted_path = tmp_path / "admitted.json"
    _write(forecast_path, _forecast_artifact())
    admitted = admit_forecasts.run(
        {
            "calculator_artifact": str(forecast_path),
            "horizon": "5d",
            "benchmark": "SPY",
            "runtime": {"run_id": "admission_test", "as_of": "2026-03-10T00:00:00+00:00"},
        },
        run_dir=tmp_path,
    )
    _write(admitted_path, admitted)

    replay = eval_replay.run(
        {
            "forecast_cards": str(admitted_path),
            "mode": "cp1_admitted_only",
            "runtime": {"run_id": "replay_test", "as_of": "2026-03-20T00:00:00+00:00"},
        },
        run_dir=tmp_path,
    )

    scorecard = replay["data"]["scorecards"][0]
    assert scorecard["status"] == "not_admissible_benchmark_member_policy_violation"
    assert scorecard["proper_score"]["benchmark_member_policy"] == "reject_if_benchmark_is_member"
    assert "benchmark_member_policy_violation" in scorecard["residual_diagnosis"]["tags"]


def test_include_benchmark_member_policy_negative_group_event_scores_claim_level_miss(tmp_path: Path) -> None:
    forecast_path = tmp_path / "calculator.json"
    admitted_path = tmp_path / "admitted.json"
    price_path = tmp_path / "price_history.json"
    truth_path = tmp_path / "resolved_truth.json"
    _write(forecast_path, _forecast_artifact())
    admitted = admit_forecasts.run(
        {
            "calculator_artifact": str(forecast_path),
            "horizon": "5d",
            "benchmark": "SPY",
            "benchmark_member_policy": "include_as_zero_excess",
            "runtime": {"run_id": "admission_test", "as_of": "2026-03-10T00:00:00+00:00"},
        },
        run_dir=tmp_path,
    )
    _write(admitted_path, admitted)
    _write(
        price_path,
        {
            "data": {
                "prices": {
                    "SPY": {"2026-03-10": 100.0, "2026-03-15": 100.0},
                    "QQQ": {"2026-03-10": 100.0, "2026-03-15": 97.0},
                }
            }
        },
    )

    resolved = resolve_forecasts.run(
        {
            "admitted_claims": str(admitted_path),
            "price_history": str(price_path),
            "as_of": "2026-03-20T00:00:00+00:00",
            "runtime": {"run_id": "resolution_test", "as_of": "2026-03-20T00:00:00+00:00"},
        },
        run_dir=tmp_path,
    )
    _write(truth_path, resolved)

    assert resolved["data"]["summary"]["status_counts"] == {"truth_materialized": 1}
    assert {row["benchmark_member_policy"] for row in resolved["data"]["rows"]} == {"include_as_zero_excess"}

    replay = eval_replay.run(
        {
            "forecast_cards": str(admitted_path),
            "prediction_reconciliation": str(truth_path),
            "horizon": "5d",
            "runtime": {"run_id": "replay_test", "as_of": "2026-03-20T00:00:00+00:00"},
        },
        run_dir=tmp_path,
    )

    scorecard = replay["data"]["scorecards"][0]
    assert scorecard["status"] == "resolved"
    assert scorecard["proper_score"]["event_outcome"] == 0.0
    assert scorecard["proper_score"]["group_excess_return"] == -0.015
    assert scorecard["proper_score"]["brier_score"] == 0.49
    assert scorecard["member_diagnostics"]["diagnostic_only"] is True
    assert scorecard["member_diagnostics"]["member_hit_rate"] == 0.0


def test_resolver_refuses_immature_claim_without_truth_rows(tmp_path: Path) -> None:
    forecast_path = tmp_path / "calculator.json"
    admitted_path = tmp_path / "admitted.json"
    price_path = tmp_path / "price_history.json"
    _write(forecast_path, _forecast_artifact())
    admitted = admit_forecasts.run(
        {
            "calculator_artifact": str(forecast_path),
            "horizon": "5d",
            "benchmark": "IWM",
            "runtime": {"run_id": "admission_test", "as_of": "2026-03-10T00:00:00+00:00"},
        },
        run_dir=tmp_path,
    )
    _write(admitted_path, admitted)
    _write(price_path, {"data": {"prices": {"SPY": {"2026-03-10": 100.0}}}})

    resolved = resolve_forecasts.run(
        {
            "admitted_claims": str(admitted_path),
            "price_history": str(price_path),
            "as_of": "2026-03-12T00:00:00+00:00",
            "runtime": {"run_id": "resolution_test", "as_of": "2026-03-12T00:00:00+00:00"},
        },
        run_dir=tmp_path,
    )

    assert resolved["data"]["rows"] == []
    assert resolved["data"]["claim_resolutions"][0]["status"] == "pending_maturity"


def test_resolver_refuses_missing_benchmark(tmp_path: Path) -> None:
    forecast_path = tmp_path / "calculator.json"
    admitted_path = tmp_path / "admitted.json"
    price_path = tmp_path / "price_history.json"
    _write(forecast_path, _forecast_artifact())
    admitted = admit_forecasts.run(
        {
            "calculator_artifact": str(forecast_path),
            "horizon": "5d",
            "benchmark": "IWM",
            "runtime": {"run_id": "admission_test", "as_of": "2026-03-10T00:00:00+00:00"},
        },
        run_dir=tmp_path,
    )
    _write(admitted_path, admitted)
    _write(price_path, {"data": {"prices": {"QQQ": {"2026-03-10": 100.0, "2026-03-15": 97.0}}}})

    resolved = resolve_forecasts.run(
        {
            "admitted_claims": str(admitted_path),
            "price_history": str(price_path),
            "as_of": "2026-03-20T00:00:00+00:00",
            "runtime": {"run_id": "resolution_test", "as_of": "2026-03-20T00:00:00+00:00"},
        },
        run_dir=tmp_path,
    )

    assert resolved["data"]["rows"] == []
    assert resolved["data"]["claim_resolutions"][0]["status"] == "not_admissible_missing_benchmark_truth"


def test_replay_refuses_insufficient_member_coverage(tmp_path: Path) -> None:
    forecast_path = tmp_path / "calculator.json"
    admitted_path = tmp_path / "admitted.json"
    truth_path = tmp_path / "prediction_reconciliation.json"
    _write(forecast_path, _forecast_artifact())
    admitted = admit_forecasts.run(
        {
            "calculator_artifact": str(forecast_path),
            "horizon": "5d",
            "benchmark": "IWM",
            "runtime": {"run_id": "admission_test", "as_of": "2026-03-10T00:00:00+00:00"},
        },
        run_dir=tmp_path,
    )
    _write(admitted_path, admitted)
    claim = admitted["data"]["admitted_claims"][0]
    event = claim["event"]
    _write(
        truth_path,
        {
            "metadata": {"tool": "finance_forecast_resolution"},
            "data": {
                "rows": [
                    {
                        "target_id": "SPY",
                        "truth_join_key": claim["truth_binding"]["truth_join_key"],
                        "subject_as_of": claim["subject"]["as_of"],
                        "event_start": event["event_start"],
                        "event_end": event["event_end"],
                        "horizon": event["horizon"],
                        "benchmark": event["benchmark"],
                        "event_type": event["event_type"],
                        "outcome_basis": event["outcome_basis"],
                        "benchmark_member_policy": event["benchmark_member_policy"],
                        "member_return": 0.06,
                        "benchmark_return": 0.0,
                    }
                ]
            },
        },
    )

    replay = eval_replay.run(
        {
            "forecast_cards": str(admitted_path),
            "prediction_reconciliation": str(truth_path),
            "minimum_coverage": 1.0,
            "runtime": {"run_id": "replay_test", "as_of": "2026-03-20T00:00:00+00:00"},
        },
        run_dir=tmp_path,
    )

    scorecard = replay["data"]["scorecards"][0]
    assert scorecard["status"] == "not_admissible_insufficient_member_coverage"
    assert scorecard["truth_coverage"]["coverage_ratio"] == 0.5
    assert scorecard["truth_coverage"]["missing_members"] == ["QQQ"]


def test_eval_replay_invalid_score_bundle_returns_failure_envelope(tmp_path: Path) -> None:
    forecast_path = tmp_path / "calculator.json"
    _write(forecast_path, _forecast_artifact())

    payload = eval_replay.run(
        {
            "forecast_cards": str(forecast_path),
            "score": "unsupported",
            "runtime": {"run_id": "replay_test"},
        },
        run_dir=tmp_path,
    )

    assert payload["metadata"]["status"] == "failure"
    assert "unsupported score bundle" in payload["metadata"]["error"]


def test_operating_picture_builder_materializes_projection(tmp_path: Path) -> None:
    scorecards_path = tmp_path / "scorecards.json"
    output_path = tmp_path / "finance_eval_operating_picture.json"
    _write(
        scorecards_path,
        {
            "metadata": {"tool": "finance_eval_replay"},
            "data": {
                "scorecards": [
                    {
                        "forecast_id": "ff_claim_one",
                        "status": "pending_truth",
                        "generator_variant_id": "calculator:calculator.6:default",
                        "event_contract": {"horizon": "5d", "event_end": "2026-03-15T00:00:00+00:00"},
                        "proper_score": {"directional_hit_probability": 0.6, "brier_score": None},
                        "residual_diagnosis": {"tags": ["truth_not_available"]},
                    }
                ]
            },
        },
    )

    projection = build_eval_operating_picture.build_projection([scorecards_path])
    build_eval_operating_picture.write_projection(projection, output_path)
    written = json.loads(output_path.read_text(encoding="utf-8"))

    assert written["schema_version"] == "finance_eval_operating_picture_v0"
    assert written["pending"]["count"] == 1
    assert written["pending"]["by_horizon"] == {"5d": 1}
    assert written["lifecycle"]["pending_maturity_count"] == 1
    assert written["residuals"]["truth_unavailable"] == 1
