"""Offline checks for the kept-experience study harness (no model or network)."""

from research.kept_experience import harness as H
from research.kept_experience import population as P

PROBLEM = {
    "task_id": "Toy/0",
    "entry_point": "close",
    "prompt": 'def close(xs: list, t: float) -> bool:\n    """True if two values are closer than t."""\n',
    "canonical_solution": ("    s = sorted(xs)\n    for i in range(len(s) - 1):\n"
                           "        if s[i + 1] - s[i] < t:\n            return True\n    return False\n"),
    "contract": '\n    assert t > 0, "invalid inputs" # $_CONTRACT_$\n',
    "atol": 0,
}


def test_parse_inputs_takes_last_block_and_wraps_single_arguments():
    text = "notes\n```python\nINPUTS = [1]\n```\nfinal\n```python\nINPUTS = [([1.0, 2.0], 0.5), (3,)]\n```"
    assert H.parse_inputs(text, 5) == [[[1.0, 2.0], 0.5], [3]]
    assert H.parse_inputs("no block", 5) == []
    assert H.parse_inputs("```python\nINPUTS = [(1,), (2,), (3,)]\n```", 2) == [[1], [2]]


def test_same_uses_float_tolerance_and_types():
    assert P.same(1.0, 1.0 + 1e-9, 0)
    assert not P.same(1, True, 0)
    assert not P.same([1, 2], (1, 2), 0)
    assert P.same({"a": [1.0]}, {"a": [1.0]}, 0)


def test_mutants_are_distinct_and_one_changes_the_boundary():
    muts = P.mutants(PROBLEM)
    assert len({m["sha256"] for m in muts}) == len(muts)
    ref = P._load(P.reference_source(PROBLEM), "close")
    boundary = [m for m in muts
                if P.outcomes_differ(P.call(ref, [[1.0, 1.5], 0.5]),
                                     P.call(P._load(m["source"], "close"), [[1.0, 1.5], 0.5]), 0)]
    assert boundary, "a <= mutant should be exposed by an exact-threshold input"


def test_validator_rejects_contract_violations():
    validator = P._load(P.validator_source(PROBLEM), "close")
    assert P.valid_input(validator, [[1.0], 0.5])
    assert not P.valid_input(validator, [[1.0], -1.0])


def _bomb(n):
    chunks = []
    while True:
        chunks.append(bytearray(50_000_000))


def _fine(n):
    return n * 2


def test_sandbox_turns_memory_bombs_into_error_rows(monkeypatch):
    from research.kept_experience import sandbox as S
    monkeypatch.setattr(S, "SOFT_RSS", 300_000_000)
    monkeypatch.setattr(S, "HARD_RSS", 600_000_000)
    rows = S.run_jobs(_bomb, [1], processes=1, wall_s=60)
    assert rows[0]["ok"] is False
    assert S.run_jobs(_fine, [1, 2], processes=2) == [{"ok": True, "value": 2}, {"ok": True, "value": 4}]
