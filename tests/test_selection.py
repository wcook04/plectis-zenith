"""Selection quality requires the original denominator and a fixed fallback."""
from copy import deepcopy
import itertools

import pytest

from feedback.selection import score_panel, score_selection


def case(**overrides):
    return {'universe': ['a', 'b', 'c'], 'selected': ['a'],
            'forecasts': {'a': .1, 'b': -.2, 'c': .1}, 'fallback': dict.fromkeys('abc', 0.),
            'truth': {'a': .1, 'b': -.2, 'c': -.1}, 'budget': 1, **overrides}


def test_perfect_selected_forecast_still_counts_unselected_names():
    score = score_selection(**case())
    assert score['metrics']['selected_loss'] == 0
    assert score['metrics']['universe_loss'] == pytest.approx(.05 / 3)
    assert score['metrics']['gain_over_fallback'] == pytest.approx(.01 / 3)
    assert score['shadow_selection']['hindsight_best_up_to_budget_gain'] == pytest.approx(.04 / 3)
    assert score['shadow_selection']['hindsight_regret'] == pytest.approx(.03 / 3)


def test_uniform_selection_expectation_matches_exhaustive_subsets():
    scores = [score_selection(**case(selected=list(s), budget=2))
              for s in itertools.combinations('abc', 2)]
    mean = sum(r['metrics']['gain_over_fallback'] for r in scores) / len(scores)
    assert all(r['shadow_selection']['uniform_same_count_expected_gain'] == pytest.approx(mean) for r in scores)


def test_missing_unselected_truth_makes_all_scores_pending():
    row = score_selection(**case(truth={'a': .1, 'b': -.2}))
    assert row['state'] == 'pending'
    assert row['missing_truth'] == ['c']
    assert row['metrics'] is None and row['shadow_selection'] is None


def test_no_shadow_does_not_invent_selection_regret():
    row = score_selection(**case(forecasts={'a': .1}))
    assert row['metrics']['universe_loss'] == pytest.approx(.05 / 3)
    assert row['shadow_selection'] is None


def test_abstain_is_fallback_not_zero_error():
    row = score_selection(**case(selected=[], forecasts={}))
    assert row['metrics']['selected_loss'] is None
    assert row['metrics']['gain_over_fallback'] == 0
    assert row['metrics']['universe_loss'] > 0


def test_absolute_loss_supports_medians_without_changing_existing_cohorts():
    row = score_selection(**case(loss='absolute'))
    assert row['metrics']['universe_loss'] == pytest.approx(.3 / 3)


@pytest.mark.parametrize('change', [
    {'universe': ['a', 'a']}, {'selected': ['a', 'a']}, {'selected': ['d']},
    {'budget': True}, {'budget': 4}, {'selected': ['a', 'b']},
    {'forecasts': {}}, {'forecasts': {'a': float('nan')}},
    {'fallback': {'a': 0}}, {'truth': {'a': True}}, {'loss': 'profit'},
])
def test_invalid_inputs_cannot_create_favorable_scores(change):
    with pytest.raises(ValueError):
        score_selection(**case(**change))


def test_panel_weights_dates_equally_and_preserves_missing_dates():
    cases = [{'issue_id': 'day1', **case()}, {'issue_id': 'day2', **case(
        universe=['a'], selected=[], forecasts={}, fallback={'a': 0}, truth={'a': 1}, budget=0)}]
    original = deepcopy(cases)
    score = score_panel(cases)
    assert score['metrics']['universe_loss'] == pytest.approx((.05 / 3 + 1) / 2)
    assert cases == original
    cases[1]['truth'] = {}
    assert score_panel(cases)['metrics'] is None
    cases[1]['issue_id'] = 'day1'
    with pytest.raises(ValueError, match='distinct'):
        score_panel(cases)


@pytest.mark.parametrize('value', [1e200, 10**400])
def test_finite_inputs_cannot_overflow_into_scored_nonfinite_losses(value):
    with pytest.raises(ValueError, match='finite|overflow'):
        score_selection(universe=['a'], selected=['a'], forecasts={'a': value},
                        fallback={'a': 0}, truth={'a': 0}, budget=1)


def test_finite_individual_losses_cannot_overflow_the_aggregate():
    with pytest.raises(ValueError, match='overflow'):
        score_selection(universe=['a', 'b'], selected=['a', 'b'],
                        forecasts={'a': 1e154, 'b': 1e154},
                        fallback={'a': 0, 'b': 0}, truth={'a': 0, 'b': 0}, budget=2)
