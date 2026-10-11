"""
[PURPOSE]
- Mechanism: Hash the canonical JSON serialization of the node identity projection with SHA-256.
- Teleology: Provide a deterministic, portable identity digest for Codex nodes (cache keys, run reproducibility).

[INTERFACE]
- Exports: hash_node(node: Any) -> str

[FLOW]
- Extract logical identity fields from the node.
- Canonicalize via JSON (sort_keys=True, ensure_ascii=True).
- Return sha256 hex digest of the UTF-8 encoded payload.
- When-needed: Open when cache reuse, artifact provenance, or resume checks need the authoritative node-identity digest contract instead of reconstructing it from engine callers.
- Escalates-to: system/core/engine.py; system/server/main.py
- Navigation-group: kernel_lib

[DEPENDENCIES]
- standard_lib.hashlib: sha256 (digest)
- standard_lib.json: canonical serialization contract (sort_keys=True, ensure_ascii=True)

[CONSTRAINTS]
- Orders: dependency list is sorted; JSON keys are sorted.
- Writes: None (pure function).
- Fails: Propagates AttributeError/TypeError if required node fields are missing or non-serializable.
"""
from __future__ import annotations
import hashlib
import json
from typing import Any, Dict

def hash_node(node: Any) -> str:
    """
    [ACTION]
    - Teleology: Compute a stable content identity for a node's logical configuration.
    - Mechanism: Extract logical fields -> canonical JSON -> sha256 hex digest.
    - Reads: node.id, node.type, node.dependencies, node.instruction, node.platform, node.config, node.execution, node.meta.is_feed (optional).
    - Writes: None.
    - Orders: dependencies sorted; JSON uses sort_keys=True and ensure_ascii=True.
    - Schema: Returns a lowercase 64-char hex string.
    - Fails: AttributeError/TypeError if required fields are missing or payload is not JSON-serializable.
    - Guarantee: Identical logical payload yields identical digest across processes.
    - Non-goal: Does not validate node schema; does not incorporate runtime state, timestamps, or artifacts.
    - When-needed: Open when a caller needs the canonical logical-field digest used for cache keys, provenance checks, or node-hash comparisons across runs.
    - Escalates-to: system/core/engine.py; system/server/main.py
    """
    # 1. Extract type value (handles both Enum and string)
    node_type = node.type
    if hasattr(node_type, "value"):
        node_type = node_type.value

    # 2. Sort dependencies for determinism
    deps = sorted(list(node.dependencies)) if node.dependencies else []

    # 3. Extract is_feed from meta
    meta = getattr(node, "meta", {})
    if not isinstance(meta, dict): meta = {}
    is_feed = meta.get("is_feed", False)

    # 4. Build identity payload (STRICT MATCH to engine.py:384)
    # output_schema is included: changing schema mode forces a cache bust (Phase 2.3).
    # boundary and routing_class are excluded: ontology metadata, not execution logic.
    identity: Dict[str, Any] = {
        "id": node.id,
        "type": node_type,
        "dependencies": deps,
        "instruction": node.instruction,
        "platform": node.platform,
        "config": node.config,
        "execution": node.execution,
        "is_feed": is_feed,
        "output_schema": getattr(node, "output_schema", "text"),
    }

    payload_str = json.dumps(identity, sort_keys=True, ensure_ascii=True)
    return hashlib.sha256(payload_str.encode("utf-8")).hexdigest()
