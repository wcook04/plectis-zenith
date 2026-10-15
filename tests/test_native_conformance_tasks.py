"""Native boundaries, private-panel custody and bounded authored probing."""
from copy import deepcopy
import json
import platform
import sqlite3

import pytest

from research.native_conformance_tasks import (
    MAX_TOTAL_BYTES, PROBE_BUDGET, SOURCE_IDS, authored_fixed_queries,
    build_dataset, measure, public_task, query_units,
)
from research import decomposition_tasks
from zenith.investigation_program import execute_local, validate_source


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def put(key):
    return {"op": "put", "id": key}


def delete(key):
    return {"op": "delete", "id": key}


def call(key):
    return {"op": "call", "key": key}


def op(name):
    return {"op": name}


def feed(values):
    return {"op": "feed", "bytes": values}


@pytest.fixture(scope="module")
def dataset():
    return build_dataset()


@pytest.mark.parametrize("actions,expected", [
    ([], 1), ([put(1000)], 1001), ([put(4), delete(4)], 5),
    ([op("begin"), put(9), op("rollback")], 1),
    ([put(2), op("begin"), delete(2), put(1000), op("rollback")], 3),
    ([op("begin"), put(9), op("commit"), delete(9)], 10),
    ([put(2), op("begin"), put(9)], 10),
    ([delete(999)], 1),
])
def test_sqlite_native_high_water_and_transaction_boundaries(actions, expected):
    query = {"actions": actions}
    assert measure("sqlite-0", query) == expected
    assert measure("sqlite-1", query) == expected
    assert measure("sqlite", query) == decomposition_tasks.oracle({"private": {"kind": "sqlite"}}, query)
    # A separate query always starts an empty connection.
    assert measure("sqlite-0", {"actions": []}) == 1


@pytest.mark.parametrize("actions", [
    [put(True)], [put(0)], [put(1001)], [put(1), put(1)],
    [op("commit")], [op("rollback")], [op("begin"), op("begin")],
    [{"op": "delete", "id": 1, "extra": 0}], [op("RESET")],
    [delete(1)] * 33,
])
def test_sqlite_reuses_strict_legal_history_validation(actions):
    with pytest.raises(ValueError):
        measure("sqlite-0", {"actions": actions})


@pytest.mark.parametrize("capacity", [1, 2, 3, 4])
def test_lru_is_fresh_native_cache_and_reset_clears_counters(capacity):
    assert measure("lru-0", {"capacity": capacity, "events": [call(31), call(31)]}) == {
        "hits": 1, "misses": 1, "size": 1}
    assert measure("lru-1", {"capacity": capacity, "events": [call(31)]}) == {
        "hits": 0, "misses": 1, "size": 1}
    assert measure("lru", {"capacity": capacity, "events": [call(1), call(1), op("reset"), call(1)]}) == {
        "hits": 0, "misses": 1, "size": 1}


def test_lru_hit_updates_recency_and_capacity_one_evicts():
    assert measure("lru", {"capacity": 2, "events": [call(k) for k in (1, 2, 1, 3, 1)]}) == {
        "hits": 2, "misses": 3, "size": 2}
    assert measure("lru", {"capacity": 1, "events": [call(k) for k in (1, 2, 1)]}) == {
        "hits": 0, "misses": 3, "size": 1}


@pytest.mark.parametrize("events,expected", [
    ([], {"count": 0, "status": "open"}),
    ([feed([]), op("finish")], {"count": 0, "status": "finished"}),
    ([feed([194])], {"count": 0, "status": "open"}),
    ([feed([194]), feed([163]), op("finish")], {"count": 1, "status": "finished"}),
    ([feed([240, 159]), feed([152]), feed([128]), op("finish")], {"count": 1, "status": "finished"}),
    ([feed([244, 143, 191, 191]), op("finish")], {"count": 1, "status": "finished"}),
    ([feed([194]), op("finish")], {"count": 0, "status": "error"}),
    ([feed([65, 255])], {"count": 0, "status": "error"}),
    ([feed([65]), feed([66, 255])], {"count": 1, "status": "error"}),
    ([feed([65, 194]), feed([66])], {"count": 1, "status": "error"}),
    ([feed([237, 160, 128])], {"count": 0, "status": "error"}),
    ([feed([244, 144, 128, 128])], {"count": 0, "status": "error"}),
    ([feed([192, 128])], {"count": 0, "status": "error"}),
    ([feed([255]), op("reset"), feed([65]), op("finish")], {"count": 1, "status": "finished"}),
    ([feed([194]), op("reset"), feed([65])], {"count": 1, "status": "open"}),
    ([op("finish"), op("reset"), feed([194])], {"count": 0, "status": "open"}),
])
def test_utf8_native_incomplete_invalid_atomic_chunk_and_reset(events, expected):
    assert measure("utf8-0", {"events": events}) == expected
    assert measure("utf8-1", {"events": events}) == expected
    assert measure("utf8", {"events": []}) == {"count": 0, "status": "open"}


@pytest.mark.parametrize("events", [
    [op("finish"), feed([])], [op("finish"), op("finish")],
    [feed([255]), feed([])], [feed([128]), op("finish")],
])
def test_events_after_terminal_require_reset(events):
    with pytest.raises(ValueError, match="terminal"):
        measure("utf8", {"events": events})


@pytest.mark.parametrize("source,query", [
    ("lru", {"capacity": True, "events": []}),
    ("lru", {"capacity": 0, "events": []}),
    ("lru", {"capacity": 5, "events": []}),
    ("lru", {"capacity": 2, "events": [call(True)]}),
    ("lru", {"capacity": 2, "events": [call(32)]}),
    ("lru", {"capacity": 2, "events": [{"op": "reset", "key": 0}]}),
    ("lru", {"capacity": 2, "events": [None]}),
    ("lru", {"capacity": 2, "events": [op("reset")] * 33}),
    ("utf8", {"events": [feed([True])]}),
    ("utf8", {"events": [feed([-1])]}),
    ("utf8", {"events": [feed([256])]}),
    ("utf8", {"events": [feed((65,))]}),
    ("utf8", {"events": [feed([65] * 65)]}),
    ("utf8", {"events": [feed([65] * 64)] * 5}),
    ("utf8", {"events": [op("reset")] * 33}),
    ("utf8", {"events": [True]}),
    ("utf8", {"events": [{"op": "finish", "final": True}]}),
    ("utf8", {"events": [feed([255]), {"op": "reset", "extra": 0}]}),
    ("utf8", {"events": [] , "expected": {"count": 0}}),
    ("sqlite", {"actions": (), "extra": 0}),
])
def test_typed_shape_and_nested_budget_legality(source, query):
    with pytest.raises(ValueError):
        measure(source, query)
    with pytest.raises(ValueError):
        query_units(query)


@pytest.mark.parametrize("source", [None, True, 1, "unknown", "sqlite-2", "lru-00"])
def test_unknown_or_untyped_source_is_rejected(source):
    with pytest.raises(ValueError):
        measure(source, {})


def test_work_units_are_source_specific_bounded_counts():
    assert query_units({"actions": [put(1), delete(1)]}) == 4
    assert query_units({"capacity": 1, "events": [call(0), op("reset")]}) == 3
    assert query_units({"events": [feed([194]), feed([163]), op("finish")]}) == 6
    query = {"events": [feed([65] * 64)] * 4 + [op("reset")] * 28}
    assert query_units(query) == 289
    assert MAX_TOTAL_BYTES == 256
    assert measure("utf8", query) == {"count": 0, "status": "open"}


def test_six_fresh_parent_tasks_freeze_versions_and_do_not_supply_initial_bug(dataset):
    assert [t["source_id"] for t in dataset["tasks"]] == [
        "sqlite-0", "lru-0", "utf8-0", "sqlite-1", "lru-1", "utf8-1"]
    assert len({t["id"] for t in dataset["tasks"]}) == 6
    assert dataset["source_versions"]["python"] == platform.python_version()
    assert dataset["source_versions"]["sqlite"] == sqlite3.sqlite_version
    assert dataset["adaptation"]["sha256"] == "dd6a1256438f83593c4078fe207d9e4953dd7668064b229ae6cc97f46648614a"
    for task in dataset["tasks"]:
        assert len(task["examples"]) == 8
        assert not {"initial_source", "initial_program", "bug", "private"} & set(task)
        for panel in ("screen", "confirmation"):
            assert len(task[panel]) == 48
            assert all(measure(task["source_id"], row["input"]) == row["expected"] for row in task[panel])


def test_native_panels_cover_disclosed_contract_features(dataset):
    for task in dataset["tasks"]:
        kind = SOURCE_IDS[task["source_id"]]
        for panel in ("screen", "confirmation"):
            rows = task[panel]
            if kind == "sqlite":
                ops = {a["op"] for row in rows for a in row["input"]["actions"]}
                assert ops == {"put", "delete", "begin", "commit", "rollback"}
                assert any(sum(a["op"] == "begin" for a in row["input"]["actions"])
                           > sum(a["op"] in ("commit", "rollback") for a in row["input"]["actions"])
                           for row in rows)
            elif kind == "lru":
                assert {row["input"]["capacity"] for row in rows} == {1, 2, 3, 4}
                assert any(op("reset") in row["input"]["events"] for row in rows)
            else:
                assert {row["expected"]["status"] for row in rows} == {"open", "finished", "error"}
                assert any(op("reset") in row["input"]["events"] for row in rows)


def test_public_allowlist_copies_only_contract_and_examples(dataset):
    for task in dataset["tasks"]:
        poisoned = deepcopy(task)
        poisoned["private_truth"] = "do not send"
        public = public_task(poisoned)
        assert set(public) == {"id", "source_id", "contract", "examples"}
        assert not {"screen", "confirmation", "fixed_queries", "reference_source", "private_truth"} & set(public)
        public["examples"][0]["expected"] = "mutated"
        assert task["examples"][0]["expected"] != "mutated"


def test_fixed_tester_is_public_input_only_and_uses_boundaries_and_proper_prefixes(dataset):
    for task in dataset["tasks"]:
        kind = SOURCE_IDS[task["source_id"]]
        observed = {canonical(r["input"]) for r in task["examples"]}
        protected = {canonical(r["input"]) for panel in ("screen", "confirmation") for r in task[panel]}
        queries = task["fixed_queries"]
        assert len(queries) == len({canonical(q) for q in queries}) == PROBE_BUDGET == 8
        assert not {canonical(q) for q in queries} & (observed | protected)
        labels_changed = [{"input": deepcopy(r["input"]), "expected": "never read"} for r in task["examples"]]
        assert authored_fixed_queries(task["source_id"], labels_changed) == queries
        field = "actions" if kind == "sqlite" else "events"
        prefixes = set()
        for row in task["examples"]:
            for cut in range(len(row["input"][field])):
                prefix = deepcopy(row["input"])
                prefix[field] = prefix[field][:cut]
                prefixes.add(canonical(prefix))
        if kind == 'utf8':
            assert [q['events'][0]['bytes'] for q in queries] == [
                [0xC0], [0xC1], [0xF5], [0xFF], [0xE0, 0x9F],
                [0xED, 0xA0], [0xF0, 0x8F], [0xF4, 0x90]]
        else:
            assert any(canonical(q) in prefixes for q in queries)
            assert any(canonical(q) not in prefixes for q in queries)
        assert all(query_units(q) <= dataset["max_query_units"][kind] for q in queries)
        assert sum(query_units(q) for q in queries) <= PROBE_BUDGET * dataset["max_query_units"][kind]
        for query in queries:
            measure(task["source_id"], query)


def test_frozen_fresh_inputs_are_disjoint_across_panels_and_parent_replicates(dataset):
    seen = {kind: set() for kind in ("sqlite", "lru", "utf8")}
    for task in dataset["tasks"]:
        kind = SOURCE_IDS[task["source_id"]]
        public_keys = {canonical(r["input"]) for r in task["examples"]}
        fixed_keys = {canonical(q) for q in task["fixed_queries"]}
        for panel in ("screen", "confirmation"):
            keys = [canonical(row["input"]) for row in task[panel]]
            assert len(keys) == len(set(keys))
            assert not set(keys) & (seen[kind] | public_keys | fixed_keys)
            seen[kind].update(keys)


def test_sqlite_and_lru_competent_restricted_controls_match_all_frozen_rows(dataset):
    for task in dataset["tasks"]:
        source = task["reference_source"]
        if task["source_id"].startswith("utf8"):
            assert source is None
            continue
        validate_source(source)
        rows = task["examples"] + task["screen"] + task["confirmation"]
        results = execute_local(source, [{"tables": {}, **deepcopy(row["input"])} for row in rows], answer_contract="json")
        assert all(result["error"] is None and result["trace"] == [] for result in results)
        assert [result["answer"] for result in results] == [row["expected"] for row in rows]


def test_dataset_is_seeded_and_panel_size_is_bounded(dataset):
    assert build_dataset() == dataset
    changed = build_dataset(seed=20261016, panel_size=4)
    assert len(changed["tasks"]) == 6
    assert all(len(t["screen"]) == len(t["confirmation"]) == 4 for t in changed["tasks"])
    assert changed["tasks"][0]["screen"] != dataset["tasks"][0]["screen"][:4]


@pytest.mark.parametrize("options", [{"seed": True}, {"seed": "1"}, {"panel_size": True},
                                     {"panel_size": 0}, {"panel_size": 257}])
def test_invalid_dataset_configuration(options):
    with pytest.raises(ValueError):
        build_dataset(**options)
