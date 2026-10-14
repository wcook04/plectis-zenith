"""Separate, synthetic state-induction fixtures; no native-domain claim.

The design adapts the polynomial/cumulative source family inspected in deep
return 02 and the continuation distinctions inspected in deep return 13. No
returned learner or native implementation is copied or exposed to a model.
The finite family below is researcher-supplied bias, not an acquired language.
All source truth, competent controls and witnesses remain host-only.
"""
from __future__ import annotations

from copy import deepcopy
from itertools import product
import json
from math import comb
import random

from research.decomposition_tasks import public_task


DEFAULT_SEED = 20261014
MAX_VALUES = 32
VALUE_BOUND = 8
COEFFICIENTS = (-2, -1, 0, 1, 2)
CROSS_COEFFICIENTS = (-2, -1, 1, 2)

DESCRIPTION = """Synthetic resettable integer source. Input is exactly
{"values":[integer,...]}, length 0..32, values -8..8. Return one JSON integer;
the empty sequence returns zero. Allowed probes use this same schema. There
are no tables, clocks, external data or persistent state across queries.

The following finite family is supplied research bias. Choose a nonzero
polynomial p(x)=a*x+b*x*x+c*x*x*x, with a,b,c each in {-2,-1,0,1,2}. For each
list position its contribution is p(x), optionally plus g*x times either the
immediately preceding value or the sum of all preceding values; g is in
{-2,-1,1,2}, and missing preceding values contribute zero. Apply between one
and four inclusive cumulative-sum passes to the contribution list, preserving
list order. Return the last entry after those passes. The source's choices
are fixed and private; none is specified by the seed program. Use the measured
examples to infer a predictor. Implement investigate(context, acquire).
"""


def _initial_source(current: bool) -> str:
    expression = "values[-1] if values else 0" if current else "sum(values)"
    return f'''def summarize_values(values):
    return {expression}

def readout(summary):
    return summary

def investigate(context, acquire):
    return readout(summarize_values(context["values"]))
'''


def _values(input: dict) -> list[int]:
    if type(input) is not dict or set(input) != {"values"}:
        raise ValueError("input must contain exactly values")
    values = input["values"]
    if type(values) is not list or len(values) > MAX_VALUES:
        raise ValueError("values must be a list of at most 32 entries")
    if any(type(value) is not int or not -VALUE_BOUND <= value <= VALUE_BOUND for value in values):
        raise ValueError("values must be integers -8..8")
    return values


def _measure(config: dict, values: list[int]) -> int:
    """Independent closed-form oracle, rather than the iterative reference."""
    a, b, c = config["coefficients"]
    depth = config["passes"]
    mode, gamma = config["interaction"], config["cross_coefficient"]
    count = len(values)
    answer = 0
    for index, value in enumerate(values):
        contribution = a * value + b * value * value + c * value * value * value
        if mode == "adjacent":
            memory = values[index - 1] if index else 0
        elif mode == "prefix":
            memory = sum(values[:index])
        else:
            memory = 0
        contribution += gamma * value * memory
        answer += comb(count - index + depth - 2, depth - 1) * contribution
    return answer


def oracle(task: dict, input: dict) -> int:
    """Host-only exact integer measurement on a fresh bounded sequence."""
    return _measure(task["private"], _values(input))


def _reference(config: dict) -> str:
    a, b, c = config["coefficients"]
    depth, gamma, mode = config["passes"], config["cross_coefficient"], config["interaction"]
    memory_update = "memory = value" if mode == "adjacent" else "memory += value"
    if mode == "none":
        memory_update = "memory = 0"
    return f'''def input_contribution(value, memory):
    return {a} * value + {b} * value * value + {c} * value * value * value + {gamma} * value * memory

def sequence_state(values):
    state = [0] * {depth}
    memory = 0
    for value in values:
        contribution = input_contribution(value, memory)
        for index in range(len(state)):
            state[index] += contribution
            contribution = state[index]
        {memory_update}
    return {{"state": state, "memory": memory}}

def readout(summary):
    return summary["state"][-1]

def investigate(context, acquire):
    return readout(sequence_state(context["values"]))
'''


def reference_source(task: dict) -> str:
    """Withheld ordinary Python control, compatible with restricted execution."""
    return task["private"]["reference_source"]


def _calibration() -> list[dict]:
    return [{"values": list(values)} for values in (
        (), (0,), (1,), (2,), (-1,), (1, 0), (0, 1), (1, 1),
        (1, 0, 0), (1, 1, 1), (1, 2, 1), (2, 1, 0))]


def candidate_family():
    """Enumerate the disclosed 4,464 structural/parameter combinations.

    This is an evaluator audit, never a supplied model-side solver. Different
    combinations can represent the same function; identifying code syntax is
    not the task. None has a delayed exception outside the supplied family.
    """
    for coefficients in product(COEFFICIENTS, repeat=3):
        if coefficients == (0, 0, 0):
            continue
        for passes in range(1, 5):
            yield {"coefficients": list(coefficients), "passes": passes,
                   "interaction": "none", "cross_coefficient": 0}
            for interaction in ("adjacent", "prefix"):
                for gamma in CROSS_COEFFICIENTS:
                    yield {"coefficients": list(coefficients), "passes": passes,
                           "interaction": interaction, "cross_coefficient": gamma}


def compatible_configs(rows: list[dict]) -> list[dict]:
    """Host audit of identifiability against the explicitly disclosed family."""
    return [config for config in candidate_family()
            if all(_measure(config, row["input"]["values"]) == row["expected"] for row in rows)]


def _continuation_witness(config: dict) -> dict:
    """Find equal actual present readouts with unequal future readouts."""
    continuations = ([0], [1], [-1], [1, 0])
    observed = {}
    for length in range(1, 5):
        for word in product((-2, -1, 0, 1, 2), repeat=length):
            history = list(word)
            present = _measure(config, history)
            for earlier in observed.get(present, []):
                for continuation in continuations:
                    left = _measure(config, earlier + continuation)
                    right = _measure(config, history + continuation)
                    if left != right:
                        return {"left": earlier, "right": history, "continuation": continuation,
                                "present": present, "left_future": left, "right_future": right}
            observed.setdefault(present, []).append(history)
    raise ValueError("no continuation distinction found in the bounded audit")


def _input(rng: random.Random, panel: int, index: int) -> dict:
    lengths = ((2, 3, 4, 5, 6), (8, 9, 10, 12, 14), (16, 20, 24, 28, 32))[panel]
    count = lengths[index % len(lengths)]
    mode = index % 6
    if mode == 0:
        values = [rng.randint(-3, 3) for unused in range(count)]
    elif mode == 1:
        values = [0] * count
        values[rng.randrange(count)] = rng.choice((-4, -3, -2, 2, 3, 4))
    elif mode == 2:
        values = [rng.choice((-3, -2, -1, 1, 2, 3))] * count
    elif mode == 3:
        magnitude = rng.randint(1, 4)
        values = [magnitude if item % 2 else -magnitude for item in range(count)]
    elif mode == 4:
        values = [0 if item % 3 else rng.randint(-4, 4) for item in range(count)]
    else:
        # A zero run between impulses changes how earlier observations can
        # affect later output without introducing an additional source rule.
        values = [rng.randint(-4, 4)] + [0] * (count - 2) + [rng.choice((-3, -2, 2, 3))]
    return {"values": values}


def _canonical(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def build_dataset(seed: int = DEFAULT_SEED, panel_size: int = 24) -> dict:
    """Build a separately versioned stage; no provider calls or integration."""
    if type(seed) is not int:
        raise ValueError("seed must be an integer")
    if type(panel_size) is not int or not 1 <= panel_size <= 128:
        raise ValueError("panel_size must be an integer 1..128")
    rng = random.Random(seed)
    configs = [
        {"coefficients": [0, rng.choice((1, 2)), 0], "passes": 2,
         "interaction": "none", "cross_coefficient": 0},
        {"coefficients": [rng.choice((1, 2)), rng.choice((1, 2)), rng.choice((1, 2))], "passes": 3,
         "interaction": "none", "cross_coefficient": 0},
        {"coefficients": [2, -1, rng.choice((1, 2))], "passes": 3,
         "interaction": "adjacent", "cross_coefficient": rng.choice(CROSS_COEFFICIENTS)},
    ]
    tasks = []
    for index, config in enumerate(configs):
        task = {"id": f"state-{index}", "family": "synthetic_integer_sequence",
                "description": DESCRIPTION, "initial_source": _initial_source(index == 2),
                "focus_function": "readout", "private": deepcopy(config)}
        task["private"]["reference_source"] = _reference(config)
        task["private"]["continuation_witness"] = _continuation_witness(config)
        task["calibration"] = [{"input": query, "expected": oracle(task, query)} for query in _calibration()]
        # The finite supplied bias makes these calibration examples identifying
        # for these selected sources; this is verified offline before freezing.
        matches = compatible_configs(task["calibration"])
        if matches != [config]:
            raise ValueError("selected source is not uniquely identified by its calibration receipts")
        task["private"]["calibration_identification"] = {"family_size": 4464, "consistent_configurations": 1}
        seen = {_canonical(row["input"]) for row in task["calibration"]}
        for panel, name in enumerate(("development", "screen", "confirmation")):
            rows = []
            for attempt in range(panel_size * 200):
                query = _input(rng, panel, attempt)
                key = _canonical(query)
                if key not in seen:
                    seen.add(key)
                    rows.append({"input": query, "expected": oracle(task, query)})
                if len(rows) == panel_size:
                    break
            if len(rows) != panel_size:
                raise RuntimeError("could not construct a distinct panel")
            task[name] = rows
        tasks.append(task)
    return {"schema": "zenith-state-discovery-tasks-v1", "seed": seed, "panel_size": panel_size,
            "source_module": "research/state_discovery_tasks.py",
            "provenance": ["Adapted mechanism design from inspected deep return 02 src/native.py and RETURN.md.",
                           "Continuation obstruction design informed by inspected deep return 13 RETURN.md and predictive closure derivation."],
            "limitations": ["Every source is synthetic host integer arithmetic; no SQLite or other native-domain result is claimed.",
                            "A finite family of 4,464 configurations and its operation language are supplied research bias.",
                            "Training identifies the selected source within that family; arbitrary delayed exceptions are excluded by assumption.",
                            "Reference implementations use two, three and four changing registers respectively, with no universal minimal-state claim.",
                            "Held-out histories test bounded longer reuse within selected mechanisms, not learning-policy transfer or independent replication.",
                            "The model is not supplied the returned exact learner, evaluator enumeration, source coefficients, depth, witnesses or correct reference."],
            "tasks": tasks}


INTERFACE_CLARIFICATION = """
Execution interface clarification: Use named or single-underscore loop
variables; other leading-underscore names remain forbidden. Use multiplication
rather than **; no defaults.
"""


def build_transfer_dataset(seed: int = 20261015, panel_size: int = 24,
                           interface_clarification: bool = True) -> dict:
    """Six fresh bindings for a separately versioned configuration comparison.

    This does not alter ``build_dataset`` or replay its old model proposals.
    None/adjacent/prefix interactions each occur twice; all four pass counts
    occur. Signed, zero-containing polynomial coefficients remain in the
    original disclosed family. The optional clarification supplies syntax
    guidance only and should be identical across paired model settings.
    """
    if type(seed) is not int:
        raise ValueError("seed must be an integer")
    if type(panel_size) is not int or not 1 <= panel_size <= 128:
        raise ValueError("panel_size must be an integer 1..128")
    if type(interface_clarification) is not bool:
        raise ValueError("interface_clarification must be a boolean")
    # Reuse the existing input-generation/panel route. Its labels and private
    # truth are discarded and remeasured for the fresh source configuration.
    templates = [build_dataset(seed=seed + offset, panel_size=panel_size) for offset in (0, 1)]
    rng = random.Random(seed)
    shapes = [
        ("none", 1, (-1, 0, 1)), ("none", 4, (0, -1, 1)),
        ("adjacent", 2, (1, 0, -1)), ("adjacent", 4, (-1, 1, 0)),
        ("prefix", 1, (0, 1, -1)), ("prefix", 3, (-1, 0, 1)),
    ]
    tasks = []
    for index, (interaction, passes, signs) in enumerate(shapes):
        for attempt in range(100):
            coefficients = [sign * rng.choice((1, 2)) if sign else 0 for sign in signs]
            config = {"coefficients": coefficients, "passes": passes,
                      "interaction": interaction,
                      "cross_coefficient": 0 if interaction == "none" else rng.choice(CROSS_COEFFICIENTS)}
            calibration = [{"input": query, "expected": _measure(config, query["values"])}
                           for query in _calibration()]
            if compatible_configs(calibration) == [config]:
                break
        else:
            raise ValueError("could not select an identifying fresh binding")
        task = deepcopy(templates[index // 3]["tasks"][index % 3])
        task.update({"id": f"binding-{index}", "description": DESCRIPTION + (INTERFACE_CLARIFICATION if interface_clarification else ""),
                     "initial_source": _initial_source(index % 2 == 1), "private": deepcopy(config),
                     "calibration": calibration})
        task["private"]["reference_source"] = _reference(config)
        # For an ordinary single accumulation with no interaction, the true
        # output already suffices for future output. Do not invent a witness.
        task["private"]["continuation_witness"] = (None if interaction == "none" and passes == 1
                                                   else _continuation_witness(config))
        task["private"]["calibration_identification"] = {"family_size": 4464, "consistent_configurations": 1}
        for name in ("development", "screen", "confirmation"):
            task[name] = [{"input": deepcopy(row["input"]), "expected": oracle(task, row["input"])}
                          for row in task[name]]
        tasks.append(task)
    return {"schema": "zenith-state-discovery-transfer-tasks-v1", "seed": seed, "panel_size": panel_size,
            "source_module": "research/state_discovery_tasks.py", "interface_clarification": interface_clarification,
            "provenance": deepcopy(templates[0]["provenance"]),
            "limitations": ["Six new configurations in the same supplied finite family; no new-domain transfer claim.",
                            "None, adjacent and prefix interactions are balanced; signed polynomial coefficients and pass counts vary.",
                            "Calibration uniquely identifies each selected configuration; the exact recurrence and competent reference remain host-only.",
                            "Whole-sequence prediction establishes rule induction, not discovery of a bounded sufficient streaming state.",
                            "The syntax clarification belongs to a new stage; comparisons with old stages also contain an executor/interface engineering change.",
                            "Fixed-source cases, model-setting comparisons and further-case reuse are not independent task replications.",
                            "No acquired investigation policy or learning-policy transfer is implemented by this fixture."],
            "tasks": tasks}
