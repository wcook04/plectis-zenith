"""

[PURPOSE]
- Teleology: Verify that CP2 prediction auditing rewrites temporal fields deterministically and only flags value mismatches when the feed-backed snapshot value materially disagrees.
- Mechanism: Build a minimal `GodModeEngine` stub with fixed run anchors and feed-value maps, then call `_audit_cp2_predictions()` with bounded payload variants.

[INTERFACE]
- Tests: `system.core.engine.GodModeEngine._audit_cp2_predictions`.
- Reads: Stubbed engine temporal anchors and synthetic prediction payloads.
- Writes: None.

[FLOW]
- Build an engine stub with a deterministic value map -> pass a prediction payload into `_audit_cp2_predictions()` -> assert rewritten timestamps, snapshot-value handling, and optional audit-error emission.
- When-needed: Open when debugging why backend-adjacent CP2 enrichment changed timestamps, rewrote snapshot values unexpectedly, or started emitting audit mismatches for stable fixtures.
- Escalates-to: system/core/engine.py; system/server/session.py
- Navigation-group: server_backend

[DEPENDENCIES]
- Couples: GodModeEngine._audit_cp2_predictions supplies the audited behavior; the local stub replaces value maps and temporal anchors, avoiding a real engine run.

[CONSTRAINTS]
- Tests bypass full engine initialization; they isolate the audit helper and its immediate state contract.
- Assertions focus on deterministic normalization behavior, not broader run orchestration or persistence.

"""
from __future__ import annotations

from system.core.engine import GodModeEngine


def _engine_stub(value_map: dict[str, float]) -> GodModeEngine:
    """[ACTION]
    - Teleology: Construct the smallest `GodModeEngine` stand-in needed to exercise CP2 audit normalization without booting the runtime.
    - Mechanism: Allocate an uninitialized engine instance, pin fixed temporal anchors, and replace `_build_observation_value_map()` with a lambda that returns the provided `value_map`.
    - Guarantee: Returns a deterministic engine-shaped object suitable for `_audit_cp2_predictions()` in this module.
    - Fails: None.
    - When-needed: Open when an audit test regresses and you need the exact stubbed engine state rather than tracing the full engine constructor path.
    - Escalates-to: system/core/engine.py; system/server/tests/test_cp2_enrichment_determinism.py
    """
    engine = object.__new__(GodModeEngine)
    engine._run_anchor_iso = "2026-03-04T00:00:00+00:00"
    engine._target_time_iso = "2026-03-04T21:00:00+00:00"
    engine._build_observation_value_map = lambda run_dir=None: dict(value_map)  # type: ignore[assignment]
    return engine


def test_cp2_audit_overwrites_temporal_and_normalizes_minor_value_drift() -> None:
    engine = _engine_stub({"SUBSYSTEM_C": 100.25})
    payload = {
        "predictions_t": [
            {
                "target_id": "SUBSYSTEM_C",
                "direction": "DOWN",
                "snapshot_time": "1999-01-01T00:00:00+00:00",
                "target_time_iso": "1999-01-02T00:00:00+00:00",
                "unit": "dimensionless", "snapshot_value": 100.2,
                "invalidation": "x",
            }
        ]
    }

    audited = GodModeEngine._audit_cp2_predictions(engine, payload)
    pred = audited["predictions_t"][0]
    assert pred["snapshot_time"] == "2026-03-04T00:00:00+00:00"
    assert pred["target_time_iso"] == "2026-03-04T21:00:00+00:00"
    assert pred["snapshot_value"] == 100.25
    assert "_engine_audit_errors" not in audited


def test_cp2_audit_flags_snapshot_value_mismatch() -> None:
    engine = _engine_stub({"SUBSYSTEM_C": 100.25})
    payload = {
        "predictions_t": [
            {
                "target_id": "SUBSYSTEM_C",
                "direction": "DOWN",
                "unit": "dimensionless", "snapshot_value": 120.0,
                "invalidation": "x",
            }
        ]
    }

    audited = GodModeEngine._audit_cp2_predictions(engine, payload)
    pred = audited["predictions_t"][0]
    assert pred["snapshot_value"] == 120.0
    assert pred["snapshot_time"] == "2026-03-04T00:00:00+00:00"
    assert pred["target_time_iso"] == "2026-03-04T21:00:00+00:00"
    assert audited["_engine_audit_errors"][0].startswith("SNAPSHOT_VALUE_MISMATCH")


def test_cp2_audit_keeps_model_snapshot_value_when_feed_value_missing() -> None:
    engine = _engine_stub({})
    payload = {
        "predictions_t": [
            {
                "target_id": "SUBSYSTEM_C",
                "direction": "DOWN",
                "unit": "dimensionless", "snapshot_value": 99.5,
                "invalidation": "x",
            }
        ]
    }

    audited = GodModeEngine._audit_cp2_predictions(engine, payload)
    pred = audited["predictions_t"][0]
    assert pred["snapshot_value"] == 99.5
    assert pred["snapshot_time"] == "2026-03-04T00:00:00+00:00"
    assert pred["target_time_iso"] == "2026-03-04T21:00:00+00:00"
    assert "_engine_audit_errors" not in audited
