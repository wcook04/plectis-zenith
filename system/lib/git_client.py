"""
[PURPOSE]
- Teleology: Provide a thin, non-interactive git utility for reading the HEAD commit hash at run init time.
- Mechanism: subprocess.run wrapper over `git rev-parse HEAD`.
- Non-goal: TUI interaction, branch management, or write operations.

[INTERFACE]
- Exports: get_head_hash(repo_root: Path) -> str
- Inputs: repo_root — absolute path to the repository root
- Outputs: 40-char hex SHA string, or the sentinel string "NO_GIT" on error/non-repo

[FLOW]
- Mechanism: Invoke git rev-parse HEAD with captured output and a bounded timeout; return the nonempty hash or NO_GIT.

[DEPENDENCIES]
- Reads: git executable and repository HEAD; subprocess enforces the timeout.
- Writes: None.

[CONSTRAINTS]
- Must never import rich, prompt_toolkit, or any TUI library.
- Must never raise — all error paths return "NO_GIT".
- Must not mutate the working directory or git state.
- When-needed: Open when runtime provenance capture needs the canonical read-only git HEAD lookup instead of reading broader engine startup code.
- Escalates-to: system/core/engine.py
- Navigation-group: kernel_lib
"""

from __future__ import annotations

import subprocess
from pathlib import Path


def get_head_hash(repo_root: Path) -> str:
    """
    [ACTION]
    - Teleology: Return the full SHA of the current HEAD commit for epistemology locking.
    - Mechanism: Runs `git rev-parse HEAD` in the given repo root via subprocess with
      capture_output=True so it never touches stdin/stdout of the calling process.
    - Preconditions: repo_root is a Path. The directory may or may not be a git repo.
    - Guarantee:
      - Returns the 40-char hex SHA when in a valid git repository with at least one commit.
      - Returns "NO_GIT" in all error cases: non-repo, no commits, git not installed, timeout.
    - Fails: Never raises. All exceptions are swallowed and produce "NO_GIT".
    - When-needed: Open when a caller needs the exact sentinel-on-error contract for stamping run metadata with the current HEAD commit.
    - Escalates-to: system/core/engine.py
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            sha = result.stdout.strip()
            if sha:
                return sha
        return "NO_GIT"
    except Exception:
        return "NO_GIT"
