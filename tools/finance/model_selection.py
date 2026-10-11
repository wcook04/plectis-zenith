#!/usr/bin/env python3
"""
[PURPOSE]
- Teleology: Fold many pairwise finance variant-admission receipts into one
  family-level model-selection receipt so shadow variants cannot be
  cherry-picked from repeated tests on the same history.
- Mechanism: Read `finance_variant_admission_receipt_v0` envelopes, enforce
  shared baseline/loss/key/split contracts, build a shared-event family loss
  matrix, and compute sample-gated bootstrap Reality Check evidence without
  granting optimizer or calculator mutation permission.
- Hardening: Blocks family inference when split membership is unbound,
  candidate-smoke-test rows are present, variants are unknown, split policies
  are mixed or non-executable, or event evidence is unpaired.

[INTERFACE]
- Reads: one or more `finance_variant_admission.1` envelopes.
- Returns/prints: `finance_model_selection.1` ArtifactEnvelope.

[CONSTRAINTS]
- Shadow family only; no optimizer/GEPA or calculator mutation permission.
- SPA and Model Confidence Set are sample-gated evidence; no statistical block
  is mutation authority.
- Navigation-group: market_intelligence
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence

from system.lib import feed_envelope
from tools.finance.family_loss_matrix import (
    FAMILY_LOSS_MATRIX_AUTHORITY,
    build_family_loss_matrix,
)
from tools.finance.model_selection_stats import (
    DEFAULT_BOOTSTRAP_REPS,
    DEFAULT_BOOTSTRAP_SEED,
    DEFAULT_MCS_ALPHA,
    DEFAULT_MIN_BOOTSTRAP_SAMPLE,
    MODEL_SELECTION_STATS_AUTHORITY,
    blocked_reality_check,
    model_confidence_set_summary,
    reality_check_summary,
    spa_readiness_summary,
)
from tools.finance.spa_statistics import SPA_STATISTICS_AUTHORITY, spa_summary
from tools.finance import variant_registry
from tools.finance.event_keys import COMPARISON_EVENT_KEY_SCHEMA

TOOL_NAME = "finance_model_selection"
DATA_SCHEMA_VERSION = "finance_model_selection.1"
RECEIPT_SCHEMA_VERSION = "finance_model_selection_receipt_v0"
VARIANT_GATE_SCHEMA_VERSION = "finance_variant_admission_receipt_v0"
DEFAULT_METHOD = "mcs_or_spa_reserved"
SUPPORTED_METHODS = {
    "single_pair_summary",
    "mcs_or_spa_reserved",
    "spa_reserved",
    "reality_check_bootstrap",
    "reality_check_reserved",
    "model_confidence_set_reserved",
}
DEFAULT_LOSS = "brier_score_binary_directional_event"


def _as_text(value: Any) -> str:
    return str(value or "").strip()


def _as_float(value: Any) -> Optional[float]:
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _as_int(value: Any, default: int = 0) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    return default


def _read_json(path: Path) -> Dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object at {path}")
    return payload


def _data(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    data = payload.get("data")
    return data if isinstance(data, Mapping) else payload


def _receipt(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    data = _data(payload)
    receipt = data.get("receipt") if isinstance(data, Mapping) else None
    if isinstance(receipt, Mapping):
        return receipt
    if payload.get("schema_version") == VARIANT_GATE_SCHEMA_VERSION:
        return payload
    return {}


def _nested(mapping: Mapping[str, Any], *keys: str) -> Any:
    current: Any = mapping
    for key in keys:
        if not isinstance(current, Mapping):
            return None
        current = current.get(key)
    return current


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


def _stable_digest(*parts: Any, length: int = 16) -> str:
    text = "|".join(_as_text(part) for part in parts)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:length]


def _candidate_id(receipt: Mapping[str, Any]) -> str:
    return _as_text(receipt.get("candidate_variant_id"))


def _baseline_id(receipt: Mapping[str, Any]) -> str:
    return _as_text(receipt.get("baseline_variant_id"))


def _loss_metric(receipt: Mapping[str, Any]) -> str:
    return _as_text(receipt.get("loss_metric") or DEFAULT_LOSS)


def _split_kind(receipt: Mapping[str, Any]) -> str:
    return _as_text(_nested(receipt, "split_policy", "kind"))


def _split_executable(receipt: Mapping[str, Any]) -> bool:
    return bool(_nested(receipt, "split_policy", "executable") is True)


def _key_schema(receipt: Mapping[str, Any]) -> str:
    return _as_text(_nested(receipt, "pairing", "key_schema") or _nested(receipt, "statistics", "loss_differential_series", "comparison_key_schema") or COMPARISON_EVENT_KEY_SCHEMA)


def _sample_paired_count(receipt: Mapping[str, Any]) -> int:
    return _as_int(_nested(receipt, "sample", "paired_claim_count") or _nested(receipt, "statistics", "paired_sample_size"))


def _mean_delta(receipt: Mapping[str, Any]) -> Optional[float]:
    return _as_float(_nested(receipt, "statistics", "mean_loss_delta"))


def _series_event_keys(receipt: Mapping[str, Any]) -> set[str]:
    rows = _nested(receipt, "statistics", "loss_differential_series", "rows")
    if not isinstance(rows, list):
        return set()
    return {
        _as_text(row.get("comparison_event_key"))
        for row in rows
        if isinstance(row, Mapping) and _as_text(row.get("comparison_event_key"))
    }


def _candidate_smoke_count(receipt: Mapping[str, Any]) -> int:
    excluded = _nested(receipt, "pairing", "excluded_from_variant_comparison")
    if not isinstance(excluded, Mapping):
        return 0
    count = 0
    for side in ("baseline", "candidate"):
        side_counts = excluded.get(side)
        if isinstance(side_counts, Mapping):
            count += _as_int(side_counts.get("candidate_smoke_test"))
    return count


def _missing_split_count(receipt: Mapping[str, Any]) -> int:
    return max(
        _as_int(_nested(receipt, "sample", "missing_split_membership_count")),
        _as_int(_nested(receipt, "statistics", "dependence_diagnostics", "missing_split_membership_count")),
        _as_int(_nested(receipt, "statistics", "dependence_diagnostics", "split_binding", "missing_split_membership_count")),
    )


def _excluded_split_count(receipt: Mapping[str, Any]) -> int:
    return max(
        _as_int(_nested(receipt, "sample", "excluded_split_count")),
        _as_int(_nested(receipt, "statistics", "dependence_diagnostics", "excluded_split_count")),
        _as_int(_nested(receipt, "statistics", "dependence_diagnostics", "split_binding", "excluded_split_count")),
    )


def _unpaired_count(receipt: Mapping[str, Any]) -> int:
    return max(
        _as_int(_nested(receipt, "sample", "excluded_unpaired_count")),
        _as_int(_nested(receipt, "pairing", "unpaired_baseline_count"))
        + _as_int(_nested(receipt, "pairing", "unpaired_candidate_count")),
    )


def _mutation_requested(receipt: Mapping[str, Any]) -> bool:
    return bool(_nested(receipt, "decision", "optimizer_permission")) or bool(
        _nested(receipt, "decision", "calculator_mutation_permission")
    )


def _variant_known(variant_id: str) -> bool:
    if not variant_id:
        return False
    try:
        variant_registry.assert_variant_known(variant_id)
    except KeyError:
        return False
    return True


def _blocked_reasons(receipt: Mapping[str, Any]) -> List[str]:
    reasons: List[str] = []
    if receipt.get("schema_version") and receipt.get("schema_version") != VARIANT_GATE_SCHEMA_VERSION:
        reasons.append("wrong_receipt_schema")
    if not _variant_known(_baseline_id(receipt)):
        reasons.append("unknown_baseline_variant")
    if not _variant_known(_candidate_id(receipt)):
        reasons.append("unknown_variant")
    if not _split_executable(receipt):
        reasons.append("non_executable_split_policy")
    if _missing_split_count(receipt) > 0:
        reasons.append("split_membership_unbound")
    if _candidate_smoke_count(receipt) > 0:
        reasons.append("candidate_smoke_test_present")
    if _unpaired_count(receipt) > 0:
        reasons.append("unpaired_event_evidence")
    if _mutation_requested(receipt):
        reasons.append("pairwise_receipt_requested_mutation")
    return reasons


def _block_status(reason: str, *, candidate_count: int) -> str:
    if candidate_count < 2:
        return "not_computed_insufficient_variant_family"
    if reason == "split_membership_unbound":
        return "not_computed_split_unbound"
    if reason == "mixed_split_policy":
        return "not_computed_mixed_split_policy"
    if reason == "non_executable_split_policy":
        return "not_computed_non_executable_split_policy"
    if reason in {"unknown_variant", "unknown_baseline_variant"}:
        return "not_computed_unknown_variant"
    if reason == "candidate_smoke_test_present":
        return "not_computed_candidate_smoke_test"
    if reason == "unpaired_event_evidence":
        return "not_computed_unpaired_event_evidence"
    if reason in {"mixed_baseline_variant", "mixed_loss_metric", "mixed_comparison_key_schema"}:
        return f"not_computed_{reason}"
    return "reserved_or_insufficient_sample"


def _first_blocking_reason(
    *,
    candidate_count: int,
    mixed: Mapping[str, bool],
    receipt_reasons: Sequence[str],
) -> str:
    if candidate_count < 2:
        return "insufficient_variant_family"
    for reason in (
        "mixed_baseline_variant",
        "mixed_loss_metric",
        "mixed_comparison_key_schema",
        "mixed_split_policy",
        "unknown_baseline_variant",
        "unknown_variant",
        "non_executable_split_policy",
        "split_membership_unbound",
        "candidate_smoke_test_present",
        "unpaired_event_evidence",
        "pairwise_receipt_requested_mutation",
    ):
        if mixed.get(reason) or reason in receipt_reasons:
            return reason
    return "family_level_selection_not_admissive"


def _reserved_family_test(status: str) -> Dict[str, Any]:
    return {
        "status": status,
        "implemented": False,
        "reason": "family_level_model_selection_reserved_until_bootstrap_or_mcs_spa_implementation",
    }


def build_model_selection_receipt(
    receipts: Sequence[Mapping[str, Any]],
    *,
    method: str = DEFAULT_METHOD,
    bootstrap_reps: int = DEFAULT_BOOTSTRAP_REPS,
    bootstrap_seed: int = DEFAULT_BOOTSTRAP_SEED,
    min_bootstrap_sample: int = DEFAULT_MIN_BOOTSTRAP_SAMPLE,
    mcs_alpha: float = DEFAULT_MCS_ALPHA,
    allow_tiny_bootstrap: bool = False,
) -> Dict[str, Any]:
    if method not in SUPPORTED_METHODS:
        raise ValueError(f"unsupported model-selection method: {method}")

    valid_receipts = [receipt for receipt in receipts if receipt]
    if not valid_receipts:
        raise ValueError("at least one finance_variant_admission receipt is required")

    baseline_ids = sorted({_baseline_id(receipt) for receipt in valid_receipts if _baseline_id(receipt)})
    candidate_ids = sorted({_candidate_id(receipt) for receipt in valid_receipts if _candidate_id(receipt)})
    loss_metrics = sorted({_loss_metric(receipt) for receipt in valid_receipts if _loss_metric(receipt)})
    key_schemas = sorted({_key_schema(receipt) for receipt in valid_receipts if _key_schema(receipt)})
    split_kinds = sorted({_split_kind(receipt) for receipt in valid_receipts if _split_kind(receipt)})
    receipt_refs = [_as_text(receipt.get("variant_gate_id")) for receipt in valid_receipts if _as_text(receipt.get("variant_gate_id"))]

    blocked_variants: List[Dict[str, Any]] = []
    reason_counts: Dict[str, int] = {}
    for receipt in valid_receipts:
        reasons = _blocked_reasons(receipt)
        if reasons:
            candidate_id = _candidate_id(receipt)
            blocked_variants.append(
                {
                    "candidate_variant_id": candidate_id,
                    "variant_gate_id": _as_text(receipt.get("variant_gate_id")),
                    "reasons": reasons,
                }
            )
            for reason in reasons:
                reason_counts[reason] = reason_counts.get(reason, 0) + 1

    mixed = {
        "mixed_baseline_variant": len(baseline_ids) > 1,
        "mixed_loss_metric": len(loss_metrics) > 1,
        "mixed_comparison_key_schema": len(key_schemas) > 1,
        "mixed_split_policy": len(split_kinds) > 1,
    }
    all_receipts_executable = all(_split_executable(receipt) for receipt in valid_receipts)
    all_receipts_split_bound = all(_missing_split_count(receipt) == 0 for receipt in valid_receipts)
    all_mutation_denied = not any(_mutation_requested(receipt) for receipt in valid_receipts)
    paired_counts = [_sample_paired_count(receipt) for receipt in valid_receipts]
    event_key_sets = [_series_event_keys(receipt) for receipt in valid_receipts]
    shared_event_count = len(set.intersection(*event_key_sets)) if event_key_sets and all(event_key_sets) else 0
    deltas = [
        (_candidate_id(receipt), _mean_delta(receipt))
        for receipt in valid_receipts
        if _mean_delta(receipt) is not None and _candidate_id(receipt)
    ]
    best = min(deltas, key=lambda item: float(item[1])) if deltas else (None, None)
    worst = max(deltas, key=lambda item: float(item[1])) if deltas else (None, None)

    receipt_reasons = [reason for row in blocked_variants for reason in row.get("reasons", [])]
    primary_reason = _first_blocking_reason(
        candidate_count=len(candidate_ids),
        mixed=mixed,
        receipt_reasons=receipt_reasons,
    )
    baseline_id = baseline_ids[0] if len(baseline_ids) == 1 else None
    loss_metric = loss_metrics[0] if len(loss_metrics) == 1 else None
    key_schema = key_schemas[0] if len(key_schemas) == 1 else None
    split_kind = split_kinds[0] if len(split_kinds) == 1 else None
    family_loss_matrix = build_family_loss_matrix(
        valid_receipts,
        baseline_variant_id=baseline_id,
        candidate_variant_ids=candidate_ids,
        loss_metric=loss_metric,
        comparison_key_schema=key_schema,
        split_policy=split_kind,
    )
    matrix_coverage = family_loss_matrix.get("coverage") if isinstance(family_loss_matrix.get("coverage"), Mapping) else {}
    matrix_diagnostics = (
        family_loss_matrix.get("dependence_diagnostics")
        if isinstance(family_loss_matrix.get("dependence_diagnostics"), Mapping)
        else {}
    )
    matrix_shared_event_count = _as_int(matrix_coverage.get("shared_event_count"))
    blocked_status: Optional[str] = None
    if primary_reason != "family_level_selection_not_admissive":
        blocked_status = _block_status(primary_reason, candidate_count=len(candidate_ids))

    if blocked_status:
        reality_check = blocked_reality_check(
            status=blocked_status,
            reason=primary_reason,
            sample_size=matrix_shared_event_count,
            minimum_sample=min_bootstrap_sample,
            bootstrap_reps=bootstrap_reps,
            seed=bootstrap_seed,
            block_length=matrix_diagnostics.get("recommended_block_length"),
        )
    else:
        reality_check = reality_check_summary(
            family_loss_matrix,
            min_sample=min_bootstrap_sample,
            bootstrap_reps=bootstrap_reps,
            seed=bootstrap_seed,
            allow_tiny_sample=allow_tiny_bootstrap,
        )
    spa = spa_summary(
        family_loss_matrix,
        min_sample=min_bootstrap_sample,
        bootstrap_reps=bootstrap_reps,
        seed=bootstrap_seed,
        allow_tiny_sample=allow_tiny_bootstrap,
        blocked_status=blocked_status,
    )
    spa_readiness = spa_readiness_summary(
        family_loss_matrix,
        reality_check_status=_as_text(reality_check.get("status")),
        min_sample=min_bootstrap_sample,
        blocked_status=blocked_status,
        spa_block=spa,
    )
    mcs = model_confidence_set_summary(
        family_loss_matrix,
        candidate_variant_ids=candidate_ids,
        blocked_status=blocked_status,
        min_sample=min_bootstrap_sample,
        bootstrap_reps=bootstrap_reps,
        seed=bootstrap_seed,
        alpha=mcs_alpha,
        allow_tiny_sample=allow_tiny_bootstrap,
    )
    reality_status = _as_text(reality_check.get("status"))
    bootstrap_conformance = (
        reality_check.get("bootstrap_conformance")
        if isinstance(reality_check.get("bootstrap_conformance"), Mapping)
        else {}
    )
    if blocked_status:
        family_level_inference_status = "blocked"
        bootstrap_status = "blocked"
    elif reality_status == "computed_bootstrap":
        family_level_inference_status = "computed_shadow_only"
        bootstrap_status = "computed"
    elif reality_status == "not_computed_minimum_sample":
        family_level_inference_status = "sample_gated"
        bootstrap_status = "sample_gated"
    else:
        family_level_inference_status = "blocked" if reality_status.startswith("not_computed") else "reserved"
        bootstrap_status = "blocked" if reality_status.startswith("not_computed") else "reserved"

    selection_id = "fin_model_sel_" + _stable_digest(
        method,
        ",".join(receipt_refs),
        ",".join(candidate_ids),
        primary_reason,
        matrix_shared_event_count,
        bootstrap_reps,
        bootstrap_seed,
        min_bootstrap_sample,
        mcs_alpha,
    )
    decision_status = "insufficient_variant_family" if len(candidate_ids) < 2 else "shadow_family_only"

    return {
        "schema_version": RECEIPT_SCHEMA_VERSION,
        "selection_id": selection_id,
        "method": method,
        "baseline_variant_id": baseline_id,
        "variant_set": sorted(set(([baseline_id] if baseline_id else []) + candidate_ids)),
        "candidate_variant_ids": candidate_ids,
        "receipt_refs": receipt_refs,
        "loss_metric": loss_metric,
        "comparison_key_schema": key_schema,
        "split_policy": {
            "kind": split_kind,
            "kinds_seen": split_kinds,
            "all_receipts_executable": all_receipts_executable,
            "all_receipts_split_bound": all_receipts_split_bound,
            **mixed,
        },
        "sample": {
            "candidate_count": len(candidate_ids),
            "receipt_count": len(valid_receipts),
            "min_paired_event_count": min(paired_counts) if paired_counts else 0,
            "max_paired_event_count": max(paired_counts) if paired_counts else 0,
            "pairwise_shared_event_count": shared_event_count,
            "shared_event_count": matrix_shared_event_count,
            "dropped_unshared_event_count": _as_int(matrix_coverage.get("dropped_unshared_event_count")),
            "blocked_variant_count": len(blocked_variants),
            "missing_split_membership_count": sum(_missing_split_count(receipt) for receipt in valid_receipts),
            "candidate_smoke_test_count": sum(_candidate_smoke_count(receipt) for receipt in valid_receipts),
            "unpaired_event_count": sum(_unpaired_count(receipt) for receipt in valid_receipts),
            "excluded_split_count": sum(_excluded_split_count(receipt) for receipt in valid_receipts),
        },
        "family_loss_matrix": family_loss_matrix,
        "bootstrap": {
            "status": bootstrap_status,
            "method": matrix_diagnostics.get("bootstrap_method") or "stationary_bootstrap",
            "authority": MODEL_SELECTION_STATS_AUTHORITY,
            "bootstrap_reps": bootstrap_reps,
            "seed": bootstrap_seed,
            "minimum_sample": min_bootstrap_sample,
            "sample_size": matrix_shared_event_count,
            "p_values_computed": reality_check.get("p_value") is not None,
            "allow_tiny_sample": allow_tiny_bootstrap,
            "fixture_only": bool(allow_tiny_bootstrap),
            "conformance_status": bootstrap_conformance.get("status"),
        },
        "bootstrap_conformance": dict(bootstrap_conformance),
        "bootstrap_reference_status": "not_started",
        "spa_readiness": spa_readiness,
        "family_statistics": {
            "statistics_authority": MODEL_SELECTION_STATS_AUTHORITY,
            "family_loss_matrix_authority": FAMILY_LOSS_MATRIX_AUTHORITY,
            "spa_statistics_authority": SPA_STATISTICS_AUTHORITY,
            "best_mean_delta_variant_id": best[0],
            "best_mean_delta": round(float(best[1]), 10) if best[1] is not None else None,
            "worst_mean_delta_variant_id": worst[0],
            "worst_mean_delta": round(float(worst[1]), 10) if worst[1] is not None else None,
            "retained_shadow_variants": candidate_ids,
            "blocked_variants": blocked_variants,
            "blocked_reason_counts": dict(sorted(reason_counts.items())),
            "reality_check": reality_check,
            "spa": spa,
            "model_confidence_set": mcs,
            "family_level_inference_status": family_level_inference_status,
        },
        "decision": {
            "status": decision_status,
            "optimizer_permission": False,
            "calculator_mutation_permission": False,
            "reason": primary_reason,
            "reasons": [primary_reason] if primary_reason else [],
            "all_mutation_denied_by_pairwise_receipts": all_mutation_denied,
        },
    }


def _paths_from_config(value: Any) -> List[Path]:
    if isinstance(value, str):
        return [Path(part.strip()) for part in value.split(",") if part.strip()]
    if isinstance(value, list):
        return [Path(_as_text(path)) for path in value if _as_text(path)]
    return []


def run(config: Dict[str, Any], run_dir: Optional[Path] = None) -> Dict[str, Any]:
    try:
        paths = _paths_from_config(config.get("variant_gates"))
        if not paths:
            raise ValueError("at least one --variant-gates path is required")
        method = _as_text(config.get("method") or DEFAULT_METHOD)
        receipts = [_receipt(_read_json(path)) for path in paths]
        receipt = build_model_selection_receipt(
            receipts,
            method=method,
            bootstrap_reps=_as_int(config.get("bootstrap_reps"), DEFAULT_BOOTSTRAP_REPS),
            bootstrap_seed=_as_int(config.get("bootstrap_seed"), DEFAULT_BOOTSTRAP_SEED),
            min_bootstrap_sample=_as_int(config.get("min_bootstrap_sample"), DEFAULT_MIN_BOOTSTRAP_SAMPLE),
            mcs_alpha=float(config.get("mcs_alpha") or DEFAULT_MCS_ALPHA),
            allow_tiny_bootstrap=bool(config.get("allow_tiny_bootstrap")),
        )
        now = feed_envelope.utc_now()
        runtime = config.get("runtime", {}) if isinstance(config.get("runtime"), Mapping) else {}
        run_id = _as_text(runtime.get("run_id") or receipt["selection_id"])
        diagnostics = feed_envelope.new_diagnostics(
            input_rows=len(paths),
            output_rows=1,
            dropped_rows=0,
            candidate_count=receipt["sample"]["candidate_count"],
            decision=receipt["decision"],
        )
        metadata = feed_envelope.build_metadata(
            tool=TOOL_NAME,
            status="success",
            now=now,
            run_id=run_id,
            as_of=_as_text(runtime.get("as_of") or now.iso),
            items_count=1,
            diagnostics=diagnostics,
            data_schema_version=DATA_SCHEMA_VERSION,
            timestamp=now.iso,
        )
        return {"metadata": metadata, "data": {"receipt": receipt}}
    except Exception as exc:
        return _failure_envelope(str(exc), run_dir=run_dir)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build a finance model-selection receipt from variant gates.")
    parser.add_argument("--variant-gates", action="append", default=[], help="finance_variant_admission receipt envelope. Repeatable.")
    parser.add_argument("--method", default=DEFAULT_METHOD, choices=sorted(SUPPORTED_METHODS))
    parser.add_argument("--bootstrap-reps", type=int, default=DEFAULT_BOOTSTRAP_REPS)
    parser.add_argument("--bootstrap-seed", type=int, default=DEFAULT_BOOTSTRAP_SEED)
    parser.add_argument("--min-bootstrap-sample", type=int, default=DEFAULT_MIN_BOOTSTRAP_SAMPLE)
    parser.add_argument("--mcs-alpha", type=float, default=DEFAULT_MCS_ALPHA)
    parser.add_argument("--allow-tiny-bootstrap", action="store_true", help="Test-only escape hatch for deterministic tiny bootstrap fixtures.")
    parser.add_argument("--json", action="store_true", help="Print JSON envelope.")
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    payload = run(
        {
            "variant_gates": args.variant_gates,
            "method": args.method,
            "bootstrap_reps": args.bootstrap_reps,
            "bootstrap_seed": args.bootstrap_seed,
            "min_bootstrap_sample": args.min_bootstrap_sample,
            "mcs_alpha": args.mcs_alpha,
            "allow_tiny_bootstrap": args.allow_tiny_bootstrap,
            "runtime": {"run_id": TOOL_NAME},
        }
    )
    text = json.dumps(payload, indent=2, sort_keys=True)
    print(text if args.json else text)
    return 0 if payload.get("metadata", {}).get("status") == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
