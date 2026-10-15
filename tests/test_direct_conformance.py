"""Offline owner-level checks for the versioned direct-action comparison."""
from copy import deepcopy
import json

import pytest

from research import conformance_study as study
from research.direct_investigation import run_direct
from research.native_conformance_tasks import build_dataset, measure
from tests.test_conformance_study import (
    CORRECT, MODEL, PARENT, PROBE, ROUTE, FixtureProvider, factory,
    prepared, response, tiny_dataset,
)


def action(*queries):
    return json.dumps({'queries': list(queries), 'note': None})


def test_direct_arms_share_first_paid_turn_and_replay_exact_feedback(tmp_path):
    arms = ('direct_adaptive', 'direct_masked')
    output = prepared(tmp_path, arms=arms)
    q1 = {'capacity': 1, 'events': [{'op': 'call', 'key': 7}]}
    assert measure('lru-0', q1) == {'hits': 0, 'misses': 1, 'size': 1}
    provider = FixtureProvider(tmp_path/'provider', [
        response(PARENT), action(q1), action(PROBE), response(CORRECT),
        action(PROBE), response(CORRECT),
    ])
    result = study.run(output, provider_factory=factory(provider))
    assert len(provider.calls) == 6
    assert result['totals']['direct_adaptive']['correct'] == 1
    assert study.read(output/'protocol.json')['max_calls'] == 6
    frozen = study.read(output/'frozen.json')
    adaptive = frozen['records'][0]['arms']['direct_adaptive']['investigation']
    masked = frozen['records'][0]['arms']['direct_masked']['investigation']
    assert len(study.recorded_calls(frozen['records'][0])) == 6
    assert adaptive['turns'][0]['call_id'] == masked['turns'][0]['call_id']
    assert adaptive['turns'][0]['envelope'] == masked['turns'][0]['envelope']
    assert adaptive['turns'][0]['raw'] == masked['turns'][0]['raw']
    assert adaptive['turns'][1]['envelope']['prompt']['receipts'][0]['expected'] == {
        'hits': 0, 'misses': 1, 'size': 1}
    assert set(masked['turns'][1]['envelope']['prompt']['receipts'][0]) == {
        'slot', 'turn', 'query'}
    assert adaptive['turns'][1]['envelope']['prompt']['outcomes_available'] is True
    assert masked['turns'][1]['envelope']['prompt']['outcomes_available'] is False
    for call in provider.calls:
        material = json.dumps(call)
        assert 'protected-screen-never-delivered' not in material
        assert 'protected-confirmation-never-delivered' not in material
        assert 'private-reference-never-delivered' not in material
    assert study.replay(output)['model_calls_replayed'] == 6


def test_direct_batch_is_one_decision_call_and_repair_receives_measured_witness(tmp_path):
    output = prepared(tmp_path, arms=('direct_batch',))
    provider = FixtureProvider(tmp_path/'provider', [
        response(PARENT), action(PROBE), response(CORRECT),
    ])
    result = study.run(output, provider_factory=factory(provider))
    assert len(provider.calls) == 3
    assert result['detection']['direct_batch']['native_probes'] == 1
    repair = provider.calls[-1]['prompt']
    assert repair['investigation']['receipts'][0]['expected'] == {
        'hits': 1, 'misses': 1, 'size': 1}
    assert 'turns' not in repair['investigation']
    assert study.replay(output)['model_calls_replayed'] == 3


def test_repair_only_has_zero_probe_and_one_repair_call(tmp_path):
    output = prepared(tmp_path, arms=('repair_only',))
    provider = FixtureProvider(tmp_path/'provider', [response(PARENT), response(CORRECT)])
    result = study.run(output, provider_factory=factory(provider))
    assert len(provider.calls) == 2
    assert result['detection']['repair_only']['native_probes'] == 0
    assert provider.calls[-1]['prompt']['investigation']['receipts'] == []
    assert study.replay(output)['model_calls_replayed'] == 2


def test_no_query_direct_and_repair_only_send_identical_repair_evidence():
    task = tiny_dataset()['tasks'][0]
    parent = {'source': PARENT,
              'development': study.score_program(PARENT,task['examples'])}
    direct = run_direct(task,parent,lambda envelope: action(),turns=1,
                        queries_per_turn=8)
    assert study.repair_prompt(task,parent,direct) == study.repair_prompt(
        task,parent,study.empty_investigation())


def test_direct_provider_failure_persists_partial_turn_and_blocks_panels(tmp_path):
    output = prepared(tmp_path, arms=('direct_adaptive',))
    q1 = {'capacity': 1, 'events': [{'op': 'call', 'key': 7}]}
    provider = FixtureProvider(tmp_path/'provider', [
        response(PARENT), action(q1), RuntimeError('fixture transport failure'),
    ])
    result = study.run(output, provider_factory=factory(provider))
    assert result['complete'] is False
    assert len(provider.calls) == 3
    record = study.read(output/'records/native-lru-0.json')
    assert len(study.recorded_calls(record)) == 3
    turn = record['arms']['direct_adaptive']['investigation']['turns'][1]
    assert turn['raw'] is None and 'fixture transport failure' in turn['delivery_error']
    assert study.read(output/'frozen.json')['complete'] is False
    assert not (output/'screen.json').exists()
    assert study.replay_partial(output)['protected_partitions'] == []
    with pytest.raises(ValueError, match='Incomplete'):
        study.evaluate(output, 'confirmation')


def test_malformed_direct_action_uses_no_hidden_retry_but_still_replays(tmp_path):
    output = prepared(tmp_path, arms=('direct_adaptive',))
    provider = FixtureProvider(tmp_path/'provider', [
        response(PARENT), '{"queries":', response(CORRECT),
    ])
    result = study.run(output, provider_factory=factory(provider))
    assert len(provider.calls) == 3
    investigation = study.read(output/'frozen.json')['records'][0]['arms']['direct_adaptive']['investigation']
    assert investigation['halted'] == 'invalid_delivery'
    assert investigation['model_turn_attempts'] == 1
    assert investigation['native_probes'] == 0
    assert result['detection']['direct_adaptive']['invalid_deliveries'] == 1
    assert study.replay(output)['model_calls_replayed'] == 3


def test_new_parent_count_freezes_distinct_panels_for_each_replicate():
    data = build_dataset(seed=20261018, panel_size=3, parents_per_contract=4)
    assert len(data['tasks']) == 12
    assert data['parents_per_contract'] == 4
    assert {task['source_id'] for task in data['tasks']} >= {
        'sqlite-3', 'lru-3', 'utf8-3'}
    for task in data['tasks']:
        assert measure(task['source_id'], task['screen'][0]['input']) == task['screen'][0]['expected']
    by_kind = {}
    for task in data['tasks']:
        kind = task['source_id'].split('-')[0]
        by_kind.setdefault(kind, []).extend(row['input'] for name in ('screen','confirmation')
                                     for row in task[name])
    for rows in by_kind.values():
        assert len(rows) == len({study.digest(row) for row in rows})
