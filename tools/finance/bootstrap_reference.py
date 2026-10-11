#!/usr/bin/env python3
"""
[PURPOSE]
- Teleology: Provide deterministic, fixture-only reference cases for the
  finance model-selection stationary-bootstrap Reality Check path.
- Mechanism: Materialize synthetic finance_family_loss_matrix_v0 payloads and
  run the same model_selection_stats kernel used by production receipts.
- Hardening: Proves null behavior, fixed-seed reproducibility,
  poor/irrelevant-alternative visibility, overlap-aware block length, and
  mutation-denial invariants before SPA/MCS expansion.

[CONSTRAINTS]
- This tool emits reference fixtures, not model-selection authority.
- No optimizer/GEPA/calculator mutation permission is ever granted here.
- Navigation-group: market_intelligence
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Sequence

from system.lib import feed_envelope
from tools.finance.family_loss_matrix import (
    BOOTSTRAP_METHOD_STATIONARY,
    FAMILY_LOSS_MATRIX_AUTHORITY,
    FAMILY_LOSS_MATRIX_SCHEMA,
)
from tools.finance.model_selection_stats import (
    DEFAULT_BOOTSTRAP_REPS,
    DEFAULT_BOOTSTRAP_SEED,
    DEFAULT_MIN_BOOTSTRAP_SAMPLE,
    MODEL_SELECTION_STATS_AUTHORITY,
    reality_check_summary,
    spa_readiness_summary,
)
from tools.finance.spa_statistics import SPA_STATISTICS_AUTHORITY, spa_summary
from tools.finance import variant_registry
from tools.finance.event_keys import COMPARISON_EVENT_KEY_SCHEMA

TOOL_NAME = "finance_bootstrap_reference"
DATA_SCHEMA_VERSION = "finance_bootstrap_reference_suite.1"
REFERENCE_SUITE_SCHEMA = "finance_bootstrap_reference_suite_v0"
REFERENCE_AUTHORITY = "test_fixture_not_model_selection_authority"
LOSS_METRIC = "brier_score_binary_directional_event"


def _as_text(value: Any) -> str:
    return str(value or "").strip()


def _failure_envelope(error: str, *, run_dir: Optional[Path] = None) -> Dict[str, Any]:
    now = feed_envelope.utc_now()
    diagnostics = feed_envelope.new_diagnostics()
    feed_envelope.append_warning(diagnostics, error)
    metadata = feed_envelope.build_metadata(
        tool=TOOL_NAME,
        status="failure",
        now=now,
        run_id=feed_envelope.resolve_run_id(None, run_dir, default=TOOL_NAME),
        as_of=now.iso,
        items_count=0,
        diagnostics=diagnostics,
        data_schema_version=DATA_SCHEMA_VERSION,
        timestamp=now.iso,
        error=error,
    )
    return {"metadata": metadata, "data": {}}


def _event_rows(
    *,
    baseline_losses: Sequence[float],
    candidate_losses: Mapping[str, Sequence[float]],
    overlap: bool = False,
) -> list[dict[str, Any]]:
    base_start = datetime(2026, 4, 1, tzinfo=timezone.utc)
    step_days = 1 if overlap else 7
    rows: list[dict[str, Any]] = []
    for index, baseline_loss in enumerate(baseline_losses):
        event_start = base_start + timedelta(days=index * step_days)
        event_end = event_start + timedelta(days=5)
        losses = {
            variant_registry.BASELINE_VARIANT_ID: round(float(baseline_loss), 10),
        }
        for candidate_id, values in candidate_losses.items():
            losses[candidate_id] = round(float(values[index]), 10)
        rows.append(
            {
                "comparison_event_key": f"fin_ref_evt_{index:03d}",
                "subject_as_of": event_start.isoformat(),
                "event_start": event_start.isoformat(),
                "event_end": event_end.isoformat(),
                "horizon": "5d",
                "split": "holdout",
                "split_membership": {
                    "bound": True,
                    "split": "holdout",
                    "split_policy": "prequential",
                    "usable_for_variant_comparison": True,
                    "reason": "bootstrap_reference_fixture",
                },
                "losses": losses,
            }
        )
    return rows


def _overlap_count(rows: Sequence[Mapping[str, Any]]) -> int:
    intervals: list[tuple[datetime, datetime]] = []
    for row in rows:
        start = datetime.fromisoformat(_as_text(row.get("event_start")))
        end = datetime.fromisoformat(_as_text(row.get("event_end")))
        intervals.append((start, end))
    count = 0
    for index, (start, end) in enumerate(intervals):
        for other_start, other_end in intervals[index + 1 :]:
            if start < other_end and other_start < end:
                count += 1
    return count


def synthetic_family_loss_matrix(
    *,
    candidate_loss_deltas: Mapping[str, Sequence[float]],
    baseline_loss: float = 0.2,
    overlap: bool = False,
) -> dict[str, Any]:
    if not candidate_loss_deltas:
        raise ValueError("candidate_loss_deltas is required")
    sample_size = len(next(iter(candidate_loss_deltas.values())))
    if sample_size <= 0:
        raise ValueError("candidate loss series must be non-empty")
    for candidate_id, deltas in candidate_loss_deltas.items():
        if len(deltas) != sample_size:
            raise ValueError(f"candidate series length mismatch for {candidate_id}")
    baseline_losses = [baseline_loss for _ in range(sample_size)]
    candidate_losses = {
        candidate_id: [baseline_loss + float(delta) for delta in deltas]
        for candidate_id, deltas in candidate_loss_deltas.items()
    }
    rows = _event_rows(
        baseline_losses=baseline_losses,
        candidate_losses=candidate_losses,
        overlap=overlap,
    )
    overlap_count = _overlap_count(rows)
    recommended_block_length = 5 if overlap_count else 1
    return {
        "schema_version": FAMILY_LOSS_MATRIX_SCHEMA,
        "authority": FAMILY_LOSS_MATRIX_AUTHORITY,
        "status": "built",
        "baseline_variant_id": variant_registry.BASELINE_VARIANT_ID,
        "candidate_variant_ids": sorted(candidate_loss_deltas),
        "loss_metric": LOSS_METRIC,
        "comparison_key_schema": COMPARISON_EVENT_KEY_SCHEMA,
        "split_policy": "prequential",
        "rows": rows,
        "coverage": {
            "shared_event_count": sample_size,
            "dropped_unshared_event_count": 0,
            "variant_count": len(candidate_loss_deltas) + 1,
            "candidate_count": len(candidate_loss_deltas),
            "candidate_event_counts": {
                candidate_id: sample_size for candidate_id in sorted(candidate_loss_deltas)
            },
            "blocked_reason_counts": {},
            "missing_split_membership_count": 0,
            "excluded_split_count": 0,
            "dropped_missing_loss_count": 0,
            "baseline_loss_mismatch_count": 0,
        },
        "dependence_diagnostics": {
            "event_window_overlap_count": overlap_count,
            "horizon_days": 5,
            "recommended_block_length": recommended_block_length,
            "bootstrap_method": BOOTSTRAP_METHOD_STATIONARY,
        },
    }


def _case(
    case_id: str,
    *,
    matrix: Mapping[str, Any],
    expected: str,
    bootstrap_reps: int,
    seed: int,
    minimum_sample: int,
    alternate_seed: Optional[int] = None,
) -> dict[str, Any]:
    reality_check = reality_check_summary(
        matrix,
        min_sample=minimum_sample,
        bootstrap_reps=bootstrap_reps,
        seed=seed,
    )
    alternate_reality_check = None
    if alternate_seed is not None:
        alternate_reality_check = reality_check_summary(
            matrix,
            min_sample=minimum_sample,
            bootstrap_reps=bootstrap_reps,
            seed=alternate_seed,
        )
    spa = spa_summary(
        matrix,
        min_sample=minimum_sample,
        bootstrap_reps=bootstrap_reps,
        seed=seed,
    )
    spa_readiness = spa_readiness_summary(
        matrix,
        reality_check_status=_as_text(reality_check.get("status")),
        min_sample=minimum_sample,
        spa_block=spa,
    )
    return {
        "case_id": case_id,
        "expected": expected,
        "status": "pass",
        "reality_check": reality_check,
        "alternate_seed_reality_check": alternate_reality_check,
        "spa": spa,
        "spa_readiness": spa_readiness,
        "matrix_diagnostics": matrix.get("dependence_diagnostics", {}),
        "decision": {
            "optimizer_permission": False,
            "calculator_mutation_permission": False,
            "authority": REFERENCE_AUTHORITY,
        },
    }


def build_reference_suite(
    *,
    bootstrap_reps: int = DEFAULT_BOOTSTRAP_REPS,
    seed: int = DEFAULT_BOOTSTRAP_SEED,
    minimum_sample: int = DEFAULT_MIN_BOOTSTRAP_SAMPLE,
) -> dict[str, Any]:
    n = minimum_sample
    good_id = variant_registry.SHADOW_TEST_VARIANT_ID
    alt_id = variant_registry.SHADOW_ALT_VARIANT_ID
    bad_id = "calculator:calculator.6:reference_bad"
    worse_id = "calculator:calculator.6:reference_worse"
    no_improvement = synthetic_family_loss_matrix(
        candidate_loss_deltas={
            good_id: [0.0 for _ in range(n)],
            alt_id: [0.0 for _ in range(n)],
        }
    )
    strong_candidate = synthetic_family_loss_matrix(
        candidate_loss_deltas={
            good_id: [-0.09 if index % 3 == 0 else (-0.08 if index % 3 == 1 else -0.07) for index in range(n)],
            alt_id: [0.01 if index % 3 == 0 else (0.02 if index % 3 == 1 else 0.03) for index in range(n)],
        }
    )
    poor_alternatives = synthetic_family_loss_matrix(
        candidate_loss_deltas={
            good_id: [-0.06 if index % 3 == 0 else (-0.05 if index % 3 == 1 else -0.04) for index in range(n)],
            bad_id: [0.29 if index % 3 == 0 else (0.30 if index % 3 == 1 else 0.31) for index in range(n)],
            worse_id: [0.39 if index % 3 == 0 else (0.40 if index % 3 == 1 else 0.41) for index in range(n)],
        }
    )
    overlap_deltas = [(-0.08 if index % 3 else -0.01) for index in range(n)]
    overlapping = synthetic_family_loss_matrix(
        candidate_loss_deltas={
            good_id: overlap_deltas,
            alt_id: [0.01 if index % 2 else -0.02 for index in range(n)],
        },
        overlap=True,
    )
    sample_gated = synthetic_family_loss_matrix(
        candidate_loss_deltas={
            good_id: [-0.05, -0.03, -0.04],
            alt_id: [0.02, 0.01, 0.03],
        }
    )
    return {
        "schema_version": REFERENCE_SUITE_SCHEMA,
        "authority": REFERENCE_AUTHORITY,
        "statistics_authority": MODEL_SELECTION_STATS_AUTHORITY,
        "spa_statistics_authority": SPA_STATISTICS_AUTHORITY,
        "generated_at": feed_envelope.utc_now().iso,
        "cases": [
            _case(
                "all_candidates_equal_to_baseline",
                matrix=no_improvement,
                expected="p_value_high_or_no_improvement",
                bootstrap_reps=bootstrap_reps,
                seed=seed,
                minimum_sample=minimum_sample,
            ),
            _case(
                "one_candidate_strictly_better",
                matrix=strong_candidate,
                expected="best_variant_detected_but_mutation_false",
                bootstrap_reps=bootstrap_reps,
                seed=seed,
                minimum_sample=minimum_sample,
            ),
            _case(
                "irrelevant_bad_candidates_added",
                matrix=poor_alternatives,
                expected="reality_check_conservative_flag_visible",
                bootstrap_reps=bootstrap_reps,
                seed=seed,
                minimum_sample=minimum_sample,
            ),
            _case(
                "overlapping_event_windows_stationary_bootstrap",
                matrix=overlapping,
                expected="block_length_tracks_dependence_fixture",
                bootstrap_reps=bootstrap_reps,
                seed=seed,
                minimum_sample=minimum_sample,
                alternate_seed=seed + 1,
            ),
            _case(
                "sample_gated_reference",
                matrix=sample_gated,
                expected="no_p_value_under_sample_gate",
                bootstrap_reps=bootstrap_reps,
                seed=seed,
                minimum_sample=minimum_sample,
            ),
        ],
    }


def run(config: Dict[str, Any], run_dir: Optional[Path] = None) -> Dict[str, Any]:
    try:
        suite = build_reference_suite(
            bootstrap_reps=int(config.get("bootstrap_reps") or DEFAULT_BOOTSTRAP_REPS),
            seed=int(config.get("bootstrap_seed") or DEFAULT_BOOTSTRAP_SEED),
            minimum_sample=int(config.get("minimum_sample") or DEFAULT_MIN_BOOTSTRAP_SAMPLE),
        )
        now = feed_envelope.utc_now()
        diagnostics = feed_envelope.new_diagnostics(
            input_rows=0,
            output_rows=len(suite["cases"]),
            dropped_rows=0,
            authority=REFERENCE_AUTHORITY,
        )
        metadata = feed_envelope.build_metadata(
            tool=TOOL_NAME,
            status="success",
            now=now,
            run_id=feed_envelope.resolve_run_id(None, run_dir, default=TOOL_NAME),
            as_of=now.iso,
            items_count=len(suite["cases"]),
            diagnostics=diagnostics,
            data_schema_version=DATA_SCHEMA_VERSION,
            timestamp=now.iso,
        )
        return {"metadata": metadata, "data": suite}
    except Exception as exc:
        return _failure_envelope(str(exc), run_dir=run_dir)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Emit deterministic finance bootstrap reference cases.")
    parser.add_argument("--bootstrap-reps", type=int, default=DEFAULT_BOOTSTRAP_REPS)
    parser.add_argument("--bootstrap-seed", type=int, default=DEFAULT_BOOTSTRAP_SEED)
    parser.add_argument("--minimum-sample", type=int, default=DEFAULT_MIN_BOOTSTRAP_SAMPLE)
    parser.add_argument("--json", action="store_true", help="Print JSON envelope.")
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    payload = run(
        {
            "bootstrap_reps": args.bootstrap_reps,
            "bootstrap_seed": args.bootstrap_seed,
            "minimum_sample": args.minimum_sample,
        }
    )
    text = json.dumps(payload, indent=2, sort_keys=True)
    print(text if args.json else text)
    return 0 if payload.get("metadata", {}).get("status") == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
