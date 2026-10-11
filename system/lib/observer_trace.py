"""
[PURPOSE]
- Teleology: Trace the lifecycle of specific ledger_ids through Lab run artifacts in
  topological DAG order. A pure factual grep engine — no semantic interpretation, no blame.
- Mechanism: For each ledger_id, walk artifacts in topological order; primary check parses
  evidence_dictionary for formal citations; secondary check raw-text greps the full artifact
  JSON blob using word-boundary regex to catch prose mentions.

[INTERFACE]
- Reads: run_dir/artifacts/*.json artifact files; run_dir/metadata.json for topological order.
- Writes: None (read-only).
- Exports: TraceResult, trace_id, trace_all.

[FLOW]
- _load_topo_order: reads metadata.json node_order or waves; fallback is sorted filenames.
- _build_artifacts_index: loads every artifact file once into memory as (raw_str, parsed_dict).
- trace_id: walks topo-ordered index; checks evidence_dictionary + word-boundary grep; returns
  TraceResult with present_in_nodes, absent_after, formally_cited_in, mentioned_in_prose.
- trace_all: batch wrapper; builds index once, calls trace_id for each ID.

[DEPENDENCIES]
- Reads: Run metadata node_order/waves and artifact evidence_dictionary fields; regex matching distinguishes formal citations from prose mentions.

[CONSTRAINTS]
- Topological order read from metadata.json node_order or waves; fallback is sorted stems.
- Primary check: parse evidence_dictionary list and match ledger_id field value.
- Secondary check: word-boundary regex (r'\\b' + re.escape(ledger_id) + r'\\b') on full JSON str.
- present_in_nodes: union of formally cited + prose mentioned, in topological order.
- absent_after: last element of present_in_nodes; None if never seen.
- never_seen: True if present_in_nodes is empty.
- All functions are read-only; never raise; return empty/default on IO failure.
- trace_all loads each artifact file exactly once regardless of how many IDs are traced.
- When-needed: Open when an observation diff or report needs the canonical ledger-id trace rules across Lab artifacts instead of re-grepping the run directory.
- Escalates-to: system/lib/observer_report.py::generate_observation_report; tools/diff/observer_diff_master.py
- Navigation-group: kernel_lib
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple


# ---------------------------------------------------------------------------
# TraceResult
# ---------------------------------------------------------------------------

@dataclass
class TraceResult:
    """
    [ROLE]
    - Factual trace of one ledger_id across all Lab run artifacts in topological order.
    - Contains no semantic interpretation — only where the ID was seen and where it dropped.
    """
    ledger_id: str
    present_in_nodes: List[str]        # Node IDs where it appeared (topological order)
    absent_after: Optional[str]        # Last node_id where it was present; None if never seen
    formally_cited_in: List[str]       # Nodes where it appears in evidence_dictionary
    mentioned_in_prose: List[str]      # Nodes where it appears in raw text but not evidence_dictionary
    never_seen: bool                   # True if ID appears in zero Lab artifacts

    def to_json_dict(self) -> Dict[str, Any]:
        """
        [ACTION]
        - Return a JSON-serializable dict representation of this TraceResult.
        """
        return {
            "ledger_id": self.ledger_id,
            "present_in_nodes": self.present_in_nodes,
            "absent_after": self.absent_after,
            "formally_cited_in": self.formally_cited_in,
            "mentioned_in_prose": self.mentioned_in_prose,
            "never_seen": self.never_seen,
        }


# ---------------------------------------------------------------------------
# Topological order loader
# ---------------------------------------------------------------------------

def _load_topo_order(run_dir: Path) -> List[str]:
    """
    [ACTION]
    - Return a list of node_ids in topological execution order for this run.
    - Reads metadata.json and tries: node_order (flat list), then waves (list of lists or
      list of dicts with 'nodes'/'id'/'node_id'), then node_tree (flat dicts with 'node_id').
    - Falls back to sorted artifact stems if metadata.json is missing or unreadable.
    - Never raises.
    """
    meta_path = run_dir / "metadata.json"
    if meta_path.exists():
        try:
            with open(meta_path) as f:
                meta = json.load(f)

            # Strategy 1: flat node_order list
            node_order = meta.get("node_order")
            if isinstance(node_order, list) and node_order:
                return [str(n) for n in node_order if n]

            # Strategy 2: waves structure (list of wave items)
            waves = meta.get("waves")
            if isinstance(waves, list):
                order: List[str] = []
                for wave in waves:
                    # wave may be a list of node_ids or dicts
                    if isinstance(wave, list):
                        for item in wave:
                            if isinstance(item, dict):
                                nid = item.get("node_id") or item.get("id")
                                if nid:
                                    order.append(str(nid))
                            elif isinstance(item, str):
                                order.append(item)
                    elif isinstance(wave, dict):
                        # wave may be {"nodes": [...]} or {"node_id": "..."}
                        nodes = wave.get("nodes") or wave.get("layer_nodes")
                        if isinstance(nodes, list):
                            for item in nodes:
                                if isinstance(item, dict):
                                    nid = item.get("node_id") or item.get("id")
                                    if nid:
                                        order.append(str(nid))
                                elif isinstance(item, str):
                                    order.append(item)
                        elif wave.get("node_id"):
                            order.append(str(wave["node_id"]))
                if order:
                    return order

            # Strategy 3: node_tree (flat list of dicts)
            node_tree = meta.get("node_tree")
            if isinstance(node_tree, list):
                order = []
                for item in node_tree:
                    if isinstance(item, dict):
                        nid = item.get("node_id") or item.get("id")
                        if nid:
                            order.append(str(nid))
                if order:
                    return order

        except Exception:
            pass

    # Fallback: sorted artifact file stems
    artifacts_dir = run_dir / "artifacts"
    if artifacts_dir.is_dir():
        return sorted(p.stem for p in artifacts_dir.glob("*.json"))
    return []


# ---------------------------------------------------------------------------
# Artifact index builder
# ---------------------------------------------------------------------------

ArtifactEntry = Tuple[str, Dict[str, Any]]  # (raw_json_str, parsed_dict)


def _build_artifacts_index(run_dir: Path) -> Dict[str, ArtifactEntry]:
    """
    [ACTION]
    - Load all artifact files from run_dir/artifacts/*.json into memory once.
    - Returns a dict mapping node_id (stem) → (raw_json_str, parsed_dict).
    - Silently skips unreadable files.
    - Never raises.
    """
    index: Dict[str, ArtifactEntry] = {}
    artifacts_dir = run_dir / "artifacts"
    if not artifacts_dir.is_dir():
        return index
    for path in artifacts_dir.glob("*.json"):
        try:
            raw = path.read_text(encoding="utf-8")
            parsed = json.loads(raw)
            index[path.stem] = (raw, parsed)
        except Exception:
            continue
    return index


def _extract_evidence_ledger_ids(parsed: Dict[str, Any]) -> Set[str]:
    """
    [ACTION]
    - Extract ledger_id values from evidence_dictionary in a parsed artifact dict.
    - Checks both data.evidence_dictionary and top-level evidence_dictionary.
    - Returns empty set if not found or malformed.
    """
    ids: Set[str] = set()
    # Check under .data first, then top-level
    for payload in (parsed.get("data"), parsed):
        if not isinstance(payload, dict):
            continue
        evidence = payload.get("evidence_dictionary")
        if isinstance(evidence, list):
            for entry in evidence:
                if isinstance(entry, dict):
                    lid = entry.get("ledger_id")
                    if lid:
                        ids.add(str(lid))
            break  # found evidence_dictionary; no need to check top-level
    return ids


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def trace_id(run_dir: Path, ledger_id: str) -> TraceResult:
    """
    [ACTION]
    - Teleology: Trace one ledger_id through a Lab run so higher-level reporting can see exactly where it appeared or disappeared.
    - Mechanism: Load topological order and artifact index for the run, then delegate to the shared single-trace implementation.
    - Guarantee: Returns a TraceResult for the requested ledger_id and never raises.
    - Fails: None.
    - When-needed: Open when a caller needs the single-id trace entrypoint rather than the batch tracer.
    - Escalates-to: system/lib/observer_trace.py::trace_all; system/lib/observer_report.py::generate_observation_report
    """
    run_dir = Path(run_dir)
    topo_order = _load_topo_order(run_dir)
    index = _build_artifacts_index(run_dir)
    return _trace_single(ledger_id, topo_order, index)


def _trace_single(
    ledger_id: str,
    topo_order: List[str],
    index: Dict[str, ArtifactEntry],
) -> TraceResult:
    """
    [ACTION]
    - Internal trace implementation shared by trace_id and trace_all.
    - Uses pre-built artifact index to avoid redundant IO.
    """
    pattern = re.compile(r"\b" + re.escape(ledger_id) + r"\b")

    formally_cited_in: List[str] = []
    mentioned_in_prose: List[str] = []

    # Walk in topological order; nodes not in index are silently skipped
    for node_id in topo_order:
        entry = index.get(node_id)
        if entry is None:
            continue
        raw_str, parsed = entry

        # Primary: formal citation in evidence_dictionary
        formal_ids = _extract_evidence_ledger_ids(parsed)
        if ledger_id in formal_ids:
            formally_cited_in.append(node_id)
        elif pattern.search(raw_str):
            # Secondary: prose mention (word-boundary grep)
            mentioned_in_prose.append(node_id)

    present_in_nodes = formally_cited_in + [
        n for n in mentioned_in_prose if n not in formally_cited_in
    ]
    # Re-sort present_in_nodes to match topo order
    topo_pos = {nid: i for i, nid in enumerate(topo_order)}
    present_in_nodes.sort(key=lambda n: topo_pos.get(n, len(topo_order)))

    absent_after = present_in_nodes[-1] if present_in_nodes else None
    never_seen = len(present_in_nodes) == 0

    return TraceResult(
        ledger_id=ledger_id,
        present_in_nodes=present_in_nodes,
        absent_after=absent_after,
        formally_cited_in=formally_cited_in,
        mentioned_in_prose=mentioned_in_prose,
        never_seen=never_seen,
    )


def trace_all(run_dir: Path, ids: Set[str]) -> List[TraceResult]:
    """
    [ACTION]
    - Teleology: Batch trace a ledger-id set through one Lab run with shared IO so report generation stays deterministic and cheap.
    - Mechanism: Load topological order and artifacts once, then trace each requested id in sorted order through the shared trace implementation.
    - Guarantee: Returns a list of TraceResult objects sorted by ledger_id and never raises.
    - Fails: None.
    - When-needed: Open when a report or diff tool needs the canonical batch trace surface for multiple ledger_ids.
    - Escalates-to: system/lib/observer_report.py::generate_observation_report; tools/diff/observer_diff_master.py
    """
    run_dir = Path(run_dir)
    if not ids:
        return []
    topo_order = _load_topo_order(run_dir)
    index = _build_artifacts_index(run_dir)
    results = [_trace_single(lid, topo_order, index) for lid in sorted(ids)]
    return results
