"""Component boundaries: original universe, immutable forecasts and delayed truth."""
import json
from copy import deepcopy
from pathlib import Path

import pytest

from research import guidance_intervention as study


def data():
    return {'price_only': {'000858': {'q10': -.02, 'q50': 0, 'q90': .03}},
            'evidence_dictionary': [{'ref_id': '[1]', 'ledger_id': 'S_TEST', 'subject': '000858'}]}


def forecast():
    return {'targets': [{'target_id': '000858', 'q10': -.02, 'q50': 0, 'q90': .03,
                         'evidence_refs': ['[1]'], 'reasoning': 'Historical uncertainty [1].'}]}


@pytest.mark.parametrize('mutation', ['extra', 'missing', 'crossing', 'wrong_ref', 'numeric_id', 'duplicate'])
def test_forecasts_cannot_change_universe_or_evidence(mutation):
    obj = forecast()
    if mutation == 'extra':
        obj['targets'].append({**obj['targets'][0], 'target_id': 'EXTRA'})
    if mutation == 'missing':
        obj['targets'] = []
    if mutation == 'crossing':
        obj['targets'][0]['q10'] = .1
    if mutation == 'wrong_ref':
        obj['targets'][0]['evidence_refs'] = ['[2]']
    if mutation == 'numeric_id':
        obj['targets'][0]['target_id'] = 858
    if mutation == 'duplicate':
        obj['targets'] *= 2
    with pytest.raises(ValueError):
        study.envelope(json.dumps(obj), data())


def test_frozen_zero_median_is_valid_and_duplicate_json_is_not():
    assert study.envelope(json.dumps(forecast()), data())['forecast_quantiles']['targets'][0]['q50'] == 0
    with pytest.raises(ValueError):
        study.envelope('{"targets":[],"targets":[]}', data())


def test_format_only_does_not_claim_semantics():
    assert study.tuple_errors('{600519, invented figure, unsupported story}') == []
    assert study.tuple_errors('Here is my result:\n{600519, value, context}')


def test_sealed_output_cannot_be_overwritten(tmp_path):
    path = tmp_path/'response.json'
    study.seal(path, {'text': 'original'})
    with pytest.raises(ValueError, match='Immutable'):
        study.seal(path, {'text': 'revised'})


def test_run_seals_all_eleven_components_before_truth(tmp_path, monkeypatch):
    spec = {'pilot': study.DATES[0], 'development': study.DATES[1], 'later': study.DATES[2]}
    study.write_json(tmp_path/'spec.json', spec)
    for day in study.DATES:
        study.write_json(tmp_path/'inputs'/day/'material.json', data())
    monkeypatch.setattr(study, 'load', lambda root: spec)
    calls = []
    def fake_call(root, spec, day, arm, kind, data, miner=None):
        calls.append((day, arm, kind))
        study.seal(root/'calls'/f'{day}-{arm}-{kind}'/'accepted.json', {'value': 'fixture'})
        return 'fixture'
    monkeypatch.setattr(study, 'call', fake_call)
    def no_truth(*args, **kwargs):
        pytest.fail('Forecast execution opened an outcome')
    monkeypatch.setattr(study, 'snapshot', no_truth)
    with pytest.raises(ValueError, match='pilot'):
        study.execute(tmp_path, 'run')
    study.execute(tmp_path, 'pilot')
    result = study.execute(tmp_path, 'run')
    assert result['accepted_components'] == len(calls) == 11
    assert len(study.read(tmp_path/'forecasts-sealed.json')['files']) == 11
    with pytest.raises(ValueError, match='already sealed'):
        study.execute(tmp_path, 'run')


def test_evaluation_rejects_partial_or_changed_seal_before_truth(tmp_path, monkeypatch):
    spec = {'pilot': study.DATES[0], 'development': study.DATES[1], 'later': study.DATES[2]}
    study.write_json(tmp_path/'spec.json', spec)
    study.write_json(tmp_path/'forecasts-sealed.json', {'files': {}, 'spec_sha256': study.sha(tmp_path/'spec.json')})
    monkeypatch.setattr(study, 'load', lambda root: spec)
    with pytest.raises(ValueError, match='Complete original'):
        study.evaluate(tmp_path)


def test_scores_native_quantiles_on_exact_next_session_only(tmp_path, monkeypatch):
    spec = {'pilot': study.DATES[0], 'development': study.DATES[1], 'later': study.DATES[2], 'dataset': 'fixture'}
    study.write_json(tmp_path/'spec.json', spec)
    fixture = {**data(), 'issue': {'source_manifest_sha256': 'fixture'},
               'stock': {'price_basis': 'raw', 'rows': [['000858', 100.]]}}
    for day in study.DATES:
        study.write_json(tmp_path/'inputs'/day/'material.json', fixture)
    monkeypatch.setattr(study, 'load', lambda root: spec)
    def fake_call(root, spec, day, arm, kind, data, miner=None):
        result = 'fixture' if kind == 'news' else study.envelope(json.dumps(forecast()), data)
        study.seal(root/'calls'/f'{day}-{arm}-{kind}'/'accepted.json', {'value': result})
        return result
    monkeypatch.setattr(study, 'call', fake_call)
    study.execute(tmp_path, 'pilot')
    study.execute(tmp_path, 'run')
    opened = []
    def truth(dataset, target, output):
        opened.append(target)
        stamp = target+'T07:00:00+00:00'
        study.write_json(output/'artifacts/global_stock_feed.json', {
            'data': {'price_basis': 'raw', 'rows': [['000858', 101.]]},
            'metadata': {'diagnostics': {'price_observations': {'000858': {
                'session_date': target, 'currency': 'CNY', 'observation_at_utc': stamp}}}}})
        return {'source_manifest_sha256': 'fixture', 'observation_at_utc': stamp}
    monkeypatch.setattr(study, 'snapshot', truth)
    result = study.evaluate(tmp_path)
    assert opened == ['2023-08-04', '2023-08-31']
    assert len(result['results']) == 9
    assert result['results'][0]['mean']['median_absolute_error'] == pytest.approx(.01)
    assert result['results'][0]['mean']['mean_quantile_pinball_loss'] == pytest.approx(.01/3)
    with pytest.raises(ValueError, match='already evaluated'):
        study.evaluate(tmp_path)
