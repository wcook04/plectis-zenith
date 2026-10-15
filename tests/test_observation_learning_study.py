import json

import pytest

from research.observation_learning_study import (
    UNKNOWN, adoption, compile_prompt, development, normalize_probe, paired_summary,
    prepare, run, score, verify_frozen, engineering_checkpoint,
)
from research.observation_world import observe, world


LOOKUP = '''def investigate(context, acquire):
    for receipt in acquire("history"):
        if receipt["source_id"] == context["source_id"] and receipt["actions"] == context["actions"]:
            return {"value": receipt["observed"][context["goal"]], "unresolved": False}
    return {"value": None, "unresolved": True}
'''


def sample():
    config = world(7)
    receipts = [observe(config, []), observe(config, [{'op': 'put', 'key': 'a', 'value': 4}])]
    return config, receipts, development(config, receipts)


def test_observed_development_is_external_and_acquired():
    config, receipts, pairs = sample()
    result = score(LOOKUP, pairs)
    assert result['correct'] == result['total'] == 6
    assert all(row['trace'][0]['table'] == 'history' for row in result['rows'])
    assert all(not {'conflict', 'insert_trigger', 'counter', 'seed'} & set(case) for case, key in pairs)
    assert [key['value'] for case, key in pairs] == [value for r in receipts for value in r['observed'].values()]


def test_exact_answer_shape_does_not_accept_bool_as_integer():
    config, receipts, pairs = sample()
    result = score('def investigate(context, acquire): return {"value": False, "unresolved": False}', pairs)
    assert result['correct'] == 0


def test_net_gain_and_neutral_revisions_do_not_force_a_fixed_point():
    old = {'correct': 1, 'errors': 0, 'rows': [{'correct': True}, {'correct': False}, {'correct': False}]}
    new = {'correct': 2, 'errors': 0, 'rows': [{'correct': False}, {'correct': True}, {'correct': True}]}
    assert adoption(old, new) == (True, 1)
    assert adoption(old, old) == (True, 0)
    assert adoption(new, old) == (False, 2)


def test_search_parent_preserves_rejected_source_and_measured_error():
    config, receipts, pairs = sample()
    old = score(UNKNOWN['source'], pairs)
    record = {'proposal': {'source': 'broken', 'scope': '', 'lesson': ''},
              'accepted': False, 'candidate_summary': {'correct': 0},
              'feedback': [{'error': 'actual parse error'}]}
    prompt = compile_prompt('incremental', receipts, UNKNOWN, [record], pairs, old)
    assert prompt['last_challenger']['proposal']['source'] == 'broken'
    assert prompt['last_challenger']['feedback'][0]['error'] == 'actual parse error'
    assert 'construction_archive' not in prompt
    archived = compile_prompt('archive', receipts, UNKNOWN, [record], pairs, old)['construction_archive'][0]
    assert archived['proposal'] == record['proposal']
    assert archived['development_score'] == record['candidate_summary']
    assert archived['feedback'] == record['feedback']


def test_wire_decoding_only_removes_declared_null_fields():
    assert normalize_probe([{'op': 'begin', 'connection': 'main', 'key': None, 'value': None}]) == [
        {'op': 'begin', 'connection': 'main'}]
    assert normalize_probe([{'op': 'begin', 'key': 'invalid'}])[0]['key'] == 'invalid'


class FixtureProvider:
    """Test the campaign's mechanics; never label these as model research."""
    def __init__(self, fail_at=None):
        self.calls = []
        self.fail_at = fail_at

    def ask_ai(self, prompt, config, cancel=None):
        self.calls.append((json.loads(prompt), config))
        if len(self.calls) == self.fail_at:
            raise RuntimeError('fixture provider failure')
        if 'probes' in config['meta']['node_id']:
            return json.dumps({'experiments': [[], [
                {'op': 'put', 'connection': 'main', 'key': 'x', 'value': 7}], [
                {'op': 'put', 'connection': 'other', 'key': 'z', 'value': 3}]], 'purpose': 'fixture'})
        return json.dumps({'source': LOOKUP, 'scope': 'Exact observed lookup only.', 'lesson': 'fixture'})


def test_whole_protocol_equal_calls_blind_audit_and_no_restart(tmp_path):
    output = tmp_path/'study'
    prepare(output, 'fixture', 'fixture', worlds=1)
    provider = FixtureProvider()
    result = run(output, provider=provider)
    assert len(provider.calls) == 21
    assert len(result['worlds']) == 1
    assert (output/'all-frozen.json').exists()
    for arm in ('incremental', 'archive', 'fresh'):
        assert sum(f'-{arm}-' in config['meta']['node_id'] for p, config in provider.calls) == 6
    fresh = [p for p, c in provider.calls if '-fresh-' in c['meta']['node_id']]
    assert all(len(p['history']) == 12 for p in fresh)
    for p, config in provider.calls:
        assert not any(k in p for k in ('private', 'configs', 'partitions', 'eval', 'expected'))
        assert 'source_id' not in p or str(p['source_id']).startswith('source-')
    # Matching previous observations is deliberately insufficient for heldout composition.
    assert result['aggregate']['incremental']['correct'] < result['aggregate']['incremental']['total']
    with pytest.raises(ValueError, match='already started'):
        run(output, provider=provider)


def test_failed_paid_call_stops_without_filling_the_slot(tmp_path):
    output = tmp_path/'study'
    prepare(output, 'fixture', 'fixture', worlds=1)
    provider = FixtureProvider(fail_at=2)
    with pytest.raises(RuntimeError, match='fixture provider failure'):
        run(output, provider=provider)
    assert len(provider.calls) == 2
    assert not (output/'results.json').exists()
    failure = json.loads((output/'failure.json').read_text())
    assert failure['automatic_retry'] is False
    assert failure['protected_evaluation_performed'] is False


def test_frozen_data_tamper_fails_before_provider_call(tmp_path):
    output = tmp_path/'study'
    prepare(output, 'fixture', 'fixture', worlds=1)
    data = json.loads((output/'datasets.json').read_text())
    data['private']['native_family_size'] = 999
    (output/'datasets.json').write_text(json.dumps(data))
    with pytest.raises(ValueError, match='dataset changed'):
        verify_frozen(output)


def test_paired_summary_uses_worlds_not_case_pseudoreplication():
    rows = [{'a': {'correct': 1, 'total': 2}, 'b': {'correct': 0, 'total': 2}},
            {'a': {'correct': 3, 'total': 4}, 'b': {'correct': 4, 'total': 4}}]
    summary = paired_summary(rows, 'a', 'b')
    assert summary['worlds'] == 2
    assert summary['per_world'] == [0.5, -0.25]
    assert summary['mean_accuracy_difference'] == 0.125


@pytest.mark.parametrize('invalid_raw', ['{not JSON', json.dumps({'source': LOOKUP, 'scope': 0, 'lesson': ''})])
def test_original_schema_error_and_raw_output_reach_next_request(tmp_path, invalid_raw):
    class InvalidFirst(FixtureProvider):
        def ask_ai(self, prompt, config, cancel=None):
            result = super().ask_ai(prompt, config, cancel)
            return invalid_raw if len(self.calls) == 2 else result
    output = tmp_path/'study'
    prepare(output, 'fixture', 'fixture', worlds=1)
    provider = InvalidFirst()
    run(output, provider=provider)
    delivered = provider.calls[2][0]['last_challenger']
    assert not delivered['accepted']
    assert delivered['response_error']['raw_content'] == invalid_raw
    assert all(r['error'] == delivered['response_error']['schema_error'] for r in delivered['feedback'])


def test_engineering_gate_stops_before_more_calls_and_before_protected_audit(tmp_path):
    class Broken(FixtureProvider):
        def ask_ai(self, prompt, config, cancel=None):
            result = super().ask_ai(prompt, config, cancel)
            return result if 'probes' in config['meta']['node_id'] else json.dumps(
                {'source': 'not Python', 'scope': '', 'lesson': ''})
    output = tmp_path/'study'
    prepare(output, 'fixture', 'fixture', worlds=1)
    provider = Broken()
    with pytest.raises(RuntimeError, match='engineering checkpoint'):
        run(output, provider=provider)
    assert len(provider.calls) == 5
    assert json.loads((output/'pilot-checkpoint.json').read_text())['continue'] is False
    assert not (output/'results.json').exists()
    assert not json.loads((output/'failure.json').read_text())['protected_evaluation_performed']


def test_parallel_worlds_overlap_but_dependencies_and_gate_remain_ordered(tmp_path):
    import threading
    import time
    class Timed(FixtureProvider):
        def __init__(self):
            super().__init__()
            self.lock = threading.Lock()
            self.active = self.peak = 0
        def ask_ai(self, prompt, config, cancel=None):
            with self.lock:
                self.active += 1
                self.peak = max(self.peak, self.active)
            try:
                time.sleep(.05)
                return super().ask_ai(prompt, config, cancel)
            finally:
                with self.lock:
                    self.active -= 1
    output = tmp_path/'study'
    protocol = prepare(output, 'fixture', 'route/a', worlds=2,
                       workers=2, provider_slugs=['route/a', 'route/b'])
    provider = Timed()
    result = run(output, provider=provider)
    assert provider.peak == 2
    assert len(provider.calls) == 42
    assert len(result['worlds']) == 2
    names = [c['meta']['node_id'] for p, c in provider.calls]
    # Both first-prefix trajectories finish before admission to the next wave.
    first_next = min(names.index(f'world-{i:02d}-probes-1') for i in range(2))
    assert first_next == 10
    for i in range(2):
        ordered = [n for n in names if n.startswith(f'world-{i:02d}-')]
        assert ordered[0].endswith('probes-0')
        assert all('fresh' in n for n in ordered[-6:])
        record = json.loads((output/f'world-{i:02d}-frozen.json').read_text())
        assert record['provider_slug'] == protocol['world_providers'][i]


def test_production_provider_identity_and_shared_ledger_are_wired(tmp_path, monkeypatch):
    from research import observation_learning_study as study
    from zenith.budgeted import OpenRouterBudgetedProvider
    monkeypatch.setenv('OPENROUTER_API_KEY', 'fixture-only-not-a-real-key')
    model = 'deepseek/fixture'
    parameters = ['max_tokens', 'temperature', 'response_format', 'structured_outputs', 'reasoning']
    pricing = {'prompt': '.0000001', 'completion': '.0000001'}
    row = {'id': model, 'context_length': 200000, 'pricing': pricing,
           'architecture': {'input_modalities': ['text'], 'output_modalities': ['text']},
           'supported_parameters': parameters}
    endpoint = {'model_id': model, 'tag': 'fixture/fp8', 'provider_name': 'Fixture', 'status': 0,
                'context_length': 200000, 'max_completion_tokens': 8192,
                'supported_parameters': parameters, 'pricing': pricing}
    posts = []
    def get(url, *args):
        return {'data': {'id': model, 'endpoints': [endpoint]}} if url.endswith('/endpoints') else {'data': [row]}
    def post(url, headers, payload, timeout):
        posts.append(payload)
        planner = 'experiments' in payload['response_format']['json_schema']['schema']['properties']
        answer = ({'experiments': [[], [], []], 'purpose': 'fixture'} if planner else
                  {'source': LOOKUP, 'scope': 'Fixture lookup', 'lesson': 'fixture'})
        return {'model': model, 'provider': 'Fixture',
                'usage': {'prompt_tokens': 10, 'completion_tokens': 10, 'cost': .000002},
                'choices': [{'message': {'content': json.dumps(answer)}}]}
    def factory(*args, **kwargs):
        return OpenRouterBudgetedProvider(*args, **kwargs, caller=post, catalogue_get=get)
    monkeypatch.setattr(study, 'OpenRouterBudgetedProvider', factory)
    output = tmp_path/'study'
    env = tmp_path/'empty.env'
    env.write_text('')
    prepare(output, model, 'fixture/fp8', worlds=1)
    run(output, env_file=env)
    ledger = json.loads((output/'budget/budget.json').read_text())
    assert len(posts) == len(ledger['entries']) == 21
    assert {e['run_id'] for e in ledger['entries'].values()} == {'provider-world-00'}
    assert all(e['status'] == 'response_supplied' for e in ledger['entries'].values())
    assert len(list((output/'provider-world-00/handoff/api_calls').rglob('*.json'))) == 21


def test_planner_receives_actual_rejected_experiment_feedback(tmp_path):
    class IllegalProbe(FixtureProvider):
        def ask_ai(self, prompt, config, cancel=None):
            result = super().ask_ai(prompt, config, cancel)
            if config['meta']['node_id'].endswith('probes-0'):
                return json.dumps({'experiments': [[], [], [
                    {'op': 'rollback', 'connection': 'main', 'key': None, 'value': None}]],
                    'purpose': 'One deliberately illegal fixture probe'})
            return result
    output = tmp_path/'study'
    prepare(output, 'fixture', 'fixture', worlds=1)
    provider = IllegalProbe()
    run(output, provider=provider)
    later = next(p for p, c in provider.calls if c['meta']['node_id'].endswith('probes-1'))
    rejected = [r for r in later['previous_experiments'] if 'error' in r]
    assert len(rejected) == 1
    assert rejected[0]['actions'] == [{'op': 'rollback', 'connection': 'main'}]
    assert rejected[0]['error'] == 'transaction completion without matching begin'


def test_gate_does_not_accept_executable_but_universally_unresolved_program():
    candidate = {'candidate_summary': {'errors': 0, 'correct': 0}}
    record = {'source_id': 'fixture', 'probe_log': [{'receipt': {}}],
              'arms': {arm: {'rounds': [candidate]} for arm in ('incremental', 'archive')}}
    assert engineering_checkpoint([record])['continue'] is False
    candidate['candidate_summary']['correct'] = 1
    assert engineering_checkpoint([record])['continue'] is True


def test_engineering_gate_keeps_hard_sources_in_the_comparison():
    def record(name, correct, errors=0, probes=True):
        return {'source_id': name, 'probe_log': [{'receipt': {}}] if probes else [],
                'arms': {arm: {'rounds': [{'candidate_summary': {'errors': errors, 'correct': correct}}]}
                         for arm in ('incremental', 'archive')}}
    useful, difficult = record('useful', 1), record('difficult', 0)
    gate = engineering_checkpoint([useful, difficult])
    assert gate['continue'] is True
    assert [r['source_id'] for r in gate['worlds']] == ['useful', 'difficult']
    assert gate['worlds'][1]['programs_above_cold_development'] == 0
    assert not engineering_checkpoint([useful, record('broken', 0, errors=1)])['continue']
    assert not engineering_checkpoint([useful, record('unmeasured', 0, probes=False)])['continue']


def test_parallel_failure_reports_cause_after_draining_sibling(tmp_path):
    import threading
    class FailingSibling(FixtureProvider):
        def __init__(self):
            super().__init__()
            self.entered = threading.Event()
            self.drained = False
        def ask_ai(self, prompt, config, cancel=None):
            name = config['meta']['node_id']
            if name == 'world-00-probes-0':
                self.entered.set()
                assert cancel.wait(5)
                self.drained = True
                return super().ask_ai(prompt, config, cancel)
            if name == 'world-01-probes-0':
                assert self.entered.wait(5)
                raise RuntimeError('original provider failure')
            raise AssertionError('No further call should be admitted')
    output = tmp_path/'study'
    prepare(output, 'fixture', 'route/a', worlds=2, workers=2,
            provider_slugs=['route/a', 'route/b'])
    provider = FailingSibling()
    with pytest.raises(RuntimeError, match='original provider failure'):
        run(output, provider=provider)
    assert provider.drained
    failure = json.loads((output/'failure.json').read_text())
    assert failure['error'] == 'RuntimeError: original provider failure'
    assert failure['protected_evaluation_performed'] is False


def test_six_world_route_assignment_counterbalances_native_settings(tmp_path):
    output = tmp_path/'study'
    protocol = prepare(output, 'fixture', 'host/a', worlds=6, workers=3,
                       provider_slugs=['host/a', 'host/b', 'host/c'])
    data = json.loads((output/'datasets.json').read_text())
    configs = [data['private']['configs'][s['source_id']] for s in data['public']['streams']]
    for route in protocol['provider_slugs']:
        assigned = [c for c, r in zip(configs, protocol['world_providers']) if r == route]
        assert len(assigned) == 2
        assert all(len({c[field] for c in assigned}) == 2 for field in ('conflict', 'counter', 'insert_trigger'))
