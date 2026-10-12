"""
[PURPOSE]
- Teleology: Guard the runtime grade path that now treats additive feed-quality
  blockers and warnings as authoritative run-grade inputs.
- Mechanism: Use a lightweight harness around `GodModeEngine._calculate_run_grade`
  with large-enough synthetic tool artifacts so the feed-quality branch is the
  deciding signal rather than the existing 5KB tool-size gate.

[INTERFACE]
- Tests GodModeEngine._calculate_run_grade with _GradeHarness and synthetic stock artifacts.

[FLOW]
- Mechanism: Write a tool artifact above the legacy size gate, set quality block/warn tones, and assert red/amber grade and reason.

[DEPENDENCIES]
- system.core.engine, CodexNode/NodeType, and temporary artifact JSON.

[CONSTRAINTS]
- Writes: Temporary fixture artifact files; no feed run or full GodModeEngine execution.
"""

from __future__ import annotations

import json
from pathlib import Path

from system.core.engine import GodModeEngine
from system.lib.types import CodexNode, NodeType


class _GradeHarness:
    def __init__(self, artifacts_dir: Path) -> None:
        self.artifacts_dir = artifacts_dir
        self._node_outcomes = {"global_stock_feed": "success"}
        self._execution_scope = {"global_stock_feed"}
        self._universe = {
            "global_stock_feed": CodexNode(
                id="global_stock_feed",
                type=NodeType.TOOL,
                group="feeds",
                lane="STOCK",
                teleology="test",
                expectation="",
                is_artifact=True,
            )
        }

    def _extract_integrity_override(self) -> str | None:
        return None


def _write_tool_artifact(artifacts_dir: Path, tone: str, reason: str) -> None:
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    (artifacts_dir / "global_stock_feed.json").write_text(
        json.dumps(
            {
                "id": "global_stock_feed",
                "status": "success",
                "metadata": {
                    "status": "success",
                    "quality": {"tone": tone, "reasons": [reason]},
                },
                "data": {"blob": "x" * 7000},
            }
        ),
        encoding="utf-8",
    )


def test_engine_grade_turns_red_on_feed_quality_block(tmp_path: Path) -> None:
    artifacts_dir = tmp_path / "artifacts"
    _write_tool_artifact(
        artifacts_dir,
        "block",
        "provider returned 1 HTML landing-page responses",
    )
    harness = _GradeHarness(artifacts_dir)

    grade, reason = GodModeEngine._calculate_run_grade(harness)

    assert grade == "red"
    assert reason.startswith("Feed quality blocker")


def test_engine_grade_turns_amber_on_feed_quality_warn(tmp_path: Path) -> None:
    artifacts_dir = tmp_path / "artifacts"
    _write_tool_artifact(
        artifacts_dir,
        "warn",
        "legacy provider fallback used; stock stayed usable but is degraded",
    )
    harness = _GradeHarness(artifacts_dir)

    grade, reason = GodModeEngine._calculate_run_grade(harness)

    assert grade == "amber"
    assert reason.startswith("Feed quality warning")
