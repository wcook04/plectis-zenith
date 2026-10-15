"""Offline fixture tests: no real credentials, catalogue or inference."""
import json
from pathlib import Path
from zipfile import ZipFile

import pytest

from research import observation_repair_screen as screen
from research.observation_learning_study import UNKNOWN
from research.observation_world import WorldConfig, observe, task_sequences
from zenith.budgeted import OpenRouterBudgetedProvider
from zenith.providers import digest, write_json

LOOKUP = '''def investigate(context, acquire):
    for receipt in acquire("history"):
        if receipt["actions"] == context["actions"]:
            return {"value": receipt["observed"][context["goal"]], "unresolved": False}
    return {"value": None, "unresolved": True}
'''


def parent_fixture(tmp_path):
    parent = tmp_path/'parent'; parent.mkdir()
    streams, configs, frozen = [], {}, []
    for index in range(6):
        config = WorldConfig('fixture-' + str(index), 'upsert', True, 'main_total')
        actions = [{'op': 'put', 'key': 'a', 'value': 2}, {'op': 'put', 'key': 'a', 'value': 5}]
        history = [observe(config, actions)]
        configs[config.source_id] = vars(config)
        streams.append({'source_id': config.source_id, 'receipts': history,
                        'partitions': {name: task_sequences(12, name) for name in ('learn', 'challenge', 'eval')}})
        broken = {'source': UNKNOWN['source'] + '# fixture seed model\n', 'scope': 'fixture broken model', 'lesson': ''}
        frozen.append({'source_id': config.source_id, 'history': history,
                       'arms': {arm: {'champion': broken} for arm in ('incremental', 'archive', 'fresh')}})
    data = {'public': {'streams': streams}, 'private': {'configs': configs}}
    protocol = {'model': 'deepseek/fixture', 'dataset_sha256': digest(data)}
    for name, value in [('datasets', data), ('protocol', protocol), ('all-frozen', frozen),
        ('preparation-receipt', {'protocol_sha256': digest(protocol), 'dataset_sha256': digest(data)}),
        ('all-frozen-receipt', {'protocol_sha256': digest(protocol), 'frozen_sha256': digest(frozen)}),
        ('results', {'frozen_sha256': digest(frozen)})]:
        write_json(parent/f'{name}.json', value)
    return parent


class FixtureProvider:
    def __init__(self, invalid_first=False, fail=False):
        self.calls = []; self.invalid_first = invalid_first; self.fail = fail
    def ask_ai(self, prompt, config, cancel=None):
        self.calls.append((json.loads(prompt), config))
        if self.fail:
            raise RuntimeError('fixture transport failure')
        if self.invalid_first and len(self.calls) == 1:
            return '{"source": "import os", "scope": 7, "lesson": "bad schema"}'
        return json.dumps({'source': LOOKUP, 'scope': 'fixture only', 'lesson': 'fixture'})


def prepared(tmp_path, **kwargs):
    output = tmp_path/'screen'
    screen.prepare(output, parent_fixture(tmp_path), 'deepseek/fixture', 'fixture/fp8',
                   pool_size=3, confirmation_size=4, **kwargs)
    return output


def test_random_pool_is_legal_and_structurally_separate_not_value_renames():
    old = {screen.shape(actions) for name in ('learn', 'challenge', 'eval') for actions in task_sequences(17, name)}
    first = screen.action_pool(123, 32, old)
    second = screen.action_pool(124, 32, old | {screen.shape(a) for a in first})
    assert first == screen.action_pool(123, 32, old)
    assert len({screen.shape(a) for a in first + second}) == 64
    assert not old & {screen.shape(a) for a in first + second}
    config = WorldConfig('legal', 'ignore', False, 'main_direct')
    for actions in first + second:
        observe(config, actions)
    renamed = [{'op': 'put', 'key': 'renamed', 'value': 999}, {'op': 'put', 'key': 'renamed', 'value': 3}]
    assert screen.shape(renamed) == screen.shape([{'op': 'put', 'key': 'a', 'value': 1}, {'op': 'put', 'key': 'a', 'value': 2}])


def test_full_18_call_fixture_freezes_before_screen_and_keeps_confirmation_untouched(tmp_path, monkeypatch):
    output = prepared(tmp_path); provider = FixtureProvider(); audit = screen.audit; phases = []
    def observed_audit(protocol, dataset, frozen, partition='screen'):
        assert len(provider.calls) == 18
        assert (output/'all-frozen-receipt.json').exists()
        phases.append(partition)
        return audit(protocol, dataset, frozen, partition)
    monkeypatch.setattr(screen, 'audit', observed_audit)
    result = screen.run(output, provider=provider)
    assert phases == ['screen']
    assert set(result['aggregate']) == {'unchanged', *screen.ARMS}
    assert not (output/'confirmation.json').exists()
    assert not (output/'confirmation-selection.json').exists()
    for index in range(3):
        arm_calls = provider.calls[index * 6:(index + 1) * 6]
        assert len({digest(prompt['history']) for prompt, config in arm_calls}) == 1
        assert len({digest(prompt['diagnostic_evidence']) for prompt, config in arm_calls}) == 1
        for prompt, config in arm_calls:
            assert 'screen_actions' not in prompt and 'confirmation_actions' not in prompt
            assert config['reasoning_effort'] == 'none'
            assert config['meta']['session_id'] == output.name
    frozen = screen.read(output/'all-frozen.json')
    assert all(len(state['rounds']) == 2 for target in frozen for state in target['arms'].values())
    assert digest(result) == digest(screen.audit(*screen.load_final(output)))
    assert phases == ['screen', 'screen']


def test_invalid_schema_error_and_raw_source_reach_actual_next_request(tmp_path):
    output = prepared(tmp_path); provider = FixtureProvider(invalid_first=True)
    screen.run(output, provider=provider)
    delivered = provider.calls[1][0]['last_challenger']
    assert delivered['accepted'] is False
    assert delivered['response_error']['raw_content'] == '{"source": "import os", "scope": 7, "lesson": "bad schema"}'
    assert 'ValidationError' in delivered['response_error']['schema_error']
    assert all('ValidationError' in row['error'] for row in delivered['feedback'])
    assert len(provider.calls) == 18


def test_restart_never_falls_back_to_seed_after_rejected_own_output(tmp_path):
    output = prepared(tmp_path)
    class RejectRestart(FixtureProvider):
        def ask_ai(self, prompt, config, cancel=None):
            name = config['meta']['node_id']
            if '-restart-' in name:
                self.calls.append((json.loads(prompt), config))
                return json.dumps({'source': 'import os', 'scope': 'fixture invalid code', 'lesson': ''})
            return super().ask_ai(prompt, config, cancel)
    provider = RejectRestart(); screen.run(output, provider=provider)
    frozen = screen.read(output/'all-frozen.json')
    for target in frozen:
        state = target['arms']['restart']
        assert state['champion'] == UNKNOWN
        assert all(not r['accepted'] for r in state['rounds'])
    for prompt, config in provider.calls:
        if '-restart-' in config['meta']['node_id']:
            assert 'champion' not in prompt
    second = next(prompt for prompt, config in provider.calls if config['meta']['node_id'].endswith('restart-1'))
    assert second['last_challenger']['proposal']['source'] == 'import os'


def test_transport_failure_is_terminal_without_retry_or_screen(tmp_path):
    output = prepared(tmp_path); provider = FixtureProvider(fail=True)
    with pytest.raises(RuntimeError, match='transport failure'):
        screen.run(output, provider=provider)
    assert len(provider.calls) == 1
    assert screen.read(output/'failure.json')['phase'] == 'construction'
    assert not (output/'results.json').exists()
    with pytest.raises(ValueError, match='already started'):
        screen.run(output, provider=provider)
    assert len(provider.calls) == 1


def test_protocol_data_and_imported_dependencies_are_frozen_but_unrelated_sibling_is_not(tmp_path, monkeypatch):
    output = prepared(tmp_path); protocol = screen.read(output/'protocol.json')
    runtime = tmp_path/'runtime'
    with ZipFile(protocol['source']['path']) as archive:
        for name in protocol['runtime_dependencies']:
            path = runtime/name; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(archive.read(name))
    monkeypatch.setattr(screen, 'ROOT', runtime)
    sibling = runtime/'research/unrelated_in_progress.py'; sibling.write_text('unfinished sibling')
    screen.verify(output)
    (runtime/'research/observation_world.py').write_text('changed')
    with pytest.raises(ValueError, match='executing dependency changed'):
        screen.run(output, provider=FixtureProvider())
    assert not (output/'started.json').exists()


@pytest.mark.parametrize('file', ['protocol.json', 'datasets.json'])
def test_changed_inputs_reject_before_provider_admission(tmp_path, file):
    output = prepared(tmp_path); value = screen.read(output/file); value['tamper'] = True; write_json(output/file, value)
    provider = FixtureProvider()
    with pytest.raises(ValueError, match='frozen protocol or data'):
        screen.run(output, provider=provider)
    assert provider.calls == []


def test_confirmation_commits_one_choice_before_reading_any_confirmation_results(tmp_path, monkeypatch):
    output = prepared(tmp_path); screen.run(output, provider=FixtureProvider())
    audit = screen.audit
    def observe_choice(protocol, dataset, frozen, partition='screen'):
        assert partition == 'confirmation'
        assert screen.read(output/'confirmation-selection.json')['arm'] == 'contrastive'
        assert all(set(target['arms']) == {'contrastive'} for target in frozen)
        return audit(protocol, dataset, frozen, partition)
    monkeypatch.setattr(screen, 'audit', observe_choice)
    result = screen.confirm(output, 'contrastive')
    assert set(result['aggregate']) == {'unchanged', 'contrastive'}
    with pytest.raises(FileExistsError):
        screen.confirm(output, 'generic')


def test_frozen_program_tampering_cannot_reach_confirmation(tmp_path):
    output = prepared(tmp_path); screen.run(output, provider=FixtureProvider())
    frozen = screen.read(output/'all-frozen.json'); frozen[0]['arms']['generic']['champion']['source'] = UNKNOWN['source']
    write_json(output/'all-frozen.json', frozen)
    with pytest.raises(ValueError, match='frozen programs changed'):
        screen.confirm(output, 'generic')
    assert not (output/'confirmation-selection.json').exists()


def test_actual_budgeted_adapter_wiring_18_calls_route_reasoning_identity_and_ledger(tmp_path, monkeypatch):
    output = prepared(tmp_path); monkeypatch.setenv('OPENROUTER_API_KEY', 'test-only-not-real')
    monkeypatch.setattr('zenith.provider_policy._inference_root', lambda: tmp_path/'test-gate')
    model = 'deepseek/fixture'; sent = []
    row = {'id': model, 'pricing': {'prompt': '.0000001', 'completion': '.0000002'},
           'context_length': 1000000, 'architecture': {'input_modalities': ['text'], 'output_modalities': ['text']},
           'supported_parameters': ['max_tokens', 'temperature', 'response_format', 'structured_outputs', 'reasoning']}
    endpoint = {'model_id': model, 'tag': 'fixture/fp8', 'provider_name': 'Fixture', 'status': 0, 'context_length': 1000000,
        'max_completion_tokens': 8192, 'supported_parameters': row['supported_parameters'], 'pricing': row['pricing']}
    def get(url, *args):
        return {'data': {'id': model, 'endpoints': [endpoint]}} if url.endswith('/endpoints') else {'data': [row]}
    def post(url, headers, body, timeout):
        sent.append(body)
        return {'id': 'fixture-' + str(len(sent)), 'model': model, 'provider': 'Fixture',
            'usage': {'prompt_tokens': 2, 'completion_tokens': 1, 'cost': .0000004},
            'choices': [{'message': {'content': json.dumps({'source': LOOKUP, 'scope': 'fixture', 'lesson': ''})}}]}
    provider = OpenRouterBudgetedProvider(output, model, '1', 18, 8192, output/'budget',
        caller=post, catalogue_get=get, provider_slug='fixture/fp8', inference_mode='bounded')
    result = screen.run(output, provider=provider)
    assert result['calls'] == 18 and len(sent) == 18
    assert all(body['provider']['only'] == ['fixture/fp8'] and not body['provider']['allow_fallbacks'] for body in sent)
    assert all(body['reasoning'] == {'enabled': False} for body in sent)
    ledger = screen.read(output/'budget/budget.json')
    assert len(ledger['entries']) == 18
    assert all(entry['status'] != 'attempt_started' for entry in ledger['entries'].values())
    assert all(body['response_format']['json_schema']['schema'] == screen.PROGRAM_SCHEMA for body in sent)
