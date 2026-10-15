"""
[PURPOSE]
- Teleology: Guard the engine artifact-writing and compact-run-snapshot provenance rules that downstream forensics, oracle flows, and contract bundles rely on.
- Mechanism: Use a lightweight harness around `GodModeEngine` helper methods to assert canonical metadata injection, cache-policy behavior, horizon recovery, compact snapshot composition, and contract-bundle persistence.

[INTERFACE]
- Coverage: GodModeEngine._write_artifact, _is_completed, _recover_horizon_from_artifacts, _write_compact_run_snapshot, and _write_run_contract_bundle.
- Inputs: Temporary artifact/run directories plus synthetic CodexNode envelopes and runtime-context fixtures.
- Outputs: Assertions over written artifact metadata, alias artifacts, completion behavior, recovered horizon state, compact snapshots, and combined contract bundles.

[FLOW]
- Build a minimal engine harness and node fixtures -> exercise artifact/provenance helpers directly -> assert canonical metadata and alias behavior -> assert compact snapshot and contract-bundle persistence rules stay stable.
- When-needed: Open when debugging engine artifact metadata, cache semantics, compact run snapshots, or contract-bundle write behavior in the backend runtime.
- Escalates-to: system/core/engine.py; system/lib/schema_validator.py; codex/contracts/contract_config.json
- Navigation-group: server_backend

[DEPENDENCIES]
- system.core.engine: Owns the artifact and runtime snapshot helpers under test.
- system.lib.types + system.lib.hashing: Supply node/status envelopes and completion hashes used by the assertions.

[CONSTRAINTS]
- Guarantee: These tests stay fully local by writing all artifacts into tmp_path rather than touching real run state.
- Non-goal: This suite does not run full DAG execution; it targets engine helper semantics directly.
"""
from __future__ import annotations

import json
import logging
import threading
from pathlib import Path

import pytest

from system.core.engine import GodModeEngine, LogicalFailure
from system.lib.hashing import hash_node
from system.lib.types import NodeType, StepStatus, TOOL_METADATA_SCHEMA_VERSION, CodexNode


class _EngineHarness:
    """
    [ROLE]
    - Teleology: Provide just enough engine state for the artifact/provenance helper methods to run without booting a full execution engine.
    - Ownership: Local test harness for this module's direct `GodModeEngine` helper coverage.
    - Mutability: Mutable fixture object whose fields are populated per test case.
    - Concurrency: Not shared across tests; one harness instance per scenario.
    - When-needed: Open when a provenance test fails and the first question is which engine fields the helper under test actually reads from its harness.
    - Escalates-to: system/core/engine.py::GodModeEngine._write_artifact; system/core/engine.py::GodModeEngine._write_compact_run_snapshot
    """
    def __init__(self, artifacts_dir: Path) -> None:
        self._stop_event = threading.Event()
        self.run_id = "RUN_TEST"
        self.root_dir = artifacts_dir.parent
        self.run_dir = artifacts_dir.parent
        self.artifacts_dir = artifacts_dir
        self.logger = logging.getLogger("tests.engine_artifact_provenance")
        self._node_outcomes = {}
        self._manifest = {}
        self._force_load_stale_feeds = False
        self._target_time_iso = None
        self._horizon_label = None
        self._execution_scope = set()
        self._universe = {}

    _stable_json_sha256 = staticmethod(GodModeEngine._stable_json_sha256)
    _is_lab_oracle_node = staticmethod(GodModeEngine._is_lab_oracle_node)
    _is_global_feed_node = staticmethod(GodModeEngine._is_global_feed_node)
    _collect_compact_contracts = GodModeEngine._collect_compact_contracts
    _load_artifact_cache = GodModeEngine._load_artifact_cache
    _compact_runtime_context = GodModeEngine._compact_runtime_context
    _normalize_contract_name = staticmethod(GodModeEngine._normalize_contract_name)
    _read_contract_body_from_repo = GodModeEngine._read_contract_body_from_repo


def test_write_artifact_injects_canonical_metadata_and_provenance(tmp_path: Path) -> None:
    """
    [ACTION]
    - Teleology: Prove the engine injects the canonical metadata and diagnostics envelope on a successful artifact write.
    - Mechanism: Build a tool node with config provenance fields, call `_write_artifact()`, then assert the persisted JSON contains schema versioning, timestamps, config provenance, and normalized diagnostics.
    - Reads: Synthetic CodexNode metadata and the harness artifact directory.
    - Writes: One temporary artifact envelope under tmp_path.
    - Guarantee: Verifies the canonical metadata/provenance fields exist even when the caller only supplies minimal metadata.
    - Fails: Propagates engine helper failures from `_write_artifact()`.
    - When-needed: Open when a debugger needs the exact regression that proves artifact envelopes still receive canonical metadata and provenance injection.
    - Escalates-to: system/core/engine.py::GodModeEngine._write_artifact; system/lib/types.py
    - Navigation-group: server_backend
    """
    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    harness = _EngineHarness(artifacts_dir)
    node = CodexNode(
        id="global_measurements_feed",
        type=NodeType.TOOL,
        config_ref="codex/configs/measurements_default.json",
        merged_hash="abc123",
        inline_overrides={"period": "2y", "precision": 4},
    )

    GodModeEngine._write_artifact(
        harness,
        node,
        StepStatus.SUCCESS,
        {"tool": "measurements"},
        {"columns": ["target_id"], "rows": [["SUBSYSTEM_A"]]},
    )

    artifact_path = artifacts_dir / "global_measurements_feed.json"
    assert artifact_path.exists()

    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    metadata = artifact["metadata"]

    assert metadata["schema_version"] == TOOL_METADATA_SCHEMA_VERSION
    assert metadata["data_schema_version"] == "measurements.1"
    assert isinstance(metadata["timestamp_iso"], str) and metadata["timestamp_iso"]
    assert isinstance(metadata["timestamp_epoch_s"], (int, float))
    assert metadata["config_ref"] == "codex/configs/measurements_default.json"
    assert metadata["merged_hash"] == "abc123"
    assert metadata["override_keys"] == ["period", "precision"]

    diagnostics = metadata["diagnostics"]
    assert diagnostics["input_rows"] == 0
    assert diagnostics["output_rows"] == 0
    assert diagnostics["dropped_rows"] == 0
    assert diagnostics["warnings"] == []


def test_write_artifact_preserves_explicit_override_keys(tmp_path: Path) -> None:
    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    harness = _EngineHarness(artifacts_dir)
    node = CodexNode(
        id="global_environment_feed",
        type=NodeType.TOOL,
        inline_overrides={"ignored": True},
    )

    GodModeEngine._write_artifact(
        harness,
        node,
        StepStatus.SUCCESS,
        {
            "tool": "environment",
            "override_keys": ["already_set"],
            "diagnostics": {"warnings": "note"},
        },
        {},
    )

    metadata = json.loads((artifacts_dir / "global_environment_feed.json").read_text(encoding="utf-8"))["metadata"]
    assert metadata["override_keys"] == ["already_set"]
    assert metadata["diagnostics"]["warnings"] == ["note"]


def test_write_artifact_writes_canonical_alias_with_shared_provenance(tmp_path: Path) -> None:
    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    harness = _EngineHarness(artifacts_dir)
    harness._target_time_iso = "2026-03-03T21:00:00+00:00"
    harness._horizon_label = "Next US System Close"
    node = CodexNode(
        id="oracle_truth_diff_observations",
        type=NodeType.TOOL,
        is_artifact=True,
        teleology="deterministic reconciliation",
        group="oracle",
        lane="SPINE",
        expectation="prediction_reconciliation",
    )
    data = {
        "status": "AVAILABLE",
        "subject_run_id": "RUN_SUBJECT",
        "truth_run_id": "RUN_TRUTH",
        "rows": [
            {
                "target_id": "SIGNAL_A",
                "target_kind": "MEASUREMENTS",
                "prediction_direction": "UP",
                "subject_snapshot_value": 100.0,
                "predicted_target_value": 105.0,
                "realized_truth_value": 104.0,
                "absolute_delta": 1.0,
                "percent_delta": 0.9523809524,
                "directional_correct": True,
                "rank": 1,
            }
        ],
        "summary": {
            "row_count": 1,
            "directionally_correct_count": 1,
            "directionally_incorrect_count": 0,
            "largest_absolute_miss_target": "SIGNAL_A",
            "largest_percent_miss_target": "SIGNAL_A",
        },
    }

    GodModeEngine._write_artifact(
        harness,
        node,
        StepStatus.SUCCESS,
        {"tool": "oracle_truth_diff_observations"},
        data,
    )

    primary = json.loads((artifacts_dir / "oracle_truth_diff_observations.json").read_text(encoding="utf-8"))
    alias = json.loads((artifacts_dir / "prediction_reconciliation.json").read_text(encoding="utf-8"))

    assert primary["id"] == "oracle_truth_diff_observations"
    assert alias["id"] == "prediction_reconciliation"
    assert alias["data"] == primary["data"]
    assert alias["node_hash"] == primary["node_hash"]
    assert alias["metadata"]["artifact_alias_of"] == "oracle_truth_diff_observations"
    assert alias["metadata"]["canonical_artifact_id"] == "prediction_reconciliation"
    assert alias["metadata"]["target_time_iso"] == primary["metadata"]["target_time_iso"]
    assert alias["metadata"]["horizon_label"] == primary["metadata"]["horizon_label"]


def test_is_completed_bypasses_cache_when_policy_is_none(tmp_path: Path) -> None:
    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    harness = _EngineHarness(artifacts_dir)
    node = CodexNode(
        id="global_measurements_feed",
        type=NodeType.TOOL,
        execution={"cache_policy": "none"},
    )
    artifact_path = artifacts_dir / "global_measurements_feed.json"
    artifact_path.write_text(
        json.dumps(
            {
                "node_hash": hash_node(node),
                "status": StepStatus.SUCCESS.value,
            }
        ),
        encoding="utf-8",
    )

    assert GodModeEngine._is_completed(harness, node) is False


def test_is_completed_uses_cache_when_policy_is_standard(tmp_path: Path) -> None:
    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    harness = _EngineHarness(artifacts_dir)
    node = CodexNode(
        id="global_measurements_feed",
        type=NodeType.TOOL,
        execution={"cache_policy": "standard"},
    )
    artifact_path = artifacts_dir / "global_measurements_feed.json"
    artifact_path.write_text(
        json.dumps(
            {
                "node_hash": hash_node(node),
                "status": StepStatus.SUCCESS.value,
            }
        ),
        encoding="utf-8",
    )

    assert GodModeEngine._is_completed(harness, node) is True


def test_is_completed_can_force_load_stale_feed_when_override_enabled(tmp_path: Path) -> None:
    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    harness = _EngineHarness(artifacts_dir)
    harness._force_load_stale_feeds = True

    node = CodexNode(
        id="global_measurements_feed",
        type=NodeType.TOOL,
        execution={"cache_policy": "standard"},
        meta={"is_feed": True},
    )
    artifact_path = artifacts_dir / "global_measurements_feed.json"
    artifact_path.write_text(
        json.dumps(
            {
                "node_hash": "hash_mismatch",
                "status": StepStatus.SUCCESS.value,
            }
        ),
        encoding="utf-8",
    )

    assert GodModeEngine._is_completed(harness, node) is True


def test_is_completed_does_not_force_load_non_feed_with_mismatch(tmp_path: Path) -> None:
    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    harness = _EngineHarness(artifacts_dir)
    harness._force_load_stale_feeds = True

    node = CodexNode(
        id="lab_director",
        type=NodeType.REASONING,
        execution={"cache_policy": "standard"},
        meta={"is_feed": False},
    )
    artifact_path = artifacts_dir / "lab_director.json"
    artifact_path.write_text(
        json.dumps(
            {
                "node_hash": "hash_mismatch",
                "status": StepStatus.SUCCESS.value,
            }
        ),
        encoding="utf-8",
    )

    assert GodModeEngine._is_completed(harness, node) is False


def test_write_artifact_failure_does_not_require_horizon_for_artifact_nodes(tmp_path: Path) -> None:
    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    harness = _EngineHarness(artifacts_dir)
    node = CodexNode(
        id="lab_decide",
        type=NodeType.REASONING,
        is_artifact=True,
    )

    GodModeEngine._write_artifact(
        harness,
        node,
        StepStatus.FAILURE,
        {"error": "boom"},
        None,
        error="boom",
    )

    artifact = json.loads((artifacts_dir / "lab_decide.json").read_text(encoding="utf-8"))
    assert artifact["status"] == StepStatus.FAILURE.value
    assert artifact["metadata"]["error"] == "boom"


def test_write_artifact_success_still_requires_horizon_for_artifact_nodes(tmp_path: Path) -> None:
    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    harness = _EngineHarness(artifacts_dir)
    node = CodexNode(
        id="lab_decide",
        type=NodeType.REASONING,
        is_artifact=True,
    )

    with pytest.raises(LogicalFailure, match=r"\[C4\].*horizon is unresolved"):
        GodModeEngine._write_artifact(
            harness,
            node,
            StepStatus.SUCCESS,
            {},
            {},
        )


def test_recover_horizon_from_artifacts_reads_envelope_metadata(tmp_path: Path) -> None:
    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    harness = _EngineHarness(artifacts_dir)

    # Non-envelope snapshot file should be ignored.
    (artifacts_dir / "graph_snapshot.json").write_text(
        json.dumps({"nodes": [], "edges": []}),
        encoding="utf-8",
    )
    (artifacts_dir / "global_measurements_feed.json").write_text(
        json.dumps(
            {
                "id": "global_measurements_feed",
                "status": "success",
                "metadata": {
                    "target_time_iso": "2026-03-03T21:00:00+00:00",
                    "horizon_label": "Next US System Close (Tue Mar 03, 4:00 PM ET)",
                },
            }
        ),
        encoding="utf-8",
    )

    recovered = GodModeEngine._recover_horizon_from_artifacts(harness)
    assert recovered is not None
    assert recovered["target_time"] == "2026-03-03T21:00:00+00:00"
    assert recovered["horizon_label"] == "Next US System Close (Tue Mar 03, 4:00 PM ET)"


def test_recover_horizon_from_artifacts_returns_none_without_metadata(tmp_path: Path) -> None:
    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    harness = _EngineHarness(artifacts_dir)

    (artifacts_dir / "lab_seed_state.json").write_text(
        json.dumps({"id": "lab_seed_state", "status": "success", "metadata": {}}),
        encoding="utf-8",
    )

    assert GodModeEngine._recover_horizon_from_artifacts(harness) is None


def test_write_compact_run_snapshot_excludes_global_feeds_and_embeds_responses(tmp_path: Path) -> None:
    """
    [ACTION]
    - Teleology: Prove the compact run snapshot keeps reasoning/oracle responses and contracts while excluding global feed nodes from the exported node list.
    - Mechanism: Seed a synthetic run directory with feed and reasoning artifacts, invoke `_write_compact_run_snapshot()`, then assert the compact JSON filters feed nodes and preserves injected dependency context plus contract references.
    - Reads: Temporary runtime_context and artifact envelopes under the synthetic run directory.
    - Writes: `run_snapshot_compact.json` under the temporary run root.
    - Guarantee: Verifies compact snapshot node selection, response embedding, and contract aggregation stay aligned with engine forensics expectations.
    - Fails: Propagates engine helper failures from `_write_compact_run_snapshot()`.
    - When-needed: Open when compact run snapshots look wrong and the debugger needs the regression that covers feed exclusion and embedded response shape.
    - Escalates-to: system/core/engine.py::GodModeEngine._write_compact_run_snapshot; system/core/engine.py::GodModeEngine._write_run_contract_bundle
    - Navigation-group: server_backend
    """
    run_dir = tmp_path / "RUN_SAMPLE"
    artifacts_dir = run_dir / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    harness = _EngineHarness(artifacts_dir)
    harness.run_id = "RUN_SAMPLE"
    harness._execution_scope = {"global_measurements_feed", "lab_decide", "oracle_score_measurements"}
    harness._node_outcomes = {
        "global_measurements_feed": "success",
        "lab_decide": "success",
        "oracle_score_measurements": "success",
    }

    harness._universe = {
        "global_measurements_feed": CodexNode(
            id="global_measurements_feed",
            type=NodeType.TOOL,
            group="feeds",
            lane="MEASUREMENTS",
            meta={"is_feed": True},
        ),
        "lab_decide": CodexNode(
            id="lab_decide",
            type=NodeType.REASONING,
            group="lab",
            lane="SPINE",
            dependencies=("global_measurements_feed",),
            instruction="[CONTRACT: schema_cp1.json]",
            output_schema="isomorphic_cp1",
        ),
        "oracle_score_measurements": CodexNode(
            id="oracle_score_measurements",
            type=NodeType.REASONING,
            group="oracle",
            lane="MEASUREMENTS",
            dependencies=("lab_decide",),
            instruction="[CONTRACT: evaluate_output.md]",
            output_schema="text",
        ),
    }

    (run_dir / "runtime_context.json").write_text(
        json.dumps(
            {
                "mission_name": "oracle",
                "target_id": "oracle_cp2_emitter",
                "run_mode": "resume",
                "execution_mode": "runtime",
                "source_run_id": "RUN_LAB",
                "subject_group": "oracle",
                "as_of": "2026-03-03T12:00:00+00:00",
                "time_anchor": "2026-03-03T12:00:00+00:00",
                "horizon": {
                    "horizon_policy": "next_us_close",
                    "target_time_iso": "2026-03-03T21:00:00+00:00",
                    "target_time_et": "2026-03-03T16:00:00-05:00",
                    "horizon_label": "Next US System Close",
                },
            }
        ),
        encoding="utf-8",
    )

    (artifacts_dir / "global_measurements_feed.json").write_text(
        json.dumps(
            {
                "id": "global_measurements_feed",
                "status": "success",
                "node_hash": "feedhash",
                "metadata": {"status": "success"},
                "data": {"rows": [["SIGNAL_B"]]},
            }
        ),
        encoding="utf-8",
    )
    (artifacts_dir / "lab_decide.json").write_text(
        json.dumps(
            {
                "id": "lab_decide",
                "status": "success",
                "node_hash": "labhash",
                "metadata": {
                    "status": "success",
                    "model": "gemini",
                    "target_time_iso": "2026-03-03T21:00:00+00:00",
                    "horizon_label": "Next US System Close",
                },
                "data": {"epicentre_thesis": "risk-off concentration"},
            }
        ),
        encoding="utf-8",
    )
    (artifacts_dir / "oracle_score_measurements.json").write_text(
        json.dumps(
            {
                "id": "oracle_score_measurements",
                "status": "success",
                "node_hash": "oraclehash",
                "metadata": {"status": "success", "model": "chatgpt"},
                "data": "SKILL",
            }
        ),
        encoding="utf-8",
    )

    GodModeEngine._write_compact_run_snapshot(harness)

    snapshot_path = run_dir / "run_snapshot_compact.json"
    assert snapshot_path.exists()
    raw = snapshot_path.read_text(encoding="utf-8")
    assert "\n" not in raw  # compact JSON: no pretty-print newlines

    payload = json.loads(raw)
    assert payload["run_id"] == "RUN_SAMPLE"
    assert payload["contracts"]["output_schemas"] == ["isomorphic_cp1"]
    assert set(payload["contracts"]["instruction_contracts"]) == {
        "evaluate_output.md",
        "schema_cp1.json",
    }

    node_ids = [entry["id"] for entry in payload["nodes"]]
    assert "global_measurements_feed" not in node_ids
    assert node_ids == ["lab_decide", "oracle_score_measurements"]

    lab_entry = payload["nodes"][0]
    assert lab_entry["dependencies"] == ["global_measurements_feed"]
    assert lab_entry["response"] == {"epicentre_thesis": "risk-off concentration"}
    assert lab_entry["injected"]["dependencies"][0]["id"] == "global_measurements_feed"
    assert lab_entry["injected"]["dependencies"][0]["status"] == "success"

    oracle_entry = payload["nodes"][1]
    assert oracle_entry["dependencies"] == ["lab_decide"]
    assert oracle_entry["response"] == "SKILL"


def test_write_compact_run_snapshot_refreshes_existing_file(tmp_path: Path) -> None:
    run_dir = tmp_path / "RUN_SAMPLE"
    artifacts_dir = run_dir / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    harness = _EngineHarness(artifacts_dir)

    snapshot_path = run_dir / "run_snapshot_compact.json"
    snapshot_path.write_text('{"sentinel":true}', encoding="utf-8")

    GodModeEngine._write_compact_run_snapshot(harness)

    payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
    assert payload["run_id"] == "RUN_TEST"
    assert payload["nodes"] == []


def test_write_run_contract_bundle_combines_and_dedupes_contracts(tmp_path: Path) -> None:
    run_dir = tmp_path / "RUN_SAMPLE"
    artifacts_dir = run_dir / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    contracts_root = run_dir / "codex" / "contracts"
    contracts_root.mkdir(parents=True, exist_ok=True)
    (contracts_root / "schema_cp2.json").write_text('{"id":"schema_cp2"}', encoding="utf-8")
    (contracts_root / "schema_realized_hindsight_brief.json").write_text(
        '{"id":"schema_realized_hindsight_brief"}',
        encoding="utf-8",
    )

    harness = _EngineHarness(artifacts_dir)
    harness.run_id = "RUN_SAMPLE"
    harness.root_dir = run_dir
    harness._execution_scope = {"lab_decide", "oracle_cp2_emitter", "oracle_truth_map"}
    harness._universe = {
        "lab_decide": CodexNode(
            id="lab_decide",
            type=NodeType.REASONING,
            group="lab",
            lane="SPINE",
            instruction=(
                "[CONTRACT: schema_cp1.json]\n"
                '{"id":"schema_cp1"}\n'
                "[/CONTRACT]\n"
                "[CONTRACT: evidence_unit.md]\n"
                "evidence unit rules\n"
                "[/CONTRACT]"
            ),
            output_schema="isomorphic_cp1",
        ),
        "oracle_cp2_emitter": CodexNode(
            id="oracle_cp2_emitter",
            type=NodeType.REASONING,
            group="oracle",
            lane="SPINE",
            instruction=(
                "[CONTRACT: schema_cp1.json]\n"
                '{"id":"schema_cp1"}\n'
                "[/CONTRACT]"
            ),
            output_schema="isomorphic_cp2",
        ),
        "oracle_truth_map": CodexNode(
            id="oracle_truth_map",
            type=NodeType.REASONING,
            group="oracle",
            lane="SPINE",
            instruction="[]",
            output_schema="schema_realized_hindsight_brief",
        ),
    }

    GodModeEngine._write_run_contract_bundle(harness)

    bundle_path = run_dir / "contracts" / "contracts_used_combined.json"
    assert bundle_path.exists()
    raw = bundle_path.read_text(encoding="utf-8")
    assert "\n" not in raw  # compact JSON

    payload = json.loads(raw)
    assert payload["run_id"] == "RUN_SAMPLE"
    assert payload["node_count"] == 3

    contracts = payload["contracts"]
    names = [entry["contract"] for entry in contracts]
    assert names == [
        "evidence_unit.md",
        "schema_cp1.json",
        "schema_cp2.json",
        "schema_realized_hindsight_brief.json",
    ]

    schema_cp1 = next(c for c in contracts if c["contract"] == "schema_cp1.json")
    assert schema_cp1["source_nodes"] == ["lab_decide", "oracle_cp2_emitter"]
    assert set(schema_cp1["sources"]) == {"instruction_inline"}

    schema_cp2 = next(c for c in contracts if c["contract"] == "schema_cp2.json")
    assert schema_cp2["source_nodes"] == ["oracle_cp2_emitter"]
    assert "output_schema" in schema_cp2["sources"]
    assert schema_cp2["content"] == '{"id":"schema_cp2"}'

    schema_truth_map = next(c for c in contracts if c["contract"] == "schema_realized_hindsight_brief.json")
    assert schema_truth_map["source_nodes"] == ["oracle_truth_map"]
    assert "output_schema" in schema_truth_map["sources"]


def test_write_run_contract_bundle_is_create_once(tmp_path: Path) -> None:
    run_dir = tmp_path / "RUN_SAMPLE"
    artifacts_dir = run_dir / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    harness = _EngineHarness(artifacts_dir)

    contracts_dir = run_dir / "contracts"
    contracts_dir.mkdir(parents=True, exist_ok=True)
    bundle_path = contracts_dir / "contracts_used_combined.json"
    bundle_path.write_text('{"sentinel":true}', encoding="utf-8")

    GodModeEngine._write_run_contract_bundle(harness)

    assert bundle_path.read_text(encoding="utf-8") == '{"sentinel":true}'
