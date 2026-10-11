"""
[PURPOSE]
- Teleology: Classify each configured FRED macro series into a lane-native
  release/vintage lifecycle state before Lab, Oracle, or cross-feed situation
  layers interpret the latest macro value.
- Mechanism: Consume the existing macro fetch/cache outputs plus per-series
  lifecycle hints from `tools.macro.macro`, then emit a deterministic sidecar
  preserving component evidence.

[INTERFACE]
- `MACRO_LIFECYCLE_STATES` — canonical ordered tuple of v0 macro lifecycle states.
- `MacroLifecycleClassification` — frozen dataclass carrying state, confidence,
  components, and reasons.
- `classify_macro_series()` — classify one configured/emitted series.
- `build_macro_lifecycle_snapshot()` — build the metadata sidecar payload.

[CONSTRAINTS]
- Substrate-only: no HTTP calls, no cache writes, no mutation of macro rows.
- Additive: the sidecar never changes the `macro.2` table shape.
- Component-preserving: reasons and source hints remain available for future
  Oracle calibration rather than being collapsed into one quality string.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any, Dict, Iterable, Mapping, Optional, Tuple


MACRO_LIFECYCLE_SIDECAR_KEY = "macro_lifecycle_snapshot"
MACRO_LIFECYCLE_SCHEMA_VERSION = "macro_lifecycle_snapshot.0"

MACRO_LIFECYCLE_STATES: Tuple[str, ...] = (
    "RELEASED_CURRENT",
    "NEW_RELEASE_OBSERVED",
    "REVISION_OBSERVED",
    "STALE_CACHE",
    "SOURCE_DEGRADED",
    "INVALID_SERIES",
    "CONFIGURED_NOT_EMITTED",
    "DATA_CONFLICT",
)


@dataclass(frozen=True)
class MacroLifecycleClassification:
    state: str
    confidence: float
    components: Dict[str, Any]
    reasons: Tuple[str, ...]


def _resolve_series_id(spec: Any, fred_row: Mapping[str, Any], hint: Mapping[str, Any]) -> str:
    if isinstance(hint.get("series_id"), str) and hint["series_id"].strip():
        return hint["series_id"].strip()
    raw = fred_row.get("id")
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    if isinstance(spec, Mapping):
        candidate = spec.get("id")
    else:
        candidate = spec
    return str(candidate or "").strip()


def _safe_error(*rows: Mapping[str, Any]) -> Optional[str]:
    for row in rows:
        raw = row.get("error")
        if raw is None:
            continue
        text = str(raw).strip()
        if text:
            return text
    return None


def _has_numeric_value(*rows: Mapping[str, Any]) -> bool:
    for row in rows:
        for key in ("end", "last"):
            try:
                value = row.get(key)
                if value is not None and float(value) == float(value):
                    return True
            except Exception:
                continue
    return False


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


def _parse_ymd(value: Any) -> Optional[date]:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def _as_of_date(as_of_iso: str) -> Optional[date]:
    parsed = _parse_iso_datetime(as_of_iso)
    return parsed.date() if parsed else _parse_ymd(as_of_iso)


def _first_nonempty(*values: Any) -> Optional[str]:
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def _detect_conflicts(components: Mapping[str, Any], *, as_of_day: Optional[date]) -> Tuple[str, ...]:
    conflicts = []
    latest_day = _parse_ymd(components.get("latest_observation_date"))
    realtime_day = _parse_ymd(components.get("realtime_start"))
    if as_of_day is not None and latest_day is not None and latest_day > as_of_day:
        conflicts.append("observation_date_after_as_of")
    if as_of_day is not None and realtime_day is not None and realtime_day > as_of_day:
        conflicts.append("realtime_start_after_as_of")
    if components.get("configured") is False and components.get("emitted") is False:
        conflicts.append("not_configured_and_not_emitted")
    return tuple(conflicts)


def classify_macro_series(
    *,
    slug: str,
    spec: Any = None,
    market_row: Optional[Mapping[str, Any]] = None,
    fred_row: Optional[Mapping[str, Any]] = None,
    hint: Optional[Mapping[str, Any]] = None,
    as_of_iso: str,
    configured: bool = True,
    emitted: bool = True,
) -> MacroLifecycleClassification:
    market = market_row or {}
    fred = fred_row or {}
    lifecycle_hint = hint or {}
    series_id = _resolve_series_id(spec, fred, lifecycle_hint)
    error = _safe_error(market, fred, lifecycle_hint)
    change_kind = _first_nonempty(lifecycle_hint.get("change_kind"))
    source_path = _first_nonempty(lifecycle_hint.get("source_path"))
    latest_observation_date = _first_nonempty(
        lifecycle_hint.get("last_observation_date"),
        lifecycle_hint.get("latest_observation_date"),
        fred.get("last_observation_date"),
        market.get("last_observation_date"),
    )
    realtime_start = _first_nonempty(
        lifecycle_hint.get("realtime_start"),
        lifecycle_hint.get("last_realtime_start"),
        fred.get("realtime_start"),
        market.get("realtime_start"),
    )
    realtime_end = _first_nonempty(
        lifecycle_hint.get("realtime_end"),
        lifecycle_hint.get("last_realtime_end"),
        fred.get("realtime_end"),
        market.get("realtime_end"),
    )
    has_value = _has_numeric_value(market, fred)
    vintage_metadata_present = bool(realtime_start or realtime_end)
    components: Dict[str, Any] = {
        "slug": slug,
        "series_id": series_id,
        "configured": bool(configured),
        "emitted": bool(emitted),
        "has_value": has_value,
        "error": error,
        "source_path": source_path,
        "change_kind": change_kind,
        "latest_observation_date": latest_observation_date,
        "realtime_start": realtime_start,
        "realtime_end": realtime_end,
        "vintage_metadata_present": vintage_metadata_present,
        "previous_observation_date": _first_nonempty(lifecycle_hint.get("previous_observation_date")),
        "previous_value_hash": _first_nonempty(lifecycle_hint.get("previous_value_hash")),
        "current_value_hash": _first_nonempty(lifecycle_hint.get("current_value_hash")),
    }

    conflicts = _detect_conflicts(components, as_of_day=_as_of_date(as_of_iso))
    reasons = list(conflicts)

    if conflicts:
        state = "DATA_CONFLICT"
        confidence = 0.35
    elif not emitted:
        state = "CONFIGURED_NOT_EMITTED"
        confidence = 0.9
        reasons.append("configured_series_absent_from_macro_payload")
    elif error and "FAIL/INVALID_SERIES" in error:
        state = "INVALID_SERIES"
        confidence = 0.95
        reasons.append("fred_marked_series_invalid")
    elif error and "using_cached_last_success" in error:
        state = "STALE_CACHE"
        confidence = 0.9
        reasons.append("fetch_degraded_but_recent_cache_reused")
    elif source_path == "stale_cache":
        state = "STALE_CACHE"
        confidence = 0.9
        reasons.append("stale_cache_path")
    elif error and not has_value:
        state = "SOURCE_DEGRADED"
        confidence = 0.9
        reasons.append("source_error_without_emitted_value")
    elif change_kind == "revision_observed":
        state = "REVISION_OBSERVED"
        confidence = 0.85
        reasons.append("same_observation_date_value_hash_changed")
    elif change_kind == "new_release_observed":
        state = "NEW_RELEASE_OBSERVED"
        confidence = 0.85
        reasons.append("latest_observation_date_advanced")
    else:
        state = "RELEASED_CURRENT"
        confidence = 0.9 if vintage_metadata_present else 0.75
        if vintage_metadata_present:
            reasons.append("fred_observation_realtime_fields_present")
        else:
            reasons.append("released_value_without_observation_realtime_fields")

    return MacroLifecycleClassification(
        state=state,
        confidence=confidence,
        components=components,
        reasons=tuple(reasons),
    )


def _state_distribution(rows: Iterable[Mapping[str, Any]]) -> Dict[str, int]:
    counts = {state: 0 for state in MACRO_LIFECYCLE_STATES}
    for row in rows:
        state = str(row.get("state") or "")
        if state not in counts:
            counts[state] = 0
        counts[state] += 1
    return {state: count for state, count in counts.items() if count}


def build_macro_lifecycle_snapshot(
    *,
    markets: Mapping[str, Any],
    fred: Mapping[str, Any],
    diagnostics: Mapping[str, Any],
    as_of_iso: str,
    configured_series: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    configured = configured_series or {}
    hints = diagnostics.get("lifecycle_hints", {}) if isinstance(diagnostics, Mapping) else {}
    if not isinstance(hints, Mapping):
        hints = {}

    slugs = sorted(set(configured.keys()) | set(markets.keys()) | set(fred.keys()) | set(hints.keys()))
    rows = []
    for slug in slugs:
        market_row = markets.get(slug, {}) if isinstance(markets.get(slug, {}), Mapping) else {}
        fred_row = fred.get(slug, {}) if isinstance(fred.get(slug, {}), Mapping) else {}
        hint = hints.get(slug, {}) if isinstance(hints.get(slug, {}), Mapping) else {}
        is_emitted = slug in markets or slug in fred
        classification = classify_macro_series(
            slug=str(slug),
            spec=configured.get(slug),
            market_row=market_row,
            fred_row=fred_row,
            hint=hint,
            as_of_iso=as_of_iso,
            configured=slug in configured,
            emitted=is_emitted,
        )
        rows.append(
            {
                "slug": str(slug),
                "series_id": classification.components.get("series_id"),
                "state": classification.state,
                "confidence": classification.confidence,
                "components": classification.components,
                "reasons": list(classification.reasons),
            }
        )

    distribution = _state_distribution(rows)
    vintage_present = sum(
        1 for row in rows if row.get("components", {}).get("vintage_metadata_present") is True
    )
    return {
        "schema_version": MACRO_LIFECYCLE_SCHEMA_VERSION,
        "as_of": as_of_iso,
        "row_count": len(rows),
        "state_distribution": distribution,
        "rows": rows,
        "diagnostics": {
            "configured_count": len(configured),
            "emitted_count": len(set(markets.keys()) | set(fred.keys())),
            "configured_not_emitted_count": distribution.get("CONFIGURED_NOT_EMITTED", 0),
            "revision_observed_count": distribution.get("REVISION_OBSERVED", 0),
            "new_release_observed_count": distribution.get("NEW_RELEASE_OBSERVED", 0),
            "stale_cache_count": distribution.get("STALE_CACHE", 0),
            "source_degraded_count": distribution.get("SOURCE_DEGRADED", 0),
            "invalid_series_count": distribution.get("INVALID_SERIES", 0),
            "vintage_metadata_present_count": vintage_present,
        },
        "capabilities": {
            "observation_realtime_fields": "observed" if vintage_present else "not_observed_in_payload",
            "series_vintagedates_endpoint": "not_integrated_v0",
            "superseded_value_archive": "hash_only_v0",
        },
    }
