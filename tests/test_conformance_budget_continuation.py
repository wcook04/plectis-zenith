"""Funding amendments reuse settled identities; fake HTTP is the only transport."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from research import conformance_study as study
from research.native_conformance_tasks import LRU_CONTRACT, LRU_REFERENCE
from scripts import continue_conformance_budget as continuation
from zenith.budgeted import OpenRouterBudgetedProvider
from zenith.providers import digest, write_json

MODEL = "fixture/chinese-text"
ROUTE = "fixture/endpoint"
ROW = {"id": MODEL, "context_length": 131072,
       "architecture": {"input_modalities": ["text"], "output_modalities": ["text"]},
       "pricing": {"prompt": "0.0000005", "completion": "0.000001", "request": "0"},
       "supported_parameters": ["max_tokens", "temperature", "structured_outputs", "response_format", "reasoning"],
       "top_provider": {"context_length": 131072, "max_completion_tokens": 4096}}
ENDPOINT = {"model_id": MODEL, "tag": ROUTE, "provider_name": "Fixture Host", "status": 0,
            "context_length": 131072, "max_completion_tokens": 4096,
            "max_prompt_tokens": None, "supported_parameters": ROW["supported_parameters"],
            "pricing": ROW["pricing"]}


@pytest.fixture
def stopped(tmp_path, monkeypatch):
    """A real terminal run stops after its settled parent on reservation capacity."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-v1-FAKE_OFFLINE_ONLY")
    monkeypatch.setattr("zenith.budgeted.require_model", lambda *a, **k: None)
    monkeypatch.setattr("zenith.budgeted.require_prices", lambda *a, **k: None)
    monkeypatch.setattr("zenith.provider_policy._inference_root", lambda: tmp_path / "gates")
    output, resumed = tmp_path / "original", tmp_path / "resumed"
    data = {"schema": "fixture", "tasks": [{
        "id": "native-lru-0", "source_id": "lru-0", "contract": LRU_CONTRACT,
        "parent_replicate": 0, "private": {}, "reference_source": LRU_REFERENCE,
        "examples": [{"input": {"capacity": 1, "events": []},
                      "expected": {"hits": 0, "misses": 0, "size": 0}}],
        "fixed_queries": [],
        "screen": [{"input": {"capacity": 1, "events": []},
                    "expected": {"hits": 0, "misses": 0, "size": 0}}],
        "confirmation": [{"input": {"capacity": 1, "events": []},
                          "expected": {"hits": 0, "misses": 0, "size": 0}}],
    }]}
    calls = []

    def catalogue(url, headers, timeout):
        assert "Authorization" not in headers
        return {"data": [ROW]} if url.endswith("/models") else {
            "data": {"id": MODEL, "endpoints": [ENDPOINT]}}

    def post(url, headers, payload, timeout):
        calls.append(deepcopy(payload))
        content = json.dumps({"source": LRU_REFERENCE, "scope": "fixture", "change": "fixture"})
        return {"model": MODEL, "provider": "Fixture Host", "id": "fixture-generation",
                "usage": {"prompt_tokens": 10, "completion_tokens": 10,
                          "total_tokens": 20, "cost": "0.00001"},
                "choices": [{"message": {"content": content}}]}

    def factory(folder):
        return lambda task, route: OpenRouterBudgetedProvider(
            folder / "providers" / task["id"], MODEL,
            study.read(folder / "protocol.json")["max_cost_usd"], 2, 1024,
            folder / "budget", provider_slug=route, inference_mode="bounded",
            catalogue_get=catalogue, caller=post)

    study.prepare(output, MODEL, [ROUTE], dataset=data, arms=("repair_only",),
                  workers=1, max_output_tokens=1024, max_cost_usd="0.006")
    result = study.run(output, provider_factory=factory(output))
    assert result["complete"] is False and len(calls) == 1, result
    protocol = study.read(output / "protocol.json")
    freeze = tmp_path / "prospective.json"
    write_json(freeze, {"schema": "zenith_progress_prospective_freeze_v1",
                        "diagnostic": {"protocol_sha256": continuation.sha(output / "protocol.json"),
                                       "dataset_sha256": digest(data), "maximum_model_calls": 2}})
    monkeypatch.setattr(continuation, "run", lambda folder, env: study.run(
        folder, provider_factory=factory(folder)))
    return output, resumed, freeze, calls


def test_funding_copy_preserves_original_and_reuses_exact_prior_call_without_http(stopped):
    original, resumed, freeze, calls = stopped
    before = continuation.file_hashes(original)
    prior = study.read(original / "budget/budget.json")["entries"]
    receipt = continuation.prepare(original, resumed, freeze, max_cost_usd="1")
    assert receipt["prior_paid_attempts"] == 1
    assert receipt["prior_call_ids"] == sorted(prior)
    assert continuation.verify_prepared(resumed, original, freeze) == receipt
    assert continuation.file_hashes(original) == before
    assert not (resumed / "started.json").exists()
    result = continuation.run_prepared(resumed, original, freeze)
    assert result["totals"]["repair_only"]["correct"] == 1
    assert len(calls) == 2  # Only the previously unattempted repair reached HTTP.
    current = study.read(resumed / "budget/budget.json")["entries"]
    assert len(current) == 2
    assert all(current[key] == value for key, value in prior.items())
    assert continuation.file_hashes(original) == before
    assert study.replay(resumed)["model_calls_replayed"] == 2
    assert not (original / "screen.json").exists()
    assert not (original / "confirmation.json").exists()
    with pytest.raises(ValueError, match="already started"):
        continuation.run_prepared(resumed, original, freeze)
    assert len(calls) == 2


@pytest.mark.parametrize("cap", ["0.006", "0.001", "4.01", "NaN", "-1"])
def test_unauthorized_or_non_enlarging_funding_is_rejected_before_copy(stopped, cap):
    original, resumed, freeze, calls = stopped
    with pytest.raises(ValueError):
        continuation.prepare(original, resumed, freeze, max_cost_usd=cap)
    assert not resumed.exists() and len(calls) == 1


@pytest.mark.parametrize("change", ["protected_panel", "unknown", "failed", "active", "complete", "freeze"])
def test_unopened_settled_prefix_is_required(stopped, change):
    original, resumed, freeze, calls = stopped
    if change == "protected_panel":
        write_json(original / "confirmation-selection.json", {})
    elif change in ("unknown", "failed", "active"):
        budget = study.read(original / "budget/budget.json")
        entry = next(iter(budget["entries"].values()))
        if change == "unknown":
            entry["cost"] = None
        else:
            entry["status"] = "failed" if change == "failed" else "attempt_started"
        write_json(original / "budget/budget.json", budget)
    elif change == "complete":
        frozen = study.read(original / "frozen.json")
        frozen["complete"] = True
        write_json(original / "frozen.json", frozen)
    else:
        frozen = study.read(freeze)
        frozen["diagnostic"]["protocol_sha256"] = "0" * 64
        write_json(freeze, frozen)
    with pytest.raises((ValueError, AssertionError)):
        continuation.prepare(original, resumed, freeze, max_cost_usd="1")
    assert not resumed.exists() and len(calls) == 1


@pytest.mark.parametrize("target", ["original", "response", "protocol", "budget", "extra", "binding"])
def test_prepared_custody_rejects_changes_before_any_new_inference(stopped, target):
    original, resumed, freeze, calls = stopped
    continuation.prepare(original, resumed, freeze, max_cost_usd="1")
    if target == "original":
        path = original / "datasets.json"
    elif target == "response":
        path = next((resumed / "responses").glob("*.json"))
    elif target == "protocol":
        path = resumed / "protocol.json"
    elif target == "budget":
        path = resumed / "budget/budget.json"
    elif target == "binding":
        path = next((resumed / "providers").glob("*/handoff/budgeted_binding.json"))
    else:
        path = resumed / "extra.txt"
    path.write_text(path.read_text() + " " if path.exists() else "unowned")
    with pytest.raises((ValueError, AssertionError)):
        continuation.run_prepared(resumed, original, freeze)
    assert len(calls) == 1


@pytest.mark.parametrize("field", ["prior_paid_attempts", "prior_call_ids", "clone_administrative_files", "original_cap_usd"])
def test_funding_receipt_cannot_exempt_scientific_files_or_rewrite_paid_identity(stopped, field):
    original, resumed, freeze, calls = stopped
    continuation.prepare(original, resumed, freeze, max_cost_usd="1")
    path = resumed / "funding-continuation.json"
    receipt = study.read(path)
    if field == "clone_administrative_files":
        response = next((resumed / "responses").glob("*.json"))
        response.write_text(response.read_text() + " ")
        receipt[field][str(response.relative_to(resumed))] = continuation.sha(response)
    elif field == "prior_call_ids":
        receipt[field] = []
    elif field == "prior_paid_attempts":
        receipt[field] = 2
    else:
        receipt[field] = "0.001"
    write_json(path, receipt)
    with pytest.raises(ValueError, match="Funding receipt"):
        continuation.run_prepared(resumed, original, freeze)
    assert len(calls) == 1
