"""Offline delivery, counterexample, preservation and custody checks."""
from copy import deepcopy
import json
from pathlib import Path
import threading

import pytest

from research import conformance_study as study
from research.native_conformance_tasks import LRU_CONTRACT, LRU_REFERENCE, UTF8_CONTRACT


MODEL = "deepseek/deepseek-v4.1-flash"
ROUTE = "fixture/endpoint"
PRIVATE = "private-configuration-never-delivered"
REFERENCE = "private-reference-never-delivered"
SCREEN = "protected-screen-never-delivered"
CONFIRMATION = "protected-confirmation-never-delivered"
PARENT = '''def investigate(context, acquire):
    calls = [event for event in context["events"] if event["op"] == "call"]
    return {"hits": 0, "misses": len(calls), "size": min(context["capacity"], len(calls))}
'''
CORRECT = LRU_REFERENCE
PROBE = {"capacity": 1, "events": [{"op": "call", "key": 7}, {"op": "call", "key": 7}]}
NOTE = {"claim": "The parent may count a repeated call as a miss.",
        "change": "Keep the cache membership and its recency.",
        "test": "Repeat one key in the same fresh cache."}
POLICY = '''def investigate(context, acquire):
    return {"query": {"capacity": 1, "events": [{"op": "call", "key": 7}, {"op": "call", "key": 7}]},
            "note": {"claim": "The parent may count a repeated call as a miss.",
                     "change": "Keep the cache membership and its recency.",
                     "test": "Repeat one key in the same fresh cache."}}
'''


def tiny_dataset():
    """A real, inexpensive native source; protected fields are conspicuous."""
    return {"schema": "offline-conformance-fixture", "tasks": [{
        "id": "native-lru-0", "source_id": "lru-0", "contract": LRU_CONTRACT,
        "private": {"sentinel": PRIVATE}, "reference_source": REFERENCE,
        "parent_replicate": 0,
        "examples": [
            {"input": {"capacity": 1, "events": []},
             "expected": {"hits": 0, "misses": 0, "size": 0}},
            {"input": {"capacity": 1, "events": [{"op": "call", "key": 1}]},
             "expected": {"hits": 0, "misses": 1, "size": 1}},
        ],
        "fixed_queries": [deepcopy(PROBE)],
        "screen": [{"input": {"capacity": 1, "events": [
            {"op": "call", "key": 22}, {"op": "call", "key": 22}]},
            "expected": {"hits": 1, "misses": 1, "size": 1}, "sentinel": SCREEN}],
        "confirmation": [{"input": {"capacity": 2, "events": [
            {"op": "call", "key": 23}, {"op": "call", "key": 23},
            {"op": "reset"}, {"op": "call", "key": 23}]},
            "expected": {"hits": 0, "misses": 1, "size": 1}, "sentinel": CONFIRMATION}],
    }]}


def response(source=CORRECT):
    return json.dumps({"source": source, "scope": "Offline fixture proposal.",
                       "change": "Fixture executable change."})


class FixtureProvider:
    """Exact finite response tape; any extra call fails the test."""
    def __init__(self, root, responses):
        self.run_dir = Path(root)
        self.responses = list(responses)
        self.calls = []
        self.lock = threading.Lock()

    def ask_ai(self, prompt, options, cancel=None):
        with self.lock:
            self.calls.append({"prompt": json.loads(prompt), "options": deepcopy(options)})
            assert cancel is not None and not cancel.is_set()
            if not self.responses:
                raise AssertionError("Unexpected extra inference attempt")
            result = self.responses.pop(0)
            if isinstance(result, Exception):
                raise result
            return result


def prepared(tmp_path, *, arms=("ordinary",), dataset=None):
    output = tmp_path / "study"
    study.prepare(output, MODEL, [ROUTE], arms=arms, workers=1,
                  max_output_tokens=1024, dataset=dataset or tiny_dataset())
    return output


def factory(provider):
    def construct(task, route):
        assert task["id"] == "native-lru-0"
        assert route == ROUTE
        return provider
    return construct


def completed(tmp_path, *, responses=None, arms=("ordinary",)):
    output = prepared(tmp_path, arms=arms)
    provider = FixtureProvider(tmp_path / "provider", responses or [
        response(PARENT), response(POLICY), response(CORRECT)])
    result = study.run(output, provider_factory=factory(provider))
    return output, provider, result


def test_measured_native_feedback_and_note_reach_the_actual_repair_request(tmp_path):
    output, provider, result = completed(tmp_path)
    assert len(provider.calls) == 3
    repair = provider.calls[2]["prompt"]
    assert repair["parent_source"] == PARENT
    assert repair["parent_examples"]["correct"] == 2
    evidence = repair["investigation"]
    assert evidence["detected"] and evidence["semantic_defect"]
    assert not evidence["technical_defect"]
    witness = evidence["receipts"][0]
    assert witness["query"] == PROBE
    assert witness["expected"] == {"hits": 1, "misses": 1, "size": 1}
    assert witness["parent_answer"] == {"hits": 0, "misses": 2, "size": 1}
    assert witness["note"] == NOTE
    assert witness["verified_counterexample"] is True
    assert study.repair_examples(tiny_dataset()["tasks"][0], evidence)[-1] == {
        "input": PROBE, "expected": witness["expected"]}
    selected = study.read(output / "frozen.json")["records"][0]["arms"]["ordinary"]["selected"]
    assert selected["source"] == CORRECT
    assert selected["preserves_measured_parent_successes"] is True
    assert selected["development"]["correct"] == 3
    assert result["totals"]["ordinary"]["correct"] == 1
    assert result["detection"]["ordinary"]["native_probes"] == 1


def test_actual_provider_requests_strip_truth_panels_and_fixed_probe_answers(tmp_path):
    tape = [response(PARENT), response(POLICY), response(),
            response(POLICY), response(), response()]
    output, provider, unused = completed(tmp_path, arms=study.LEGACY_ARMS, responses=tape)
    assert len(provider.calls) == 6
    for call in provider.calls:
        material = json.dumps(call)
        for sentinel in (PRIVATE, REFERENCE, SCREEN, CONFIRMATION):
            assert sentinel not in material
        assert set(call["prompt"]["task"]) == {"id", "source_id", "contract", "examples"}
        assert set(call["options"]["meta"]) == {"session_id", "node_id"}
        assert call["options"]["reasoning_effort"] == "low"
        assert call["options"]["response_format"]["json_schema"]["schema"] == study.SCHEMA
    for index in (1, 3):
        assert provider.calls[index]["options"]["system_prompt"] == study.POLICY_LANGUAGE
        assert provider.calls[index]["prompt"]["parent_source"] == PARENT
    for index in (0, 2, 4, 5):
        assert provider.calls[index]["options"]["system_prompt"] == study.LANGUAGE
    assert study.replay(output)["model_calls_replayed"] == 6


def test_policy_execution_receives_only_public_context_and_measured_receipts(monkeypatch):
    seen = []
    original = study.invoke

    def inspect(source, context):
        if source == POLICY:
            seen.append(deepcopy(context))
        return original(source, context)

    monkeypatch.setattr(study, "invoke", inspect)
    task = tiny_dataset()["tasks"][0]
    result = study.investigate(task, PARENT, POLICY)
    assert result["detected"] is True
    assert len(seen) == 1
    assert set(seen[0]) == {"source_id", "contract", "parent_source", "examples", "receipts", "remaining_slots"}
    assert seen[0]["receipts"] == []
    assert all(sentinel not in json.dumps(seen) for sentinel in (PRIVATE, REFERENCE, SCREEN, CONFIRMATION))


@pytest.mark.parametrize("extra_wrong", [1, 2])
def test_repair_cannot_exchange_an_old_success_for_more_new_successes(extra_wrong):
    parent_source = 'def investigate(context, acquire):\n    return 0\n'
    replacement = parent_source.replace("return 0", "return 1")
    parent = {"source": parent_source, "error": None, "call_id": "parent"}
    candidate = {"source": replacement, "error": None, "call_id": "repair"}
    examples = [{"input": {"value": 0}, "expected": 0}]
    examples += [{"input": {"value": n + 1}, "expected": 1} for n in range(extra_wrong)]
    selected = study.selected_candidate(parent, candidate, examples)
    assert selected["candidate_on_final_evidence"]["correct"] >= selected["parent_on_final_evidence"]["correct"]
    assert selected["preserves_measured_parent_successes"] is False
    assert selected["candidate_selected"] is False
    assert selected["source"] == parent_source
    assert selected["call_id"] == "parent"


def test_invalid_and_duplicate_queries_consume_slots_without_becoming_defects():
    policy = '''def investigate(context, acquire):
    index = len(context["receipts"])
    choices = [{"capacity": 1, "events": []},
               {"capacity": 0, "events": []},
               {"capacity": 0, "events": []},
               {"capacity": 1, "events": [{"op": "call", "key": 7}, {"op": "call", "key": 7}]},
               None]
    return {"query": choices[index]}
'''
    result = study.investigate(tiny_dataset()["tasks"][0], CORRECT, policy)
    assert result["slots_used"] == 5
    assert result["query_attempts"] == 2
    assert result["native_probes"] == 1
    assert result["policy_executions"] == 5
    assert result["detected"] is False
    assert result["witness_sha256"] is None
    assert all("query_error" in row for row in result["receipts"][:3])
    assert result["receipts"][3]["verified_counterexample"] is False
    assert result["receipts"][4]["stopped"] is True
    assert len(study.repair_examples(tiny_dataset()["tasks"][0], result)) == 3


def test_probe_cap_stops_invalid_attempts_without_automatic_repair():
    policy = '''def investigate(context, acquire):
    return {"query": {"capacity": -context["remaining_slots"], "events": []}}
'''
    result = study.investigate(tiny_dataset()["tasks"][0], PARENT, policy, cap=3)
    assert result["slots_used"] == result["query_attempts"] == result["policy_executions"] == 3
    assert result["native_probes"] == 0
    assert not result["detected"]
    assert all("expected" not in row for row in result["receipts"])


@pytest.mark.parametrize("body", [
    "[]", '{"query": None, "expected": 999}',
    '{"query": None, "note": "x" * 2049}',
])
def test_malformed_policy_output_stops_without_native_measurement(body):
    source = f"def investigate(context, acquire):\n    return {body}\n"
    result = study.investigate(tiny_dataset()["tasks"][0], PARENT, source)
    assert result["slots_used"] == result["policy_executions"] == 1
    assert result["query_attempts"] == result["native_probes"] == 0
    assert not result["detected"]
    assert "policy_error" in result["receipts"][0]


def test_native_decoder_error_is_a_valid_measured_output_not_an_invalid_query():
    task = {"source_id": "utf8", "contract": UTF8_CONTRACT, "examples": []}
    parent = 'def investigate(context, acquire):\n    return {"count": 0, "status": "open"}\n'
    policy = '''def investigate(context, acquire):
    return {"query": {"events": [{"op": "feed", "bytes": [255]}]}}
'''
    result = study.investigate(task, parent, policy)
    assert result["native_probes"] == result["query_attempts"] == 1
    assert result["semantic_defect"] and not result["technical_defect"]
    assert result["receipts"][0]["expected"] == {"count": 0, "status": "error"}


def test_runtime_failure_is_distinct_from_a_semantic_counterexample():
    parent = 'def investigate(context, acquire):\n    return 1 // 0\n'
    result = study.investigate(tiny_dataset()["tasks"][0], parent, POLICY)
    assert result["detected"] and result["technical_defect"]
    assert not result["semantic_defect"]
    assert "ZeroDivisionError" in result["receipts"][0]["parent_error"]


def test_panel_opening_preserves_selection_and_never_dispatches_again(tmp_path):
    output, provider, unused = completed(tmp_path)
    frozen = study.read(output / "frozen.json")
    assert study.read(output / "frozen-receipt.json")["frozen_sha256"] == study.digest(frozen)
    result = study.evaluate(output, "confirmation")
    assert result["totals"]["ordinary"]["correct"] == 1
    assert study.read(output / "frozen.json") == frozen
    assert study.replay(output) == {
        "ok": True, "model_calls_replayed": 3, "native_investigations": 1,
        "protected_partitions": ["screen", "confirmation"]}
    assert len(provider.calls) == 3
    with pytest.raises(ValueError, match="already opened"):
        study.evaluate(output, "confirmation")
    with pytest.raises(ValueError, match="cannot be retried"):
        study.run(output, provider_factory=factory(provider))


def test_provider_failure_is_one_attempt_and_a_started_study_is_not_retried(tmp_path):
    output = prepared(tmp_path)
    provider = FixtureProvider(tmp_path / "provider", [RuntimeError("fixture transport failure")])
    result = study.run(output, provider_factory=factory(provider))
    assert result["complete"] is False
    assert len(provider.calls) == 1
    assert "fixture transport failure" in result["failures"][0]["error"]
    assert study.read(output / "frozen.json")["complete"] is False
    with pytest.raises(ValueError, match="cannot be retried"):
        study.run(output, provider_factory=factory(provider))
    with pytest.raises(ValueError, match="Incomplete"):
        study.evaluate(output, "confirmation")
    assert len(provider.calls) == 1


@pytest.mark.parametrize("raw", [
    "not JSON", "[]", '{"scope":"missing source","change":"none"}',
    response("import os"), response("def investigate(:\n    return 0\n"),
    json.dumps({"source": CORRECT, "scope": 9, "change": "wrong type"}),
])
def test_malformed_model_deliveries_are_outcomes_and_exactly_replay(tmp_path, raw):
    output, provider, unused = completed(tmp_path, responses=[response(PARENT), response(POLICY), raw])
    frozen = study.read(output / "frozen.json")
    item = frozen["records"][0]["arms"]["ordinary"]
    assert item["candidate"]["error"] is not None
    assert item["selected"]["candidate_selected"] is False
    assert item["selected"]["source"] == PARENT
    assert study.read(output / "responses/native-lru-0-ordinary-repair.json")["raw"] == raw
    assert study.replay(output)["model_calls_replayed"] == 3
    assert len(provider.calls) == 3


@pytest.mark.parametrize("artifact", ["response", "prompt", "dataset", "protocol", "archive", "panel", "selection", "summary", "frozen"])
def test_exact_replay_detects_tampering_beyond_aggregate_scores(tmp_path, artifact):
    output, unused_provider, unused = completed(tmp_path)
    if artifact == "archive":
        path = output / "runtime-source.zip"
        path.write_bytes(path.read_bytes() + b"tamper")
    else:
        paths = {"response": "responses/native-lru-0-ordinary-repair.json",
                 "prompt": "prompts/native-lru-0-ordinary-repair.json",
                 "dataset": "datasets.json", "protocol": "protocol.json",
                 "panel": "screen.json", "selection": "screen-selection.json",
                 "summary": "screen-summary.json", "frozen": "frozen.json"}
        path = output / paths[artifact]
        data = study.read(path)
        if artifact == "response":
            data["raw"] += " "  # Semantics unchanged; byte custody still changes.
        elif artifact == "prompt":
            data["prompt"]["instruction"] += " Changed instruction."
        elif artifact == "dataset":
            data["tasks"][0]["confirmation"][0]["expected"]["hits"] = 99
        elif artifact == "protocol":
            data["reasoning_effort"] = "none"
        elif artifact == "panel":
            data["tasks"]["native-lru-0"]["arms"]["ordinary"]["selected"]["rows"][0]["answer"]["hits"] = 99
        elif artifact == "selection":
            data["selection"]["native-lru-0"]["ordinary"] = "other-selection"
        elif artifact == "summary":
            data["totals"]["ordinary"]["correct"] = 99
        else:
            data["records"][0]["arms"]["ordinary"]["investigation"]["receipts"][0]["expected"]["hits"] = 99
        study.write_json(path, data)
        if artifact == "frozen":
            # Recomputing the custody hash must not defeat semantic replay.
            receipt = study.read(output / "frozen-receipt.json")
            study.write_json(output / "frozen-receipt.json", {**receipt, "frozen_sha256": study.digest(data)})
    with pytest.raises((AssertionError, ValueError)):
        study.replay(output)


def test_summary_derives_panel_counts_from_rows_and_rejects_forged_totals(tmp_path):
    output, unused_provider, unused = completed(tmp_path)
    data = study.read(output / "screen.json")
    data["tasks"]["native-lru-0"]["arms"]["ordinary"]["selected"]["correct"] = 99
    with pytest.raises(ValueError, match="totals differ"):
        study.summarize_results(data, study.read(output / "frozen.json"))
