"""
[PURPOSE]
- Teleology: Emit a typed, read-only candidate archive of terminal Polymarket
  lifecycle rows so Oracle hindsight can consume resolved market evidence without
  inventing a Polymarket-local truth ledger.
- Mechanism: Combine pre-normalization identity rows with their lifecycle
  classifications, keep only terminal/archive candidate states, and preserve
  deterministic outcome and raw-status evidence in an additive metadata sidecar.
- Non-goal: This is not a settlement oracle, not a target-pairing engine, and
  not permission to emit production cross-feed divergence cards.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from tools.polymarket.identity import PolymarketMarketIdentity
from tools.polymarket.lifecycle import LifecycleClassification


SCHEMA_VERSION = "polymarket_resolved_archive_candidates.0"
ORACLE_ATTACH_CONTRACT = "oracle_truth_poly_resolved_archive_candidate_v0"
ORACLE_CONSUMER_NODE = "codex/nodes/oracle/oracle_truth_poly.json"

ORACLE_ARCHIVE_CANDIDATE_STATES: Tuple[str, ...] = (
    "FORMALLY_RESOLVED",
    "DE_FACTO_TERMINAL",
    "EVENT_PASSED_UNRESOLVED",
    "ARCHIVED_OR_STALE",
    "DATA_CONFLICT",
)

_TERMINAL_STATES = frozenset({"FORMALLY_RESOLVED", "DE_FACTO_TERMINAL"})


@dataclass(frozen=True)
class ResolvedArchiveCandidate:
    archive_key: str
    observation_id: str
    source_lane: str
    oracle_attach_contract: str
    oracle_consumer_node: str
    truth_boundary: str
    lifecycle_state: str
    resolution_status: str
    resolution_confidence: float
    event_id: Optional[str]
    event_slug: Optional[str]
    market_id: Optional[str]
    market_slug: Optional[str]
    market_question: Optional[str]
    condition_id: Optional[str]
    clob_token_ids: Tuple[str, ...]
    outcomes: Tuple[str, ...]
    outcome_prices: Tuple[float, ...]
    top_outcome_label: Optional[str]
    top_outcome_price: Optional[float]
    terminal_price_evidence: bool
    end_date_iso: Optional[str]
    resolution_source: Optional[str]
    raw_status: Mapping[str, Optional[bool]]
    lifecycle_components: Mapping[str, Any]
    lifecycle_conflicts: Tuple[str, ...]
    admissible_for: Tuple[str, ...]
    not_admissible_for: Tuple[str, ...]


def _archive_key(row: PolymarketMarketIdentity) -> str:
    stable_id = row.condition_id or row.market_id or row.market_slug or "unknown_market"
    return f"polymarket:{stable_id}"


def _as_tuple(value: Optional[Sequence[Any]]) -> Tuple[Any, ...]:
    if value is None:
        return ()
    return tuple(value)


def _top_outcome(
    row: PolymarketMarketIdentity,
) -> Tuple[Optional[str], Optional[float], bool]:
    prices = _as_tuple(row.outcome_prices)
    outcomes = _as_tuple(row.outcomes)
    if not prices:
        return None, None, False
    best_index = max(range(len(prices)), key=lambda idx: float(prices[idx]))
    label = str(outcomes[best_index]) if best_index < len(outcomes) else None
    price = float(prices[best_index])
    return label, price, price >= 0.95 or price <= 0.05


def _resolution_status(state: str) -> str:
    if state == "FORMALLY_RESOLVED":
        return "formally_resolved"
    if state == "DE_FACTO_TERMINAL":
        return "terminal_inferred"
    if state == "EVENT_PASSED_UNRESOLVED":
        return "event_passed_unresolved"
    if state == "ARCHIVED_OR_STALE":
        return "archived_or_stale"
    if state == "DATA_CONFLICT":
        return "data_conflict"
    return "unknown"


def build_resolved_archive_candidates(
    rows: Sequence[PolymarketMarketIdentity],
    lifecycle_classifications: Sequence[LifecycleClassification],
    *,
    as_of: str,
    max_embedded_rows: int = 1000,
) -> Dict[str, Any]:
    """Build the Oracle-facing resolved-archive candidate sidecar.

    The sidecar is intentionally a candidate archive. It exposes terminal and
    post-event evidence to Oracle's existing hindsight lane, while leaving target
    alignment and cross-feed claim admission to Oracle/Lab readiness gates.
    """

    if len(rows) != len(lifecycle_classifications):
        raise ValueError(
            "lifecycle_classifications length ("
            f"{len(lifecycle_classifications)}) must match identity row count ({len(rows)}). "
            "Resolved archive candidates require the same ordered identity/lifecycle universe."
        )

    candidates: List[ResolvedArchiveCandidate] = []
    for row, classification in zip(rows, lifecycle_classifications):
        state = classification.state
        if state not in ORACLE_ARCHIVE_CANDIDATE_STATES:
            continue
        key = _archive_key(row)
        top_label, top_price, terminal_price = _top_outcome(row)
        outcomes = tuple(str(item) for item in _as_tuple(row.outcomes))
        prices = tuple(float(item) for item in _as_tuple(row.outcome_prices))
        token_ids = tuple(str(item) for item in _as_tuple(row.clob_token_ids))

        candidates.append(
            ResolvedArchiveCandidate(
                archive_key=key,
                observation_id=f"{key}@{as_of}",
                source_lane="global_polymarket_feed",
                oracle_attach_contract=ORACLE_ATTACH_CONTRACT,
                oracle_consumer_node=ORACLE_CONSUMER_NODE,
                truth_boundary="truth_side_observation_only_existing_oracle_hindsight_lane",
                lifecycle_state=state,
                resolution_status=_resolution_status(state),
                resolution_confidence=classification.confidence,
                event_id=row.event_id,
                event_slug=row.event_slug,
                market_id=row.market_id,
                market_slug=row.market_slug,
                market_question=row.market_question,
                condition_id=row.condition_id,
                clob_token_ids=token_ids,
                outcomes=outcomes,
                outcome_prices=prices,
                top_outcome_label=top_label,
                top_outcome_price=top_price,
                terminal_price_evidence=terminal_price,
                end_date_iso=row.end_date_iso,
                resolution_source=row.resolution_source,
                raw_status={
                    "active": row.raw_status_active,
                    "closed": row.raw_status_closed,
                    "resolved": row.raw_status_resolved,
                    "archived": row.raw_status_archived,
                },
                lifecycle_components=classification.components,
                lifecycle_conflicts=classification.conflicts,
                admissible_for=(
                    "oracle_truth_poly",
                    "realized_hindsight_brief_context",
                    "cp2_critique_realized_refs",
                ),
                not_admissible_for=(
                    "standalone_truth_ledger",
                    "prediction_reconciliation_without_target_pairing",
                    "cross_feed_divergence_card_without_relation_gate",
                ),
            )
        )

    state_counts: Dict[str, int] = {state: 0 for state in ORACLE_ARCHIVE_CANDIDATE_STATES}
    status_counts: Dict[str, int] = {}
    for row in candidates:
        state_counts[row.lifecycle_state] = state_counts.get(row.lifecycle_state, 0) + 1
        status_counts[row.resolution_status] = status_counts.get(row.resolution_status, 0) + 1

    embedded = candidates[: max(0, max_embedded_rows)]
    embedded_rows = [asdict(row) for row in embedded]
    for payload in embedded_rows:
        for key in (
            "clob_token_ids",
            "outcomes",
            "outcome_prices",
            "lifecycle_conflicts",
            "admissible_for",
            "not_admissible_for",
        ):
            value = payload.get(key)
            if isinstance(value, tuple):
                payload[key] = list(value)

    return {
        "schema_version": SCHEMA_VERSION,
        "enabled": True,
        "as_of": as_of,
        "oracle_attach": {
            "contract": ORACLE_ATTACH_CONTRACT,
            "consumer_node": ORACLE_CONSUMER_NODE,
            "owner_boundary": "Oracle consumes this as truth-side lane evidence; Polymarket does not own a local truth ledger.",
            "target_pairing_status": "not_built",
        },
        "candidate_states": list(ORACLE_ARCHIVE_CANDIDATE_STATES),
        "row_count": len(candidates),
        "rows": embedded_rows,
        "diagnostics": {
            "candidate_pool_size": len(rows),
            "embedded_row_count": len(embedded_rows),
            "rows_truncated": len(embedded_rows) < len(candidates),
            "lifecycle_state_counts": state_counts,
            "resolution_status_counts": dict(sorted(status_counts.items())),
            "terminal_state_count": sum(
                1 for row in candidates if row.lifecycle_state in _TERMINAL_STATES
            ),
            "terminal_price_evidence_count": sum(
                1 for row in candidates if row.terminal_price_evidence
            ),
            "resolution_source_count": sum(
                1 for row in candidates if row.resolution_source
            ),
            "data_conflict_count": state_counts.get("DATA_CONFLICT", 0),
            "selection_rule": "lifecycle_state_in_oracle_archive_candidate_states",
            "truth_boundary": "read_only_candidate_archive_existing_oracle_lane",
        },
    }


def empty_resolved_archive_candidates() -> Dict[str, Any]:
    """Stable empty sidecar shape for the failure envelope path."""

    return {
        "schema_version": SCHEMA_VERSION,
        "enabled": False,
        "as_of": None,
        "oracle_attach": {
            "contract": ORACLE_ATTACH_CONTRACT,
            "consumer_node": ORACLE_CONSUMER_NODE,
            "owner_boundary": "not_attempted_on_scanner_failure",
            "target_pairing_status": "not_built",
        },
        "candidate_states": list(ORACLE_ARCHIVE_CANDIDATE_STATES),
        "row_count": 0,
        "rows": [],
        "diagnostics": {"reason": "scanner failure path; resolved archive not attempted"},
    }
