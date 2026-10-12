"""Daily control transitions and rejection boundaries; all evidence is synthetic."""
from copy import deepcopy
import json
from pathlib import Path
import shutil

import pytest
from benchmarks import fnspid as fn
from zenith import daily, runtime


@pytest.fixture
def programme(tmp_path, monkeypatch):
    root = tmp_path/'checkout'
    shutil.copytree(runtime.DEFAULT_ROOT/'codex', root/'codex')
    daily.write_json(root/'master_config.json', {'paths': {'runs_dir': 'state/runs'}, 'execution': {'max_workers': 8}})
    source = tmp_path/'source'
    source.mkdir()
    (source/'aa-prices.csv').write_text('Date,Open,High,Low,Close,Adj Close,Volume\n2024-01-16,30,31,29,30,30,20\n2024-01-17,30,32,30,31,31,40\n2024-01-18,31,33,30,32,32,50\n')
    (source/'aa-news.csv').write_text('Date,Url,Text,Mark\n"January 16, 2024 — 03:00 pm EST",https://example.invalid/a,Synthetic source,1\n')
    files = {name: {'upstream': name, 'bytes': (source/name).stat().st_size, 'sha256': fn.sha(source/name)} for name in fn.FILES}
    monkeypatch.setattr(fn, 'FILES', files)
    manifest = {'schema': 'fnspid_raw_source_v1', 'repository': fn.REPOSITORY, 'revision': fn.REVISION, 'files': files, 'policy': fn.POLICY}
    fn.write_json(source/'source-manifest.json', {**manifest, 'manifest_sha256': fn.canonical_hash(manifest)})
    directory = tmp_path/'programme'
    daily.initialize(root, directory, source, '2024-01-16', '2024-01-17')
    return root, directory


def completed_fixture(programme, monkeypatch):
    """Stub mission completion to isolate the controller, not claim execution."""
    root, directory = programme
    manifest = daily.load(root, directory)
    seen = []
    def checked(root, manifest, index, mission, policy_path):
        seen.append((index, mission, daily.read(policy_path)))
        lab, oracle = daily.run_ids(manifest, index)
        daily.write_json(runtime.runs_root(root)/lab/'artifacts/lab_director.json', {'data': {'observation': 'synthetic trend only'}})
        for name, _ in daily.evolve.ORACLE_ARTIFACTS:
            daily.write_json(runtime.runs_root(root)/oracle/'artifacts'/f'{name}.json', {'data': {'diagnosis': 'cause unestablished'}})
        return {'status': 'completed'}
    monkeypatch.setattr(daily, 'checked_run', checked)
    return seen


def answer(packet):
    return {'packet_sha256': packet['packet_sha256'], 'decision': 'candidate',
            'diagnosis': 'Synthetic price trend does not establish mechanism.',
            'uncertainty': 'A single episode cannot justify causal confidence.',
            'test': 'Inspect later forecasts for explicit separation of observation and hypothesis.',
            'evidence': [{'source': 'lab_director', 'pointer': '/data/observation', 'value': 'synthetic trend only'}],
            'change': {'node_id': 'lab_director', 'skill_addon': 'Separate observed trend, proposed mechanism and target rule.'}}


def test_first_day_uses_native_full_lab_without_future_source(programme):
    root, directory = programme
    result = daily.advance(root, directory)
    assert (result['stage'], result['status'], result['completed_count'], result['scope_count']) == ('lab', 'awaiting_agent', 7, 28)
    assert [p['node_id'] for p in result['pending']] == ['lab_seed_state']
    spec = daily.read(runtime.runs_root(root)/result['run_id']/'zenith_run.json')
    assert spec['feed_source'].endswith('2024-01-16') and spec['truth_run'] is None
    assert runtime.stamp(spec['horizon']) > runtime.stamp(spec['time_anchor'])
    assert daily.advance(root, directory)['run_id'] == result['run_id']


def test_review_freezes_successor_and_next_day_consumes_it(programme, monkeypatch):
    root, directory = programme
    seen = completed_fixture(programme, monkeypatch)
    pending = daily.advance(root, directory)
    packet = daily.read(pending['packet_path'])
    response = directory/'answer.json'
    daily.write_json(response, answer(packet))
    reviewed = daily.advance(root, directory, response, 'synthetic reviewer')
    assert reviewed['status'] == 'reviewed_candidate'
    assert not (root/'codex/substrate/dossiers/learning_ledger.jsonl').exists()
    pending = daily.advance(root, directory)
    assert pending['stage'] == 'evolve' and pending['episode'] == 1
    next_lab = [policy for index, mission, policy in seen if index == 1 and mission == 'lab'][0]
    assert next_lab['nodes']['lab_director']['skill_addon'] == answer(packet)['change']['skill_addon']
    assert next_lab != daily.read(directory/'policies/baseline.json')
    newer = daily.read(pending['packet_path'])
    no_change = answer(newer)
    no_change.update(decision='no_change', change=None)
    daily.write_json(response, no_change)
    assert daily.advance(root, directory, response, 'synthetic reviewer')['status'] == 'reviewed_no_change'
    assert daily.advance(root, directory)['status'] == 'completed'


def test_false_evidence_is_rejected_and_retained(programme, monkeypatch):
    root, directory = programme
    completed_fixture(programme, monkeypatch)
    pending = daily.advance(root, directory)
    response = answer(daily.read(pending['packet_path']))
    response['evidence'][0]['value'] = 'invented cause'
    path = directory/'bad.json'
    daily.write_json(path, response)
    with pytest.raises(ValueError, match='quote does not match'):
        daily.advance(root, directory, path, 'synthetic reviewer')
    assert not (directory/'episodes/0/review.json').exists()
    attempts = list((directory/'episodes/0/attempts').glob('*/result.json'))
    assert len(attempts) == 1 and daily.read(attempts[0])['status'] == 'rejected'


def test_later_snapshot_and_review_source_drift_are_rejected(programme, monkeypatch):
    root, directory = programme
    completed_fixture(programme, monkeypatch)
    pending = daily.advance(root, directory)
    packet = daily.read(pending['packet_path'])
    daily.write_json(Path(packet['sources']['lab_director']), {'data': {'observation': 'changed'}})
    # The original Evolve verifier rejects a changed source, even if a review self-hash is valid.
    with pytest.raises(ValueError, match='source changed'):
        daily.evolve.verify_agent_handoff(Path(packet['evolve_input']))
    snapshot = directory/'feeds/2024-01-18/artifacts/global_stock_feed.json'
    snapshot.write_text('{}')
    with pytest.raises(ValueError, match='snapshot changed'):
        daily.advance(root, directory)


def test_review_cannot_change_non_lab_or_hide_change(programme, monkeypatch):
    root, directory = programme
    completed_fixture(programme, monkeypatch)
    pending = daily.advance(root, directory)
    packet = daily.read(pending['packet_path'])
    base = answer(packet)
    for change in ({'node_id': 'oracle_cp2_emitter', 'skill_addon': 'Wrong scope'},
                   {'node_id': 'lab_director', 'skill_addon': 'x'*513}):
        response = deepcopy(base)
        response['change'] = change
        with pytest.raises(ValueError):
            daily.compile_review(root, packet, response)
    base['decision'] = 'no_change'
    with pytest.raises(ValueError, match='must not contain'):
        daily.compile_review(root, packet, base)


def test_changed_reviewed_policy_is_not_adopted(programme, monkeypatch):
    root, directory = programme
    completed_fixture(programme, monkeypatch)
    pending = daily.advance(root, directory)
    response = directory/'answer.json'
    daily.write_json(response, answer(daily.read(pending['packet_path'])))
    result = daily.advance(root, directory, response, 'synthetic reviewer')
    policy = daily.read(result['policy_path'])
    policy['nodes']['lab_director']['skill_addon'] = 'Unreviewed replacement'
    policy['policy_sha256'] = daily.policy_sha256(policy)
    daily.write_json(Path(result['policy_path']), policy)
    with pytest.raises(ValueError, match='successor policy changed'):
        daily.advance(root, directory)


def test_authored_source_change_before_first_run_is_rejected(programme):
    root, directory = programme
    node = next((root/'codex/substrate/nodes/lab').glob('*.json'))
    node.write_text(node.read_text() + '\n')
    with pytest.raises(ValueError, match='Frozen graph'):
        daily.advance(root, directory)


def test_review_identity_drift_is_not_silently_accepted(programme, monkeypatch):
    root, directory = programme
    completed_fixture(programme, monkeypatch)
    pending = daily.advance(root, directory)
    response = directory/'answer.json'
    daily.write_json(response, answer(daily.read(pending['packet_path'])))
    daily.advance(root, directory, response, 'synthetic reviewer')
    receipt = directory/'episodes/0/review.json'
    changed = daily.read(receipt)
    changed['reviewer'] = 'someone else'
    daily.write_json(receipt, changed)
    with pytest.raises(ValueError, match='receipt changed'):
        daily.advance(root, directory)
