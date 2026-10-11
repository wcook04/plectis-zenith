"""
[PURPOSE]
- Teleology: Emit the Polymarket scanner's topic -> lens -> matrix payload without breaking downstream matrix consumers.
- Mechanism: Dedupe rows within each lens by slug, sort deterministically, and format matrix rows with the preserved core columns plus optional additive columns.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Tuple

from tools.polymarket.config import LENS_ORDER, OutputOptions
from tools.polymarket.models import NormalizedMarket


def _base_columns(output: OutputOptions) -> List[str]:
    columns = ["q", "o", "p", "c", "v", "s"]
    if output.include_slug:
        columns.append("slug")
    columns.extend(list(output.extra_columns))
    return columns


def build_legend(output: OutputOptions) -> Dict[str, str]:
    legend = {
        "q": "Question",
        "o": "Top Outcome",
        "p": f"Probability (0-1, {output.float_precision}dp)",
        "c": f"24h Change ({output.float_precision}dp)",
        "v": "Volume (24h)",
        "s": f"Conviction Score (|p-0.5|*2, {output.float_precision}dp)",
    }
    if output.include_slug:
        legend["slug"] = "Market slug / fallback identity"

    extra_legend = {
        "score": "Lens score after deterministic scoring and sorting",
        "topic": "Deterministic topic assignment",
        "status": "Normalized market status after resolved/zombie suppression",
        "liquidity": "Normalized liquidity value",
        "event": "Parent event title",
        "event_slug": "Parent event slug",
        "market_id": "Raw market id when available",
        "market_slug": "Raw market slug when available",
    }
    for column in output.extra_columns:
        legend[column] = extra_legend[column]
    return legend


def _row_sort_key(row: NormalizedMarket, lens: str) -> Tuple[Any, ...]:
    return (
        -row.scores[lens],
        -row.v,
        -abs(row.c),
        -row.s,
        row.q.casefold(),
        row.slug,
    )


def _choose_better_row(existing: NormalizedMarket, candidate: NormalizedMarket, lens: str) -> NormalizedMarket:
    return candidate if _row_sort_key(candidate, lens) < _row_sort_key(existing, lens) else existing


def _dedupe_rows(rows: Iterable[NormalizedMarket], lens: str) -> Tuple[List[NormalizedMarket], int]:
    best_by_slug: Dict[str, NormalizedMarket] = {}
    deduped = 0
    for row in rows:
        key = row.slug
        existing = best_by_slug.get(key)
        if existing is None:
            best_by_slug[key] = row
            continue
        best_by_slug[key] = _choose_better_row(existing, row, lens)
        deduped += 1
    return list(best_by_slug.values()), deduped


def _format_value(row: NormalizedMarket, lens: str, column: str, precision: int) -> Any:
    if column == "q":
        return row.q
    if column == "o":
        return row.o
    if column == "p":
        return round(row.p, precision)
    if column == "c":
        return round(row.c, precision)
    if column == "v":
        return int(row.v)
    if column == "s":
        return round(row.s, precision)
    if column == "slug":
        return row.slug
    if column == "score":
        return round(row.scores[lens], precision)
    if column == "topic":
        return row.topic
    if column == "status":
        return row.status
    if column == "liquidity":
        return int(row.liquidity)
    if column == "event":
        return row.event_title
    if column == "event_slug":
        return row.event_slug
    if column == "market_id":
        return row.market_id
    if column == "market_slug":
        return row.market_slug
    return None


def emit_matrix(
    markets: List[NormalizedMarket],
    topics: Iterable[str],
    output: OutputOptions,
    diagnostics: Dict[str, Any],
) -> Tuple[Dict[str, Any], int]:
    columns = _base_columns(output)
    matrix: Dict[str, Dict[str, List[NormalizedMarket]]] = {
        topic: {lens: [] for lens in LENS_ORDER}
        for topic in topics
    }

    for row in markets:
        if row.topic not in matrix:
            continue
        for lens in LENS_ORDER:
            if row.scores.get(lens, 0.0) > 0:
                matrix[row.topic][lens].append(row)

    final_data: Dict[str, Any] = {}
    total_rows = 0
    deduped_rows = 0

    for topic in topics:
        final_data[topic] = {}
        for lens in LENS_ORDER:
            lens_rows = matrix[topic][lens]
            if output.dedupe_slug_within_lens:
                lens_rows, deduped = _dedupe_rows(lens_rows, lens)
                deduped_rows += deduped

            lens_limit = output.top_n_by_lens.get(lens, output.top_n)
            sorted_rows = sorted(lens_rows, key=lambda row: _row_sort_key(row, lens))[:lens_limit]

            final_data[topic][lens] = {
                "columns": columns,
                "rows": [
                    [
                        _format_value(row, lens, column, output.float_precision)
                        for column in columns
                    ]
                    for row in sorted_rows
                ],
            }
            total_rows += len(sorted_rows)

    diagnostics["deduped_rows"] = deduped_rows
    diagnostics["emitted_rows"] = total_rows
    diagnostics["emitted_topics"] = len(final_data)
    return final_data, total_rows
