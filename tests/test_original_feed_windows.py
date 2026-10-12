"""Offline checks for the real-data example's attribution and claim boundaries."""
from copy import deepcopy
from types import SimpleNamespace

import pytest

from research.original_feed_windows import NODE, aggregate, checked_change, observe, verify_baseline
from system.lib.reasoning_policy import policy_sha256
from zenith.providers import write_json


def policy():
    value = {'variant_id': 'base', 'nodes': {NODE: {'skill_addon': 'Base'},
                                          'lab_seed_state': {'skill_addon': 'Unchanged'}}}
    value['policy_sha256'] = policy_sha256(value)
    return value


def graph():
    return {n: SimpleNamespace(dependencies=()) for n in policy()['nodes']}


@pytest.mark.parametrize('extra', ['upstream', 'context', 'node_set'])
def test_repair_rejects_extra_changes(extra):
    base = policy()
    candidate = deepcopy(base)
    candidate['variant_id'] = 'candidate'
    candidate['nodes'][NODE]['skill_addon'] = 'Bound output length'
    if extra == 'upstream':
        candidate['nodes']['lab_seed_state']['skill_addon'] = 'Different input treatment'
    elif extra == 'context':
        candidate['nodes'][NODE]['max_context_chars'] = 256
    else:
        del candidate['nodes']['lab_seed_state']
    candidate['policy_sha256'] = policy_sha256(candidate)
    with pytest.raises(ValueError):
        checked_change(base, candidate, graph())


def test_single_supplemental_instruction_is_admitted():
    base = policy()
    candidate = deepcopy(base)
    candidate['nodes'][NODE]['skill_addon'] = 'Bound output length'
    candidate['policy_sha256'] = policy_sha256(candidate)
    checked_change(base, candidate, graph())


def test_capacity_class_needs_failed_artifact_and_provider_length_receipt(tmp_path):
    artifact = tmp_path / 'artifacts' / (NODE + '.json')
    call = tmp_path / 'handoff/api_calls/openrouter_budgeted/call.json'
    write_json(artifact, {'status': 'failure', 'metadata': {'error': 'invalid JSON'}})
    record = {'node_id': NODE, 'provider_response': {'choices': [{'finish_reason': 'stop'}]}}
    write_json(call, record)
    assert observe(tmp_path)['failure_mode'] == 'other_execution_failure'
    record['provider_response']['choices'][0]['finish_reason'] = 'length'
    write_json(call, record)
    assert observe(tmp_path)['failure_mode'] == 'output_capacity'
    write_json(artifact, {'status': 'success'})
    assert observe(tmp_path)['failure_mode'] == 'none'


def test_overlap_does_not_inflate_failures_or_claim_forecast_benefit():
    episodes = [{'id': str(i), 'split': 'development' if i < 2 else 'later',
                 'baseline': {'failure_mode': 'output_capacity', 'native_contract_pass': False}}
                for i in range(4)]
    for row in episodes[2:]:
        row['candidate'] = {'native_contract_pass': True}
    report = aggregate(episodes)
    assert len(report['windows']) == 9
    assert len(report['failure_modes']['output_capacity']) == 4
    assert report['paired_later_episodes'] == report['later_candidate_passes'] == 2
    assert report['forecast_improvement'] is None
    assert report['promotion_allowed'] is False
    with pytest.raises(ValueError, match='duplicate'):
        aggregate(episodes + [episodes[0]])


@pytest.mark.parametrize('changed', ['node_hashes', 'implementation_hashes', 'model', 'source_hashes', 'policy_source_sha256', 'horizon'])
def test_comparison_rejects_mixed_graphs_inputs_or_windows(tmp_path, changed):
    episode = {'time_anchor': '2026-06-26T14:31:59+00:00', 'horizon': '2026-06-26T15:30:00+00:00',
               'source_hashes': {'feed': 'original'}}
    plan = {'graph': {'nodes': [{'id': NODE, 'node_hash': 'n'}]},
            'implementation_hashes': {'runtime': 'r'}, 'model': 'model',
            'provider_slug': 'provider', 'context_profile': 'compact_feeds',
            'baseline_policy_sha256': 'policy'}
    spec = {**episode, **{k: plan[k] for k in ('implementation_hashes', 'model', 'provider_slug', 'context_profile')},
            'node_hashes': {NODE: 'n'}, 'policy_source_sha256': 'policy'}
    write_json(tmp_path / 'zenith_run.json', spec)
    verify_baseline(plan, episode, tmp_path)
    spec[changed] = '2026-06-26T16:30:00+00:00' if changed == 'horizon' else 'changed'
    write_json(tmp_path / 'zenith_run.json', spec)
    with pytest.raises(ValueError):
        verify_baseline(plan, episode, tmp_path)
