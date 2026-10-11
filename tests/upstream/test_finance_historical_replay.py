"""
[PURPOSE]
- Teleology: Verify v3 finance historical replay remains an evaluator gate, not
  optimizer mutation or frontend semantics.
- Mechanism: Run tiny local calculator/price fixtures through historical replay,
  shadow calibration, and operating-picture projection.
- Navigation-group: server_backend

[INTERFACE]
- Reads: Tiny local calculator/price and replay fixtures.
- Writes: Temporary experiment/calibration JSON under tmp_path.

[FLOW]
- Guarantee: Replay emits membership/purge evidence, rejects unsupported split policies and keeps shadow calibration mutation-denying.

[DEPENDENCIES]
- Couples: historical_replay, calibrate_forecast_probabilities, variant_registry and build_eval_operating_picture.

[CONSTRAINTS]
- Atomicity: Fixture-root output only; no live optimizer or frontend action.
- Orders: Authored split and variant policies drive deterministic tiny replay assertions.
"""

from __future__ import annotations

import json
from pathlib import Path

from tools.finance import build_eval_operating_picture, calibrate_forecast_probabilities, historical_replay, variant_registry


def _write(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def _forecast_artifact() -> dict:
    return {
        "metadata": {"tool": "calculator", "data_schema_version": "calculator.6"},
        "data": {
            "candidate_forecast_cards": [
                {
                    "schema_version": "forecast_claim_card_v0",
                    "identity": {
                        "forecast_id": "calc_fc_hist",
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


def _price_history() -> dict:
    return {
        "data": {
            "prices": {
                "SPY": {"2026-03-10": 100.0, "2026-03-12": 101.0, "2026-03-15": 106.0, "2026-03-17": 107.0},
                "QQQ": {"2026-03-10": 100.0, "2026-03-12": 98.0, "2026-03-15": 97.0, "2026-03-17": 99.0},
                "IWM": {"2026-03-10": 100.0, "2026-03-12": 100.0, "2026-03-15": 100.0, "2026-03-17": 100.0},
            }
        }
    }


def _forecast_artifact_on(as_of: str, forecast_id: str = "calc_fc_hist") -> dict:
    artifact = _forecast_artifact()
    card = artifact["data"]["candidate_forecast_cards"][0]
    card["identity"]["forecast_id"] = forecast_id
    card["identity"]["as_of"] = as_of
    return artifact


def test_historical_replay_builds_experiment_ledger_without_optimizer_permission(tmp_path: Path) -> None:
    forecast_path = tmp_path / "calculator.json"
    price_path = tmp_path / "prices.json"
    _write(forecast_path, _forecast_artifact())
    _write(price_path, _price_history())

    payload = historical_replay.run(
        {
            "calculator_artifacts": [str(forecast_path)],
            "price_history": str(price_path),
            "horizons": "5d",
            "benchmark": "IWM",
            "split_policy": "prequential",
            "truth_as_of": "2026-03-20T00:00:00+00:00",
            "runtime": {"run_id": "historical_test", "as_of": "2026-03-20T00:00:00+00:00"},
        },
        run_dir=tmp_path,
    )

    assert payload["metadata"]["status"] == "success"
    ledger = payload["data"]["experiment_ledger"]
    assert ledger["schema_version"] == "finance_eval_experiment_ledger_v0"
    assert ledger["split_policy"]["kind"] == "prequential"
    assert ledger["split_policy"]["random_kfold_allowed"] is False
    assert ledger["split_policy"]["executable"] is True
    assert ledger["split_policy"]["split_membership_counts"] == {"evaluation": 1}
    assert ledger["variant_registry_ref"] == variant_registry.REGISTRY_REF
    assert ledger["variant_known"] is True
    assert ledger["variant_status"] == "baseline"
    assert ledger["truth_resolution_policy"] == {
        "resolver_ref": "tools/finance/resolve_forecasts.py",
        "date_match_policy": "exact_or_next_available",
        "max_roll_days": 3,
        "deterministic_local_truth_only": True,
        "match_reason_authority": "tools/finance/resolve_forecasts.py",
    }
    assert payload["data"]["split_membership"]["rows"][0]["split"] == "evaluation"
    assert ledger["claim_counts"]["candidate"] == 1
    assert ledger["claim_counts"]["admitted"] == 1
    assert ledger["claim_counts"]["resolved"] == 1
    assert ledger["scores"]["mean_brier"] == 0.09
    assert ledger["variant_decision"]["optimizer_permission"] is False
    assert payload["data"]["scorecards"][0]["proper_score"]["brier_score"] == 0.09
    scorecard_split = payload["data"]["scorecards"][0]["split_membership"]
    assert scorecard_split["split"] == "evaluation"
    assert scorecard_split["split_policy"] == "prequential"
    assert scorecard_split["usable_for_variant_comparison"] is True
    assert scorecard_split["comparison_event_key"] == payload["data"]["scorecards"][0]["comparison_event_key"]


def test_historical_replay_rejects_random_or_unknown_split_policy(tmp_path: Path) -> None:
    forecast_path = tmp_path / "calculator.json"
    price_path = tmp_path / "prices.json"
    _write(forecast_path, _forecast_artifact())
    _write(price_path, _price_history())

    payload = historical_replay.run(
        {
            "calculator_artifacts": [str(forecast_path)],
            "price_history": str(price_path),
            "split_policy": "random_kfold",
            "truth_as_of": "2026-03-20T00:00:00+00:00",
        },
        run_dir=tmp_path,
    )

    assert payload["metadata"]["status"] == "failure"
    assert "unsupported split_policy" in payload["metadata"]["error"]


def test_variant_registry_knows_baseline_and_rejects_unknown_variant(tmp_path: Path) -> None:
    assert variant_registry.assert_variant_known(variant_registry.BASELINE_VARIANT_ID)["status"] == "baseline"
    assert variant_registry.assert_variant_known(variant_registry.SHADOW_TEST_VARIANT_ID)["status"] == "shadow"
    assert variant_registry.mutation_gate_for(variant_registry.SHADOW_TEST_VARIANT_ID)["calculator_mutation_permission"] is False

    forecast_path = tmp_path / "calculator.json"
    price_path = tmp_path / "prices.json"
    _write(forecast_path, _forecast_artifact())
    _write(price_path, _price_history())

    payload = historical_replay.run(
        {
            "calculator_artifacts": [str(forecast_path)],
            "price_history": str(price_path),
            "variant_id": "calculator:calculator.6:unknown",
            "truth_as_of": "2026-03-20T00:00:00+00:00",
        },
        run_dir=tmp_path,
    )

    assert payload["metadata"]["status"] == "failure"
    assert "not_admissible_unknown_variant" in payload["metadata"]["error"]


def test_purged_holdout_emits_executable_membership_and_purge_evidence(tmp_path: Path) -> None:
    forecast_a = tmp_path / "calculator_a.json"
    forecast_b = tmp_path / "calculator_b.json"
    price_path = tmp_path / "prices.json"
    _write(forecast_a, _forecast_artifact_on("2026-03-10T00:00:00+00:00", "calc_fc_hist_a"))
    _write(forecast_b, _forecast_artifact_on("2026-03-12T00:00:00+00:00", "calc_fc_hist_b"))
    _write(price_path, _price_history())

    payload = historical_replay.run(
        {
            "calculator_artifacts": [str(forecast_a), str(forecast_b)],
            "price_history": str(price_path),
            "horizons": "5d",
            "benchmark": "IWM",
            "split_policy": "purged_holdout",
            "embargo_days": 0,
            "truth_as_of": "2026-03-20T00:00:00+00:00",
        },
        run_dir=tmp_path,
    )

    assert payload["metadata"]["status"] == "success"
    split = payload["data"]["experiment_ledger"]["split_policy"]
    assert split["executable"] is True
    assert split["split_membership_counts"]["holdout"] == 1
    assert split["split_membership_counts"]["purged"] == 1
    assert split["purged_count"] == 1
    scorecard_splits = [card["split_membership"] for card in payload["data"]["scorecards"]]
    assert {row["split"] for row in scorecard_splits} == {"holdout", "purged"}
    assert all(row["split"] in {"train", "validation", "holdout", "purged", "embargoed", "evaluation"} for row in scorecard_splits)
    assert all(row["usable_for_variant_comparison"] is False for row in scorecard_splits if row["split"] == "purged")
    assert all(row["usable_for_variant_comparison"] is True for row in scorecard_splits if row["split"] == "holdout")


def test_shadow_calibrator_and_operating_picture_gate_do_not_allow_live_mutation(tmp_path: Path) -> None:
    forecast_path = tmp_path / "calculator.json"
    price_path = tmp_path / "prices.json"
    replay_path = tmp_path / "historical_replay.json"
    calibrator_path = tmp_path / "calibrator.json"
    _write(forecast_path, _forecast_artifact())
    _write(price_path, _price_history())
    historical = historical_replay.run(
        {
            "calculator_artifacts": [str(forecast_path)],
            "price_history": str(price_path),
            "horizons": "5d",
            "benchmark": "IWM",
            "truth_as_of": "2026-03-20T00:00:00+00:00",
        },
        run_dir=tmp_path,
    )
    _write(replay_path, historical)

    calibrator = calibrate_forecast_probabilities.run(
        {
            "scorecards": [str(replay_path)],
            "method": "isotonic",
            "holdout_policy": "prequential",
            "runtime": {"run_id": "calibrator_test"},
        },
        run_dir=tmp_path,
    )
    _write(calibrator_path, calibrator)

    assert calibrator["metadata"]["status"] == "success"
    artifact = calibrator["data"]["calibrator"]
    assert artifact["schema_version"] == "finance_probability_calibrator_v0"
    assert artifact["status"] == "shadow_only"
    assert artifact["admission_decision"]["accepted"] is False
    assert artifact["admission_decision"]["reason"] == "in_sample_diagnostic_only"
    assert artifact["admission_decision"]["live_probability_mutation_allowed"] is False

    projection = build_eval_operating_picture.build_projection(
        [replay_path],
        experiment_paths=[replay_path],
        calibrator_paths=[calibrator_path],
    )

    assert projection["integrity"]["claim_outcome_invariant_status"] == "pass"
    assert projection["historical_replay"]["latest_experiment_id"] == historical["data"]["experiment_ledger"]["experiment_id"]
    assert projection["historical_replay"]["split_policy"] == "prequential"
    assert projection["calibration_gate"]["shadow_calibrator_count"] == 1
    assert projection["calibration_gate"]["holdout_eligible_count"] == 0
    assert projection["calibration_gate"]["live_probability_mutation_allowed"] is False
    assert projection["variant_gate"]["calculator_mutation_permission"] is False
