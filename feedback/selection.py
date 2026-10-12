"""Descriptive scores for a frozen universe, selection and fallback forecast.

Callers own source/time binding. This does not admit a native cohort, infer
predictability, or turn forecast error into trading profit.
"""
from __future__ import annotations

import math


def _ids(values, name):
    if (not isinstance(values, list) or any(not isinstance(v, str) or not v for v in values)
            or len(set(values)) != len(values)):
        raise ValueError(f'{name} must contain distinct nonempty string IDs')
    return set(values)


def _numbers(values, name):
    if not isinstance(values, dict):
        raise ValueError(f'{name} requires finite numbers, not missing values or booleans')
    for value in values.values():
        _finite(value, name)


def _finite(value, name):
    try:
        valid = type(value) in (int, float) and math.isfinite(value)
    except OverflowError:
        valid = False
    if not valid:
        raise ValueError(f'{name} requires finite representable numbers')
    return value


def _sum(values):
    try:
        return _finite(math.fsum(values), 'derived aggregate')
    except OverflowError as exc:
        raise ValueError('derived aggregate overflow') from exc


def score_selection(*, universe, selected, forecasts, fallback, truth, budget, loss='squared'):
    """Score unselected names at the predeclared fallback, never drop them.

    Complete shadow forecasts enable descriptive selection comparisons. The
    hindsight bound uses realized labels and is never an admissible selector.
    Missing truth anywhere keeps all losses pending, including selected loss.
    """
    members = _ids(universe, 'universe')
    chosen = _ids(selected, 'selected')
    if not members or type(budget) is not int or not 0 <= budget <= len(members):
        raise ValueError('nonempty universe and integer budget within its size required')
    if not chosen <= members or len(chosen) > budget:
        raise ValueError('selection exceeds frozen universe or budget')
    if loss not in ('squared', 'absolute'):
        raise ValueError('loss must be squared or absolute')
    _numbers(forecasts, 'forecasts')
    _numbers(fallback, 'fallback')
    if not chosen <= set(forecasts) <= members or set(fallback) != members:
        raise ValueError('selected forecasts and complete universe fallback required')
    if not isinstance(truth, dict) or not set(truth) <= members:
        raise ValueError('truth has unknown IDs')
    _numbers({k: v for k, v in truth.items() if v is not None}, 'truth')
    missing = sorted(k for k in members if truth.get(k) is None)
    result = {'schema': 'zenith_selection_score_v1', 'loss': loss,
              'universe_count': len(members), 'selected_count': len(chosen),
              'selection_coverage': len(chosen) / len(members), 'budget': budget,
              'truth_coverage': (len(members) - len(missing)) / len(members),
              'missing_truth': missing, 'state': 'pending' if missing else 'scored',
              'metrics': None, 'shadow_selection': None,
              'boundary': 'Descriptive forecast loss; no causal, predictability or trading claim.'}
    if missing:
        return result

    def error(prediction, actual):
        delta = _finite(abs(prediction - actual), 'derived error')
        return _finite(delta * delta if loss == 'squared' else delta, 'derived loss')

    ids = sorted(members)
    reference = {k: error(fallback[k], truth[k]) for k in ids}
    losses = {k: error(forecasts[k], truth[k]) if k in chosen else reference[k] for k in ids}
    baseline = _sum(reference.values()) / len(ids)
    total = _sum(losses.values()) / len(ids)
    selected_loss = _sum(losses[k] for k in sorted(chosen)) / len(chosen) if chosen else None
    result['metrics'] = {'universe_loss': total, 'fallback_loss': baseline,
                         'gain_over_fallback': baseline - total, 'selected_loss': selected_loss}
    if set(forecasts) == members:
        gains = {k: reference[k] - error(forecasts[k], truth[k]) for k in ids}
        # Uniform selection of the same number of names has this exact expectation.
        random_gain = len(chosen) / len(ids) * _sum(gains.values()) / len(ids)
        ordered = sorted(gains.values(), reverse=True)
        hindsight = _sum(max(0., v) for v in ordered[:budget]) / len(ids)
        result['shadow_selection'] = {
            'uniform_same_count_expected_gain': random_gain,
            'selection_gain_over_uniform': baseline - total - random_gain,
            'hindsight_best_up_to_budget_gain': hindsight,
            'hindsight_regret': hindsight - (baseline - total),
            'label': 'Realized hindsight bound, not foreknowable opportunity or causal blame',
        }
        _numbers({k: v for k, v in result['shadow_selection'].items() if k != 'label'}, 'derived selection')
    return result


def score_panel(cases):
    """Equal issue weights, full support; no deletion of a difficult date."""
    if not isinstance(cases, list) or not cases:
        raise ValueError('nonempty issue list required')
    _ids([case.get('issue_id') for case in cases], 'issue IDs')
    rows = [{'issue_id': case['issue_id'], **score_selection(**{k: v for k, v in case.items()
                                                              if k != 'issue_id'})} for case in cases]
    if len({row['loss'] for row in rows}) != 1:
        raise ValueError('panel loss must be fixed across issues')
    complete = all(row['state'] == 'scored' for row in rows)
    return {'schema': 'zenith_selection_panel_v1', 'state': 'scored' if complete else 'pending',
            'issue_count': len(rows), 'loss': rows[0]['loss'], 'issues': rows,
            'metrics': {key: _sum(row['metrics'][key] for row in rows) / len(rows)
                        for key in ('universe_loss', 'fallback_loss', 'gain_over_fallback')}
            if complete else None}
