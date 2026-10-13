"""Operator's inexpensive-model policy and host-wide bounded inference admission.

Model developers, rather than hosting companies, determine the allowlist.
Prices are USD per token. Metadata lookup never authorizes inference.
Legacy calls remain exclusive; explicitly opted-in pinned calls share bounded
capacity. These are operator controls, not universal provider concurrency rules.
"""
from __future__ import annotations

import fcntl
import functools
import contextlib
import hashlib
import threading
import time
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

DEVELOPERS = frozenset({"deepseek", "qwen", "z-ai", "minimax", "moonshotai", "inclusionai"})
MAX_INPUT = Decimal("0.0000005")
MAX_OUTPUT = Decimal("0.0000015")
MAX_AGE_DAYS = 180
_THREAD_LOCK = threading.Lock()
GLOBAL_INFERENCE_SLOTS = 3


def _inference_root():
    return Path.home() / '.cache' / 'zenith'


def _check_wait_cancel(cancel):
    if cancel is not None and cancel.is_set():
        raise RuntimeError('paid call cancelled while waiting for inference capacity; no reservation made')


@contextlib.contextmanager
def _file_gate(path, operation, cancel=None):
    with path.open('a+') as lock:
        acquired = False
        try:
            while not acquired:
                _check_wait_cancel(cancel)
                try:
                    fcntl.flock(lock, operation | fcntl.LOCK_NB)
                    acquired = True
                except BlockingIOError:
                    time.sleep(.01)
            _check_wait_cancel(cancel)
            yield lock
        finally:
            if acquired:
                fcntl.flock(lock, fcntl.LOCK_UN)


@contextlib.contextmanager
def inference_gate(mode='serial', provider_slug=None, cancel=None):
    """Operator limits, not a guarantee of a provider's allowed concurrency.

    Serial retains the legacy exclusive host lock. Bounded callers share that
    gate, take one of three host slots, and exclusively hold the pinned route.
    Route admission is conservative across models sharing a provider slug.
    Waiting bounded calls have no budget reservation and may be cancelled.
    """
    if mode not in ('serial', 'bounded'):
        raise ValueError('inference_mode must be serial or bounded')
    if mode == 'bounded' and not provider_slug:
        raise ValueError('bounded inference requires a pinned provider_slug')
    queued_at = time.monotonic()
    root = _inference_root()
    root.mkdir(parents=True, exist_ok=True)
    if mode == 'serial':
        # Keep legacy ordering, including cached-response/cancellation behavior.
        with _THREAD_LOCK, (root/'inference.lock').open('a+') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            try:
                yield {'queue_elapsed_seconds': time.monotonic() - queued_at,
                       'inference_mode': mode}
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)
        return
    route = hashlib.sha256(provider_slug.encode()).hexdigest()
    with _file_gate(root/f'inference-route-{route}.lock', fcntl.LOCK_EX, cancel):
        slot = None
        try:
            while slot is None:
                _check_wait_cancel(cancel)
                for index in range(GLOBAL_INFERENCE_SLOTS):
                    candidate = (root/f'inference-slot-{index}.lock').open('a+')
                    try:
                        fcntl.flock(candidate, fcntl.LOCK_EX | fcntl.LOCK_NB)
                        slot = candidate
                        break
                    except BlockingIOError:
                        candidate.close()
                    except BaseException:
                        candidate.close()
                        raise
                if slot is None:
                    time.sleep(.01)
            # Taking slots before the shared gate avoids a queue of shared
            # holders preventing an exclusive legacy call from entering.
            with _file_gate(root/'inference.lock', fcntl.LOCK_SH, cancel):
                yield {'queue_elapsed_seconds': time.monotonic() - queued_at,
                       'inference_mode': mode, 'global_inference_limit': GLOBAL_INFERENCE_SLOTS,
                       'provider_route_limit': 1, 'provider_route_sha256': route}
        finally:
            if slot is not None:
                fcntl.flock(slot, fcntl.LOCK_UN)
                slot.close()


def require_model(model):
    if not isinstance(model, str) or model.split("/", 1)[0] not in DEVELOPERS:
        raise ValueError("Provider policy: select a recent, capable, inexpensive Chinese-developed model")
    if model.count("/") != 1:
        raise ValueError("Provider policy: invalid model identifier")


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
        with inference_gate():
            return function(*args, **kwargs)
    return call
