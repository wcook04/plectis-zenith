"""Matched-generation adapter tests, using a synthetic reviewed teacher."""
import json
from pathlib import Path
import pytest
from research import daily_matchoff, cohort
from zenith import daily, runtime
from zenith.providers import AgentProvider, ResponsePending
from benchmarks import investorbench as ib
from test_investorbench import source


def teacher(tmp_path, monkeypatch, matured='2020-06-30T20:00:00+00:00'):
    baseline = {'variant_id': 'fixture-baseline', 'nodes': {}}
    baseline['policy_sha256'] = daily.policy_sha256(baseline)
    candidate = {'variant_id': 'fixture-candidate', 'nodes': {'lab_director': {'skill_addon': 'Synthetic comparison skill.'}}}
    candidate['policy_sha256'] = daily.policy_sha256(candidate)
    a, b = tmp_path/'baseline.json', tmp_path/'candidate.json'
    daily.write_json(a, baseline); daily.write_json(b, candidate)
    packet = {'matured_at': matured, 'packet_sha256': 'a'*64}
    decision = {'status': 'reviewed_candidate', 'review_sha256': 'b'*64,
                'response': {'diagnosis': 'Synthetic candidate', 'change': {'node_id': 'lab_director', 'skill_addon': 'Synthetic comparison skill.'}}}
    monkeypatch.setattr(daily, 'reviewed_episode', lambda *args: ({'programme_sha256': 'c'*64}, packet, decision, a, b))
    return a, b


def test_freeze_uses_same_native_issues_and_distinct_policies(source, tmp_path, monkeypatch):
    teacher(tmp_path, monkeypatch)
    output = tmp_path/'matchoff'
    result = daily_matchoff.freeze(runtime.DEFAULT_ROOT, tmp_path, 0, source,
                                   '2020-07-01', '2020-07-01', output, 'synthetic-agent', 0.001)
    assert result['reasoning_responses_planned'] == 42
    spec = daily.read(output/'cohort/cohort.json')
    assert [c['candidate_id'] for c in spec['candidates']] == ['baseline', 'challenger']
    assert spec['issues'][0]['target_ids'] == ['HON', 'JNJ', 'MSFT']
    assert {c['model'] for c in spec['candidates']} == {'synthetic-agent'}
    assert all(len(c['reasoner_scope']) == 21 for c in spec['candidates'])
    result = cohort.evaluate(output/'cohort')
    assert result['state'] == 'pending'
    with pytest.raises(ValueError, match='Complete matched'):
        daily_matchoff.retain(runtime.DEFAULT_ROOT, output, 'synthetic reviewer')
    assert not (output/'retained-policy.json').exists()


def test_matchoff_cannot_use_teacher_period(source, tmp_path, monkeypatch):
    teacher(tmp_path, monkeypatch, '2020-07-02T20:00:00+00:00')
    with pytest.raises(ValueError, match='follow the teacher'):
        daily_matchoff.freeze(runtime.DEFAULT_ROOT, tmp_path, 0, source,
                              '2020-07-01', '2020-07-01', tmp_path/'bad', 'synthetic', 0)


def test_agent_receipt_discloses_native_execution_kind(tmp_path):
    run = tmp_path/'SYNTHETIC'
    provider = AgentProvider(run)
    with pytest.raises(ResponsePending):
        provider.ask_ai('synthetic prompt', {'meta': {'node_id': 'lab_seed_state', 'session_id': 'SYNTHETIC'}})
    receipts = list((run/'handoff/receipts').glob('*.json'))
    assert len(receipts) == 1
    assert daily.read(receipts[0])['execution_kind'] == 'agent'


@pytest.mark.parametrize('decision,selected', [('candidate_proposal', 'challenger'), ('discard', 'incumbent')])
def test_retention_binds_selection_and_next_generation_cutoff(tmp_path, monkeypatch, decision, selected):
    """Stub only scores; real source adaptation, freeze, retention and init boundaries."""
    teacher(tmp_path, monkeypatch)
    raw = tmp_path/'raw'
    raw.mkdir()
    calendar = daily.fnspid.calendar_for('2020-07-01', '2020-08-10')
    rows = {s.date().isoformat(): {'prices': 100+i, 'news': [], '10k': [], '10q': []}
            for i, s in enumerate(calendar.sessions_in_range('2020-07-01', '2020-08-07'))}
    pins = {}
    for name in ib.FILES:
        daily.write_json(raw/name, rows)
        pins[name] = ib.sha(raw/name)
    monkeypatch.setattr(ib, 'FILES', pins)
    dataset = tmp_path/'admitted'
    ib.acquire(dataset, raw)
    output = tmp_path/'matchoff'
    daily_matchoff.freeze(runtime.DEFAULT_ROOT, tmp_path, 0, dataset,
                          '2020-07-01', '2020-07-29', output, 'synthetic-agent', 0.001)
    frozen = daily.read(output/'cohort/cohort.json')
    assert len(frozen['issues']) == 20
    result = {'state': 'complete', 'issue_count': 20, 'decisions': {'challenger': decision}}
    def synthetic_evaluate(study):
        daily.write_json(study/'development-comparison.json', result)
        return result
    monkeypatch.setattr(cohort, 'evaluate', synthetic_evaluate)
    receipt = daily_matchoff.retain(runtime.DEFAULT_ROOT, output, 'synthetic reviewer')
    assert receipt['selected'] == selected
    assert receipt['evidence_through'] == frozen['truth_as_of']
    retained, cutoff, _ = daily_matchoff.retained_policy(output/'retention.json')
    assert retained['policy_sha256'] == receipt['policy_sha256']
    assert cutoff.startswith('2020-07-30')
    with pytest.raises(ValueError, match='after selection evidence'):
        daily.initialize(runtime.DEFAULT_ROOT, tmp_path/'overlap', dataset,
                         '2020-07-30', '2020-07-31', retention=output/'retention.json')
    next_dir = tmp_path/'next-generation'
    daily.initialize(runtime.DEFAULT_ROOT, next_dir, dataset,
                     '2020-07-31', '2020-08-03', retention=output/'retention.json')
    assert daily.load(runtime.DEFAULT_ROOT, next_dir)['baseline'] == retained
    changed = daily.read(output/'cohort/development-comparison.json')
    changed['decisions']['challenger'] = 'tampered'
    daily.write_json(output/'cohort/development-comparison.json', changed)
    with pytest.raises(ValueError, match='comparison changed'):
        daily_matchoff.retained_policy(output/'retention.json')
