"""
[PURPOSE]
- Teleology: Validate the engine's error resilience upgrades: selective stop-event guard,
  empty extraction pre-guard, and per-attempt forensic metadata tracking.
- Mechanism: Unit tests that mock the Bridge and PhysicalLoader to isolate the three
  new behaviors without requiring real LLM calls.

[INTERFACE]
- Reads: GodModeEngine._write_artifact, _exec_reasoning, LogicalFailure.
- Writes: Temporary artifacts in tmp_path.

[FLOW]
- Build a mocked engine and harness -> trigger selective stop, extraction, retry, and bridge-failure scenarios -> assert artifacts and failure metadata preserve the expected forensic fields.
- When-needed: Open when debugging engine retry forensics, stop-event artifact behavior, or bridge failure metadata retention in the backend runtime.
- Escalates-to: system/core/engine.py; system/core/bridge.py; system/lib/schema_validator.py
- Navigation-group: server_backend

[DEPENDENCIES]
- Python stdlib: json, threading, hashlib, logging, pathlib, unittest.mock.
- Internal: system.lib.types (CodexNode, NodeType, StepStatus).
- Internal: system.core.engine (GodModeEngine, LogicalFailure) — mocked Bridge/Loader.

[CONSTRAINTS]
- Guarantee: All bridge and loader interactions are mocked, so failures isolate engine error-handling semantics rather than external providers.
- Non-goal: This suite does not validate real bridge transport or full DAG scheduling.
"""
from __future__ import annotations

import hashlib
import json
import logging
import threading
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

import pytest

from system.core.bridge import NodeFailure
from system.core.engine import GodModeEngine, LogicalFailure
from system.lib.types import CodexNode, NodeType, StepStatus


# ---------------------------------------------------------------------------
# Harness & Helpers (reused patterns from test_engine_artifact_provenance.py)
# ---------------------------------------------------------------------------

class _EngineHarness:
    """
    [ROLE]
    - Teleology: Supply the minimal state `_write_artifact()` and related helper paths inspect during resilience tests.
    - Ownership: Local helper shared by the stop-guard and artifact-forensics scenarios in this module.
    - Mutability: Mutable per-test harness with a small set of engine-like fields.
    - Concurrency: Not shared across tests; one harness instance per scenario.
    - When-needed: Open when a failure suggests `_write_artifact()` now depends on more engine state than this resilience harness provides.
    - Escalates-to: system/core/engine.py::GodModeEngine._write_artifact; system/server/tests/test_engine_artifact_provenance.py::_EngineHarness
    """
    def __init__(self, artifacts_dir: Path) -> None:
        self._stop_event = threading.Event()
        self.artifacts_dir = artifacts_dir
        self.logger = logging.getLogger("tests.engine_error_resilience")
        self._node_outcomes: Dict[str, str] = {}
        self._manifest: Dict[str, Any] = {}
        self._force_load_stale_feeds = False
        self._target_time_iso = None
        self._horizon_label = None


def _make_harness_node(node_id: str = "test_node") -> CodexNode:
    return CodexNode(
        id=node_id,
        type=NodeType.REASONING,
        is_artifact=False,
    )


def _make_engine(tmp_path: Path):
    """Construct a GodModeEngine with mocked dependencies."""
    mock_bridge_cls = MagicMock()
    mock_bridge_instance = MagicMock()
    mock_bridge_cls.return_value = mock_bridge_instance
    mock_loader = MagicMock()
    mock_loader.hydrate_graph.return_value = {}

    root_dir = tmp_path / "project"
    root_dir.mkdir()
    state_dir = root_dir / "state" / "runs"
    state_dir.mkdir(parents=True)

    config = {
        "execution": {"retries": {"value": 1}, "max_workers": {"value": 1}},
        "bridge": {},
        "paths": {"runs_dir": "state/runs"},
        "ui": {"lane_colors": {}},
    }
    (root_dir / "master_config.json").write_text(json.dumps(config))

    with patch("system.core.engine.Bridge", mock_bridge_cls), \
         patch("system.core.engine.PhysicalLoader", return_value=mock_loader):
        engine = GodModeEngine(
            run_id="test_run",
            root_dir=str(root_dir),
        )

    engine.bridge = mock_bridge_instance
    return engine


def _make_node(
    output_schema: str = "json",
    retries: int = 1,
    node_id: str = "test_node",
) -> MagicMock:
    node = MagicMock()
    node.id = node_id
    node.instruction = "Test prompt"
    node.output_schema = output_schema
    node.execution = {"retries": retries}
    node.lane = "MEASUREMENTS"
    node.config = {}
    node.config_ref = ""
    node.merged_hash = ""
    node.inline_overrides = {}
    node.platform = "chatgpt"
    node.teleology = "test"
    node.group = "test_group"
    node.expectation = ""
    node.is_artifact = False
    node.meta = {}
    return node


def _make_tool_node(node_id: str = "global_measurements_feed") -> CodexNode:
    return CodexNode(
        id=node_id,
        type=NodeType.TOOL,
        group="feeds",
        lane="MEASUREMENTS",
        teleology="test",
        expectation="",
        is_artifact=True,
        meta={"is_feed": True},
        config={"module": "tools.measurements.measurements"},
    )


# ---------------------------------------------------------------------------
# TESTS: Selective Stop-Event Guard
# ---------------------------------------------------------------------------

class TestSelectiveStopGuard:
    def test_failure_artifact_written_after_stop(self, tmp_path):
        """FAILURE artifacts MUST be written even when stop is set."""
        artifacts_dir = tmp_path / "artifacts"
        artifacts_dir.mkdir(parents=True, exist_ok=True)

        harness = _EngineHarness(artifacts_dir)
        harness._stop_event.set()  # Simulate stop signal

        node = _make_harness_node("stopped_node")

        GodModeEngine._write_artifact(
            harness, node, StepStatus.FAILURE,
            {"error": "retry exhausted"}, None, error="retry exhausted",
        )

        artifact_path = artifacts_dir / "stopped_node.json"
        assert artifact_path.exists(), "Failure artifact must be written even after stop"
        artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
        assert artifact["status"] == StepStatus.FAILURE.value
        assert artifact["metadata"]["error"] == "retry exhausted"

    def test_success_artifact_blocked_after_stop(self, tmp_path):
        """SUCCESS artifacts MUST NOT be written when stop is set (zombie prevention)."""
        artifacts_dir = tmp_path / "artifacts"
        artifacts_dir.mkdir(parents=True, exist_ok=True)

        harness = _EngineHarness(artifacts_dir)
        harness._stop_event.set()  # Simulate stop signal

        node = _make_harness_node("zombie_node")

        GodModeEngine._write_artifact(
            harness, node, StepStatus.SUCCESS,
            {"model": "test"}, {"data": "should not persist"},
        )

        artifact_path = artifacts_dir / "zombie_node.json"
        assert not artifact_path.exists(), "Success artifact must be blocked after stop"


# ---------------------------------------------------------------------------
# TESTS: Empty Extraction Pre-Guard
# ---------------------------------------------------------------------------

class TestEmptyExtractionGuard:
    def test_empty_extraction_retries_cleanly(self, tmp_path, caplog):
        """Empty bridge response triggers EMPTY_EXTRACTION, retries, and succeeds on valid response."""
        engine = _make_engine(tmp_path)
        node = _make_node(output_schema="json", retries=2)

        # First call returns empty, second returns valid JSON
        engine.bridge.manager.ask_ai.side_effect = [
            "",
            '{"key": "value"}',
        ]

        with caplog.at_level(logging.WARNING):
            meta, data = engine._exec_reasoning(node, {}, {"platform": "chatgpt"})

        assert isinstance(data, dict)
        assert data == {"key": "value"}
        assert engine.bridge.manager.ask_ai.call_count == 2
        assert any("EMPTY_EXTRACTION" in r.message or "empty extraction" in r.message
                    for r in caplog.records)

    def test_whitespace_only_extraction_is_caught(self, tmp_path):
        """Whitespace-only response must produce EMPTY_EXTRACTION, not JSON_PARSE_ERROR."""
        engine = _make_engine(tmp_path)
        node = _make_node(output_schema="json", retries=1)

        engine.bridge.manager.ask_ai.return_value = "   \n  \t  "

        with pytest.raises(LogicalFailure, match="JSON/schema validation") as exc_info:
            engine._exec_reasoning(node, {}, {"platform": "chatgpt"})

        # The artifact_metadata should have an attempt_log with EMPTY_EXTRACTION
        meta = getattr(exc_info.value, "artifact_metadata", {})
        assert "EMPTY_EXTRACTION" in meta.get("validation_errors", [""])[0]
        attempt_log = meta.get("attempt_log", [])
        assert len(attempt_log) == 1
        assert attempt_log[0]["error_class"] == "EMPTY_EXTRACTION"


# ---------------------------------------------------------------------------
# TESTS: Per-Attempt Forensic Metadata
# ---------------------------------------------------------------------------

class TestAttemptLogForensics:
    def test_attempt_log_in_failure_artifact(self, tmp_path):
        """Exhausted retries must produce failure with structured attempt_log."""
        engine = _make_engine(tmp_path)
        node = _make_node(output_schema="json", retries=2)

        engine.bridge.manager.ask_ai.return_value = "not json"

        with pytest.raises(LogicalFailure) as exc_info:
            engine._exec_reasoning(node, {}, {"platform": "chatgpt"})

        meta = getattr(exc_info.value, "artifact_metadata", {})
        attempt_log = meta.get("attempt_log", [])
        assert len(attempt_log) == 2  # Two attempts
        for entry in attempt_log:
            assert "attempt" in entry
            assert "error_class" in entry
            assert "output_sha256" in entry
            assert "output_length" in entry
            assert "errors" in entry
        assert attempt_log[0]["attempt"] == 1
        assert attempt_log[1]["attempt"] == 2

        # artifact_data should also contain attempt_log
        data = getattr(exc_info.value, "artifact_data", {})
        assert "attempt_log" in data

    def test_attempt_log_includes_sha256_per_attempt(self, tmp_path):
        """Each attempt in the log must have a distinct SHA256 when outputs differ."""
        engine = _make_engine(tmp_path)
        node = _make_node(output_schema="json", retries=2)

        # Two different invalid outputs
        engine.bridge.manager.ask_ai.side_effect = [
            "invalid output A",
            "different invalid output B",
        ]

        with pytest.raises(LogicalFailure) as exc_info:
            engine._exec_reasoning(node, {}, {"platform": "chatgpt"})

        meta = getattr(exc_info.value, "artifact_metadata", {})
        attempt_log = meta.get("attempt_log", [])
        assert len(attempt_log) == 2

        sha_1 = attempt_log[0]["output_sha256"]
        sha_2 = attempt_log[1]["output_sha256"]
        assert sha_1 != sha_2, "Different outputs must produce different SHA256 hashes"

        # Verify correctness
        expected_1 = hashlib.sha256("invalid output A".encode("utf-8")).hexdigest()
        expected_2 = hashlib.sha256("different invalid output B".encode("utf-8")).hexdigest()
        assert sha_1 == expected_1
        assert sha_2 == expected_2


def test_tool_failure_artifact_preserves_reported_metadata_and_data(tmp_path: Path) -> None:
    """
    [ACTION]
    - Teleology: Prove tool-node failures preserve the tool-reported metadata and failure payload rather than collapsing them into a generic engine error envelope.
    - Mechanism: Patch `_exec_tool()` to return structured failure metadata/data, execute the node, then assert the persisted failure artifact keeps those fields intact.
    - Reads: Mocked tool failure metadata and the temporary engine artifact directory.
    - Writes: A failure artifact envelope under tmp_path.
    - Guarantee: Verifies structured tool diagnostics survive the engine failure path.
    - Fails: Propagates unexpected execution-path failures outside the intended LogicalFailure.
    - When-needed: Open when a debugger needs the regression that proves engine failure artifacts preserve tool-reported metadata instead of erasing it.
    - Escalates-to: system/core/engine.py::GodModeEngine._execute_node; system/core/engine.py::GodModeEngine._write_artifact
    - Navigation-group: server_backend
    """
    engine = _make_engine(tmp_path)
    node = _make_tool_node()
    engine._universe = {node.id: node}

    failure_meta = {
        "status": "failure",
        "tool": "measurements",
        "schema_version": "1.0",
        "data_schema_version": "measurements.1",
        "error": "No data fetched from measurements source. Check Endpoints.",
        "definitions": {"sec": {"encoding": "integer_enum"}},
        "diagnostics": {
            "input_rows": 0,
            "output_rows": 0,
            "dropped_rows": 0,
            "warnings": [
                "No data fetched from measurements source. Check Endpoints.",
                "signals error: DNS failure",
            ],
        },
    }
    failure_data = {"source_diagnostics": {"errors": ["signals error: DNS failure"]}}

    with patch.object(engine, "_exec_tool", return_value=(failure_meta, failure_data)):
        with pytest.raises(LogicalFailure, match="No data fetched from measurements source"):
            engine._execute_node(node.id)

    artifact = json.loads((engine.artifacts_dir / f"{node.id}.json").read_text(encoding="utf-8"))
    assert artifact["status"] == StepStatus.FAILURE.value
    assert artifact["metadata"]["tool"] == "measurements"
    assert artifact["metadata"]["error"] == "No data fetched from measurements source. Check Endpoints."
    assert artifact["metadata"]["definitions"] == {"sec": {"encoding": "integer_enum"}}
    assert artifact["metadata"]["diagnostics"]["warnings"] == [
        "No data fetched from measurements source. Check Endpoints.",
        "signals error: DNS failure",
    ]
    assert artifact["data"] == failure_data


def test_run_failure_from_node_is_not_logged_as_engine_crash(tmp_path: Path) -> None:
    engine = _make_engine(tmp_path)
    node = _make_tool_node()
    engine.loader.load_all_nodes.return_value = {node.id: node}

    failure_meta = {
        "status": "failure",
        "tool": "measurements",
        "schema_version": "1.0",
        "data_schema_version": "measurements.1",
        "error": "No data fetched from measurements source. Check Endpoints.",
        "diagnostics": {
            "input_rows": 0,
            "output_rows": 0,
            "dropped_rows": 0,
            "warnings": ["No data fetched from measurements source. Check Endpoints."],
        },
    }

    with patch.object(engine, "_exec_tool", return_value=(failure_meta, {})):
        engine.run(target_id=node.id)

    summary = json.loads((engine.run_dir / "run_summary.json").read_text(encoding="utf-8"))
    engine_log = (engine.run_dir / "engine.log").read_text(encoding="utf-8")

    assert summary["grade"] == "red"
    assert summary["grade_reason"] == "Run contains failed nodes"
    assert summary["node_outcomes"][node.id] == StepStatus.FAILURE.value
    assert "Engine Crash" not in engine_log
    assert (
        "Run failed because node global_measurements_feed failed: "
        "No data fetched from measurements source. Check Endpoints."
    ) in engine_log


class TestGlobalJsonDiagnostics:
    def test_json_prompt_includes_engine_guardrail(self, tmp_path):
        """Every JSON-mode call should include the shared engine syntax guardrail."""
        engine = _make_engine(tmp_path)
        node = _make_node(output_schema="json", retries=1)
        captured: Dict[str, str] = {}

        def _ask(prompt: str, config=None, cancel=None):
            captured["prompt"] = prompt
            return '{"ok": true}'

        engine.bridge.manager.ask_ai.side_effect = _ask
        engine._exec_reasoning(node, {}, {"platform": "chatgpt"})

        assert "[ENGINE_JSON_SYNTAX_GUARDRAIL]" in captured["prompt"]

    def test_repeated_invalid_output_short_circuits_retries(self, tmp_path):
        """If a retry repeats the exact same invalid output, stop retrying early."""
        engine = _make_engine(tmp_path)
        node = _make_node(output_schema="json", retries=3)
        engine.bridge.manager.ask_ai.return_value = "not valid json"

        with pytest.raises(LogicalFailure) as exc_info:
            engine._exec_reasoning(node, {}, {"platform": "chatgpt"})

        assert engine.bridge.manager.ask_ai.call_count == 2
        meta = getattr(exc_info.value, "artifact_metadata", {})
        assert meta.get("validation_attempts_configured") == 3
        assert meta.get("validation_attempts_executed") == 2
        assert any("STUCK_RETRY" in e for e in meta.get("validation_errors", []))

    def test_bridge_abort_carries_partial_output_forensics(self, tmp_path):
        """Bridge aborts should preserve prior attempt forensics and partial output."""
        engine = _make_engine(tmp_path)
        node = _make_node(output_schema="json", retries=2)
        abort_error = NodeFailure("Aborted by Engine Signal")
        setattr(abort_error, "bridge_partial_output", '{"partial":"still useful"}')
        engine.bridge.manager.ask_ai.side_effect = [
            "not valid json",
            abort_error,
        ]

        with pytest.raises(NodeFailure) as exc_info:
            engine._exec_reasoning(node, {}, {"platform": "chatgpt"})

        meta = getattr(exc_info.value, "artifact_metadata", {})
        data = getattr(exc_info.value, "artifact_data", {})
        assert meta.get("aborted_on_attempt") == 2
        assert meta.get("bridge_partial_output_sha256")
        assert "bridge_partial_output_snippet" in meta
        assert len(meta.get("partial_attempt_log", [])) == 1
        assert data.get("bridge_partial_output") == '{"partial":"still useful"}'

    def test_failure_data_contains_last_invalid_output_payload(self, tmp_path):
        """Failure artifact payload should include the last invalid raw output."""
        engine = _make_engine(tmp_path)
        node = _make_node(output_schema="json", retries=1)
        invalid = '{"epicentre_thesis": "broken "observation""}'
        engine.bridge.manager.ask_ai.return_value = invalid

        with pytest.raises(LogicalFailure) as exc_info:
            engine._exec_reasoning(node, {}, {"platform": "chatgpt"})

        data = getattr(exc_info.value, "artifact_data", {})
        assert data.get("last_invalid_output") == invalid

    def test_attempt_sidecar_persists_raw_payload(self, tmp_path):
        """Per-attempt sidecar should store raw response text for debugging."""
        engine = _make_engine(tmp_path)
        node = _make_node(output_schema="json", retries=1)
        invalid = '{"epicentre_thesis": "broken "observation""}'
        engine.bridge.manager.ask_ai.return_value = invalid

        with pytest.raises(LogicalFailure) as exc_info:
            engine._exec_reasoning(node, {}, {"platform": "chatgpt"})

        meta = getattr(exc_info.value, "artifact_metadata", {})
        sidecars = meta.get("attempt_sidecars", [])
        assert sidecars, "Expected at least one sidecar path"

        sidecar_path = engine.run_dir / sidecars[0]
        assert sidecar_path.exists(), f"Missing sidecar: {sidecar_path}"
        payload = json.loads(sidecar_path.read_text(encoding="utf-8"))
        assert payload.get("output_text") == invalid

    def test_provider_label_placeholder_classified_as_bridge_extraction_error(self, tmp_path):
        """Provider-label stubs like 'Gemini said' should not be misclassified as JSON parse errors."""
        engine = _make_engine(tmp_path)
        node = _make_node(output_schema="json", retries=1)
        engine.bridge.manager.ask_ai.return_value = "Gemini said"

        with pytest.raises(LogicalFailure) as exc_info:
            engine._exec_reasoning(node, {}, {"platform": "gemini"})

        meta = getattr(exc_info.value, "artifact_metadata", {})
        assert any("BRIDGE_EXTRACTION_ERROR" in err for err in meta.get("validation_errors", []))
        attempt_log = meta.get("attempt_log", [])
        assert attempt_log
        assert attempt_log[0]["error_class"] == "BRIDGE_EXTRACTION_ERROR"

    def test_execute_node_persists_bridge_failure_metadata_into_failure_artifact(self, tmp_path):
        """Node failure artifacts should retain structured bridge category/stage/details."""
        engine = _make_engine(tmp_path)
        node = _make_node(output_schema="text", retries=1, node_id="lab_seed_state")
        node.type = NodeType.REASONING
        engine._universe = {node.id: node}
        engine._execution_scope = {node.id}
        engine._group_map = {node.group: [node.id]}
        engine._gather_inputs = lambda _node: {}
        engine._merge_runtime_config = lambda _node: {"platform": "gemini"}

        engine.bridge.manager.ask_ai.side_effect = NodeFailure(
            "gemini prompt submission failed after 1 transport attempts",
            category="provider_cancelled",
            stage="provider_wait",
            provider="gemini",
            details={
                "attempts": [
                    {
                        "transport": "dom_inject_click",
                        "status": "error",
                        "category": "provider_cancelled",
                        "stage": "provider_wait",
                    }
                ]
            },
        )

        with pytest.raises(NodeFailure):
            engine._execute_node(node.id)

        artifact_path = engine.artifacts_dir / f"{node.id}.json"
        artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
        bridge_failure = artifact["metadata"]["bridge_failure"]
        assert bridge_failure["category"] == "provider_cancelled"
        assert bridge_failure["stage"] == "provider_wait"
        assert bridge_failure["provider"] == "gemini"
        assert bridge_failure["details"]["attempts"][0]["transport"] == "dom_inject_click"
