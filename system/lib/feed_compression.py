"""
[PURPOSE]
- Teleology: Reduce LLM prompt payload for dense feed artifacts without destroying the raw artifact on disk.
- Mechanism: Trim stock/ETF feed envelopes down to tail movers plus optional focus tickers for reasoning-time injection.
- Non-goal: Rewrite stored artifacts, alter pricing math, or compress Oracle truth-side reads.

[INTERFACE]
- Exports: `compress_reasoning_feed_envelope(repo_root: Path, dep_id: str, envelope: Dict[str, Any]) -> Dict[str, Any]`
- Inputs: repository root, dependency id, and a full artifact envelope.
- Outputs: A prompt-optimized envelope copy or the original envelope when compression is not applicable.

[FLOW]
- Detect compressible tabular feeds (`global_stock_feed`, `global_etf_feed`).
- Rank rows by `Chg_5d`, keep top/bottom tails, optionally union focus tickers from ontology/config.
- Return a shallow-copied envelope with reduced rows plus compression metadata.
- When-needed: Open when reasoning-time prompt construction needs the canonical stock or ETF feed compression rule instead of scanning engine call sites and raw envelope examples.
- Escalates-to: system/core/engine.py; codex/refs/universe_ontology_report.json
- Navigation-group: kernel_lib

[DEPENDENCIES]
- Stock/ETF feed envelopes and optional codex/refs/universe_ontology_report.json focus hints.

[CONSTRAINTS]
- Compression is deterministic and stable by ticker symbol.
- Raw artifacts remain unchanged; callers receive a copied envelope.
- Missing fields or small datasets degrade to the unmodified envelope.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Dict, List, Sequence, Set

COMPRESSIBLE_FEED_IDS = {"global_stock_feed", "global_etf_feed"}
DEFAULT_TAIL_FRACTION = 0.20
DEFAULT_TAIL_CAP = 25
DEFAULT_MIN_ROWS = 40
COMPRESSION_VERSION = "omit_the_middle.v1"


def _load_focus_tickers(repo_root: Path) -> Set[str]:
    """
    [ACTION]
    - Teleology: Read optional focus ticker hints from the universe ontology report.
    - Mechanism: Accept a few explicit list-style keys and normalize them to uppercase symbols.
    - Guarantee: Returns a set of ticker symbols; unknown schemas degrade to empty.
    - Fails: None.
    """
    report_path = repo_root / "codex" / "refs" / "universe_ontology_report.json"
    if not report_path.exists():
        return set()
    try:
        payload = json.loads(report_path.read_text(encoding="utf-8"))
    except Exception:
        return set()
    if not isinstance(payload, dict):
        return set()

    focus_keys = ("focus_tickers", "must_track_tickers", "selected_tickers")
    tickers: Set[str] = set()
    for key in focus_keys:
        values = payload.get(key)
        if not isinstance(values, list):
            continue
        for raw in values:
            token = str(raw).upper().strip()
            if token:
                tickers.add(token)
    return tickers


def _to_float(value: Any) -> float | None:
    """
    [ACTION]
    - Teleology: Normalize metric cells into sortable numeric values.
    - Mechanism: Coerce to float and drop NaN.
    - Guarantee: Returns `None` when coercion fails.
    - Fails: None.
    """
    try:
        parsed = float(value)
    except Exception:
        return None
    if parsed != parsed:
        return None
    return parsed


def compress_reasoning_feed_envelope(repo_root: Path, dep_id: str, envelope: Dict[str, Any]) -> Dict[str, Any]:
    """
    [ACTION]
    - Teleology: Produce an LLM-friendly view of dense stock/ETF feeds while keeping the original artifact intact on disk.
    - Mechanism: Tail-trim by `Chg_5d`, cap row count, and annotate the returned envelope with compression metadata.
    - Guarantee: Returns a copied envelope when compression applies, otherwise returns the original envelope object.
    - Fails: None.
    - When-needed: Open when engine prompt assembly needs to know exactly when stock or ETF envelopes are tail-trimmed and what metadata is added to the compressed copy.
    - Escalates-to: system/core/engine.py; codex/refs/universe_ontology_report.json
    """
    if dep_id not in COMPRESSIBLE_FEED_IDS:
        return envelope
    if not isinstance(envelope, dict):
        return envelope

    data = envelope.get("data")
    if not isinstance(data, dict):
        return envelope

    columns = data.get("columns")
    rows = data.get("rows")
    if not isinstance(columns, list) or not isinstance(rows, list):
        return envelope
    if len(rows) < DEFAULT_MIN_ROWS:
        return envelope

    try:
        ticker_idx = columns.index("Ticker")
        chg_idx = columns.index("Chg_5d")
    except ValueError:
        return envelope

    structured: List[Dict[str, Any]] = []
    for raw_row in rows:
        if not isinstance(raw_row, list):
            continue
        row = list(raw_row[: len(columns)])
        if len(row) < len(columns):
            row.extend([None] * (len(columns) - len(row)))
        ticker = str(row[ticker_idx]).upper().strip() if ticker_idx < len(row) else ""
        if not ticker:
            continue
        structured.append(
            {
                "ticker": ticker,
                "chg_5d": _to_float(row[chg_idx] if chg_idx < len(row) else None),
                "row": row,
            }
        )

    valid_rows = [entry for entry in structured if entry["chg_5d"] is not None]
    if len(valid_rows) < DEFAULT_MIN_ROWS:
        return envelope

    tail_count = max(1, math.ceil(len(valid_rows) * DEFAULT_TAIL_FRACTION))
    tail_count = min(DEFAULT_TAIL_CAP, tail_count)

    top_rows = sorted(valid_rows, key=lambda item: (item["chg_5d"], item["ticker"]), reverse=True)[:tail_count]
    bottom_rows = sorted(valid_rows, key=lambda item: (item["chg_5d"], item["ticker"]))[:tail_count]

    focus_tickers = _load_focus_tickers(repo_root)
    focus_rows = [entry for entry in structured if entry["ticker"] in focus_tickers]
    focus_rows.sort(key=lambda item: item["ticker"])

    selected: List[Dict[str, Any]] = []
    seen: Set[str] = set()
    for bucket in (top_rows, bottom_rows, focus_rows):
        for entry in bucket:
            ticker = str(entry["ticker"])
            if ticker in seen:
                continue
            seen.add(ticker)
            selected.append(entry)

    if not selected or len(selected) >= len(rows):
        return envelope

    selected_rows = [entry["row"] for entry in selected]
    selected_tickers = [entry["ticker"] for entry in selected]
    focus_found = sorted({entry["ticker"] for entry in focus_rows})

    semantic_summary = {
        "version": COMPRESSION_VERSION,
        "mode": "omit_the_middle",
        "metric": "Chg_5d",
        "full_row_count": len(rows),
        "selected_row_count": len(selected_rows),
        "rows_omitted": len(rows) - len(selected_rows),
        "tail_count_per_side": tail_count,
        "tail_fraction": DEFAULT_TAIL_FRACTION,
        "selected_tickers": selected_tickers,
        "top_tickers": [entry["ticker"] for entry in top_rows],
        "bottom_tickers": [entry["ticker"] for entry in bottom_rows],
        "focus_tickers": focus_found,
        "focus_tickers_missing": sorted(focus_tickers - set(focus_found)),
    }

    metadata = envelope.get("metadata")
    meta_copy = dict(metadata) if isinstance(metadata, dict) else {}
    diagnostics = meta_copy.get("diagnostics")
    diagnostics_copy = dict(diagnostics) if isinstance(diagnostics, dict) else {}
    diagnostics_copy["prompt_input_rows"] = len(selected_rows)
    diagnostics_copy["prompt_rows_omitted"] = len(rows) - len(selected_rows)
    meta_copy["diagnostics"] = diagnostics_copy
    meta_copy["prompt_input_compression"] = "omit_the_middle"
    meta_copy["prompt_input_full_rows"] = len(rows)

    data_copy = dict(data)
    data_copy["rows"] = selected_rows
    data_copy["full_row_count"] = len(rows)
    data_copy["semantic_compression"] = semantic_summary

    return {
        **envelope,
        "metadata": meta_copy,
        "data": data_copy,
    }
