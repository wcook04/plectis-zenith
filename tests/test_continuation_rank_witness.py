"""Check rank witnesses without changing the frozen learner test dependency."""

from research.continuation_learning import Teacher, _inverse, learn
from scripts.demo_continuation_learning import native_source


def test_counterexample_rank_witnesses_use_only_acquired_measurements():
    teacher = Teacher(native_source("deque-4"), (1,), "deque-maxlen-4")
    fit = learn(teacher, [(1,) * n for n in range(9)])

    assert teacher.meter.source_calls == 10
    assert fit.model.dimension == 5
    assert len(fit.refinements) == 3

    # Worrell's weighted-automata notes, Proposition 1 (pp. 2-3), require
    # retaining both the new access history and its distinguishing column.
    # Replay every rank witness from measurements already paid for by fitting;
    # verification must neither query the teacher nor change its work counters.
    measured_cache = dict(teacher.cache)
    measured_work = vars(teacher.meter).copy()
    initial_dimension = fit.model.dimension - len(fit.refinements)
    for width, refinement in enumerate(fit.refinements, start=initial_dimension):
        access = fit.model.access[:width]
        tests = fit.model.tests[:width]
        assert refinement.history not in access
        assert refinement.continuation not in tests
        assert fit.model.access[width] == refinement.history
        assert fit.model.tests[width] == refinement.continuation

        matrix = tuple(tuple(measured_cache[p + q] for q in tests) for p in access)
        inverse = _inverse(matrix)
        row = tuple(measured_cache[refinement.history + q] for q in tests)
        column = tuple(measured_cache[p + refinement.continuation] for p in access)
        coefficients = tuple(sum(row[i] * inverse[i][j] for i in range(width))
                             for j in range(width))
        residual = measured_cache[refinement.history + refinement.continuation] - sum(
            coefficient * value for coefficient, value in zip(coefficients, column)
        )
        assert residual == refinement.residual != 0
        extended = tuple(tuple(measured_cache[p + q] for q in fit.model.tests[:width + 1])
                         for p in fit.model.access[:width + 1])
        assert len(_inverse(extended)) == width + 1
    assert teacher.cache == measured_cache
    assert vars(teacher.meter) == measured_work
