"""Native transaction semantics, executable reuse, isolation and real adapter wiring."""
import json
from pathlib import Path

import pytest

from research import observation_composition_screen as screen
from research.observation_world import WorldConfig, _run_native

PRIMITIVE = '''def transition(state, action, context, acquire):
    if state is None:
        state = {"actions": []}
    state["actions"].append(action)
    return state

def readout(state, context, acquire):
    if state is None:
        state = {"actions": []}
    for receipt in acquire("history"):
        if receipt["actions"] == state["actions"]:
            return {"value": receipt["observed"][context["goal"]], "unresolved": False}
    return {"value": None, "unresolved": True}

def investigate(context, acquire):
    state = None
    for action in context["actions"]:
        state = transition(state, action, context, acquire)
    return readout(state, context, acquire)
'''


def program(source=PRIMITIVE):
    return {'source': source, 'scope': 'Fixture observed lookup, not learned research.', 'lesson': 'fixture'}


def cfg(trigger=False, counter='main_total'):
    return WorldConfig('test-native', 'upsert', trigger, counter)


def measured(actions, config=None):
    return screen.observe(config or cfg(), actions)['observed']


def test_outer_release_commits_but_inner_release_inside_begin_does_not():
    actions = [screen.sp('savepoint', 's0'), screen.put('a', 7), screen.sp('release', 's0')]
    assert measured(actions) == {'channel': 1, 'committed_count': 1, 'committed_sum': 7}
    explicit = [{'op': 'begin'}, *actions]
    assert measured(explicit) == {'channel': 1, 'committed_count': 0, 'committed_sum': 0}
    assert measured([*explicit, {'op': 'commit'}])['committed_sum'] == 7


def test_rollback_to_keeps_target_and_discards_inner_points_without_undoing_counter():
    prefix = [screen.sp('savepoint', 's0'), screen.put('a', 7), screen.sp('savepoint', 's1'),
              screen.put('b', 11), screen.sp('rollback_to', 's0')]
    actions = [*prefix, screen.put('c', 13), screen.sp('rollback_to', 's0'),
               screen.put('d', 17), screen.sp('release', 's0')]
    assert measured(actions, cfg(True)) == {'channel': 8, 'committed_count': 1, 'committed_sum': 17}
    with pytest.raises(ValueError, match='target not active'):
        screen.normalize([*prefix, screen.sp('release', 's1')])


def test_open_nested_scope_reader_remains_independently_committed():
    prefix = [screen.put('committed', 19), screen.sp('savepoint', 's0'), screen.put('tentative', 23),
              screen.sp('savepoint', 's1'), {'op': 'delete', 'key': 'committed'}]
    assert measured(prefix)['committed_sum'] == 19
    assert measured([*prefix, screen.sp('release', 's0')])['committed_sum'] == 23


@pytest.mark.parametrize('actions', [
    [{'op': 'savepoint', 'name': 's0; DROP TABLE items'}],
    [{'op': 'savepoint', 'name': '"s0"'}],
    [{'op': 'SAVEPOINT s0'}],
    [screen.sp('savepoint', 's0'), screen.sp('savepoint', 's0')],
    [screen.sp('savepoint', 's0'), {'op': 'begin'}],
    [screen.sp('savepoint', 's0'), screen.put('x', 2, 'other')],
    [{'op': 'release', 'name': 's0', 'value': 2}],
])
def test_sql_names_fields_nesting_and_connections_are_validated_before_native_run(actions, monkeypatch):
    def forbidden(*args):
        raise AssertionError('native runner must not be called')
    monkeypatch.setattr(screen, '_run_native', forbidden)
    with pytest.raises(ValueError):
        screen.observe(cfg(), actions)


def test_ordinary_sequences_share_exact_existing_native_instrument():
    for conflict in ('ignore', 'replace', 'upsert'):
        for trigger in (False, True):
            for counter in ('main_direct', 'main_total', 'all_total'):
                config = WorldConfig('same-native', conflict, trigger, counter)
                actions = [screen.put('x', 3), {'op': 'begin'}, screen.put('x', 7), {'op': 'rollback'},
                           screen.put('y', 11, 'other')]
                assert tuple(screen.observe(config, actions)['observed'].values()) == _run_native(config, actions)


def caller(identity):
    return f'''def investigate(context, acquire):
    state = None
    for action in context["actions"]:
        state = unit{identity[:12]}transition(state, action, context, acquire)
    return unit{identity[:12]}readout(state, context, acquire)
'''


def test_linked_learned_state_outputs_are_consumed_and_flat_execution_is_identical():
    store = screen.NodeStore()
    identity = store.add(program())
    root = program(caller(identity))
    receipts = [screen.observe(cfg(), [screen.put('a', 5)])]
    pairs = screen.panels(cfg(), receipts, nodes=store.nodes)
    linked = store.link(root, [identity])
    graph = screen.node_score(store, root, [identity], pairs)
    flat = screen.node_score(store, program(linked), [], pairs)
    assert graph == flat and graph['correct'] == graph['total'] == 3
    assert screen.dependency_usage(graph)[identity] == {'transition_initialization': 3, 'readout': 3}
    # Semantics are still the supplied model/fixture source, never host-supplied.
    assert store.nodes[identity]['program']['source'] == PRIMITIVE
    with pytest.raises(ValueError, match='missing'):
        store.link(root, ['f' * 64])


def test_primitive_exports_are_qualified_independently_of_full_predictor():
    mismatched = PRIMITIVE.replace('return {"value": receipt["observed"][context["goal"]], "unresolved": False}',
                                  'return {"value": 99, "unresolved": False}', 1)
    # A fake investigate can succeed while state exports are incorrect.
    mismatched = mismatched[:mismatched.index('def investigate')] + '''def investigate(context, acquire):
    receipt = acquire("history")[0]
    return {"value": receipt["observed"][context["goal"]], "unresolved": False}
'''
    pairs = screen.panels(cfg(), [screen.observe(cfg(), [screen.put('a', 5)])])
    assert screen.score(mismatched, pairs)['correct'] == 3
    assert screen.score(screen.primitive_driver(mismatched), pairs)['correct'] == 0
    with pytest.raises(ValueError, match='positional'):
        screen.exports(PRIMITIVE.replace('transition(state, action, context, acquire)', 'transition(state)'))


def test_explicit_zero_action_driver_contract_exposes_readout_none_failure():
    source = PRIMITIVE.replace('''def readout(state, context, acquire):
    if state is None:
        state = {"actions": []}
''', '''def readout(state, context, acquire):
''')
    source = source[:source.index('def investigate')] + '''def investigate(context, acquire):
    for receipt in acquire("history"):
        if receipt["actions"] == context["actions"]:
            return {"value": receipt["observed"][context["goal"]], "unresolved": False}
    return {"value": None, "unresolved": True}
'''
    pairs = screen.panels(cfg(), [screen.observe(cfg(), [])])
    assert screen.score(source, pairs)['correct'] == 3
    exported = screen.score(screen.primitive_driver(source), pairs)
    assert exported['errors'] == 3 and exported['correct'] == 0
    assert 'readout(None,' in screen.PRIMITIVE_INTERFACE
    assert 'context is never None' in screen.PRIMITIVE_INTERFACE


def test_invocation_is_not_effective_dependence():
    store = screen.NodeStore()
    identity = store.add(program())
    cosmetic = program(f'''def investigate(context, acquire):
    ignored = unit{identity[:12]}readout(None, context, acquire)
    return {{"value": 0, "unresolved": False}}
''')
    pairs = screen.panels(cfg(), [screen.observe(cfg(), [])], nodes=store.nodes)
    before = screen.node_score(store, cosmetic, [identity], pairs)
    assert screen.dependency_usage(before)[identity]['readout'] == 3
    store.nodes[identity]['program'] = program('''def transition(state, action, context, acquire):
    return state
def readout(state, context, acquire):
    return {"value": None, "unresolved": True}
def investigate(context, acquire):
    return {"value": None, "unresolved": True}
''')
    after = screen.node_score(store, cosmetic, [identity], pairs)
    assert [r['answer'] for r in before['rows']] == [r['answer'] for r in after['rows']]


def test_readout_only_ablation_preserves_state_interface_but_can_remove_correct_answers():
    store = screen.NodeStore()
    identity = store.add(program())
    pairs = screen.panels(cfg(), [screen.observe(cfg(), [screen.put('a', 5)])], nodes=store.nodes)
    root = program(caller(identity))
    before = screen.node_score(store, root, [identity], pairs)
    changed = PRIMITIVE.replace('return {"value": receipt["observed"][context["goal"]], "unresolved": False}',
                               'return {"value": None, "unresolved": True}')
    store.nodes[identity]['program'] = program(changed)
    after = screen.node_score(store, root, [identity], pairs)
    assert before['correct'] == 3 and after['correct'] == 0
    assert after['errors'] == 0
    assert screen.dependency_usage(before) == screen.dependency_usage(after)


def test_store_linker_restrictions_are_scored_before_adoption_can_accept_a_tie():
    store = screen.NodeStore()
    pairs = screen.panels(cfg(), [screen.observe(cfg(), [])])
    source = '''def helper(value):
    return value
def investigate(context, acquire):
    helper = 0
    return {"value": 0, "unresolved": False}
'''
    old = screen.node_score(store, screen.UNKNOWN, [], pairs)
    candidate = screen.node_score(store, program(source), [], pairs)
    assert old['correct'] == candidate['correct'] == 0
    assert candidate['errors'] == 3
    assert screen.adoption(old, candidate)[0] is False
    assert all('shadowed' in row['error'] for row in candidate['rows'])


class FixtureProvider:
    def __init__(self, fail_at=None):
        self.calls, self.fail_at = [], fail_at

    def ask_ai(self, prompt, config):
        prompt = json.loads(prompt)
        self.calls.append((prompt, config))
        if len(self.calls) == self.fail_at:
            raise RuntimeError('fixture terminal failure')
        if 'primitive-' in config['meta']['node_id'] or 'fresh-no-library' in config['meta']['node_id']:
            answer = {**program(), 'dependencies': []}
        else:
            identity = prompt['library'][0]['id']
            answer = {**program(caller(identity)), 'dependencies': [identity]}
        return json.dumps(answer)


def test_36_calls_equal_primary_allowances_blind_future_and_early_final_history(tmp_path):
    output = tmp_path/'screen'
    screen.prepare(output, 'fixture', 'fixture', seed=20261107)
    provider = FixtureProvider()
    result = screen.run(output, provider=provider)
    assert len(provider.calls) == 36
    assert len(result['worlds']) == 3
    assert result['aggregate']['graph'] == result['aggregate']['flat']
    for arm in ('graph', 'flat', 'fresh'):
        assert sum(f'-{arm}-' in c['meta']['node_id'] and 'no-library' not in c['meta']['node_id']
                   for p, c in provider.calls) == 9
    for prompt, config in provider.calls:
        assert 'protected-' not in json.dumps(prompt)
        assert 'confirmation-' not in json.dumps(prompt)
        assert not {'private', 'configs', 'eval', 'seed'} & set(prompt)
        assert config['reasoning_effort'] == 'none'
    receipt = json.loads((output/'all-frozen-receipt.json').read_text())
    assert receipt['construction_complete'] and receipt['protected_audit_started'] is False
    assert result['aggregate']['freeze_and_grow'] == result['aggregate']['graph']
    frozen = json.loads((output/'all-frozen.json').read_text())
    for record in frozen:
        assert record['arms']['graph']['champion']['dependencies']
        assert not record['arms']['flat']['champion']['dependencies']
    protocol, data = screen.verify_frozen(output)
    raw = {p.name.removesuffix('-raw.json'): json.loads(p.read_text())['content']
           for p in (output/'responses').glob('*-raw.json')}
    checked = screen.replay_records(protocol, data, frozen, raw)
    assert checked == {'construction_checks': 66, 'inference_calls': 0}
    original_audit = screen.audit(protocol, data, frozen)
    assert original_audit == {k: v for k, v in result.items() if k not in ('cost', 'calls')}
    confirmed = screen.confirm(output, 'flat')
    selection = json.loads((output/'confirmation-selection.json').read_text())
    assert set(confirmed['aggregate']) == {'flat'}
    assert screen.replay_confirmation(protocol, data, frozen, selection, confirmed)['exact_replay']
    assert len(provider.calls) == 36  # Confirmation and replay are inference-free.
    with pytest.raises(FileExistsError):
        screen.confirm(output, 'graph')
    with pytest.raises(ValueError, match='prior attempts'):
        screen.run(output, provider=provider)


def test_failure_preserves_raw_invalid_primitive_and_stops_without_repair(tmp_path):
    class Broken(FixtureProvider):
        def ask_ai(self, prompt, config):
            super().ask_ai(prompt, config)
            return '{invalid'
    output = tmp_path/'broken'
    screen.prepare(output, 'fixture', 'fixture')
    provider = Broken()
    with pytest.raises(RuntimeError, match='no executable composable primitive'):
        screen.run(output, provider=provider)
    assert len(provider.calls) == 2
    assert (output/'responses/world-00-primitive-0-raw.json').exists()
    delivered = provider.calls[1][0]['prior_trials'][0]
    assert delivered['response_error']['raw_content'] == '{invalid'
    assert delivered['interface_error']
    assert not json.loads((output/'failure.json').read_text())['protected_evaluation_performed']
    assert not (output/'results.json').exists()


def test_valid_abstaining_exports_do_not_claim_a_learned_primitive(tmp_path):
    class Abstaining(FixtureProvider):
        def ask_ai(self, prompt, config):
            super().ask_ai(prompt, config)
            source = '''def transition(state, action, context, acquire):
    return state
def readout(state, context, acquire):
    return {"value": None, "unresolved": True}
def investigate(context, acquire):
    return {"value": None, "unresolved": True}
'''
            return json.dumps({**program(source), 'dependencies': []})
    output = tmp_path/'abstaining'
    screen.prepare(output, 'fixture', 'fixture')
    provider = Abstaining()
    with pytest.raises(RuntimeError, match='no executable composable primitive'):
        screen.run(output, provider=provider)
    record = json.loads((output/'world-00-partial.json').read_text())
    assert record['primitive_ids'] == []
    assert all('no correct observed computation' in row['interface_error'] for row in record['primitive_rounds'])
    assert len(provider.calls) == 2


def test_confirmation_has_new_action_structures_and_exclusive_selection_precedes_queries(tmp_path, monkeypatch):
    def shape(actions):
        return tuple((a['op'], a.get('connection', 'main'), a.get('name')) for a in actions)
    initial = screen.protected_sequences(11)
    confirmation = screen.protected_sequences(12, 'confirmation')
    assert not {shape(a) for a in initial} & {shape(a) for a in confirmation}
    for actions in confirmation:
        screen.normalize(actions)
        screen.observe(cfg(), actions)
    output = tmp_path/'selected'
    output.mkdir()
    protocol = {'confirmation_boundary': 'fixture'}
    data = {'public': {'streams': [{'confirmation': confirmation}]}}
    records = []
    monkeypatch.setattr(screen, 'verify_frozen', lambda directory: (protocol, data))
    (output/'all-frozen.json').write_text('[]')
    (output/'results.json').write_text(json.dumps({'frozen_sha256': screen.digest(records),
                                                  'protocol_sha256': screen.digest(protocol)}))
    def checked(p, d, f, selection):
        assert json.loads((output/'confirmation-selection.json').read_text()) == selection
        return {'aggregate': {'graph': {}}}
    monkeypatch.setattr(screen, 'confirmation_result', checked)
    screen.confirm(output, 'graph')


def test_frozen_dataset_change_is_rejected_before_calls(tmp_path):
    output = tmp_path/'tamper'
    screen.prepare(output, 'fixture', 'fixture')
    path = output/'datasets.json'
    data = json.loads(path.read_text())
    data['public']['documentation'] += ' changed'
    path.write_text(json.dumps(data))
    provider = FixtureProvider()
    with pytest.raises(ValueError, match='dataset changed'):
        screen.run(output, provider=provider)
    assert provider.calls == []


def test_real_provider_identity_schema_reasoning_and_cost_ledger(tmp_path, monkeypatch):
    from zenith.budgeted import OpenRouterBudgetedProvider
    monkeypatch.setenv('OPENROUTER_API_KEY', 'fixture-only-not-a-real-key')
    monkeypatch.setattr('zenith.provider_policy._inference_root', lambda: tmp_path/'test-gate')
    model = 'deepseek/fixture'
    params = ['max_tokens', 'temperature', 'response_format', 'structured_outputs', 'reasoning']
    prices = {'prompt': '.0000001', 'completion': '.0000001'}
    row = {'id': model, 'context_length': 500000, 'pricing': prices,
           'architecture': {'input_modalities': ['text'], 'output_modalities': ['text']},
           'supported_parameters': params}
    endpoint = {'model_id': model, 'tag': 'fixture/fp8', 'provider_name': 'Fixture', 'status': 0,
                'context_length': 500000, 'max_completion_tokens': 8192,
                'supported_parameters': params, 'pricing': prices}
    posts = []
    def get(url, *args):
        return {'data': {'id': model, 'endpoints': [endpoint]}} if url.endswith('/endpoints') else {'data': [row]}
    def post(url, headers, payload, timeout):
        assert payload['response_format']['json_schema']['schema'] == screen.TRANSPORT_SCHEMA
        assert 'uniqueItems' not in payload['response_format']['json_schema']['schema']['properties']['dependencies']
        posts.append(payload)
        prompt = json.loads(payload['messages'][-1]['content'])
        primitive = prompt.get('interface', '').startswith('Additionally')
        if primitive or not prompt.get('library'):
            answer = {**program(), 'dependencies': []}
        else:
            identity = prompt['library'][0]['id']
            answer = {**program(caller(identity)), 'dependencies': [identity]}
        return {'model': model, 'provider': 'Fixture',
                'usage': {'prompt_tokens': 10, 'completion_tokens': 10, 'cost': .000002},
                'choices': [{'message': {'content': json.dumps(answer)}}]}
    def factory(*args, **kwargs):
        return OpenRouterBudgetedProvider(*args, **kwargs, caller=post, catalogue_get=get)
    monkeypatch.setattr(screen, 'OpenRouterBudgetedProvider', factory)
    output = tmp_path/'real-adapter'
    env = tmp_path/'empty.env'
    env.write_text('')
    protocol = screen.prepare(output, model, 'fixture/fp8', reasoning_effort='low', primitive_proposals=4, worlds=1)
    assert protocol['primitive_proposals'] == 4 and protocol['worlds'] == 1 and protocol['max_calls'] == 14
    assert protocol['host_schema_sha256'] == screen.digest(screen.SCHEMA)
    assert protocol['transport_schema_sha256'] == screen.digest(screen.TRANSPORT_SCHEMA)
    result = screen.run(output, env_file=env)
    ledger = json.loads((output/'budget/budget.json').read_text())
    assert len(posts) == len(ledger['entries']) == result['calls'] == 14
    frozen = json.loads((output/'all-frozen.json').read_text())
    assert all(len(record['primitive_rounds']) == 4 for record in frozen)
    assert len(frozen) == 1
    assert all('readout(None,' in prompt['interface'] for prompt, config in
        [(json.loads(p['messages'][-1]['content']), p) for p in posts] if 'prior_trials' in prompt and 'library' not in prompt)
    assert {entry['run_id'] for entry in ledger['entries'].values()} == {'provider'}
    assert all(entry['status'] == 'response_supplied' for entry in ledger['entries'].values())
    assert all(payload['reasoning']['effort'] == 'low' for payload in posts)
    assert result['cost']['total_reported_cost_usd'] == '0.000028'
    artifacts = [json.loads(path.read_text()) for path in (output/'prompts').glob('*.json')]
    assert len(artifacts) == 14 and all(a['schema'] == screen.TRANSPORT_SCHEMA for a in artifacts)
    protocol, data = screen.verify_frozen(output)
    raw = {path.name.removesuffix('-raw.json'): json.loads(path.read_text())['content']
           for path in (output/'responses').glob('*-raw.json')}
    assert screen.replay_records(protocol, data, frozen, raw) == {'construction_checks': 26, 'inference_calls': 0}
    assert screen.audit(protocol, data, frozen) == {k:v for k,v in result.items() if k not in ('calls','cost')}


def test_prepare_rejects_overlapping_primary_confirmation_family_and_unbounded_qualification(tmp_path):
    with pytest.raises(ValueError, match='separate sealed structural panel'):
        screen.prepare(tmp_path/'overlap', 'fixture', 'fixture', panel_family='confirmation')
    for proposals in (True, 1, 5):
        with pytest.raises(ValueError, match='between two and four'):
            screen.prepare(tmp_path/f'invalid-{proposals}', 'fixture', 'fixture', primitive_proposals=proposals)


def test_transport_only_omits_unique_items_and_host_still_rejects_duplicates():
    from jsonschema import ValidationError, validate
    assert screen.SCHEMA['properties']['dependencies']['uniqueItems'] is True
    expected = json.loads(json.dumps(screen.SCHEMA))
    del expected['properties']['dependencies']['uniqueItems']
    assert screen.TRANSPORT_SCHEMA == expected
    answer = {**program(), 'dependencies': ['same', 'same']}
    validate(answer, screen.TRANSPORT_SCHEMA)
    with pytest.raises(ValidationError, match='non-unique'):
        validate(answer, screen.SCHEMA)


def test_one_world_is_fixed_prefix_and_budget_is_predeclared(tmp_path):
    one, three = tmp_path/'one', tmp_path/'three'
    protocol = screen.prepare(one, 'fixture', 'fixture', seed=20261101, worlds=1, primitive_proposals=4)
    default = screen.prepare(three, 'fixture', 'fixture', seed=20261101, primitive_proposals=4)
    _, a = screen.verify_frozen(one); _, b = screen.verify_frozen(three)
    assert protocol['worlds'] == 1 and protocol['max_calls'] == 14
    assert default['worlds'] == 3 and default['max_calls'] == 42
    assert a['public']['streams'] == b['public']['streams'][:1]
    assert a['private']['configs'] == {a['public']['streams'][0]['source_id']:
        b['private']['configs'][a['public']['streams'][0]['source_id']]}
    assert protocol['request_interface_version'] == 2
    for worlds in (True, 0, 4):
        with pytest.raises(ValueError, match='between one and three'):
            screen.prepare(tmp_path/f'invalid-worlds-{worlds}', 'fixture', 'fixture', worlds=worlds)


def test_host_uniqueness_failure_is_preserved_and_delivered_without_output_repair(tmp_path):
    class DuplicateFirst(FixtureProvider):
        def ask_ai(self, prompt, config):
            raw = super().ask_ai(prompt, config)
            if len(self.calls) == 1:
                answer = json.loads(raw); answer['dependencies'] = ['same', 'same']
                return json.dumps(answer)
            return raw
    output = tmp_path/'duplicates'; screen.prepare(output, 'fixture', 'fixture', worlds=1)
    provider = DuplicateFirst(); result = screen.run(output, provider=provider)
    assert len(provider.calls) == 12
    delivered = provider.calls[1][0]['prior_trials'][0]
    assert json.loads(delivered['response_error']['raw_content'])['dependencies'] == ['same', 'same']
    assert 'non-unique' in delivered['response_error']['error'] and delivered['interface_error']
    assert (output/'responses/world-00-primitive-0-invalid.json').exists()
    assert result['worlds'] and len(result['worlds']) == 1


def test_schema_hash_custody_rejects_before_provider_attempt(tmp_path):
    output = tmp_path/'schemas'; screen.prepare(output, 'fixture', 'fixture', worlds=1)
    path = output/'protocol.json'; protocol = json.loads(path.read_text())
    protocol['transport_schema_sha256'] = 'wrong'; path.write_text(json.dumps(protocol))
    receipt = json.loads((output/'preparation-receipt.json').read_text())
    receipt['protocol_sha256'] = screen.digest(protocol)
    (output/'preparation-receipt.json').write_text(json.dumps(receipt))
    provider = FixtureProvider()
    with pytest.raises(ValueError, match='request schema custody'):
        screen.run(output, provider=provider)
    assert provider.calls == []
