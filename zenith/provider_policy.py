"""Operator's inexpensive-model policy and host-wide inference singleflight.

Model developers, rather than hosting companies, determine the allowlist.
Prices are USD per token. Metadata lookup never authorizes inference.
"""
from __future__ import annotations

import fcntl
import functools
import threading
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

DEVELOPERS = frozenset({"deepseek", "qwen", "z-ai", "minimax", "moonshotai", "inclusionai"})
MAX_INPUT = Decimal("0.0000005")
MAX_OUTPUT = Decimal("0.0000015")
MAX_AGE_DAYS = 180
_THREAD_LOCK = threading.Lock()


def require_model(model):
    if not isinstance(model, str) or model.split("/", 1)[0] not in DEVELOPERS:
        raise ValueError("Provider policy: only inexpensive Chinese-developed models are allowed; GPT-4.1 and other non-allowlisted models are banned")
    if "gpt-4.1" in model.lower() or model.count("/") != 1:
        raise ValueError("Provider policy: invalid or banned model")


def require_prices(prices):
    for key, limit in (("prompt", MAX_INPUT), ("completion", MAX_OUTPUT)):
        rate = Decimal(str(prices[key]))
        if not rate.is_finite() or rate < 0 or rate > limit:
            raise ValueError(f"Provider policy: {key} exceeds cheap-model ceiling ({limit * 1000000} USD / million tokens)")
    if Decimal(str(prices.get("request", 0))) != 0:
        raise ValueError("Provider policy: per-request fees are not allowed")


def recent_models(rows, *, family=None, now=None):
    """Newest eligible release first; no unverified names or cached defaults."""
    from .budgeted import reservation_prices
    current = now or datetime.now(timezone.utc).timestamp()
    eligible = []
    for row in rows:
        try:
            require_model(row["id"])
            require_prices(reservation_prices(row["pricing"]))
            if ":" in row["id"] or family and row["id"].split("/")[0] != family:
                continue
            if not 0 <= current - row["created"] <= MAX_AGE_DAYS * 86400:
                continue
            if row.get("architecture", {}).get("output_modalities") != ["text"]:
                continue
            if not {"max_tokens", "response_format", "structured_outputs"} <= set(row.get("supported_parameters", [])):
                continue
            eligible.append(row)
        except (ValueError, KeyError, TypeError, ArithmeticError):
            continue
    return sorted(eligible, key=lambda r: (-r["created"], Decimal(r["pricing"]["completion"]), r["id"]))


def latest_model(*, family=None, http_get=None):
    from system.lib.openrouter_free_runtime import _catalogue_rows
    rows = recent_models(_catalogue_rows(http_get=http_get), family=family)
    if not rows:
        raise RuntimeError("No recent cheap allowlisted model verified; no fallback permitted")
    return rows[0]["id"]


def serialized_inference(function):
    """One in-flight call across threads, processes, runs and Zenith checkouts."""
    @functools.wraps(function)
    def call(*args, **kwargs):
        path = Path.home() / ".cache" / "zenith" / "inference.lock"
        path.parent.mkdir(parents=True, exist_ok=True)
        with _THREAD_LOCK, path.open("a+") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            try:
                return function(*args, **kwargs)
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)
    return call
