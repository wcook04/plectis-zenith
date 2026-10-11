"""
[PURPOSE]
- Teleology: Turn raw Gamma event payloads into bounded, deterministic market rows ready for scoring and matrix emission.
- Mechanism: Normalize event context, validate outcome payloads, suppress malformed/resolved/zombie rows, assign topics, and preserve slug identity.
"""

from __future__ import annotations

import json
import math
import re
from typing import Any, Dict, Iterable, List, Sequence, Tuple

from tools.polymarket.config import RuntimeOptions
from tools.polymarket.models import EventContext, NormalizedMarket
from tools.polymarket.score import calculate_lenses


_SLUG_PATTERN = re.compile(r"[^a-z0-9]+")


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return parsed if math.isfinite(parsed) else default


def _boolish(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"1", "true", "yes", "y", "on"}:
            return True
        if lowered in {"0", "false", "no", "n", "off"}:
            return False
    return None


def _text(*values: Any) -> str:
    parts: List[str] = []
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            parts.append(text)
    return " ".join(parts)


def _first_text(*values: Any) -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""


def _slugify(value: Any) -> str:
    text = str(value or "").strip().lower()
    if not text:
        return ""
    return _SLUG_PATTERN.sub("-", text).strip("-")


def _unique_preserve_order(values: Sequence[str]) -> Tuple[str, ...]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return tuple(ordered)


def _parse_listish(value: Any) -> List[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except Exception:
            return []
        return parsed if isinstance(parsed, list) else []
    return []


def _extract_tag_slugs(*tag_blocks: Any) -> Tuple[str, ...]:
    tags: list[str] = []
    for block in tag_blocks:
        if not isinstance(block, list):
            continue
        for tag in block:
            if isinstance(tag, dict):
                value = tag.get("slug") or tag.get("name") or tag.get("label")
            else:
                value = tag
            slug = _slugify(value)
            if slug:
                tags.append(slug)
    return _unique_preserve_order(tags)


def _normalize_event(event: Dict[str, Any]) -> EventContext:
    title = _first_text(event.get("title"), event.get("question"), event.get("name")) or "Untitled event"
    slug = str(event.get("slug") or "").strip() or _slugify(title)
    tags = _extract_tag_slugs(event.get("tags"), event.get("categories"))
    text_blob = _text(title, slug, " ".join(tags)).lower()
    return EventContext(title=title, slug=slug, tags=tags, text_blob=text_blob)


def _iter_markets(event: Dict[str, Any]) -> Iterable[Dict[str, Any]]:
    markets = event.get("markets")
    if isinstance(markets, list):
        for market in markets:
            if isinstance(market, dict):
                yield market
        return
    if any(key in event for key in ("question", "outcomes", "outcomePrices")):
        yield event


def _parse_outcome_pairs(market: Dict[str, Any]) -> List[Tuple[str, float]]:
    outcomes = _parse_listish(market.get("outcomes"))
    prices = _parse_listish(market.get("outcomePrices"))
    if not outcomes or not prices or len(outcomes) != len(prices):
        return []

    pairs: List[Tuple[str, float]] = []
    for outcome, price in zip(outcomes, prices):
        label = str(outcome or "").strip()
        probability = _safe_float(price, default=-1.0)
        if not label:
            continue
        if probability < 0.0 or probability > 1.0:
            continue
        pairs.append((label, probability))
    return pairs


def _topic_for_market(text_blob: str, tag_slugs: Sequence[str], options: RuntimeOptions) -> str:
    best_topic = "OTHER"
    best_score = 0
    for topic, keywords in options.topics.items():
        tag_hits = sum(1 for keyword in keywords for tag in tag_slugs if keyword in tag)
        text_hits = sum(1 for keyword in keywords if keyword in text_blob)
        score = (tag_hits * 4) + text_hits
        if score > best_score:
            best_topic = topic
            best_score = score
    return best_topic


def _normalized_status(
    event: Dict[str, Any],
    market: Dict[str, Any],
    options: RuntimeOptions,
) -> str:
    explicit_statuses = [
        str(value).strip().lower()
        for value in (
            market.get("status"),
            event.get("status"),
        )
        if str(value or "").strip()
    ]
    if any(token in {"resolved", "settled", "finalized"} for token in explicit_statuses):
        return "resolved"
    if any(token in {"closed", "archived", "expired", "ended"} for token in explicit_statuses):
        return "closed"

    for flag in (
        market.get("resolved"),
        market.get("isResolved"),
        event.get("resolved"),
        market.get("closed"),
        event.get("closed"),
        market.get("archived"),
        event.get("archived"),
    ):
        if _boolish(flag) is True:
            return "resolved"

    active_values = [
        _boolish(value)
        for value in (
            market.get("active"),
            event.get("active"),
            market.get("enableOrderBook"),
            market.get("acceptingOrders"),
        )
    ]
    if any(value is False for value in active_values if value is not None):
        return "resolved"

    return "active"


def _build_slug(event_ctx: EventContext, market: Dict[str, Any], question: str) -> str:
    for candidate in (
        market.get("slug"),
        market.get("market_slug"),
        market.get("clobTokenId"),
        market.get("id"),
    ):
        text = str(candidate or "").strip()
        if text:
            return text
    derived = _slugify(question) or _slugify(event_ctx.title) or event_ctx.slug
    return f"{event_ctx.slug}-{derived}".strip("-")


def normalize_events(
    events: Sequence[Dict[str, Any]],
    options: RuntimeOptions,
    diagnostics: Dict[str, Any],
) -> List[NormalizedMarket]:
    rows: List[NormalizedMarket] = []

    for event in events:
        event_ctx = _normalize_event(event)
        for market in _iter_markets(event):
            diagnostics["fetched_markets"] = int(diagnostics.get("fetched_markets", 0)) + 1

            market_tags = _extract_tag_slugs(market.get("tags"), market.get("categories"))
            all_tags = _unique_preserve_order((*event_ctx.tags, *market_tags))
            question = _first_text(market.get("question"), market.get("title"), event_ctx.title) or event_ctx.title
            text_blob = _text(event_ctx.text_blob, question, market.get("description"), " ".join(all_tags)).lower()

            kill_hit = any(keyword in tag for keyword in options.kill_list for tag in all_tags)
            safe_hit = any(keyword in text_blob for keyword in options.safety_keywords)
            if kill_hit and not safe_hit:
                diagnostics["noise_killed"] = int(diagnostics.get("noise_killed", 0)) + 1
                continue
            if kill_hit and safe_hit:
                diagnostics["rescued_safe"] = int(diagnostics.get("rescued_safe", 0)) + 1

            volume_24h = _safe_float(market.get("volume24hr"))
            volume_total = _safe_float(market.get("volume"))
            volume = volume_24h or volume_total
            if volume < options.filters.min_volume:
                diagnostics["dropped_volume"] = int(diagnostics.get("dropped_volume", 0)) + 1
                continue

            liquidity = _safe_float(
                market.get("liquidityClob", market.get("liquidityNum", market.get("liquidity")))
            )
            if liquidity < options.filters.min_liquidity:
                diagnostics["dropped_liquidity"] = int(diagnostics.get("dropped_liquidity", 0)) + 1
                continue

            outcome_pairs = _parse_outcome_pairs(market)
            if len(outcome_pairs) < 2:
                diagnostics["dropped_malformed"] = int(diagnostics.get("dropped_malformed", 0)) + 1
                continue

            best_outcome, best_probability = sorted(
                outcome_pairs,
                key=lambda pair: (-pair[1], pair[0].casefold()),
            )[0]

            change = _safe_float(
                market.get("oneDayPriceChange", market.get("priceChange24hr", market.get("price_change_24hr")))
            )
            status = _normalized_status(event, market, options)
            if options.filters.allowed_statuses and status not in options.filters.allowed_statuses:
                diagnostics["dropped_status"] = int(diagnostics.get("dropped_status", 0)) + 1
                continue

            zombie_cfg = options.tuning.get("zombie", {}) if isinstance(options.tuning.get("zombie"), dict) else {}
            zombie_floor = _safe_float(zombie_cfg.get("price_floor"), 0.95)
            zombie_velocity = _safe_float(zombie_cfg.get("max_velocity"), 0.015)
            is_zombie = status != "resolved" and best_probability >= zombie_floor and abs(change) <= zombie_velocity
            if options.filters.exclude_zombies and is_zombie:
                diagnostics["zombies_killed"] = int(diagnostics.get("zombies_killed", 0)) + 1
                diagnostics["dropped_zombies"] = int(diagnostics.get("dropped_zombies", 0)) + 1
                continue

            news_cfg = options.tuning.get("newsbreaker", {}) if isinstance(options.tuning.get("newsbreaker"), dict) else {}
            is_probability_resolved = best_probability >= _safe_float(
                news_cfg.get("resolved_ceiling"), 0.95
            ) or best_probability <= _safe_float(news_cfg.get("resolved_floor"), 0.05)
            if options.filters.exclude_resolved and (status == "resolved" or is_probability_resolved):
                diagnostics["dropped_resolved"] = int(diagnostics.get("dropped_resolved", 0)) + 1
                continue

            topic = _topic_for_market(text_blob, all_tags, options)
            if topic == "OTHER":
                diagnostics["dropped_topicless"] = int(diagnostics.get("dropped_topicless", 0)) + 1
                continue

            slug = _build_slug(event_ctx, market, question)
            row = NormalizedMarket(
                q=question,
                o=best_outcome,
                p=best_probability,
                c=change,
                v=volume,
                s=abs(best_probability - 0.5) * 2.0,
                slug=slug,
                topic=topic,
                status=status,
                liquidity=liquidity,
                event_title=event_ctx.title,
                event_slug=event_ctx.slug,
                market_id=str(market.get("id") or "").strip(),
                market_slug=str(market.get("slug") or market.get("market_slug") or slug).strip(),
            )
            row.scores = calculate_lenses(row, options.tuning)
            rows.append(row)

    diagnostics["normalized_markets"] = len(rows)
    return rows
