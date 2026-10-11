"""Mechanical observations remain separate from execution/causal authority."""
from copy import deepcopy
import hashlib
import json
from types import SimpleNamespace

import pytest

from research.diagnosis import observe_run
from system.lib.reasoning_policy import apply_reasoning_policy, policy_sha256, persist_context_receipt
from zenith.providers import digest, text_digest, write_json


def prepared(tmp_path, scope=('reasoner', 'source', 'withheld', 'unavailable')):
    run = tmp_path / 'episode'
    manifest = {'schema': 'zenith_execution_manifest_v1', 'mission': 'lab', 'run_id': run.name,
                'scope': list(scope), 'node_hashes': {node: text_digest(node) for node in scope}}
    write_json(run / 'zenith_run.json', manifest)
    return run, manifest


def codes(result):
    return [row['code'] for row in result['observations']]


def packet(run, node='reasoner'):
    identity = {'run_id': run.name, 'node_id': node, 'prompt_sha256': text_digest('exact prompt')}
    value = {'schema': 'zenith_agent_packet_v1', **identity, 'packet_id': digest(identity), 'prompt': 'exact prompt'}
    path = run / 'handoff/requests' / (value['packet_id'] + '.json')
    write_json(path, value)
    return path, value


def bound_policy(run, manifest):
    policy = {'variant_id': 'weighted', 'nodes': {'reasoner': {
        'skill_addon': 'Compare evidence.', 'incoming_weights': {'withheld': 0}, 'max_context_chars': 256}}}
    policy['policy_sha256'] = policy_sha256(policy)
    manifest['reasoning_policy'] = policy
    write_json(run / 'zenith_run.json', manifest)
    node = SimpleNamespace(id='reasoner', dependencies=['source', 'withheld', 'unavailable'])
    _, _, receipt = apply_reasoning_policy(node, {'source': {'text': 'x' * 600}, 'withheld': {'text': 'y'}}, policy)
    path = persist_context_receipt(run / 'artifacts', receipt)
    return path, receipt


def test_missing_run_is_observed_without_creating_it(tmp_path):
    missing = tmp_path / 'never-created'
    result = observe_run(missing)
    assert result['status'] == 'missing'
    assert codes(result) == ['manifest_missing']
    assert result['causal_claims'] is False
    assert result['manifest_ref']['sha256'] is None
    assert not missing.exists()


@pytest.mark.parametrize('raw', ['{', '{"scope":[],"scope":[]}', '{"value":NaN}', '[]', '{"value":"\\ud800"}'])
def test_malformed_manifest_is_unknown_not_absent(tmp_path, raw):
    run = tmp_path / 'bad'
    run.mkdir()
    (run / 'zenith_run.json').write_text(raw)
    result = observe_run(run)
    assert result['status'] == 'unknown'
    assert codes(result) == ['observability_unknown']
    assert result['manifest_ref']['sha256'] == hashlib.sha256(raw.encode()).hexdigest()


@pytest.mark.parametrize('field,value', [('run_id', 'another'), ('scope', ['../escape']), ('node_hashes', {})])
def test_manifest_identity_must_bind_before_artifact_absence(tmp_path, field, value):
    run, manifest = prepared(tmp_path)
    manifest[field] = value
    write_json(run / 'zenith_run.json', manifest)
    result = observe_run(run)
    assert result['status'] == 'unknown'
    assert codes(result) == ['observability_unknown']


def test_artifact_absence_presence_failure_and_unknown_have_distinct_facts(tmp_path):
    run, manifest = prepared(tmp_path)
    write_json(run / 'artifacts/reasoner.json', {'id': 'reasoner', 'node_hash': manifest['node_hashes']['reasoner'],
               'status': 'failure', 'metadata': {'error': 'contract rejected', 'validation_errors': ['required target']}})
    write_json(run / 'artifacts/source.json', {'id': 'source', 'node_hash': manifest['node_hashes']['source'],
               'status': 'loaded', 'metadata': {}, 'data': {'rows': []}})
    write_json(run / 'artifacts/withheld.json', {'id': 'other', 'status': 'success', 'metadata': {}})
    before = {p: p.read_bytes() for p in run.rglob('*') if p.is_file()}
    result = observe_run(run)
    assert result['status'] == 'observed'
    facts = {(o['node_id'], o['code']) for o in result['observations']}
    assert ('reasoner', 'node_failure_recorded') in facts
    assert ('reasoner', 'output_validation_rejected') in facts
    assert ('source', 'node_artifact_present') in facts
    assert ('unavailable', 'node_artifact_absent') in facts
    assert ('withheld', 'observability_unknown') in facts
    assert ('withheld', 'node_artifact_absent') not in facts
    assert before == {p: p.read_bytes() for p in run.rglob('*') if p.is_file()}
    assert result['causal_claims'] is False


def test_pending_requires_bound_packet_and_no_completed_artifact(tmp_path):
    run, manifest = prepared(tmp_path)
    path, value = packet(run)
    assert 'agent_response_pending' in codes(observe_run(run))
    write_json(run / 'artifacts/reasoner.json', {'id': 'reasoner', 'node_hash': manifest['node_hashes']['reasoner'],
               'status': 'success', 'metadata': {}})
    assert 'agent_response_pending' not in codes(observe_run(run))
    (run / 'artifacts/reasoner.json').unlink()
    value['prompt'] = 'changed bytes'
    write_json(path, value)
    assert 'agent_response_pending' not in codes(observe_run(run))
    assert any(o['details'].get('reason') == 'packet_binding' for o in observe_run(run)['observations'])


def test_rejection_requires_matching_request_response_and_validation(tmp_path):
    run, _ = prepared(tmp_path)
    path, request = packet(run)
    answer = {**request, 'response_text': 'invalid output'}
    write_json(run / 'handoff/responses' / path.name, answer)
    validation = {'schema': 'zenith_import_validation_v1', **{k: request[k] for k in ('packet_id', 'run_id', 'node_id')},
                  'response_sha256': text_digest(answer['response_text']), 'engine_accepted': False,
                  'engine_errors': ['schema rejected']}
    destination = run / 'handoff/validation' / path.name
    write_json(destination, validation)
    result = observe_run(run)
    assert 'output_validation_rejected' in codes(result)
    rejection = next(o for o in result['observations'] if o['code'] == 'output_validation_rejected')
    assert rejection['source_ref']['sha256'] == hashlib.sha256(destination.read_bytes()).hexdigest()
    validation['response_sha256'] = '0' * 64
    write_json(destination, validation)
    assert 'output_validation_rejected' not in codes(observe_run(run))
    assert any(o['details'].get('reason') == 'validation_binding' for o in observe_run(run)['observations'])


def test_native_policy_receipt_reports_only_recorded_delivery_not_cause(tmp_path):
    run, manifest = prepared(tmp_path)
    path, _ = bound_policy(run, manifest)
    result = observe_run(run)
    contexts = [o for o in result['observations'] if o['code'].startswith('context_')]
    assert {o['code']: o['details']['dependency_ids'] for o in contexts} == {
        'context_missing_recorded': ['unavailable'], 'context_omitted_recorded': ['withheld'],
        'context_excerpt_recorded': ['source']}
    assert all(o['source_ref']['sha256'] == hashlib.sha256(path.read_bytes()).hexdigest() for o in contexts)
    assert all(o['verification'] == 'receipt_hash_manifest_policy_binding' for o in contexts)
    assert 'no independent execution' in result['verification_boundary']
    assert result['causal_claims'] is False


@pytest.mark.parametrize('tamper', ['hash', 'node', 'policy', 'counter', 'view', 'weight', 'missing'])
def test_unverified_or_self_consistent_malformed_policy_is_unknown(tmp_path, tamper):
    run, manifest = prepared(tmp_path)
    path, receipt = bound_policy(run, manifest)
    receipt = deepcopy(receipt)
    if tamper == 'hash':
        receipt['receipt_sha256'] = '0' * 64
    elif tamper == 'node':
        receipt['node_id'] = 'source'
    elif tamper == 'policy':
        receipt['policy_sha256'] = '0' * 64
    elif tamper == 'counter':
        receipt['retained_source_chars'] += 1
    elif tamper == 'view':
        receipt['incoming_edges'][0]['view'] = 'omitted'
    elif tamper == 'weight':
        receipt['incoming_edges'][0]['weight'] = True
    else:
        receipt['missing_dependency_ids'] = ['../../outside']
    if tamper != 'hash':
        receipt['receipt_sha256'] = digest({k: v for k, v in receipt.items() if k != 'receipt_sha256'})
    path.unlink()
    write_json(path.with_name(receipt['node_id'] + '.' + receipt['receipt_sha256'] + '.json'), receipt)
    result = observe_run(run)
    assert not any(o['code'].startswith('context_') for o in result['observations'])
    assert any(o['details'].get('reason') == 'context_receipt_binding' for o in result['observations'])


def test_external_symlink_is_unknown_and_never_artifact_absence(tmp_path):
    run, manifest = prepared(tmp_path)
    outside = tmp_path / 'private.json'
    write_json(outside, {'id': 'reasoner', 'node_hash': manifest['node_hashes']['reasoner'], 'status': 'success'})
    (run / 'artifacts').mkdir()
    (run / 'artifacts/reasoner.json').symlink_to(outside)
    observation = next(o for o in observe_run(run)['observations'] if o['node_id'] == 'reasoner')
    assert observation['code'] == 'observability_unknown'
    assert observation['details']['reason'] == 'outside_run'
    assert observation['source_ref']['sha256'] is None
