"""
Guarded OpenRouter metadata, quota, and explicit chat smoke runtime.

[PURPOSE]
- Teleology: Let the repo discover current OpenRouter free-model capacity
  and perform bounded, explicit inference smoke calls without turning
  OpenRouter into an ungoverned paid provider.
- Mechanism: Read repo-local OPENROUTER_* config, call metadata/key-status
  endpoints, filter models to zero-cost/free-router surfaces, derive a
  conservative throughput envelope from OpenRouter's published free limits,
  and expose a chat/completions helper that defaults to no-spend/free-model
  posture unless the caller passes an explicit paid-call gate.

[INTERFACE]
- Exports runtime_status, guarded chat_completion_packet/chat_completion, explicit smoke, model/opportunity probes, and receipt writers.

[FLOW]
- Mechanism: Load runtime config, optionally query metadata/key endpoints, bound free-model candidates, enforce explicit inference policy, and normalize call receipts.

[DEPENDENCIES]
- Reads: Repo/process OPENROUTER configuration; injected or HTTP metadata/chat clients contact OpenRouter.
- Writes: Explicit receipt writers materialize JSON under state/openrouter_free_runtime.

[CONSTRAINTS]
- Guarantee: Metadata/status probes never call inference endpoints.
- Safety: This standalone adaptation never permits paid calls, verifies current
  catalogue zero pricing, restricts credentials to the official HTTPS host,
  disables redirects, and redacts durable receipts. Dotenv files are explicit.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import os
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

try:
    import requests
except ImportError:
    requests = None

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BASE_URL = "https://openrouter.ai"
DEFAULT_STATE_ROOT = "state/openrouter_free_runtime"
DEFAULT_TOP_N = 20
DEFAULT_CHAT_MODEL = FREE_ROUTER_MODEL_ID = "openrouter/free"
DEFAULT_CHAT_MAX_TOKENS = 64
DEFAULT_CHAT_TIMEOUT_S = 60
LONG_CONTEXT_THRESHOLD = 128_000
FREE_MODEL_BURST_RPM = 20
FREE_TIER_REQUESTS_PER_DAY = 50
PAID_HISTORY_FREE_REQUESTS_PER_DAY = 1000

HttpGet = Callable[[str, Mapping[str, str], int], Mapping[str, Any]]
HttpPost = Callable[[str, Mapping[str, str], Mapping[str, Any], int], Mapping[str, Any]]
_DOTENV_LOADED = False


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _ensure_env_loaded() -> None:
    # No automatic dotenv discovery: the standalone CLI accepts an explicit env file.
    return


def load_env_file(path: str | Path) -> None:
    """Load a user-selected local dotenv file without replacing process environment."""
    try:
        from dotenv import dotenv_values
    except ImportError:
        raise RuntimeError("explicit --env-file requires python-dotenv; install project dependencies or use environment variables") from None
    path = Path(path).expanduser().resolve()
    if not path.is_file():
        raise RuntimeError("selected environment file does not exist")
    allowed = {"OPENROUTER_API_KEY", "OPENROUTER_CHAT_MODEL", "NVIDIA_API_KEY"}
    try:
        values = dotenv_values(path, interpolate=False)
    except Exception:
        raise RuntimeError("selected environment file could not be parsed") from None
    for key, value in values.items():
        if key in allowed and value is not None:
            os.environ.setdefault(key, value)


def redact(value: Any, *, secrets: tuple[str, ...] = ()) -> Any:
    """Remove credentials from transport failures, response packets and durable receipts."""
    known = [str(os.environ.get(name) or "").strip() for name in ("OPENROUTER_API_KEY", "NVIDIA_API_KEY")]
    known.extend(str(item) for item in secrets if item)
    if isinstance(value, Mapping):
        hidden = {"apikey", "authorization", "accesstoken", "secret", "managementkey", "nvidiaapikey", "openrouterapikey", "password", "credentials"}
        return {str(key): "[REDACTED]" if re.sub(r"[^a-z]", "", str(key).lower()) in hidden else redact(item, secrets=tuple(known))
                for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact(item, secrets=tuple(known)) for item in value]
    if isinstance(value, str):
        result = value
        for token in sorted(set(known), key=len, reverse=True):
            if token:
                result = result.replace(token, "[REDACTED]")
        result = re.sub(r"(?i)Bearer\s+[^\s\"'<>]+", "Bearer [REDACTED]", result)
        result = re.sub(r"sk-or-v1-[A-Za-z0-9_-]+", "[REDACTED]", result)
        return result
    return value


def safe_error(exc: Exception, *, secrets: tuple[str, ...] = ()) -> str:
    return str(redact(f"{type(exc).__name__}: {exc}", secrets=secrets))


def _official_base_url(config: Mapping[str, Any] | None = None) -> str:
    candidate = str(_config_value(config, "base_url", "OPENROUTER_BASE_URL", DEFAULT_BASE_URL)).rstrip("/")
    if candidate != DEFAULT_BASE_URL:
        raise RuntimeError("OpenRouter credentials may be sent only to the official HTTPS API host; custom base URLs are disabled")
    return DEFAULT_BASE_URL


def _config_value(config: Mapping[str, Any] | None, key: str, env_var: str, default: Any) -> Any:
    if config and config.get(key) not in (None, ""):
        return config[key]
    _ensure_env_loaded()
    value = os.environ.get(env_var)
    return value if value not in (None, "") else default


def _bool_value(value: Any, *, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    token = str(value).strip().lower()
    if token in {"1", "true", "yes", "y", "on"}:
        return True
    if token in {"0", "false", "no", "n", "off"}:
        return False
    return default


def _positive_int(value: Any, *, default: int = DEFAULT_TOP_N) -> int:
    if isinstance(value, bool):
        return default
    if isinstance(value, int):
        return value if value > 0 else default
    token = str(value or "").strip()
    if token.isdigit():
        parsed = int(token)
        return parsed if parsed > 0 else default
    return default


def _as_float(value: Any) -> float | None:
    if isinstance(value, bool) or value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _transport(url: str, headers: Mapping[str, str], timeout_s: int, payload=None) -> Mapping[str, Any]:
    if not url.startswith(DEFAULT_BASE_URL + "/api/v1/"):
        raise RuntimeError("OpenRouter transport requires the official HTTPS API endpoint")
    token = str(headers.get("Authorization", "")).removeprefix("Bearer ")
    if requests is None:
        raise RuntimeError("provider network checks require requests; install project dependencies")
    try:
        if payload is None:
            response = requests.get(url, headers=dict(headers), timeout=timeout_s, allow_redirects=False)
        else:
            response = requests.post(url, headers=dict(headers), json=dict(payload), timeout=timeout_s, allow_redirects=False)
        if 300 <= response.status_code < 400:
            raise RuntimeError("OpenRouter redirects are disabled")
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, Mapping):
            raise RuntimeError("OpenRouter returned a non-object JSON response")
        return data
    except Exception as exc:
        raise RuntimeError(safe_error(exc, secrets=(token,))) from None


def _default_http_get(url: str, headers: Mapping[str, str], timeout_s: int) -> Mapping[str, Any]:
    return _transport(url, headers, timeout_s)


def _default_http_post(url: str, headers: Mapping[str, str], payload: Mapping[str, Any], timeout_s: int) -> Mapping[str, Any]:
    return _transport(url, headers, timeout_s, payload)


def _headers(api_key: str | None = None) -> dict[str, str]:
    headers = {
        "Accept": "application/json",
        "User-Agent": "plectis-zenith-provider-check/1.0",
    }
    token = str(api_key or "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _chat_headers(api_key: str, config: Mapping[str, Any] | None = None) -> dict[str, str]:
    headers = _headers(api_key)
    headers["Content-Type"] = "application/json"
    site_url = str(_config_value(config, "site_url", "OPENROUTER_SITE_URL", "") or "").strip()
    app_title = str(_config_value(config, "app_title", "OPENROUTER_APP_TITLE", "Plectis Zenith") or "").strip()
    if site_url:
        headers["HTTP-Referer"] = site_url
    if app_title:
        headers["X-Title"] = app_title
    return headers


def _resolve_api_key(config: Mapping[str, Any] | None) -> str:
    token = _config_value(config, "api_key", "OPENROUTER_API_KEY", "")
    api_key = str(token or "").strip()
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY is not configured")
    return api_key


def _pricing_zero(pricing: Any) -> bool:
    if not isinstance(pricing, Mapping) or not {"prompt", "completion"}.issubset(pricing):
        return False
    # Unknown, malformed, non-finite or ancillary nonzero pricing is not free.
    for value in pricing.values():
        parsed = _as_float(value)
        if parsed is None or not math.isfinite(parsed) or parsed != 0.0:
            return False
    return True


def _model_is_free(row: Mapping[str, Any]) -> bool:
    return _model_id_shape_is_free(str(row.get("id") or "")) and _pricing_zero(row.get("pricing"))


def _catalogue_rows(config=None, http_get=None) -> list[Mapping[str, Any]]:
    base = _official_base_url(config)
    getter = http_get or _default_http_get
    try:
        data = getter(base + "/api/v1/models", _headers(None), 30)
        rows = data.get("data")
        if not isinstance(rows, list):
            raise RuntimeError("OpenRouter model catalogue is unavailable or malformed")
        return [row for row in rows if isinstance(row, Mapping)]
    except Exception as exc:
        raise RuntimeError(safe_error(exc, secrets=(str((config or {}).get("api_key") or ""),))) from None


def verified_free_model(model: str, *, config=None, http_get=None) -> Mapping[str, Any]:
    matches = [row for row in _catalogue_rows(config, http_get) if row.get("id") == model]
    if len(matches) != 1 or not _model_is_free(matches[0]):
        raise RuntimeError("requested model is absent, ambiguous, or lacks verified zero pricing in the current catalogue")
    return matches[0]


def _model_score(row: Mapping[str, Any]) -> tuple[int, int, int, int, str]:
    supported = row.get("supported_parameters")
    supported_count = len(supported) if isinstance(supported, list) else 0
    context = int(_as_float(row.get("context_length")) or 0)
    created = int(_as_float(row.get("created")) or 0)
    model_id = str(row.get("id") or "")
    suffix_bonus = 1 if model_id.endswith(":free") else 0
    router_bonus = 1 if model_id == FREE_ROUTER_MODEL_ID else 0
    return (router_bonus, suffix_bonus, supported_count, context + created, model_id)


def _model_outputs_text(row: Mapping[str, Any]) -> bool:
    architecture = row.get("architecture") if isinstance(row.get("architecture"), Mapping) else {}
    output_modalities = architecture.get("output_modalities")
    if not isinstance(output_modalities, list):
        return True
    return "text" in output_modalities


def _supports_any(row: Mapping[str, Any], names: set[str]) -> bool:
    supported = row.get("supported_parameters")
    if not isinstance(supported, list):
        return False
    return bool(names.intersection(str(item) for item in supported))


def _price_per_million_tokens(pricing: Mapping[str, Any], key: str) -> float:
    value = _as_float(pricing.get(key))
    if value is None:
        return 0.0
    return round(value * 1_000_000, 6)


def _pricing_per_million(row: Mapping[str, Any]) -> dict[str, float]:
    pricing = row.get("pricing") if isinstance(row.get("pricing"), Mapping) else {}
    prompt = _price_per_million_tokens(pricing, "prompt")
    completion = _price_per_million_tokens(pricing, "completion")
    return {
        "prompt": prompt,
        "completion": completion,
        "one_m_input_plus_one_m_output": round(prompt + completion, 6),
        "internal_reasoning": _price_per_million_tokens(pricing, "internal_reasoning"),
        "input_cache_read": _price_per_million_tokens(pricing, "input_cache_read"),
        "input_cache_write": _price_per_million_tokens(pricing, "input_cache_write"),
    }


def _pricing_unit_costs(row: Mapping[str, Any]) -> dict[str, float]:
    pricing = row.get("pricing") if isinstance(row.get("pricing"), Mapping) else {}
    return {
        "request": _as_float(pricing.get("request")) or 0.0,
        "image": _as_float(pricing.get("image")) or 0.0,
        "web_search": _as_float(pricing.get("web_search")) or 0.0,
    }


def _model_blended_text_cost(row: Mapping[str, Any]) -> tuple[float, float, float, str]:
    pricing = _pricing_per_million(row)
    return (
        pricing["one_m_input_plus_one_m_output"],
        pricing["completion"],
        pricing["prompt"],
        str(row.get("id") or ""),
    )


def _paid_text_model(row: Mapping[str, Any]) -> bool:
    if _model_is_free(row) or not _model_outputs_text(row):
        return False
    pricing = _pricing_per_million(row)
    return pricing["prompt"] > 0.0 or pricing["completion"] > 0.0


def _model_id_shape_is_free(model_id: str) -> bool:
    token = str(model_id or "").strip()
    return token == FREE_ROUTER_MODEL_ID or token.endswith(":free")


def _normalize_message_content(content: Any) -> str:
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        chunks: list[str] = []
        for item in content:
            if isinstance(item, str):
                token = item.strip()
                if token:
                    chunks.append(token)
                continue
            if isinstance(item, Mapping):
                text = item.get("text")
                if isinstance(text, str) and text.strip():
                    chunks.append(text.strip())
        return "\n".join(chunks).strip()
    return str(content or "").strip()


def _chat_messages(prompt: str, cfg: Mapping[str, Any]) -> list[dict[str, Any]]:
    raw_messages = cfg.get("messages")
    if isinstance(raw_messages, list):
        return [dict(item) for item in raw_messages if isinstance(item, Mapping)]
    messages: list[dict[str, Any]] = []
    system_prompt = cfg.get("system_prompt")
    if system_prompt:
        messages.append({"role": "system", "content": str(system_prompt)})
    messages.append({"role": "user", "content": str(prompt)})
    return messages


def _chat_cache_key(
    *,
    model: str,
    messages: list[dict[str, Any]],
    max_tokens: int,
    temperature: Any,
    schema_version: str = "openrouter_chat_completion_v1",
) -> str:
    material = {
        "schema_version": schema_version,
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    return hashlib.sha256(
        json.dumps(material, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _paid_gate(cfg: Mapping[str, Any], model: str) -> dict[str, Any]:
    if _bool_value(_config_value(cfg, "allow_paid", "OPENROUTER_ALLOW_PAID", False)) or not _bool_value(_config_value(cfg, "free_only", "OPENROUTER_FREE_ONLY", True), default=True):
        raise RuntimeError("standalone OpenRouter adapter never permits paid calls")
    if not _model_id_shape_is_free(model):
        raise RuntimeError("standalone OpenRouter adapter permits only verified free model IDs")
    return {"free_only": True, "allow_paid": False, "paid_call_authorized": False,
            "model_id_shape": "free_candidate_requires_current_catalogue_validation"}


def _compact_market_model(row: Mapping[str, Any]) -> dict[str, Any]:
    model_id = str(row.get("id") or "").strip()
    architecture = row.get("architecture") if isinstance(row.get("architecture"), Mapping) else {}
    top_provider = row.get("top_provider") if isinstance(row.get("top_provider"), Mapping) else {}
    pricing = row.get("pricing") if isinstance(row.get("pricing"), Mapping) else {}
    return {
        "id": model_id,
        "name": str(row.get("name") or model_id),
        "context_length": row.get("context_length"),
        "created": row.get("created"),
        "pricing_zero": _pricing_zero(pricing),
        "free": _model_is_free(row),
        "pricing_usd_per_million_tokens": _pricing_per_million(row),
        "pricing_usd_per_unit": _pricing_unit_costs(row),
        "capability_flags": {
            "tools": _supports_any(row, {"tools"}),
            "structured_output": _supports_any(row, {"structured_outputs", "response_format"}),
            "reasoning": _supports_any(row, {"reasoning", "include_reasoning"}),
            "image_input": "image" in (architecture.get("input_modalities") or []),
            "file_input": "file" in (architecture.get("input_modalities") or []),
            "audio_input": "audio" in (architecture.get("input_modalities") or []),
            "video_input": "video" in (architecture.get("input_modalities") or []),
        },
        "top_provider": {
            "context_length": top_provider.get("context_length"),
            "max_completion_tokens": top_provider.get("max_completion_tokens"),
            "is_moderated": top_provider.get("is_moderated"),
        },
    }


def _rank_by_price(rows: list[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    return sorted(
        rows,
        key=lambda row: (
            *_model_blended_text_cost(row),
            -(int(_as_float(row.get("context_length")) or 0)),
        ),
    )


def _rank_free_capable(rows: list[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    return sorted(
        rows,
        key=lambda row: (
            -int(_as_float(row.get("context_length")) or 0),
            -len(row.get("supported_parameters") if isinstance(row.get("supported_parameters"), list) else []),
            str(row.get("id") or ""),
        ),
    )


def _model_opportunity_snapshot(
    model_rows: list[Mapping[str, Any]],
    *,
    top_n: int = DEFAULT_TOP_N,
) -> dict[str, Any]:
    limit = max(int(top_n), 0)
    text_rows = [row for row in model_rows if _model_outputs_text(row)]
    free_rows = [row for row in text_rows if _model_is_free(row)]
    paid_rows = [row for row in text_rows if _paid_text_model(row)]
    tool_structured = [
        row
        for row in paid_rows
        if _supports_any(row, {"tools"}) and _supports_any(row, {"structured_outputs", "response_format"})
    ]
    free_tool_structured = [
        row
        for row in free_rows
        if _supports_any(row, {"tools"}) and _supports_any(row, {"structured_outputs", "response_format"})
    ]
    long_context = [
        row
        for row in paid_rows
        if int(_as_float(row.get("context_length")) or 0) >= LONG_CONTEXT_THRESHOLD
    ]
    return {
        "schema_version": "openrouter_model_opportunities_v1",
        "authority": "metadata_only_no_inference",
        "pricing_units": {
            "token_prices": "USD per million tokens derived from OpenRouter per-token model metadata",
            "unit_prices": "USD per request/image/web_search unit when present",
            "blended_sort": "one million prompt tokens plus one million completion tokens",
        },
        "counts": {
            "models_seen": len(model_rows),
            "text_output_models_seen": len(text_rows),
            "free_text_output_models_seen": len(free_rows),
            "paid_text_output_models_seen": len(paid_rows),
        },
        "limits": {
            "top_n": limit,
            "long_context_threshold": LONG_CONTEXT_THRESHOLD,
        },
        "free_tool_structured_long_context": [
            _compact_market_model(row) for row in _rank_free_capable(free_tool_structured)[:limit]
        ],
        "cheapest_paid_text": [
            _compact_market_model(row) for row in _rank_by_price(paid_rows)[:limit]
        ],
        "cheapest_paid_tool_structured": [
            _compact_market_model(row) for row in _rank_by_price(tool_structured)[:limit]
        ],
        "cheapest_paid_long_context": [
            _compact_market_model(row) for row in _rank_by_price(long_context)[:limit]
        ],
        "interpretation_notes": [
            "This packet ranks metadata, price, context, and parameter support only; it is not a quality benchmark.",
            "Use OpenRouter provider.sort=price or the :floor shortcut only inside an explicit chat/task packet with paid-call gating.",
            "Free model daily quota is account-tier scoped, so do not assume the free shortlist can be multiplied by model count.",
        ],
    }


def _compact_model(row: Mapping[str, Any]) -> dict[str, Any]:
    model_id = str(row.get("id") or "").strip()
    pricing = row.get("pricing") if isinstance(row.get("pricing"), Mapping) else {}
    architecture = row.get("architecture") if isinstance(row.get("architecture"), Mapping) else {}
    top_provider = row.get("top_provider") if isinstance(row.get("top_provider"), Mapping) else {}
    return {
        "id": model_id,
        "name": str(row.get("name") or model_id),
        "context_length": row.get("context_length"),
        "created": row.get("created"),
        "pricing_zero": _pricing_zero(pricing),
        "free_suffix": model_id.endswith(":free"),
        "free_router": model_id == FREE_ROUTER_MODEL_ID,
        "input_modalities": architecture.get("input_modalities"),
        "output_modalities": architecture.get("output_modalities"),
        "supported_parameters": row.get("supported_parameters") or [],
        "pricing_usd_per_million_tokens": _pricing_per_million(row),
        "pricing_usd_per_unit": _pricing_unit_costs(row),
        "capability_flags": {
            "tools": _supports_any(row, {"tools"}),
            "structured_output": _supports_any(row, {"structured_outputs", "response_format"}),
            "reasoning": _supports_any(row, {"reasoning", "include_reasoning"}),
            "image_input": "image" in (architecture.get("input_modalities") or []),
            "file_input": "file" in (architecture.get("input_modalities") or []),
            "audio_input": "audio" in (architecture.get("input_modalities") or []),
            "video_input": "video" in (architecture.get("input_modalities") or []),
        },
        "top_provider": {
            "context_length": top_provider.get("context_length"),
            "max_completion_tokens": top_provider.get("max_completion_tokens"),
            "is_moderated": top_provider.get("is_moderated"),
        },
    }


def _sanitize_key_info(raw: Mapping[str, Any]) -> dict[str, Any]:
    data = raw.get("data") if isinstance(raw.get("data"), Mapping) else raw
    if not isinstance(data, Mapping):
        return {}
    keep = (
        "limit",
        "limit_reset",
        "limit_remaining",
        "include_byok_in_limit",
        "usage",
        "usage_daily",
        "usage_weekly",
        "usage_monthly",
        "byok_usage",
        "byok_usage_daily",
        "byok_usage_weekly",
        "byok_usage_monthly",
        "is_free_tier",
    )
    sanitized = {key: data.get(key) for key in keep if key in data}
    if "limit" in sanitized:
        sanitized["credit_limit_usd"] = sanitized.get("limit")
    if "limit_remaining" in sanitized:
        sanitized["credit_limit_remaining_usd"] = sanitized.get("limit_remaining")
    sanitized["limit_field_interpretation"] = (
        "OpenRouter /api/v1/key `limit` is the API-key credit limit, not the daily free-model request cap."
    )
    return sanitized


def _derive_throughput(key_info: Mapping[str, Any] | None) -> dict[str, Any]:
    info = dict(key_info or {})
    is_free_tier = info.get("is_free_tier")
    if is_free_tier is False:
        daily_limit = PAID_HISTORY_FREE_REQUESTS_PER_DAY
        daily_source = "openrouter_docs_paid_history_free_variant_limit"
    else:
        daily_limit = FREE_TIER_REQUESTS_PER_DAY
        daily_source = "openrouter_docs_free_tier_default"
    safe_interval = 86400.0 / float(max(daily_limit, 1))
    return {
        "free_model_burst_requests_per_minute": FREE_MODEL_BURST_RPM,
        "free_model_daily_request_limit": daily_limit,
        "daily_limit_source": daily_source,
        "recommended_sustained_requests_per_minute": round(daily_limit / 1440.0, 4),
        "recommended_min_interval_seconds_for_always_on": round(safe_interval, 3),
        "daily_cap_binds_before_burst_cap": True,
        "scope_notes": [
            "OpenRouter documents free :free variants as 20 rpm with a daily account-tier cap.",
            "`/api/v1/key.limit` is the key credit limit in dollars; do not read it as the free-model daily request cap.",
            "Additional accounts or API keys do not increase global rate limits.",
            "Different free models may still experience independent upstream 429s, so rotate on provider errors but do not assume per-model daily quota multiplication.",
        ],
    }


def runtime_status(config: Mapping[str, Any] | None = None, *, probe_live: bool = False,
                   include_models: bool = False, top_n: int = DEFAULT_TOP_N, http_get: HttpGet | None = None) -> dict[str, Any]:
    cfg = dict(config or {})
    base = _official_base_url(cfg)
    token = str(_config_value(cfg, "api_key", "OPENROUTER_API_KEY", "") or "").strip()
    result = {"kind": "openrouter_free_runtime_status", "schema_version": "openrouter_free_runtime_status_v1",
              "generated_at": _utc_now(), "configured": {"api_key_present": bool(token), "base_url": base,
              "free_only": True, "allow_paid": False}, "limits": {"free_model_daily_requests": None},
              "live_probe": {"status": "not_run", "key_status_checked": False, "models_checked": False}}
    errors = []
    if include_models or probe_live:
        try:
            rows = _catalogue_rows(cfg, http_get)
            eligible = sorted([row for row in rows if _model_is_free(row)], key=_model_score, reverse=True)
            result["models"] = {"total_models_seen": len(rows), "free_models_seen": len(eligible),
                "ranked_free_models": [{"id": row["id"], "name": row.get("name"), "context_length": row.get("context_length"),
                    "pricing_zero": True, "supported_parameters": row.get("supported_parameters", [])} for row in eligible[:max(0, top_n)]],
                "free_filter": "exact current catalogue ID and all present pricing fields numeric finite zero; prompt/completion required"}
            result["live_probe"]["models_checked"] = True
        except Exception as exc:
            errors.append({"endpoint": "/api/v1/models", "error": safe_error(exc, secrets=(token,))})
    if probe_live and token:
        try:
            payload = (http_get or _default_http_get)(base + "/api/v1/key", _headers(token), 30)
            data = payload.get("data", {})
            quota = data.get("free_model_daily_requests") if isinstance(data, Mapping) else None
            if isinstance(quota, Mapping):
                result["limits"]["free_model_daily_requests"] = {key: quota.get(key) if isinstance(quota.get(key), int) and not isinstance(quota.get(key), bool) and quota.get(key) >= 0 else None for key in ("used", "limit", "remaining")}
            result["live_probe"]["key_status_checked"] = True
        except Exception as exc:
            errors.append({"endpoint": "/api/v1/key", "error": safe_error(exc, secrets=(token,))})
    if include_models or probe_live:
        result["live_probe"]["status"] = "error" if errors else "ok"
        result["live_probe"]["errors"] = errors
    return redact(result, secrets=(token,))


def chat_completion_packet(
    prompt: str,
    config: Mapping[str, Any] | None = None,
    *,
    http_post: HttpPost | None = None,
    http_get: HttpGet | None = None,
) -> dict[str, Any]:
    """
    Run one explicit OpenRouter chat completion and return a redacted receipt packet.

    The default candidate is `openrouter/free`; its current catalogue entry
    must verify zero pricing. Paid calls are disabled in this standalone adapter.
    """
    cfg = dict(config or {})
    api_key = _resolve_api_key(cfg)
    base_url = _official_base_url(cfg)
    model = str(_config_value(cfg, "model", "OPENROUTER_CHAT_MODEL", DEFAULT_CHAT_MODEL) or "").strip()
    if not model:
        model = DEFAULT_CHAT_MODEL
    timeout_s = _positive_int(_config_value(cfg, "timeout_s", "OPENROUTER_CHAT_TIMEOUT_S", DEFAULT_CHAT_TIMEOUT_S), default=DEFAULT_CHAT_TIMEOUT_S)
    max_tokens = _positive_int(cfg.get("max_tokens"), default=DEFAULT_CHAT_MAX_TOKENS)
    temperature = cfg.get("temperature", 0)
    gate = _paid_gate(cfg, model)
    messages = _chat_messages(prompt, cfg)
    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "stream": False,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    for key in (
        "top_p",
        "seed",
        "response_format",
        "stop",
        "tools",
        "tool_choice",
        "provider",
        "reasoning",
        "include_reasoning",
        "max_completion_tokens",
        "verbosity",
    ):
        if key in cfg and cfg[key] is not None:
            payload[key] = cfg[key]
    overrides = cfg.get("payload_overrides")
    if isinstance(overrides, Mapping):
        payload.update(overrides)

    model = str(payload.get("model") or model)
    gate = _paid_gate(cfg, model)
    if not gate["paid_call_authorized"]:
        if payload.get("models") or payload.get("plugins"):
            raise RuntimeError("free-only calls cannot add fallback models or paid plugins")
        provider = dict(payload.get("provider") or {})
        provider["max_price"] = {"prompt": 0, "completion": 0, "request": 0}
        payload["provider"] = provider

    selected = verified_free_model(model, config=cfg, http_get=http_get)
    context_length = _as_float(selected.get("context_length"))
    if context_length is not None and math.isfinite(context_length) and context_length > 0:
        estimated_input_tokens = max(1, sum(len(str(message.get("content", ""))) for message in messages) // 4)
        if estimated_input_tokens + max_tokens > context_length:
            raise RuntimeError("prompt plus output budget exceeds selected model context limit (input estimate uses characters/4)")
    cache_key = _chat_cache_key(
        model=model,
        messages=messages,
        max_tokens=max_tokens,
        temperature=temperature,
    )
    poster = http_post or _default_http_post
    started_at = _utc_now()
    try:
        data = poster(f"{base_url}/api/v1/chat/completions", _chat_headers(api_key, cfg), payload, timeout_s)
    except Exception as exc:
        raise RuntimeError(safe_error(exc, secrets=(api_key,))) from None
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        raise RuntimeError("OpenRouter chat response did not include choices")
    first = choices[0]
    if not isinstance(first, Mapping):
        raise RuntimeError("OpenRouter chat response choice is malformed")
    message = first.get("message")
    if not isinstance(message, Mapping):
        raise RuntimeError("OpenRouter chat response did not include a message")
    text = _normalize_message_content(message.get("content"))
    if not text:
        text = _normalize_message_content(message.get("reasoning_content"))
    if not text:
        text = _normalize_message_content(message.get("reasoning"))
    empty_response = not bool(text)

    packet = {
        "kind": "openrouter_chat_completion",
        "schema_version": "openrouter_chat_completion_packet_v1",
        "status": "ok",
        "generated_at": _utc_now(),
        "started_at": started_at,
        "base_url": base_url,
        "model": data.get("model"),
        "requested_model": model,
        "provider": data.get("provider"),
        "generation_id": data.get("id"),
        "latency_seconds": max(0.0, (datetime.now(timezone.utc) - datetime.fromisoformat(started_at.replace("Z", "+00:00"))).total_seconds()),
        "free_or_paid_gate": gate,
        "cache_key": cache_key,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "usage": data.get("usage") if isinstance(data.get("usage"), Mapping) else {},
        "choices_seen": len(choices),
        "finish_reason": first.get("finish_reason"),
        "empty_response": empty_response,
        "message_keys": sorted(str(key) for key in message.keys()),
        "response_text": text,
        "context_length": selected.get("context_length"),
        "catalogue_pricing": selected.get("pricing"),
        "endpoint": base_url + "/api/v1/chat/completions",
        "cost": (data.get("usage") or {}).get("cost") if isinstance(data.get("usage"), Mapping) else None,
    }
    return redact(packet, secrets=(api_key,))


def chat_completion(
    prompt: str,
    config: Mapping[str, Any] | None = None,
    *,
    http_post: HttpPost | None = None,
) -> str:
    """Return only the assistant text for callers that use ask_ai-style providers."""
    return str(chat_completion_packet(prompt, config, http_post=http_post)["response_text"])


def _atomic_write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f"{path.name}.", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(redact(payload), handle, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _write_named_receipt(
    repo_root: Path,
    payload: Mapping[str, Any],
    *,
    state_root: str = DEFAULT_STATE_ROOT,
    latest_name: str,
    ledger_name: str,
) -> dict[str, str]:
    root = Path(repo_root) / state_root
    latest = root / latest_name
    ledger = root / ledger_name
    _atomic_write_json(latest, dict(payload))
    ledger.parent.mkdir(parents=True, exist_ok=True)
    with ledger.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(redact(dict(payload)), ensure_ascii=False, sort_keys=True) + "\n")
    return {
        "latest": str(latest.relative_to(repo_root)),
        "ledger": str(ledger.relative_to(repo_root)),
    }


def write_probe_receipt(
    repo_root: Path,
    payload: Mapping[str, Any],
    *,
    state_root: str = DEFAULT_STATE_ROOT,
) -> dict[str, str]:
    refs = _write_named_receipt(
        repo_root,
        payload,
        state_root=state_root,
        latest_name="latest_probe.json",
        ledger_name="probe_ledger.jsonl",
    )
    return {
        "latest_probe": refs["latest"],
        "probe_ledger": refs["ledger"],
    }


def write_opportunities_receipt(
    repo_root: Path,
    payload: Mapping[str, Any],
    *,
    state_root: str = DEFAULT_STATE_ROOT,
) -> dict[str, str]:
    refs = _write_named_receipt(
        repo_root,
        payload,
        state_root=state_root,
        latest_name="latest_opportunities.json",
        ledger_name="opportunities_ledger.jsonl",
    )
    return {
        "latest_opportunities": refs["latest"],
        "opportunities_ledger": refs["ledger"],
    }


def write_chat_receipt(
    repo_root: Path,
    payload: Mapping[str, Any],
    *,
    state_root: str = DEFAULT_STATE_ROOT,
) -> dict[str, str]:
    refs = _write_named_receipt(
        repo_root,
        payload,
        state_root=state_root,
        latest_name="latest_chat_smoke.json",
        ledger_name="chat_smoke_ledger.jsonl",
    )
    return {
        "latest_chat_smoke": refs["latest"],
        "chat_smoke_ledger": refs["ledger"],
    }


def smoke_openrouter_chat(
    repo_root: Path,
    *,
    prompt: str = "Reply with exactly OPENROUTER_OK.",
    write: bool = False,
    config: Mapping[str, Any] | None = None,
    http_post: HttpPost | None = None,
) -> dict[str, Any]:
    payload = chat_completion_packet(prompt, config=config, http_post=http_post)
    payload["smoke_completed_at"] = _utc_now()
    if write:
        payload["artifact_refs"] = write_chat_receipt(repo_root, payload)
    return payload


def probe_openrouter_free_models(
    repo_root: Path,
    *,
    top_n: int = DEFAULT_TOP_N,
    write: bool = False,
    config: Mapping[str, Any] | None = None,
    http_get: HttpGet | None = None,
) -> dict[str, Any]:
    payload = runtime_status(
        config=config,
        probe_live=True,
        include_models=True,
        top_n=top_n,
        http_get=http_get,
    )
    payload["probe_completed_at"] = _utc_now()
    payload["docs_assumptions"] = {
        "consulted_at": time.strftime("%Y-%m-%d", time.gmtime()),
        "free_variant_rpm": FREE_MODEL_BURST_RPM,
        "free_tier_daily_requests": FREE_TIER_REQUESTS_PER_DAY,
        "paid_history_free_variant_daily_requests": PAID_HISTORY_FREE_REQUESTS_PER_DAY,
    }
    if write:
        payload["artifact_refs"] = write_probe_receipt(repo_root, payload)
    return payload


def probe_openrouter_model_opportunities(
    repo_root: Path,
    *,
    top_n: int = DEFAULT_TOP_N,
    write: bool = False,
    config: Mapping[str, Any] | None = None,
    http_get: HttpGet | None = None,
) -> dict[str, Any]:
    status = runtime_status(
        config=config,
        probe_live=True,
        include_models=True,
        top_n=top_n,
        http_get=http_get,
    )
    models = status.get("models") if isinstance(status.get("models"), Mapping) else {}
    payload: dict[str, Any] = {
        "kind": "openrouter_model_opportunities",
        "schema_version": "openrouter_model_opportunities_packet_v1",
        "generated_at": _utc_now(),
        "configured": status.get("configured") or {},
        "policy": status.get("policy") or {},
        "limits": status.get("limits") or {},
        "live_probe": status.get("live_probe") or {},
        "key_info": status.get("key_info") or {},
        "model_opportunities": models.get("opportunity_snapshot") or {},
        "docs_assumptions": {
            "consulted_at": time.strftime("%Y-%m-%d", time.gmtime()),
            "free_variant_rpm": FREE_MODEL_BURST_RPM,
            "free_tier_daily_requests": FREE_TIER_REQUESTS_PER_DAY,
            "paid_history_free_variant_daily_requests": PAID_HISTORY_FREE_REQUESTS_PER_DAY,
        },
    }
    if write:
        payload["artifact_refs"] = write_opportunities_receipt(repo_root, payload)
    return payload
