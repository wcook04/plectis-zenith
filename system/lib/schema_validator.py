r"""

[PURPOSE]
- Teleology: Provide machine-checkable, deterministic validators for CP1 and CP2 artifact schemas,
  producing stable ValidationResult objects that the engine can act on (retry, hard-fail, persist).
- Mechanism: Pure functions over dict payloads with stable error codes;
  ValidationResult.errors is always sorted(set(...)) for deterministic ordering.

[INTERFACE]
- Reads: dict payloads (CP1/CP2 JSON objects) and optional subject_run_dir Path.
- Writes: None (pure validation; payloads are never mutated).
- Fails: Detected artifact validation failures are encoded in ValidationResult.errors; callers supply dictionary payloads.

[FLOW]
- ValidationResult: dataclass aggregate result with an ok flag and sorted, deduplicated failure errors.
- validate_cp1: structural + uniqueness + ref_id/ledger_id format + citation + word-count checks.
- validate_cp2: runs validate_cp1 then adds predictions_t, forecast_rationale, observation grounding, and universe checks.
- validate_golden_ids: Oracle-only guard; validates CP2 evidence ledger_ids against snapshot ledger set.
- _load_target_id_set: discovers measurements+SUBSYSTEMS target_id universe from subject_run_dir for OUT_OF_UNIVERSE guard.
- When-needed: Open when CP1, CP2, or Oracle artifact payloads need deterministic schema validation and stable error-code semantics before engine, server, or grading logic proceeds.
- Escalates-to: system/lib/citations.py; system/lib/artifacts.py; codex/contracts/contract_config.json
- Navigation-group: kernel_lib

[DEPENDENCIES]
- Couples: system.lib.artifacts supplies subject-run target_id universes and snapshot ledger IDs; contract_config.json overrides validation thresholds.
- Internal: system.lib.citations (detect_malformed_citations, extract_citations, validate_citations).

[CONSTRAINTS]
- Validators must not mutate payloads. Derived values (e.g. normalized lane) live in local variables.
- ValidationResult.errors is always sorted(set(errors)) — deterministic, deduplicated.
- detect_malformed_citations runs before validate_citations.
- Word count: len(re.findall(r"\S+", text)) on raw text.
- Lane/target_id comparison: .upper().strip() normalization.
- This module must remain free of engine, server, and bridge imports.

"""
from __future__ import annotations

import json
import math
import re
from datetime import datetime, timezone
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, List, Optional, Set

from system.lib.citations import detect_malformed_citations, extract_citations, validate_citations
from system.lib.artifacts import load_observation_universe, load_snapshot_ledger_ids
from system.lib.empirical_forecast import rule_errors, target_errors
from system.lib.judgmental_forecast import rule_errors as quantile_rule_errors, target_errors as quantile_target_errors

# ---------------------------------------------------------------------------
# Format constants
# ---------------------------------------------------------------------------
_REF_ID_RE = re.compile(r"^\[([1-9]\d*)\]$")
_ARTIFACT_HANDLE_RE = re.compile(r"^[a-z][a-z0-9_]*:[A-Za-z0-9._-]+$")
_VALID_DIRECTIONS = frozenset({"UP", "DOWN"})

_DEFAULT_CONFIG = {
    "epicentre_thesis_min_words": 150,
    "forecast_rationale_base_words": 75,
    "forecast_rationale_per_prediction_words": 30,
    "lane_prefix_map": {
        "S": "MEASUREMENTS",
        "M": "ENVIRONMENT",
        "P": "INTERVENTIONS",
        "N": "EVENTS",
        "E": "SUBSYSTEMS",
        "C": "DERIVED",
        "X": "UNKNOWN",
    },
}


# ---------------------------------------------------------------------------
# ValidationResult
# ---------------------------------------------------------------------------

@dataclass
class ValidationResult:
    """
    [ROLE]
    - Teleology: Aggregate result of a CP schema validation pass with a stable ok flag and error list.
    - Ownership: Owns the ok bool and the sorted, deduplicated errors list produced by the class methods.
    - Mutability: Effectively immutable after construction via success() or failure() class methods.
    - Concurrency: Safe to read from multiple threads; not designed for concurrent mutation.
    """
    ok: bool
    errors: List[str] = field(default_factory=list)

    @classmethod
    def success(cls) -> "ValidationResult":
        return cls(ok=True, errors=[])

    @classmethod
    def failure(cls, errors: List[str]) -> "ValidationResult":
        return cls(ok=False, errors=sorted(set(errors)))


# ---------------------------------------------------------------------------
# Config loader
# ---------------------------------------------------------------------------

def _load_config() -> dict:
    """
    [ACTION]
    - Load validator thresholds from contract_config.json relative to the project root.
    - Falls back to _DEFAULT_CONFIG if the file cannot be read (e.g. in isolated test environments).
    """
    config_path = Path(__file__).parent.parent.parent / "codex" / "contracts" / "contract_config.json"
    try:
        with open(config_path) as f:
            loaded = json.load(f)
            if not isinstance(loaded, dict):
                return dict(_DEFAULT_CONFIG)
            merged = dict(_DEFAULT_CONFIG)
            for key, value in loaded.items():
                if key == "lane_prefix_map":
                    if isinstance(value, dict):
                        merged[key] = value
                else:
                    merged[key] = value
            return merged
    except Exception:
        return dict(_DEFAULT_CONFIG)


def _build_ledger_id_re(cfg: dict) -> re.Pattern:
    """
    [ACTION]
    - Build ledger_id regex from contract_config lane_prefix_map.
    - Falls back to default prefixes when lane_prefix_map is missing/malformed.
    """
    raw_map = cfg.get("lane_prefix_map", {})
    prefixes: List[str] = []
    if isinstance(raw_map, dict):
        for key in raw_map.keys():
            if isinstance(key, str) and len(key) == 1 and key.isalpha() and key.isupper():
                prefixes.append(key)

    if not prefixes:
        prefixes = list(_DEFAULT_CONFIG["lane_prefix_map"].keys())

    # Character class is deterministic and safely escaped.
    prefix_class = "".join(sorted(set(prefixes)))
    return re.compile(rf"^[{re.escape(prefix_class)}]_[0-9A-F]{{8}}$")


# ---------------------------------------------------------------------------
# Word count
# ---------------------------------------------------------------------------

def _count_words(text: str) -> int:
    return len(re.findall(r"\S+", text))


def _parse_iso_datetime(raw: Any) -> Optional[datetime]:
    """Parse numeric/ISO timestamps into UTC datetime objects."""
    if isinstance(raw, (int, float)):
        try:
            return datetime.fromtimestamp(float(raw), tz=timezone.utc)
        except Exception:
            return None
    if isinstance(raw, str):
        token = raw.strip()
        if not token:
            return None
        try:
            parsed = datetime.fromisoformat(token.replace("Z", "+00:00"))
        except ValueError:
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    return None


# ---------------------------------------------------------------------------
# Evidence dictionary validation (shared between CP1 and CP2)
# ---------------------------------------------------------------------------

def _validate_evidence_dictionary(evidence: List[Any], ledger_id_re: re.Pattern) -> List[str]:
    """
    [ACTION]
    - Validate all EvidenceUnit entries for field presence, ref_id format, ledger_id format,
      and uniqueness across the array.
    - Returns list of error strings; empty list if all entries are valid.
    - When-needed: Open when CP1 or CP2 evidence validation needs the authoritative `INVALID_LEDGER_ID` route for malformed evidence_dictionary ledger ids before artifact acceptance or retry logic.
    - Escalates-to: system/lib/artifacts.py; codex/contracts/contract_config.json
    """
    errors: List[str] = []
    seen_ref_ids: Set[str] = set()
    seen_ledger_ids: Set[str] = set()

    for i, entry in enumerate(evidence):
        if not isinstance(entry, dict):
            errors.append(f"MISSING_FIELD: evidence[{i}] is not an object")
            continue

        for fld in ("ref_id", "ledger_id", "subject", "signal_summary"):
            if not entry.get(fld):
                errors.append(f"MISSING_FIELD: evidence[{i}].{fld}")

        ref_id = entry.get("ref_id", "")
        ledger_id = entry.get("ledger_id", "")

        if ref_id:
            if not _REF_ID_RE.fullmatch(str(ref_id)):
                errors.append(f"INVALID_REF_ID: evidence[{i}].ref_id={ref_id!r}")
            elif ref_id in seen_ref_ids:
                errors.append(f"DUPLICATE_REF_ID: {ref_id}")
            else:
                seen_ref_ids.add(ref_id)

        if ledger_id:
            if not ledger_id_re.fullmatch(str(ledger_id)):
                errors.append(f"INVALID_LEDGER_ID: evidence[{i}].ledger_id={ledger_id!r}")
            elif ledger_id in seen_ledger_ids:
                errors.append(f"DUPLICATE_LEDGER_ID: {ledger_id}")
            else:
                seen_ledger_ids.add(ledger_id)

    return errors


# ---------------------------------------------------------------------------
# target_id universe loader for CP2 OUT_OF_UNIVERSE guard
# ---------------------------------------------------------------------------

def _load_target_id_set(subject_run_dir: Path) -> Optional[Set[str]]:
    """
    [ACTION]
    - Load the observation target_id universe from subject_run_dir/artifacts/ by unioning
      global_measurements_feed and global_subsystems_feed artifacts.
    - Delegates to system.lib.artifacts.load_observation_universe which handles both flat and
      nested artifact shapes and falls back to glob patterns if named feeds are absent.
    - Returns set of uppercase target_id strings, or None if no target_id set could be extracted.
    - Never raises; returns None on any IO or shape failure.
    """
    return load_observation_universe(Path(subject_run_dir))


def _load_snapshot_ledger_set(subject_run_dir: Path) -> Optional[Set[str]]:
    """
    [ACTION]
    - Load the Golden-ID snapshot ledger set from subject_run_dir/artifacts.
    - Delegates to system.lib.artifacts.load_snapshot_ledger_ids.
    - Returns None if no snapshot ledger_ids are discoverable.
    - Never raises.
    """
    return load_snapshot_ledger_ids(Path(subject_run_dir))


def validate_golden_ids(
    evidence: Any,
    subject_run_dir: Optional[Path],
) -> ValidationResult:
    """
    [ACTION]
    - Oracle-only guard: every evidence_dictionary.ledger_id must exist in the T-n snapshot
      ledger set derived from subject_run_dir.
    - Returns INVALID_GOLDEN_ID for each non-snapshot ledger_id.
    - Returns MISSING_CONTEXT when snapshot ledger set cannot be loaded.
    - Does not mutate evidence.
    - When-needed: Open when Oracle validation must prove that an `INVALID_GOLDEN_ID` failure comes from evidence ledger ids outside the subject run's snapshot ledger set rather than later realized artifacts.
    - Escalates-to: system/lib/artifacts.py; codex/contracts/contract_config.json
    """
    errors: List[str] = []

    if not isinstance(evidence, list):
        return ValidationResult.success()

    if subject_run_dir is None:
        return ValidationResult.failure(
            ["MISSING_CONTEXT: could not load golden snapshot ledger set from subject_run_dir"]
        )

    snapshot_ids = _load_snapshot_ledger_set(Path(subject_run_dir))
    if snapshot_ids is None:
        return ValidationResult.failure(
            ["MISSING_CONTEXT: could not load golden snapshot ledger set from subject_run_dir"]
        )

    for i, entry in enumerate(evidence):
        if not isinstance(entry, dict):
            continue
        ledger_id = entry.get("ledger_id")
        if not ledger_id:
            continue
        normalized = str(ledger_id)
        if normalized not in snapshot_ids:
            errors.append(
                f"INVALID_GOLDEN_ID: evidence[{i}].ledger_id={normalized!r} not in subject snapshot"
            )

    if errors:
        return ValidationResult.failure(errors)
    return ValidationResult.success()


def _validate_cross_corr_block_list(
    payload: Any,
    field: str,
    *,
    require_direction: bool = False,
    require_subjects: bool = False,
    require_target_ids: bool = False,
) -> List[str]:
    errors: List[str] = []
    items = payload.get(field) if isinstance(payload, dict) else None
    if not isinstance(items, list):
        errors.append(f"MISSING_FIELD: {field} must be a list")
        return errors
    for i, entry in enumerate(items):
        if not isinstance(entry, dict):
            errors.append(f"MISSING_FIELD: {field}[{i}] is not an object")
            continue
        required_fields: List[str] = ["id", "name", "lanes", "summary"]
        if require_subjects:
            required_fields.append("subjects")
        if require_target_ids:
            required_fields.append("target_ids")
        for req in required_fields:
            if req not in entry:
                errors.append(f"MISSING_FIELD: {field}[{i}].{req}")
        lanes = entry.get("lanes")
        if not isinstance(lanes, list) or not all(isinstance(x, str) and x.strip() for x in lanes):
            errors.append(f"INVALID_FIELD: {field}[{i}].lanes must be non-empty list[str]")
        if "subjects" in entry:
            subjects = entry.get("subjects")
            if not isinstance(subjects, list) or not all(isinstance(x, str) and x.strip() for x in subjects):
                errors.append(f"INVALID_FIELD: {field}[{i}].subjects must be list[str]")
        if "target_ids" in entry:
            target_ids = entry.get("target_ids")
            if not isinstance(target_ids, list):
                errors.append(f"INVALID_FIELD: {field}[{i}].target_ids must be list[str]")
            else:
                for t in target_ids:
                    if not isinstance(t, str) or not t.strip():
                        errors.append(f"INVALID_FIELD: {field}[{i}].target_ids contains empty token")
        if require_direction:
            consensus = entry.get("direction_consensus")
            if consensus not in {"INCREASE", "DECREASE", "CONTESTED", "N/A"}:
                errors.append(
                    f"INVALID_FIELD: {field}[{i}].direction_consensus={consensus!r} "
                    "(must be INCREASE|DECREASE|CONTESTED|N/A)"
                )
    return errors


def validate_cross_corr_v1(payload: Any) -> ValidationResult:
    """
    [ACTION]
    - Teleology: Validate a structured cross_corr_v1 JSON payload for required top-level block arrays.
    - Guarantee: Returns a ValidationResult with sorted, deduplicated errors and no payload mutation.
    - Fails: None.
    - When-needed: Open when a structured `cross_corr_v1` payload needs the authoritative field-presence and block-shape validator.
    - Escalates-to: codex/contracts/contract_config.json; system/lib/contracts.py
    """
    if not isinstance(payload, dict):
        return ValidationResult.failure(["MISSING_FIELD: payload is not a JSON object"])
    errors: List[str] = []
    errors.extend(_validate_cross_corr_block_list(payload, "swarms", require_subjects=True))
    errors.extend(_validate_cross_corr_block_list(payload, "bifurcations", require_subjects=True))
    errors.extend(_validate_cross_corr_block_list(payload, "orphans", require_subjects=True))
    errors.extend(_validate_cross_corr_block_list(payload, "confidence_asymmetries", require_subjects=True))
    if errors:
        return ValidationResult.failure(errors)
    return ValidationResult.success()


def validate_cross_corr_v2(payload: Any) -> ValidationResult:
    """
    [ACTION]
    - Teleology: Validate a structured cross_corr_v2 JSON payload for directional block validity and target-union consistency.
    - Guarantee: Returns a ValidationResult with sorted, deduplicated errors and no payload mutation.
    - Fails: None.
    - When-needed: Open when a structured `cross_corr_v2` payload must be checked for directional block validity and target-union consistency.
    - Escalates-to: codex/contracts/contract_config.json; system/lib/contracts.py
    """
    if not isinstance(payload, dict):
        return ValidationResult.failure(["MISSING_FIELD: payload is not a JSON object"])
    errors: List[str] = []
    errors.extend(
        _validate_cross_corr_block_list(
            payload, "target_swarms", require_direction=True, require_target_ids=True
        )
    )
    errors.extend(
        _validate_cross_corr_block_list(
            payload, "directional_conflicts", require_direction=True, require_target_ids=True
        )
    )
    errors.extend(
        _validate_cross_corr_block_list(
            payload, "solo_targets", require_direction=True, require_target_ids=True
        )
    )
    errors.extend(
        _validate_cross_corr_block_list(
            payload, "thesis_stress", require_direction=True, require_target_ids=True
        )
    )

    valid_targets = payload.get("valid_prediction_targets")
    if not isinstance(valid_targets, list):
        errors.append("MISSING_FIELD: valid_prediction_targets must be a list")
    else:
        normalized_targets = {
            str(t).upper().strip()
            for t in valid_targets
            if isinstance(t, str) and str(t).strip()
        }
        if len(normalized_targets) != len(valid_targets):
            errors.append("INVALID_FIELD: valid_prediction_targets must be unique non-empty target_id strings")

        expected_targets: Set[str] = set()
        for field in ("target_swarms", "solo_targets"):
            items = payload.get(field)
            if not isinstance(items, list):
                continue
            for entry in items:
                if not isinstance(entry, dict):
                    continue
                target_ids = entry.get("target_ids")
                if not isinstance(target_ids, list):
                    continue
                for token in target_ids:
                    t = str(token).upper().strip()
                    if t and t != "NONE":
                        expected_targets.add(t)
        if expected_targets and normalized_targets != expected_targets:
            errors.append(
                "INVALID_FIELD: valid_prediction_targets must equal union of target_swarms/solo_targets target_ids"
            )

    if errors:
        return ValidationResult.failure(errors)
    return ValidationResult.success()


def _validate_string_list_field(
    value: Any,
    field_name: str,
    errors: List[str],
    *,
    allow_empty: bool = True,
) -> List[str]:
    normalized: List[str] = []
    if not isinstance(value, list):
        errors.append(f"MISSING_FIELD: {field_name} must be a list")
        return normalized
    for idx, item in enumerate(value):
        if not isinstance(item, str) or not item.strip():
            errors.append(f"INVALID_FIELD: {field_name}[{idx}] must be a non-empty string")
            continue
        normalized.append(item.strip())
    if not allow_empty and not normalized:
        errors.append(f"INVALID_FIELD: {field_name} must be a non-empty list[str]")
    return normalized


def _validate_artifact_handle_list(
    value: Any,
    field_name: str,
    errors: List[str],
) -> List[str]:
    handles = _validate_string_list_field(value, field_name, errors)
    for idx, handle in enumerate(handles):
        if not _ARTIFACT_HANDLE_RE.fullmatch(handle):
            errors.append(
                f"INVALID_HANDLE_FORMAT: {field_name}[{idx}]={handle!r} "
                "(expected <artifact>:<identifier>)"
            )
    return handles


def validate_prediction_reconciliation(payload: Any) -> ValidationResult:
    """[ACTION]
    - Teleology: Validate the deterministic Oracle `prediction_reconciliation` artifact before storage or downstream grading use.
    - Mechanism: Check required top-level fields, row uniqueness and numeric invariants, optional environment rows, and summary/count coherence.
    - Guarantee: Returns a ValidationResult with sorted, deduplicated errors and never mutates the payload.
    - Fails: None.
    - When-needed: Open when Oracle comparison output must be accepted or rejected as a valid `prediction_reconciliation` artifact.
    - Escalates-to: system/lib/run_compare.py::grade_predictions; system/lib/artifacts.py
    """
    if not isinstance(payload, dict):
        return ValidationResult.failure(["MISSING_FIELD: payload is not a JSON object"])

    errors: List[str] = []
    status = payload.get("status")
    if status not in ("AVAILABLE", "ABSTAINED"):
        errors.append(f"INVALID_FIELD: status={status!r} (must be AVAILABLE or ABSTAINED)")
    if status == "ABSTAINED" and payload.get("subject_decision_status") != "ABSTAIN":
        errors.append("INVALID_FIELD: ABSTAINED requires subject_decision_status ABSTAIN")
    if "subject_decision_status" in payload:
        expected_decision = "ABSTAIN" if status == "ABSTAINED" else "FORECAST"
        if payload["subject_decision_status"] != expected_decision:
            errors.append("INVALID_FIELD: reconciliation and subject decision disagree")

    for field in ("subject_run_id", "truth_run_id"):
        value = payload.get(field)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"MISSING_FIELD: {field}")

    rows = payload.get("rows")
    if status == "ABSTAINED" and rows != []:
        errors.append("INVALID_FIELD: ABSTAINED reconciliation must have no prediction rows")
    if not isinstance(rows, list) or (not rows and status != "ABSTAINED"):
        errors.append("MISSING_FIELD: rows must be a non-empty list")
        rows = []

    seen_targets: Set[str] = set()
    for idx, row in enumerate(rows):
        if not isinstance(row, dict):
            errors.append(f"MISSING_FIELD: rows[{idx}] is not an object")
            continue

        target_id = row.get("target_id")
        if not isinstance(target_id, str) or not target_id.strip():
            errors.append(f"MISSING_FIELD: rows[{idx}].target_id")
        else:
            normalized_target = target_id.strip().upper()
            if normalized_target in seen_targets:
                errors.append(f"DUPLICATE_TARGET_ID: rows[{idx}].target_id={normalized_target!r}")
            seen_targets.add(normalized_target)

        target_kind = row.get("target_kind")
        if target_kind not in {"MEASUREMENTS", "SUBSYSTEMS"}:
            errors.append(f"INVALID_FIELD: rows[{idx}].target_kind={target_kind!r}")

        direction = row.get("prediction_direction")
        if direction not in _VALID_DIRECTIONS | ({'FLAT'} if payload.get('subject_forecast_basis') == 'JUDGMENTAL' else set()):
            errors.append(
                f"INVALID_FIELD: rows[{idx}].prediction_direction={direction!r} "
                "(must be UP or DOWN)"
            )

        for field in (
            "subject_snapshot_value",
            "predicted_target_value",
            "realized_truth_value",
            "absolute_delta",
            "percent_delta",
        ):
            value = row.get(field)
            if not isinstance(value, (int, float)) or not math.isfinite(float(value)):
                errors.append(f"INVALID_FIELD: rows[{idx}].{field} must be finite numeric")

        if not isinstance(row.get("directional_correct"), bool):
            errors.append(f"INVALID_FIELD: rows[{idx}].directional_correct must be boolean")

        if "rank" in row and (
            not isinstance(row.get("rank"), int) or isinstance(row.get("rank"), bool) or row.get("rank") < 1
        ):
            errors.append(f"INVALID_FIELD: rows[{idx}].rank must be positive integer when present")

    environment_rows = payload.get("environment_rows")
    if environment_rows is not None:
        if not isinstance(environment_rows, list):
            errors.append("INVALID_FIELD: environment_rows must be a list when present")
        else:
            for idx, row in enumerate(environment_rows):
                if not isinstance(row, dict):
                    errors.append(f"MISSING_FIELD: environment_rows[{idx}] is not an object")
                    continue
                for field in ("series_id", "subject_value", "realized_value", "comparison_basis"):
                    if field not in row:
                        errors.append(f"MISSING_FIELD: environment_rows[{idx}].{field}")
                if not isinstance(row.get("series_id"), str) or not str(row.get("series_id")).strip():
                    errors.append(f"INVALID_FIELD: environment_rows[{idx}].series_id must be non-empty string")
                if not isinstance(row.get("comparison_basis"), str) or not str(row.get("comparison_basis")).strip():
                    errors.append(
                        f"INVALID_FIELD: environment_rows[{idx}].comparison_basis must be non-empty string"
                    )

    summary = payload.get("summary")
    if not isinstance(summary, dict):
        errors.append("MISSING_FIELD: summary must be an object")
    else:
        row_count = summary.get("row_count")
        correct = summary.get("directionally_correct_count")
        incorrect = summary.get("directionally_incorrect_count")

        for field in ("row_count", "directionally_correct_count", "directionally_incorrect_count"):
            value = summary.get(field)
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                errors.append(f"INVALID_FIELD: summary.{field} must be non-negative integer")

        if isinstance(row_count, int) and row_count != len(rows):
            errors.append(
                f"INVALID_FIELD: summary.row_count={row_count} must equal len(rows)={len(rows)}"
            )
        if (
            isinstance(row_count, int)
            and isinstance(correct, int)
            and isinstance(incorrect, int)
            and correct + incorrect != row_count
        ):
            errors.append(
                "INVALID_FIELD: summary direction counts must sum to summary.row_count"
            )

        if len(rows) == 0:
            for field in ("largest_absolute_miss_target", "largest_percent_miss_target"):
                if summary.get(field) is not None:
                    errors.append(
                        f"INVALID_FIELD: summary.{field} must be absent when rows is empty"
                    )
        else:
            if summary.get("largest_absolute_miss_target") is not None:
                largest_abs = str(summary.get("largest_absolute_miss_target")).upper().strip()
                if largest_abs not in seen_targets:
                    errors.append(
                        "INVALID_FIELD: summary.largest_absolute_miss_target must reference rows.target_id"
                    )
            if summary.get("largest_percent_miss_target") is not None:
                largest_pct = str(summary.get("largest_percent_miss_target")).upper().strip()
                if largest_pct not in seen_targets:
                    errors.append(
                        "INVALID_FIELD: summary.largest_percent_miss_target must reference rows.target_id"
                    )

    if errors:
        return ValidationResult.failure(errors)
    return ValidationResult.success()


def validate_oracle_cp2_meta(payload: Any) -> ValidationResult:
    """[ACTION]
    - Teleology: Validate Oracle-only `oracle_meta` structure and artifact-handle syntax inside a CP2 payload.
    - Mechanism: Require oracle_meta, validate realized/truth handle lists, and check optional exclusions and hindsight note lists.
    - Guarantee: Returns a ValidationResult with deterministic error ordering and no payload mutation.
    - Fails: None.
    - When-needed: Open when Oracle-only `oracle_meta` on a CP2 payload needs structural validation before persistence or downstream critique generation.
    - Escalates-to: system/lib/artifacts.py; codex/contracts/contract_config.json
    """
    if not isinstance(payload, dict):
        return ValidationResult.failure(["MISSING_FIELD: payload is not a JSON object"])

    errors: List[str] = []
    oracle_meta = payload.get("oracle_meta")
    if not isinstance(oracle_meta, dict):
        return ValidationResult.failure(["MISSING_FIELD: oracle_meta"])

    _validate_artifact_handle_list(
        oracle_meta.get("truth_influence_refs", []),
        "oracle_meta.truth_influence_refs",
        errors,
    )
    _validate_artifact_handle_list(
        oracle_meta.get("realized_diff_refs", []),
        "oracle_meta.realized_diff_refs",
        errors,
    )

    explicit_exclusions = oracle_meta.get("explicit_exclusions", [])
    if explicit_exclusions is not None:
        if not isinstance(explicit_exclusions, list):
            errors.append("INVALID_FIELD: oracle_meta.explicit_exclusions must be a list when present")
        else:
            for idx, item in enumerate(explicit_exclusions):
                if not isinstance(item, dict):
                    errors.append(f"MISSING_FIELD: oracle_meta.explicit_exclusions[{idx}] is not an object")
                    continue
                for field in ("kind", "ref", "reason"):
                    value = item.get(field)
                    if not isinstance(value, str) or not value.strip():
                        errors.append(
                            f"MISSING_FIELD: oracle_meta.explicit_exclusions[{idx}].{field}"
                        )
                ref = item.get("ref")
                if isinstance(ref, str) and ref.strip() and not _ARTIFACT_HANDLE_RE.fullmatch(ref.strip()):
                    errors.append(
                        "INVALID_HANDLE_FORMAT: "
                        f"oracle_meta.explicit_exclusions[{idx}].ref={ref!r} "
                        "(expected <artifact>:<identifier>)"
                    )

    notes = oracle_meta.get("oracle_hindsight_notes", [])
    if notes is not None:
        _validate_string_list_field(
            notes,
            "oracle_meta.oracle_hindsight_notes",
            errors,
        )

    if errors:
        return ValidationResult.failure(errors)
    return ValidationResult.success()


def validate_realized_hindsight_brief(payload: Any) -> ValidationResult:
    """[ACTION]
    - Teleology: Validate the structured Oracle `realized_hindsight_brief` artifact that explains realized drivers, package splits, and target outcomes.
    - Mechanism: Check required summary strings, driver classifications, mutually exclusive package lists, and per-target outcome blocks.
    - Guarantee: Returns a ValidationResult with deterministic error ordering and no payload mutation.
    - Fails: None.
    - When-needed: Open when Oracle hindsight narration must be accepted or rejected as a valid `realized_hindsight_brief` artifact.
    - Escalates-to: system/lib/artifacts.py; codex/contracts/contract_config.json
    """
    if not isinstance(payload, dict):
        return ValidationResult.failure(["MISSING_FIELD: payload is not a JSON object"])

    errors: List[str] = []
    status = payload.get("status")
    if status != "AVAILABLE":
        errors.append(f"INVALID_FIELD: status={status!r} (must be 'AVAILABLE')")

    for field in ("realized_dominant_force", "regime_summary"):
        value = payload.get(field)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"MISSING_FIELD: {field}")

    driver_classification = payload.get("driver_classification")
    if not isinstance(driver_classification, list) or not driver_classification:
        errors.append("MISSING_FIELD: driver_classification must be a non-empty list")
    else:
        seen_drivers: Set[str] = set()
        for idx, item in enumerate(driver_classification):
            if not isinstance(item, dict):
                errors.append(f"MISSING_FIELD: driver_classification[{idx}] is not an object")
                continue
            driver = item.get("driver")
            if not isinstance(driver, str) or not driver.strip():
                errors.append(f"MISSING_FIELD: driver_classification[{idx}].driver")
            else:
                normalized_driver = driver.strip()
                if normalized_driver in seen_drivers:
                    errors.append(f"DUPLICATE_DRIVER: driver_classification[{idx}].driver={normalized_driver!r}")
                seen_drivers.add(normalized_driver)

            classification = item.get("classification")
            if classification not in {"SURPRISE", "ALREADY_OBSERVED", "PARTIAL_CHANGE", "UNRESOLVED"}:
                errors.append(
                    f"INVALID_FIELD: driver_classification[{idx}].classification={classification!r}"
                )

            why = item.get("why")
            if not isinstance(why, str) or not why.strip():
                errors.append(f"MISSING_FIELD: driver_classification[{idx}].why")

            _validate_string_list_field(
                item.get("supporting_lanes"),
                f"driver_classification[{idx}].supporting_lanes",
                errors,
                allow_empty=False,
            )
            if "affected_targets" in item:
                _validate_string_list_field(
                    item.get("affected_targets"),
                    f"driver_classification[{idx}].affected_targets",
                    errors,
                )

    package_fields = (
        "already_observed_packages",
        "surprise_packages",
        "partial_change_packages",
        "unresolved_packages",
    )
    package_sets: Dict[str, Set[str]] = {}
    for field in package_fields:
        package_sets[field] = set(
            _validate_string_list_field(payload.get(field, []) if field == "unresolved_packages" else payload.get(field), field, errors)
        )

    for left_idx, left in enumerate(package_fields):
        for right in package_fields[left_idx + 1 :]:
            overlap = package_sets[left] & package_sets[right]
            if overlap:
                errors.append(
                    f"INVALID_FIELD: {left} and {right} must be mutually exclusive ({sorted(overlap)})"
                )

    prediction_target_outcomes = payload.get("prediction_target_outcomes")
    if not isinstance(prediction_target_outcomes, list):
        errors.append("MISSING_FIELD: prediction_target_outcomes must be a list")
    else:
        seen_targets: Set[str] = set()
        for idx, item in enumerate(prediction_target_outcomes):
            if not isinstance(item, dict):
                errors.append(f"MISSING_FIELD: prediction_target_outcomes[{idx}] is not an object")
                continue
            target_id = item.get("target_id")
            if not isinstance(target_id, str) or not target_id.strip():
                errors.append(f"MISSING_FIELD: prediction_target_outcomes[{idx}].target_id")
            else:
                normalized_target = target_id.strip().upper()
                if normalized_target in seen_targets:
                    errors.append(
                        f"DUPLICATE_TARGET_ID: prediction_target_outcomes[{idx}].target_id={normalized_target!r}"
                    )
                seen_targets.add(normalized_target)
            what_happened = item.get("what_happened")
            if not isinstance(what_happened, str) or not what_happened.strip():
                errors.append(f"MISSING_FIELD: prediction_target_outcomes[{idx}].what_happened")
            availability_judgement = item.get("availability_judgement")
            if availability_judgement not in {"SURPRISE", "ALREADY_OBSERVED", "PARTIAL_CHANGE", "UNRESOLVED"}:
                errors.append(
                    f"INVALID_FIELD: prediction_target_outcomes[{idx}].availability_judgement={availability_judgement!r}"
                )

    if errors:
        return ValidationResult.failure(errors)
    return ValidationResult.success()


def validate_cp2_critique(payload: Any) -> ValidationResult:
    """[ACTION]
    - Teleology: Validate the structured Oracle `cp2_critique` artifact that records failure modes, critique items, and optional reconstruction guidance.
    - Mechanism: Check required top-level fields, critique-item structure, realized-reference handles, error-class enums, and optional guidance lists.
    - Guarantee: Returns a ValidationResult with deterministic error ordering and no payload mutation.
    - Fails: None.
    - When-needed: Open when Oracle retrospective critique output must be validated before it can be trusted as a `cp2_critique` artifact.
    - Escalates-to: system/lib/artifacts.py; codex/contracts/contract_config.json
    """
    if not isinstance(payload, dict):
        return ValidationResult.failure(["MISSING_FIELD: payload is not a JSON object"])

    errors: List[str] = []
    status = payload.get("status")
    if status != "AVAILABLE":
        errors.append(f"INVALID_FIELD: status={status!r} (must be 'AVAILABLE')")

    root_failure_mode = payload.get("root_failure_mode")
    if not isinstance(root_failure_mode, str) or not root_failure_mode.strip():
        errors.append("MISSING_FIELD: root_failure_mode")

    if "comparison_to_ideal_summary" in payload:
        summary = payload.get("comparison_to_ideal_summary")
        if summary is not None and (not isinstance(summary, str) or not summary.strip()):
            errors.append("INVALID_FIELD: comparison_to_ideal_summary must be a non-empty string when present")

    finding_status = payload.get("finding_status", "ERRORS_FOUND")
    if finding_status not in {"ERRORS_FOUND", "NO_FINDINGS"}:
        errors.append("INVALID_FIELD: finding_status must be ERRORS_FOUND or NO_FINDINGS")
    critique_items = payload.get("critique_items")
    if finding_status == "NO_FINDINGS":
        if critique_items != []:
            errors.append("INVALID_FIELD: NO_FINDINGS requires empty critique_items")
        review = payload.get("no_findings_review")
        if not isinstance(review, dict):
            errors.append("MISSING_FIELD: no_findings_review")
        else:
            if not isinstance(review.get("review_summary"), str) or not review["review_summary"].strip():
                errors.append("MISSING_FIELD: no_findings_review.review_summary")
            for field in ("subject_grounding_refs", "realized_refs"):
                values = review.get(field)
                checker = _validate_artifact_handle_list if field == "realized_refs" else _validate_string_list_field
                checker(values, f"no_findings_review.{field}", errors)
                if not isinstance(values, list) or not values:
                    errors.append(f"MISSING_FIELD: no_findings_review.{field}")
    elif "no_findings_review" in payload:
        errors.append("INVALID_FIELD: error critique cannot carry no_findings_review")
    if not isinstance(critique_items, list) or (not critique_items and finding_status != "NO_FINDINGS"):
        errors.append("MISSING_FIELD: critique_items must be a non-empty list")
    else:
        for idx, item in enumerate(critique_items):
            if not isinstance(item, dict):
                errors.append(f"MISSING_FIELD: critique_items[{idx}] is not an object")
                continue
            scope = item.get("scope")
            if scope not in {
                "thesis",
                "prediction",
                "prediction_justification",
                "citations_grounding",
                "oracle_meta",
            }:
                errors.append(f"INVALID_FIELD: critique_items[{idx}].scope={scope!r}")

            for field in ("target_or_claim", "what_was_wrong"):
                value = item.get(field)
                if not isinstance(value, str) or not value.strip():
                    errors.append(f"MISSING_FIELD: critique_items[{idx}].{field}")

            _validate_string_list_field(
                item.get("subject_grounding_refs"),
                f"critique_items[{idx}].subject_grounding_refs",
                errors,
            )
            _validate_artifact_handle_list(
                item.get("realized_refs"),
                f"critique_items[{idx}].realized_refs",
                errors,
            )
            realized_refs = item.get("realized_refs")
            if not isinstance(realized_refs, list) or not realized_refs:
                errors.append(
                    f"INVALID_FIELD: critique_items[{idx}].realized_refs must be a non-empty list[str]"
                )

            error_class = item.get("error_class")
            if error_class not in {
                "OBSERVATION_MISS",
                "OBSERVATION_NOISE",
                "SYNTHESIS_BLIND",
                "SYNTHESIS_LEAP",
                "PREDICTION_DRIFT",
                "EXOGENOUS_SHOCK",
            }:
                errors.append(f"INVALID_FIELD: critique_items[{idx}].error_class={error_class!r}")

            if "comparison_to_ideal" in item:
                comparison = item.get("comparison_to_ideal")
                if comparison is not None and (not isinstance(comparison, str) or not comparison.strip()):
                    errors.append(
                        f"INVALID_FIELD: critique_items[{idx}].comparison_to_ideal must be a non-empty string when present"
                    )

    if "reconstruction_guidance" in payload:
        guidance = payload.get("reconstruction_guidance")
        if not isinstance(guidance, dict):
            errors.append("INVALID_FIELD: reconstruction_guidance must be an object when present")
        else:
            dominant_force = guidance.get("dominant_force")
            if dominant_force is not None and (not isinstance(dominant_force, str) or not dominant_force.strip()):
                errors.append("INVALID_FIELD: reconstruction_guidance.dominant_force must be a non-empty string")
            for field in ("prefer_targets", "avoid_targets", "eligible_ledger_ids"):
                if field in guidance:
                    _validate_string_list_field(
                        guidance.get(field),
                        f"reconstruction_guidance.{field}",
                        errors,
                    )

    if errors:
        return ValidationResult.failure(errors)
    return ValidationResult.success()


# ---------------------------------------------------------------------------
# Public validators
# ---------------------------------------------------------------------------

def validate_cp1(payload: Any) -> ValidationResult:
    """
    [ACTION]
    - Teleology: Validate a CP1 artifact for evidence-dictionary shape, citation integrity, and thesis word-count compliance.
    - Guarantee: Returns a ValidationResult with sorted, deduplicated errors and no payload mutation.
    - Fails: None.
    - When-needed: Open when a CP1 artifact must be validated for evidence-dictionary shape, citation integrity, and thesis word-count compliance.
    - Escalates-to: system/lib/citations.py; codex/contracts/contract_config.json
    - Navigation-group: kernel_lib
    """
    errors: List[str] = []
    cfg = _load_config()
    ledger_id_re = _build_ledger_id_re(cfg)

    if not isinstance(payload, dict):
        return ValidationResult.failure(["MISSING_FIELD: payload is not a JSON object"])

    # --- evidence_dictionary ---
    evidence: List[Any] = []
    if "evidence_dictionary" not in payload:
        errors.append("MISSING_FIELD: evidence_dictionary")
    else:
        raw_evidence = payload["evidence_dictionary"]
        if not isinstance(raw_evidence, list):
            errors.append("MISSING_FIELD: evidence_dictionary must be a list")
        else:
            evidence = raw_evidence
            errors.extend(_validate_evidence_dictionary(evidence, ledger_id_re))

    errors.extend(rule_errors(payload))
    errors.extend(quantile_rule_errors(payload))
    # Abstention is an explicit, evidence-bound decision, never an empty forecast.
    decision_status = payload.get("decision_status", "FORECAST")
    if decision_status not in ("FORECAST", "ABSTAIN"):
        errors.append("INVALID_FIELD: decision_status must be FORECAST or ABSTAIN")
    if decision_status == "ABSTAIN":
        if payload.get("dominant_evidence_track") != "INSUFFICIENT":
            errors.append("INVALID_FIELD: abstention requires INSUFFICIENT evidence track")
        abstention = payload.get("abstention")
        if not isinstance(abstention, dict):
            errors.append("MISSING_FIELD: abstention must be an object")
        else:
            for field in ("reason", "unsupported_claims", "missing_information", "reconsider_when"):
                value = abstention.get(field)
                if not isinstance(value, str) or not value.strip():
                    errors.append(f"MISSING_FIELD: abstention.{field}")
                elif detect_malformed_citations(value):
                    errors.append(f"MALFORMED_CITATION: abstention.{field}")
                else:
                    errors.extend(validate_citations(value, evidence))
            refs = abstention.get("evidence_refs")
            allowed = {e["ref_id"] for e in evidence if isinstance(e, dict) and isinstance(e.get("ref_id"), str)}
            if (not isinstance(refs, list) or not refs or
                    any(not isinstance(ref, str) or ref not in allowed for ref in refs)):
                errors.append("CITATION_UNRESOLVED: abstention.evidence_refs must name supplied evidence")
        if "predictions_t" in payload and payload["predictions_t"] != []:
            errors.append("INVALID_FIELD: abstention cannot contain predictions")
    elif "abstention" in payload:
        errors.append("INVALID_FIELD: forecast mode cannot carry an abstention")

    # --- epicentre_thesis ---
    if not payload.get("epicentre_thesis"):
        errors.append("MISSING_FIELD: epicentre_thesis")
    else:
        thesis = payload["epicentre_thesis"]
        if not isinstance(thesis, str):
            errors.append("MISSING_FIELD: epicentre_thesis must be a string")
        else:
            malformed = detect_malformed_citations(thesis)
            if malformed:
                for tok in malformed:
                    errors.append(f"MALFORMED_CITATION: {tok}")
            else:
                min_words = cfg.get("epicentre_thesis_min_words", 150)
                word_count = _count_words(thesis)
                if word_count < min_words:
                    errors.append(
                        f"BELOW_MIN_WORD_COUNT: epicentre_thesis has {word_count} words (min {min_words})"
                    )
                cite_errors = validate_citations(thesis, evidence)
                errors.extend(cite_errors)

    # --- bifurcation_resolutions (optional, validated when present) ---
    if "bifurcation_resolutions" in payload:
        resolutions = payload.get("bifurcation_resolutions")
        if not isinstance(resolutions, list):
            errors.append("INVALID_FIELD: bifurcation_resolutions must be a list when present")
        else:
            for i, item in enumerate(resolutions):
                if not isinstance(item, dict):
                    errors.append(f"INVALID_FIELD: bifurcation_resolutions[{i}] is not an object")
                    continue
                for fld in ("bifurcation_id", "selected_side", "rationale", "opposite_side_invalidation"):
                    if not isinstance(item.get(fld), str) or not item.get(fld).strip():
                        errors.append(f"MISSING_FIELD: bifurcation_resolutions[{i}].{fld}")

    if errors:
        return ValidationResult.failure(errors)
    return ValidationResult.success()


def validate_cp2(
    payload: Any,
    subject_run_dir: Optional[Path] = None,
    cross_corr_v2_targets: Optional[Set[str]] = None,
    expected_snapshot_time: Optional[str] = None,
    expected_target_time_iso: Optional[str] = None,
) -> ValidationResult:
    """
    [ACTION]
    - Validate a CP2 payload: runs validate_cp1 then adds predictions_t, forecast_rationale,
      grounding checks, and (if subject_run_dir provided) out-of-universe checks.
    - subject_run_dir: path to the Lab run directory whose T-n artifacts define the target_id universe.
      Pass None to skip out-of-universe checks (structure is still fully validated).
    - expected_snapshot_time / expected_target_time_iso: optional canonical runtime timestamps
      used to enforce deterministic temporal stamping.
    - Returns ValidationResult with sorted deduplicated error list.
    - Does not mutate payload.
    - When-needed: Open when a CP2 artifact needs the authoritative full validation pass, including CP1 inheritance, prediction structure, oracle-only guards, and optional universe/time checks.
    - Escalates-to: system/lib/citations.py; system/lib/artifacts.py; codex/contracts/contract_config.json
    - Navigation-group: kernel_lib
    """
    cp1_result = validate_cp1(payload)
    errors: List[str] = list(cp1_result.errors)
    cfg = _load_config()

    if not isinstance(payload, dict):
        return ValidationResult.failure(errors or ["MISSING_FIELD: payload is not a JSON object"])

    evidence: List[Any] = (
        payload.get("evidence_dictionary", [])
        if isinstance(payload.get("evidence_dictionary"), list)
        else []
    )

    # --- predictions_t ---
    predictions: List[Any] = []
    if "predictions_t" not in payload:
        errors.append("MISSING_FIELD: predictions_t")
    else:
        raw_preds = payload["predictions_t"]
        if payload.get("decision_status") == "ABSTAIN" and raw_preds == []:
            pass
        elif not isinstance(raw_preds, list) or len(raw_preds) == 0:
            errors.append("MISSING_FIELD: predictions_t must be a non-empty list")
        else:
            predictions = raw_preds
            for i, pred in enumerate(predictions):
                if not isinstance(pred, dict):
                    errors.append(f"MISSING_FIELD: predictions_t[{i}] is not an object")
                    continue
                snapshot_value: Optional[float] = None
                target_value: Optional[float] = None
                has_valid_snapshot_value = False
                has_valid_target_value = False
                if not isinstance(pred.get("unit"), str) or not pred["unit"].strip():
                    errors.append(f"MISSING_FIELD: predictions_t[{i}].unit")
                if not pred.get("target_id"):
                    errors.append(f"MISSING_FIELD: predictions_t[{i}].target_id")
                if "direction" not in pred:
                    errors.append(f"MISSING_FIELD: predictions_t[{i}].direction")
                elif pred["direction"] not in (_VALID_DIRECTIONS | ({'FLAT'} if payload.get('forecast_basis') == 'JUDGMENTAL' else set())):
                    errors.append(
                        f"INVALID_FIELD: predictions_t[{i}].direction={pred['direction']!r} "
                        f"(must be UP or DOWN)"
                    )
                # --- Deterministic baseline fields ---
                if "snapshot_value" not in pred:
                    errors.append(f"MISSING_SNAPSHOT_VALUE: predictions_t[{i}].snapshot_value")
                else:
                    try:
                        if isinstance(pred.get("snapshot_value"), bool):
                            raise ValueError("boolean observation")
                        snapshot_value = float(pred.get("snapshot_value"))
                        if not math.isfinite(snapshot_value):
                            raise ValueError("non-finite")
                        has_valid_snapshot_value = True
                    except Exception:
                        errors.append(
                            f"INVALID_FIELD: predictions_t[{i}].snapshot_value={pred.get('snapshot_value')!r} "
                            "(must be numeric)"
                        )
                if "target_value" not in pred:
                    errors.append(f"MISSING_TARGET_VALUE: predictions_t[{i}].target_value")
                else:
                    try:
                        if isinstance(pred.get("target_value"), bool):
                            raise ValueError("boolean observation")
                        target_value = float(pred.get("target_value"))
                        if not math.isfinite(target_value):
                            raise ValueError("non-finite")
                        has_valid_target_value = True
                    except Exception:
                        errors.append(
                            f"INVALID_FIELD: predictions_t[{i}].target_value={pred.get('target_value')!r} "
                            "(must be numeric)"
                        )
                if not pred.get("snapshot_time"):
                    errors.append(f"MISSING_FIELD: predictions_t[{i}].snapshot_time")
                if not pred.get("target_time_iso"):
                    errors.append(f"MISSING_FIELD: predictions_t[{i}].target_time_iso")
                if not pred.get("invalidation"):
                    errors.append(f"MISSING_FIELD: predictions_t[{i}].invalidation")

                direction = pred.get("direction")
                if has_valid_snapshot_value and has_valid_target_value:
                    if direction == "UP" and target_value <= snapshot_value:
                        errors.append(
                            f"INVALID_TARGET_DIRECTION: predictions_t[{i}] "
                            "UP prediction requires target_value > snapshot_value"
                        )
                    elif direction == "DOWN" and target_value >= snapshot_value:
                        errors.append(
                            f"INVALID_TARGET_DIRECTION: predictions_t[{i}] "
                            "DOWN prediction requires target_value < snapshot_value"
                        )
                    elif direction == "FLAT" and target_value != snapshot_value:
                        errors.append(f"INVALID_TARGET_DIRECTION: predictions_t[{i}] FLAT median must equal snapshot_value")

                snapshot_dt = _parse_iso_datetime(pred.get("snapshot_time"))
                target_dt = _parse_iso_datetime(pred.get("target_time_iso"))
                if pred.get("snapshot_time") and snapshot_dt is None:
                    errors.append(f"INVALID_FIELD: predictions_t[{i}].snapshot_time must be ISO datetime")
                if pred.get("target_time_iso") and target_dt is None:
                    errors.append(f"INVALID_FIELD: predictions_t[{i}].target_time_iso must be ISO datetime")
                if snapshot_dt is not None and target_dt is not None and target_dt <= snapshot_dt:
                    errors.append(
                        f"TEMPORAL_ORDER_INVALID: predictions_t[{i}] target_time_iso must be after snapshot_time"
                    )

                if expected_snapshot_time:
                    expected_snapshot_dt = _parse_iso_datetime(expected_snapshot_time)
                    if snapshot_dt is not None and expected_snapshot_dt is not None:
                        if snapshot_dt != expected_snapshot_dt:
                            errors.append(
                                f"TEMPORAL_MISMATCH: predictions_t[{i}].snapshot_time="
                                f"{pred.get('snapshot_time')!r} expected={expected_snapshot_time!r}"
                            )
                if expected_target_time_iso:
                    expected_target_dt = _parse_iso_datetime(expected_target_time_iso)
                    if target_dt is not None and expected_target_dt is not None:
                        if target_dt != expected_target_dt:
                            errors.append(
                                f"TEMPORAL_MISMATCH: predictions_t[{i}].target_time_iso="
                                f"{pred.get('target_time_iso')!r} expected={expected_target_time_iso!r}"
                            )

    # --- forecast_rationale ---
    if not payload.get("forecast_rationale"):
        errors.append("MISSING_FIELD: forecast_rationale")
    else:
        rationale = payload["forecast_rationale"]
        if not isinstance(rationale, str):
            errors.append("MISSING_FIELD: forecast_rationale must be a string")
        else:
            malformed = detect_malformed_citations(rationale)
            if malformed:
                for tok in malformed:
                    errors.append(f"MALFORMED_CITATION: {tok} in forecast_rationale")
            else:
                base = cfg.get("forecast_rationale_base_words", 75)
                per_pred = cfg.get("forecast_rationale_per_prediction_words", 30)
                min_words = base + per_pred * len(predictions)
                word_count = _count_words(rationale)
                if word_count < min_words:
                    errors.append(
                        f"BELOW_MIN_WORD_COUNT: forecast_rationale has {word_count} words (min {min_words})"
                    )
                cite_errors = validate_citations(rationale, evidence)
                errors.extend(cite_errors)

    # --- Grounding: every valid target_id needs an observation (S_/E_) evidence entry ---
    valid_predictions = [
        p for p in predictions if isinstance(p, dict) and p.get("target_id")
    ]
    for pred in valid_predictions:
        target = str(pred["target_id"]).upper().strip()
        grounding = [
            e for e in evidence
            if isinstance(e, dict)
            and str(e.get("subject", "")).upper().strip() == target
            and str(e.get("ledger_id", "")).startswith(("S_", "E_"))
        ]
        if not grounding:
            errors.append(
                f"GROUNDING_FAILED_WRONG_LANE: no observation ledger grounding for target_id={target}"
            )

    # --- Cross-corr structural grounding (orphan prevention) ---
    if cross_corr_v2_targets is not None and valid_predictions:
        for pred in valid_predictions:
            target = str(pred["target_id"]).upper().strip()
            if target not in cross_corr_v2_targets:
                errors.append(
                    f"UNGROUNDED_TARGET: target_id={target} not found in cross_corr_v2 "
                    f"TARGET_SWARM or SOLO_TARGET sets"
                )

    # --- Out-of-universe check (requires subject_run_dir) ---
    if valid_predictions and subject_run_dir is not None:
        target_id_set = _load_target_id_set(Path(subject_run_dir))
        if target_id_set is None:
            errors.append("MISSING_CONTEXT: could not load target_id universe from subject_run_dir")
        else:
            for pred in valid_predictions:
                target = str(pred["target_id"]).upper().strip()
                if target not in target_id_set:
                    errors.append(f"OUT_OF_UNIVERSE: target_id={target} not in T-n target_id set")

    if valid_predictions and subject_run_dir is not None:
        from system.lib.run_compare import combined_values
        source_values=combined_values(subject_run_dir)
        for pred in valid_predictions:
            row=source_values.get(str(pred["target_id"]).upper().strip(),{})
            if row.get("unit") and row["unit"] != pred.get("unit"):
                errors.append(f"UNIT_MISMATCH: target_id={pred['target_id']}")
    # --- Engine value-audit mismatches ---
    errors.extend(target_errors(payload, subject_run_dir, expected_snapshot_time,
                                expected_target_time_iso))
    errors.extend(quantile_target_errors(payload, subject_run_dir, expected_snapshot_time,
                                        expected_target_time_iso))
    audit_errors = payload.get("_engine_audit_errors")
    if isinstance(audit_errors, list):
        for raw in audit_errors:
            if isinstance(raw, str) and raw.startswith("SNAPSHOT_VALUE_MISMATCH"):
                errors.append(raw)

    if errors:
        return ValidationResult.failure(errors)
    return ValidationResult.success()
