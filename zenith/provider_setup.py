"""Own-key setup and metadata checks; never sends an inference request."""
from __future__ import annotations

import os
from system.lib import openrouter_free_runtime as openrouter
from .providers import NVIDIA_ENDPOINT


def check(*, provider="openrouter_free", env_file=None, offline=False, check_key=False, http_get=None):
    if env_file:
        openrouter.load_env_file(env_file)
    if provider == "nvidia_nim":
        return {"schema": "zenith_provider_check_v1", "provider": provider,
                "key_configured": bool(os.environ.get("NVIDIA_API_KEY")), "endpoint": NVIDIA_ENDPOINT,
                "models": [], "catalogue_status": "select_from_official_documentation",
                "model_reference": "https://docs.api.nvidia.com/nim/reference/llm-apis",
                "pricing": "unknown; this integration does not provision an account or claim a free quota",
                "inference_performed": False}
    payload = openrouter.runtime_status(probe_live=check_key and not offline, include_models=not offline,
                                       top_n=200, http_get=http_get)
    return openrouter.redact({"schema": "zenith_provider_check_v1", "provider": provider,
        "key_configured": payload["configured"]["api_key_present"], "endpoint": openrouter.DEFAULT_BASE_URL,
        "catalogue_status": payload["live_probe"]["status"],
        "models": payload.get("models", {}).get("ranked_free_models", []),
        "key_status_checked": payload["live_probe"]["key_status_checked"],
        "free_model_daily_requests": payload["limits"]["free_model_daily_requests"],
        "errors": payload["live_probe"].get("errors", []), "inference_performed": False,
        "policy": "exact current catalogue entry with fully verified zero pricing; no paid models or fallbacks"})
