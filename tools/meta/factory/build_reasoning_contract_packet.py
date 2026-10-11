#!/usr/bin/env python3
"""Build a dry-run packet manifest from a node reasoning contract."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from jsonschema import Draft202012Validator

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from system.lib.strict_json import StrictJsonError, loads_json_strict  # noqa: E402

import validate_reasoning_contracts as contract_validator  # noqa: E402


SCHEMA_VERSION = "reasoning_contract_packet_manifest_v0"
NODES_DIR = REPO_ROOT / "codex" / "substrate" / "nodes"
STANDARD_PATH = REPO_ROOT / "codex" / "standards" / "std_node_reasoning.json"
MANIFEST_SCHEMA_PATH = (
    REPO_ROOT / "codex" / "substrate" / "contracts" / "schema_reasoning_contract_packet_manifest.json"
)
TERMINAL_ERROR_STATUSES = {"not_found", "invalid_json", "no_reasoning_contract", "invalid_contract"}


def _as_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _as_str_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _display_path(path: Path, root: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return str(path)


def _manifest_source_refs(repo_root: Path, *paths: str | Path | None) -> list[str]:
    refs: list[str] = []
    for raw_path in paths:
        if raw_path is None:
            continue
        path = raw_path if isinstance(raw_path, str) else _display_path(Path(raw_path), repo_root)
        if path and path not in refs:
            refs.append(path)
    for path in (
        _display_path(STANDARD_PATH, repo_root),
        _display_path(MANIFEST_SCHEMA_PATH, repo_root),
    ):
        if path not in refs:
            refs.append(path)
    return refs


def _dry_run_evaluation(
    *,
    available_context: Sequence[str] = (),
    available_artifacts: Sequence[str] = (),
) -> dict[str, Any]:
    return {
        "available_context": [item for item in available_context if isinstance(item, str)],
        "available_artifacts": [item for item in available_artifacts if isinstance(item, str)],
        "model_dispatch": False,
        "provider_dispatch": False,
        "runtime_execution": False,
        "writes": False,
    }


def _json_path(error_path: Iterable[Any]) -> str:
    parts = list(error_path)
    if not parts:
        return "$"
    rendered = "$"
    for part in parts:
        if isinstance(part, int):
            rendered += f"[{part}]"
        else:
            rendered += f".{part}"
    return rendered


def validate_manifest(
    manifest: Mapping[str, Any],
    repo_root: Path = REPO_ROOT,
) -> list[dict[str, str]]:
    """Validate a packet manifest against the durable JSON Schema contract."""
    repo_root = Path(repo_root)
    schema_path = repo_root / MANIFEST_SCHEMA_PATH.relative_to(REPO_ROOT)
    schema = loads_json_strict(schema_path.read_text(encoding="utf-8"), source=_display_path(schema_path, repo_root))
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    errors = sorted(
        validator.iter_errors(manifest),
        key=lambda error: (list(error.path), list(error.schema_path), error.message),
    )
    return [
        {
            "path": _json_path(error.path),
            "code": "schema_validation_error",
            "message": error.message,
        }
        for error in errors
    ]


def _node_paths(root: Path) -> list[Path]:
    nodes_dir = root / NODES_DIR.relative_to(REPO_ROOT)
    if not nodes_dir.exists():
        return []
    return sorted(nodes_dir.rglob("*.json"), key=lambda path: str(path))


def _find_node_path(
    repo_root: Path,
    node_id: str,
    *,
    node_paths: Iterable[Path] | None = None,
) -> Path | None:
    paths = list(node_paths) if node_paths is not None else _node_paths(repo_root)
    for path in paths:
        try:
            raw = json.loads(Path(path).read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(raw, Mapping) and raw.get("id") == node_id:
            return Path(path)
    return None


def _load_selected_node(path: Path, repo_root: Path) -> tuple[Mapping[str, Any] | None, dict[str, Any] | None]:
    display = _display_path(path, repo_root)
    try:
        raw = loads_json_strict(path.read_text(encoding="utf-8"), source=display)
    except StrictJsonError as exc:
        return None, {
            "schema_version": SCHEMA_VERSION,
            "node_id": None,
            "node_path": display,
            "dry_run": True,
            "status": "invalid_json",
            "issues": [{"path": "json", "code": "strict_json_error", "message": str(exc)}],
        }
    if not isinstance(raw, Mapping):
        return None, {
            "schema_version": SCHEMA_VERSION,
            "node_id": None,
            "node_path": display,
            "dry_run": True,
            "status": "invalid_json",
            "issues": [{"path": "json", "code": "not_object", "message": "Node JSON must be an object."}],
        }
    return raw, None


def _validation_issues(repo_root: Path, node_path: Path) -> list[dict[str, str]]:
    report = contract_validator.build_report(repo_root, node_paths=[node_path])
    if report.get("malformed_json"):
        return [
            {
                "path": str(row.get("path") or "json"),
                "code": str(row.get("code") or "malformed_json"),
                "message": str(row.get("message") or "Malformed JSON."),
            }
            for row in report["malformed_json"]
        ]
    rows = [row for row in report.get("rows", []) if isinstance(row, Mapping)]
    if not rows:
        return []
    return [dict(issue) for issue in rows[0].get("issues", []) if isinstance(issue, Mapping)]


def _blocked_by(
    *,
    available_context: Sequence[str],
    available_artifacts: Sequence[str],
    injection: Mapping[str, Any],
    inputs: Mapping[str, Any],
) -> list[dict[str, str]]:
    blocked: list[dict[str, str]] = []
    forbidden_context = set(_as_str_list(injection.get("forbidden")))
    forbidden_artifacts = set(_as_str_list(inputs.get("forbidden_artifacts")))
    for context_class in available_context:
        if context_class in forbidden_context:
            blocked.append(
                {
                    "kind": "context_class",
                    "class": context_class,
                    "source_field": "injection_contract.forbidden",
                    "reason": "forbidden by injection_contract.forbidden",
                }
            )
    for artifact in available_artifacts:
        if artifact in forbidden_artifacts:
            blocked.append(
                {
                    "kind": "artifact",
                    "artifact": artifact,
                    "source_field": "input_contract.forbidden_artifacts",
                    "reason": "forbidden by input_contract.forbidden_artifacts",
                }
            )
    return blocked


def build_manifest(
    repo_root: Path = REPO_ROOT,
    *,
    node_id: str,
    available_context: Sequence[str] = (),
    available_artifacts: Sequence[str] = (),
    node_paths: Iterable[Path] | None = None,
) -> dict[str, Any]:
    repo_root = Path(repo_root)
    available_context_list = [item for item in available_context if isinstance(item, str)]
    available_artifact_list = [item for item in available_artifacts if isinstance(item, str)]
    evaluation = _dry_run_evaluation(
        available_context=available_context_list,
        available_artifacts=available_artifact_list,
    )
    node_path = _find_node_path(repo_root, node_id, node_paths=node_paths)
    if node_path is None:
        return {
            "schema_version": SCHEMA_VERSION,
            "node_id": node_id,
            "node_path": None,
            "source_refs": _manifest_source_refs(repo_root),
            "evaluation": evaluation,
            "dry_run": True,
            "status": "not_found",
            "issues": [
                {
                    "path": "node_id",
                    "code": "node_not_found",
                    "message": f"No node with id {node_id!r} was found.",
                }
            ],
        }

    raw, error_manifest = _load_selected_node(node_path, repo_root)
    if error_manifest is not None:
        error_manifest["node_id"] = node_id
        error_manifest["source_refs"] = _manifest_source_refs(repo_root, _display_path(node_path, repo_root))
        error_manifest["evaluation"] = evaluation
        return error_manifest

    display = _display_path(node_path, repo_root)
    meta = _as_mapping(raw.get("meta"))
    contract = meta.get("reasoning_contract")
    if not isinstance(contract, Mapping):
        return {
            "schema_version": SCHEMA_VERSION,
            "node_id": node_id,
            "node_path": display,
            "source_refs": _manifest_source_refs(repo_root, display),
            "evaluation": evaluation,
            "dry_run": True,
            "status": "no_reasoning_contract",
            "issues": [
                {
                    "path": "meta.reasoning_contract",
                    "code": "missing_reasoning_contract",
                    "message": "Node does not carry meta.reasoning_contract.",
                }
            ],
        }

    validation_issues = _validation_issues(repo_root, node_path)
    if validation_issues:
        return {
            "schema_version": SCHEMA_VERSION,
            "node_id": node_id,
            "node_path": display,
            "source_refs": _manifest_source_refs(repo_root, display),
            "evaluation": evaluation,
            "dry_run": True,
            "status": "invalid_contract",
            "issues": validation_issues,
        }

    role = _as_mapping(contract.get("role_contract"))
    inputs = _as_mapping(contract.get("input_contract"))
    injection = _as_mapping(contract.get("injection_contract"))
    output = _as_mapping(contract.get("output_contract"))
    oracle = _as_mapping(contract.get("oracle_contract"))
    learning = _as_mapping(contract.get("learning_contract"))
    side_effect = _as_mapping(contract.get("side_effect_contract"))
    trace = _as_mapping(contract.get("trace_contract"))

    required_artifacts = _as_str_list(inputs.get("required_artifacts"))
    required_present = [item for item in required_artifacts if item in set(available_artifact_list)]
    required_missing = [item for item in required_artifacts if item not in set(available_artifact_list)]
    blocked = _blocked_by(
        available_context=available_context_list,
        available_artifacts=available_artifact_list,
        injection=injection,
        inputs=inputs,
    )
    artifact_mode = "evaluated" if available_artifact_list else "not_evaluated"
    status = "blocked" if blocked else "ready"
    if status == "ready" and artifact_mode == "evaluated" and required_missing:
        status = "incomplete"

    return {
        "schema_version": SCHEMA_VERSION,
        "node_id": node_id,
        "node_path": display,
        "source_refs": _manifest_source_refs(repo_root, display),
        "role": {
            "role_class": role.get("role_class"),
            "mission_role": role.get("mission_role"),
            "authority_tier": role.get("authority_tier"),
            "context_mode": role.get("context_mode"),
        },
        "context_policy": {
            "inject": _as_str_list(injection.get("inject")),
            "reference_only": _as_str_list(injection.get("reference_only")),
            "withhold": _as_str_list(injection.get("withhold")),
            "redact": _as_str_list(injection.get("redact")),
            "forbidden": _as_str_list(injection.get("forbidden")),
            "max_context_tokens": injection.get("max_context_tokens"),
            "leakage_mode": injection.get("leakage_mode"),
        },
        "artifact_policy": {
            "required_artifacts": required_artifacts,
            "optional_artifacts": _as_str_list(inputs.get("optional_artifacts")),
            "forbidden_artifacts": _as_str_list(inputs.get("forbidden_artifacts")),
            "available_artifacts": available_artifact_list,
            "required_present": required_present,
            "required_missing": required_missing if artifact_mode == "evaluated" else [],
            "artifact_presence_mode": artifact_mode,
            "output_artifact_kind": output.get("artifact_kind"),
            "schema_or_standard": output.get("schema_or_standard"),
            "citation_requirements": _as_str_list(output.get("citation_requirements")),
            "confidence_shape": output.get("confidence_shape"),
            "failure_shape": output.get("failure_shape"),
        },
        "blocked_conditions": _as_str_list(oracle.get("blocked_conditions")),
        "blocked_if_present": {
            "context_classes": _as_str_list(injection.get("forbidden")),
            "artifacts": _as_str_list(inputs.get("forbidden_artifacts")),
        },
        "blocked_by": blocked,
        "freshness_requirements": _as_str_list(inputs.get("freshness_requirements")),
        "authority_requirements": _as_str_list(inputs.get("authority_requirements")),
        "oracle_policy": {
            "deterministic_check": _as_str_list(oracle.get("deterministic_check")),
            "soft_review": _as_str_list(oracle.get("soft_review")),
            "human_review_gate": _as_str_list(oracle.get("human_review_gate")),
        },
        "learning_policy": {
            "dossier_reads": _as_str_list(learning.get("dossier_reads")),
            "dossier_writes": _as_str_list(learning.get("dossier_writes")),
            "learning_ledger_rows": learning.get("learning_ledger_rows"),
            "mutation_gate": learning.get("mutation_gate"),
            "no_learning_when": _as_str_list(learning.get("no_learning_when")),
        },
        "side_effect_policy": {
            "read_only": side_effect.get("read_only"),
            "writes_allowed": _as_str_list(side_effect.get("writes_allowed")),
            "commit_allowed": side_effect.get("commit_allowed"),
            "external_action_allowed": side_effect.get("external_action_allowed"),
        },
        "trace_policy": {
            "retained_fields": _as_str_list(trace.get("retained_fields")),
            "fact_extraction_fields": _as_str_list(trace.get("fact_extraction_fields")),
            "residual_routing": trace.get("residual_routing"),
        },
        "evaluation": evaluation,
        "dry_run": True,
        "status": status,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build a dry-run manifest from a node's meta.reasoning_contract overlay."
    )
    parser.add_argument("--node-id", required=True, help="Node id to inspect.")
    parser.add_argument("--repo-root", default=str(REPO_ROOT), help="Repository root.")
    parser.add_argument(
        "--available-context",
        action="append",
        default=[],
        help="Context class present in a simulated launch packet. Repeatable.",
    )
    parser.add_argument(
        "--available-artifact",
        action="append",
        default=[],
        help="Artifact id present in a simulated launch packet. Repeatable.",
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON. Currently always true.")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Validate the generated manifest against its schema and emit a compact check report.",
    )
    args = parser.parse_args(argv)

    manifest = build_manifest(
        Path(args.repo_root),
        node_id=args.node_id,
        available_context=args.available_context,
        available_artifacts=args.available_artifact,
    )
    schema_issues = validate_manifest(manifest, Path(args.repo_root))
    if args.check:
        print(
            json.dumps(
                {
                    "ok": not schema_issues,
                    "schema_version": "reasoning_contract_packet_manifest_check_v0",
                    "manifest_schema": _display_path(
                        Path(args.repo_root)
                        / MANIFEST_SCHEMA_PATH.relative_to(REPO_ROOT),
                        Path(args.repo_root),
                    ),
                    "node_id": args.node_id,
                    "manifest_status": manifest.get("status"),
                    "issues": schema_issues,
                },
                indent=2,
                sort_keys=False,
            )
        )
        return 0 if not schema_issues else 2
    if schema_issues:
        print(
            json.dumps(
                {
                    "ok": False,
                    "schema_version": "reasoning_contract_packet_manifest_check_v0",
                    "manifest_schema": _display_path(
                        Path(args.repo_root)
                        / MANIFEST_SCHEMA_PATH.relative_to(REPO_ROOT),
                        Path(args.repo_root),
                    ),
                    "node_id": args.node_id,
                    "manifest_status": manifest.get("status"),
                    "issues": schema_issues,
                },
                indent=2,
                sort_keys=False,
            )
        )
        return 2
    print(json.dumps(manifest, indent=2, sort_keys=False))
    return 1 if manifest.get("status") in TERMINAL_ERROR_STATUSES else 0


if __name__ == "__main__":
    raise SystemExit(main())
