#!/usr/bin/env python3
"""Validate optional v2 reasoning-node overlays.

This is intentionally a lint, not a runtime gate. It scans node JSON files,
ignores nodes without ``meta.reasoning_contract``, and checks only the compact
contract invariants that make the overlay useful before full runtime migration.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Iterable, Mapping

from system.lib.strict_json import DuplicateJsonKeyError, StrictJsonError, loads_json_strict


REPO_ROOT = Path(__file__).resolve().parents[3]
STANDARD_PATH = REPO_ROOT / "codex" / "standards" / "std_node_reasoning.json"
NODES_DIR = REPO_ROOT / "codex" / "substrate" / "nodes"
SCHEMA_VERSION = "reasoning_contract_validator_v0"


def _load_json(path: Path) -> Any:
    return loads_json_strict(path.read_text(encoding="utf-8"), source=str(path))


def _load_node_json(path: Path) -> tuple[Any | None, list[dict[str, str]], bool]:
    text = path.read_text(encoding="utf-8")
    try:
        return loads_json_strict(text, source=str(path)), [], False
    except DuplicateJsonKeyError as exc:
        raw = json.loads(text)
        overlay_present = _has_reasoning_contract(raw) or '"reasoning_contract"' in text
        if not overlay_present:
            return raw, [], False
        return (
            raw,
            [_issue("json", "duplicate_json_key", str(exc))],
            True,
        )
    except StrictJsonError as exc:
        raise ValueError(str(exc)) from exc


def _as_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _string_set(value: Any) -> set[str]:
    return {item for item in _as_list(value) if isinstance(item, str)}


def _enum_values(value: Any) -> set[str]:
    """Extract ``a | b | c`` enum strings from the standard shape."""
    if not isinstance(value, str):
        return set()
    if "|" not in value:
        return set()
    return {part.strip() for part in value.split("|") if part.strip()}


def _has_reasoning_contract(value: Any) -> bool:
    if not isinstance(value, Mapping):
        return False
    meta = value.get("meta")
    return isinstance(meta, Mapping) and "reasoning_contract" in meta


def _standard_vocab(standard: Mapping[str, Any]) -> dict[str, set[str]]:
    shape = _as_mapping(_as_mapping(standard.get("meta_reasoning_contract")).get("shape"))
    role = _as_mapping(shape.get("role_contract"))
    injection = _as_mapping(shape.get("injection_contract"))
    topology = _as_mapping(shape.get("topology_contract"))
    learning = _as_mapping(shape.get("learning_contract"))
    trace = _as_mapping(shape.get("trace_contract"))
    return {
        "context_classes": _string_set(standard.get("context_class_vocabulary")),
        "role_class": _enum_values(role.get("role_class")),
        "context_mode": _enum_values(role.get("context_mode")),
        "leakage_mode": _enum_values(injection.get("leakage_mode")),
        "fan_out_reason": _enum_values(topology.get("fan_out_reason")),
        "shard_key": _enum_values(topology.get("shard_key")),
        "shard_isolation": _enum_values(topology.get("shard_isolation")),
        "fan_in_reducer": _enum_values(topology.get("fan_in_reducer")),
        "learning_ledger_rows": _enum_values(learning.get("learning_ledger_rows")),
        "mutation_gate": _enum_values(learning.get("mutation_gate")),
        "residual_routing": _enum_values(trace.get("residual_routing")),
    }


def _issue(path: str, code: str, message: str) -> dict[str, str]:
    return {"path": path, "code": code, "message": message}


def _check_enum(
    issues: list[dict[str, str]],
    field_path: str,
    value: Any,
    allowed: set[str],
) -> None:
    if value is None or not allowed:
        return
    if not isinstance(value, str):
        issues.append(_issue(field_path, "not_string", "Expected a string enum value."))
        return
    if value not in allowed:
        issues.append(
            _issue(
                field_path,
                "unknown_enum_value",
                f"Unknown value {value!r}; expected one of {sorted(allowed)}.",
            )
        )


def _check_context_list(
    issues: list[dict[str, str]],
    field_path: str,
    value: Any,
    allowed: set[str],
) -> None:
    if value is None:
        return
    if not isinstance(value, list):
        issues.append(_issue(field_path, "not_list", "Expected a list of context-class strings."))
        return
    for index, item in enumerate(value):
        item_path = f"{field_path}[{index}]"
        if not isinstance(item, str):
            issues.append(_issue(item_path, "not_string", "Expected a context-class string."))
        elif item not in allowed:
            issues.append(
                _issue(
                    item_path,
                    "unknown_context_class",
                    f"Unknown context class {item!r}; expected one of {sorted(allowed)}.",
                )
            )


def validate_contract(
    contract: Mapping[str, Any],
    *,
    vocab: Mapping[str, set[str]],
) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    role = _as_mapping(contract.get("role_contract"))
    inputs = _as_mapping(contract.get("input_contract"))
    injection = _as_mapping(contract.get("injection_contract"))
    output = _as_mapping(contract.get("output_contract"))
    oracle = _as_mapping(contract.get("oracle_contract"))
    topology = _as_mapping(contract.get("topology_contract"))
    learning = _as_mapping(contract.get("learning_contract"))
    side_effect = _as_mapping(contract.get("side_effect_contract"))
    trace = _as_mapping(contract.get("trace_contract"))

    if not role.get("role_class"):
        issues.append(_issue("role_contract.role_class", "missing_required_field", "Required."))
    if not role.get("context_mode"):
        issues.append(_issue("role_contract.context_mode", "missing_required_field", "Required."))
    if not output.get("artifact_kind") and not output.get("schema_or_standard"):
        issues.append(
            _issue(
                "output_contract",
                "missing_output_contract",
                "Provide artifact_kind or schema_or_standard.",
            )
        )
    if "read_only" not in side_effect:
        issues.append(
            _issue("side_effect_contract.read_only", "missing_required_field", "Required.")
        )
    elif not isinstance(side_effect.get("read_only"), bool):
        issues.append(
            _issue("side_effect_contract.read_only", "not_boolean", "Expected boolean.")
        )
    if not trace.get("residual_routing"):
        issues.append(_issue("trace_contract.residual_routing", "missing_required_field", "Required."))

    _check_enum(issues, "role_contract.role_class", role.get("role_class"), vocab["role_class"])
    _check_enum(
        issues,
        "role_contract.context_mode",
        role.get("context_mode"),
        vocab["context_mode"],
    )
    _check_enum(
        issues,
        "injection_contract.leakage_mode",
        injection.get("leakage_mode"),
        vocab["leakage_mode"],
    )
    _check_enum(
        issues,
        "topology_contract.fan_out_reason",
        topology.get("fan_out_reason"),
        vocab["fan_out_reason"],
    )
    _check_enum(
        issues,
        "topology_contract.shard_key",
        topology.get("shard_key"),
        vocab["shard_key"],
    )
    _check_enum(
        issues,
        "topology_contract.shard_isolation",
        topology.get("shard_isolation"),
        vocab["shard_isolation"],
    )
    _check_enum(
        issues,
        "topology_contract.fan_in_reducer",
        topology.get("fan_in_reducer"),
        vocab["fan_in_reducer"],
    )
    _check_enum(
        issues,
        "learning_contract.learning_ledger_rows",
        learning.get("learning_ledger_rows"),
        vocab["learning_ledger_rows"],
    )
    _check_enum(
        issues,
        "learning_contract.mutation_gate",
        learning.get("mutation_gate"),
        vocab["mutation_gate"],
    )
    _check_enum(
        issues,
        "trace_contract.residual_routing",
        trace.get("residual_routing"),
        vocab["residual_routing"],
    )

    for key in ("inject", "reference_only", "withhold", "redact", "forbidden"):
        _check_context_list(
            issues,
            f"injection_contract.{key}",
            injection.get(key),
            vocab["context_classes"],
        )

    input_forbidden = _as_list(inputs.get("forbidden_artifacts"))
    injection_forbidden = _as_list(injection.get("forbidden"))
    if input_forbidden or injection_forbidden:
        blocked_conditions = _as_list(oracle.get("blocked_conditions"))
        failure_shape = output.get("failure_shape")
        if not blocked_conditions and not failure_shape:
            issues.append(
                _issue(
                    "output_contract.failure_shape",
                    "missing_blocked_behavior",
                    "Declare failure_shape or oracle_contract.blocked_conditions when forbidden inputs exist.",
                )
            )

    fan_out_reason = topology.get("fan_out_reason", "none")
    if fan_out_reason != "none":
        if topology.get("shard_key", "none") == "none":
            issues.append(
                _issue(
                    "topology_contract.shard_key",
                    "missing_shard_key",
                    "Non-none fan_out_reason requires a non-none shard_key.",
                )
            )
        if topology.get("fan_in_reducer", "none") == "none":
            issues.append(
                _issue(
                    "topology_contract.fan_in_reducer",
                    "missing_fan_in_reducer",
                    "Non-none fan_out_reason requires a non-none fan_in_reducer.",
                )
            )

    if learning.get("learning_ledger_rows") == "append_after_oracle_gate":
        if not _as_list(oracle.get("blocked_conditions")):
            issues.append(
                _issue(
                    "oracle_contract.blocked_conditions",
                    "missing_oracle_blockers",
                    "append_after_oracle_gate requires oracle blocked_conditions.",
                )
            )
        if not _as_list(learning.get("no_learning_when")):
            issues.append(
                _issue(
                    "learning_contract.no_learning_when",
                    "missing_no_learning_when",
                    "append_after_oracle_gate requires no_learning_when.",
                )
            )
        if learning.get("mutation_gate") in (None, "", "none"):
            issues.append(
                _issue(
                    "learning_contract.mutation_gate",
                    "missing_mutation_gate",
                    "append_after_oracle_gate requires a non-none mutation_gate.",
                )
            )

    if side_effect.get("commit_allowed") is True:
        if learning.get("mutation_gate") not in {"version_committer_required", "human_required"}:
            issues.append(
                _issue(
                    "learning_contract.mutation_gate",
                    "unsafe_commit_gate",
                    "commit_allowed=true requires version_committer_required or human_required.",
                )
            )

    return issues


def _node_paths(root: Path) -> list[Path]:
    nodes_dir = root / "codex" / "substrate" / "nodes"
    if not nodes_dir.exists():
        return []
    return sorted(nodes_dir.rglob("*.json"), key=lambda path: str(path))


def _display_path(path: Path, root: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return str(path)


def build_report(
    repo_root: Path = REPO_ROOT,
    *,
    node_paths: Iterable[Path] | None = None,
    standard_path: Path | None = None,
) -> dict[str, Any]:
    repo_root = Path(repo_root)
    standard = _as_mapping(_load_json(standard_path or repo_root / STANDARD_PATH.relative_to(REPO_ROOT)))
    vocab = _standard_vocab(standard)
    paths = list(node_paths) if node_paths is not None else _node_paths(repo_root)
    rows: list[dict[str, Any]] = []
    malformed: list[dict[str, str]] = []

    for path in paths:
        path = Path(path)
        display = _display_path(path, repo_root)
        try:
            raw, json_issues, overlay_forced = _load_node_json(path)
        except Exception as exc:
            malformed.append(
                {"path": display, "code": "malformed_json", "message": str(exc)}
            )
            continue
        if not isinstance(raw, Mapping):
            continue
        node_id = raw.get("id") if isinstance(raw.get("id"), str) else display
        meta = raw.get("meta")
        if not isinstance(meta, Mapping):
            if overlay_forced:
                rows.append(
                    {
                        "node_id": node_id,
                        "path": display,
                        "has_reasoning_contract": True,
                        "issues": json_issues,
                    }
                )
            continue
        contract = meta.get("reasoning_contract")
        if contract is None:
            if overlay_forced:
                rows.append(
                    {
                        "node_id": node_id,
                        "path": display,
                        "has_reasoning_contract": True,
                        "issues": json_issues,
                    }
                )
            continue
        if not isinstance(contract, Mapping):
            rows.append(
                {
                    "node_id": node_id,
                    "path": display,
                    "has_reasoning_contract": True,
                    "issues": [
                        *json_issues,
                        _issue("meta.reasoning_contract", "not_object", "Expected object.")
                    ],
                }
            )
            continue
        issues = validate_contract(contract, vocab=vocab)
        issues = [*json_issues, *issues]
        rows.append(
            {
                "node_id": node_id,
                "path": display,
                "has_reasoning_contract": True,
                "role_class": _as_mapping(contract.get("role_contract")).get("role_class"),
                "context_mode": _as_mapping(contract.get("role_contract")).get("context_mode"),
                "artifact_kind": _as_mapping(contract.get("output_contract")).get("artifact_kind"),
                "issues": issues,
            }
        )

    issue_count = sum(len(row["issues"]) for row in rows) + len(malformed)
    return {
        "schema_version": SCHEMA_VERSION,
        "ok": issue_count == 0,
        "standard_path": _display_path(standard_path or repo_root / STANDARD_PATH.relative_to(REPO_ROOT), repo_root),
        "summary": {
            "node_file_count": len(paths),
            "overlay_count": len(rows),
            "issue_count": issue_count,
            "malformed_json_count": len(malformed),
        },
        "malformed_json": malformed,
        "rows": rows,
    }


def _render_text(report: Mapping[str, Any]) -> str:
    summary = _as_mapping(report.get("summary"))
    lines = [
        "reasoning contract validation",
        f"ok: {report.get('ok')}",
        f"node_file_count: {summary.get('node_file_count')}",
        f"overlay_count: {summary.get('overlay_count')}",
        f"issue_count: {summary.get('issue_count')}",
    ]
    for row in _as_list(report.get("rows")):
        issues = _as_list(_as_mapping(row).get("issues"))
        if not issues:
            continue
        lines.append(f"- {row.get('node_id')} ({row.get('path')}):")
        for issue in issues:
            lines.append(f"  - {issue.get('path')}: {issue.get('code')} - {issue.get('message')}")
    for issue in _as_list(report.get("malformed_json")):
        lines.append(f"- {issue.get('path')}: {issue.get('code')} - {issue.get('message')}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate meta.reasoning_contract overlays.")
    parser.add_argument("--json", action="store_true", help="Emit JSON report.")
    parser.add_argument("--check", action="store_true", help="Exit non-zero when overlays are invalid.")
    args = parser.parse_args(argv)

    report = build_report(REPO_ROOT)
    if args.json or args.check:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(_render_text(report))
    return 0 if (not args.check or report["ok"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
