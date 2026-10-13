"""Provider seams for the original engine; responses never write artifacts directly."""
from __future__ import annotations

import hashlib
import json
import os
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from .provider_policy import require_model, serialized_inference


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def text_digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        with tmp.open("w", encoding="utf-8") as stream:
            json.dump(value, stream, indent=2, ensure_ascii=False, allow_nan=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        tmp.replace(path)
    finally:
        tmp.unlink(missing_ok=True)


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ResponsePending(RuntimeError):
    """The original engine records failure; the command reports a pending handoff."""


class Provider:
    def __init__(self, run_dir: Path):
        self.run_dir = Path(run_dir)
        self.manager = self
        self._lock = threading.Lock()

    def close(self, terminate_browser: bool = False) -> None:
        pass

    def identity(self, prompt: str, config: dict | None) -> dict:
        meta = (config or {}).get("meta", {})
        node_id, run_id = meta.get("node_id"), meta.get("session_id")
        if not isinstance(node_id, str) or not node_id or not isinstance(run_id, str) or not run_id:
            raise ValueError("engine provider metadata requires node_id and session_id")
        if run_id != self.run_dir.name:
            raise ValueError("provider run_id differs from engine run directory")
        return {"run_id": run_id, "node_id": node_id, "prompt_sha256": text_digest(prompt)}

    def receipt(self, identity: dict, **extra: Any) -> None:
        from system.lib.openrouter_free_runtime import redact
        record = redact({"schema": "zenith_provider_attempt_v1", **identity, "recorded_at": now(), **extra})
        write_json(self.run_dir / "handoff" / "receipts" / (uuid.uuid4().hex + ".json"), record)


class AgentProvider(Provider):
    """Durable prompt/response mailbox consumed through engine validation."""

    def ask_ai(self, prompt: str, config: dict | None = None, cancel=None) -> str:
        identity = self.identity(prompt, config)
        packet_id = digest(identity)
        packet_path = self.run_dir / "handoff" / "requests" / (packet_id + ".json")
        packet = {"schema": "zenith_agent_packet_v1", "packet_id": packet_id, **identity,
                  "prompt": prompt, "engine_config": config or {},
                  "instruction": "Return the node output requested by this exact prompt. Import through Zenith; do not edit artifacts."}
        with self._lock:
            if packet_path.exists():
                previous = json.loads(packet_path.read_text())
                if previous != packet:
                    raise ValueError("existing handoff packet differs from engine prompt/config")
            else:
                write_json(packet_path, packet)
        response_path = self.run_dir / "handoff" / "responses" / (packet_id + ".json")
        if not response_path.exists():
            self.receipt(identity, provider="agent", execution_kind="agent", status="pending_response", packet_id=packet_id,
                         requested_model=None, actual_model=None, usage=None, cost=None)
            raise ResponsePending(f"Agent response pending: {packet_path}")
        response = json.loads(response_path.read_text())
        verify_response(packet, response)
        self.receipt(identity, provider="agent", execution_kind="agent", status="response_supplied", packet_id=packet_id,
                     requested_model=response.get("requested_model"), actual_model=response.get("actual_model"),
                     usage=response.get("usage"), cost=response.get("cost"),
                     response_sha256=text_digest(response["response_text"]))
        return response["response_text"]


def verify_packet(packet: dict) -> None:
    if packet.get("schema") != "zenith_agent_packet_v1":
        raise ValueError("unsupported agent packet schema")
    if text_digest(packet.get("prompt", "")) != packet.get("prompt_sha256"):
        raise ValueError("packet prompt hash mismatch")
    identity = {key: packet.get(key) for key in ("run_id", "node_id", "prompt_sha256")}
    if digest(identity) != packet.get("packet_id"):
        raise ValueError("packet identity mismatch")


def verify_response(packet: dict, response: dict) -> None:
    verify_packet(packet)
    for key in ("packet_id", "run_id", "node_id", "prompt_sha256"):
        if response.get(key) != packet.get(key):
            raise ValueError(f"response {key} mismatch")
    if not isinstance(response.get("response_text"), str) or not response["response_text"].strip():
        raise ValueError("nonempty response_text required")


class CapturedProvider(Provider):
    """Replays prompt-bound captured responses, including failure when unavailable."""

    def __init__(self, run_dir: Path, captures: Path | list[dict]):
        super().__init__(run_dir)
        payload = json.loads(Path(captures).read_text()) if isinstance(captures, (str, Path)) else captures
        records = payload.get("responses", []) if isinstance(payload, dict) else payload
        if not isinstance(records, list):
            raise ValueError("captured responses must be a list or an object with responses")
        self.records = {}
        for record in records:
            key = (record["node_id"], record["prompt_sha256"])
            if key in self.records:
                raise ValueError("duplicate captured node/prompt identity")
            if not isinstance(record.get("response_text"), str):
                raise ValueError("captured response_text required")
            self.records[key] = record

    def ask_ai(self, prompt: str, config: dict | None = None, cancel=None) -> str:
        identity = self.identity(prompt, config)
        record = self.records.get((identity["node_id"], identity["prompt_sha256"]))
        if record is None:
            self.receipt(identity, provider="captured", status="missing_capture", actual_model=None,
                         requested_model=None, usage=None, cost=None)
            raise ValueError("no captured response matches exact node and prompt hash")
        if record.get("run_id") not in (None, identity["run_id"]):
            raise ValueError("captured run_id mismatch")
        self.receipt(identity, provider="captured", status="replayed", actual_model=record.get("actual_model"),
                     requested_model=record.get("requested_model"), usage=record.get("usage"),
                     cost=record.get("cost"), execution_kind="captured_replay",
                     response_sha256=text_digest(record["response_text"]))
        return record["response_text"]


class OpenRouterFreeProvider(Provider):
    """Explicit, free-only API calls with durable requested/actual model receipts."""

    def __init__(self, run_dir: Path, model: str | None = None, caller=None):
        super().__init__(run_dir)
        require_model(model)
        if not model.endswith(":free"):
            raise ValueError("OpenRouter free adapter requires an explicit allowlisted :free model ID")
        self.model = model
        self.caller = caller

    @serialized_inference
    def ask_ai(self, prompt: str, config: dict | None = None, cancel=None) -> str:
        identity = self.identity(prompt, config)
        call_id = digest({**identity, "requested_model": self.model})
        call_path = self.run_dir / "handoff" / "api_calls" / "openrouter_free" / (call_id + ".json")
        with self._lock:
            if call_path.exists():
                previous = json.loads(call_path.read_text())
                if previous.get("status") == "response_supplied":
                    packet = previous["provider_receipt"]
                    self.receipt(identity, provider="openrouter_free", status="loaded_previous_response",
                                 requested_model=self.model, actual_model=packet.get("model"),
                                 usage=packet.get("usage"), cost=packet.get("cost"),
                                 response_sha256=text_digest(packet["response_text"]))
                    return packet["response_text"]
                raise RuntimeError("this exact API attempt already failed or was interrupted; it will not be silently resent")
            record = {"schema": "zenith_api_call_v1", **identity, "requested_model": self.model,
                      "status": "attempt_started", "recorded_at": now()}
            write_json(call_path, record)
        self.receipt(identity, provider="openrouter_free", status="attempt_started",
                     requested_model=self.model, actual_model=None, usage=None, cost=None)
        try:
            if cancel is not None and cancel.is_set():
                raise RuntimeError("provider call cancelled")
            caller = self.caller
            if caller is None:
                from system.lib.openrouter_free_runtime import chat_completion_packet
                caller = chat_completion_packet
            packet = caller(prompt, config={"model": self.model, "free_only": True, "allow_paid": False,
                                           "temperature": 0, "max_tokens": 12000, "timeout_s": 120})
            from system.lib.openrouter_free_runtime import redact
            packet = redact(packet)
            require_model(packet.get("model"))
            response = packet["response_text"]
            record.update(status="response_supplied", provider_receipt=packet)
            write_json(call_path, record)
            self.receipt(identity, provider="openrouter_free", status="response_supplied",
                         requested_model=self.model, actual_model=packet.get("model"),
                         usage=packet.get("usage"), cost=packet.get("cost"), provider_receipt=packet,
                         response_sha256=text_digest(response))
            return response
        except Exception as exc:
            from system.lib.openrouter_free_runtime import safe_error
            message = safe_error(exc)
            record.update(status="failed", error=message)
            write_json(call_path, record)
            self.receipt(identity, provider="openrouter_free", status="failed", requested_model=self.model,
                         actual_model=None, usage=None, cost=None, error=record["error"])
            raise RuntimeError(message) from None


NVIDIA_ENDPOINT = "https://integrate.api.nvidia.com/v1/chat/completions"


def _nvidia_http_post(url, headers, payload, timeout_s):
    if url != NVIDIA_ENDPOINT:
        raise RuntimeError("NVIDIA transport requires the official hosted HTTPS endpoint")
    import requests
    from system.lib.openrouter_free_runtime import safe_error
    token = str(headers.get("Authorization", "")).removeprefix("Bearer ")
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=timeout_s, allow_redirects=False)
        if 300 <= response.status_code < 400:
            raise RuntimeError("NVIDIA redirects are disabled")
        response.raise_for_status()
        value = response.json()
        if not isinstance(value, dict):
            raise RuntimeError("NVIDIA returned a non-object JSON response")
        return value
    except Exception as exc:
        raise RuntimeError(safe_error(exc, secrets=(token,))) from None


class NvidiaNimProvider(Provider):
    """Own-key NVIDIA hosted NIM connector; model and account access are explicit."""
    def __init__(self, run_dir: Path, model: str, caller=None):
        super().__init__(run_dir)
        require_model(model)
        raise ValueError("NVIDIA hosted route has unverified pricing; use the price-verified budgeted route")
