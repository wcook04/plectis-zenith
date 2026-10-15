"""Behavioral and evidence-boundary checks for the authored client pilot."""
from __future__ import annotations

import hashlib
import json

import pytest

from research import client_investigation_study as study
from research.client_investigation_tasks import prepare_task, public_family_spec, task_ids


TRANSFER_SPEC = {
    'family': 'transfer', 'contract': 'test contract',
    'query_shape': {'steps': 'legal transfer steps'}, 'probe_limit': 6}


BATCH_QUERY = {'outer': True, 'initial': [1],
               'steps': [[2, 2], [3]], 'continuation': 4}
TRANSFER_QUERY = {'outer': True, 'initial': [[1, 5], [2, 1]],
                  'steps': [[1, 2, 2], [1, 10, 1], [2, 1, 1]],
                  'continuation': [2, 1]}


def action(queries, note=None):
    return json.dumps({'queries': queries, 'note': note})


def development_row():
    run = study.run_arm('batch-a7', 'same_history',
                        ask=lambda envelope: action([BATCH_QUERY]))
    return {'public_task': run['public_task'], 'receipts': run['receipts']}


def test_fixed_tester_detects_all_flawed_clients_and_spares_correct_ones():
    outcomes = {task: study.run_arm(task, 'fixed') for task in task_ids()}
    assert {task for task, run in outcomes.items() if run['detected']} == {
        'batch-a7', 'batch-r9', 'batch-u2', 'batch-z5',
        'transfer-b8', 'transfer-f3', 'transfer-q1', 'transfer-v4'}
    assert all(run['query_slots'] <= study.QUERY_CAP for run in outcomes.values())
    assert all(run['valid_probes'] == run['native_cost']['reference_calls']
               for run in outcomes.values())


def test_host_receipt_keeps_custody_but_next_model_prompt_hides_fingerprints():
    prompts = []
    def ask(envelope):
        prompts.append(envelope)
        return action([BATCH_QUERY]) if len(prompts) == 1 else action([])
    run = study.run_arm('batch-k4', 'same_history', ask=ask)
    assert len(prompts) == 2 and run['valid_probes'] == 1
    host = run['receipts'][0]['measurement']
    assert 'source_sha256' in host and 'reference_sql' in host['cost']
    model = prompts[1]['prompt']
    assert model['target_receipts'][0]['reference'] == host['reference']
    for forbidden in ('source_sha256', 'sqlite_version', 'reference_sql',
                      'client_sql', 'example_audit', 'mode'):
        assert forbidden not in json.dumps(model)


def test_prepared_example_is_shared_and_audited_once():
    prepared = prepare_task('transfer-m6')
    snapshots = []
    run = study.run_arm('transfer-m6', 'fixed', prepared=prepared,
                        on_event=lambda record: snapshots.append(record))
    assert run['example_audit'] == prepared['audit']
    assert 'cost' not in run['public_task']['example']
    assert snapshots[-1]['native_cost'] == run['native_cost']
    assert run['native_cost']['reference_calls'] == run['valid_probes']
    assert prepared['audit']['example_receipt']['cost']['reference_calls'] == 1


def test_same_history_ablation_receives_full_measured_history_but_no_host_custody():
    development = [development_row()]
    shown = []
    def ask(envelope):
        shown.append(envelope['prompt'])
        return action([])
    study.run_arm('transfer-m6', 'same_history', ask=ask, development=development)
    assert shown[0]['development_history'][0]['receipts'][0]['discrepancy']
    assert 'source_sha256' not in json.dumps(shown[0])
    assert 'cost' not in json.dumps(shown[0])
    with pytest.raises(ValueError, match='cold'):
        study.run_arm('transfer-m6', 'cold', ask=ask, development=development)


def test_duplicate_and_invalid_queries_consume_slots_without_native_charge():
    example = prepare_task('batch-k4')['public']['example']['query']
    deliveries = iter([action([example]), action([{'bad': 1}]),
                       action([BATCH_QUERY]), action([])])
    run = study.run_arm('batch-k4', 'same_history',
                        ask=lambda envelope: next(deliveries))
    assert run['query_slots'] == 3 and run['valid_probes'] == 1
    assert run['native_cost']['reference_calls'] == 1
    assert all('query_error' in r for r in run['receipts'][:2])


def test_invalid_model_delivery_is_retained_and_not_retried():
    calls = []
    def ask(envelope):
        calls.append(envelope)
        return '{"queries":'
    run = study.run_arm('transfer-b8', 'cold', ask=ask)
    assert len(calls) == 1 and run['model_call_attempts'] == 1
    assert run['halted'] == 'model_delivery_error'
    assert run['valid_probes'] == 0 and run['turns'][0]['error']


def test_provider_exception_is_terminal_for_arm_and_cannot_open_a_panel(tmp_path):
    def fail(envelope):
        raise RuntimeError('simulated transport failure')
    events = []
    with pytest.raises(RuntimeError, match='study is incomplete'):
        study.run_arm('transfer-b8', 'cold', ask=fail,
                      on_event=lambda row: events.append(row))
    assert events[-1]['halted'] == 'adapter_failure'
    assert events[-1]['turns'][0]['error'].startswith('adapter_failure:')


def test_restricted_artifact_compilation_and_execution():
    source = '''def investigate(context, acquire):
    if context["public_task"]["family"] == "transfer":
        return {"query": {"outer": True, "initial": [[1, 5], [2, 1]], "steps": [[1, 2, 2], [1, 10, 1], [2, 1, 1]], "continuation": [2, 1]}, "note": "failure then recovery"}
    return {"query": None, "note": None}
'''
    artifact_prompts = []
    def artifact_ask(envelope):
        artifact_prompts.append(envelope)
        return json.dumps({'source': source, 'scope': 'caller-owned transactions'})
    artifact = study.compile_artifact([development_row()], artifact_ask,
        kind='procedure', target_family_spec=TRANSFER_SPEC)
    assert artifact['error'] is None
    assert 'Only function definitions at module level.' in artifact_prompts[0]['system']
    assert artifact_prompts[0]['prompt']['prospective_target_family'] == TRANSFER_SPEC
    assert 'example' not in json.dumps(artifact_prompts[0]['prompt']['prospective_target_family'])
    assert 'target task' not in json.dumps(artifact_prompts[0]['prompt'])
    run = study.run_arm('transfer-b8', 'procedure',
                        development=[development_row()], artifact=artifact)
    assert run['detected'] and run['valid_probes'] == 1
    assert run['model_call_attempts'] == 0
    forbidden = study.compile_artifact([development_row()],
        lambda envelope: json.dumps({'source': 'import os\ndef investigate(context, acquire): return {}',
                                     'scope': 'bad'}), kind='ordinary_reuse',
        target_family_spec=TRANSFER_SPEC)
    assert forbidden['error'] and forbidden['source'] is None


@pytest.mark.parametrize('kind', ('procedure', 'ordinary_reuse'))
def test_v2_actual_preparation_allows_unmeasured_legal_actions_for_both_rivals(kind):
    prompts = []
    source = '''def investigate(context, acquire):
    if not context["target_receipts"]:
        return {"query": {"outer": True, "initial": [[1, 5], [2, 1]], "steps": [[1, 2, 2], [1, 10, 1], [2, 1, 1]], "continuation": [2, 1]}, "note": "proposed contract test; outcome unmeasured"}
    return {"query": None, "note": None}
'''
    def ask(envelope):
        prompts.append(envelope)
        return json.dumps({'source': source, 'scope': 'known-interface experiment'})
    spec = public_family_spec('transfer')
    artifact = study.compile_artifact([development_row()], ask,
        kind=kind, target_family_spec=spec, prompt_version='v2')
    assert len(prompts) == artifact['model_call_attempts'] == 1
    assert artifact['raw'] == json.dumps({'source': source, 'scope': 'known-interface experiment'})
    assert artifact['source'] == source and artifact['error'] is None
    envelope = prompts[0]
    assert study.ACTION_PERMISSION in envelope['system']
    assert 'including before any target receipt exists.' in envelope['system']
    assert 'Never present an unmeasured reference/client outcome' in envelope['system']
    assert 'Stopping remains allowed.' in envelope['system']
    assert 'Use only that measured evidence.' not in envelope['system']
    assert envelope['prompt']['prospective_target_family'] == spec
    assert artifact['envelope_sha256'] == study.digest(envelope)
    run = study.run_arm('transfer-b8', kind, artifact=artifact,
                        development=[development_row()], prompt_version='v2')
    assert run['detected'] and run['query_slots'] == run['valid_probes'] == 1
    assert run['policy_executions'] == 1 and run['model_call_attempts'] == 0
    assert run['native_cost']['reference_calls'] == 1


@pytest.mark.parametrize('arm', ('same_history', 'cold'))
def test_v2_actual_first_direct_request_allows_action_before_target_receipts(arm):
    prompts = []
    def ask(envelope):
        prompts.append(envelope)
        return action([])
    run = study.run_arm('transfer-b8', arm, ask=ask, prompt_version='v2')
    assert len(prompts) == run['model_call_attempts'] == 1
    assert prompts[0]['prompt']['target_receipts'] == []
    assert prompts[0]['prompt']['public_task']['query_shape'] == prepare_task('transfer-b8')['public']['query_shape']
    assert study.ACTION_PERMISSION in prompts[0]['system']
    assert run['halted'] == 'model_stop' and run['query_slots'] == 0


@pytest.mark.parametrize('kind', ('procedure', 'ordinary_reuse'))
def test_v2_retains_artifact_stop_without_rescue(kind):
    source = 'def investigate(context, acquire):\n    return {"query": None, "note": "decline"}\n'
    raw = json.dumps({'source': source, 'scope': 'declined'})
    artifact = study.compile_artifact([], lambda envelope: raw,
        kind=kind, target_family_spec=public_family_spec('transfer'))
    run = study.run_arm('transfer-b8', kind, artifact=artifact)
    assert artifact['raw'] == raw and artifact['source'] == source
    assert run['halted'] == 'policy_stop' and run['query_slots'] == 0
    assert run['policy_executions'] == 1 and run['model_call_attempts'] == 0


def test_v1_prompts_remain_byte_identical_and_selectable():
    assert hashlib.sha256(study.DIRECT_SYSTEM_V1.encode()).hexdigest() == (
        'c3811e6eaa649ea9f4c8875d8026c973a0b6b801ab3cb4cb87a6993d4f814591')
    assert hashlib.sha256(study.ARTIFACT_SYSTEM_V1.encode()).hexdigest() == (
        '8d82b152bd7215c487b3f7872d2f1f51e9ff58317f6757361ecfe5b2d4ffd051')
    direct = []
    run = study.run_arm('transfer-b8', 'cold',
        ask=lambda envelope: direct.append(envelope) or action([]), prompt_version='v1')
    prepared = []
    study.compile_artifact([], lambda envelope: prepared.append(envelope) or '{}',
        kind='procedure', target_family_spec=public_family_spec('transfer'), prompt_version='v1')
    assert run['version'] == study.VERSION_V1
    assert direct[0]['system'] == study.DIRECT_SYSTEM_V1
    assert prepared[0]['system'] == study.ARTIFACT_SYSTEM_V1
    assert set(direct[0]) == {'phase', 'arm', 'turn', 'system', 'response_schema', 'prompt'}
    assert set(prepared[0]) == {'phase', 'kind', 'system', 'response_schema', 'prompt'}


def test_unknown_prompt_version_is_rejected_before_inference_or_freeze(tmp_path):
    def no_call(envelope):
        pytest.fail('unknown prompt version must not reach provider')
    with pytest.raises(ValueError, match='prompt version'):
        study.run_arm('transfer-b8', 'cold', ask=no_call, prompt_version='v3')
    with pytest.raises(ValueError, match='prompt version'):
        study.compile_artifact([], no_call, kind='procedure',
            target_family_spec=public_family_spec('transfer'), prompt_version='v3')
    output = tmp_path/'unknown-profile'
    with pytest.raises(ValueError, match='prompt version'):
        study.prepare_study(output, model='deepseek/offline-test',
            provider_slug='offline-test', prompt_version='v3',
            model_evidence={'source': 'offline fixture; no inference'})
    assert not output.exists()


def test_same_history_and_ordinary_artifact_are_distinct_arms():
    assert set(study.ARMS) == {'procedure', 'ordinary_reuse',
                               'same_history', 'cold', 'fixed'}
    with pytest.raises(ValueError, match='artifact'):
        study.run_arm('transfer-b8', 'ordinary_reuse', development=[development_row()])
    assert study.MAX_CALLS == 92


def test_panel_cannot_open_without_complete_frozen_study(tmp_path):
    with pytest.raises(FileNotFoundError):
        study.open_panel(tmp_path)


@pytest.mark.parametrize('prompt_version', study.PROMPT_VERSIONS)
def test_offline_freeze_run_and_panel_are_separate_once_only(tmp_path, prompt_version):
    source = '''def investigate(context, acquire):
    if context["target_receipts"]:
        return {"query": None, "note": None}
    return {"query": {"outer": True, "initial": [[1, 5], [2, 1]], "steps": [[1, 2, 2], [1, 10, 1], [2, 1, 1]], "continuation": [2, 1]}, "note": "failure then continuation"}
'''
    output = tmp_path/'client-pilot'
    protocol = study.prepare_study(
        output, model='deepseek/offline-test', provider_slug='offline-test',
        prompt_version=prompt_version,
        model_evidence={'source': 'offline fixture; no inference'})
    assert protocol['max_calls'] == 92
    assert protocol['schema'] == (study.VERSION_V1 if prompt_version == 'v1' else study.VERSION)
    if prompt_version == 'v2':
        assert protocol['prompt_version'] == 'v2'
        assert protocol['protocol_doc'] == 'docs/client-investigation-protocol-v2-20261015.md'
        assert protocol['prompt_sha256'] == {
            'direct': hashlib.sha256(study.DIRECT_SYSTEM.encode()).hexdigest(),
            'artifact': hashlib.sha256(study.ARTIFACT_SYSTEM.encode()).hexdigest()}
    else:
        assert 'prompt_version' not in protocol and 'prompt_sha256' not in protocol
    assert not (output/'started.json').exists()
    prompts = []
    def ask(envelope):
        prompts.append(envelope)
        if envelope['phase'] == 'prepare':
            return json.dumps({'source': source, 'scope': 'known-interface transfer test'})
        if envelope['prompt']['target_receipts']:
            return action([])
        family = envelope['prompt']['public_task']['family']
        return action([BATCH_QUERY if family == 'batch' else TRANSFER_QUERY])
    frozen = study.execute_study(output, ask)
    assert frozen['complete'] and frozen['failure'] is None
    assert len(frozen['development']) == 5 and len(frozen['targets']) == 5
    assert all(set(arms) == set(study.ARMS) for arms in frozen['targets'].values())
    assert frozen['artifacts']['procedure']['error'] is None
    assert frozen['artifacts']['ordinary_reuse']['error'] is None
    assert len(prompts) <= 92
    assert len(prompts) == (
        sum(run['model_call_attempts'] for run in frozen['development_runs']) +
        sum(row['model_call_attempts'] for row in frozen['artifacts'].values()) +
        sum(run['model_call_attempts'] for arms in frozen['targets'].values()
            for run in arms.values()))
    assert frozen['schema'] == protocol['schema']
    assert all('source_sha256' not in json.dumps(p) and 'reference_sql' not in json.dumps(p)
               for p in prompts)
    replay = study.replay_study(output)
    assert replay['status'] == 'exact' and replay['network_calls'] == 0
    assert replay['model_attempts_replayed'] == len(prompts)
    assert not (output/'protected-panel.json').exists()
    panel = study.open_panel(output)
    assert panel['target_clients']['transfer-m6']['correct'] == 80
    assert all(panel['target_clients'][key]['correct'] < 80
               for key in task_ids('transfer') if key != 'transfer-m6')
    with pytest.raises(ValueError, match='retried'):
        study.execute_study(output, ask)
    with pytest.raises(ValueError, match='already opened'):
        study.open_panel(output)


def test_v2_freeze_rejects_changed_prompt_profile(tmp_path):
    output = tmp_path/'v2-prompt-freeze'
    protocol = study.prepare_study(output, model='deepseek/offline-test',
        provider_slug='offline-test', model_evidence={'source': 'offline fixture; no inference'})
    protocol['prompt_sha256']['artifact'] = 'changed'
    (output/'protocol.json').write_text(json.dumps(protocol))
    with pytest.raises(ValueError, match='prompt profile differs'):
        study.verify_study(output)
    protocol['prompt_version'] = 'v1'
    (output/'protocol.json').write_text(json.dumps(protocol))
    with pytest.raises(ValueError, match='schema differs'):
        study.verify_study(output)


def test_transport_failure_freezes_partial_attempt_and_seals_panel(tmp_path):
    output = tmp_path/'partial-client-pilot'
    study.prepare_study(output, model='deepseek/offline-test',
                        provider_slug='offline-test',
                        model_evidence={'source': 'offline fixture; no inference'})
    def fail(envelope):
        raise RuntimeError('simulated budget or transport failure')
    frozen = study.execute_study(output, fail)
    assert not frozen['complete'] and frozen['failure']
    assert frozen['terminal_error']['active_phase'] == 'development'
    assert frozen['terminal_error']['partial_active_retained']
    active = frozen['active']['development']['batch-a7']
    assert active['model_call_attempts'] == 1
    assert active['turns'][0]['error'].startswith('adapter_failure:')
    assert json.loads((output/'frozen.json').read_text()) == frozen
    replay = study.replay_study(output)
    assert replay['status'] == 'partial_exact'
    assert replay['model_attempts_replayed'] == 1 and replay['network_calls'] == 0
    with pytest.raises(ValueError, match='incomplete'):
        study.open_panel(output)
