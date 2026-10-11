"""
[PURPOSE]
- Teleology: Classify stock and ETF feed rows into a lane-native equity
  lifecycle sidecar before Lab, Oracle, or cross-feed situation layers interpret
  raw price movement as event evidence.
- Mechanism: Consume the existing `stock.1` table plus configured universe rows,
  derive deterministic U.S. equity session posture from the run `as_of`, and
  preserve explicit v0 gaps for halt, corporate-action, NAV, premium/discount,
  basket, and rebalance evidence.

[INTERFACE]
- `EQUITY_LIFECYCLE_STATES` — canonical ordered tuple of v0 equity states.
- `EquityLifecycleClassification` — frozen dataclass carrying state,
  confidence, components, and reasons.
- `classify_equity_row()` — classify one configured or emitted ticker row.
- `build_equity_lifecycle_snapshot()` — build the metadata sidecar payload.

[CONSTRAINTS]
- Substrate-only: no HTTP calls, no cache writes, no mutation of stock rows.
- Additive: the sidecar never changes the `stock.1` table shape.
- Honest v0: unsupported halt/corporate-action/NAV evidence is typed as unknown
  or unavailable rather than inferred from price movement.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timezone
from typing import Any, Dict, Iterable, Mapping, Optional, Sequence, Tuple
from zoneinfo import ZoneInfo


EQUITY_LIFECYCLE_SIDECAR_KEY = "equity_lifecycle_snapshot"
EQUITY_LIFECYCLE_SCHEMA_VERSION = "equity_lifecycle_snapshot.0"

EQUITY_LIFECYCLE_STATES: Tuple[str, ...] = (
    "REGULAR_SESSION_PRICE_OBSERVED",
    "PRE_MARKET_PRICE_OBSERVED",
    "AFTER_HOURS_PRICE_OBSERVED",
    "WEEKEND_PRICE_OBSERVED",
    "SESSION_UNKNOWN_PRICE_OBSERVED",
    "PRICE_UNAVAILABLE",
    "CONFIGURED_NOT_EMITTED",
    "DATA_CONFLICT",
)

EQUITY_SESSION_STATES: Tuple[str, ...] = (
    "REGULAR_SESSION",
    "PRE_MARKET_WINDOW",
    "AFTER_HOURS_WINDOW",
    "WEEKEND_CLOSED",
    "UNKNOWN",
)

_SESSION_TO_PRICE_STATE = {
    "REGULAR_SESSION": "REGULAR_SESSION_PRICE_OBSERVED",
    "PRE_MARKET_WINDOW": "PRE_MARKET_PRICE_OBSERVED",
    "AFTER_HOURS_WINDOW": "AFTER_HOURS_PRICE_OBSERVED",
    "WEEKEND_CLOSED": "WEEKEND_PRICE_OBSERVED",
    "UNKNOWN": "SESSION_UNKNOWN_PRICE_OBSERVED",
}


@dataclass(frozen=True)
class EquityLifecycleClassification:
    state: str
    confidence: float
    components: Dict[str, Any]
    reasons: Tuple[str, ...]


def _parse_iso_datetime(value: str) -> Optional[datetime]:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _market_session(as_of_iso: str) -> Dict[str, Any]:
    parsed = _parse_iso_datetime(as_of_iso)
    if parsed is None:
        return {
            "state": "UNKNOWN",
            "market": "XNYS",
            "calendar_model": "weekday_regular_hours_v0",
            "anchor_utc": as_of_iso,
            "anchor_local": None,
            "timezone": "America/New_York",
            "limitations": [
                "holiday_calendar_not_integrated_v0",
                "early_close_calendar_not_integrated_v0",
            ],
        }

    local = parsed.astimezone(ZoneInfo("America/New_York"))
    if local.weekday() >= 5:
        state = "WEEKEND_CLOSED"
    elif time(9, 30) <= local.time() <= time(16, 0):
        state = "REGULAR_SESSION"
    elif local.time() < time(9, 30):
        state = "PRE_MARKET_WINDOW"
    else:
        state = "AFTER_HOURS_WINDOW"

    return {
        "state": state,
        "market": "XNYS",
        "calendar_model": "weekday_regular_hours_v0",
        "anchor_utc": parsed.isoformat(),
        "anchor_local": local.isoformat(),
        "timezone": "America/New_York",
        "regular_session_local": "09:30-16:00",
        "limitations": [
            "holiday_calendar_not_integrated_v0",
            "early_close_calendar_not_integrated_v0",
        ],
    }


def _safe_float(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None
        parsed = float(value)
        if parsed != parsed:
            return None
        return parsed
    except (TypeError, ValueError):
        return None


def _first_nonempty(*values: Any) -> Optional[str]:
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def resolve_equity_lane(config: Mapping[str, Any]) -> str:
    runtime = config.get("runtime", {}) if isinstance(config.get("runtime"), Mapping) else {}
    candidates = [
        config.get("lane"),
        runtime.get("lane") if isinstance(runtime, Mapping) else None,
        runtime.get("feed_id") if isinstance(runtime, Mapping) else None,
        runtime.get("node_id") if isinstance(runtime, Mapping) else None,
        config.get("id"),
        config.get("universe_ref"),
        config.get("__doc"),
    ]
    haystack = " ".join(str(item).lower() for item in candidates if item is not None)
    if "etf" in haystack or "global_etf_feed" in haystack:
        return "ETF"
    return "STOCK"


def _asset_components(asset_class: str) -> Dict[str, Any]:
    if asset_class == "ETF":
        return {
            "nav_posture": "NAV_UNAVAILABLE_V0",
            "premium_discount_posture": "PREMIUM_DISCOUNT_UNAVAILABLE_V0",
            "basket_rebalance_posture": "BASKET_REBALANCE_UNAVAILABLE_V0",
        }
    return {
        "nav_posture": "NOT_APPLICABLE",
        "premium_discount_posture": "NOT_APPLICABLE",
        "basket_rebalance_posture": "NOT_APPLICABLE",
    }


def classify_equity_row(
    *,
    ticker: str,
    category: Optional[str],
    identity: Optional[str],
    price: Any,
    as_of_iso: str,
    asset_class: str = "STOCK",
    emitted: bool = True,
    session: Optional[Mapping[str, Any]] = None,
) -> EquityLifecycleClassification:
    session_info = dict(session or _market_session(as_of_iso))
    session_state = str(session_info.get("state") or "UNKNOWN")
    reasons = []
    price_value = _safe_float(price)

    if not str(ticker or "").strip():
        state = "DATA_CONFLICT"
        confidence = 0.3
        reasons.append("missing_ticker_identity")
    elif not emitted:
        state = "CONFIGURED_NOT_EMITTED"
        confidence = 0.9
        reasons.append("configured_ticker_absent_from_stock_payload")
    elif price_value is None:
        state = "PRICE_UNAVAILABLE"
        confidence = 0.85
        reasons.append("emitted_row_without_numeric_price")
    else:
        state = _SESSION_TO_PRICE_STATE.get(session_state, "SESSION_UNKNOWN_PRICE_OBSERVED")
        confidence = 0.9 if session_state != "UNKNOWN" else 0.7
        reasons.extend(["numeric_price_observed", f"session_state_{session_state.lower()}"])

    components: Dict[str, Any] = {
        "ticker": str(ticker or "").upper().strip(),
        "category": category,
        "identity": identity,
        "asset_class": asset_class,
        "emitted": bool(emitted),
        "has_numeric_price": price_value is not None,
        "price": price_value,
        "session_state": session_state,
        "market": session_info.get("market"),
        "calendar_model": session_info.get("calendar_model"),
        "halt_posture": "UNKNOWN_NOT_IN_PROVIDER_EVIDENCE",
        "delay_or_suspension_posture": "UNKNOWN_NOT_IN_PROVIDER_EVIDENCE",
        "corporate_action_posture": "UNKNOWN_NOT_IN_PROVIDER_EVIDENCE",
        "quote_interpretability": (
            "price_interpretable_with_session_context"
            if price_value is not None
            else "price_missing_or_unusable"
        ),
    }
    components.update(_asset_components(asset_class))

    if asset_class == "ETF":
        reasons.append("etf_nav_basket_rebalance_provider_not_integrated_v0")
    reasons.append("halt_and_corporate_action_provider_not_integrated_v0")

    return EquityLifecycleClassification(
        state=state,
        confidence=confidence,
        components=components,
        reasons=tuple(reasons),
    )


def _rows_from_table(table: Mapping[str, Any]) -> Dict[str, Dict[str, Any]]:
    columns = table.get("columns", [])
    rows = table.get("rows", [])
    if not isinstance(columns, list) or not isinstance(rows, list):
        return {}
    normalized: Dict[str, Dict[str, Any]] = {}
    for raw in rows:
        if not isinstance(raw, list):
            continue
        record = {
            str(col): raw[index] if index < len(raw) else None
            for index, col in enumerate(columns)
        }
        ticker = str(record.get("Ticker") or "").upper().strip()
        if ticker:
            normalized[ticker] = record
    return normalized


def _configured_rows(
    configured_universe: Sequence[Tuple[str, str, str]],
) -> Dict[str, Dict[str, Any]]:
    rows: Dict[str, Dict[str, Any]] = {}
    for category, ticker, identity in configured_universe:
        key = str(ticker or "").upper().strip()
        if not key:
            continue
        rows[key] = {
            "Category": category,
            "Ticker": ticker,
            "Identity": identity,
        }
    return rows


def _state_distribution(rows: Iterable[Mapping[str, Any]]) -> Dict[str, int]:
    counts = {state: 0 for state in EQUITY_LIFECYCLE_STATES}
    for row in rows:
        state = str(row.get("state") or "")
        if state not in counts:
            counts[state] = 0
        counts[state] += 1
    return {state: count for state, count in counts.items() if count}


def build_equity_lifecycle_snapshot(
    *,
    table: Mapping[str, Any],
    configured_universe: Sequence[Tuple[str, str, str]],
    diagnostics: Mapping[str, Any],
    as_of_iso: str,
    config: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    cfg = config or {}
    lane = resolve_equity_lane(cfg)
    asset_class = "ETF" if lane == "ETF" else "STOCK"
    session_info = _market_session(as_of_iso)
    emitted = _rows_from_table(table)
    configured = _configured_rows(configured_universe)
    tickers = sorted(set(configured.keys()) | set(emitted.keys()))

    rows = []
    for ticker in tickers:
        record = emitted.get(ticker) or configured.get(ticker) or {}
        classification = classify_equity_row(
            ticker=ticker,
            category=_first_nonempty(record.get("Category")),
            identity=_first_nonempty(record.get("Identity")),
            price=record.get("Price"),
            as_of_iso=as_of_iso,
            asset_class=asset_class,
            emitted=ticker in emitted,
            session=session_info,
        )
        rows.append(
            {
                "ticker": ticker,
                "asset_class": asset_class,
                "state": classification.state,
                "confidence": classification.confidence,
                "components": classification.components,
                "reasons": list(classification.reasons),
            }
        )

    distribution = _state_distribution(rows)
    missing_price_count = sum(1 for row in rows if row["state"] == "PRICE_UNAVAILABLE")
    configured_not_emitted_count = distribution.get("CONFIGURED_NOT_EMITTED", 0)
    return {
        "schema_version": EQUITY_LIFECYCLE_SCHEMA_VERSION,
        "as_of": as_of_iso,
        "lane": lane,
        "asset_class": asset_class,
        "session": session_info,
        "row_count": len(rows),
        "state_distribution": distribution,
        "rows": rows,
        "diagnostics": {
            "configured_count": len(configured),
            "emitted_count": len(emitted),
            "configured_not_emitted_count": configured_not_emitted_count,
            "missing_price_count": missing_price_count,
            "fetch_success_count": diagnostics.get("fetch_success_count"),
            "fetch_failure_count": diagnostics.get("fetch_failure_count"),
        },
        "capabilities": {
            "market_session_calendar": "weekday_regular_hours_v0",
            "holiday_calendar": "not_integrated_v0",
            "early_close_calendar": "not_integrated_v0",
            "halt_delay_suspension_provider": "not_integrated_v0",
            "corporate_actions_provider": "not_integrated_v0",
            "etf_nav_premium_discount_provider": (
                "not_integrated_v0" if asset_class == "ETF" else "not_applicable"
            ),
        },
    }
