"""
[PURPOSE]
- Teleology: Validate the engine's Phase 3 JSON enforcement, checkpoint validation, and retry loop logic.
- Mechanism: Unit tests that mock the Bridge and PhysicalLoader to test _exec_reasoning branching,
  fence stripping, JSON parsing, CP1/CP2 validation, retry correction prompts, and artifact data persistence.
- Non-goal: Full end-to-end engine execution or LLM interaction testing.

[INTERFACE]
- Reads: GodModeEngine class, _strip_json_fences, _build_correction_prompt, _validate_schema_output.
- Writes: Temporary run/config/feed and engine artifact fixtures under tmp_path; bridge/loader collaborators are mocked.

[FLOW]
- Fixtures: Provides minimal CP1/CP2 payloads and mock engine construction.
- Tests: Regression cases covering text mode, JSON mode, CP1/CP2 validation, retry loop, correction prompt,
  fence stripping, alias coercion, artifact data type, and subject_run_dir resolution.
- When-needed: Open when debugging engine-side JSON/schema enforcement, correction-prompt retries, subject-run resolution, or feed-compression behavior in backend execution.
- Escalates-to: system/core/engine.py; system/lib/schema_validator.py; codex/contracts/contract_config.json
- Navigation-group: server_backend

[DEPENDENCIES]
- Python stdlib: json, unittest.mock, pathlib, logging.
- Internal: system.lib.schema_validator (validate_cp1, validate_cp2, ValidationResult).
- Internal: system.lib.types (CodexNode, NodeType, RunMode, ExecutionMode).

[CONSTRAINTS]
- Tests must not perform real LLM calls; all Bridge interactions are mocked.
- Tests must not depend on external dependencies (requests, websocket-client, etc.)
  and must mock/patch the Bridge import to avoid ImportError.
- Non-goal: This suite does not validate real provider transport or full run orchestration.
"""
from __future__ import annotations

import json
import hashlib
import logging
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from system.lib.schema_validator import ValidationResult, validate_cp1, validate_cp2
from system.lib.types import CodexNode, NodeType


# ---------------------------------------------------------------------------
# Fixture builders (reused from test_schema_validator.py patterns)
# ---------------------------------------------------------------------------

def _words(n: int, cite: str = "") -> str:
    """Generate n whitespace-separated tokens, optionally appending a citation string."""
    base = " ".join(f"word{i}" for i in range(n))
    return f"{base} {cite}".strip() if cite else base


def _minimal_evidence_cp1() -> List[Dict[str, Any]]:
    return [
        {"ref_id": "[1]", "ledger_id": "M_DEADBEEF", "subject": "ENVIRONMENT_REGIME", "signal_summary": "A environment signal."},
        {"ref_id": "[2]", "ledger_id": "S_CAFEBABE", "subject": "SUBSYSTEM_C", "signal_summary": "SUBSYSTEM_C measurements signal."},
    ]


def _minimal_cp1_payload() -> Dict[str, Any]:
    return {
        "evidence_dictionary": _minimal_evidence_cp1(),
        "epicentre_thesis": _words(148, "[1] [2]"),
    }


def _minimal_cp2_payload() -> Dict[str, Any]:
    base = _minimal_cp1_payload()
    base["predictions_t"] = [
        {
            "target_id": "SUBSYSTEM_C",
            "direction": "DOWN",
            "unit": "dimensionless", "snapshot_value": 100.0,
            "target_value": 95.0,
            "invalidation": "Invalidated if SUBSYSTEM_C reclaims VWAP and holds above 197 by 15:30 ET.",
        }
    ]
    base["forecast_rationale"] = _words(103, "[1] [2]")
    return base


def _minimal_realized_hindsight_brief_payload() -> Dict[str, Any]:
    return {
        "status": "AVAILABLE",
        "realized_dominant_force": "Oil shock continuation with partial residual change.",
        "regime_summary": "Energy led realized upside while residual breadth stayed constrained.",
        "driver_classification": [
            {
                "driver": "Oil shock continuation",
                "classification": "PARTIAL_CHANGE",
                "why": "Continuation was visible at T-n, but the final magnitude still surprised.",
                "supporting_lanes": ["MEASUREMENTS", "SUBSYSTEMS", "ENVIRONMENT"],
                "affected_targets": ["SIGNAL_A", "XLE"],
            }
        ],
        "already_observed_packages": ["Baseline energy continuation"],
        "surprise_packages": ["Residual supply squeeze"],
        "partial_change_packages": ["Oil shock continuation"],
        "prediction_target_outcomes": [
            {
                "target_id": "SIGNAL_A",
                "what_happened": "SIGNAL_A rallied but by less than the forward target implied.",
                "availability_judgement": "PARTIAL_CHANGE",
            }
        ],
    }


def _minimal_cp2_critique_payload() -> Dict[str, Any]:
    return {
        "status": "AVAILABLE",
        "root_failure_mode": "valued_in_continuation_bias",
        "critique_items": [
            {
                "scope": "prediction",
                "target_or_claim": "SIGNAL_A",
                "subject_grounding_refs": ["[1]", "S_CAFEBABE"],
                "realized_refs": ["prediction_reconciliation:SIGNAL_A"],
                "error_class": "PREDICTION_DRIFT",
                "what_was_wrong": "The target level overstated residual upside.",
                "comparison_to_ideal": "Ideal CP2 should have kept the name but narrowed the magnitude.",
            }
        ],
        "comparison_to_ideal_summary": "Lab generally found the right lane but overshot the consequence sizing.",
        "reconstruction_guidance": {
            "dominant_force": "Residual energy continuation",
            "prefer_targets": ["SIGNAL_A"],
            "avoid_targets": ["UAL"],
            "eligible_ledger_ids": ["S_CAFEBABE"],
        },
    }


def _write_measurements_feed(artifacts_dir: Path, target_ids: List[str]) -> None:
    """Write a minimal MEASUREMENTS feed artifact for CP2 universe check."""
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    feed = {
        "metadata": {"as_of": "2026-01-01"},
        "data": {
            "topic": {
                "row": {
                    "columns": ["target_id", "Value"],
                    "rows": [[t, "100.0"] for t in target_ids],
                }
            }
        },
    }
    (artifacts_dir / "global_measurements_feed.json").write_text(json.dumps(feed))


def _write_subject_snapshot_cp_artifact(artifacts_dir: Path) -> None:
    """Write a minimal CP artifact that seeds the Golden-ID snapshot ledger set."""
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "evidence_dictionary": [
            {
                "ref_id": "[1]",
                "ledger_id": "M_DEADBEEF",
                "subject": "ENVIRONMENT_REGIME",
                "signal_summary": "Environment snapshot evidence.",
            },
            {
                "ref_id": "[2]",
                "ledger_id": "S_CAFEBABE",
                "subject": "SUBSYSTEM_C",
                "signal_summary": "Measurements snapshot evidence.",
            },
        ]
    }
    envelope = {"metadata": {"as_of": "2026-01-01"}, "data": payload}
    (artifacts_dir / "lab_director.json").write_text(json.dumps(envelope))


# ---------------------------------------------------------------------------
# Minimal CodexNode construction
# ---------------------------------------------------------------------------

def _make_node(
    output_schema: str = "text",
    retries: int = 1,
    node_id: str = "test_node",
) -> MagicMock:
    """
    Create a minimal CodexNode-like mock with the fields _exec_reasoning needs.
    Using a MagicMock avoids the need for importing/constructing a full CodexNode
    which would pull in governance and loader dependencies.
    """
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
    node.is_artifact = True
    node.meta = {}
    return node


# ---------------------------------------------------------------------------
# Minimal engine construction (mocks Bridge and Loader)
# ---------------------------------------------------------------------------

def _make_engine(
    tmp_path: Path,
    oracle_subject_run_dir: str | None = None,
    oracle_truth_run_dir: str | None = None,
):
    """
    [ACTION]
    - Teleology: Build a fully mocked `GodModeEngine` suitable for JSON/schema enforcement tests without touching real bridge or loader dependencies.
    - Mechanism: Create a temporary repo root and minimal master_config, patch Bridge and PhysicalLoader during engine construction, then return the engine with a controllable mock bridge instance attached.
    - Reads: Temporary config files under tmp_path plus the engine constructor path in system.core.engine.
    - Writes: Minimal repo/config directories inside tmp_path.
    - Guarantee: Returns an engine whose bridge calls are fully mockable and whose run directory is isolated to the temporary fixture root.
    - Fails: Propagates engine-construction failures if the mocked bootstrap contract drifts.
    - When-needed: Open when many JSON-enforcement tests start failing and the first question is whether the shared mocked engine builder still matches the engine constructor contract.
    - Escalates-to: system/core/engine.py::GodModeEngine; system/lib/schema_validator.py
    """
    # We need to mock the Bridge import before importing engine
    # to avoid the requests/websocket ImportError.
    mock_bridge_cls = MagicMock()
    mock_bridge_instance = MagicMock()
    mock_bridge_cls.return_value = mock_bridge_instance
    # mock_bridge_instance.manager.ask_ai will be set per test

    mock_loader = MagicMock()
    mock_loader.hydrate_graph.return_value = {}

    # Create necessary directories
    root_dir = tmp_path / "project"
    root_dir.mkdir()
    state_dir = root_dir / "state" / "runs"
    state_dir.mkdir(parents=True)

    # Write a minimal master_config.json
    config = {
        "execution": {"retries": {"value": 1}, "max_workers": {"value": 1}},
        "bridge": {},
        "paths": {"runs_dir": "state/runs"},
        "ui": {"lane_colors": {}},
    }
    (root_dir / "master_config.json").write_text(json.dumps(config))
    if oracle_subject_run_dir and oracle_truth_run_dir is None:
        oracle_truth_run_dir = oracle_subject_run_dir

    with patch("system.core.engine.Bridge", mock_bridge_cls), \
         patch("system.core.engine.PhysicalLoader", return_value=mock_loader):
        from system.core.engine import GodModeEngine
        engine = GodModeEngine(
            run_id="test_run",
            root_dir=str(root_dir),
            oracle_subject_run_dir=oracle_subject_run_dir,
            oracle_truth_run_dir=oracle_truth_run_dir,
        )

    # Replace bridge with our mock so we can control ask_ai
    engine.bridge = mock_bridge_instance
    return engine


# ---------------------------------------------------------------------------
# TESTS: Fence stripping
# ---------------------------------------------------------------------------

class TestStripJsonFences:
    def test_clean_json_fenced(self):
        from system.core.engine import GodModeEngine
        raw = '```json\n{"key": "value"}\n```'
        assert GodModeEngine._strip_json_fences(raw) == '{"key": "value"}'

    def test_plain_fenced(self):
        from system.core.engine import GodModeEngine
        raw = '```\n{"key": "value"}\n```'
        assert GodModeEngine._strip_json_fences(raw) == '{"key": "value"}'

    def test_no_fences(self):
        from system.core.engine import GodModeEngine
        raw = '{"key": "value"}'
        assert GodModeEngine._strip_json_fences(raw) == '{"key": "value"}'

    def test_partial_fences_not_stripped(self):
        """If there's prose around fences, don't strip — let json.loads fail."""
        from system.core.engine import GodModeEngine
        raw = 'Here is the JSON:\n```json\n{"key": "value"}\n```\nThat was it.'
        # Should NOT strip because the text doesn't start with ```
        result = GodModeEngine._strip_json_fences(raw)
        assert result == raw.strip()

    def test_whitespace_padded(self):
        from system.core.engine import GodModeEngine
        raw = '  \n```json\n{"key": "value"}\n```  \n  '
        assert GodModeEngine._strip_json_fences(raw) == '{"key": "value"}'


# ---------------------------------------------------------------------------
# TESTS: Correction prompt
# ---------------------------------------------------------------------------

class TestBuildCorrectionPrompt:
    def test_includes_errors(self):
        from system.core.engine import GodModeEngine
        prompt = GodModeEngine._build_correction_prompt(
            "Original prompt", ["MISSING_FIELD: foo", "INVALID_REF_ID: bar"], '{"bad": true}'
        )
        assert "[SYSTEM_CORRECTION]" in prompt
        assert "MISSING_FIELD: foo" in prompt
        assert "INVALID_REF_ID: bar" in prompt
        assert '{"bad": true}' in prompt
        assert "Original prompt" in prompt

    def test_truncates_large_output(self):
        from system.core.engine import GodModeEngine
        large_output = "x" * 20000
        prompt = GodModeEngine._build_correction_prompt(
            "Prompt", ["ERR"], large_output
        )
        assert "[TRUNCATED" in prompt
        # SHA256 prefix is included
        expected_hash = hashlib.sha256(large_output.encode()).hexdigest()[:12]
        assert expected_hash in prompt
        # Output should be capped to ~8192 + overhead
        assert len(prompt) < len(large_output)

    def test_short_output_not_truncated(self):
        from system.core.engine import GodModeEngine
        short_output = '{"valid": false}'
        prompt = GodModeEngine._build_correction_prompt(
            "Prompt", ["ERR"], short_output
        )
        assert "[TRUNCATED" not in prompt
        assert short_output in prompt


# ---------------------------------------------------------------------------
# TESTS: Text mode (unchanged behavior)
# ---------------------------------------------------------------------------

class TestTextModeUnchanged:
    def test_text_schema_returns_raw_string(self, tmp_path):
        engine = _make_engine(tmp_path)
        node = _make_node(output_schema="text")
        engine.bridge.manager.ask_ai.return_value = "This is plain text response."

        meta, data = engine._exec_reasoning(node, {}, {"platform": "chatgpt"})

        assert isinstance(data, str)
        assert data == "This is plain text response."
        assert meta.get("model") == "chatgpt"


# ---------------------------------------------------------------------------
# TESTS: JSON mode (parse only, no CP validation)
# ---------------------------------------------------------------------------

class TestJsonMode:
    def test_json_parse_success(self, tmp_path):
        engine = _make_engine(tmp_path)
        node = _make_node(output_schema="json")
        engine.bridge.manager.ask_ai.return_value = '{"key": "value"}'

        meta, data = engine._exec_reasoning(node, {}, {"platform": "chatgpt"})

        assert isinstance(data, dict)
        assert data == {"key": "value"}

    def test_json_parse_failure_hard_fail(self, tmp_path):
        from system.core.engine import LogicalFailure
        engine = _make_engine(tmp_path)
        node = _make_node(output_schema="json", retries=1)
        engine.bridge.manager.ask_ai.return_value = "not valid json at all"

        with pytest.raises(LogicalFailure, match="JSON/schema validation"):
            engine._exec_reasoning(node, {}, {"platform": "chatgpt"})

    def test_json_parse_fenced_success(self, tmp_path):
        engine = _make_engine(tmp_path)
        node = _make_node(output_schema="json")
        engine.bridge.manager.ask_ai.return_value = '```json\n{"key": "value"}\n```'

        meta, data = engine._exec_reasoning(node, {}, {"platform": "chatgpt"})

        assert isinstance(data, dict)
        assert data == {"key": "value"}


# ---------------------------------------------------------------------------
# TESTS: CP1 validation
# ---------------------------------------------------------------------------

class TestCP1Validation:
    def test_cp1_validation_success(self, tmp_path):
        engine = _make_engine(tmp_path)
        node = _make_node(output_schema="isomorphic_cp1")
        payload = _minimal_cp1_payload()
        engine.bridge.manager.ask_ai.return_value = json.dumps(payload)

        meta, data = engine._exec_reasoning(node, {}, {"platform": "chatgpt"})

        assert isinstance(data, dict)
        assert data["evidence_dictionary"] == payload["evidence_dictionary"]

    def test_cp1_validation_failure_retry_success(self, tmp_path):
        engine = _make_engine(tmp_path)
        node = _make_node(output_schema="isomorphic_cp1", retries=2)

        # First call returns invalid payload, second returns valid
        invalid_payload = {"evidence_dictionary": [], "epicentre_thesis": "too short"}
        valid_payload = _minimal_cp1_payload()
        engine.bridge.manager.ask_ai.side_effect = [
            json.dumps(invalid_payload),
            json.dumps(valid_payload),
        ]

        meta, data = engine._exec_reasoning(node, {}, {"platform": "chatgpt"})

        assert isinstance(data, dict)
        assert data == valid_payload
        assert engine.bridge.manager.ask_ai.call_count == 2

    def test_cp1_retry_exhaustion_hard_fail(self, tmp_path):
        from system.core.engine import LogicalFailure
        engine = _make_engine(tmp_path)
        node = _make_node(output_schema="isomorphic_cp1", retries=2)

        invalid_payload = {"evidence_dictionary": [], "epicentre_thesis": "too short"}
        engine.bridge.manager.ask_ai.return_value = json.dumps(invalid_payload)

        with pytest.raises(LogicalFailure, match="JSON/schema validation"):
            engine._exec_reasoning(node, {}, {"platform": "chatgpt"})

        assert engine.bridge.manager.ask_ai.call_count == 2


# ---------------------------------------------------------------------------
# TESTS: CP2 validation
# ---------------------------------------------------------------------------

class TestCP2Validation:
    def test_cp2_validation_success(self, tmp_path):
        engine = _make_engine(tmp_path)
        _write_measurements_feed(engine.run_dir / "artifacts", ["SUBSYSTEM_C", "SUBSYSTEM_A", "SIGNAL_B"])
        node = _make_node(output_schema="isomorphic_cp2")
        payload = _minimal_cp2_payload()
        engine.bridge.manager.ask_ai.return_value = json.dumps(payload)

        meta, data = engine._exec_reasoning(node, {}, {"platform": "chatgpt"})

        assert isinstance(data, dict)
        assert "predictions_t" in data

    def test_cp2_validation_with_oracle_subject_run_dir(self, tmp_path):
        # Create a fake "lab run" with measurements feed for universe check
        lab_run_dir = tmp_path / "lab_run"
        lab_run_dir.mkdir()
        _write_measurements_feed(lab_run_dir / "artifacts", ["SUBSYSTEM_C", "SUBSYSTEM_A", "SIGNAL_B"])
        _write_subject_snapshot_cp_artifact(lab_run_dir / "artifacts")

        engine = _make_engine(tmp_path, oracle_subject_run_dir=str(lab_run_dir))
        node = _make_node(output_schema="isomorphic_cp2")
        payload = _minimal_cp2_payload()
        engine.bridge.manager.ask_ai.return_value = json.dumps(payload)

        meta, data = engine._exec_reasoning(node, {}, {"platform": "chatgpt"})

        assert isinstance(data, dict)
        assert data["predictions_t"][0]["target_id"] == "SUBSYSTEM_C"

    def test_cp2_out_of_universe_via_oracle_dir(self, tmp_path):
        """Oracle subject_run_dir has feed without SUBSYSTEM_C → OUT_OF_UNIVERSE → hard-fail."""
        from system.core.engine import LogicalFailure

        lab_run_dir = tmp_path / "lab_run"
        lab_run_dir.mkdir()
        _write_measurements_feed(lab_run_dir / "artifacts", ["SUBSYSTEM_A", "SIGNAL_B"])  # no SUBSYSTEM_C
        _write_subject_snapshot_cp_artifact(lab_run_dir / "artifacts")

        engine = _make_engine(tmp_path, oracle_subject_run_dir=str(lab_run_dir))
        node = _make_node(output_schema="isomorphic_cp2", retries=1)
        payload = _minimal_cp2_payload()
        engine.bridge.manager.ask_ai.return_value = json.dumps(payload)

        with pytest.raises(LogicalFailure, match="JSON/schema validation"):
            engine._exec_reasoning(node, {}, {"platform": "chatgpt"})


class TestOracleStructuredJsonValidation:
    def test_realized_hindsight_brief_validation_success(self, tmp_path):
        engine = _make_engine(tmp_path)
        node = _make_node(
            output_schema="schema_realized_hindsight_brief",
            node_id="oracle_truth_map",
        )
        payload = _minimal_realized_hindsight_brief_payload()
        engine.bridge.manager.ask_ai.return_value = json.dumps(payload)

        meta, data = engine._exec_reasoning(node, {}, {"platform": "chatgpt"})

        assert isinstance(data, dict)
        assert data["status"] == "AVAILABLE"
        assert data["driver_classification"][0]["classification"] == "PARTIAL_CHANGE"

    def test_cp2_critique_validation_failure_retry_success(self, tmp_path):
        engine = _make_engine(tmp_path)
        node = _make_node(
            output_schema="schema_cp2_critique",
            retries=2,
            node_id="oracle_attribution_map",
        )
        invalid_payload = {
            "status": "AVAILABLE",
            "root_failure_mode": "valued_in_continuation_bias",
            "critique_items": [{"scope": "bad_scope"}],
        }
        valid_payload = _minimal_cp2_critique_payload()
        engine.bridge.manager.ask_ai.side_effect = [
            json.dumps(invalid_payload),
            json.dumps(valid_payload),
        ]

        meta, data = engine._exec_reasoning(node, {}, {"platform": "chatgpt"})

        assert isinstance(data, dict)
        assert data["critique_items"][0]["scope"] == "prediction"
        assert engine.bridge.manager.ask_ai.call_count == 2


# ---------------------------------------------------------------------------
# TESTS: Alias coercion
# ---------------------------------------------------------------------------

class TestAliasCoercion:
    def test_isomorphic_v1_alias_coercion(self, tmp_path, caplog):
        engine = _make_engine(tmp_path)
        _write_measurements_feed(engine.run_dir / "artifacts", ["SUBSYSTEM_C", "SUBSYSTEM_A", "SIGNAL_B"])
        node = _make_node(output_schema="isomorphic_v1")
        payload = _minimal_cp2_payload()
        engine.bridge.manager.ask_ai.return_value = json.dumps(payload)

        with caplog.at_level(logging.WARNING):
            meta, data = engine._exec_reasoning(node, {}, {"platform": "chatgpt"})

        assert isinstance(data, dict)
        # Check that warning was logged about alias
        assert any("isomorphic_v1" in record.message for record in caplog.records)


# ---------------------------------------------------------------------------
# TESTS: subject_run_dir resolution
# ---------------------------------------------------------------------------

class TestSubjectRunDirResolution:
    def test_defaults_to_run_dir(self, tmp_path):
        engine = _make_engine(tmp_path, oracle_subject_run_dir=None)
        assert engine._subject_run_dir == engine.run_dir

    def test_uses_oracle_dir_when_provided(self, tmp_path):
        oracle_path = tmp_path / "oracle_lab_run"
        oracle_path.mkdir()
        oracle_dir = str(oracle_path)
        engine = _make_engine(tmp_path, oracle_subject_run_dir=oracle_dir)
        assert engine._subject_run_dir == Path(oracle_dir)
        assert engine._truth_run_dir == Path(oracle_dir)


# ---------------------------------------------------------------------------
# TESTS: Runtime config injection for tools
# ---------------------------------------------------------------------------

class TestToolRuntimeConfigInjection:
    def test_tool_runtime_includes_stable_anchor_and_run_id(self, tmp_path):
        engine = _make_engine(tmp_path)
        node = _make_node()
        node.type = NodeType.TOOL
        node.config = {"module": "tools.derived.derived"}

        merged = engine._merge_runtime_config(node)

        runtime = merged.get("runtime", {})
        assert runtime.get("run_id") == "test_run"
        assert runtime.get("time_anchor") == engine._run_anchor_iso
        assert runtime.get("as_of") == engine._run_anchor_iso
        assert runtime.get("effective_date") == engine._run_anchor_iso

    def test_tool_runtime_preserves_explicit_anchor_override(self, tmp_path):
        engine = _make_engine(tmp_path)
        node = _make_node()
        node.type = NodeType.TOOL
        node.config = {
            "module": "tools.environment.environment",
            "runtime": {
                "time_anchor": "2025-01-01T00:00:00+00:00",
                "lookback_years": 5,
            },
        }

        merged = engine._merge_runtime_config(node)

        runtime = merged.get("runtime", {})
        assert runtime.get("time_anchor") == "2025-01-01T00:00:00+00:00"
        assert runtime.get("lookback_years") == 5
        assert runtime.get("run_id") == "test_run"

    def test_oracle_tool_runtime_includes_subject_and_truth_dirs(self, tmp_path):
        subject_dir = tmp_path / "subject_run"
        truth_dir = tmp_path / "truth_run"
        subject_dir.mkdir()
        truth_dir.mkdir()
        engine = _make_engine(
            tmp_path,
            oracle_subject_run_dir=str(subject_dir),
            oracle_truth_run_dir=str(truth_dir),
        )
        node = _make_node()
        node.type = NodeType.TOOL
        node.config = {"module": "tools.oracle.subject_index"}

        merged = engine._merge_runtime_config(node)

        runtime = merged.get("runtime", {})
        assert runtime.get("oracle_mode") is True
        assert runtime.get("oracle_subject_run_dir") == str(subject_dir)
        assert runtime.get("oracle_truth_run_dir") == str(truth_dir)


class TestOracleFeedHydration:
    def test_oracle_feed_nodes_hydrate_from_truth_run(self, tmp_path):
        subject_dir = tmp_path / "subject_run"
        truth_dir = tmp_path / "truth_run"
        subject_dir.mkdir()
        truth_dir.mkdir()
        _write_measurements_feed(subject_dir / "artifacts", ["SUBJ"])
        _write_measurements_feed(truth_dir / "artifacts", ["TRUTH"])

        engine = _make_engine(
            tmp_path,
            oracle_subject_run_dir=str(subject_dir),
            oracle_truth_run_dir=str(truth_dir),
        )
        node = _make_node(node_id="global_measurements_feed")
        node.type = NodeType.TOOL
        node.meta = {"is_feed": True}
        node.config = {"module": "tools.measurements.measurements"}

        meta, data = engine._exec_tool(node, {}, {"platform": "chatgpt"})

        assert meta.get("hydrated_from_truth") == str(truth_dir)
        assert data["topic"]["row"]["rows"][0][0] == "TRUTH"


# ---------------------------------------------------------------------------
# TESTS: Execution scope resolution
# ---------------------------------------------------------------------------

class TestExecutionScopeResolution:
    def test_scope_includes_group_siblings_and_target_dependencies(self, tmp_path):
        engine = _make_engine(tmp_path)
        engine._universe = {
            "global_derived_feed": CodexNode(
                id="global_derived_feed",
                type=NodeType.TOOL,
                group="feeds",
                dependencies=("global_measurements_feed", "global_environment_feed"),
            ),
            "global_measurements_feed": CodexNode(
                id="global_measurements_feed",
                type=NodeType.TOOL,
                group="feeds",
                dependencies=(),
            ),
            "global_environment_feed": CodexNode(
                id="global_environment_feed",
                type=NodeType.TOOL,
                group="feeds",
                dependencies=(),
            ),
            "global_events_feed": CodexNode(
                id="global_events_feed",
                type=NodeType.TOOL,
                group="feeds",
                dependencies=(),
            ),
            "lab_director": CodexNode(
                id="lab_director",
                type=NodeType.REASONING,
                group="lab",
                dependencies=(),
            ),
        }

        engine._resolve_execution_scope("global_derived_feed")

        assert "global_derived_feed" in engine._execution_scope
        assert "global_measurements_feed" in engine._execution_scope
        assert "global_environment_feed" in engine._execution_scope
        assert "global_events_feed" in engine._execution_scope
        assert "lab_director" not in engine._execution_scope

    def test_scope_includes_upstream_dependencies_outside_group(self, tmp_path):
        engine = _make_engine(tmp_path)
        engine._universe = {
            "global_derived_feed": CodexNode(
                id="global_derived_feed",
                type=NodeType.TOOL,
                group="feeds",
                dependencies=("global_measurements_feed",),
            ),
            "global_measurements_feed": CodexNode(
                id="global_measurements_feed",
                type=NodeType.TOOL,
                group="feeds",
                dependencies=("shared_seed",),
            ),
            "shared_seed": CodexNode(
                id="shared_seed",
                type=NodeType.TOOL,
                group="core",
                dependencies=(),
            ),
        }

        engine._resolve_execution_scope("global_derived_feed")

        assert "shared_seed" in engine._execution_scope


# ---------------------------------------------------------------------------
# TESTS: Artifact data type verification
# ---------------------------------------------------------------------------

class TestArtifactDataType:
    def test_json_mode_returns_parsed_dict(self, tmp_path):
        """For JSON modes, _exec_reasoning returns a dict, not a raw string."""
        engine = _make_engine(tmp_path)
        node = _make_node(output_schema="json")
        engine.bridge.manager.ask_ai.return_value = '{"result": 42}'

        meta, data = engine._exec_reasoning(node, {}, {"platform": "chatgpt"})

        assert isinstance(data, dict)
        assert data["result"] == 42
        # NOT a string
        assert not isinstance(data, str)

    def test_cp1_mode_returns_parsed_dict(self, tmp_path):
        """CP1 mode returns parsed dict for artifact persistence."""
        engine = _make_engine(tmp_path)
        node = _make_node(output_schema="isomorphic_cp1")
        payload = _minimal_cp1_payload()
        engine.bridge.manager.ask_ai.return_value = json.dumps(payload)

        meta, data = engine._exec_reasoning(node, {}, {"platform": "chatgpt"})

        assert isinstance(data, dict)
        assert "evidence_dictionary" in data
        assert "epicentre_thesis" in data


# ---------------------------------------------------------------------------
# TESTS: Web search contract injection (Deliverable 2)
# ---------------------------------------------------------------------------

def _make_node_with_tools(
    tools: list,
    output_schema: str = "text",
    *,
    node_id: str = "test_node",
) -> MagicMock:
    """Create a node mock with a specific tools list."""
    node = _make_node(output_schema=output_schema, node_id=node_id)
    node.execution = {"retries": 1, "tools": tools}
    return node


class TestWebSearchContractInjection:
    """
    [ROLE]
    - Teleology: Group the regression checks that guard web-search contract injection inside engine reasoning prompts.
    - Ownership: Covers the prompt-assembly branch in `GodModeEngine._exec_reasoning`.
    - Mutability: Stateless test grouping container.
    - Concurrency: Safe under parallel test execution because each case uses a fresh mocked engine.
    - When-needed: Open when prompt-policy drift is suspected around the `web_search` tool toggle rather than schema validation itself.
    - Escalates-to: system/core/engine.py::GodModeEngine._exec_reasoning; system/core/bridge.py
    """

    def _captured_prompt(self, engine, node) -> str:
        """Run _exec_reasoning and return the prompt that was sent to ask_ai."""
        captured = []

        def _intercept(prompt, config=None, cancel=None, **kwargs):
            captured.append(prompt)
            return "result text"

        engine.bridge.manager.ask_ai.side_effect = _intercept
        engine._exec_reasoning(node, {}, {"platform": "chatgpt"})
        return captured[0]

    def test_no_web_search_injects_disabled_contract(self, tmp_path):
        """Toggle OFF: prompt must contain disabled contract text and nothing from enabled."""
        engine = _make_engine(tmp_path)
        node = _make_node_with_tools(tools=[])

        prompt = self._captured_prompt(engine, node)

        assert "Web Search Policy: DISABLED" in prompt
        assert "Do not browse the internet" in prompt
        assert "Web Search Policy: ENABLED" not in prompt

    def test_web_search_tool_injects_enabled_contract(self, tmp_path):
        """Toggle ON: prompt must contain enabled contract text and nothing from disabled."""
        engine = _make_engine(tmp_path)
        node = _make_node_with_tools(tools=["web_search"])

        prompt = self._captured_prompt(engine, node)

        assert "Web Search Policy: ENABLED" in prompt
        assert "search the internet" in prompt
        assert "Web Search Policy: DISABLED" not in prompt

    def test_ab_contract_swap_no_prompt_drift(self, tmp_path):
        """A/B: both prompts are identical except for the web search policy block."""
        (tmp_path / "off").mkdir()
        (tmp_path / "on").mkdir()
        engine_off = _make_engine(tmp_path / "off")
        engine_on = _make_engine(tmp_path / "on")

        node_off = _make_node_with_tools(tools=[])
        node_on = _make_node_with_tools(tools=["web_search"])
        node_off.instruction = "Shared instruction text"
        node_on.instruction = "Shared instruction text"

        prompt_off = self._captured_prompt(engine_off, node_off)
        prompt_on = self._captured_prompt(engine_on, node_on)

        # Both must contain the shared instruction
        assert "Shared instruction text" in prompt_off
        assert "Shared instruction text" in prompt_on

        # The only difference must be in the WEB_SEARCH_POLICY block
        # Strip the policy block from both and assert everything else is equal
        def _strip_policy(p: str) -> str:
            import re
            return re.sub(r"\n\n\[WEB_SEARCH_POLICY\]\n.*", "", p, flags=re.DOTALL).strip()

        assert _strip_policy(prompt_off) == _strip_policy(prompt_on)

    def test_oracle_mode_raises_on_web_search_tool(self, tmp_path):
        """Oracle hard-stop: LogicalFailure raised before any contract is injected."""
        from system.core.engine import LogicalFailure
        oracle_path = tmp_path / "lab_run"
        oracle_path.mkdir()
        oracle_dir = str(oracle_path)
        engine = _make_engine(tmp_path, oracle_subject_run_dir=oracle_dir)
        node = _make_node_with_tools(tools=["web_search"], node_id="oracle_truth_map")

        with pytest.raises(LogicalFailure, match="Only oracle_explain"):
            engine._exec_reasoning(node, {}, {"platform": "chatgpt"})

    def test_oracle_explain_is_allowed_to_use_web_search(self, tmp_path):
        oracle_path = tmp_path / "lab_run"
        oracle_path.mkdir()
        oracle_dir = str(oracle_path)
        engine = _make_engine(tmp_path, oracle_subject_run_dir=oracle_dir)
        node = _make_node_with_tools(
            tools=["web_search"],
            output_schema="json",
            node_id="oracle_explain",
        )
        engine.bridge.manager.ask_ai.return_value = '{"status":"OPTIONAL","explanatory_notes":[],"no_new_grounding_claims":true}'

        meta, data = engine._exec_reasoning(node, {}, {"platform": "chatgpt"})

        assert meta.get("model") == "chatgpt"
        assert data["status"] == "OPTIONAL"


def test_gather_inputs_preserves_every_dense_observation_for_reasoning_nodes(tmp_path: Path) -> None:
    engine = _make_engine(tmp_path)
    engine.artifacts_dir.mkdir(parents=True, exist_ok=True)
    rows = [[f"TARGET_{idx:03d}",float(idx-50),"dimensionless"] for idx in range(100)]
    envelope={"metadata":{"tool":"local_observations"},"data":{"columns":["target_id","Value","unit"],"rows":rows}}
    (engine.artifacts_dir/"global_measurements_feed.json").write_text(json.dumps(envelope))
    node=MagicMock();node.dependencies=("global_measurements_feed",);node.type=NodeType.REASONING
    projected=engine._gather_inputs(node)["global_measurements_feed"]
    assert projected["data"]["rows"]==rows
    assert len(projected["data"]["rows"])==100
    assert "prompt_input_compression" not in projected.get("metadata",{})


def test_gather_inputs_preserves_full_measurements_feed_for_oracle_mode(tmp_path: Path) -> None:
    oracle_path = tmp_path / "subject_run"
    oracle_path.mkdir()
    engine = _make_engine(tmp_path, oracle_subject_run_dir=str(oracle_path))
    artifacts_dir = engine.artifacts_dir
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    rows = [
        ["tech", f"T{idx:03d}", f"target_id {idx}", 100.0 + idx, 0.2, float(idx), float(idx), 0.5, 0.25]
        for idx in range(60)
    ]
    envelope = {
        "metadata": {"tool": "measurements", "diagnostics": {}},
        "data": {
            "columns": ["Category", "target_id", "Identity", "Value", "Vol_20d", "Chg_5d", "Chg_63d", "Z_Short", "Z_Long"],
            "rows": rows,
        },
    }
    (artifacts_dir / "global_measurements_feed.json").write_text(json.dumps(envelope), encoding="utf-8")

    node = MagicMock()
    node.dependencies = ("global_measurements_feed",)
    node.type = NodeType.REASONING

    inputs = engine._gather_inputs(node)

    assert len(inputs["global_measurements_feed"]["data"]["rows"]) == 60
    assert "semantic_compression" not in inputs["global_measurements_feed"]["data"]
