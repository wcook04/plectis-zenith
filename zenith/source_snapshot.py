"""Source custody without importing an experiment, graph engine or market task.

The archive's member policy deliberately matches the retained broad policy.
This is an ownership extraction, not a smaller historical runtime or a change
of evaluator. Existing archives and their hashes must never be regenerated.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

IMPLEMENTATION_FOLDERS = ("zenith", "system/core", "system/lib", "tools", "variants")
ARCHIVE_SCOPE = ("Python implementation, research runners, native graphs/contracts "
                 "and master configuration; no credentials or run payloads")


def implementation_hashes() -> dict[str, str]:
    """Freeze the same implementation members as the historical runtime API."""
    root = Path(__file__).resolve().parents[1]
    paths = []
    for folder in IMPLEMENTATION_FOLDERS:
        paths.extend((root / folder).rglob("*.py"))
    return {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(paths) if path.is_file()}


def archive_runtime(study: str | Path) -> dict[str, str]:
    """Exclusively create the established source snapshot, without live imports."""
    root = Path(__file__).resolve().parents[1]
    paths = set(implementation_hashes())
    paths.update(str(path.relative_to(root)) for path in (root / "research").rglob("*.py"))
    paths.update(str(path.relative_to(root)) for path in (root / "codex").rglob("*.json"))
    paths.add("master_config.json")
    target = Path(study) / "runtime-source.zip"
    with ZipFile(target, "x", compression=ZIP_DEFLATED) as archive:
        for relative in sorted(paths):
            archive.write(root / relative, relative)
    return {"path": str(target), "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
            "scope": ARCHIVE_SCOPE}
