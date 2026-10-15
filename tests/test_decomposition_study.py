"""Offline custody, feedback and comparison-boundary checks for decomposition."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
from pathlib import Path
import threading

import pytest

from research import decomposition_study as study


INITIAL = '''def focus(value):
    return 0

def investigate(context, acquire):
    return focus(context["value"])
'''
CORRECT = INITIAL.replace('return 0', 'return value + 1')
BROKEN = INITIAL.replace('return 0', 'return value // 0')
MODEL = 'deepseek/deepseek-v4.1-flash'
ROUTE = 'fixture/endpoint'


def tiny_dataset():
    """No fixture builders, oracle implementation or private truth in prompts."""
    return {'schema': 'offline-decomposition-fixture', 'tasks': [{
        'id': 'task-0', 'family': 'fixture',
        'description': 'Return the measured integer response to the input value.',
        'initial_source': INITIAL, 'focus_function': 'focus',
        'private': {'secret': 'private-configuration-never-delivered',
                    'reference_source': 'private-reference-never-delivered'},
        'calibration': [{'input': {'value': 0}, 'expected': 1}],
        'development': [{'input': {'value': 1}, 'expected': 2},
                        {'input': {'value': 2}, 'expected': 3}],
        'screen': [{'input': {'value': 10002}, 'expected': 10003}],
        'confirmation': [{'input': {'value': 20006}, 'expected': 20007}],
    }]}


def response(source=CORRECT):
    return json.dumps({'source': source, 'scope': 'Offline fixture proposal.',
                       'change': 'Fixture executable change.'})


class FixtureProvider:
    def __init__(self, root, responses):
        self.run_dir = Path(root)
        self.responses = list(responses)
        self.calls = []
        self.lock = threading.Lock()

    def ask_ai(self, prompt, options, cancel=None):
        with self.lock:
            self.calls.append({'prompt': json.loads(prompt), 'options': deepcopy(options)})
            assert cancel is not None
            assert not cancel.is_set()
            if not self.responses:
                raise AssertionError('unexpected extra inference attempt')
            return self.responses.pop(0)


def prepared(tmp_path, *, arms=('global',), proposals=2, dataset=None):
    output = tmp_path / 'study'
    study.prepare(output, MODEL, [ROUTE], arms=arms, proposals=proposals,
                  workers=1, max_output_tokens=1024, dataset=dataset or tiny_dataset())
    return output


def factory(provider):
    def construct(task, route):
        assert task['id'] == 'task-0'
        assert route == ROUTE
        return provider
    return construct


def test_rejected_runtime_error_is_delivered_to_the_next_actual_request(tmp_path):
    output = prepared(tmp_path)
    provider = FixtureProvider(tmp_path / 'provider', [response(BROKEN), response()])
    study.run(output, provider_factory=factory(provider))
    assert len(provider.calls) == 2
    second = provider.calls[1]['prompt']
    rejected = second['prior_attempts'][0]
    assert rejected['source'] == BROKEN
    assert rejected['response_error'] is None
    assert rejected['constraint_error'] is None
    assert rejected['development']['errors'] > 0
    assert all('ZeroDivisionError' in row['error'] for row in rejected['development']['rows'])
    assert second['current_program'] == INITIAL
    assert study.read(output / 'frozen.json')['records'][0]['arms']['global']['selected']['source'] == CORRECT
    assert study.replay(output)['construction_attempts'] == 2


def test_actual_requests_never_deliver_private_or_protected_material(tmp_path):
    output = prepared(tmp_path, arms=study.ARMS)
    provider = FixtureProvider(tmp_path / 'provider', [response() for unused in range(8)])
    study.run(output, provider_factory=factory(provider))
    for call in provider.calls:
        material = json.dumps(call)
        for forbidden in ('private-configuration-never-delivered', 'private-reference-never-delivered',
                          '10002', '10003', '20006', '20007'):
            assert forbidden not in material
        assert not {'private', 'screen', 'confirmation', 'initial_source'} & call['prompt']['task'].keys()
        assert set(call['options']['meta']) == {'session_id', 'node_id'}
        assert call['options']['reasoning_effort'] == 'none'
        assert call['options']['response_format']['json_schema']['schema'] == study.SCHEMA
        assert call['options']['system_prompt'] == study.LANGUAGE
    global_request = provider.calls[0]['prompt']
    assert 'local_context' not in global_request
    assert 'function_contracts' not in global_request
    contextual = provider.calls[2]['prompt']['local_context']
    assert contextual == {'focus': 'focus', 'nodes': study.call_structure(INITIAL)}
    contracts = provider.calls[4]['prompt']['function_contracts']
    assert contracts == ["focus(value); calls []; used by ['investigate']",
                         "investigate(context, acquire); calls ['focus']; used by []"]
    assert study.replay(output)['construction_attempts'] == 8


def test_function_metadata_is_mechanical_and_has_no_hidden_diagnosis():
    rows = study.call_structure(INITIAL)
    assert rows == [
        {'name': 'focus', 'arguments': ['value'], 'calls': [], 'called_by': ['investigate']},
        {'name': 'investigate', 'arguments': ['context', 'acquire'], 'calls': ['focus'], 'called_by': []},
    ]
    assert all(set(row) == {'name', 'arguments', 'calls', 'called_by'} for row in rows)


@pytest.mark.parametrize('source', [
    CORRECT.replace('focus(value)', 'focus(value, extra)'),
    CORRECT.replace('return focus(context["value"])', 'return context["value"] + 1'),
    CORRECT + '\ndef extra(value):\n    return value\n',
    'def investigate(context, acquire):\n    return focus(context["value"])\n\n'
    'def focus(value):\n    return value + 1\n',
])
def test_fixed_helper_cannot_change_the_actual_boundary_or_other_code(source):
    task = tiny_dataset()['tasks'][0]
    assert study.constraint(task, 'fixed', source) is not None
    assert study.constraint(task, 'global', source) is None


def test_fixed_helper_body_edit_remains_permitted():
    task = tiny_dataset()['tasks'][0]
    assert study.constraint(task, 'fixed', CORRECT) is None


def test_selected_program_is_frozen_and_both_panels_replay_without_inference(tmp_path):
    output = prepared(tmp_path)
    # The final attempted body has execution errors; selection must preserve the
    # earlier executable body and its original response without host repair.
    provider = FixtureProvider(tmp_path / 'provider', [response(), response(BROKEN)])
    screen = study.run(output, provider_factory=factory(provider))
    frozen = study.read(output / 'frozen.json')
    receipt = study.read(output / 'frozen-receipt.json')
    assert receipt['frozen_sha256'] == study.digest(frozen)
    selected = frozen['records'][0]['arms']['global']['selected']
    assert selected['source'] == CORRECT
    assert selected['node_id'].endswith('-global-0')
    assert screen['totals']['global']['correct'] == 1
    confirmation = study.evaluate(output, 'confirmation')
    assert confirmation['totals']['global']['correct'] == 1
    replayed = study.replay(output)
    assert replayed == {'ok': True, 'construction_attempts': 2,
                        'protected_partitions': ['screen', 'confirmation']}
    assert len(provider.calls) == 2
    assert study.read(output / 'frozen.json') == frozen
    with pytest.raises(ValueError, match='already evaluated'):
        study.evaluate(output, 'confirmation')


def test_started_identity_cannot_be_rerun_even_after_a_provider_failure(tmp_path):
    output = prepared(tmp_path)
    provider = FixtureProvider(tmp_path / 'provider', [])
    result = study.run(output, provider_factory=factory(provider))
    assert result['complete'] is False
    assert (output / 'started.json').exists()
    assert len(provider.calls) == 1
    with pytest.raises(ValueError, match='already started'):
        study.run(output, provider_factory=factory(provider))
    assert len(provider.calls) == 1
    with pytest.raises(ValueError, match='Incomplete'):
        study.evaluate(output, 'confirmation')


def test_dataset_and_raw_response_custody_detect_mutation(tmp_path):
    output = prepared(tmp_path)
    provider = FixtureProvider(tmp_path / 'provider', [response(), response()])
    study.run(output, provider_factory=factory(provider))
    response_path = output / 'responses' / 'task-0-global-0.json'
    original = study.read(response_path)
    study.write_json(response_path, {**original, 'raw': original['raw'] + ' '})
    with pytest.raises((AssertionError, ValueError)):
        study.replay(output)
    study.write_json(response_path, original)
    dataset = study.read(output / 'datasets.json')
    dataset['tasks'][0]['confirmation'][0]['expected'] = 0
    study.write_json(output / 'datasets.json', dataset)
    with pytest.raises(ValueError, match='protocol/dataset'):
        study.verify(output)


def test_selection_replays_calibration_as_well_as_development(tmp_path):
    output = prepared(tmp_path)
    # This later program fits every fresh development row, but regresses an
    # independently observed calibration row. A visible-evidence tie is false.
    regression = INITIAL.replace('return 0', 'return 999 if value == 0 else value + 1')
    provider = FixtureProvider(tmp_path / 'provider', [response(), response(regression)])
    study.run(output, provider_factory=factory(provider))
    state = study.read(output / 'frozen.json')['records'][0]['arms']['global']
    assert state['selected']['source'] == CORRECT
    assert state['trials'][1]['development']['correct'] < state['trials'][0]['development']['correct']
    assert study.replay(output)['construction_attempts'] == 2


def test_start_admission_is_exclusive_under_simultaneous_invocations(tmp_path, monkeypatch):
    output = prepared(tmp_path, proposals=1)
    started = output.resolve() / 'started.json'
    barrier = threading.Barrier(2)
    seen = threading.local()
    original_exists = Path.exists

    def synchronized_exists(path):
        result = original_exists(path)
        if path == started and not getattr(seen, 'checked', False):
            seen.checked = True
            barrier.wait(timeout=5)
        return result

    monkeypatch.setattr(Path, 'exists', synchronized_exists)
    provider = FixtureProvider(tmp_path / 'provider', [response(), response()])

    def attempt():
        try:
            return study.run(output, provider_factory=factory(provider))
        except Exception as error:
            return error

    with ThreadPoolExecutor(max_workers=2) as pool:
        attempts = list(pool.map(lambda unused: attempt(), range(2)))
    assert len(provider.calls) == 1
    assert sum(isinstance(result, (ValueError, FileExistsError)) for result in attempts) == 1
