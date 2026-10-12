from decimal import Decimal

import pytest

from benchmarks.guidance_events import comparisons


def document(stamp, values):
    return {'id': stamp, 'symbol': 'ADBE', 'fiscal_period': 'FY2023',
            'sec_acceptance_at_utc': stamp + 'T20:00:00Z', 'annual_guidance': values}


def test_guidance_uses_latest_publication_per_metric_without_inventing_reaffirmation():
    first = document('2022-12-15', {'revenue': ['19.1','19.3'], 'eps': ['15.15','15.45']})
    second = document('2023-03-15', {'eps': ['15.30','15.60']})
    current = document('2023-06-15', {'revenue': ['19.25','19.35'], 'eps': ['15.65','15.75']})
    result = {r['metric']: r for r in comparisons(current, [first, second])}
    assert result['revenue']['prior_source'] == first['id']
    assert result['eps']['prior_source'] == second['id']
    assert Decimal(result['revenue']['midpoint_change']) == Decimal('.1')
    with pytest.raises(ValueError, match='fiscal period'):
        comparisons(current, [{**first, 'fiscal_period': 'FY2022'}])
    with pytest.raises(ValueError, match='precede'):
        comparisons(current, [current])


def test_mixed_guidance_preserves_unchanged_and_lowered_measures():
    prior = document('2023-01-01', {'revenue': ['10','12'], 'margin': ['30','30']})
    current = document('2023-04-01', {'revenue': ['10','12'], 'margin': ['28','28']})
    assert [r['direction'] for r in comparisons(current, [prior])] == ['unchanged', 'lowered']


def test_equal_midpoint_does_not_hide_a_revised_range():
    prior = document('2023-01-01', {'revenue': ['10','12']})
    current = document('2023-04-01', {'revenue': ['10.5','11.5']})
    result = comparisons(current, [prior])[0]
    assert result['direction'] == 'range_revised_same_midpoint'
    assert Decimal(result['range_width_change']) == -1
