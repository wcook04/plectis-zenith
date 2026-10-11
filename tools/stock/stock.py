"""
[PURPOSE]
- Teleology: Provides a market-data "sense" mechanism that converts a hierarchical ticker universe into derived physics metrics (Volatility, Z-Scores) and a LOUD-compliant envelope.
- Mechanism: Hydrates config -> Fetches OHLCV via yfinance -> Filters by time anchor -> Computes rolling window metrics -> Serializes to JSON.
[INTERFACE]
- Reads: `config` dictionary (std_tool_config schema).
- Writes: Network requests to Yahoo Finance API; Warning logs for per-ticker failures.
- Exports: `StandardActor`, `run`.
[FLOW]
1. Ingest: unwraps config and determines snapshot period/precision.
2. Fetch: Iterates universe, calls `yfinance` for history.
3. Compute: Calculates annualized volatility, changes, and Z-scores via Pandas.
4. Envelope: Wraps results in Phase 2 metadata (run_id, as_of, legend).
[DEPENDENCIES]
- pypi.yfinance: ohlcv_fetch
- pypi.pandas: rolling_metrics
[CONSTRAINTS]
- Precision: Configurable float precision (default 4).
- Time Anchor: Respects `runtime.time_anchor` for historical simulation (filters future data).
- Reliability: Partial failures allowed (single ticker failure does not crash batch).
- When-needed: Open when a market-intelligence workflow needs the stock-feed lane that fetches OHLCV history, computes physics metrics, and emits the stock envelope.
- Escalates-to: tools/stock/stock.py::fetch_market_physics; tools/calculator/calculator.py::run
- Navigation-group: market_intelligence
"""

from __future__ import annotations

import datetime as _dt
import logging
import math
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, TypedDict

import pandas as pd
import yfinance as yf
from system.lib import feed_envelope
from system.lib.types import TOOL_METADATA_SCHEMA_VERSION
from tools.stock.lifecycle import (
    EQUITY_LIFECYCLE_SIDECAR_KEY,
    build_equity_lifecycle_snapshot,
)

logger = logging.getLogger("tools.stock")

TOOL_NAME = "stock"
DATA_SCHEMA_VERSION = "stock.1"

# --- LEGEND DEFINITION (Phase 2) ---
STOCK_LEGEND = {
    "Category": "Market segment or grouping",
    "Ticker": "Symbol identifier",
    "Identity": "Asset description / Proxy role",
    "Price": "Latest close price",
    "Vol_20d": "20-day annualized volatility (rolling std dev * sqrt(252))",
    "Chg_5d": "5-day percent change",
    "Chg_63d": "63-day (quarterly) percent change",
    "Z_Short": "Z-score of price vs 20-day moving average",
    "Z_Long": "Z-score of price vs 63-day moving average",
}

# --- MOLDS (TYPED CONTRACTS) ---


class InnerConfig(TypedDict, total=False):
    """
    [ROLE]
    - Teleology: Contract nucleus for tool-local tuning knobs (snapshot lookback + numeric precision).
    - Mechanism: Static schema surface (TypedDict) used for doc+type tooling; runtime accepts plain dict.
    - Ownership: Owned by the hydrated tool config (`config["config"]`).
    - Mutability: Treated as immutable after config unwrap (read-only semantics).
    - Concurrency: Safe to share across threads (no internal state).
    - Invariants: Keys are optional; omission implies defaults (`snapshot_period="2y"`, `precision=4`).
    - Non-goal: Does not validate/coerce user input (handled by `_period_from_config` / `_precision_from_config`).
    """

    snapshot_period: str
    precision: int


class EnvelopeMetadata(TypedDict, total=False):
    """
    [ROLE]
    - Teleology: Standardized header that makes tool results replayable, debuggable, and LOUD-compliant.
    - Mechanism: JSON-serializable metadata slab emitted by `run()` and consumed by external orchestrators.
    - Ownership: Owned by the tool runtime; produced per invocation and never mutated after return.
    - Mutability: Immutable-by-convention after envelope emission.
    - Concurrency: Safe to share across threads/processes (pure data container).
    - Invariants:
        - `tool` identifies the module ABI (`tools.stock`).
        - `status` is `"success"` or `"failure"`.
        - `as_of` is an ISO8601 anchor for time-travel determinism.
        - `legend` binds column meaning to prevent schema drift.
    - Couples: External callers rely on `run_id/as_of/diagnostics` for trace correlation.
    - Non-goal: Not a validation schema; missing keys are tolerated for backward compatibility.
    """

    tool: str
    status: str
    items_count: int
    timestamp: str  # Legacy
    as_of: str  # Phase 2
    run_id: Optional[str]  # Phase 2
    legend: Dict[str, str]  # Phase 2
    error: Optional[str]
    diagnostics: Dict[str, Any]


class Envelope(TypedDict, total=False):
    """
    [ROLE]
    - Teleology: Single transport shape for returning success/failure without leaking internal exceptions upstream.
    - Mechanism: `{metadata, data}` wrapper that stays JSON-safe across all tool executions.
    - Ownership: Owned by `run()`; emitted as the sole public return object.
    - Mutability: Immutable after construction (treat as write-once).
    - Concurrency: Safe to share (pure data).
    - Invariants:
        - `metadata` is an `EnvelopeMetadata` describing status + trace context.
        - `data` is payload content (table-like structure or empty sentinel).
    - Non-goal: Does not guarantee payload completeness; partial failures may be encoded as `None` rows.
    """

    metadata: EnvelopeMetadata
    data: Any


class StandardActor:
    """
    [ROLE]
    Object-shaped entrypoint for the Stock tool.

    - Ownership: Owns the hydrated configuration dictionary.
    - Mutability: Immutable `config` after initialization.
    - Concurrency: Thread-safe (read-only config).
    - Lifecycle: Initialized with config; `run()` delegates to module-level logic.
    - Failure Posture: Delegates exception handling to `run()`.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        # PHASE 2: CONFIG UNWRAP
        raw_config = config or {}
        self.config = raw_config.get("data", raw_config) if isinstance(raw_config, dict) else {}
        self.memory: Dict[str, Any] = {}

    def run(self, run_dir: Path = None) -> Dict[str, Any]:
        """
        [ACTION]
        Delegates execution to the module-level `run` function.

        - Preconditions: None.
        - Reads: `self.config`.
        - Guarantee: Returns the result of `run(config=self.config)`.
        - Fails: See module `run` specification.
        """
        return run(config=self.config, run_dir=run_dir)


class StockToolError(Exception):
    """
    [ROLE]
    - Teleology: Domain-scoped exception that marks fetch/market I/O failures as tool-native signals.
    - Mechanism: Raised by `_fetch_history()` to distinguish upstream network/data faults from compute faults.
    - Ownership: Owned by tool internals; intended for catching at tool boundaries (per-ticker or top-level).
    - Mutability: Immutable (exception message only).
    - Concurrency: Thread-safe (no shared state).
    - Failure Posture: Represents fatal failure for a single ticker fetch; caller may downgrade to warning + null-row.
    - Non-goal: Not a user-facing envelope; external boundary conversion happens in `fetch_market_physics()` / `run()`.
    """

    pass


# --- HELPERS: JSON-SAFE FLOATS ---


def _clean_float(val: Any, precision: Optional[int] = None) -> Optional[float]:
    """
    [ACTION]
    Sanitizes numerical input into a JSON-safe float.

    - Preconditions: `val` is numeric or coercible to float.
    - Transformation: Rounds to `precision` if provided.
    - Fails: Returns `None` if `val` is NaN, Infinite, or non-coercible.
    - Orders: None.
    """
    try:
        if val is None:
            return None
        f = float(val)
        if math.isnan(f) or math.isinf(f):
            return None
        if precision is not None:
            f = round(f, precision)
        return f
    except Exception:
        return None


def _utc_iso_now() -> str:
    """
    [ACTION]
    Returns current UTC timestamp in ISO 8601 format.

    - Guarantee: Returns string format `YYYY-MM-DDTHH:MM:SS+00:00`.
    - Fails: None.
    """
    return _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat()


def _parse_anchor_iso(anchor: str) -> Optional[_dt.datetime]:
    """
    [ACTION]
    Parses an ISO 8601 string into a timezone-aware UTC datetime.

    - Preconditions: `anchor` is a valid ISO string.
    - Transformation: Normalizes "Z" to "+00:00".
    - Fails: Returns `None` on parsing error.
    """
    try:
        a = anchor.replace("Z", "+00:00")
        dt = _dt.datetime.fromisoformat(a)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=_dt.timezone.utc)
        return dt.astimezone(_dt.timezone.utc)
    except Exception:
        return None


def _filter_future_rows(df: pd.DataFrame, anchor_utc: _dt.datetime) -> pd.DataFrame:
    """
    [ACTION]
    Filters dataframe rows that occur after the anchor time (Time Travel).

    - Preconditions: `df` has a DatetimeIndex. `anchor_utc` is timezone-aware.
    - Transformation: Drops rows where index > anchor_utc.
    - Guarantee: Returns dataframe subset or original if filtering fails.
    - Fails: Returns original `df` on index errors.
    """
    if df is None or df.empty or df.index is None:
        return df

    try:
        idx = df.index
        if idx.tz is not None:
            idx_utc = idx.tz_convert(_dt.timezone.utc)
        else:
            idx_utc = idx.tz_localize(_dt.timezone.utc)

        return df[idx_utc <= anchor_utc]
    except Exception:
        return df


def _as_list(x: Any) -> List[str]:
    """
    [ACTION]
    Normalizes input into a list of strings.

    - Guarantee: Always returns a list.
    - Fails: None.
    """
    if x is None:
        return []
    if isinstance(x, (list, tuple, set)):
        return [str(i) for i in x]
    return [str(x)]


def _universe_from_config(cfg: Dict[str, Any]) -> List[Tuple[str, str, str]]:
    """
    [ACTION]
    Flattens the configuration universe into a list of tuples.

    - Reads: `cfg["universe"]`.
    - Transformation: Walks nested dicts/lists -> `(category, ticker, identity)`.
    - Guarantee: Returns list of 3-tuples.
    - Fails: Returns empty list if universe missing.
    """
    uni = cfg.get("universe")
    if uni is None:
        return []
    rows: List[Tuple[str, str, str]] = []

    if isinstance(uni, dict):
        for cat, bucket in uni.items():
            category = str(cat)
            if isinstance(bucket, dict):
                for ident, tkr in bucket.items():
                    rows.append((category, str(ident), str(tkr)))
            elif isinstance(bucket, (list, tuple, set)):
                for tkr in bucket:
                    rows.append((category, str(tkr), str(tkr)))
            else:
                rows.append((category, str(bucket), str(bucket)))
        return rows

    for tkr in _as_list(uni):
        if tkr:
            rows.append(("universe", tkr, tkr))
    return rows


def _period_from_config(cfg: Dict[str, Any]) -> str:
    """
    [ACTION]
    Extracts snapshot period from config.

    - Reads: `cfg["config"]["snapshot_period"]`.
    - When-needed: Open when `snapshot_period` routing needs the authoritative stock-config seam that reads the lookback window from hydrated tool config and applies the default.
    - Escalates-to: tools/stock/stock.py::InnerConfig; tools/stock/stock.py::run
    - Guarantee: Returns string (default "2y").
    """
    inner = cfg.get("config") or {}
    if isinstance(inner, dict):
        p = inner.get("snapshot_period")
        if isinstance(p, str) and p.strip():
            return p.strip()
    return "2y"


def _precision_from_config(cfg: Dict[str, Any]) -> int:
    """
    [ACTION]
    Extracts precision from config.

    - Reads: `cfg["config"]["precision"]`.
    - Guarantee: Returns int (default 4).
    """
    inner = cfg.get("config") or {}
    if isinstance(inner, dict):
        val = inner.get("precision")
        if val is not None:
            try:
                return int(val)
            except (ValueError, TypeError):
                pass
    return 4


def _fetch_history(ticker: str, period: str) -> pd.DataFrame:
    """
    [ACTION]
    Fetches market data from yfinance.

    - Reads: Network (Yahoo Finance).
    - Guarantee: Returns Pandas DataFrame.
    - Fails: Raises `StockToolError` on fetch failure.
    """
    try:
        obj = yf.Ticker(ticker)
        return obj.history(period=period, interval="1d", auto_adjust=False)
    except Exception as e:
        raise StockToolError(f"Failed to fetch history for {ticker}: {e}") from e


# --- BATCH FETCH (Tier B: cadence unblocker) ---

_BATCH_DOWNLOAD_MAX_RETRIES: int = 2
_BATCH_DOWNLOAD_BACKOFF_S: float = 0.8


def _batch_download_history(
    tickers: List[str],
    period: str,
    *,
    max_retries: int = _BATCH_DOWNLOAD_MAX_RETRIES,
    backoff_s: float = _BATCH_DOWNLOAD_BACKOFF_S,
) -> Optional[pd.DataFrame]:
    """Fetch multiple tickers in one `yf.download` call with bounded retry.

    Returns a DataFrame (MultiIndex columns for >1 ticker; single-level for 1 ticker)
    or None if yfinance returns empty / every retry attempt raises.

    Retry/backoff is bounded to transient network exceptions; deterministic compute
    downstream is never retried. Caller is expected to fall back to per-ticker
    `_fetch_history` for any ticker missing from the returned batch.
    """
    if not tickers:
        return None
    last_exc: Optional[BaseException] = None
    for attempt in range(max_retries + 1):
        try:
            df = yf.download(
                tickers=list(tickers),
                period=period,
                progress=False,
                threads=True,
                group_by="ticker",
                interval="1d",
                auto_adjust=False,
            )
            if df is None or getattr(df, "empty", True):
                return None
            return df
        except Exception as exc:
            last_exc = exc
            if attempt >= max_retries:
                break
            logger.warning(
                "yf.download attempt %d/%d failed (%s); retrying in %.1fs",
                attempt + 1,
                max_retries + 1,
                type(exc).__name__,
                backoff_s * (2 ** attempt),
            )
            time.sleep(backoff_s * (2 ** attempt))
    if last_exc is not None:
        raise StockToolError(
            f"Batch download failed after {max_retries + 1} attempts: {type(last_exc).__name__}"
        ) from last_exc
    return None


def _close_series_from_batch(
    batch_df: Optional[pd.DataFrame],
    ticker: str,
) -> Optional[pd.Series]:
    """Extract a ticker's Close series from a `yf.download` batch frame.

    Handles both the multi-ticker MultiIndex shape (`(ticker, OHLCV)`) and the
    single-ticker flat shape (`OHLCV` only). Returns None if the ticker is absent,
    the Close column is missing, or the series is all-NaN.
    """
    if batch_df is None or getattr(batch_df, "empty", True):
        return None
    try:
        cols = batch_df.columns
        if isinstance(cols, pd.MultiIndex):
            level_zero = cols.get_level_values(0)
            if ticker not in level_zero:
                return None
            per_ticker = batch_df[ticker]
            if not hasattr(per_ticker, "columns"):
                return None
            if "Close" not in per_ticker.columns:
                return None
            series = per_ticker["Close"]
        else:
            if "Close" not in cols:
                return None
            series = batch_df["Close"]
        if series is None:
            return None
        series = series.dropna()
        if series.empty:
            return None
        return series
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("close-extraction failed for %s: %s", ticker, type(exc).__name__)
        return None


def _annualized_volatility(close: pd.Series, window: int, precision: int = 6) -> Optional[float]:
    """
    [ACTION]
    Computes annualized volatility.

    - Transformation: `std(pct_change) * sqrt(252)`.
    - Fails: Returns `None` if insufficient data or NaN results.
    """
    try:
        if close is None or len(close) < window + 1:
            return None
        ret = close.pct_change()
        vol = ret.rolling(window).std(ddof=0)
        latest = vol.iloc[-1]
        if pd.isna(latest):
            return None
        return _clean_float(float(latest) * math.sqrt(252.0), precision=precision)
    except Exception:
        return None


def _pct_change(close: pd.Series, days: int, precision: int = 4) -> Optional[float]:
    """
    [ACTION]
    Computes percent change over `days`.

    - Transformation: `(current / past) - 1`.
    - Fails: Returns `None` if insufficient data, zero-division, or NaN.
    """
    try:
        if close is None or len(close) < days + 1:
            return None
        a, b = close.iloc[-1], close.iloc[-(days + 1)]
        if pd.isna(a) or pd.isna(b) or b == 0:
            return None
        return _clean_float((float(a) / float(b) - 1.0) * 100.0, precision=precision)
    except Exception:
        return None


def _z_score(close: pd.Series, window: int, precision: int = 4) -> Optional[float]:
    """
    [ACTION]
    Computes Z-Score against moving average.

    - Transformation: `(price - mean) / std`.
    - Fails: Returns `None` if insufficient data or std is 0.
    """
    try:
        if close is None or len(close) < window:
            return None
        w = close.iloc[-window:]
        mean, std, last = w.mean(), w.std(ddof=0), close.iloc[-1]
        if pd.isna(std) or std == 0 or pd.isna(last) or pd.isna(mean):
            return None
        z = (float(last) - float(mean)) / float(std)
        return _clean_float(z, precision=precision)
    except Exception:
        return None


def fetch_market_physics(
    config: Dict[str, Any],
    diagnostics: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    [ACTION]
    - Teleology: Produce the stock table that turns a configured ticker universe into comparable market-physics rows.
    - Mechanism: Expand the configured universe, fetch each ticker's history, apply the optional time anchor, compute price, volatility, percent-change, and z-score metrics, and emit a dense table.
    - Preconditions: `config` contains universe definition.
    - Reads: `config` for universe, period, precision, and time_anchor.
    - Transformation: Iterates universe -> fetch -> compute metrics -> row generation.
    - Guarantee: Returns dictionary with "columns" and "rows".
    - Fails: Catches individual ticker errors, logging warning and appending `None` filled row (Partial Failure support).
    - Orders: Rows follow the iteration order of `_universe_from_config`.
    - When-needed: Open when a caller needs the exact per-ticker fetch-and-compute loop or the null-row fallback used for partial stock failures.
    - Escalates-to: tools/stock/stock.py::run; tools/calculator/calculator.py::run
    - Navigation-group: market_intelligence

    Observability: when an optional `diagnostics` dict is supplied, this function
    records per-ticker fetch outcomes (fetch_success_count / fetch_failure_count /
    fetch_success_rate) and appends structured `partial_failures` entries plus
    plain-string warnings so downstream readiness surfaces (run_tools6, Oracle
    feed_health) see an explicit accounting of silent per-ticker nulls. The
    returned data shape is unchanged either way.
    """
    universe_rows = _universe_from_config(config)
    if not universe_rows:
        return {"columns": [], "rows": []}

    period = _period_from_config(config)
    precision = _precision_from_config(config)

    runtime = config.get("runtime") or {}
    anchor_str = runtime.get("time_anchor") if isinstance(runtime, dict) else None
    anchor_utc = _parse_anchor_iso(anchor_str) if isinstance(anchor_str, str) else None

    # --- Tier B: batch download (one yf.download for all unique tickers) ---
    unique_tickers: List[str] = []
    _seen = set()
    for _cat, ticker, _ident in universe_rows:
        if ticker not in _seen:
            _seen.add(ticker)
            unique_tickers.append(ticker)

    batch_df: Optional[pd.DataFrame] = None
    batch_attempted = False
    batch_ok = False
    if unique_tickers:
        batch_attempted = True
        try:
            batch_df = _batch_download_history(unique_tickers, period)
            batch_ok = batch_df is not None
        except Exception as exc:
            logger.warning(
                "Stock batch download failed (%s); falling through to per-ticker path",
                type(exc).__name__,
            )
            if diagnostics is not None:
                feed_envelope.append_warning(
                    diagnostics,
                    f"stock: batch_download_failed: {type(exc).__name__}",
                )
    if diagnostics is not None:
        diagnostics["batch_download_attempted"] = batch_attempted
        diagnostics["batch_download_ok"] = batch_ok
        diagnostics["batch_ticker_count"] = len(unique_tickers)
        diagnostics["price_observations"] = {}

    rows: List[List[Any]] = []

    for category, ticker, identity in universe_rows:
        try:
            close: Optional[pd.Series] = _close_series_from_batch(batch_df, ticker)
            if close is None:
                # Per-ticker fallback preserves the original single-ticker path semantics.
                df = _fetch_history(ticker, period=period)
                if anchor_utc is not None:
                    df = _filter_future_rows(df, anchor_utc)
                if df is None or df.empty or "Close" not in df.columns:
                    rows.append([category, ticker, identity, None, None, None, None, None, None])
                    _record_empty_ticker(diagnostics, ticker, category, reason="no_close_column")
                    continue
                close = df["Close"].dropna()
            else:
                # Batch series is already a Close series; apply anchor filter in-place.
                if anchor_utc is not None:
                    close = _filter_future_series(close, anchor_utc)

            if close is None or close.empty:
                rows.append([category, ticker, identity, None, None, None, None, None, None])
                _record_empty_ticker(diagnostics, ticker, category, reason="empty_close_series")
                continue

            price = _clean_float(close.iloc[-1], precision=precision)
            vol_20 = _annualized_volatility(close, 20, precision=precision)
            chg_5 = _pct_change(close, 5, precision=precision)
            chg_63 = _pct_change(close, 63, precision=precision)
            z_short = _z_score(close, 20, precision=precision)
            z_long = _z_score(close, 63, precision=precision)

            rows.append([category, ticker, identity, price, vol_20, chg_5, chg_63, z_short, z_long])
            if diagnostics is not None:
                if price is not None:
                    diagnostics["price_observations"][ticker] = {
                        "session_date": pd.Timestamp(close.index[-1]).date().isoformat(),
                        "interval": "1d",
                        "auto_adjust": False,
                        "provider": "yahoo_finance",
                    }
                feed_envelope.record_fetch_outcome(diagnostics, ok=True)

        except Exception as e:
            logger.warning("Stock compute failed for %s: %s", ticker, type(e).__name__)
            rows.append([category, ticker, identity, None, None, None, None, None, None])
            _record_ticker_exception(diagnostics, ticker, category, exc=e)

    return {
        "columns": ["Category", "Ticker", "Identity", "Price", "Vol_20d", "Chg_5d", "Chg_63d", "Z_Short", "Z_Long"],
        "rows": rows,
    }


def _filter_future_series(series: pd.Series, anchor_utc: _dt.datetime) -> pd.Series:
    """Series-level twin of `_filter_future_rows` for batch-extracted Close series."""
    if series is None or series.empty or series.index is None:
        return series
    try:
        idx = series.index
        if idx.tz is not None:
            idx_utc = idx.tz_convert(_dt.timezone.utc)
        else:
            idx_utc = idx.tz_localize(_dt.timezone.utc)
        return series[idx_utc <= anchor_utc]
    except Exception:
        return series


def _record_empty_ticker(
    diagnostics: Optional[Dict[str, Any]],
    ticker: str,
    category: str,
    *,
    reason: str,
) -> None:
    if diagnostics is None:
        return
    feed_envelope.record_fetch_outcome(diagnostics, ok=False)
    feed_envelope.append_partial_failure(
        diagnostics,
        feed_envelope.warning_event(
            code=reason,
            lane="stock",
            ticker=ticker,
            message=f"{ticker} returned no usable Close series ({reason})",
            extra={"category": category},
        ),
    )
    feed_envelope.append_warning(
        diagnostics,
        f"stock: {ticker} empty ({reason})",
    )


def _record_ticker_exception(
    diagnostics: Optional[Dict[str, Any]],
    ticker: str,
    category: str,
    *,
    exc: BaseException,
) -> None:
    if diagnostics is None:
        return
    feed_envelope.record_fetch_outcome(diagnostics, ok=False)
    feed_envelope.append_partial_failure(
        diagnostics,
        feed_envelope.warning_event(
            code="ticker_exception",
            lane="stock",
            exc=exc,
            ticker=ticker,
            extra={"category": category},
        ),
    )
    feed_envelope.append_warning(
        diagnostics,
        f"stock: {ticker} failed: {type(exc).__name__}",
    )


def run(config: Dict[str, Any] = None, run_dir: Path = None) -> Dict[str, Any]:
    """
    [ACTION]
    - Teleology: Expose the hardened top-level entrypoint for the stock market-physics lane.
    - Mechanism: Unwraps config, derives run context, delegates the table build to `fetch_market_physics()`, and wraps success or failure in the standard envelope.
    - Reads: `config` dictionary.
    - Guarantee: Always returns a JSON-serializable `Envelope`.
    - Schema:
        ```json
        {
          "metadata": { "tool": "tools.stock", "status": "success|failure", ... },
          "data": { "columns": [...], "rows": [...] }
        }
        ```
    - Fails: Catches top-level exceptions and returns a failure `Envelope` with error details.
    - When-needed: Open when orchestration needs the stock tool's public entrypoint, envelope schema, or top-level failure posture.
    - Escalates-to: tools/stock/stock.py::fetch_market_physics; tools/calculator/calculator.py::run
    - Navigation-group: market_intelligence
    """
    t0 = time.time()

    # 1. PHASE 2: CONFIG UNWRAP
    raw_config = config or {}
    config_unwrapped = raw_config.get("data", raw_config) if isinstance(raw_config, dict) else {}

    # 2. Derive Context (Run ID / As Of)
    runtime = config_unwrapped.get("runtime", {}) if isinstance(config_unwrapped, dict) else {}
    anchor_str = runtime.get("time_anchor") if isinstance(runtime, dict) else None
    now = feed_envelope.utc_now()
    as_of = anchor_str if isinstance(anchor_str, str) and anchor_str else now.iso
    run_id = feed_envelope.resolve_run_id(runtime if isinstance(runtime, dict) else None, run_dir)

    period = _period_from_config(config_unwrapped)
    precision = _precision_from_config(config_unwrapped)

    try:
        # 3. Execution — seed diagnostics so per-ticker failures surface
        diagnostics = feed_envelope.new_diagnostics(
            elapsed_s=0.0,
            period=period,
            precision=precision,
            ticker_count=0,
            anchor_used=bool(anchor_str),
        )
        table = fetch_market_physics(config_unwrapped, diagnostics=diagnostics)
        configured_universe = _universe_from_config(config_unwrapped)
        row_count = len(table.get("rows", []))

        ok = bool(table.get("columns")) and (row_count > 0 or not configured_universe)
        status = "success" if ok else "failure"
        diagnostics["elapsed_s"] = round(time.time() - t0, 4)
        diagnostics["ticker_count"] = row_count
        diagnostics["input_rows"] = row_count
        diagnostics["output_rows"] = row_count
        diagnostics["dropped_rows"] = 0
        if status != "success":
            feed_envelope.append_warning(diagnostics, "No data returned")

        # 4. PHASE 2: METADATA & LEGEND — stock legacy: `timestamp` = as_of (anchor-aware)
        meta = feed_envelope.build_metadata(
            tool=TOOL_NAME,
            status=status,
            now=now,
            run_id=run_id,
            as_of=as_of,
            items_count=row_count,
            diagnostics=diagnostics,
            data_schema_version=DATA_SCHEMA_VERSION,
            timestamp=as_of,
            legend=STOCK_LEGEND,
            always_include_error=True,
            error=None if status == "success" else "No data returned",
            extra={
                "sidecars": {
                    EQUITY_LIFECYCLE_SIDECAR_KEY: build_equity_lifecycle_snapshot(
                        table=table,
                        configured_universe=configured_universe,
                        diagnostics=diagnostics,
                        as_of_iso=as_of,
                        config=config_unwrapped,
                    ),
                },
            },
        )
        return {"metadata": meta, "data": table}

    except Exception as e:
        # Stock's original failure path deliberately falls back to wall-clock for `timestamp`
        # and `as_of`; preserve that ABI.
        fail_diag = feed_envelope.new_diagnostics(exception=type(e).__name__)
        feed_envelope.append_warning(fail_diag, str(e))
        meta = feed_envelope.build_metadata(
            tool=TOOL_NAME,
            status="failure",
            now=now,
            run_id=run_id,
            as_of=now.iso,
            items_count=0,
            diagnostics=fail_diag,
            data_schema_version=DATA_SCHEMA_VERSION,
            timestamp=now.iso,
            legend=STOCK_LEGEND,
            always_include_error=True,
            error=str(e),
        )
        return {"metadata": meta, "data": {"columns": [], "rows": []}}
