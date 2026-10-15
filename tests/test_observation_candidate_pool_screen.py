"""Offline native and real-adapter fixtures; no real inference or credentials."""
import copy
import hashlib
import json
import sqlite3
import sys
from pathlib import Path
from zipfile import ZipFile

import pytest

from research import observation_candidate_pool_screen as pool
from research import observation_repair_screen as repair
from research.observation_world import WorldConfig, observe
from zenith.budgeted import OpenRouterBudgetedProvider
from zenith.providers import digest, text_digest, write_json

LOOKUP = '''def investigate(context, acquire):
    for receipt in acquire("history"):
        if receipt["actions"] == context["actions"]:
            return {"value": receipt["observed"][context["goal"]], "unresolved": False}
    return {"value": None, "unresolved": True}
'''


def proposal(source):
    return {'source': source, 'scope': 'offline fixture', 'lesson': ''}


def parents(tmp_path):
    ancestor = tmp_path/'v5'; ancestor.mkdir()
    action = [{'op': 'put', 'key': 'a', 'value': 2}, {'op': 'put', 'key': 'a', 'value': 5}]
    extra = [{'op': 'put', 'key': 'a', 'value': 2}, {'op': 'begin'}, {'op': 'delete', 'key': 'a'}, {'op': 'rollback'}]
    streams, ancestor_frozen, targets = [], [], []
    for index in range(3):
        config = WorldConfig('fixture-' + str(index), 'upsert', True, 'main_total')
        history = [observe(config, action), observe(config, [])]
        streams.append({'source_id': config.source_id, 'receipts': history,
            'partitions': {'learn': [action], 'challenge': [[]], 'eval': [action]}})
        ancestor_frozen.append({'history': history + [observe(config, extra)]})
        targets.append({'id': f'world-{index:02d}-failure', 'source_id': config.source_id,
            'config': vars(config), 'history': history, 'starting_program': dict(repair.UNKNOWN),
            'parent_program_sha256': digest(repair.UNKNOWN),
            'diagnostic': {'minimum': {'actions': []}, 'prefixes': [], 'reduction_trials': [{'actions': action}]}})
    ancestor_data = {'public': {'streams': streams}}
    ancestor_protocol = {'dataset_sha256': digest(ancestor_data)}
    for name, value in [('datasets', ancestor_data), ('protocol', ancestor_protocol), ('all-frozen', ancestor_frozen),
        ('preparation-receipt', {'protocol_sha256': digest(ancestor_protocol), 'dataset_sha256': digest(ancestor_data)}),
        ('all-frozen-receipt', {'protocol_sha256': digest(ancestor_protocol), 'frozen_sha256': digest(ancestor_frozen)}),
        ('results', {'frozen_sha256': digest(ancestor_frozen)})]:
        write_json(ancestor/f'{name}.json', value)
    old_screen = repair.action_pool(111, 2, {repair.shape(action), repair.shape([]), repair.shape(extra)})
    old_confirmation = repair.action_pool(112, 2, {repair.shape(a) for a in [action, [], extra, *old_screen]})
    data = {'targets': targets, 'screen_actions': old_screen, 'confirmation_actions': old_confirmation}
    paths = []
    for label in pool.MODELS:
        path = tmp_path/label; path.mkdir(); paths.append(path)
        dependencies = repair.dependencies()
        protocol = {'schema': repair.VERSION, 'parent': str(ancestor),
            'parent_protocol_sha256': digest(ancestor_protocol), 'parent_frozen_sha256': digest(ancestor_frozen),
            'model': label + '/fixture', 'provider_slug': 'fixture/' + label,
            'source_author_model': 'deepseek/fixture', 'reasoning_effort': 'none', 'max_output_tokens': 8192,
            'runtime_dependencies': dependencies, 'source': repair.archive(path, dependencies),
            'python_version': sys.version, 'sqlite_version': sqlite3.sqlite_version, 'dataset_sha256': digest(data)}
        frozen = []
        for index, target in enumerate(targets):
            pairs = repair.development(WorldConfig(**target['config']), target['history'])
            state = {'champion': dict(repair.UNKNOWN), 'rounds': []}
            for step in range(2):
                node = f'{target["id"]}-restart-{step}'
                prompt = repair.prompt_for('restart', target, state, pairs, repair.score(state['champion']['source'], pairs))
                write_json(path/'prompts'/f'{node}.json', {'system': repair.LANGUAGE, 'prompt': prompt, 'schema': repair.PROGRAM_SCHEMA})
                source = 'import os' if step == 0 and index == 0 else LOOKUP + '# ' + label + '-old-' + str(step)
                raw = json.dumps(proposal(source))
                pool.transition(state, raw, pairs)
                write_json(path/'responses'/f'{node}-raw.json', {'content': raw})
                write_json(path/'handoff/api_calls/openrouter_budgeted'/f'{node}.json', {
                    'node_id': node, 'run_id': path.name, 'call_id': node + label, 'cost': '0.00001',
                    'requested_model': protocol['model'], 'requested_provider_slug': protocol['provider_slug'],
                    'prompt_sha256': text_digest(json.dumps(prompt, ensure_ascii=False)),
                    'response_sha256': text_digest(raw), 'provider_receipt': {'response_text': raw}})
            frozen.append({'id': target['id'], 'arms': {'restart': state}})
        for name, value in [('datasets', data), ('protocol', protocol), ('all-frozen', frozen),
            ('preparation-receipt', {'protocol_sha256': digest(protocol), 'dataset_sha256': digest(data)}),
            ('all-frozen-receipt', {'protocol_sha256': digest(protocol), 'frozen_sha256': digest(frozen)}),
            ('results', {'frozen_sha256': digest(frozen), 'cost': {'total_reported_cost_usd': '0.001'}})]:
            write_json(path/f'{name}.json', value)
    return paths, extra


def prepared(tmp_path):
    paths, extra = parents(tmp_path)
    output = tmp_path/'pool'
    pool.prepare(output, *paths, pool_size=2, confirmation_size=3)
    return output, extra


class FixtureProvider:
    def __init__(self, label, invalid_first=False, fail=False):
        self.label = label; self.calls = []; self.invalid_first = invalid_first; self.fail = fail
    def ask_ai(self, prompt, config, cancel=None):
        self.calls.append((json.loads(prompt), config))
        if self.fail: raise RuntimeError('test transport failure')
        if self.invalid_first and len(self.calls) == 1: return '{"source": "import os", "scope": 7}'
        return json.dumps(proposal(LOOKUP + '# ' + self.label + '-new-' + str(len(self.calls))))


def raw_map(output):
    return {p.name.removesuffix('-raw.json'): repair.read(p)['content'] for p in (output/'responses').glob('*-raw.json')}


def test_preparation_retains_every_reused_slot_and_excludes_actual_v5_probes(tmp_path):
    output, extra = prepared(tmp_path); protocol, data = repair.verify(output)
    assert len(data['reused']) == 12
    assert any(r['entry']['candidate_summary']['errors'] for r in data['reused'])
    excluded = {tuple(tuple(a) for a in s) for s in data['excluded_structures']}
    assert repair.shape(extra) in excluded
    assert protocol['accounting'] == {'new_calls': 12, 'reused_unique_calls': 12,
        'pool_slot_references': 36, 'previous_parent_campaign_calls': 36}
    new = [repair.shape(a) for key in ('screen_actions', 'confirmation_actions') for a in data[key]]
    assert len(new) == len(set(new)) and not set(new) & excluded
    assert len(data['ancestor']['frozen_sha256']) == 64
    assert all(json.loads(r['raw_content']) == r['entry']['proposal'] for r in data['reused'])


def test_full_twelve_calls_preserve_own_feedback_freeze_before_screen_and_exact_replay(tmp_path, monkeypatch):
    output, _ = prepared(tmp_path)
    providers = {label: FixtureProvider(label, invalid_first=True) for label in pool.MODELS}
    original_audit = pool.audit; phases = []
    def audit(protocol, data, frozen, partition='screen'):
        assert sum(len(p.calls) for p in providers.values()) == 12
        assert (output/'all-frozen-receipt.json').exists(); phases.append(partition)
        return original_audit(protocol, data, frozen, partition)
    monkeypatch.setattr(pool, 'audit', audit)
    result = pool.run(output, providers=providers)
    assert phases == ['screen'] and not (output/'confirmation-selection.json').exists()
    protocol, data, frozen = repair.load_final(output)
    prompts = {p.stem: repair.read(p) for p in (output/'prompts').glob('*.json')}
    replay = pool.replay_records(protocol, data, frozen, raw_map(output), prompts)
    assert replay['exact_development_replay'] and replay['construction_checks'] > 0
    assert replay['construction_prompt_checks'] == 12
    assert digest(result) == digest(pool.audit(protocol, data, frozen))
    for label, provider in providers.items():
        assert len(provider.calls) == 6
        other = next(m for m in pool.MODELS if m != label)
        for prompt, config in provider.calls:
            assert other + '-old-' not in json.dumps(prompt) and other + '-new-' not in json.dumps(prompt)
            assert 'screen_actions' not in prompt and 'confirmation_actions' not in prompt
            assert config['reasoning_effort'] == 'none'
        delivered = provider.calls[1][0]['last_challenger']
        assert not delivered['accepted'] and delivered['response_error']['raw_content'].endswith('7}')
        assert 'ValidationError' in delivered['feedback'][0]['error']
    for target in frozen:
        assert all(len(state['rounds']) == 4 for state in target['continuations'].values())
        assert all(len(state['slots']) == 4 for state in target['arms'].values())
        assert {s['origin'] for s in target['arms']['mixed']['slots']} == {'reused'}
    tampered = raw_map(output); tampered[next(iter(tampered))] = json.dumps(proposal(repair.UNKNOWN['source']))
    with pytest.raises(ValueError, match='replay differs'): pool.replay_records(protocol, data, frozen, tampered)
    tampered_prompts = copy.deepcopy(prompts)
    node = data['targets'][0]['id'] + '-deepseek-3'
    assert tampered_prompts[node]['prompt']['last_challenger']['response_error'] is not None
    tampered_prompts[node]['prompt']['last_challenger']['response_error'] = None
    with pytest.raises(ValueError, match='own feedback differs'):
        pool.replay_records(protocol, data, frozen, raw_map(output), tampered_prompts)


def test_maximum_accuracy_selection_is_order_independent_with_source_hash_ties(monkeypatch):
    def score(source, pairs):
        correct, errors = {'a': (2, 0), 'b': (2, 0), 'c': (1, 0), 'bad': (3, 1)}[source]
        return {'correct': correct, 'total': 3, 'errors': errors, 'unsupported': 0,
                'rows': [{'correct': True, 'error': None} for _ in range(3)]}
    monkeypatch.setattr(repair, 'score', score)
    slots = [{'slot_id': model + str(i), 'proposal': proposal(source)}
        for i, (model, source) in enumerate([('qwen', 'a'), ('deepseek', 'b'), ('deepseek', 'c'), ('qwen', 'bad')])]
    winner = min(('a', 'b'), key=lambda s: hashlib.sha256(s.encode()).hexdigest())
    assert pool.select(slots, [])['champion']['source'] == winner
    assert pool.select(list(reversed(slots)), [])['champion']['source'] == winner
    invalid = {'slot_id': 'bad-schema', 'proposal': proposal('a'), 'response_error': {'schema_error': 'fixture invalid'}}
    selected = pool.select([invalid, slots[2]], [])
    assert selected['champion']['source'] == 'c'
    assert selected['slots'][0]['development']['errors'] == 3


def test_confirmation_choice_is_exclusive_and_bound_before_evaluation(tmp_path, monkeypatch):
    output, _ = prepared(tmp_path); result = pool.run(output, providers={m: FixtureProvider(m) for m in pool.MODELS})
    primary = result['primary_pool']; other = next(arm for arm in pool.ARMS if arm != primary)
    with pytest.raises(ValueError, match='screening rule'): pool.confirm(output, other)
    assert not (output/'confirmation-selection.json').exists()
    original = pool.audit
    def audit(protocol, data, frozen, partition='screen'):
        assert repair.read(output/'confirmation-selection.json')['arm'] == primary
        assert all(set(record['arms']) == set(pool.ARMS) for record in frozen)
        return original(protocol, data, frozen, partition)
    monkeypatch.setattr(pool, 'audit', audit)
    confirmed = pool.confirm(output, primary)
    assert set(confirmed['aggregate']) == {'unchanged', *pool.ARMS}
    protocol, data, frozen = repair.load_final(output)
    assert digest(pool.replay_confirmation(protocol, data, frozen, confirmed['selection'], confirmed)) == digest(confirmed)
    with pytest.raises(FileExistsError): pool.confirm(output, primary)


def test_transport_failure_stops_without_retry_or_protected_evaluation(tmp_path):
    output, _ = prepared(tmp_path); providers = {m: FixtureProvider(m, fail=True) for m in pool.MODELS}
    with pytest.raises(RuntimeError, match='test transport'): pool.run(output, providers=providers)
    assert sum(len(p.calls) for p in providers.values()) == 1
    assert repair.read(output/'failure.json')['automatic_retry'] is False
    assert not (output/'all-frozen.json').exists() and not (output/'results.json').exists()
    with pytest.raises(ValueError, match='already started'): pool.run(output, providers=providers)


def test_ancestor_custody_tampering_rejects_preparation(tmp_path):
    paths, _ = parents(tmp_path); ancestor = tmp_path/'v5'
    frozen = repair.read(ancestor/'all-frozen.json'); frozen[0]['history'] = []; write_json(ancestor/'all-frozen.json', frozen)
    with pytest.raises(ValueError, match='ancestor custody'): pool.prepare(tmp_path/'pool', *paths)


def test_own_import_is_frozen_before_provider_admission(tmp_path, monkeypatch):
    output, _ = prepared(tmp_path); protocol = repair.read(output/'protocol.json')
    runtime = tmp_path/'runtime'
    with ZipFile(protocol['source']['path']) as archive:
        for name in protocol['runtime_dependencies']:
            path = runtime/name; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(archive.read(name))
    monkeypatch.setattr(repair, 'ROOT', runtime)
    (runtime/'research/observation_candidate_pool_screen.py').write_text('changed')
    providers = {m: FixtureProvider(m) for m in pool.MODELS}
    with pytest.raises(ValueError, match='executing dependency changed'): pool.run(output, providers=providers)
    assert not (output/'started.json').exists() and all(not p.calls for p in providers.values())


def test_actual_budgeted_adapter_twelve_calls_share_ledger_pinned_routes_and_identity(tmp_path, monkeypatch):
    output, _ = prepared(tmp_path); monkeypatch.setenv('OPENROUTER_API_KEY', 'test-only')
    monkeypatch.setattr('zenith.provider_policy._inference_root', lambda: tmp_path/'test-gate')
    models = repair.read(output/'protocol.json')['models']; sent = []
    def row(label):
        return {'id': models[label]['model'], 'pricing': {'prompt': '.0000001', 'completion': '.0000002'},
            'context_length': 1000000, 'architecture': {'input_modalities': ['text'], 'output_modalities': ['text']},
            'supported_parameters': ['max_tokens', 'temperature', 'response_format', 'structured_outputs', 'reasoning']}
    def get(url, *args):
        if url.endswith('/endpoints'):
            label = 'qwen' if 'qwen' in url else 'deepseek'; model = row(label)
            return {'data': {'id': model['id'], 'endpoints': [{'model_id': model['id'], 'tag': models[label]['provider_slug'],
                'provider_name': 'Fixture', 'status': 0, 'context_length': 1000000, 'max_completion_tokens': 8192,
                'supported_parameters': model['supported_parameters'], 'pricing': model['pricing']}]}}
        return {'data': [row(m) for m in pool.MODELS]}
    def post(url, headers, body, timeout):
        sent.append(body)
        return {'id': 'fixture-' + str(len(sent)), 'model': body['model'], 'provider': 'Fixture',
            'usage': {'prompt_tokens': 2, 'completion_tokens': 1, 'cost': .0000004},
            'choices': [{'message': {'content': json.dumps(proposal(LOOKUP))}}]}
    providers = {label: OpenRouterBudgetedProvider(output/(output.name+'-'+label), model['model'],
        '0.50', 12, 8192, output/'budget', provider_slug=model['provider_slug'], inference_mode='bounded',
        caller=post, catalogue_get=get) for label, model in models.items()}
    result = pool.run(output, providers=providers)
    assert result['calls'] == len(sent) == 12
    assert all(body['reasoning'] == {'enabled': False} and not body['provider']['allow_fallbacks'] for body in sent)
    assert {tuple(body['provider']['only']) for body in sent} == {('fixture/deepseek',), ('fixture/qwen',)}
    ledger = repair.read(output/'budget/budget.json')
    assert len(ledger['entries']) == 12 and all(e['status'] != 'attempt_started' for e in ledger['entries'].values())
    assert {e['run_id'] for e in ledger['entries'].values()} == {output.name + '-' + m for m in pool.MODELS}
    assert pool.replay_records(*repair.load_final(output), raw_map(output))['exact_development_replay']


def test_uniform_primary_ranks_correct_then_errors_then_program_hash():
    frozen = [{'arms': {arm: {'champion': proposal(arm)} for arm in pool.ARMS}} for _ in range(3)]
    result = {'aggregate': {arm: {'correct': 4, 'errors': 0} for arm in pool.ARMS}}
    tied = min(pool.ARMS, key=lambda a: digest([text_digest(a)] * 3))
    assert pool.primary_pool(frozen, result) == tied
    result['aggregate'][tied]['errors'] = 1
    assert pool.primary_pool(frozen, result) != tied
    result['aggregate'][tied]['correct'] = 5
    assert pool.primary_pool(frozen, result) == tied
