"""
[PURPOSE]
- Teleology: Provide a FRED-only macro snapshot with bounded network behavior.
- Mechanism: Poll/cache/update flow over FRED series with rate-limit handling,
  then emit a compact matrix artifact for downstream consumers.

[INTERFACE]
- Inputs: `config` (dict), `run_dir` (optional Path-like).
- Outputs: Macro artifact envelope (`metadata` + `data`).
- Exports: `run`, `StandardActor`.

[FLOW]
1. Ingest: hydrate config, runtime anchor, and FRED policy knobs.
2. Acquire: for each FRED series, reuse cache when valid; otherwise poll and fetch.
3. Compute: derive per-series metrics (`pct_change`, `z_score`, `risk_d2`).
4. Emit: serialize to matrix rows and metadata diagnostics.

[DEPENDENCIES]
- pypi.requests: FRED API HTTP client.
- env.FRED_API_KEY: authentication.

[CONSTRAINTS]
- FRED-only execution path (no yfinance branch).
- Soft-fail posture: partial outputs allowed; failures are row-level.
- Rate-limit control: paced requests + 429 backoff + circuit breaker.
- Cache contract: `state/cache/fred` stores per-series snapshots + index.
- When-needed: Open when a market-intelligence workflow needs the FRED-backed macro lane, including cache reuse, rate-limit behavior, and the emitted macro artifact envelope.
- Escalates-to: tools/calculator/calculator.py::run; tools/oracle/subject_index.py::run
- Navigation-group: market_intelligence
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import random
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Literal, Mapping, Optional, Tuple

from system.lib import feed_envelope
from system.lib.types import TOOL_METADATA_SCHEMA_VERSION
from tools.macro.lifecycle import (
    MACRO_LIFECYCLE_SIDECAR_KEY,
    build_macro_lifecycle_snapshot,
)

try:
    import requests
except Exception:  # pragma: no cover - optional at runtime
    requests = None  # type: ignore[assignment]


TOOL_NAME = "macro"
DATA_SCHEMA_VERSION = "macro.2"

FRED_OBSERVATIONS_URL = "https://api.stlouisfed.org/fred/series/observations"
CACHE_ROOT_REL = Path("state/cache/fred")
CACHE_INDEX_NAME = "index.json"
CACHE_SERIES_DIR = "series"

STATUS_PASS = "PASS"
STATUS_WARN = "WARN"
STATUS_FAIL = "FAIL"

WARN_RATE_LIMIT = "WARN/RATE_LIMIT"
WARN_NETWORK = "WARN/NETWORK_ERROR"
FAIL_INVALID_SERIES = "FAIL/INVALID_SERIES"


MACRO_LEGEND = {
    "columns": [
        "ticker",
        "Proxy",
        "n",
        "start",
        "end",
        "recent_change",
        "recent_change_label",
        "display_change",
        "pct_change",
        "z_score",
        "risk_d2",
        "error",
    ],
    "fred_columns": ["slug", "id", "n", "last", "z", "error"],
    "definitions": {
        "ticker": "Series slug identifier used in macro rows",
        "Proxy": "Derived macro grouping for downstream aggregations",
        "recent_change": "Absolute change between the last two valid observations",
        "recent_change_label": "Human label for the displayed recent change metric",
        "display_change": "Preformatted recent-change string intended for UI display",
        "pct_change": "Change between first and last values in the cached window",
        "z_score": "Last-value z-score over the cached numeric window",
        "risk_d2": "Mean return / stddev return over the cached window",
        "start": "First value in the cached numeric window",
        "end": "Latest value in the cached numeric window",
        "slug": "Series slug from macro_fred_series.json",
        "id": "FRED series ID",
        "last": "Latest numeric observation",
        "z": "Last-value z-score over the cached numeric window",
    },
    "note": (
        "FRED-only macro feed with cache-aware update polling. "
        "Rows expose both legacy pct_change and a recent-change display contract; "
        "WARN/FAIL source degradations surface through row error tags and metadata quality."
    ),
}


@dataclass
class AnalyzerContext:
    """
    [ROLE]
    - Teleology: Carry the per-run analyzer configuration, time anchor, and repo root needed by fetch and compute helpers.
    - Ownership: Owns cfg, params, as_of, and repo_root references for a single run.
    - Mutability: Mutable dataclass; fields set at construction and read by helpers.
    - Concurrency: Not shared across threads; one instance per run.
    """

    cfg: Dict[str, Any]
    params: Dict[str, Any]
    as_of: str
    repo_root: Path


@dataclass(frozen=True)
class RatePolicy:
    """
    [ROLE]
    - Teleology: Encode the FRED request pacing and retry policy as an immutable config object.
    - Ownership: Owns rate, timeout, backoff, and circuit-breaker parameters for a run.
    - Mutability: Config-frozen (frozen dataclass).
    - Concurrency: Safe to share across threads; immutable after construction.
    """

    requests_per_second: float = 2.0
    timeout_s: float = 10.0
    max_retries_429: int = 4
    backoff_base_s: float = 0.6
    backoff_jitter_s: float = 0.25
    breaker_consecutive_429: int = 6


@dataclass(frozen=True)
class CachePolicy:
    """
    [ROLE]
    - Teleology: Encode the FRED series cache TTL, stale-on-error window, and history depth as an immutable config object.
    - Ownership: Owns cache enablement and TTL parameters for a run.
    - Mutability: Config-frozen (frozen dataclass).
    - Concurrency: Safe to share across threads; immutable after construction.
    """

    enabled: bool = True
    poll_ttl_s: int = 6 * 3600
    stale_if_error_ttl_s: int = 72 * 3600
    history_limit: int = 240


@dataclass(frozen=True)
class FredObservation:
    date: str
    value: float
    realtime_start: Optional[str] = None
    realtime_end: Optional[str] = None


class FredError(Exception):
    """
    [ROLE]
    - Teleology: Base exception for all FRED fetch and cache errors in the macro lane.
    - Ownership: Owns no state beyond the exception message.
    - Mutability: Immutable after raise.
    - Concurrency: Thread-safe; stateless.
    """


class RateLimitError(FredError):
    """
    [ROLE]
    - Teleology: Signal that the FRED API returned 429 Too Many Requests after all retries.
    - Ownership: Owns no state beyond the exception message.
    - Mutability: Immutable after raise.
    - Concurrency: Thread-safe; stateless.
    """


class NetworkError(FredError):
    """
    [ROLE]
    - Teleology: Signal a transport-level failure (connection error, timeout, or malformed response) during a FRED request.
    - Ownership: Owns no state beyond the exception message.
    - Mutability: Immutable after raise.
    - Concurrency: Thread-safe; stateless.
    """


class InvalidSeriesError(FredError):
    """
    [ROLE]
    - Teleology: Signal that a FRED series ID was rejected as invalid (HTTP 400/404 or empty observations).
    - Ownership: Owns no state beyond the exception message.
    - Mutability: Immutable after raise.
    - Concurrency: Thread-safe; stateless.
    """


class CircuitBreakerOpen(FredError):
    """
    [ROLE]
    - Teleology: Signal that the circuit breaker tripped after too many consecutive 429 responses, blocking further requests.
    - Ownership: Owns no state beyond the exception message.
    - Mutability: Immutable after raise.
    - Concurrency: Thread-safe; stateless.
    """


class RequestPacer:
    """
    [ROLE]
    - Teleology: Enforce per-run FRED request pacing via a leaky-bucket interval gate.
    - Ownership: Owns the minimum interval and next-allowed timestamp for a single run.
    - Mutability: Mutable; _next_allowed advances on each wait() call.
    - Concurrency: Not thread-safe; intended for single-threaded use within a run.
    """

    def __init__(self, requests_per_second: float) -> None:
        rps = max(float(requests_per_second), 0.1)
        self._min_interval = 1.0 / rps
        self._next_allowed = 0.0

    def wait(self) -> None:
        """
        [ACTION]
        - Teleology: Block the caller until the leaky-bucket interval has elapsed since the last request.
        - Guarantee: After returning, at least _min_interval seconds have passed since the previous call.
        - Fails: None; always sleeps as needed and advances _next_allowed.
        """
        now = time.monotonic()
        if now < self._next_allowed:
            time.sleep(self._next_allowed - now)
            now = time.monotonic()
        self._next_allowed = max(now, self._next_allowed) + self._min_interval


class FredHttpClient:
    """
    [ROLE]
    - Teleology: Execute rate-limited, retrying HTTP requests to the FRED observations endpoint with circuit-breaker protection.
    - Ownership: Owns the requests.Session, RequestPacer, and per-run diagnostic counters.
    - Mutability: Mutable; counters and breaker state update on each get_json() call.
    - Concurrency: Not thread-safe; intended for single-threaded sequential use within a run.
    """

    def __init__(self, api_key: str, policy: RatePolicy) -> None:
        self.api_key = api_key
        self.policy = policy
        self.pacer = RequestPacer(policy.requests_per_second)
        self.session = requests.Session() if requests is not None else None  # type: ignore[operator]

        self.total_requests = 0
        self.rate_limited_count = 0
        self.network_warn_count = 0
        self.invalid_series_count = 0
        self.breaker_tripped = False
        self.breaker_skipped_count = 0
        self._consecutive_429 = 0

    def _extract_api_error(self, response: Any) -> str:
        try:
            payload = response.json()
            if isinstance(payload, Mapping):
                msg = payload.get("error_message")
                if isinstance(msg, str) and msg.strip():
                    return msg.strip()
        except Exception:
            pass
        return ""

    def get_json(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        [ACTION]
        - Teleology: Execute a paced, retrying GET to the FRED observations endpoint and return the parsed JSON payload.
        - Guarantee: Returns a dict payload on success; advances all diagnostic counters on each attempt.
        - Fails: Raises CircuitBreakerOpen when breaker is tripped; RateLimitError after max retries on 429; InvalidSeriesError on 400/404; NetworkError on transport failure or non-dict payload.
        """
        if self.breaker_tripped:
            self.breaker_skipped_count += 1
            raise CircuitBreakerOpen("Circuit breaker open after repeated 429 responses")

        if self.session is None:
            self.network_warn_count += 1
            raise NetworkError("Missing dependency: requests")

        req_params = dict(params)
        req_params["api_key"] = self.api_key
        req_params["file_type"] = "json"

        for attempt in range(self.policy.max_retries_429 + 1):
            self.pacer.wait()
            self.total_requests += 1
            try:
                resp = self.session.get(
                    FRED_OBSERVATIONS_URL,
                    params=req_params,
                    timeout=float(self.policy.timeout_s),
                )
            except Exception as exc:
                self.network_warn_count += 1
                raise NetworkError(str(exc)) from exc

            if resp.status_code == 429:
                self.rate_limited_count += 1
                self._consecutive_429 += 1
                if self._consecutive_429 >= self.policy.breaker_consecutive_429:
                    self.breaker_tripped = True

                if attempt < self.policy.max_retries_429 and not self.breaker_tripped:
                    base = float(self.policy.backoff_base_s) * (2**attempt)
                    jitter = random.uniform(0.0, float(self.policy.backoff_jitter_s))
                    time.sleep(base + jitter)
                    continue

                raise RateLimitError(
                    f"429 Too Many Requests for series_id={req_params.get('series_id')}"
                )

            if resp.status_code in (400, 404):
                self._consecutive_429 = 0
                self.invalid_series_count += 1
                api_error = self._extract_api_error(resp)
                msg = api_error or f"HTTP {resp.status_code}"
                raise InvalidSeriesError(msg)

            if resp.status_code >= 500:
                self._consecutive_429 = 0
                self.network_warn_count += 1
                raise NetworkError(f"HTTP {resp.status_code}")

            try:
                resp.raise_for_status()
                payload = resp.json()
            except Exception as exc:
                self.network_warn_count += 1
                raise NetworkError(str(exc)) from exc

            self._consecutive_429 = 0
            if isinstance(payload, Mapping):
                return dict(payload)

            self.network_warn_count += 1
            raise NetworkError("Invalid JSON payload shape from FRED")

        raise RateLimitError("Unreachable retry state")


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _parse_iso_to_epoch(value: Any) -> Optional[float]:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except Exception:
        return None


def _as_of_date(as_of: str) -> str:
    try:
        dt = datetime.fromisoformat(str(as_of).replace("Z", "+00:00"))
        return dt.astimezone(timezone.utc).strftime("%Y-%m-%d")
    except Exception:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _isfinite(x: Any) -> bool:
    try:
        return math.isfinite(float(x))
    except Exception:
        return False


def _to_float(value: Any) -> Optional[float]:
    try:
        f = float(value)
    except Exception:
        return None
    return f if math.isfinite(f) else None


def _hash_value(value: Any) -> str:
    return hashlib.sha1(str(value).encode("utf-8")).hexdigest()[:12]


def _safe_slug(value: str) -> str:
    out = []
    for ch in str(value).strip().upper():
        if ch.isalnum() or ch in ("-", "_"):
            out.append(ch)
        else:
            out.append("_")
    return "".join(out) or "UNKNOWN"


def _calc_pct(start: float, end: float) -> float:
    if start == 0:
        return 0.0
    return (end - start) / start


def _calc_recent_change(series: List[float]) -> Optional[float]:
    if len(series) < 2:
        return None
    return float(series[-1] - series[-2])


def _format_display_change(value: Optional[float]) -> Optional[str]:
    if value is None or not math.isfinite(value):
        return None
    magnitude = abs(value)
    if magnitude >= 1_000:
        return f"{value:+,.0f}"
    if magnitude >= 100:
        return f"{value:+.1f}"
    if magnitude >= 10:
        return f"{value:+.2f}"
    if magnitude >= 1:
        return f"{value:+.3f}"
    return f"{value:+.4f}"


def _calc_z(series: List[float]) -> float:
    if len(series) < 2:
        return 0.0
    mu = sum(series) / len(series)
    var = sum((x - mu) ** 2 for x in series) / (len(series) - 1)
    sd = math.sqrt(var) if var > 0 else 0.0
    if sd == 0:
        return 0.0
    return (series[-1] - mu) / sd


def _calc_d2_score(returns: List[float]) -> float:
    if not returns:
        return 0.0
    mu = sum(returns) / len(returns)
    var = sum((r - mu) ** 2 for r in returns) / max(1, len(returns) - 1)
    sd = math.sqrt(var) if var > 0 else 0.0
    if sd == 0:
        return 0.0
    return mu / sd


def _returns(values: List[float]) -> List[float]:
    out: List[float] = []
    for i in range(1, len(values)):
        a = values[i - 1]
        b = values[i]
        if a != 0:
            out.append((b - a) / a)
    return out


def clean_nan_for_json(obj: Any) -> Any:
    """
    [ACTION]
    - Teleology: Recursively replace non-finite floats (NaN, inf, -inf) with None so the result is JSON-serializable.
    - Guarantee: Returns a structurally equivalent object where all non-finite floats are replaced with None.
    - Fails: None; non-float, non-dict, non-list values are returned unchanged.
    """
    if isinstance(obj, dict):
        return {k: clean_nan_for_json(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [clean_nan_for_json(v) for v in obj]
    if isinstance(obj, float) and not math.isfinite(obj):
        return None
    return obj


def _extract_numeric_observations_with_realtime(payload: Mapping[str, Any]) -> List[FredObservation]:
    observations = payload.get("observations")
    if not isinstance(observations, list):
        return []

    parsed: List[FredObservation] = []
    for obs in observations:
        if not isinstance(obs, Mapping):
            continue
        date = str(obs.get("date") or "").strip()
        if not date:
            continue
        val = _to_float(obs.get("value"))
        if val is None:
            continue
        realtime_start = str(obs.get("realtime_start") or "").strip() or None
        realtime_end = str(obs.get("realtime_end") or "").strip() or None
        parsed.append(
            FredObservation(
                date=date,
                value=val,
                realtime_start=realtime_start,
                realtime_end=realtime_end,
            )
        )

    parsed.sort(key=lambda item: item.date)
    return parsed


def _extract_numeric_observations(payload: Mapping[str, Any]) -> List[Tuple[str, float]]:
    return [(obs.date, obs.value) for obs in _extract_numeric_observations_with_realtime(payload)]


def _infer_proxy(slug: str, spec: Any) -> str:
    if isinstance(spec, Mapping):
        for key in ("proxy", "category", "group"):
            raw = spec.get(key)
            if isinstance(raw, str) and raw.strip():
                return raw.strip()

    s = slug.lower()
    if any(k in s for k in ("cpi", "ppi", "pce", "inflation")):
        return "inflation"
    if any(k in s for k in ("gdp", "income", "sales", "production")):
        return "growth"
    if any(k in s for k in ("rate", "yield", "spread", "sofr", "effr", "iorb")):
        return "rates"
    if any(k in s for k in ("credit", "delinq", "default", "loan")):
        return "credit"
    if any(k in s for k in ("housing", "mortgage", "home")):
        return "housing"
    if any(k in s for k in ("labor", "employment", "unemployment", "claims", "jobs")):
        return "labor"
    return "fred_series"


def _build_success_rows(
    slug: str,
    series_id: str,
    spec: Any,
    values: List[float],
    *,
    latest_observation_date: Optional[str] = None,
    latest_realtime_start: Optional[str] = None,
    latest_realtime_end: Optional[str] = None,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    z = _calc_z(values)
    start = float(values[0])
    end = float(values[-1])
    pct = _calc_pct(start, end)
    recent_change = _calc_recent_change(values)
    d2 = _calc_d2_score(_returns(values))

    market_row = {
        "proxy": _infer_proxy(slug, spec),
        "n": len(values),
        "start": start,
        "end": end,
        "recent_change": recent_change,
        "recent_change_label": "Δ last obs",
        "display_change": _format_display_change(recent_change),
        "pct": float(pct),
        "z": float(z),
        "d2": float(d2),
        "error": None,
        "last_observation_date": latest_observation_date,
        "realtime_start": latest_realtime_start,
        "realtime_end": latest_realtime_end,
    }

    fred_row = {
        "id": series_id,
        "n": len(values),
        "last": end,
        "z": float(z),
        "error": None,
        "last_observation_date": latest_observation_date,
        "realtime_start": latest_realtime_start,
        "realtime_end": latest_realtime_end,
    }

    return market_row, fred_row


def _build_error_rows(series_id: str, error: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    market_row = {
        "proxy": "fred_series",
        "n": None,
        "start": None,
        "end": None,
        "recent_change": None,
        "recent_change_label": "Δ last obs",
        "display_change": None,
        "pct": None,
        "z": None,
        "d2": None,
        "error": error,
    }
    fred_row = {
        "id": series_id,
        "n": None,
        "last": None,
        "z": None,
        "error": error,
    }
    return market_row, fred_row


def _read_json(path: Path) -> Dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_json_atomic(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def _load_cache_index(cache_root: Path) -> Dict[str, Any]:
    return _read_json(cache_root / CACHE_INDEX_NAME)


def _save_cache_index(cache_root: Path, index_payload: Mapping[str, Any]) -> None:
    _write_json_atomic(cache_root / CACHE_INDEX_NAME, index_payload)


def _load_series_cache(cache_root: Path, series_id: str) -> Dict[str, Any]:
    path = cache_root / CACHE_SERIES_DIR / f"{_safe_slug(series_id)}.json"
    return _read_json(path)


def _save_series_cache(cache_root: Path, series_id: str, payload: Mapping[str, Any]) -> None:
    path = cache_root / CACHE_SERIES_DIR / f"{_safe_slug(series_id)}.json"
    _write_json_atomic(path, payload)


def _cache_can_skip_poll(entry: Mapping[str, Any], now_epoch: float, policy: CachePolicy) -> bool:
    last_poll = _parse_iso_to_epoch(entry.get("last_poll_utc"))
    if last_poll is None:
        return False
    return (now_epoch - last_poll) <= float(policy.poll_ttl_s)


def _cache_is_usable_on_error(entry: Mapping[str, Any], now_epoch: float, policy: CachePolicy) -> bool:
    last_fetch = _parse_iso_to_epoch(entry.get("last_fetch_utc"))
    if last_fetch is None:
        return False
    return (now_epoch - last_fetch) <= float(policy.stale_if_error_ttl_s)


def _resolve_series_map(cfg: Mapping[str, Any]) -> Dict[str, Any]:
    series_map = cfg.get("fred_series")
    if isinstance(series_map, Mapping):
        return dict(series_map)
    return {}


def _resolve_series_id(spec: Any) -> str:
    if isinstance(spec, Mapping):
        candidate = spec.get("id")
    else:
        candidate = spec
    return str(candidate or "").strip()


def fetch_fred_series(
    ctx: AnalyzerContext,
    api_key: str,
    rate_policy: RatePolicy,
    cache_policy: CachePolicy,
) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
    """
    [ACTION]
    - Teleology: Fetch or reuse cached FRED series rows and assemble the macro lane payload plus diagnostics.
    - Mechanism: Resolve configured series ids, decide cache fast-path versus poll/full fetch, normalize FRED responses into market/fred row maps, and accumulate error and rate-limit diagnostics.
    - Reads: `ctx.cfg`, `ctx.repo_root`, `rate_policy`, `cache_policy`, FRED network responses, and `state/cache/fred`.
    - Writes: Cache index and per-series cache files when cache updates are enabled.
    - Guarantee: Returns `(markets_out, fred_out, diag)` where `diag` always contains source-level counts and warning/error buckets even on degraded runs.
    - Fails: Missing API key or series definitions do not raise; they downgrade into warning/error diagnostics and sparse outputs. Transport, rate-limit, and invalid-series errors are absorbed into per-series rows or cache fallback paths.
    - When-needed: Open when the macro lane needs the exact cache-versus-network fetch path or you are tracing why a FRED series was reused, polled, or downgraded.
    - Escalates-to: tools/calculator/calculator.py::run; tools/oracle/subject_index.py::run
    """
    diag: Dict[str, Any] = {
        "source": "fred",
        "valid_items": 0,
        "errors": [],
        "warnings": [],
        "cached_used": 0,
        "stale_cache_used": 0,
        "polled_count": 0,
        "fetched_count": 0,
        "rate_limited_count": 0,
        "invalid_series_count": 0,
        "network_warn_count": 0,
        "breaker_tripped": False,
        "breaker_skipped_count": 0,
        "total_series": 0,
        "lifecycle_hints": {},
    }

    series_map = _resolve_series_map(ctx.cfg)
    if not series_map:
        msg = "Missing or empty config: fred_series"
        diag["errors"].append(msg)
        feed_envelope.record_fetch_outcome(diag, ok=False)
        feed_envelope.append_partial_failure(
            diag,
            feed_envelope.warning_event(
                code="fred_missing_config",
                lane="macro",
                message=msg,
            ),
        )
        return {}, {}, diag

    diag["total_series"] = len(series_map)

    if not api_key:
        msg = "Missing API Key (checked config and env)"
        diag["warnings"].append(msg)
        feed_envelope.record_fetch_outcome(diag, ok=False)
        feed_envelope.append_partial_failure(
            diag,
            feed_envelope.warning_event(
                code="fred_missing_api_key",
                lane="macro",
                message=msg,
            ),
        )
        return {}, {}, diag

    markets_out: Dict[str, Any] = {}
    fred_out: Dict[str, Any] = {}

    cache_root = (ctx.repo_root / CACHE_ROOT_REL).resolve()
    cache_enabled = bool(cache_policy.enabled)
    cache_index = _load_cache_index(cache_root) if cache_enabled else {}
    cache_index_entries = cache_index.get("series", {}) if isinstance(cache_index.get("series", {}), dict) else {}

    client = FredHttpClient(api_key=api_key, policy=rate_policy)
    now_epoch = time.time()
    as_of_date = _as_of_date(ctx.as_of)

    for slug, spec in series_map.items():
        slug_str = str(slug)
        series_id = _resolve_series_id(spec)

        def _record_lifecycle_hint(
            *,
            resolved_series_id: str,
            source_path: str,
            change_kind: str,
            latest_observation_date: Optional[str] = None,
            latest_realtime_start: Optional[str] = None,
            latest_realtime_end: Optional[str] = None,
            previous_observation_date: Optional[str] = None,
            previous_value_hash: Optional[str] = None,
            current_value_hash: Optional[str] = None,
            error: Optional[str] = None,
        ) -> None:
            hints = diag.get("lifecycle_hints")
            if not isinstance(hints, dict):
                hints = {}
                diag["lifecycle_hints"] = hints
            hints[slug_str] = {
                "series_id": resolved_series_id,
                "source_path": source_path,
                "change_kind": change_kind,
                "last_observation_date": latest_observation_date,
                "last_realtime_start": latest_realtime_start,
                "last_realtime_end": latest_realtime_end,
                "previous_observation_date": previous_observation_date,
                "previous_value_hash": previous_value_hash,
                "current_value_hash": current_value_hash,
                "error": error,
            }

        if not series_id:
            msg = f"{slug_str} missing series id"
            diag["errors"].append(msg)
            feed_envelope.record_fetch_outcome(diag, ok=False)
            feed_envelope.append_partial_failure(
                diag,
                feed_envelope.warning_event(
                    code="fred_missing_config",
                    lane="macro",
                    series_id=slug_str,
                    message=msg,
                ),
            )
            market_err, fred_err = _build_error_rows("UNKNOWN", FAIL_INVALID_SERIES)
            markets_out[slug_str] = market_err
            fred_out[slug_str] = fred_err
            _record_lifecycle_hint(
                resolved_series_id="UNKNOWN",
                source_path="config_error",
                change_kind="invalid_series",
                error=FAIL_INVALID_SERIES,
            )
            continue

        entry = _load_series_cache(cache_root, series_id) if cache_enabled else {}
        cached_market = entry.get("market_row") if isinstance(entry.get("market_row"), Mapping) else None
        cached_fred = entry.get("fred_row") if isinstance(entry.get("fred_row"), Mapping) else None

        def _use_cached_row(
            *,
            stale_warning: Optional[str] = None,
            source_path: str = "cache_hit",
            change_kind: str = "cache_hit",
        ) -> bool:
            if not (cached_market and cached_fred):
                return False
            market_row = dict(cached_market)
            fred_row = dict(cached_fred)
            if stale_warning:
                market_row["error"] = stale_warning
                fred_row["error"] = stale_warning
                diag["stale_cache_used"] += 1
            else:
                diag["cached_used"] += 1
            markets_out[slug_str] = market_row
            fred_out[slug_str] = fred_row
            diag["valid_items"] += 1
            feed_envelope.record_fetch_outcome(diag, ok=True)
            _record_lifecycle_hint(
                resolved_series_id=series_id,
                source_path=source_path,
                change_kind=change_kind,
                latest_observation_date=str(entry.get("last_observation_date") or "")
                or market_row.get("last_observation_date")
                or fred_row.get("last_observation_date"),
                latest_realtime_start=str(entry.get("last_realtime_start") or "")
                or market_row.get("realtime_start")
                or fred_row.get("realtime_start"),
                latest_realtime_end=str(entry.get("last_realtime_end") or "")
                or market_row.get("realtime_end")
                or fred_row.get("realtime_end"),
                previous_observation_date=str(entry.get("last_observation_date") or "") or None,
                previous_value_hash=str(entry.get("last_value_hash") or "") or None,
                current_value_hash=str(entry.get("last_value_hash") or "") or None,
                error=stale_warning,
            )
            return True

        # Fast path: recently polled cache can be used without network.
        if cache_enabled and entry and _cache_can_skip_poll(entry, now_epoch, cache_policy):
            if _use_cached_row():
                continue

        pending_change_kind = "initial_fetch" if not entry else "full_fetch_refresh"
        pending_previous_observation_date = str(entry.get("last_observation_date") or "") or None
        pending_previous_value_hash = str(entry.get("last_value_hash") or "") or None

        # Cache-aware poll path (only if cache already exists).
        if cache_enabled and entry and cached_market and cached_fred:
            try:
                poll_payload = client.get_json(
                    {
                        "series_id": series_id,
                        "observation_end": as_of_date,
                        "sort_order": "desc",
                        "limit": 1,
                    }
                )
                diag["polled_count"] += 1
                poll_observations = _extract_numeric_observations_with_realtime(poll_payload)
                if not poll_observations:
                    raise InvalidSeriesError("No numeric observations in poll payload")

                latest_obs = poll_observations[-1]
                latest_date = latest_obs.date
                latest_value = latest_obs.value
                latest_hash = _hash_value(latest_value)
                cached_date = str(entry.get("last_observation_date") or "")
                cached_hash = str(entry.get("last_value_hash") or "")

                if latest_date == cached_date and latest_hash == cached_hash:
                    if _use_cached_row():
                        updated_entry = dict(entry)
                        updated_entry["last_poll_utc"] = _utcnow_iso()
                        updated_entry["last_realtime_start"] = latest_obs.realtime_start
                        updated_entry["last_realtime_end"] = latest_obs.realtime_end
                        _save_series_cache(cache_root, series_id, updated_entry)
                        cache_index_entries[series_id] = {
                            "series_id": series_id,
                            "slug": slug_str,
                            "last_observation_date": latest_date,
                            "last_value_hash": latest_hash,
                            "last_realtime_start": latest_obs.realtime_start,
                            "last_realtime_end": latest_obs.realtime_end,
                            "last_fetch_utc": updated_entry.get("last_fetch_utc"),
                            "last_poll_utc": updated_entry.get("last_poll_utc"),
                            "status": STATUS_PASS,
                            "error_class": None,
                        }
                        _record_lifecycle_hint(
                            resolved_series_id=series_id,
                            source_path="cache_hit",
                            change_kind="cache_hit",
                            latest_observation_date=latest_date,
                            latest_realtime_start=latest_obs.realtime_start,
                            latest_realtime_end=latest_obs.realtime_end,
                            previous_observation_date=cached_date,
                            previous_value_hash=cached_hash,
                            current_value_hash=latest_hash,
                        )
                        continue
                pending_change_kind = (
                    "revision_observed"
                    if latest_date == cached_date and latest_hash != cached_hash
                    else "new_release_observed"
                )
            except InvalidSeriesError:
                # Invalid means stale cache cannot be trusted as authoritative freshness.
                pass
            except (RateLimitError, NetworkError, CircuitBreakerOpen) as exc:
                warn_tag = WARN_RATE_LIMIT if isinstance(exc, (RateLimitError, CircuitBreakerOpen)) else WARN_NETWORK
                if _cache_is_usable_on_error(entry, now_epoch, cache_policy):
                    stale_msg = f"{warn_tag}: using_cached_last_success"
                    if _use_cached_row(
                        stale_warning=stale_msg,
                        source_path="stale_cache",
                        change_kind="fetch_error_cache_fallback",
                    ):
                        diag["warnings"].append(f"{slug_str} -> {stale_msg}")
                        continue
                # If cache is too stale or unusable, fall through to error row below.
                market_err, fred_err = _build_error_rows(series_id, warn_tag)
                markets_out[slug_str] = market_err
                fred_out[slug_str] = fred_err
                _record_lifecycle_hint(
                    resolved_series_id=series_id,
                    source_path="source_degraded",
                    change_kind="fetch_error",
                    previous_observation_date=pending_previous_observation_date,
                    previous_value_hash=pending_previous_value_hash,
                    error=warn_tag,
                )
                warn_msg = f"{slug_str} failed: {warn_tag}: {exc}"
                diag["warnings"].append(warn_msg)
                feed_envelope.record_fetch_outcome(diag, ok=False)
                feed_envelope.append_partial_failure(
                    diag,
                    feed_envelope.warning_event(
                        code="fred_rate_limit" if isinstance(exc, (RateLimitError, CircuitBreakerOpen)) else "fred_network",
                        lane="macro",
                        series_id=slug_str,
                        exc=exc,
                        message=warn_msg,
                    ),
                )
                continue

        # Full fetch path (no cache, changed cache, or invalid poll outcome).
        try:
            history_payload = client.get_json(
                {
                    "series_id": series_id,
                    "observation_end": as_of_date,
                    # Desc + limit yields the most recent N points; extractor re-sorts ascending.
                    "sort_order": "desc",
                    "limit": int(cache_policy.history_limit),
                }
            )
            observations = _extract_numeric_observations_with_realtime(history_payload)
            if not observations:
                raise InvalidSeriesError("No numeric observations in history payload")

            values = [float(obs.value) for obs in observations]
            latest_obs = observations[-1]
            latest_date = latest_obs.date
            latest_value = latest_obs.value
            latest_hash = _hash_value(latest_value)

            market_row, fred_row = _build_success_rows(
                slug_str,
                series_id,
                spec,
                values,
                latest_observation_date=latest_date,
                latest_realtime_start=latest_obs.realtime_start,
                latest_realtime_end=latest_obs.realtime_end,
            )
            markets_out[slug_str] = market_row
            fred_out[slug_str] = fred_row
            diag["valid_items"] += 1
            diag["fetched_count"] += 1
            feed_envelope.record_fetch_outcome(diag, ok=True)
            _record_lifecycle_hint(
                resolved_series_id=series_id,
                source_path="full_fetch",
                change_kind=pending_change_kind,
                latest_observation_date=latest_date,
                latest_realtime_start=latest_obs.realtime_start,
                latest_realtime_end=latest_obs.realtime_end,
                previous_observation_date=pending_previous_observation_date,
                previous_value_hash=pending_previous_value_hash,
                current_value_hash=latest_hash,
            )

            if cache_enabled:
                now_iso = _utcnow_iso()
                cache_payload = {
                    "series_id": series_id,
                    "slug": slug_str,
                    "market_row": market_row,
                    "fred_row": fred_row,
                    "last_observation_date": latest_date,
                    "last_value_hash": latest_hash,
                    "last_realtime_start": latest_obs.realtime_start,
                    "last_realtime_end": latest_obs.realtime_end,
                    "last_fetch_utc": now_iso,
                    "last_poll_utc": now_iso,
                    "status": STATUS_PASS,
                    "error_class": None,
                }
                _save_series_cache(cache_root, series_id, cache_payload)
                cache_index_entries[series_id] = {
                    "series_id": series_id,
                    "slug": slug_str,
                    "last_observation_date": latest_date,
                    "last_value_hash": latest_hash,
                    "last_realtime_start": latest_obs.realtime_start,
                    "last_realtime_end": latest_obs.realtime_end,
                    "last_fetch_utc": now_iso,
                    "last_poll_utc": now_iso,
                    "status": STATUS_PASS,
                    "error_class": None,
                }

        except InvalidSeriesError as exc:
            market_err, fred_err = _build_error_rows(series_id, FAIL_INVALID_SERIES)
            markets_out[slug_str] = market_err
            fred_out[slug_str] = fred_err
            _record_lifecycle_hint(
                resolved_series_id=series_id,
                source_path="invalid_series",
                change_kind="invalid_series",
                previous_observation_date=pending_previous_observation_date,
                previous_value_hash=pending_previous_value_hash,
                error=FAIL_INVALID_SERIES,
            )
            err_msg = f"{slug_str} failed: {FAIL_INVALID_SERIES}: {exc}"
            diag["errors"].append(err_msg)
            feed_envelope.record_fetch_outcome(diag, ok=False)
            feed_envelope.append_partial_failure(
                diag,
                feed_envelope.warning_event(
                    code="fred_invalid_series",
                    lane="macro",
                    series_id=slug_str,
                    exc=exc,
                    message=err_msg,
                ),
            )
            if cache_enabled:
                now_iso = _utcnow_iso()
                cache_index_entries[series_id] = {
                    "series_id": series_id,
                    "slug": slug_str,
                    "last_observation_date": str(entry.get("last_observation_date") or ""),
                    "last_value_hash": str(entry.get("last_value_hash") or ""),
                    "last_fetch_utc": now_iso,
                    "last_poll_utc": now_iso,
                    "status": STATUS_FAIL,
                    "error_class": FAIL_INVALID_SERIES,
                }

        except (RateLimitError, CircuitBreakerOpen) as exc:
            if cache_enabled and entry and _cache_is_usable_on_error(entry, now_epoch, cache_policy):
                stale_msg = f"{WARN_RATE_LIMIT}: using_cached_last_success"
                if _use_cached_row(
                    stale_warning=stale_msg,
                    source_path="stale_cache",
                    change_kind="fetch_error_cache_fallback",
                ):
                    diag["warnings"].append(f"{slug_str} -> {stale_msg}")
                    continue

            market_err, fred_err = _build_error_rows(series_id, WARN_RATE_LIMIT)
            markets_out[slug_str] = market_err
            fred_out[slug_str] = fred_err
            _record_lifecycle_hint(
                resolved_series_id=series_id,
                source_path="source_degraded",
                change_kind="fetch_error",
                previous_observation_date=pending_previous_observation_date,
                previous_value_hash=pending_previous_value_hash,
                error=WARN_RATE_LIMIT,
            )
            warn_msg = f"{slug_str} failed: {WARN_RATE_LIMIT}: {exc}"
            diag["warnings"].append(warn_msg)
            feed_envelope.record_fetch_outcome(diag, ok=False)
            feed_envelope.append_partial_failure(
                diag,
                feed_envelope.warning_event(
                    code="fred_rate_limit",
                    lane="macro",
                    series_id=slug_str,
                    exc=exc,
                    message=warn_msg,
                ),
            )

        except NetworkError as exc:
            if cache_enabled and entry and _cache_is_usable_on_error(entry, now_epoch, cache_policy):
                stale_msg = f"{WARN_NETWORK}: using_cached_last_success"
                if _use_cached_row(
                    stale_warning=stale_msg,
                    source_path="stale_cache",
                    change_kind="fetch_error_cache_fallback",
                ):
                    diag["warnings"].append(f"{slug_str} -> {stale_msg}")
                    continue

            market_err, fred_err = _build_error_rows(series_id, WARN_NETWORK)
            markets_out[slug_str] = market_err
            fred_out[slug_str] = fred_err
            _record_lifecycle_hint(
                resolved_series_id=series_id,
                source_path="source_degraded",
                change_kind="fetch_error",
                previous_observation_date=pending_previous_observation_date,
                previous_value_hash=pending_previous_value_hash,
                error=WARN_NETWORK,
            )
            warn_msg = f"{slug_str} failed: {WARN_NETWORK}: {exc}"
            diag["warnings"].append(warn_msg)
            feed_envelope.record_fetch_outcome(diag, ok=False)
            feed_envelope.append_partial_failure(
                diag,
                feed_envelope.warning_event(
                    code="fred_network",
                    lane="macro",
                    series_id=slug_str,
                    exc=exc,
                    message=warn_msg,
                ),
            )

    diag["rate_limited_count"] = client.rate_limited_count
    diag["invalid_series_count"] = client.invalid_series_count
    diag["network_warn_count"] = client.network_warn_count
    diag["breaker_tripped"] = client.breaker_tripped
    diag["breaker_skipped_count"] = client.breaker_skipped_count

    if cache_enabled:
        cache_index_payload = {
            "updated_at": _utcnow_iso(),
            "schema": "fred_cache.1",
            "series": cache_index_entries,
        }
        _save_cache_index(cache_root, cache_index_payload)

    return markets_out, fred_out, diag


def serialize_payload(markets: Dict[str, Any], fred: Dict[str, Any], decimals: int = 4) -> Dict[str, Any]:
    """
    [ACTION]
    - Teleology: Serialize the market and FRED row dicts into the columnar list format expected by the macro artifact envelope.
    - Guarantee: Returns a dict with columns, fred_columns, rows, and fred_rows keys; float values are rounded to `decimals` places.
    - Fails: None; missing or malformed rows are treated as empty dicts and produce sparse column lists.
    """
    def fmt(val: Any) -> Any:
        if isinstance(val, float) and math.isfinite(val):
            return round(val, decimals)
        return val

    assets_rows: List[List[Any]] = []
    for slug, row in (markets or {}).items():
        if not isinstance(row, Mapping):
            row = {}
        assets_rows.append(
            [
                slug,
                row.get("proxy"),
                row.get("n"),
                fmt(row.get("start")),
                fmt(row.get("end")),
                fmt(row.get("recent_change")),
                row.get("recent_change_label"),
                row.get("display_change"),
                fmt(row.get("pct")),
                fmt(row.get("z")),
                fmt(row.get("d2")),
                row.get("error"),
            ]
        )

    fred_rows: List[List[Any]] = []
    for slug, row in (fred or {}).items():
        if not isinstance(row, Mapping):
            row = {}
        fred_rows.append(
            [
                slug,
                row.get("id"),
                row.get("n"),
                fmt(row.get("last")),
                fmt(row.get("z")),
                row.get("error"),
            ]
        )

    return {
        "columns": MACRO_LEGEND["columns"],
        "fred_columns": MACRO_LEGEND["fred_columns"],
        "rows": assets_rows,
        "fred_rows": fred_rows,
    }


class StandardActor:
    """
    [ROLE]
    - Teleology: Orchestrate the FRED-only macro lane from config hydration through artifact emission for a single run.
    - Ownership: Owns config, params, run_id, as_of, repo_root, and the AnalyzerContext for a run.
    - Mutability: Mutable; initialized in __init__ and consumed by execute().
    - Concurrency: Not thread-safe; one instance per run.
    """

    def __init__(self, config: Dict[str, Any], run_dir: Optional[Any] = None):
        self.config = config.get("data", config)

        runtime_ctx = self.config.get("runtime", {})
        self.run_id = runtime_ctx.get("run_id")
        if not self.run_id and run_dir:
            try:
                self.run_id = run_dir.name
            except AttributeError:
                self.run_id = str(run_dir)
        if not self.run_id:
            self.run_id = "manual_run"

        anchor_str = runtime_ctx.get("time_anchor") or runtime_ctx.get("effective_date")
        self.as_of = str(anchor_str) if anchor_str else _utcnow_iso()

        raw_params = self.config.get("params") or self.config.get("macro_params") or {}
        if not raw_params:
            for k in ("decimals",):
                if k in runtime_ctx:
                    raw_params[k] = runtime_ctx[k]
        self.params = raw_params

        self.repo_root = Path(__file__).resolve().parents[2]
        self.ctx = AnalyzerContext(
            cfg=self.config,
            params=self.params,
            as_of=self.as_of,
            repo_root=self.repo_root,
        )

    def _rate_policy(self) -> RatePolicy:
        fred_cfg = self.config.get("fred", {}) if isinstance(self.config.get("fred"), Mapping) else {}
        return RatePolicy(
            requests_per_second=float(fred_cfg.get("requests_per_second", 2.0)),
            timeout_s=float(fred_cfg.get("timeout_s", 10.0)),
            max_retries_429=int(fred_cfg.get("max_retries_429", 4)),
            backoff_base_s=float(fred_cfg.get("backoff_base_s", 0.6)),
            backoff_jitter_s=float(fred_cfg.get("backoff_jitter_s", 0.25)),
            breaker_consecutive_429=int(fred_cfg.get("breaker_consecutive_429", 6)),
        )

    def _cache_policy(self) -> CachePolicy:
        fred_cfg = self.config.get("fred", {}) if isinstance(self.config.get("fred"), Mapping) else {}
        return CachePolicy(
            enabled=bool(fred_cfg.get("cache_enabled", True)),
            poll_ttl_s=int(fred_cfg.get("poll_ttl_s", 6 * 3600)),
            stale_if_error_ttl_s=int(fred_cfg.get("stale_if_error_ttl_s", 72 * 3600)),
            history_limit=int(fred_cfg.get("history_limit", 240)),
        )

    def execute(self) -> Dict[str, Any]:
        """
        [ACTION]
        - Teleology: Run the FRED-only macro lane end-to-end and emit the normalized artifact envelope expected by downstream market-intelligence tools.
        - Mechanism: Resolve analyzer toggles and auth, call `fetch_fred_series()`, serialize the lane payload, and package diagnostics plus metadata.
        - Reads: Config/runtime params, env-backed FRED credentials, cache state, and FRED responses via `fetch_fred_series()`.
        - Writes: Indirect cache updates only through `fetch_fred_series()`; otherwise returns an in-memory envelope.
        - Guarantee: Returns a macro tool envelope with metadata, diagnostics, legend, and serialized data rows even when the lane degrades into warnings or failure status.
        - Fails: Unhandled runtime exceptions bubble to the module-level `run()` wrapper, which converts them into a failure envelope.
        - When-needed: Open when you need the orchestration boundary that turns FRED fetch diagnostics into the final macro artifact consumed by calculator or oracle surfaces.
        - Escalates-to: tools/calculator/calculator.py::run; tools/oracle/subject_index.py::run
        """
        analyzers = self.config.get("analyzers", {}) if isinstance(self.config.get("analyzers"), Mapping) else {}
        fred_enabled = bool((analyzers.get("fred", {}) or {}).get("enabled", True))

        diagnostics: Dict[str, Any] = {
            "analyzers": {"prices": False, "fred": fred_enabled},
            "prices": {"skipped": True, "reason": "FRED-only macro runtime"},
            "fred": {},
        }

        markets_payload: Dict[str, Any] = {}
        fred_payload: Dict[str, Any] = {}

        if fred_enabled:
            fred_cfg = self.config.get("fred", {}) if isinstance(self.config.get("fred"), Mapping) else {}
            api_key = fred_cfg.get("api_key")
            if not api_key:
                fallback_var = str(fred_cfg.get("api_key_env_fallback") or "FRED_API_KEY")
                api_key = os.getenv(fallback_var)
            diagnostics["fred"]["auth_found"] = bool(api_key)

            markets_payload, fred_payload, diag_fred = fetch_fred_series(
                self.ctx,
                api_key=str(api_key or ""),
                rate_policy=self._rate_policy(),
                cache_policy=self._cache_policy(),
            )
            diagnostics["fred"].update(diag_fred)
        else:
            diagnostics["fred"] = {"skipped": True}

        decimals = int(self.params.get("decimals", 4))
        data = clean_nan_for_json(serialize_payload(markets_payload, fred_payload, decimals=decimals))

        input_rows = int((diagnostics.get("fred", {}) or {}).get("total_series", len(markets_payload)))
        output_rows = int(len(markets_payload))
        valid_count = int((diagnostics.get("fred", {}) or {}).get("valid_items", 0))
        dropped_rows = max(0, input_rows - output_rows)

        status: Literal["success", "failure"] = "success" if valid_count > 0 else "failure"

        warning_list: List[str] = []
        fred_errors = diagnostics.get("fred", {}).get("errors", [])
        if isinstance(fred_errors, list):
            warning_list.extend(str(err) for err in fred_errors if str(err).strip())
        fred_warnings = diagnostics.get("fred", {}).get("warnings", [])
        if isinstance(fred_warnings, list):
            warning_list.extend(str(err) for err in fred_warnings if str(err).strip())

        diagnostics = {
            **diagnostics,
            "input_rows": input_rows,
            "output_rows": output_rows,
            "dropped_rows": dropped_rows,
            "warnings": warning_list,
        }
        quality = self._build_quality_block(diagnostics, valid_count)
        lifecycle_snapshot = build_macro_lifecycle_snapshot(
            markets=markets_payload,
            fred=fred_payload,
            diagnostics=diagnostics.get("fred", {}) if isinstance(diagnostics.get("fred"), Mapping) else {},
            as_of_iso=self.as_of,
            configured_series=_resolve_series_map(self.config),
        )

        now = feed_envelope.utc_now()
        meta = feed_envelope.build_metadata(
            tool=TOOL_NAME,
            status=status,
            now=now,
            run_id=self.run_id,
            as_of=self.as_of,
            items_count=valid_count,
            diagnostics=diagnostics,
            data_schema_version=DATA_SCHEMA_VERSION,
            timestamp=now.iso,
            legend=MACRO_LEGEND,
            extra={
                "quality": quality,
                "display_hints": {
                    "pct_change": "percent_ratio",
                    "recent_change": "absolute_delta",
                    "display_change": "display_text",
                },
                "sidecars": {
                    MACRO_LIFECYCLE_SIDECAR_KEY: lifecycle_snapshot,
                },
            },
        )
        return {"metadata": meta, "data": data}

    def _build_quality_block(
        self,
        diagnostics: Mapping[str, Any],
        valid_count: int,
    ) -> Dict[str, Any]:
        fred_diag = diagnostics.get("fred", {}) if isinstance(diagnostics.get("fred"), Mapping) else {}
        reasons: List[str] = []
        blocked_metrics: List[str] = []

        for bucket in ("errors", "warnings"):
            raw_items = fred_diag.get(bucket, [])
            if not isinstance(raw_items, list):
                continue
            for item in raw_items:
                text = str(item or "").strip()
                if text and text not in reasons:
                    reasons.append(text)
                metric_slug = text.split(" failed:", 1)[0].strip() if " failed:" in text else ""
                if metric_slug and metric_slug not in blocked_metrics:
                    blocked_metrics.append(metric_slug)

        if valid_count <= 0:
            tone: Literal["ok", "warn", "block"] = "block"
            if not reasons:
                reasons.append("macro feed returned 0 valid series")
        elif reasons:
            tone = "warn"
        else:
            tone = "ok"

        quality: Dict[str, Any] = {
            "tone": tone,
            "reasons": reasons,
        }
        if blocked_metrics:
            quality["blocked_metrics"] = blocked_metrics
        return quality


def run(config: Dict[str, Any], run_dir: Optional[Any] = None) -> Dict[str, Any]:
    """
    [ACTION]
    - Teleology: Provide the harness-facing entrypoint for the macro lane and normalize top-level failures into a tool envelope.
    - Mechanism: Instantiate `StandardActor`, delegate to `execute()`, and catch uncaught exceptions to return a failure payload with metadata.
    - Reads: `config` and optional `run_dir`.
    - Writes: None directly; delegated cache writes occur only inside `StandardActor.execute()`.
    - Guarantee: Returns a dictionary envelope for both success and failure paths.
    - Fails: None locally; uncaught exceptions are converted into the returned failure envelope.
    - When-needed: Open when a runner or downstream tool needs the canonical macro entrypoint rather than the lower-level FRED helpers.
    - Escalates-to: tools/calculator/calculator.py::run; tools/oracle/subject_index.py::run
    """
    try:
        actor = StandardActor(config, run_dir)
        return actor.execute()
    except Exception as e:
        warning = str(e)
        now = feed_envelope.utc_now()
        diag = feed_envelope.new_diagnostics()
        if warning:
            feed_envelope.append_warning(diag, warning)
        run_id = feed_envelope.resolve_run_id(None, run_dir, default="unknown")
        meta = feed_envelope.build_metadata(
            tool=TOOL_NAME,
            status="failure",
            now=now,
            run_id=run_id,
            as_of=now.iso,
            items_count=0,
            diagnostics=diag,
            data_schema_version=DATA_SCHEMA_VERSION,
            timestamp=now.iso,
            legend=MACRO_LEGEND,
            error=warning,
            extra={
                "quality": {
                    "tone": "block",
                    "reasons": [warning] if warning else ["macro feed failed before emission"],
                },
                "display_hints": {
                    "pct_change": "percent_ratio",
                    "recent_change": "absolute_delta",
                    "display_change": "display_text",
                },
            },
        )
        return {"metadata": meta, "data": {}}
