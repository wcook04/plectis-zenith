"""Exact obstruction, source custody and native allocation checks."""
from copy import deepcopy
import json
import sqlite3

import pytest

from research.decomposition_tasks import build_dataset, oracle, public_task, reference_source
from zenith.investigation_program import BUILTINS, execute, execute_local, validate_source


@pytest.fixture(scope="module")
def dataset():
    return build_dataset()


def namespace(source):
    result = {"__builtins__": BUILTINS}
    exec(compile(validate_source(source), "<fixture>", "exec"), result)
    return result


def panels(task):
    return [row for name in ("calibration", "development", "screen", "confirmation") for row in task[name]]


def cases(rows):
    return [{"tables": {}, **deepcopy(row["input"])} for row in rows]


@pytest.mark.parametrize("index", range(4))
def test_withheld_ordinary_reference_matches_every_frozen_case(dataset, index):
    task = dataset["tasks"][index]
    rows = panels(task)
    # Exercise the actual resource-limited worker and JSON contract, not just
    # direct execution in the test interpreter.
    results = execute(reference_source(task), cases(rows), answer_contract="json")
    assert all(result["error"] is None for result in results)
    assert [result["answer"] for result in results] == [row["expected"] for row in rows]
    assert all(result["trace"] == [] for result in results)


def test_initial_programs_are_executable_and_control_is_already_correct(dataset):
    for index, task in enumerate(dataset["tasks"]):
        rows = panels(task)
        results = execute_local(task["initial_source"], cases(rows), answer_contract="json")
        assert all(result["error"] is None for result in results)
        successes = sum(result["answer"] == row["expected"] for result, row in zip(results, rows))
        if index == 3:
            assert successes == len(rows)
        else:
            assert successes < len(rows)
            assert task["initial_source"] != reference_source(task)


def test_sensor_equal_raw_totals_require_unequal_answers(dataset):
    task = dataset["tasks"][0]
    program = namespace(task["initial_source"])
    left, right = {"rows": [3]}, {"rows": [1, 2]}
    # Whatever a replacement calibrate(total) does, it receives 3 in both
    # contexts. The caller/interface must preserve an additional distinction.
    assert program["sum_readings"](left["rows"]) == program["sum_readings"](right["rows"])
    assert oracle(task, left) != oracle(task, right)
    assert program["investigate"](left, None) == program["investigate"](right, None)
    assert oracle(task, right) - oracle(task, left) == task["private"]["offset"]
    observed = {json.dumps(row["input"], sort_keys=True): row["expected"] for row in task["calibration"]}
    assert json.dumps(left, sort_keys=True) in observed and json.dumps(right, sort_keys=True) in observed
    # Individual observations identify both integer coefficients; no private
    # reference program or hidden constants need enter the model payload.
    offset = oracle(task, {"rows": [0]})
    scale = oracle(task, {"rows": [1]}) - offset
    assert scale == task["private"]["scale"]
    assert offset != 0


def test_allocator_equal_visible_rows_require_unequal_answers(dataset):
    task = dataset["tasks"][1]
    program = namespace(task["initial_source"])
    left = {"actions": []}
    right = {"actions": [{"op": "put", "id": 4}, {"op": "delete", "id": 4}]}
    assert program["visible_rows"](left["actions"]) == program["visible_rows"](right["actions"]) == []
    assert oracle(task, left) == 1
    assert oracle(task, right) == 5
    assert program["investigate"](left, None) == program["investigate"](right, None) == 1


def native_visible(actions):
    connection = sqlite3.connect(":memory:", isolation_level=None)
    try:
        connection.execute("CREATE TABLE items (id INTEGER PRIMARY KEY AUTOINCREMENT)")
        for action in actions:
            if action["op"] == "put":
                connection.execute("INSERT INTO items(id) VALUES (?)", (action["id"],))
            elif action["op"] == "delete":
                connection.execute("DELETE FROM items WHERE id=?", (action["id"],))
            else:
                connection.execute(action["op"].upper())
        return [row[0] for row in connection.execute("SELECT id FROM items ORDER BY id")]
    finally:
        connection.close()


def test_seed_visible_row_simulator_matches_native_even_while_its_prediction_fails(dataset):
    task = dataset["tasks"][1]
    program = namespace(task["initial_source"])
    for row in panels(task):
        actions = row["input"]["actions"]
        assert program["visible_rows"](actions) == native_visible(actions)


@pytest.mark.parametrize("actions, expected", [
    ([], 1),
    ([{"op": "put", "id": 8}, {"op": "delete", "id": 8}], 9),
    ([{"op": "begin"}, {"op": "put", "id": 9}, {"op": "rollback"}], 1),
    ([{"op": "put", "id": 4}, {"op": "begin"}, {"op": "put", "id": 9}, {"op": "rollback"}], 5),
    ([{"op": "put", "id": 4}, {"op": "begin"}, {"op": "put", "id": 9},
      {"op": "commit"}, {"op": "delete", "id": 9}], 10),
    ([{"op": "begin"}, {"op": "put", "id": 9}], 10),
    ([{"op": "delete", "id": 999}], 1),
])
def test_native_rollback_and_open_transaction_allocation_semantics(dataset, actions, expected):
    assert oracle(dataset["tasks"][1], {"actions": actions}) == expected


def test_stream_projection_loses_both_key_and_timestamp_distinctions(dataset):
    task = dataset["tasks"][2]
    program = namespace(task["initial_source"])
    # Same values, arrival sequence and requested keys; timestamps alone change.
    left = {"events": [{"key": "a", "time": 9, "value": 4}, {"key": "a", "time": 1, "value": 8}], "keys": ["a"]}
    right = {"events": [{"key": "a", "time": 1, "value": 4}, {"key": "a", "time": 9, "value": 8}], "keys": ["a"]}
    assert program["project_values"](left["events"]) == program["project_values"](right["events"])
    assert oracle(task, left) == [{"key": "a", "value": 4}]
    assert oracle(task, right) == [{"key": "a", "value": 8}]
    # Keys alone change in a second boundary collision.
    left = {"events": [{"key": "a", "time": 9, "value": 4}, {"key": "b", "time": 1, "value": 8}], "keys": ["a", "b"]}
    right = {"events": [{"key": "b", "time": 9, "value": 4}, {"key": "a", "time": 1, "value": 8}], "keys": ["a", "b"]}
    assert program["project_values"](left["events"]) == program["project_values"](right["events"])
    assert oracle(task, left) != oracle(task, right)
    assert program["investigate"](left, None) == program["investigate"](right, None)


def test_stream_rule_family_is_identified_by_receipts_and_ties(dataset):
    task = dataset["tasks"][2]
    arrival_task = deepcopy(task)
    arrival_task["private"]["rule"] = "arrival"
    assert any(oracle(task, row["input"]) != oracle(arrival_task, row["input"]) for row in task["calibration"])
    assert oracle(task, {"events": [{"key": "a", "time": 3, "value": 4},
                                    {"key": "a", "time": 3, "value": -2}],
                         "keys": ["missing", "a"]}) == [{"key": "missing", "value": None}, {"key": "a", "value": -2}]


def test_model_payloads_and_evaluation_context_are_isolated(dataset):
    context_probe = '''def investigate(context, acquire):
    return sorted(context.keys())
'''
    allowed = {"id", "family", "description", "initial_source", "focus_function", "calibration", "development"}
    for task in dataset["tasks"]:
        public = public_task(task)
        assert set(public) == allowed
        assert not {"private", "reference_source", "screen", "confirmation"} & set(public)
        results = execute_local(context_probe, cases(panels(task)), answer_contract="json")
        assert [result["answer"] for result in results] == [sorted(row["input"]) for row in panels(task)]
        for row in panels(task):
            assert not {"expected", "private", "seed", "screen", "confirmation"} & set(row["input"])
        public["calibration"][0]["expected"] = "mutated"
        assert task["calibration"][0]["expected"] != "mutated"


def test_dataset_is_deterministic_and_exact_inputs_are_disjoint(dataset):
    assert build_dataset() == dataset
    assert build_dataset(seed=43) != dataset
    assert [task["id"] for task in dataset["tasks"]] == ["task-0", "task-1", "task-2", "task-3"]
    for task in dataset["tasks"]:
        assert len(task["calibration"]) == 8
        observed = set()
        for name in ("calibration", "development", "screen", "confirmation"):
            keys = [json.dumps(row["input"], sort_keys=True) for row in task[name]]
            assert len(keys) == len(set(keys))
            assert not set(keys) & observed
            observed.update(keys)
            assert all(oracle(task, row["input"]) == row["expected"] for row in task[name])


def test_protected_panels_change_structure_beyond_random_constants(dataset):
    for index in (0, 3):
        task = dataset["tasks"][index]
        lengths = [{len(row["input"]["rows"]) for row in task[name]}
                   for name in ("development", "screen", "confirmation")]
        assert not lengths[0] & lengths[1] and not lengths[1] & lengths[2]
    task = dataset["tasks"][2]
    counts = [{len({event["key"] for event in row["input"]["events"]}) for row in task[name]}
              for name in ("development", "screen", "confirmation")]
    assert counts == [{2}, {4}, {6}]
    task = dataset["tasks"][1]
    training_shapes = {tuple(action["op"] for action in row["input"]["actions"]) for row in task["calibration"] + task["development"]}
    for name in ("screen", "confirmation"):
        protected_shapes = {tuple(action["op"] for action in row["input"]["actions"]) for row in task[name]}
        assert protected_shapes - training_shapes
        assert any(shape.count("begin") >= 2 for shape in protected_shapes)


@pytest.mark.parametrize("index, query", [
    (0, {"rows": [True]}), (0, {"rows": [101]}), (0, {"rows": [0] * 33}),
    (0, {"rows": [], "expected": 0}),
    (1, {"actions": [{"op": "put", "id": True}]}),
    (1, {"actions": [{"op": "put", "id": 0}]}),
    (1, {"actions": [{"op": "begin"}, {"op": "begin"}]}),
    (1, {"actions": [{"op": "rollback"}]}),
    (1, {"actions": [{"op": "put", "id": 3}, {"op": "put", "id": 3}]}),
    (1, {"actions": [{"op": "delete", "id": 1}] * 33}),
    (2, {"events": [], "keys": ["a", "a"]}),
    (2, {"events": [{"key": "a", "time": 1001, "value": 0}], "keys": ["a"]}),
    (2, {"events": [{"key": "a", "time": 1, "value": 1.0}], "keys": ["a"]}),
    (2, {"events": [], "keys": ["bad key"]}),
    (2, {"events": [], "keys": [str(i) for i in range(9)]}),
])
def test_oracle_enforces_disclosed_probe_bounds(dataset, index, query):
    with pytest.raises(ValueError):
        oracle(dataset["tasks"][index], query)


@pytest.mark.parametrize("size", [1, 3, 32])
def test_configurable_panel_size_preserves_source_and_separation(size):
    result = build_dataset(seed=9, panel_size=size)
    for task in result["tasks"]:
        assert all(len(task[name]) == size for name in ("development", "screen", "confirmation"))
        keys = [json.dumps(row["input"], sort_keys=True) for row in panels(task)]
        assert len(keys) == len(set(keys))


@pytest.mark.parametrize("seed, size", [(True, 24), (1, 0), (1, 257), (1, True)])
def test_invalid_dataset_envelope_is_rejected(seed, size):
    with pytest.raises(ValueError):
        build_dataset(seed=seed, panel_size=size)
