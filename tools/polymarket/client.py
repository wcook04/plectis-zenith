"""
[PURPOSE]
- Teleology: Fetch a bounded Polymarket Gamma event slice with deterministic pagination and diagnostics.
- Mechanism: Request one or more pages, normalize the response envelope, and stop early if the API repeats already-seen events.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List

import requests

from system.lib import feed_envelope
from tools.polymarket.config import ApiOptions


def _event_key(event: Dict[str, Any], fallback: str) -> str:
    for candidate in (event.get("id"), event.get("slug"), event.get("ticker")):
        text = str(candidate or "").strip()
        if text:
            return text
    return fallback


def _extract_events(payload: Any) -> List[Dict[str, Any]]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict):
        for key in ("data", "events"):
            if isinstance(payload.get(key), list):
                return [row for row in payload[key] if isinstance(row, dict)]
    return []


class GammaClient:
    def __init__(
        self,
        api: ApiOptions,
        *,
        request_get: Callable[..., Any] | None = None,
    ) -> None:
        self.api = api
        self.request_get = request_get or requests.get

    def fetch_events(self, diagnostics: Dict[str, Any]) -> List[Dict[str, Any]]:
        seen: set[str] = set()
        events: List[Dict[str, Any]] = []
        pages = 0

        for page_index in range(self.api.pagination_cap):
            params = {
                "limit": self.api.limit,
                "offset": page_index * self.api.limit,
                "active": "true",
                "closed": "false",
                "order": "volume",
                "ascending": "false",
            }
            response = self.request_get(self.api.base_url, params=params, timeout=self.api.timeout)
            response.raise_for_status()
            batch = _extract_events(response.json())
            feed_envelope.record_fetch_outcome(diagnostics, ok=True)
            pages += 1
            if not batch:
                break

            deduped_batch: List[Dict[str, Any]] = []
            for idx, event in enumerate(batch):
                key = _event_key(event, fallback=f"page-{page_index}-row-{idx}")
                if key in seen:
                    continue
                seen.add(key)
                deduped_batch.append(event)

            if page_index > 0 and not deduped_batch:
                diagnostics.setdefault("warnings", []).append(
                    f"Pagination repeated existing events at page {page_index}; stopped early."
                )
                break

            events.extend(deduped_batch)

            if len(batch) < self.api.limit:
                break

        diagnostics["pages"] = pages
        diagnostics["fetched"] = len(events)
        diagnostics["fetched_events"] = len(events)
        return events
