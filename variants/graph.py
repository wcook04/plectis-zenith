"""Validate and execute frozen topology overlays without editing source nodes."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, replace
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Mapping

from system.core.governance import compile_standard, compute_waves, parse_node, validate_graph
from system.core.engine import _OUTPUT_SCHEMA_CONTRACTS
from system.lib.hashing import hash_node
from system.lib.types import CodexNode, NodeType, DEFAULT_EXECUTION_CONFIG
from system.lib.utils import to_jsonable
from tools.meta.factory.validate_reasoning_contracts import _standard_vocab, validate_contract

SCHEMA_VERSION = "zenith_graph_variant_v1"
ROOT_FIELDS = {"schema_version", "variant_id", "base_graph_sha256", "base_node_hashes", "operations", "variant_sha256"}
NODE_FIELDS = {"id", "type", "group", "lane", "expectation", "is_artifact", "dependencies", "instruction", "platform", "config", "execution", "teleology", "mechanism", "output_schema", "boundary", "routing_class", "meta"}
NODE_ID = re.compile(r"^[a-z][a-z0-9_]{0,95}$")
DEFAULT_ROOT = Path(__file__).resolve().parents[1]


def _digest(value: Any) -> str:
    text = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def build_base_identity(graph: Mapping[str, CodexNode]) -> dict[str, Any]:
    return {"base_node_hashes": {node_id: hash_node(node) for node_id, node in sorted(graph.items())},
            "base_graph_sha256": _digest({node_id: to_jsonable(asdict(node)) for node_id, node in sorted(graph.items())})}


def variant_sha256(payload: Mapping[str, Any]) -> str:
    return _digest({key: value for key, value in payload.items() if key != "variant_sha256"})


def _strict_overlay(value: Any, shape: Any, path: str = "meta.reasoning_contract") -> None:
    if isinstance(shape, dict):
        if not isinstance(value, Mapping) or set(value) - set(shape):
            raise ValueError(f"Invalid or unknown contract fields at {path}")
        for key, child in value.items():
            _strict_overlay(child, shape[key], f"{path}.{key}")
    elif isinstance(shape, list):
        if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
            raise ValueError(f"Expected a string list at {path}")
    elif str(shape).startswith("boolean"):
        if not isinstance(value, bool):
            raise ValueError(f"Expected boolean at {path}")
    elif path.endswith("max_context_tokens"):
        if value is not None and (isinstance(value, bool) or not isinstance(value, int) or value <= 0):
            raise ValueError(f"Expected positive token limit or null at {path}")
    elif not isinstance(value, str):
        raise ValueError(f"Expected text at {path}")


def _new_reasoning_node(raw: Any, root: Path, groups: set[str]) -> CodexNode:
    if not isinstance(raw, Mapping) or set(raw) - NODE_FIELDS:
        raise ValueError("New reasoning node has unknown fields")
    node = deepcopy(dict(raw))
    for field in NODE_FIELDS - {"dependencies", "is_artifact", "config", "execution", "meta"}:
        if field in node and not isinstance(node[field], str):
            raise ValueError(f"Reasoning node field must be text: {field}")
    if not isinstance(node.get("is_artifact"), bool):
        raise ValueError("Reasoning is_artifact must be boolean")
    if node.get("type") != "reasoning" or not NODE_ID.fullmatch(str(node.get("id", ""))):
        raise ValueError("Only safely named reasoning nodes may be added")
    if node.get("group") not in groups - {"feeds"}:
        raise ValueError("New reasoning nodes require an existing non-feed mission group")
    if not isinstance(node.get("dependencies"), list) or any(not isinstance(dep, str) for dep in node["dependencies"]):
        raise ValueError("New reasoning dependencies must be a string list")
    if len(node["dependencies"]) != len(set(node["dependencies"])):
        raise ValueError("Duplicate reasoning dependencies")
    if not isinstance(node.get("instruction"), str) or not node["instruction"].strip() or len(node["instruction"]) > 2048:
        raise ValueError("New reasoning instruction must contain 1..2048 characters")
    if node.get("config", {}) != {}:
        raise ValueError("New reasoning nodes cannot configure dynamic tools or provider calls")
    execution = node.get("execution", {})
    if not isinstance(execution, Mapping) or set(execution) - set(DEFAULT_EXECUTION_CONFIG) or execution.get("tools", []) != []:
        raise ValueError("New reasoning execution cannot declare tools or unknown fields")
    for field in ("timeout", "retries"):
        if field in execution and (isinstance(execution[field], bool) or not isinstance(execution[field], int) or execution[field] <= 0):
            raise ValueError(f"Experimental execution {field} must be a positive integer")
    if execution.get("cache_policy", "standard") not in {"standard", "none"}:
        raise ValueError("Unknown experimental cache policy")
    meta = node.get("meta", {})
    if not isinstance(meta, Mapping) or set(meta) != {"reasoning_contract"}:
        raise ValueError("New reasoning nodes require only the canonical reasoning_contract overlay")
    standard = json.loads((root / "codex/standards/std_node_reasoning.json").read_text())
    law = compile_standard(standard)
    if law is None:
        raise ValueError("Canonical reasoning node standard unavailable")
    if law.required_keys - set(node):
        raise ValueError(f"Missing canonical reasoning node fields: {sorted(law.required_keys - set(node))}")
    for key, values in law.enum_constraints.items():
        if key in node and str(node[key]) not in values:
            raise ValueError(f"Invalid canonical reasoning node enum: {key}")
    contract = meta["reasoning_contract"]
    _strict_overlay(contract, standard["meta_reasoning_contract"]["shape"])
    issues = validate_contract(contract, vocab=_standard_vocab(standard))
    if issues:
        raise ValueError("Invalid reasoning contract: " + json.dumps(issues, sort_keys=True))
    inputs = contract.get("input_contract", {})
    required = inputs.get("required_artifacts", [])
    optional = inputs.get("optional_artifacts", [])
    if set(required) - set(node["dependencies"]) or set(optional) - set(node["dependencies"]):
        raise ValueError("Declared reasoning input artifacts must be graph dependencies")
    if set(required) & set(optional) or set(node["dependencies"]) - set(required) - set(optional):
        raise ValueError("Each incoming dependency must have one declared input contract")
    effects = contract.get("side_effect_contract", {})
    if effects.get("read_only") is not True or effects.get("commit_allowed", False) or effects.get("external_action_allowed", False) or effects.get("writes_allowed", []):
        raise ValueError("Experimental reasoning skills must be read-only")
    if node["group"] in {"lab", "surveillance"}:
        if contract["role_contract"]["context_mode"] != "forward_subject_only" or "truth_side_evidence" not in contract.get("injection_contract", {}).get("forbidden", []):
            raise ValueError("Forward skills must explicitly forbid truth-side evidence")
    output_schema = node.get("output_schema", "text")
    declaration = contract["output_contract"].get("schema_or_standard")
    expected = _OUTPUT_SCHEMA_CONTRACTS.get(output_schema)
    if expected is not None:
        if declaration not in {f"codex/contracts/{expected}", f"codex/substrate/contracts/{expected}"}:
            raise ValueError("Output contract must match the engine's existing schema validator")
        if not (root / declaration).is_file():
            raise ValueError("Declared output contract is missing")
    elif output_schema not in {"text", "json"} or declaration != output_schema:
        raise ValueError("Unknown or unvalidated experimental output contract")
    # Use the same tag/contract/dossier hydration transformations as the source loader.
    from system.core.loader import PhysicalLoader
    loader = PhysicalLoader(root, inject_sys_path=False)
    for reference in re.findall(r"See Contract:\s*(codex/[A-Za-z0-9_./-]+\.(?:json|md))", node["instruction"]):
        destination = (root / reference).resolve()
        if not destination.is_relative_to(root.resolve()) or not destination.is_file():
            raise ValueError("Experimental instruction references a missing or escaping contract")
    node["instruction"] = loader._inject_tags(node["instruction"], Path("variants") / node["id"])
    node["instruction"] = loader._resolve_contracts(node["instruction"])
    node["instruction"] = loader._resolve_map_injections(node["id"], node["instruction"])
    loader._inject_compiled_dossiers(node)
    return parse_node(node)


def _ancestors(graph: Mapping[str, CodexNode], node_id: str) -> set[str]:
    result: set[str] = set()
    pending = list(graph[node_id].dependencies)
    while pending:
        dependency = pending.pop()
        if dependency not in result:
            result.add(dependency)
            pending.extend(graph[dependency].dependencies)
    return result


def _truth_tainted(node: CodexNode) -> bool:
    role = node.meta.get("reasoning_contract", {}).get("role_contract", {})
    return node.group in {"oracle", "refinement"} or role.get("context_mode") == "hindsight_truth_allowed"


def apply_graph_variant(base_graph: Mapping[str, CodexNode], payload: Mapping[str, Any], *, root: Path = DEFAULT_ROOT):
    """Apply typed overlay operations, prove graph shape, and return its receipt."""
    if not isinstance(payload, Mapping) or set(payload) != ROOT_FIELDS:
        raise ValueError("Graph variant requires exactly its declared root fields")
    if payload["schema_version"] != SCHEMA_VERSION or not isinstance(payload["variant_id"], str) or not NODE_ID.fullmatch(payload["variant_id"]):
        raise ValueError("Unknown graph variant schema or unsafe variant id")
    if payload["variant_sha256"] != variant_sha256(payload):
        raise ValueError("Graph variant hash mismatch")
    identity = build_base_identity(base_graph)
    if identity["base_graph_sha256"] != payload["base_graph_sha256"] or identity["base_node_hashes"] != payload["base_node_hashes"]:
        raise ValueError("Graph variant base source drift")
    if not isinstance(payload["operations"], list) or not payload["operations"]:
        raise ValueError("Graph variant requires typed operations")
    graph = deepcopy(dict(base_graph))
    added: set[str] = set()
    groups = {node.group for node in base_graph.values()}
    for operation in payload["operations"]:
        if not isinstance(operation, Mapping):
            raise ValueError("Graph operation must be an object")
        op = operation.get("op")
        if op == "add_reasoning_node":
            if set(operation) != {"op", "node"}:
                raise ValueError("Unknown add_reasoning_node fields")
            node = _new_reasoning_node(operation["node"], Path(root), groups)
            if node.id in graph:
                raise ValueError("Cannot replace an existing graph node")
            graph[node.id] = node
            added.add(node.id)
        elif op in {"add_edge", "remove_edge"}:
            if set(operation) != {"op", "dependency_id", "node_id"}:
                raise ValueError("Unknown graph edge operation fields")
            source, target = operation["dependency_id"], operation["node_id"]
            if not isinstance(source, str) or not isinstance(target, str):
                raise ValueError("Graph edge endpoints must be node ids")
            if source not in graph or target not in graph:
                raise ValueError("Dangling graph edge endpoint")
            if graph[target].type != NodeType.REASONING:
                raise ValueError("Tool/feed topology cannot be mutated")
            dependencies = list(graph[target].dependencies)
            if op == "add_edge":
                if source in dependencies:
                    raise ValueError("Duplicate graph edge")
                dependencies.append(source)
            else:
                if source not in dependencies:
                    raise ValueError("Graph edge does not exist")
                dependencies.remove(source)
            graph[target] = replace(graph[target], dependencies=tuple(dependencies))
        elif op == "remove_experimental_node":
            if set(operation) != {"op", "node_id"} or not isinstance(operation["node_id"], str) or operation["node_id"] not in added:
                raise ValueError("Only a node added by this variant may be removed")
            node_id = operation["node_id"]
            if any(node_id in node.dependencies for node in graph.values()):
                raise ValueError("Removing experimental node would leave dangling edges")
            del graph[node_id]
            added.remove(node_id)
        else:
            raise ValueError("Unknown graph operation or dynamic tool mutation")
    issues = validate_graph(graph)
    if issues:
        raise ValueError("Invalid variant topology: " + repr(issues))
    ancestry = {node_id: _ancestors(graph, node_id) for node_id in graph}
    for node_id, base_node in base_graph.items():
        if set(base_node.dependencies) - ancestry[node_id]:
            raise ValueError(f"Variant loses mandatory base ancestry for {node_id}")
        if base_node.type == NodeType.TOOL and graph[node_id] != base_node:
            raise ValueError("Tool/feed source contract changed")
    for node_id, node in graph.items():
        if node.group in {"lab", "surveillance"}:
            if _truth_tainted(node) or any(_truth_tainted(graph[parent]) for parent in ancestry[node_id]):
                raise ValueError(f"Oracle/truth contamination of forward node {node_id}")
        if node_id in added:
            input_contract = node.meta["reasoning_contract"].get("input_contract", {})
            required = set(input_contract.get("required_artifacts", []))
            if required - set(node.dependencies):
                raise ValueError("Experimental node lost a declared required input")
            if set(node.dependencies) - required - set(input_contract.get("optional_artifacts", [])):
                raise ValueError("Experimental node has an undeclared input edge")
    waves = compute_waves(graph)
    ranks = {node_id: index for index, wave in enumerate(waves) for node_id in wave}
    edges = [{"dependency_id": dependency, "node_id": node_id} for node_id, node in sorted(graph.items()) for dependency in sorted(node.dependencies)]
    certificate = {"schema_version": "zenith_graph_rank_certificate_v1", "node_ids": sorted(graph), "edges": edges, "ranks": ranks, "condition": "rank(dependency)<rank(node)"}
    base_edges = {(dependency, node_id) for node_id, node in base_graph.items() for dependency in node.dependencies}
    variant_edges = {(edge["dependency_id"], edge["node_id"]) for edge in edges}
    receipt = {"schema_version": "zenith_graph_variant_receipt_v1", "variant_id": payload["variant_id"], "variant_sha256": payload["variant_sha256"], **identity,
               "effective_graph_sha256": build_base_identity(graph)["base_graph_sha256"],
               "added_node_ids": sorted(added), "added_edges": [list(edge) for edge in sorted(variant_edges - base_edges)],
               "rerouted_base_edges": [list(edge) for edge in sorted(base_edges - variant_edges)],
               "node_count": len(graph), "waves": waves, "acyclic_certificate": certificate,
               "invariants": {"base_contracts_preserved": True, "base_ancestry_preserved": True, "feed_tools_unchanged": True, "forward_truth_isolation": True}}
    return graph, receipt


class FrozenGraphLoader:
    """PhysicalLoader-compatible graph view for the existing GodModeEngine."""
    def __init__(self, base_loader, variant_payload: Mapping[str, Any]):
        self.base_loader = base_loader
        self.root = base_loader.root
        self.variant_payload = deepcopy(dict(variant_payload))
        self._graph, self.receipt = apply_graph_variant(base_loader.load_all_nodes(), self.variant_payload, root=self.root)

    def load_all_nodes(self):
        return deepcopy(self._graph)

    def load_node(self, node_id):
        return deepcopy(self._graph[node_id])

    def compute_waves(self, graph=None):
        return compute_waves(graph if graph is not None else self._graph)

    def validate_topology(self, graph=None):
        return validate_graph(graph if graph is not None else self._graph)

    def get_manifest(self):
        return self.base_loader.get_manifest()

    @property
    def manifest(self):
        return self.get_manifest()

    def get_nodes_dir(self):
        return self.base_loader.get_nodes_dir()

    def import_tool(self, dotted_path):
        return self.base_loader.import_tool(dotted_path)
