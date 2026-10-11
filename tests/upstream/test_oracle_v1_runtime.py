"""
[PURPOSE]
- Teleology: Verify Oracle v1 runtime behavior inside `GodModeEngine`, especially run-anchor selection, additive observation-report emission, and schema validation for structured tool outputs.
- Mechanism: Build synthetic run directories under `tmp_path`, patch runtime collaborators, and seed compact Oracle artifacts so the tests exercise engine-owned contracts without live bridge execution.

[INTERFACE]
- Tests: `GodModeEngine` initialization, `_maybe_write_oracle_observation_report`, and `_exec_tool` schema-validation behavior.

[FLOW]
- Create minimal project and run directories.
- Patch bridge and loader collaborators to keep the engine local and deterministic.
- Seed subject/truth artifacts or fake tool modules, then assert on persisted observation-report payloads and expected failures.

[DEPENDENCIES]
- system.core.engine: `GodModeEngine`, `LogicalFailure`.
- system.lib.observer_report: Observation-report sidecar contract exercised through the engine.

[CONSTRAINTS]
- All writes stay under `tmp_path`; no shared repo runtime state is mutated.
- Tests isolate bridge and loader behavior with mocks instead of starting live services.
- When-needed: Open when an Oracle v1 runtime regression touches engine anchor selection, additive observation-report synthesis, or schema-gated tool execution.
- Escalates-to: system/core/engine.py::GodModeEngine; system/lib/observer_report.py::generate_observation_report; system/lib/schema_validator.py
- Navigation-group: server_backend
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from system.lib.types import ExecutionMode


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_oracle_engine_anchor_prefers_subject_run_context(tmp_path: Path) -> None:
    root_dir = tmp_path / "project"
    runs_dir = root_dir / "state" / "runs"
    subject_run_id = "RUN_SUBJECT"
    truth_run_id = "RUN_TRUTH"
    subject_dir = runs_dir / subject_run_id
    truth_dir = runs_dir / truth_run_id
    subject_dir.mkdir(parents=True, exist_ok=True)
    truth_dir.mkdir(parents=True, exist_ok=True)
    (root_dir / "master_config.json").write_text(
        json.dumps(
            {
                "execution": {"retries": {"value": 1}, "max_workers": {"value": 1}},
                "bridge": {},
                "paths": {"runs_dir": "state/runs"},
                "ui": {"lane_colors": {}},
            }
        ),
        encoding="utf-8",
    )
    (subject_dir / "runtime_context.json").write_text(
        json.dumps({"as_of": "2026-03-03T14:05:00+00:00"}),
        encoding="utf-8",
    )
    (truth_dir / "runtime_context.json").write_text(
        json.dumps({"as_of": "2026-03-03T22:05:00+00:00"}),
        encoding="utf-8",
    )

    mock_loader = MagicMock()
    mock_loader.hydrate_graph.return_value = {}
    with patch("system.core.engine.Bridge", MagicMock()), patch(
        "system.core.engine.PhysicalLoader",
        return_value=mock_loader,
    ):
        from system.core.engine import GodModeEngine

        engine = GodModeEngine(
            run_id="RUN_ORACLE",
            root_dir=str(root_dir),
            execution_mode=ExecutionMode.LAB,
            source_run_id=subject_run_id,
            feed_source_run_id=truth_run_id,
            horizon="2026-03-03T21:00:00+00:00",
            oracle_subject_run_dir=str(subject_dir),
            oracle_truth_run_dir=str(truth_dir),
        )

    assert engine._run_anchor_iso == "2026-03-03T14:05:00+00:00"


def test_oracle_engine_writes_additive_observation_report(tmp_path: Path) -> None:
    root_dir = tmp_path / "project"
    runs_dir = root_dir / "state" / "runs"
    subject_dir = runs_dir / "RUN_SUBJECT"
    truth_dir = runs_dir / "RUN_TRUTH"
    subject_dir.mkdir(parents=True, exist_ok=True)
    truth_dir.mkdir(parents=True, exist_ok=True)
    (root_dir / "master_config.json").write_text(
        json.dumps(
            {
                "execution": {"retries": {"value": 1}, "max_workers": {"value": 1}},
                "bridge": {},
                "paths": {"runs_dir": "state/runs"},
                "ui": {"lane_colors": {}},
            }
        ),
        encoding="utf-8",
    )
    _write_json(subject_dir / "runtime_context.json", {"as_of": "2026-03-03T14:05:00+00:00"})
    _write_json(truth_dir / "runtime_context.json", {"as_of": "2026-03-03T22:05:00+00:00"})
    _write_json(
        subject_dir / "artifacts" / "lab_director.json",
        {
            "metadata": {"as_of": "2026-03-03T14:05:00+00:00"},
            "data": {
                "evidence_dictionary": [
                    {
                        "ref_id": "[1]",
                        "ledger_id": "S_CAFEBABE",
                        "subject": "XOM",
                        "signal_summary": "Subject-side stock support.",
                    }
                ],
                "predictions_t": [
                    {
                        "target_id": "XOM",
                        "direction": "UP",
                        "snapshot_price": 100.0,
                        "target_price": 105.0,
                        "invalidation": "Lose support.",
                    }
                ],
            },
        },
    )

    mock_loader = MagicMock()
    mock_loader.hydrate_graph.return_value = {}
    with patch("system.core.engine.Bridge", MagicMock()), patch(
        "system.core.engine.PhysicalLoader",
        return_value=mock_loader,
    ):
        from system.core.engine import GodModeEngine

        engine = GodModeEngine(
            run_id="RUN_ORACLE",
            root_dir=str(root_dir),
            execution_mode=ExecutionMode.LAB,
            source_run_id="RUN_SUBJECT",
            feed_source_run_id="RUN_TRUTH",
            horizon="2026-03-03T21:00:00+00:00",
            oracle_subject_run_dir=str(subject_dir),
            oracle_truth_run_dir=str(truth_dir),
        )

    _write_json(
        engine.run_dir / "artifacts" / "prediction_reconciliation.json",
        {
            "metadata": {"status": "success", "artifact_alias_of": "oracle_truth_diff_equity"},
            "data": {
                "status": "AVAILABLE",
                "subject_run_id": "RUN_SUBJECT",
                "truth_run_id": "RUN_TRUTH",
                "rows": [
                    {
                        "target_id": "XOM",
                        "asset_class": "STOCK",
                        "prediction_direction": "UP",
                        "subject_snapshot_price": 100.0,
                        "predicted_target_price": 105.0,
                        "realized_truth_price": 105.0,
                        "absolute_delta": 0.0,
                        "percent_delta": 0.0,
                        "directional_correct": True,
                        "rank": 1,
                    }
                ],
                "summary": {
                    "row_count": 1,
                    "directionally_correct_count": 1,
                    "directionally_incorrect_count": 0,
                    "largest_absolute_miss_target": "XOM",
                    "largest_percent_miss_target": "XOM",
                },
            },
        },
    )
    _write_json(
        engine.run_dir / "artifacts" / "cp2_critique.json",
        {
            "metadata": {"status": "success", "artifact_alias_of": "oracle_attribution_map"},
            "data": {
                "root_failure_mode": "priced_in_continuation_bias",
                "critique_items": [
                    {
                        "scope": "prediction",
                        "target_or_claim": "XOM",
                        "subject_grounding_refs": ["[1]", "S_CAFEBABE"],
                        "realized_refs": ["prediction_reconciliation:XOM"],
                        "error_class": "PREDICTION_DRIFT",
                        "what_was_wrong": "Residual upside was smaller than the original target assumed.",
                    }
                ],
                "reconstruction_guidance": {
                    "dominant_force": "Residual energy continuation",
                    "prefer_targets": ["XOM"],
                    "avoid_targets": ["UAL"],
                    "eligible_ledger_ids": ["S_CAFEBABE"],
                },
            },
        },
    )

    engine._maybe_write_oracle_observation_report(
        {
            "evidence_dictionary": [
                {
                    "ref_id": "[1]",
                    "ledger_id": "S_CAFEBABE",
                    "subject": "XOM",
                    "signal_summary": "Oracle uses the same subject-side grounding.",
                }
            ],
            "predictions_t": [
                {
                    "target_id": "XOM",
                    "direction": "UP",
                    "snapshot_price": 100.0,
                    "target_price": 104.0,
                    "invalidation": "Lose support.",
                }
            ],
        }
    )

    report_path = engine.run_dir / "artifacts" / "observation_report.json"
    payload = json.loads(report_path.read_text(encoding="utf-8"))

    assert payload["run_id"] == "RUN_ORACLE"
    assert payload["oracle_v1"]["subject_run_id"] == "RUN_SUBJECT"
    assert payload["oracle_v1"]["truth_run_id"] == "RUN_TRUTH"
    assert payload["oracle_v1"]["grading_summary"]["hit_rate"] == 1.0
    assert payload["oracle_v1"]["attribution_summary"]["root_failure_mode"] == "priced_in_continuation_bias"
    assert payload["oracle_v1"]["reconstruction_guidance_summary"]["prefer_targets"] == ["XOM"]


def test_oracle_engine_writes_additive_observation_report_from_contract_aligned_diff(
    tmp_path: Path,
) -> None:
    root_dir = tmp_path / "project"
    runs_dir = root_dir / "state" / "runs"
    subject_dir = runs_dir / "RUN_SUBJECT"
    truth_dir = runs_dir / "RUN_TRUTH"
    subject_dir.mkdir(parents=True, exist_ok=True)
    truth_dir.mkdir(parents=True, exist_ok=True)
    (root_dir / "master_config.json").write_text(
        json.dumps(
            {
                "execution": {"retries": {"value": 1}, "max_workers": {"value": 1}},
                "bridge": {},
                "paths": {"runs_dir": "state/runs"},
                "ui": {"lane_colors": {}},
            }
        ),
        encoding="utf-8",
    )
    _write_json(subject_dir / "runtime_context.json", {"as_of": "2026-03-03T14:05:00+00:00"})
    _write_json(truth_dir / "runtime_context.json", {"as_of": "2026-03-03T22:05:00+00:00"})
    _write_json(
        subject_dir / "artifacts" / "lab_director.json",
        {
            "metadata": {"as_of": "2026-03-03T14:05:00+00:00"},
            "data": {
                "evidence_dictionary": [
                    {
                        "ref_id": "[1]",
                        "ledger_id": "S_CAFEBABE",
                        "subject": "XOM",
                        "signal_summary": "Subject-side stock support.",
                    }
                ],
                "predictions_t": [
                    {
                        "target_id": "XOM",
                        "direction": "UP",
                        "snapshot_price": 100.0,
                        "target_price": 105.0,
                        "invalidation": "Lose support.",
                    }
                ],
            },
        },
    )

    mock_loader = MagicMock()
    mock_loader.hydrate_graph.return_value = {}
    with patch("system.core.engine.Bridge", MagicMock()), patch(
        "system.core.engine.PhysicalLoader",
        return_value=mock_loader,
    ):
        from system.core.engine import GodModeEngine

        engine = GodModeEngine(
            run_id="RUN_ORACLE",
            root_dir=str(root_dir),
            execution_mode=ExecutionMode.LAB,
            source_run_id="RUN_SUBJECT",
            feed_source_run_id="RUN_TRUTH",
            horizon="2026-03-03T21:00:00+00:00",
            oracle_subject_run_dir=str(subject_dir),
            oracle_truth_run_dir=str(truth_dir),
        )

    _write_json(
        engine.run_dir / "artifacts" / "prediction_reconciliation.json",
        {
            "metadata": {"status": "success", "artifact_alias_of": "oracle_truth_diff_equity"},
            "data": {
                "status": "AVAILABLE",
                "subject_run_id": "RUN_SUBJECT",
                "truth_run_id": "RUN_TRUTH",
                "rows": [
                    {
                        "target_id": "XOM",
                        "asset_class": "STOCK",
                        "prediction_direction": "UP",
                        "subject_snapshot_price": 100.0,
                        "predicted_target_price": 105.0,
                        "realized_truth_price": 105.0,
                        "absolute_delta": 0.0,
                        "percent_delta": 0.0,
                        "directional_correct": True,
                        "rank": 1,
                    }
                ],
                "summary": {
                    "row_count": 1,
                    "directionally_correct_count": 1,
                    "directionally_incorrect_count": 0,
                    "largest_absolute_miss_target": "XOM",
                    "largest_percent_miss_target": "XOM",
                },
            },
        },
    )
    _write_json(
        engine.run_dir / "artifacts" / "cp2_critique.json",
        {
            "metadata": {"status": "success", "artifact_alias_of": "oracle_attribution_map"},
            "data": {
                "root_failure_mode": "priced_in_continuation_bias",
                "critique_items": [
                    {
                        "scope": "prediction",
                        "target_or_claim": "XOM",
                        "subject_grounding_refs": ["[1]", "S_CAFEBABE"],
                        "realized_refs": ["prediction_reconciliation:XOM"],
                        "error_class": "PREDICTION_DRIFT",
                        "what_was_wrong": "Residual upside was smaller than the original target assumed.",
                    }
                ],
                "reconstruction_guidance": {
                    "dominant_force": "Residual energy continuation",
                    "prefer_targets": ["XOM"],
                    "avoid_targets": ["UAL"],
                    "eligible_ledger_ids": ["S_CAFEBABE"],
                },
            },
        },
    )

    engine._maybe_write_oracle_observation_report(
        {
            "evidence_dictionary": [
                {
                    "ref_id": "[1]",
                    "ledger_id": "S_CAFEBABE",
                    "subject": "XOM",
                    "signal_summary": "Oracle uses the same subject-side grounding.",
                }
            ],
            "predictions_t": [
                {
                    "target_id": "XOM",
                    "direction": "UP",
                    "snapshot_price": 100.0,
                    "target_price": 104.0,
                    "invalidation": "Lose support.",
                }
            ],
        }
    )

    report_path = engine.run_dir / "artifacts" / "observation_report.json"
    payload = json.loads(report_path.read_text(encoding="utf-8"))

    assert payload["oracle_v1"]["reconciliation_summary"]["row_count"] == 1
    assert payload["oracle_v1"]["largest_miss_targets"]["absolute"] == "XOM"
    assert payload["oracle_v1"]["largest_miss_targets"]["percent"] == "XOM"
    assert payload["oracle_v1"]["grading_summary"]["hits"] == 1
    assert payload["oracle_v1"]["grading_summary"]["hit_rate"] == 1.0
    assert payload["oracle_v1"]["attribution_summary"]["critique_item_count"] == 1
    assert payload["oracle_v1"]["attribution_summary"]["critique_scopes"] == ["prediction"]
    assert payload["oracle_v1"]["reconstruction_guidance_summary"]["prefer_targets"] == ["XOM"]
    assert payload["oracle_v1"]["reconstruction_guidance_summary"]["eligible_ledger_id_count"] == 1
    assert "realized_target_table" not in payload["oracle_v1"]
    assert "top_movers" not in payload["oracle_v1"]


def test_engine_validates_structured_tool_output_when_output_schema_is_declared(tmp_path: Path) -> None:
    root_dir = tmp_path / "project"
    (root_dir / "state" / "runs").mkdir(parents=True, exist_ok=True)
    (root_dir / "master_config.json").write_text(
        json.dumps(
            {
                "execution": {"retries": {"value": 1}, "max_workers": {"value": 1}},
                "bridge": {},
                "paths": {"runs_dir": "state/runs"},
                "ui": {"lane_colors": {}},
            }
        ),
        encoding="utf-8",
    )

    mock_loader = MagicMock()
    mock_loader.hydrate_graph.return_value = {}
    with patch("system.core.engine.Bridge", MagicMock()), patch(
        "system.core.engine.PhysicalLoader",
        return_value=mock_loader,
    ):
        from system.core.engine import GodModeEngine, LogicalFailure

        engine = GodModeEngine(
            run_id="RUN_ORACLE",
            root_dir=str(root_dir),
            execution_mode=ExecutionMode.LAB,
        )

    node = SimpleNamespace(
        id="oracle_truth_diff_equity",
        meta={},
        config={"module": "tools.oracle.truth_diff_equity"},
        output_schema="schema_prediction_reconciliation",
    )

    fake_module = SimpleNamespace(
        run=lambda config, run_dir=None: {
            "metadata": {"tool": "oracle_truth_diff_equity", "status": "success"},
            "data": {"status": "AVAILABLE", "subject_run_id": "RUN_SUBJECT", "truth_run_id": "RUN_TRUTH"},
        }
    )

    with patch("system.core.engine.importlib.import_module", return_value=fake_module):
        try:
            engine._exec_tool(node, {}, {"platform": "chatgpt"})
        except LogicalFailure as exc:
            assert "MISSING_FIELD: rows must be a non-empty list" in str(exc)
        else:
            raise AssertionError("Expected LogicalFailure for invalid structured tool output")
