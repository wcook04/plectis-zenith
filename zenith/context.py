"""Audited metadata projection for full feed data in reasoning context.

This profile removes duplicate acquisition/debug metadata only. It never reduces
feed data, edits a canonical artifact, or silently substitutes a price basis.
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from .providers import digest

PROFILE = "compact_feeds"
METADATA_KEYS = frozenset({
    "schema_version", "data_schema_version", "tool", "status", "error", "message",
    "timestamp", "timestamp_iso", "timestamp_epoch_s", "as_of", "time_anchor", "effective_date", "effective_time",
    "run_id", "provider", "source", "price_basis", "price_observations", "interval", "auto_adjust",
    "currency", "timezone", "session_date", "bar_date", "observation_time", "observed_at", "acquired_at",
    "vintage_date", "observation_date", "available_at", "release_time", "event_time",
    "items_count", "data_quality", "quality", "feed_health", "freshness", "coverage",
    "config_ref", "merged_hash", "override_keys", "hydrated_from", "hydrated_from_truth",
    "target_time_iso", "horizon_label", "synthetic_fixture", "cached", "cache_hit",
})
DIAGNOSTIC_KEYS = frozenset({
    "input_rows", "output_rows", "dropped_rows", "warnings", "errors", "items_count",
    "data_available_unused_count", "price_observations", "data_quality", "quality", "feed_health",
    "source_status", "source_statuses", "missing_fields", "missing_tickers", "missing_series",
    "provider", "interval", "auto_adjust", "session_date", "price_basis", "currency", "timezone",
    "lag_seconds", "freshness", "coverage", "error_count", "warning_count",
})


def compact_feed_envelope(envelope: dict, *, artifact_path: Path, artifact_ref: str | None = None) -> dict:
    metadata = envelope.get("metadata", {})
    if not isinstance(metadata, dict):
        raise ValueError("feed metadata must be an object for compact projection")
    projected = {key: copy.deepcopy(value) for key, value in metadata.items() if key in METADATA_KEYS}
    diagnostics = metadata.get("diagnostics", {})
    omitted_diagnostics = []
    if isinstance(diagnostics, dict):
        projected["diagnostics"] = {key: copy.deepcopy(value) for key, value in diagnostics.items() if key in DIAGNOSTIC_KEYS}
        omitted_diagnostics = sorted(set(diagnostics) - DIAGNOSTIC_KEYS)
    raw = Path(artifact_path).read_bytes()
    projected["context_projection"] = {
        "schema": "zenith_feed_context_projection_v1", "profile": PROFILE,
        "full_artifact_sha256": hashlib.sha256(raw).hexdigest(),
        "full_artifact_ref": artifact_ref or str(artifact_path),
        "data_sha256": digest(envelope.get("data")), "data_preserved": True,
        "omitted_metadata_keys": sorted(set(metadata) - METADATA_KEYS - {"diagnostics"}),
        "omitted_diagnostic_keys": omitted_diagnostics,
        "source_metadata_chars": len(json.dumps(metadata, separators=(",", ":"), ensure_ascii=False)),
        "projection_rule": "metadata allowlist only; full feed data is preserved; omitted metadata remains in the cited artifact",
    }
    result = copy.deepcopy(envelope)
    result["metadata"] = projected
    return result


def gather_compact_feed_inputs(engine, node, inherited: dict) -> dict:
    """Restore full canonical data for feed dependencies, then project metadata."""
    result = dict(inherited)
    for dependency_id in node.dependencies:
        dependency = engine._universe.get(dependency_id)
        if dependency is None or not dependency.meta.get("is_feed"):
            continue
        path = engine.artifacts_dir / (dependency_id + ".json")
        if not path.exists():
            continue
        envelope = json.loads(path.read_text())
        try:
            artifact_ref = str(path.relative_to(engine.root_dir))
        except ValueError:
            artifact_ref = str(path)
        result[dependency_id] = compact_feed_envelope(envelope, artifact_path=path, artifact_ref=artifact_ref)
    return result
