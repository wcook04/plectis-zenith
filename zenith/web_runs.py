"""Bounded, read-only projection of local Zenith run records for a web adapter.

This module does no HTTP, network, provider, configuration, or write operations.
The caller chooses the runs directory and supplies the authored node ID allowlist.
"""

from __future__ import annotations

import json
import os
import re
import stat
from pathlib import Path
from typing import Any

MAX_ARTIFACT_BYTES = 8 * 1024 * 1024
MAX_ATTEMPT_BYTES = 128_000
MAX_SUMMARY_BYTES = 64_000
MAX_PAGE_SIZE = 100
_RUN_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,119}\Z")
_ATTEMPT_SUFFIX = re.compile(r"\.attempt_\d{2}\.json\Z")


def _object(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _text(value: Any, limit: int) -> str | None:
    return value[:limit] if isinstance(value, str) else None


def _bounded_text(value: Any, limit: int) -> tuple[str | None, bool]:
    if not isinstance(value, str):
        return None, False
    return value[:limit], len(value) > limit


def _plain_scalar(value: Any) -> str | int | float | None:
    return value if isinstance(value, (str, int, float)) and not isinstance(value, bool) else None


def _subject_ref(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    name = Path(value).name
    return name if _RUN_ID.fullmatch(name) and name not in {".", ".."} else None


def _safe_dir(path: Path) -> bool:
    try:
        mode = path.lstat().st_mode
    except FileNotFoundError:
        return False
    return stat.S_ISDIR(mode)


def _read_json(path: Path, max_bytes: int) -> tuple[Any | None, str | None, int | None]:
    """Return (JSON, error code, byte size); never follow a final symlink."""
    try:
        mode = path.lstat().st_mode
    except FileNotFoundError:
        return None, "missing", None
    if not stat.S_ISREG(mode):
        return None, "not_regular_file", None
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
        try:
            size = os.fstat(descriptor).st_size
            if size > max_bytes:
                return None, "too_large", size
            with os.fdopen(os.dup(descriptor), "rb") as stream:
                content = stream.read(max_bytes + 1)
        finally:
            os.close(descriptor)
    except (OSError, PermissionError):
        return None, "unreadable", None
    if len(content) > max_bytes:
        return None, "too_large", len(content)
    def reject_constant(value: str):
        raise ValueError("Nonfinite JSON number")
    try:
        return json.loads(content, parse_constant=reject_constant), None, len(content)
    except (UnicodeDecodeError, ValueError):
        return None, "malformed_json", len(content)


class RunStore:
    """Read saved native/conditional runs through an authored-node allowlist."""

    def __init__(self, runs_root: Path, allowed_node_ids: set[str]):
        self.runs_root = Path(runs_root).absolute()
        self.allowed_node_ids = frozenset(allowed_node_ids)

    @staticmethod
    def _run_id(value: str) -> str:
        if not isinstance(value, str) or not _RUN_ID.fullmatch(value) or value in {".", ".."}:
            raise ValueError("run_id must be a simple local name")
        return value

    def _run_dir(self, run_id: str) -> Path:
        self._run_id(run_id)
        if not _safe_dir(self.runs_root):
            raise FileNotFoundError("runs directory unavailable")
        run_dir = self.runs_root / run_id
        if not _safe_dir(run_dir):
            raise FileNotFoundError("run not found")
        return run_dir

    def _summary(self, run_id: str) -> dict[str, Any]:
        run_dir = self._run_dir(run_id)
        raw, error, _ = _read_json(run_dir / "run_summary.json", MAX_SUMMARY_BYTES)
        if error == "missing":
            raise FileNotFoundError("run summary not found")
        if error:
            raise ValueError(f"run summary {error}")
        summary = _object(raw)
        if not summary:
            raise ValueError("run summary invalid")
        marker, _, _ = _read_json(run_dir / "zenith_run.json", MAX_SUMMARY_BYTES)
        conditional, _, _ = _read_json(run_dir / "conditional_lab.json", MAX_SUMMARY_BYTES)
        marker = _object(marker)
        conditional = _object(conditional)
        outcomes = _object(summary.get("node_outcomes"))
        node_outcomes = {
            key: value[:60] for key, value in outcomes.items()
            if key in self.allowed_node_ids and isinstance(value, str)
        }
        native_mission = marker.get("mission")
        if conditional:
            mission, source_kind = "lab", "conditional_lab"
        elif isinstance(native_mission, str) and native_mission in {"lab", "oracle", "refinement"}:
            mission, source_kind = native_mission, "native_run"
        else:
            raise ValueError("run marker missing or invalid")
        return {
            "run_id": run_id,
            "mission": mission,
            "source_kind": source_kind,
            "subject_run": _subject_ref(conditional.get("subject_run")),
            "grade": _text(summary.get("grade"), 60),
            "grade_reason": _text(summary.get("grade_reason"), 400),
            "timestamp": _plain_scalar(summary.get("timestamp")),
            "node_outcomes": node_outcomes,
        }

    def list_runs(self, query: str = "", mission: str | None = None, limit: int = 40, offset: int = 0) -> dict[str, Any]:
        if not isinstance(query, str) or len(query) > 200:
            raise ValueError("query must be a short string")
        if mission not in {None, "lab", "oracle", "refinement"}:
            raise ValueError("invalid mission")
        if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= MAX_PAGE_SIZE:
            raise ValueError("limit must be 1..100")
        if not isinstance(offset, int) or isinstance(offset, bool) or offset < 0:
            raise ValueError("offset must be nonnegative")
        if not _safe_dir(self.runs_root):
            return {"runs": [], "total": 0, "limit": limit, "offset": offset}
        needle = query.casefold()
        runs = []
        for entry in self.runs_root.iterdir():
            if not _RUN_ID.fullmatch(entry.name) or entry.name in {".", ".."} or not _safe_dir(entry):
                continue
            if needle not in entry.name.casefold():
                continue
            try:
                item = self._summary(entry.name)
            except (FileNotFoundError, ValueError):
                continue
            if mission is None or item["mission"] == mission:
                runs.append(item)
        def order(item: dict[str, Any]) -> tuple[str, str]:
            timestamp = item["timestamp"]
            sortable = f"{timestamp:020.6f}" if isinstance(timestamp, (int, float)) else str(timestamp or "")
            return (sortable, item["run_id"])
        runs.sort(key=order, reverse=True)
        return {"runs": runs[offset:offset + limit], "total": len(runs), "limit": limit, "offset": offset}

    def node_evidence(self, run_id: str, node_id: str) -> dict[str, Any]:
        if not isinstance(node_id, str) or node_id not in self.allowed_node_ids:
            raise ValueError("unknown node_id")
        run_dir = self._run_dir(run_id)
        summary = self._summary(run_id)
        artifacts_dir = run_dir / "artifacts"
        artifact_raw, artifact_error, artifact_bytes = (None, "missing", None)
        if _safe_dir(artifacts_dir):
            artifact_raw, artifact_error, artifact_bytes = _read_json(
                artifacts_dir / f"{node_id}.json", MAX_ARTIFACT_BYTES
            )
        elif artifacts_dir.is_symlink():
            artifact_error = "unsafe_path"
        artifact_obj = _object(artifact_raw)
        metadata = _object(artifact_obj.get("metadata"))
        artifact = None
        if artifact_obj:
            inputs = metadata.get("input_node_ids")
            artifact = {
                "status": _text(artifact_obj.get("status"), 60),
                "timestamp": _plain_scalar(artifact_obj.get("timestamp")),
                "metadata": {
                    "error": _text(metadata.get("error"), 4000),
                    "hydrated_from": _text(metadata.get("hydrated_from"), 250),
                    "input_node_ids": [item for item in inputs if isinstance(item, str) and item in self.allowed_node_ids][:55]
                    if isinstance(inputs, list) else [],
                },
                "data": artifact_obj.get("data"),
            }
        elif artifact_error is None:
            artifact_error = "invalid_artifact"
        attempts_dir = run_dir / "debug" / "json_attempts"
        attempts: list[dict[str, Any]] = []
        if _safe_dir(run_dir / "debug") and _safe_dir(attempts_dir):
            names = sorted(
                (entry for entry in attempts_dir.iterdir()
                 if entry.name.startswith(f"{node_id}.attempt_")
                 and _ATTEMPT_SUFFIX.search(entry.name) and entry.is_file() and not entry.is_symlink()),
                key=lambda entry: entry.name,
            )[-3:]
            for path in names:
                raw, error, size = _read_json(path, MAX_ATTEMPT_BYTES)
                if error:
                    attempts.append({"file": path.name, "error": error, "bytes": size})
                    continue
                value = _object(raw)
                prompt, prompt_truncated = _bounded_text(value.get("prompt_snippet"), 8000)
                output, output_truncated = _bounded_text(value.get("output_text"), 16_000)
                json_error = value.get("json_error")
                if not isinstance(json_error, str) and json_error is not None:
                    json_error = json.dumps(json_error, ensure_ascii=False)
                errors = value.get("errors")
                attempts.append({
                    "attempt": value.get("attempt") if isinstance(value.get("attempt"), int) else None,
                    "status": _text(value.get("status"), 60),
                    "error_class": _text(value.get("error_class"), 150),
                    "errors": [_text(item, 1000) for item in errors[:20] if isinstance(item, str)] if isinstance(errors, list) else [],
                    "json_error": _text(json_error, 2000),
                    "prompt_sha256": _text(value.get("prompt_sha256"), 100),
                    "prompt_length": value.get("prompt_length") if isinstance(value.get("prompt_length"), int) else None,
                    "prompt_snippet": prompt,
                    "prompt_truncated": prompt_truncated,
                    "output_length": value.get("output_length") if isinstance(value.get("output_length"), int) else None,
                    "output_text": output,
                    "output_truncated": output_truncated,
                })
        return {
            "run_id": run_id,
            "node_id": node_id,
            "status": summary["node_outcomes"].get(node_id) or (artifact or {}).get("status") or "not_started",
            "source_kind": summary["source_kind"],
            "subject_run": summary["subject_run"],
            "artifact": artifact,
            "artifact_bytes": artifact_bytes,
            "artifact_omitted": artifact_error == "too_large",
            "artifact_error": artifact_error,
            "attempts": attempts,
        }
