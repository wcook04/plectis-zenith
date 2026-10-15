"""JSON readers that reject duplicate object keys and retain source context.

JSONL readers can require object rows, ignore blank lines and treat a missing
file as an empty log. Artifact ownership and rebuild policies belong to their
actual producing tools, rather than this parsing module.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class StrictJsonError(ValueError):
    """Raised when a strict JSON artifact cannot be parsed safely."""


class DuplicateJsonKeyError(StrictJsonError):
    """Raised when a JSON object repeats the same key."""


class StrictJsonObjectError(StrictJsonError):
    """Raised when a JSONL row must be an object but is not."""


def _reject_duplicate_keys(source: str):
    def hook(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        seen: dict[str, Any] = {}
        for key, value in pairs:
            if key in seen:
                raise DuplicateJsonKeyError(f"{source}: duplicate JSON key {key!r}")
            seen[key] = value
        return seen

    return hook


def loads_json_strict(text: str, *, source: str = "<json>") -> Any:
    try:
        return json.loads(text, object_pairs_hook=_reject_duplicate_keys(source))
    except DuplicateJsonKeyError:
        raise
    except json.JSONDecodeError as exc:
        raise StrictJsonError(f"{source}: invalid JSON: {exc}") from exc


def read_json_strict(path: Path) -> Any:
    return loads_json_strict(path.read_text(encoding="utf-8"), source=str(path))


def read_jsonl_strict(path: Path, *, require_object: bool = True) -> list[Any]:
    rows: list[Any] = []
    if not path.exists():
        return rows
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        item = loads_json_strict(line, source=f"{path}:{line_number}")
        if require_object and not isinstance(item, dict):
            raise StrictJsonObjectError(f"{path}:{line_number} is not a JSON object")
        rows.append(item)
    return rows
