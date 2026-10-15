"""Bounded family identification and exact future-distinction checks."""
from copy import deepcopy
import hashlib
from itertools import product
import json

import pytest

from research.state_discovery_tasks import (
    build_dataset, build_transfer_dataset, candidate_family, compatible_configs, oracle, public_task, reference_source,
)
from zenith.investigation_program import BUILTINS, execute, execute_local, validate_source


@pytest.fixture(scope="module")
def dataset():
    return build_dataset()


def rows(task):
    return [row for name in ("calibration", "development", "screen", "confirmation") for row in task[name]]


def cases(examples):
    return [{"tables": {}, **deepcopy(row["input"])} for row in examples]


def namespace(source):
    answer = {"__builtins__": BUILTINS}
    exec(compile(validate_source(source), "<reference>", "exec"), answer)
    return answer


@pytest.mark.parametrize("index", range(3))
def test_correct_reference_runs_all_panels_in_restricted_worker(dataset, index):
    task = dataset["tasks"][index]
    examples = rows(task)
    result = execute(reference_source(task), cases(examples), answer_contract="json")
    assert all(row["error"] is None for row in result)
    assert [row["answer"] for row in result] == [row["expected"] for row in examples]
    assert all(row["trace"] == [] for row in result)


def literal_passes(config, values):
    """Third implementation: transform full lists rather than weighted sums
    or incremental register state. It is exclusively evaluator-side."""
    a, b, c = config["coefficients"]
    contributions = []
    for index, value in enumerate(values):
        memory = 0
        if config["interaction"] == "adjacent" and index:
            memory = values[index - 1]
        elif config["interaction"] == "prefix":
            memory = sum(values[:index])
        contributions.append(a * value + b * value * value + c * value * value * value
                             + config["cross_coefficient"] * value * memory)
    for unused in range(config["passes"]):
        contributions = [sum(contributions[:index + 1]) for index in range(len(contributions))]
    return contributions[-1] if contributions else 0


def test_oracle_formula_reference_and_literal_list_contract_agree(dataset):
    for task in dataset["tasks"]:
        predictor = namespace(reference_source(task))["investigate"]
        for length in range(5):
            for values in product((-2, 0, 1, 2), repeat=length):
                query = {"values": list(values)}
                expected = literal_passes(task["private"], query["values"])
                assert oracle(task, query) == expected
                assert predictor(query, None) == expected


def test_disclosed_finite_family_identifies_each_source_without_private_answers(dataset):
    family = list(candidate_family())
    assert len(family) == 4464
    assert len({json.dumps(config, sort_keys=True) for config in family}) == len(family)
    for task in dataset["tasks"]:
        matches = compatible_configs(task["calibration"])
        assert len(matches) == 1
        config = {key: task["private"][key] for key in matches[0]}
        assert matches[0] == config
        assert compatible_configs(task["calibration"] + task["development"]) == matches
        # Fitting uses source observations only; it does not consult future
        # labels or a truth field while searching the declared finite family.
        changed = deepcopy(task["calibration"])
        changed[0]["expected"] = 1
        assert not compatible_configs(changed)


def test_cross_history_choices_are_genuinely_different():
    common = {"coefficients": [1, 0, 0], "passes": 3, "cross_coefficient": 1}
    adjacent = {"private": {**common, "interaction": "adjacent"}}
    prefix = {"private": {**common, "interaction": "prefix"}}
    query = {"values": [1, 2, 3]}
    assert oracle(adjacent, query) == 27
    assert oracle(prefix, query) == 30


def test_initial_focus_boundary_has_exact_same_summary_different_future_pairs(dataset):
    for index, task in enumerate(dataset["tasks"]):
        program = namespace(task["initial_source"])
        if index < 2:
            left, right = [1, 0], [0, 1]
        else:
            left, right = [1, 0], [1, 0, 0]
        continuation = [0]
        assert program["summarize_values"](left) == program["summarize_values"](right)
        assert program["summarize_values"](left + continuation) == program["summarize_values"](right + continuation)
        assert oracle(task, {"values": left + continuation}) != oracle(task, {"values": right + continuation})
        assert program["investigate"]({"values": left + continuation}, None) == program["investigate"]({"values": right + continuation}, None)
        results = execute_local(task["initial_source"], cases(rows(task)), answer_contract="json")
        assert all(result["error"] is None for result in results)
        assert any(result["answer"] != row["expected"] for result, row in zip(results, rows(task)))


def test_equal_actual_present_outputs_do_not_determine_continuation(dataset):
    for task in dataset["tasks"]:
        witness = task["private"]["continuation_witness"]
        left, right, continuation = witness["left"], witness["right"], witness["continuation"]
        assert left != right
        assert oracle(task, {"values": left}) == oracle(task, {"values": right}) == witness["present"]
        assert oracle(task, {"values": left + continuation}) == witness["left_future"]
        assert oracle(task, {"values": right + continuation}) == witness["right_future"]
        assert witness["left_future"] != witness["right_future"]


def test_private_state_configs_references_and_witnesses_do_not_enter_model_inputs(dataset):
    context_probe = '''def investigate(context, acquire):
    return sorted(context.keys())
'''
    allowed = {"id", "family", "description", "initial_source", "focus_function", "calibration", "development"}
    for task in dataset["tasks"]:
        public = public_task(task)
        assert set(public) == allowed
        assert not {"private", "screen", "confirmation", "coefficients", "passes", "continuation_witness"} & set(public)
        assert reference_source(task) not in json.dumps(public)
        assert task["description"] == dataset["tasks"][0]["description"]
        assert all(set(row["input"]) == {"values"} for row in rows(task))
        result = execute_local(context_probe, cases(rows(task)), answer_contract="json")
        assert all(row["answer"] == ["values"] for row in result)
        public["calibration"][0]["expected"] = "changed"
        assert task["calibration"][0]["expected"] == 0


def test_frozen_panels_are_deterministic_disjoint_and_structurally_longer(dataset):
    assert build_dataset() == dataset
    assert build_dataset(seed=2) != dataset
    for task in dataset["tasks"]:
        assert len(task["calibration"]) == 12
        seen = set()
        lengths = []
        for name in ("calibration", "development", "screen", "confirmation"):
            keys = [json.dumps(row["input"], sort_keys=True) for row in task[name]]
            assert len(keys) == len(set(keys))
            assert not seen & set(keys)
            seen.update(keys)
            lengths.append({len(row["input"]["values"]) for row in task[name]})
            assert all(oracle(task, row["input"]) == row["expected"] for row in task[name])
        assert max(lengths[1]) < min(lengths[2])
        assert max(lengths[2]) < min(lengths[3])
        for name in ("screen", "confirmation"):
            sequences = [row["input"]["values"] for row in task[name]]
            assert any(any(value < 0 for value in sequence) for sequence in sequences)
            assert any(sequence.count(0) >= len(sequence) - 1 for sequence in sequences)
            assert any(any(value < 0 for value in sequence) and any(value > 0 for value in sequence)
                       for sequence in sequences)


def test_source_cross_memory_has_measurable_effect_on_calibration(dataset):
    task = dataset["tasks"][2]
    removed = deepcopy(task)
    removed["private"]["interaction"] = "none"
    removed["private"]["cross_coefficient"] = 0
    assert any(oracle(task, row["input"]) != oracle(removed, row["input"]) for row in task["calibration"])


@pytest.mark.parametrize("input", [
    {}, {"values": [], "expected": 0}, {"values": (1, 2)}, {"values": [True]},
    {"values": [1.0]}, {"values": [9]}, {"values": [-9]}, {"values": [0] * 33},
    {"values": ["1"]}, {"values": [None]},
])
def test_source_contract_bounds_are_enforced(dataset, input):
    with pytest.raises(ValueError):
        oracle(dataset["tasks"][0], input)


@pytest.mark.parametrize("size", [1, 7, 32])
def test_panel_size_is_configurable_without_leaking_labels(size):
    data = build_dataset(seed=5, panel_size=size)
    for task in data["tasks"]:
        assert all(len(task[name]) == size for name in ("development", "screen", "confirmation"))
        keys = [json.dumps(row["input"]) for row in rows(task)]
        assert len(keys) == len(set(keys))


@pytest.mark.parametrize("seed, size", [(True, 24), (1, 0), (1, 129), (1, True), (1, 1.0)])
def test_invalid_dataset_arguments_are_rejected(seed, size):
    with pytest.raises(ValueError):
        build_dataset(seed=seed, panel_size=size)


@pytest.fixture(scope="module")
def transfer():
    return build_transfer_dataset()


def config(task):
    return {key: task["private"][key] for key in ("coefficients", "passes", "interaction", "cross_coefficient")}


def test_original_dataset_bytes_remain_identical():
    serialized = json.dumps(build_dataset(), sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    assert hashlib.sha256(serialized).hexdigest() == "6adcd0cd75e77804b3cd4a6711557917d5a8110ebf06391a95cc63991e98dcf1"


@pytest.mark.parametrize("index", range(6))
def test_transfer_references_match_every_new_case_in_restricted_executor(transfer, index):
    task = transfer["tasks"][index]
    examples = rows(task)
    results = execute(reference_source(task), cases(examples), answer_contract="json")
    assert all(result["error"] is None for result in results)
    assert [result["answer"] for result in results] == [row["expected"] for row in examples]
    assert all(result["trace"] == [] for result in results)


def test_transfer_bindings_are_fresh_balanced_and_calibration_identified(dataset, transfer):
    old = {json.dumps(config(task), sort_keys=True) for task in dataset["tasks"]}
    fresh = {json.dumps(config(task), sort_keys=True) for task in transfer["tasks"]}
    assert len(fresh) == 6 and not old & fresh
    interactions = [task["private"]["interaction"] for task in transfer["tasks"]]
    assert all(interactions.count(mode) == 2 for mode in ("none", "adjacent", "prefix"))
    assert {task["private"]["passes"] for task in transfer["tasks"]} == {1, 2, 3, 4}
    for task in transfer["tasks"]:
        coefficients = task["private"]["coefficients"]
        assert 0 in coefficients and min(coefficients) < 0 < max(coefficients)
        assert compatible_configs(task["calibration"]) == [config(task)]
        results = execute_local(task["initial_source"], cases(rows(task)), answer_contract="json")
        assert all(result["error"] is None for result in results)
        assert any(result["answer"] != row["expected"] for result, row in zip(results, rows(task)))


def test_transfer_inputs_are_separate_truth_is_private_and_present_output_witness_is_honest(transfer):
    for task in transfer["tasks"]:
        seen = set()
        for name in ("calibration", "development", "screen", "confirmation"):
            keys = [json.dumps(row["input"], sort_keys=True) for row in task[name]]
            assert len(keys) == len(set(keys)) and not set(keys) & seen
            seen.update(keys)
            assert all(oracle(task, row["input"]) == row["expected"] for row in task[name])
            assert all(set(row["input"]) == {"values"} for row in task[name])
        assert not {"private", "screen", "confirmation"} & set(public_task(task))
        witness = task["private"]["continuation_witness"]
        if witness is None:
            assert task["private"]["interaction"] == "none" and task["private"]["passes"] == 1
        else:
            left, right, continuation = witness["left"], witness["right"], witness["continuation"]
            assert oracle(task, {"values": left}) == oracle(task, {"values": right})
            assert oracle(task, {"values": left + continuation}) != oracle(task, {"values": right + continuation})


def test_transfer_clarification_changes_syntax_guidance_only(transfer):
    unclarified = build_transfer_dataset(interface_clarification=False)
    for clarified, plain in zip(transfer["tasks"], unclarified["tasks"]):
        assert "single-underscore" in clarified["description"]
        assert "other leading-underscore" in clarified["description"]
        assert "multiplication" in clarified["description"]
        assert "no defaults" in clarified["description"]
        assert clarified["description"].startswith(plain["description"])
        assert "Execution interface clarification" not in plain["description"]
        assert {key: value for key, value in clarified.items() if key != "description"} == {
            key: value for key, value in plain.items() if key != "description"}
    assert build_transfer_dataset() == transfer


@pytest.mark.parametrize("seed, size, clarification", [(True, 24, True), (1, 0, True),
                                                        (1, 129, True), (1, True, True),
                                                        (1, 24, "yes")])
def test_transfer_rejects_invalid_arguments(seed, size, clarification):
    with pytest.raises(ValueError):
        build_transfer_dataset(seed, size, clarification)
