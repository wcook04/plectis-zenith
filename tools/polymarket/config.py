"""
[PURPOSE]
- Teleology: Hydrate the Polymarket scanner's bounded runtime options from the nested tool config surface.
- Mechanism: Unwrap config envelopes, apply optional defaults for pagination, filters, and extra output columns, and expose one typed options packet to the runtime seams.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Tuple

from tools.polymarket.clob_snapshot import ClobOptions, hydrate_clob_options
from tools.polymarket.lifecycle import LifecycleOptions, hydrate_lifecycle_options


LENS_ORDER: Tuple[str, ...] = ("HOT SEAT", "NEWSBREAKER", "GOD MODE", "SCOUT")
SUPPORTED_EXTRA_COLUMNS: Tuple[str, ...] = (
    "score",
    "topic",
    "status",
    "liquidity",
    "event",
    "event_slug",
    "market_id",
    "market_slug",
)


def unwrap_config(config: Dict[str, Any]) -> Dict[str, Any]:
    current: Any = config
    while isinstance(current, dict) and current.get("type") == "config" and "data" in current:
        current = current["data"]
    return current if isinstance(current, dict) else {}


def _as_int(value: Any, default: int, *, minimum: int | None = None) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    if minimum is not None:
        return max(minimum, parsed)
    return parsed


def _as_float(value: Any, default: float, *, minimum: float | None = None) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        parsed = default
    if minimum is not None:
        return max(minimum, parsed)
    return parsed


def _as_bool(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"1", "true", "yes", "y", "on"}:
            return True
        if lowered in {"0", "false", "no", "n", "off"}:
            return False
    if isinstance(value, (int, float)):
        return bool(value)
    return default


def _lowered_strings(values: Any) -> Tuple[str, ...]:
    if not isinstance(values, (list, tuple)):
        return ()
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        text = str(value).strip().lower()
        if not text or text in seen:
            continue
        seen.add(text)
        ordered.append(text)
    return tuple(ordered)


def _normalized_topics(values: Any) -> Dict[str, Tuple[str, ...]]:
    if not isinstance(values, dict):
        return {}
    topics: Dict[str, Tuple[str, ...]] = {}
    for topic, keywords in values.items():
        topic_name = str(topic).strip().upper()
        if not topic_name:
            continue
        topics[topic_name] = _lowered_strings(keywords)
    return topics


def _extra_columns(values: Any) -> Tuple[str, ...]:
    requested = _lowered_strings(values)
    seen: set[str] = set()
    ordered: list[str] = []
    for column in requested:
        if column not in SUPPORTED_EXTRA_COLUMNS or column in seen:
            continue
        seen.add(column)
        ordered.append(column)
    return tuple(ordered)


@dataclass(frozen=True)
class ApiOptions:
    base_url: str
    limit: int
    timeout: float
    pagination_cap: int


@dataclass(frozen=True)
class OutputOptions:
    top_n: int
    top_n_by_lens: Dict[str, int]
    dedupe_slug_within_lens: bool
    include_slug: bool
    float_precision: int
    extra_columns: Tuple[str, ...]


@dataclass(frozen=True)
class FilterOptions:
    min_volume: float
    min_liquidity: float
    exclude_resolved: bool
    exclude_zombies: bool
    allowed_statuses: Tuple[str, ...]


@dataclass(frozen=True)
class RuntimeOptions:
    api: ApiOptions
    output: OutputOptions
    filters: FilterOptions
    tuning: Dict[str, Any]
    topics: Dict[str, Tuple[str, ...]]
    kill_list: Tuple[str, ...]
    safety_keywords: Tuple[str, ...]
    runtime: Dict[str, Any]
    clob: ClobOptions
    lifecycle: LifecycleOptions


def hydrate_runtime_options(config: Dict[str, Any]) -> RuntimeOptions:
    raw = unwrap_config(config)

    api_cfg = raw.get("api", {}) if isinstance(raw.get("api"), dict) else {}
    output_cfg = raw.get("output", {}) if isinstance(raw.get("output"), dict) else {}
    routing_cfg = raw.get("routing", {}) if isinstance(raw.get("routing"), dict) else {}
    filter_cfg = raw.get("filters", {}) if isinstance(raw.get("filters"), dict) else {}
    tuning_cfg = raw.get("tuning", {}) if isinstance(raw.get("tuning"), dict) else {}
    runtime_cfg = raw.get("runtime", {}) if isinstance(raw.get("runtime"), dict) else {}

    api = ApiOptions(
        base_url=str(api_cfg.get("base_url", "")).strip(),
        limit=_as_int(api_cfg.get("limit"), 1000, minimum=1),
        timeout=_as_float(api_cfg.get("timeout"), 60.0, minimum=1.0),
        pagination_cap=_as_int(api_cfg.get("pagination_cap"), 1, minimum=1),
    )

    top_n = _as_int(output_cfg.get("top_n"), 22, minimum=1)
    top_n_by_lens: Dict[str, int] = {}
    raw_top_n_by_lens = output_cfg.get("top_n_by_lens")
    if isinstance(raw_top_n_by_lens, dict):
        for lens_name, limit in raw_top_n_by_lens.items():
            normalized_lens = str(lens_name).strip().upper()
            if normalized_lens not in LENS_ORDER:
                continue
            top_n_by_lens[normalized_lens] = _as_int(limit, top_n, minimum=1)

    output = OutputOptions(
        top_n=top_n,
        top_n_by_lens=top_n_by_lens,
        dedupe_slug_within_lens=_as_bool(output_cfg.get("dedupe_slug_within_lens"), True),
        include_slug=_as_bool(output_cfg.get("include_slug"), True),
        float_precision=_as_int(output_cfg.get("float_precision"), 3, minimum=0),
        extra_columns=_extra_columns(output_cfg.get("extra_columns")),
    )

    filters = FilterOptions(
        min_volume=_as_float(filter_cfg.get("min_volume"), 500.0, minimum=0.0),
        min_liquidity=_as_float(filter_cfg.get("min_liquidity"), 0.0, minimum=0.0),
        exclude_resolved=_as_bool(filter_cfg.get("exclude_resolved"), True),
        exclude_zombies=_as_bool(filter_cfg.get("exclude_zombies"), True),
        allowed_statuses=_lowered_strings(filter_cfg.get("allowed_statuses")),
    )

    return RuntimeOptions(
        api=api,
        output=output,
        filters=filters,
        tuning=tuning_cfg,
        topics=_normalized_topics(routing_cfg.get("topics")),
        kill_list=_lowered_strings(routing_cfg.get("kill_list")),
        safety_keywords=_lowered_strings(routing_cfg.get("safety_keywords")),
        runtime=runtime_cfg,
        clob=hydrate_clob_options(raw),
        lifecycle=hydrate_lifecycle_options(raw),
    )
