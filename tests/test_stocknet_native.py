"""Dated local price admission and frozen native study; no real provider calls."""
import csv
from datetime import datetime
from pathlib import Path

import exchange_calendars as xcals
import pytest

from benchmarks import stocknet_native as native
from benchmarks.stocknet import FIELDS, digest, protocol
from research import cohort
from research.engine import read_json, write_json


def dataset(tmp_path):
    root = tmp_path / 'dataset'
    sessions = xcals.get_calendar('XNYS', start='2015-01-01', end='2016-01-01').sessions_in_range('2015-05-01', '2015-11-01')
    files = []
    for symbol in native.SYMBOLS:
        path = root / f'price/raw/{symbol}.csv'; path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('w') as stream:
            writer = csv.writer(stream); writer.writerow(FIELDS)
            for index, session in enumerate(sessions):
                price = 100 + index
                writer.writerow([session.date().isoformat(), price, price + 1, price - 1, price, price, 1000])
        files.append({'path': str(path.relative_to(root)), 'symbol': symbol, 'sha256': digest(path.read_bytes())})
    write_json(root / 'source-manifest.json', {'dataset_commit': protocol()['dataset_commit'], 'files': files})
    return root


def test_prepare_freezes_one_policy_change_and_native_temporal_support(tmp_path):
    data = dataset(tmp_path); study = tmp_path / 'study'
    native.prepare(data, study, 'fixed/model', provider_slug='fixture')
    spec = read_json(study / 'cohort/cohort.json')
    assert len(spec['issues']) == 25
    assert sum(row['split'] == 'development' for row in spec['issues']) == 20
    assert sum(row['split'] == 'holdout' for row in spec['issues']) == 5
    assert spec['max_calls_per_run'] == 2
    assert all(len(row['target_ids']) == 3 and row['horizon_id'] == 'next_us_close' for row in spec['issues'])
    baseline, candidate = spec['candidates']
    before, after = baseline['reasoning_policy_payload'], candidate['reasoning_policy_payload']
    assert before['nodes']['lab_decide'] == after['nodes']['lab_decide']
    assert set(after['nodes']['lab_director']) - set(before['nodes']['lab_director']) == {'skill_addon'}
    assert len(after['nodes']['lab_director']['skill_addon']) <= 512
    assert baseline['model'] == candidate['model'] == 'fixed/model'
    assert baseline['graph_variant_payload'] == candidate['graph_variant_payload']
    assert len(baseline['scope']) == 3 and len(baseline['reasoner_scope']) == 2
    for issue in spec['issues']:
        feed = read_json(study / 'cohort' / issue['feed_source'] / 'artifacts/global_stock_feed.json')
        assert feed['metadata']['available_feed_lanes'] == ['STOCK']
        assert 'truth' not in feed['data'] and 'target_price' not in str(feed['data'])
        for asset in feed['data']['assets']:
            assert len(asset['past_20_rows']) == 20
            assert all(row['Date'] <= issue['time_anchor'][:10] for row in asset['past_20_rows'])
        assert all(datetime.fromisoformat(row[2]) == datetime.fromisoformat(issue['time_anchor']) for row in feed['data']['rows'])
    result = native.plan(study)
    assert result['maximum_calls'] == 100 and result['paid_calls_here'] is False
    assert result['maximum_output_tokens'] == 409600
    assert not (study / 'native-attempts').exists()
    references = read_json(study / 'reference-baselines.json')
    assert references['model_arms'] is False
    issue = spec['issues'][0]
    truth = read_json(study / 'truth.json')['data']['rows'][0]['price']
    reference = references['per_issue']['no_change'][issue['issue_id']]
    forecast = reference['per_target'][0]
    assert forecast['target_price_relative_error'] == abs(forecast['target_price'] - truth) / truth
    assert reference['issue_score'] == sum(row['target_price_relative_error'] for row in reference['per_target']) / 3
    assert references['scores']['development']['no_change'] == sum(
        row['issue_score'] for row in references['per_issue']['no_change'].values() if row['split'] == 'development') / 20
    pending = cohort.evaluate(study / 'cohort')
    assert pending['state'] == 'pending' and pending['scores'] is None


def test_fresh_preparation_and_source_hashes_are_enforced(tmp_path):
    data = dataset(tmp_path); output = tmp_path / 'study'
    native.prepare(data, output, 'fixed/model', provider_slug='fixture', development_count=1, holdout_count=0)
    with pytest.raises(ValueError, match='overwrite'): native.prepare(data, output, 'fixed/model', provider_slug='fixture')
    (data / 'price/raw/AAPL.csv').write_text('changed')
    with pytest.raises(ValueError, match='source hash'): native.prepare(data, tmp_path / 'changed-study', 'fixed/model', provider_slug='fixture')


def test_pilot_is_excluded_and_freezes_before_native_invocation(tmp_path, monkeypatch):
    data = dataset(tmp_path); output = tmp_path / 'pilot'; observed = []
    def start(root, **kwargs):
        observed.append(kwargs)
        assert read_json(output / 'pilot.json')['study_membership'] == 'excluded from dev/holdout'
        assert read_json(output / 'recorded/artifacts/global_stock_feed.json')['metadata']['available_feed_lanes'] == ['STOCK']
        return {'status': 'not_executed_test_provider'}
    monkeypatch.setattr(native.runtime, 'start', start)
    native.pilot(data, output, 'fixed/model', budget_dir=tmp_path / 'shared')
    assert len(observed) == 1 and observed[0]['target'] == 'lab_director'
    assert observed[0]['max_cost_usd'] == '5' and observed[0]['max_calls'] == 128
    assert read_json(output / 'pilot.json')['issue_date'].startswith('2015-07')
    assert read_json(output / 'pilot.json')['accuracy_evaluation'] is False
    with pytest.raises(ValueError, match='no retry'): native.pilot(data, output, 'fixed/model', budget_dir=tmp_path / 'shared')


def test_holdout_cannot_execute_before_complete_development(tmp_path, monkeypatch):
    data = dataset(tmp_path); study = tmp_path / 'study'
    native.prepare(data, study, 'fixed/model', provider_slug='fixture')
    monkeypatch.setattr(native.runtime, 'start', lambda *a, **k: pytest.fail('must not execute provider'))
    with pytest.raises(ValueError, match='twenty-issue'):
        native.run(study, phase='holdout', budget_dir=tmp_path / 'budget', pause_seconds=0)


def test_endpoint_pin_survives_freeze_and_native_dispatch(tmp_path, monkeypatch):
    data = dataset(tmp_path); study = tmp_path / 'study'
    native.prepare(data, study, 'fixed/model', provider_slug='deepinfra/fp8', development_count=1, holdout_count=0)
    spec = read_json(study / 'cohort/cohort.json')
    assert all(row['provider_slug'] == 'deepinfra/fp8' for row in spec['candidates'])
    actions = cohort.next_actions(study / 'cohort')['actions']
    assert all(row['native_argv'][-2:] == ['--provider-slug', 'deepinfra/fp8'] for row in actions)
    observed = []
    def failure(*args, **kwargs):
        observed.append(kwargs)
        raise RuntimeError('synthetic no-inference boundary')
    monkeypatch.setattr(native.runtime, 'start', failure)
    native.run(study, phase='development', budget_dir=tmp_path / 'shared', pause_seconds=0)
    assert len(observed) == 1 and observed[0]['provider_slug'] == 'deepinfra/fp8'


def test_run_failure_imported_once_and_stops_without_retry(tmp_path, monkeypatch):
    data = dataset(tmp_path); study = tmp_path / 'study'
    native.prepare(data, study, 'fixed/model', provider_slug='fixture', development_count=2, holdout_count=0)
    observed = []
    def failure(*args, **kwargs):
        observed.append(kwargs)
        raise RuntimeError('synthetic provider failure')
    monkeypatch.setattr(native.runtime, 'start', failure)
    result = native.run(study, phase='development', budget_dir=tmp_path / 'budget', pause_seconds=0)
    assert len(observed) == 1
    assert len(result['imports']) == 1 and result['imports'][0]['state'] == 'error'
    assert 'diagnostics' in result['imports'][0]
    assert result['comparison']['state'] == 'pending' and result['comparison']['scores'] is None
    assert read_json(study / 'cohort/cohort-state.json')['attempts'] == 1
    with pytest.raises(ValueError, match='no automatic retry'):
        native.run(study, phase='development', budget_dir=tmp_path / 'budget', pause_seconds=0)
    assert len(observed) == 1
