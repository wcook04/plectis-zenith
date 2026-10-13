"""Frozen learned skill/context views over the existing node contracts.

Policies affect provider prompt views only. Canonical upstream artifacts remain
unchanged, and every excerpt or omission is represented explicitly and hashed.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import os
import tempfile
from typing import Any, Mapping


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def policy_sha256(policy: Mapping[str, Any]) -> str:
    payload = {key: value for key, value in policy.items() if key != "policy_sha256"}
    return hashlib.sha256(_canonical(payload).encode("utf-8")).hexdigest()


def investigation_policy(procedure: str, parent_sha256: str | None = None) -> dict:
    """Separate v1 replacement procedure contract; legacy addons stay <=512."""
    if not isinstance(procedure, str) or not 1 <= len(procedure) <= 4096 or not procedure.strip():
        raise ValueError("investigation procedure must contain 1..4096 characters")
    if parent_sha256 is not None and (not isinstance(parent_sha256, str) or len(parent_sha256) != 64):
        raise ValueError("invalid parent policy hash")
    result = {"schema":"zenith_investigation_policy_v1", "procedure":procedure,"parent_sha256":parent_sha256}
    result["policy_sha256"] = policy_sha256(result)
    return result


def validate_investigation_policy(policy: Mapping[str, Any]) -> dict:
    if not isinstance(policy, Mapping) or set(policy) != {"schema","procedure","parent_sha256","policy_sha256"}:
        raise ValueError("invalid investigation policy fields")
    expected = investigation_policy(policy["procedure"], policy["parent_sha256"])
    if dict(policy) != expected:
        raise ValueError("investigation policy hash/schema mismatch")
    return expected


def validate_reasoning_policy(policy: Mapping[str, Any], graph: Mapping[str, Any]) -> dict[str, Any]:
    """Reject undeclared fields, graph edges, invalid weights and hash drift."""
    if not isinstance(policy, Mapping):
        raise ValueError("reasoning_policy must be an object")
    if set(policy) != {"variant_id", "policy_sha256", "nodes"}:
        raise ValueError("reasoning_policy requires exactly variant_id, policy_sha256 and nodes")
    if not isinstance(policy["variant_id"], str) or not policy["variant_id"].strip():
        raise ValueError("reasoning_policy variant_id must be a nonempty string")
    if not isinstance(policy["nodes"], Mapping):
        raise ValueError("reasoning_policy nodes must be an object")
    for node_id, row in policy["nodes"].items():
        if node_id not in graph:
            raise ValueError(f"reasoning_policy unknown node: {node_id}")
        if not isinstance(row, Mapping) or set(row) - {"skill_addon", "incoming_weights", "max_context_chars"}:
            raise ValueError(f"reasoning_policy invalid fields for node {node_id}")
        if "skill_addon" in row and not isinstance(row["skill_addon"], str):
            raise ValueError(f"reasoning_policy skill_addon must be text for {node_id}")
        if len(row.get("skill_addon", "")) > 512:
            raise ValueError(f"reasoning_policy skill_addon must be <= 512 characters for {node_id}")
        if "max_context_chars" in row:
            budget = row["max_context_chars"]
            if isinstance(budget, bool) or not isinstance(budget, int) or budget < 256:
                raise ValueError(f"reasoning_policy max_context_chars must be an integer >= 256 for {node_id}")
        weights = row.get("incoming_weights", {})
        if not isinstance(weights, Mapping):
            raise ValueError(f"reasoning_policy incoming_weights must be an object for {node_id}")
        dependencies = set(graph[node_id].dependencies)
        for edge, weight in weights.items():
            if edge not in dependencies:
                raise ValueError(f"reasoning_policy unknown incoming edge {edge} for {node_id}")
            if isinstance(weight, bool) or not isinstance(weight, (int, float)):
                raise ValueError(f"reasoning_policy weight must be numeric for {node_id}/{edge}")
            try:
                valid = math.isfinite(weight) and weight >= 0
            except (OverflowError, TypeError):
                valid = False
            if not valid:
                raise ValueError(f"reasoning_policy weight must be finite and nonnegative for {node_id}/{edge}")
    if not isinstance(policy["policy_sha256"], str) or policy["policy_sha256"] != policy_sha256(policy):
        raise ValueError("reasoning_policy policy_sha256 mismatch")
    return deepcopy(dict(policy))


def apply_reasoning_policy(node: Any, inputs: Mapping[str, Any], policy: Mapping[str, Any]):
    """Return deterministic provider views, subordinate skill text, and receipt.

    The budget counts serialized source characters retained in prompt views.
    Receipt/envelope metadata and the skill addon are additional prompt content.
    Unspecified edge weights default to 1. Zero explicitly withholds an edge.
    """
    row = policy["nodes"].get(node.id)
    if row is None:
        return dict(inputs), "", None
    if set(inputs) - set(node.dependencies):
        raise ValueError(f"reasoning_policy undeclared input edges for {node.id}")
    weights = row.get("incoming_weights", {})
    ordered = sorted(inputs, key=lambda edge: (-weights.get(edge, 1), edge))
    encoded = {edge: json.dumps(inputs[edge], separators=(",", ":"), ensure_ascii=False, allow_nan=False) for edge in ordered}
    positive = [edge for edge in ordered if weights.get(edge, 1) > 0]
    total = sum(len(encoded[edge]) for edge in positive)
    budget = row.get("max_context_chars", total)
    allocation = {edge: 0 for edge in ordered}
    remaining = min(budget, total)
    active = list(positive)
    while active and remaining:
        largest_weight = max(weights.get(edge, 1) for edge in active)
        normalized = {edge: weights.get(edge, 1) / largest_weight for edge in active}
        denominator = sum(normalized.values())
        shares = {edge: remaining * normalized[edge] / denominator for edge in active}
        grants = {edge: min(len(encoded[edge]) - allocation[edge], int(shares[edge])) for edge in active}
        if not any(grants.values()):
            grants[active[0]] = 1
        used = sum(grants.values())
        for edge, grant in grants.items():
            allocation[edge] += grant
        remaining -= used
        active = [edge for edge in active if allocation[edge] < len(encoded[edge])]
    views: dict[str, Any] = {}
    edges: list[dict[str, Any]] = []
    for edge in ordered:
        text = encoded[edge]
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        kept = allocation[edge]
        state = "omitted" if weights.get(edge, 1) == 0 else ("full" if kept == len(text) else "excerpt")
        entry = {"dependency_id": edge, "weight": weights.get(edge, 1), "view": state,
                 "original_sha256": digest, "original_chars": len(text), "retained_source_chars": kept}
        edges.append(entry)
        if state == "full":
            views[edge] = inputs[edge]
        else:
            views[edge] = {"context_policy_view": state, "original_sha256": digest,
                           "original_chars": len(text), "retained_source_chars": kept,
                           "reason": "zero incoming weight" if state == "omitted" else "frozen weighted context budget"}
            if state == "excerpt":
                views[edge]["serialized_envelope_excerpt"] = text[:kept]
    receipt = {"schema_version": "zenith_context_policy_receipt_v1", "node_id": node.id,
               "variant_id": policy["variant_id"], "policy_sha256": policy["policy_sha256"],
               "max_context_chars": row.get("max_context_chars"),
               "budget_basis": "serialized source characters, excluding view/receipt metadata and skill addon",
               "retained_source_chars": sum(allocation.values()), "incoming_edges": edges,
               "missing_dependency_ids": sorted(set(node.dependencies) - set(inputs)),
               "omitted_dependency_ids": [edge["dependency_id"] for edge in edges if edge["view"] == "omitted"],
               "excerpt_dependency_ids": [edge["dependency_id"] for edge in edges if edge["view"] == "excerpt"],
               "skill_addon_sha256": hashlib.sha256(row.get("skill_addon", "").encode("utf-8")).hexdigest()}
    receipt["receipt_sha256"] = hashlib.sha256(_canonical(receipt).encode("utf-8")).hexdigest()
    return views, row.get("skill_addon", ""), receipt


def persist_context_receipt(artifacts_dir: Path, receipt: Mapping[str, Any]) -> Path:
    """Atomically publish a content-addressed receipt without replacing one."""
    folder = artifacts_dir / "context_policy"
    folder.mkdir(parents=True, exist_ok=True)
    destination = folder / f"{receipt['node_id']}.{receipt['receipt_sha256']}.json"
    content = _canonical(receipt) + "\n"
    fd, temporary = tempfile.mkstemp(prefix=".context-", dir=folder)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.link(temporary, destination)
        except FileExistsError:
            if destination.read_text(encoding="utf-8") != content:
                raise ValueError("context receipt identity collision or corrupt prior receipt")
    finally:
        os.unlink(temporary)
    return destination
