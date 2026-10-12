"""No heldout fitting, hindsight retrieval or numerical-only memory shortcut."""
from copy import deepcopy

import pytest

from research import ashare_text as text


def packet(date, content, state=0.):
    return {'issue_date': date, 'issue_at': date + 'T07:00:00+00:00', 'assets': [{
        'asset_id': 'asset_1', 'features': {'return_5': state, 'realized_vol_20': .01},
        'context_evidence': [
            {'ref_id': 'asset_1:identity', 'content': 'Fixed universe issuer code: 600519'},
            {'ref_id': 'asset_1:news_1', 'content': content, 'kind': 'news',
             'available_at': date + 'T06:00:00+00:00', 'availability_basis': 'observed_timestamp'}]}]}


def rows(dates):
    return [{'sample_id': d + ':600519', 'symbol': '600519', 'phase': 'training',
             'issue_date': d, 'issue_at': d + 'T07:00:00+00:00',
             'outcome_available_at': d + 'T23:00:00+00:00', 'actual_return': i * .01} for i, d in enumerate(dates)]


def test_text_control_fits_only_training_vocabulary_and_rejects_unmatured_fit():
    dates = ['2023-01-01', '2023-01-10', '2023-01-20']
    packets = {d: packet(d, '利润增长30%') for d in dates}
    fit = text.fit_control(rows(dates[:2]), packets, use_text=True)
    vocab = deepcopy(fit['encoder'].vocabulary_)
    packets[dates[2]] = packet(dates[2], '全新测试秘密XYZ')
    query = rows(dates[2:])
    assert text.predict_control(fit, query, packets)
    assert fit['encoder'].vocabulary_ == vocab
    before = text.predict_control(fit, query, packets)
    features = packets[dates[2]]['assets'][0]['features']
    packets[dates[2]]['assets'][0]['features'] = dict(reversed(list(features.items())))
    assert text.predict_control(fit, query, packets) == before
    assert not any('XYZ' in k for k in vocab)
    with pytest.raises(ValueError, match='mature'):
        text.predict_control(fit, rows(dates[:1]), packets)
    with pytest.raises(ValueError, match='training'):
        text.fit_control([{**query[0], 'phase': 'test'}], packets, use_text=True)


def test_memory_uses_forward_financial_text_not_outcomes_or_reflection_words():
    query = packet('2024-01-01', '上半年净利润 业绩预告 下调盈利增长')
    contents = ['收购子公司 董事会通过合并', '上半年净利润 业绩预告 下调盈利增长']
    cases = [{'case_id': str(i), 'packet': packet('2023-01-01', c), 'outcomes': [{'actual_return': i}],
              'update_available_at': '2023-02-01T00:00:00+00:00'} for i, c in enumerate(contents)]
    reviews = [{'classification': 'unresolved', 'lesson': '上半年净利润' * 5}, {'classification': 'unresolved'}]
    first = text.retrieve(query, cases, reviews)
    assert first[0]['case_id'] == '1'
    cases[0]['outcomes'][0]['actual_return'] = 999
    reviews[0]['lesson'] = '上半年净利润' * 100
    assert text.retrieve(query, cases, reviews)[0]['case_id'] == '1'
    future = {**cases[1], 'case_id': 'future', 'update_available_at': '2025-01-01T00:00:00+00:00'}
    assert 'future' not in [r['case_id'] for r in text.retrieve(query, cases + [future], reviews + [{}])]


def test_panel_common_text_is_counted_once_and_identity_is_not_retrieval_text():
    p = packet('2023-01-01', 'common story')
    p['assets'] *= 10
    assert text.panel_text(p) == 'common story'


def test_signal_identity_separates_alignment_from_overshoot_date_equally():
    r = rows(['2023-01-01', '2023-01-10'])
    r[0]['actual_return'], r[1]['actual_return'] = .01, .02
    p = {x['sample_id']: .06 for x in r}
    d = text.signal_diagnosis(r, p)
    assert d['forecast_energy'] == pytest.approx(.0036)
    assert d['outcome_alignment'] == pytest.approx(.0009)
    assert d['excess_mse'] == pytest.approx(.0018)
    assert d['retrospective_unconstrained_scale'] == pytest.approx(.25)
    duplicated = r + [{**r[0], 'sample_id': 'duplicate'}]
    assert text.signal_diagnosis(duplicated, {**p, 'duplicate': .06})['excess_mse'] == pytest.approx(.0018)


def test_chronological_scale_cannot_use_query_or_unmatured_outcomes():
    r = rows(['2023-01-01', '2023-01-10', '2023-01-20', '2023-01-30'])
    for row in r:
        row['actual_return'] = .01
    p = {x['sample_id']: .04 for x in r}
    r[1]['outcome_available_at'] = '2023-02-01T00:00:00Z'
    first, receipt = text.chronological_scale(r, p, min_dates=1, prior_dates=0)
    assert receipt['fits'][2]['fit_issue_dates'] == ['2023-01-01']
    assert first[r[2]['sample_id']] == pytest.approx(.01)
    r[2]['actual_return'] = -.5
    second, _ = text.chronological_scale(r, p, min_dates=1, prior_dates=0)
    assert second[r[2]['sample_id']] == first[r[2]['sample_id']]
    assert second[r[3]['sample_id']] == 0.
    with pytest.raises(ValueError, match='training'):
        text.chronological_scale([{**r[0], 'phase': 'test'}], p)
