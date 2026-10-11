"""
[PURPOSE]
- Teleology: Orchestrate the bounded Polymarket scan while preserving the stable tool entrypoint and matrix envelope consumed by downstream feeds, diff lanes, and UI adapters.
- Mechanism: Hydrate config -> fetch Gamma events -> normalize/suppress malformed or resolved markets -> score the four lenses -> emit the matrix envelope.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional

from system.lib.types import TOOL_METADATA_SCHEMA_VERSION, ArtifactEnvelope
from tools.polymarket.client import GammaClient
from tools.polymarket.config import hydrate_runtime_options
from tools.polymarket.emit import build_legend, emit_matrix
from tools.polymarket.clob_snapshot import build_clob_snapshot, empty_clob_snapshot
from tools.polymarket.identity import (
    build_identity_snapshot,
    empty_identity_snapshot,
    extract_market_identities,
)
from tools.polymarket.lifecycle import classify_all_lifecycles
from tools.polymarket.normalize import normalize_events
from tools.polymarket.resolved_archive import (
    build_resolved_archive_candidates,
    empty_resolved_archive_candidates,
)


class StandardActor:
    TOOL_NAME = "polymarket"
    TOOL_VERSION = "5.0 (Annex-Informed Scanner)"
    DATA_SCHEMA_VERSION = "polymarket.2"

    def __init__(
        self,
        config: Dict[str, Any],
        run_dir: Optional[str] = None,
        *,
        request_get: Callable[..., Any] | None = None,
        request_post: Callable[..., Any] | None = None,
    ) -> None:
        self.config = config
        self.run_dir = run_dir
        self.request_get = request_get
        self.request_post = request_post
        self.options = hydrate_runtime_options(config)
        self.diagnostics: Dict[str, Any] = {
            "fetched": 0,
            "fetched_events": 0,
            "fetched_markets": 0,
            "noise_killed": 0,
            "zombies_killed": 0,
            "rescued_safe": 0,
            "dropped_volume": 0,
            "dropped_liquidity": 0,
            "dropped_malformed": 0,
            "dropped_resolved": 0,
            "dropped_topicless": 0,
            "dropped_status": 0,
            "deduped_rows": 0,
            "warnings": [],
            "errors": [],
        }

    def _get_time_context(self) -> str:
        anchor = self.options.runtime.get("time_anchor")
        if anchor:
            return str(anchor)
        return datetime.now(timezone.utc).isoformat()

    def _get_run_id(self) -> str:
        runtime_run_id = self.options.runtime.get("run_id")
        if runtime_run_id:
            return str(runtime_run_id)
        if self.run_dir:
            import os

            return os.path.basename(self.run_dir)
        return "unknown_run"

    def _build_metadata(
        self,
        *,
        start_ts: float,
        status: str,
        items_count: int,
        diagnostics: Dict[str, Any],
        legend: Dict[str, str],
        sidecars: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        timestamp_iso = datetime.fromtimestamp(start_ts, tz=timezone.utc).replace(microsecond=0).isoformat()
        return {
            "status": status,
            "items_count": items_count,
            "timestamp": start_ts,
            "timestamp_iso": timestamp_iso,
            "timestamp_epoch_s": start_ts,
            "schema_version": TOOL_METADATA_SCHEMA_VERSION,
            "data_schema_version": self.DATA_SCHEMA_VERSION,
            "override_keys": [],
            "tool": self.TOOL_NAME,
            "diagnostics": diagnostics,
            "data_schema": legend,
            "run_id": self._get_run_id(),
            "as_of": self._get_time_context(),
            "legend": legend,
            "sidecars": sidecars if sidecars is not None else {},
        }

    def execute(self) -> ArtifactEnvelope:
        start_ts = time.time()
        legend = build_legend(self.options.output)

        try:
            if not self.options.api.base_url:
                raise ValueError("Config missing 'api' section. Unwrap failed or invalid config.")

            client = GammaClient(self.options.api, request_get=self.request_get)
            events = client.fetch_events(self.diagnostics)

            # Pre-normalization identity extraction over the FULL raw Gamma universe.
            # Substrate root: the measurement-substrate WorkItem (spine cap
            # cap_quick_polymarket_intelligence_spine_graduate_g_2804be84e1df) requires
            # identity coverage of markets the scanner will drop downstream, so the
            # extraction runs before normalize_events applies any filter.
            identity_rows = extract_market_identities(events)

            # Bet lifecycle classification over the FULL identity universe.
            # Substrate root: lifecycle subordinates CLOB book interpretation —
            # no_clob_book on a DE_FACTO_TERMINAL market is expected, not anomalous
            # (operator correction 2026-05-12). CLOB enrichment consumes the
            # classifications to skip terminal states before issuing any HTTP.
            as_of_iso = self._get_time_context()
            lifecycle_classifications = classify_all_lifecycles(
                identity_rows,
                as_of_iso=as_of_iso,
                options=self.options.lifecycle,
            )
            identity_snapshot = build_identity_snapshot(
                identity_rows,
                lifecycle_classifications=lifecycle_classifications,
            )

            # CLOB enrichment over the lifecycle-filtered identity rows
            # (default-disabled via config). When enabled, makes bounded read-only
            # HTTP calls to the public CLOB endpoints; cap hard-capped at
            # MAX_CAP=500 inside hydrate_clob_options.
            clob_snapshot = build_clob_snapshot(
                identity_rows,
                self.options.clob,
                self.diagnostics,
                request_get=self.request_get,
                request_post=self.request_post,
                as_of=as_of_iso,
                lifecycle_classifications=lifecycle_classifications,
            )
            resolved_archive_candidates = build_resolved_archive_candidates(
                identity_rows,
                lifecycle_classifications,
                as_of=as_of_iso,
            )

            sidecars: Dict[str, Any] = {
                "polymarket_market_identity_snapshot": identity_snapshot,
                "polymarket_clob_snapshot": clob_snapshot,
                "polymarket_resolved_archive_candidates": resolved_archive_candidates,
            }

            markets = normalize_events(events, self.options, self.diagnostics)
            data, total_rows = emit_matrix(markets, self.options.topics.keys(), self.options.output, self.diagnostics)

            dropped_rows = sum(
                int(self.diagnostics.get(key, 0))
                for key in (
                    "noise_killed",
                    "zombies_killed",
                    "dropped_volume",
                    "dropped_liquidity",
                    "dropped_malformed",
                    "dropped_resolved",
                    "dropped_topicless",
                    "dropped_status",
                )
            )
            warnings = [str(item) for item in self.diagnostics.get("warnings", []) if str(item).strip()]
            diagnostics = {
                **self.diagnostics,
                "input_rows": int(self.diagnostics.get("fetched_markets", 0)),
                "output_rows": int(total_rows),
                "dropped_rows": dropped_rows,
                "warnings": warnings,
                "errors": warnings,
            }

            return {
                "metadata": self._build_metadata(
                    start_ts=start_ts,
                    status="success",
                    items_count=total_rows,
                    diagnostics=diagnostics,
                    legend=legend,
                    sidecars=sidecars,
                ),
                "data": data,
            }

        except Exception as exc:
            warning = str(exc)
            diagnostics = {
                **self.diagnostics,
                "error": warning,
                "input_rows": int(self.diagnostics.get("fetched_markets", 0)),
                "output_rows": 0,
                "dropped_rows": sum(
                    int(self.diagnostics.get(key, 0))
                    for key in (
                        "noise_killed",
                        "zombies_killed",
                        "dropped_volume",
                        "dropped_liquidity",
                        "dropped_malformed",
                        "dropped_resolved",
                        "dropped_topicless",
                        "dropped_status",
                    )
                ),
                "warnings": [warning] if warning else [],
            }
            return {
                "metadata": self._build_metadata(
                    start_ts=start_ts,
                    status="failure",
                    items_count=0,
                    diagnostics=diagnostics,
                    legend=legend,
                    sidecars={
                        "polymarket_market_identity_snapshot": empty_identity_snapshot(),
                        "polymarket_clob_snapshot": empty_clob_snapshot(),
                        "polymarket_resolved_archive_candidates": empty_resolved_archive_candidates(),
                    },
                ),
                "data": {},
            }


def run(config: Dict[str, Any], run_dir: Optional[str] = None) -> ArtifactEnvelope:
    actor = StandardActor(config, run_dir)
    return actor.execute()
