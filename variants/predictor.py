"""Explicit price-only replacement of Lab internals, using its native CP contracts.

This is an ablation declaration, not an ancestry-preserving topology overlay.
The authored graph remains untouched. Only this fixed, forward-only profile is
admitted; tools, output schemas and the native executor are reused.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from typing import Mapping

from system.core.governance import compute_waves, validate_topology
from system.lib.hashing import hash_node
from variants.graph import FrozenGraphLoader, build_base_identity, variant_sha256

SCHEMA = "zenith_predictor_replacement_v1"
PROFILE = "stocknet_price_only_cp1_cp2_v2"
FIELDS = {"schema_version", "variant_id", "base_graph_sha256", "base_node_hashes",
          "instruction_profile", "variant_sha256"}
NODE_IDS = ("global_stock_feed", "lab_decide", "lab_director")

# The source roles, thesis scaffold, citations, grounding and word requirements
# are retained from the original CP1/CP2 instructions. Missing miner/flow lanes
# are explicitly removed by this price-only ablation, not simulated.
FORWARD_RULE = (
    "You are forecasting from a frozen public historical snapshot. Use only supplied observations. "
    "Do not use remembered subsequent events. No browsing, tools or external sources. "
    "Only the STOCK lane is supplied; ETF, MACRO, NEWS, POLYMARKET, STOCKGRID and CALCULATOR "
    "are unavailable. Absence is unavailable evidence, never a neutral measurement. "
    "Return ONLY one valid JSON object, without markdown or a prose wrapper."
)
CP1_RULE = """[ROLE]
You are the Synthesizer. Build one dominant epicentre thesis from the recorded STOCK snapshot.
[CORE REQUIREMENTS]
- Thesis must be singular, specific, and falsifiable.
- Begin: 'At T-n, the dominant force is <FORCE> operating through <PRIMARY TRANSMISSION PATH>, producing <SPECIFIC CROSS-ASSET CONSEQUENCE SET>; this thesis is false if <OBSERVABLE INVALIDATION CONDITIONS>.'
- Include dominance justification, transmission path, consequence map by {{TARGET_TIME}} and invalidation conditions. Distinguish observed prices from hypotheses; unavailable flow or narrative data cannot support a claim.
- epicentre_thesis must contain at least 150 words. Aim for 200-250 words inside that JSON string; count whitespace-separated words, not tokens, JSON keys or evidence_dictionary entries.
- Cite resolved [N] entries in evidence_dictionary. ref_id values must be literal bracketed strings such as "[1]", "[2]", "[3]", never "1" or "2". Before returning, self-check that every citation uses brackets and resolves to an evidence_dictionary ref_id.
- Ground EVERY declared target in a stock evidence entry. Copy each supplied ledger_id and subject exactly; ref_id sequential [N].
- No cross-correlation, bifurcation or miner output was executed. Do not invent one.
[OUTPUT]
See Contract: codex/substrate/contracts/schema_cp1.json
Return {"evidence_dictionary":[{"ref_id":"[1]","ledger_id":"S_00000001","subject":"AAPL","signal_summary":"..."}],"epicentre_thesis":"..."}.
"""
CP2_RULE = """[ROLE]
You are the Trajectory Director. CP1 thesis is locked. Project its force into specific directional consequences by {{TARGET_TIME}}.
[INPUTS]
- lab_decide: locked CP1 thesis and evidence dictionary.
- global_stock_feed: exact subject quotes, past observed OHLCV and declared targets.
[REQUIREMENTS]
- Inherit CP1 epicentre_thesis verbatim and all its evidence entries exactly.
- Forecast EACH declared target exactly once. No other target; no omission.
- Cite the supplied current spot price and emit snapshot_price equal to it.
- Emit a specific finite target_price consistent with direction: UP => target_price > snapshot_price; DOWN => target_price < snapshot_price.
- Every target needs subject==target_id and an S_ equity ledger entry, copied from the subject feed.
- Explain force -> transmission -> each prediction consequence; dense resolved [N] citations and concrete invalidation conditions. Minimum trade_rationale length: 75 + 30N words for N targets.
- For this three-target profile, trade_rationale must contain at least 165 words. Aim for 220-280 words inside that JSON string. Count whitespace-separated words in trade_rationale only; the inherited epicentre_thesis, evidence_dictionary and predictions_t do NOT count toward the rationale minimum.
- Before returning, self-check the separate trade_rationale word count and literal bracketed ref_id strings such as "[1]", "[2]", "[3]". Every [N] citation must resolve to an inherited or valid added evidence_dictionary entry; unbracketed ref_id values are invalid.
- No Phase 2 miner, cross-correlation or thesis-stress node was executed. Do not invent its findings.
[OUTPUT]
See Contract: codex/substrate/contracts/schema_cp2.json
Return {"evidence_dictionary":[...],"epicentre_thesis":"[copy CP1 verbatim]","predictions_t":[{"target_id":"AAPL","direction":"UP","snapshot_price":100.0,"target_price":100.1,"invalidation":"..."}],"trade_rationale":"..."}.
The engine binds snapshot_time={{SNAPSHOT_TIME}} and target_time_iso={{TARGET_TIME}}; do not change them.
"""


def build_replacement(base_graph: Mapping) -> dict:
    payload = {"schema_version": SCHEMA, "variant_id": PROFILE,
               "instruction_profile": PROFILE, **build_base_identity(base_graph)}
    payload["variant_sha256"] = variant_sha256(payload)
    return payload


def apply_predictor_replacement(base_graph: Mapping, payload: Mapping):
    if not isinstance(payload, Mapping) or set(payload) != FIELDS:
        raise ValueError("predictor replacement requires exactly the declared fields")
    if (payload["schema_version"] != SCHEMA or payload["instruction_profile"] != PROFILE
            or payload["variant_id"] != PROFILE):
        raise ValueError("unknown predictor replacement profile")
    identity = build_base_identity(base_graph)
    if any(payload[key] != identity[key] for key in identity):
        raise ValueError("predictor replacement base source identity differs")
    if payload["variant_sha256"] != variant_sha256(payload):
        raise ValueError("predictor replacement hash differs")
    if not set(NODE_IDS) <= set(base_graph):
        raise ValueError("canonical stock/CP1/CP2 nodes are missing")
    stock, cp1, cp2 = (deepcopy(base_graph[key]) for key in NODE_IDS)
    if (stock.type.value != "tool" or not stock.meta.get("is_feed")
            or stock.dependencies or cp1.output_schema != "isomorphic_cp1"
            or cp2.output_schema != "isomorphic_cp2"
            or cp1.type.value != "reasoning" or cp2.type.value != "reasoning"
            or cp1.group != "lab" or cp2.group != "lab"):
        raise ValueError("canonical predictor interfaces differ")
    graph = {stock.id: stock}
    for node, dependencies, instruction in (
        (cp1, (stock.id,), CP1_RULE),
        (cp2, (cp1.id, stock.id), CP2_RULE),
    ):
        meta = deepcopy(node.meta)
        contract = meta.get("reasoning_contract")
        if contract is not None:
            contract["input_contract"].update(
                required_artifacts=list(dependencies), optional_artifacts=[],
                authority_requirements=["CP evidence cites subject-side STOCK ledger ids and the locked CP1 thesis"])
            contract["learning_contract"]["dossier_reads"] = []
            contract["injection_contract"]["inject"] = [
                value for value in contract["injection_contract"]["inject"] if value != "prior_dossier_slice"]
        meta["predictor_replacement"] = {
            "profile": PROFILE, "context_mode": "forward_subject_only",
            "required_artifacts": list(dependencies), "forbidden_context": ["truth_side_evidence"],
            "available_feed_lanes": ["STOCK"],
        }
        execution = {**node.execution, "retries": 1, "tools": []}
        graph[node.id] = replace(node, dependencies=dependencies,
                                 instruction=FORWARD_RULE + "\n" + instruction,
                                 meta=meta, execution=execution)
    if validate_topology(graph):
        raise ValueError("replacement predictor topology is invalid")
    waves = compute_waves(graph)
    ranks = {key: index for index, wave in enumerate(waves) for key in wave}
    edges = [{"dependency_id": parent, "node_id": key}
             for key, node in sorted(graph.items()) for parent in sorted(node.dependencies)]
    receipt = {"schema_version": SCHEMA, "variant_id": payload["variant_id"],
               "variant_sha256": payload["variant_sha256"], **identity,
               "effective_graph_sha256": build_base_identity(graph)["base_graph_sha256"],
               "node_hashes": {key: hash_node(node) for key, node in sorted(graph.items())},
               "node_count": len(graph), "waves": waves,
               "removed_node_ids": sorted(set(base_graph) - set(graph)),
               "acyclic_certificate": {"schema_version": "zenith_graph_rank_certificate_v1",
                   "node_ids": sorted(graph), "edges": edges, "ranks": ranks,
                   "condition": "rank(dependency)<rank(node)"},
               "invariants": {"cp1_cp2_interfaces_preserved": True, "stock_tool_unchanged": True,
                   "forward_truth_isolation": True, "base_ancestry_preserved": False},
               "claim_boundary": "Explicit price-only replacement; not full authored Lab execution or proven empirical refinement."}
    return graph, receipt


class PredictorLoader(FrozenGraphLoader):
    """Reuse the native loader interface and engine, with explicit ablated scope."""
    def __init__(self, base_loader, replacement_payload):
        self.base_loader = base_loader
        self.root = base_loader.root
        self.variant_payload = deepcopy(dict(replacement_payload))
        self._graph, self.receipt = apply_predictor_replacement(
            base_loader.load_all_nodes(), replacement_payload)
