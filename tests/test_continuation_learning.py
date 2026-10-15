"""Regression and boundary checks for the maintained witness-basis learner."""

from collections import deque
from fractions import Fraction

import pytest

from research.continuation_learning import Teacher, _inverse, learn


def unary_deque(word):
    return sum(deque(word, maxlen=4))


def test_counterexample_keeps_the_history_as_well_as_the_question():
    teacher = Teacher(unary_deque, (1,), "deque-maxlen-4")
    fit = learn(teacher, [(1,) * n for n in range(9)])

    # The archived basis-rebuilding learner aborted after six source calls on
    # this exact schedule. A retained 3/11 witness makes the new fit possible.
    assert teacher.meter.source_calls == 10
    assert fit.model.dimension == 5
    assert fit.refinements[0].history == (1, 1, 1)
    assert fit.refinements[0].continuation == (1, 1)
    assert fit.refinements[0].residual == Fraction(-1)
    assert fit.refinements[0].history in fit.model.access
    assert fit.refinements[0].continuation in fit.model.tests
    assert all(fit.model.predict((1,) * n) == min(n, 4) for n in range(33))

    witness_matrix = tuple(teacher.row(p, fit.model.tests) for p in fit.model.access)
    assert len(witness_matrix) == fit.model.dimension
    assert len(_inverse(witness_matrix)) == fit.model.dimension

    # Five linear coordinates are not an information lower bound: ordinary
    # nonlinear code has a one-integer update for the same source.
    count = 0
    for _ in range(32):
        count = min(count + 1, 4)
        assert count == unary_deque((1,) * (_ + 1))


def test_delayed_nonzero_series_bootstraps_from_a_supplied_challenge():
    source = lambda word: int(word == (1, 1, 1))
    teacher = Teacher(source, (1,), "length-three-impulse")
    fit = learn(teacher, [(1,) * n for n in range(7)])
    assert fit.model.dimension == 4
    assert all(fit.model.predict((1,) * n) == source((1,) * n) for n in range(20))


def test_generic_questions_are_a_competent_no_experience_control():
    from scripts.demo_continuation_learning import ALPHABET, native_source, panels

    development, longer, _ = panels()
    source = native_source("deque-4")
    cold = Teacher(source, ALPHABET, "deque-4")
    generic = Teacher(source, ALPHABET, "deque-4")
    cold_fit = learn(cold, development)
    generic_fit = learn(generic, development,
                        bank=tuple((symbol,) for symbol in ALPHABET), cost_gate=True)

    assert cold.meter.source_calls == 873
    assert generic.meter.source_calls == 857
    assert all(cold_fit.model.predict(word) == source(word) for word in longer)
    assert all(generic_fit.model.predict(word) == source(word) for word in longer)


def test_finite_fit_can_still_miss_native_behavior():
    from scripts.demo_continuation_learning import ALPHABET, native_source, panels

    source = native_source("utf8")
    development, _, _ = panels()
    teacher = Teacher(source, ALPHABET, "utf8")
    fit = learn(teacher, development)
    assert fit.status == "passed_finite_development_challenges"
    assert teacher.meter.source_calls == 933
    assert fit.model.predict((6, -2, -5)) == 0
    assert source((6, -2, -5)) == 2


def test_binding_validation_and_cache_are_local_to_one_teacher():
    first = Teacher(lambda word: sum(word), (1,), "first")
    second = Teacher(lambda word: sum(word) + 7, (1,), "second")
    assert first.ask((1,)) == first.ask((1,)) == 1
    assert first.meter.source_calls == first.meter.cache_hits == 1
    assert second.ask((1,)) == 8
    assert second.meter.source_calls == 1
    with pytest.raises(ValueError, match="bank outside"):
        learn(first, [(1,)], bank=[(2,)])
    with pytest.raises(ValueError, match="challenge outside"):
        learn(first, [(True,)])
    assert first.meter.source_calls == 1


def test_model_rejects_out_of_scope_symbols_and_length():
    teacher = Teacher(unary_deque, (1,), "deque-maxlen-4")
    fit = learn(teacher, [(1,) * n for n in range(9)])
    with pytest.raises(ValueError, match="binding"):
        fit.model.predict((1,) * 33)
    with pytest.raises(ValueError, match="binding"):
        fit.model.predict((2,))
