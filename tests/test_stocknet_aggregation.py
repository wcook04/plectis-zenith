from datetime import datetime, timezone
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from benchmarks.stocknet import canonical_digest, digest
from benchmarks.stocknet_aggregation import parse_tweets, select_tweets, validate_response, verify_study, run


def request(arm='price_text'):
    return {'case_ids': ['A:2015-08-03:h1'], 'allowed_tweet_ids': ['1'] if arm == 'price_text' else [], 'arm': arm}


def response(citations=None, number=0.01):
    return json.dumps({'forecasts': [{'case_id': 'A:2015-08-03:h1', 'predicted_return': number,
                                     'evidence_tweet_ids': citations or []}]})


def test_actual_utc_cutoff_excludes_late_posts_and_receipts_keep_full_hash():
    content = '\n'.join(json.dumps({'id_str': str(index), 'created_at': stamp, 'text': 'x' * 300})
                       for index, stamp in [(1, 'Mon Aug 03 19:59:59 +0000 2015'),
                                            (2, 'Mon Aug 03 20:00:01 +0000 2015'),
                                            (3, 'Fri Jul 31 19:00:00 +0000 2015')]).encode()
    tweets, rejected = parse_tweets(content, 'tweet/raw/AAPL/2015-08-03')
    selected, receipt = select_tweets(tweets, datetime(2015, 8, 3, 20, tzinfo=timezone.utc))
    assert not rejected and [row['tweet_id'] for row in selected] == ['1']
    assert selected[0]['text_sha256'] == digest(('x' * 300).encode())
    assert selected[0]['truncated_chars'] == 20 and len(selected[0]['text']) == 280
    assert receipt['retained_count'] == 1


def test_selection_deterministic_bounded_and_absence_explicit():
    tweets = [{'tweet_id': str(i), 'created_at_utc': '2015-08-03T19:00:00+00:00', 'text': str(i)} for i in range(8)]
    cutoff = datetime(2015, 8, 3, 20, tzinfo=timezone.utc)
    selected, receipt = select_tweets(tweets, cutoff)
    assert select_tweets(list(reversed(tweets)), cutoff)[0] == selected
    assert len(selected) == 4 and receipt['omitted_count'] == 4
    assert select_tweets([], cutoff)[1]['availability'] == 'unavailable'


def test_strict_output_schema_rejects_foreign_evidence_missing_and_nonfinite():
    assert validate_response(response(['1']), request())
    for raw in [response(['unknown']), response(['1'], float('nan')), response(['1'], True),
                response(['1']), '{"forecasts":[],"forecasts":[]}', '{}', '{"forecasts":[],"extra":1}']:
        with pytest.raises(ValueError):
            validate_response(raw, request('price_only'))


def frozen_fixture(tmp_path):
    study = tmp_path / 'study'; study.mkdir()
    truth = [{'case_id': f'A:2015-08-03:h{h}', 'issue_date': '2015-08-03', 'horizon_observed_rows': h,
              'issue_price': 100, 'target_price': 101, 'actual_return': 0.01, 'momentum_return': 0.02} for h in [1, 5, 20]]
    (study / 'truth-rows.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in truth))
    (study / 'predictor-rows.jsonl').write_text('{"observed_ohlcv":{"Close":100}}\n')
    requests = []
    for arm in ['price_only', 'price_text']:
        path = study / (arm + '.txt'); path.write_text('no truth supplied ' + arm)
        requests.append({'node_id': arm, 'arm': arm, 'issue_date': '2015-08-03', 'path': path.name,
                         'sha256': digest(path.read_bytes()), 'case_ids': [row['case_id'] for row in truth],
                         'allowed_tweet_ids': ['1'] if arm == 'price_text' else []})
    manifest = {'requests': requests, 'tweet_sources': [], 'limitations': ['test'],
                'artifact_hashes': {name: digest((study / name).read_bytes()) for name in ['truth-rows.jsonl', 'predictor-rows.jsonl']}}
    manifest['study_sha256'] = canonical_digest(manifest)
    (study / 'study-manifest.json').write_text(json.dumps(manifest))
    return study


def test_shared_valid_support_and_failure_coverage_no_retry(tmp_path):
    study = frozen_fixture(tmp_path); calls = []
    def ask(prompt, config):
        calls.append(config['meta']['node_id'])
        if 'price_text' in prompt: return '{}'
        return json.dumps({'forecasts': [{'case_id': f'A:2015-08-03:h{h}', 'predicted_return': 0,
                                        'evidence_tweet_ids': []} for h in [1, 5, 20]]})
    provider = SimpleNamespace(manager=SimpleNamespace(ask_ai=ask))
    result = run(study, tmp_path / 'results', provider)
    assert result['coverage']['price_only']['valid_cases'] == 3
    assert result['coverage']['price_text']['valid_cases'] == 0
    assert result['common_valid_cases'] == 0 and result['missing_or_rejected_calls'] == 1
    assert result['comparison_complete'] is False and result['automatic_selection_or_promotion'] is False
    assert all(row['forecast_count'] == 0 for row in result['evaluations'])
    run(study, tmp_path / 'results', provider)
    assert len(calls) == 2


def test_frozen_prompt_and_artifact_drift_rejected(tmp_path):
    study = frozen_fixture(tmp_path); verify_study(study)
    (study / 'price_only.txt').write_text('changed')
    with pytest.raises(ValueError, match='prompt drift'): verify_study(study)


def test_success_cites_text_and_scores_both_arms_same_cases(tmp_path):
    study = frozen_fixture(tmp_path)
    def ask(prompt, config):
        return json.dumps({'forecasts': [{'case_id': f'A:2015-08-03:h{h}', 'predicted_return': 0.01,
                                        'evidence_tweet_ids': ['1'] if 'price_text' in prompt else []} for h in [1, 5, 20]]})
    provider = SimpleNamespace(manager=SimpleNamespace(ask_ai=ask), model='fixed/model', options={'max_output_tokens': 1024})
    result = run(study, tmp_path / 'results', provider)
    assert result['common_valid_cases'] == 3 and result['text_cited_forecasts'] == 3
    assert result['comparison_complete'] is True
    assert len(result['evaluations']) == 12
    assert (tmp_path / 'results/frozen-execution.json').exists()
    provider.model = 'other/model'
    with pytest.raises(ValueError, match='parameters'): run(study, tmp_path / 'results', provider)


def test_public_projection_keeps_hashes_metrics_and_excludes_private_path(tmp_path):
    from benchmarks.stocknet_aggregation import public_summary
    study = frozen_fixture(tmp_path)
    manifest = json.loads((study / 'study-manifest.json').read_text())
    manifest.update(dataset_commit='0' * 40, source_manifest_sha256='a' * 64, price_sources=[],
                    issue_dates=['2015-08-03'], symbols=['A'], horizons_observed_rows=[1, 5, 20])
    for row in manifest['requests']: row['utf8_bytes'] = len((study / row['path']).read_bytes())
    manifest.pop('study_sha256'); manifest['study_sha256'] = canonical_digest(manifest)
    (study / 'study-manifest.json').write_text(json.dumps(manifest))
    def ask(prompt, config):
        return json.dumps({'forecasts': [{'case_id': f'A:2015-08-03:h{h}', 'predicted_return': 0.01,
                                        'evidence_tweet_ids': []} for h in [1, 5, 20]]})
    provider = SimpleNamespace(manager=SimpleNamespace(ask_ai=ask), model='fixed/model',
                               options={'max_output_tokens': 1024, 'budget_dir': '/PRIVATE/PATH'})
    result_dir = tmp_path / 'results'; run(study, result_dir, provider)
    destination = tmp_path / 'public.json'; summary = public_summary(study, result_dir, destination)
    assert summary['comparison_complete'] is True
    assert '/PRIVATE/PATH' not in destination.read_text()
    assert 'raw_response' not in destination.read_text()
    assert set(summary['implementation_hashes']) == {'benchmarks/stocknet_aggregation.py', 'benchmarks/stocknet.py',
        'benchmarks/stocknet_protocol.json', 'zenith/budgeted.py', 'zenith/providers.py', 'system/lib/openrouter_free_runtime.py'}


def test_resume_refuses_changed_transport_before_call(tmp_path, monkeypatch):
    study = frozen_fixture(tmp_path); calls = []
    def ask(prompt, config):
        calls.append(config['meta']['node_id'])
        return json.dumps({'forecasts': [{'case_id': f'A:2015-08-03:h{h}', 'predicted_return': 0,
                                        'evidence_tweet_ids': []} for h in [1, 5, 20]]})
    provider = SimpleNamespace(manager=SimpleNamespace(ask_ai=ask))
    result_dir = tmp_path / 'results'; run(study, result_dir, provider)
    original = Path.read_bytes
    def changed_bytes(path):
        return b'changed transport' if path.name == 'openrouter_free_runtime.py' else original(path)
    monkeypatch.setattr(Path, 'read_bytes', changed_bytes)
    with pytest.raises(ValueError, match='parameters'): run(study, result_dir, provider)
    assert len(calls) == 2
