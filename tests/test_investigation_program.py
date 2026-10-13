import pytest

from zenith.investigation_program import (execute, execute_local, validate_source,
                                         JSON_ANSWER_MAX_BYTES, JSON_ANSWER_MAX_DEPTH)
from research.operational_cases import INCUMBENT, grade, make_case, suite, novel_suite, typed_reference, rename_fields, FIELDS
from research.investigation_learning_study import score_program


@pytest.mark.parametrize('schema', ['native', 'foreign'])
def test_observed_reference_matches_independent_latent_oracle(schema):
    for case, expected in suite(123, 256, schema) + novel_suite(500, 256, schema):
        assert grade(expected, typed_reference(case))['correct']


def test_same_spans_require_different_computations():
    active, a = make_case(1, kind='active', overlap=True)
    work, w = make_case(1, kind='work', overlap=True)
    assert active['tables'] == work['tables']
    assert a['ratio'] == pytest.approx(1)
    assert w['ratio'] == pytest.approx(2)
    assert a['findings'] != w['findings']


def test_unresolved_does_not_erase_supported_findings():
    case, key = make_case(44, duplicate=True, missing=True, shift=True, unknown=True, conflict=True)
    assert key['findings'] == ['duplicate_delivery', 'workload_shift']
    assert key['unresolved'] == ['conflicting_event', 'incomplete_coverage', 'unknown_clock_unit']
    assert key['ratio'] is None
    assert grade(key, typed_reference(case))['correct']


def test_incumbent_has_measurable_failure_and_records_real_acquisition():
    result = score_program(INCUMBENT, suite(800, 16))
    assert 0 < result['correct'] < result['total']
    assert all(row['trace'][0]['table'] == 'spans' for row in result['rows'])
    assert all(len(row['trace']) == 1 for row in result['rows'])


@pytest.mark.parametrize('source', [
    'import os\ndef investigate(context, acquire): return {}',
    'def investigate(context, acquire): return context.__class__',
    'def investigate(context, acquire):\n while True: pass',
    'def investigate(context, acquire): return 10 ** 100000',
    'x = 1\ndef investigate(context, acquire): return {}',
    'def investigate(context, acquire):\n return [x for x in context.__class__.__bases__]',
    'def investigate(context, acquire=open("/tmp/example", "w")): return {}',
])
def test_rejects_ambient_or_unbounded_syntax(source):
    with pytest.raises((ValueError, SyntaxError)):
        validate_source(source)


def test_worker_has_no_import_and_no_unacquired_tables():
    case, key = make_case(4)
    for source in ['def investigate(context, acquire): return open("/etc/passwd")',
                   'def investigate(context, acquire): return context["tables"]']:
        result = execute(source, [case])[0]
        assert result['answer'] is None
        assert result['error']
        assert result['trace'] == []


def test_execution_resets_state_and_copies_table_data():
    case, key = make_case(4)
    source = '''def investigate(context, acquire):
    spans = acquire("spans")
    spans.pop()
    restored = acquire("spans")
    return {"findings": [], "unresolved": [], "ratio": len(restored) - len(spans)}
'''
    results = execute(source, [case, case])
    assert [r['answer']['ratio'] for r in results] == [1, 1]
    assert results[0]['trace'] == results[1]['trace']


def test_nonlocal_simulator_state_is_mutable_and_resets_between_cases():
    source = '''def investigate(context, acquire):
    state = {}
    total = 0
    def put(key, value):
        nonlocal state, total
        state = dict(state)
        state[key] = value
        total += 1
    for action in context["actions"]:
        put(action["key"], action["value"])
    return {"findings": [], "unresolved": [], "ratio": total + sum(state.values())}
'''
    case = {'actions': [{'key': 'a', 'value': 3}, {'key': 'a', 'value': 5}], 'tables': {}}
    results = execute(source, [case, case])
    assert [row['answer']['ratio'] for row in results] == [7, 7]
    assert all(row['error'] is None for row in results)


def test_container_update_clear_and_deletion_preserve_acquired_input():
    source = '''def investigate(context, acquire):
    rows = acquire("events")
    state = {"drop": 0}
    state.update(rows[0])
    state.update([("second", 2)], third=3)
    scratch = 10
    other = 11
    del (scratch, other)
    del state["drop"], rows[0]["value"]
    total = state["value"] + state["second"] + state["third"]
    state.clear()
    rows.clear()
    restored = acquire("events")
    del restored[:]
    return {"total": total, "state": state, "rows": rows,
            "restored": restored, "original": acquire("events")}
'''
    case = {'tables': {'events': [{'value': 4}]}}
    results = execute(source, [case, case], answer_contract='json')
    assert all(row['answer'] == {'total': 9, 'state': {}, 'rows': [],
                                 'restored': [], 'original': [{'value': 4}]} for row in results)
    assert all(row['error'] is None for row in results)
    assert case['tables']['events'] == [{'value': 4}]
    assert all(len(row['trace']) == 3 for row in results)


@pytest.mark.parametrize('body,expected', [
    ('global state\n    return {}', 'unsupported syntax: Global'),
    ('import os\n    return {}', 'unsupported syntax: Import'),
    ('nonlocal hidden, _secret\n    return {}', 'private names'),
    ('nonlocal __builtins__\n    return {}', 'private names'),
    ('del _secret\n    return {}', 'private names'),
    ('del context.clear\n    return {}', 'deletion is permitted only'),
    ('del (context["value"], context.update)\n    return {}', 'deletion is permitted only'),
    ('return context.__dict__', 'unsupported method'),
    ('return context.write("value")', 'unsupported method'),
])
def test_new_state_operations_do_not_broaden_ambient_or_attribute_access(body, expected):
    with pytest.raises(ValueError, match=expected):
        validate_source('def investigate(context, acquire):\n    ' + body)


def test_json_answer_contract_returns_nested_computed_observations():
    case = {'id': 'observation', 'channel': 'settled',
            'tables': {'events': [{'amount': 3}, {'amount': 4}]}}
    source = '''def investigate(context, acquire):
    events = acquire("events")
    return {"channel": context["channel"],
            "observations": [{"value": sum(row["amount"] for row in events),
                              "available": True, "missing": None}],
            "interval": [-0.5, 7.5]}
'''
    result = execute(source, [case], answer_contract='json')[0]
    assert result['answer'] == {'channel': 'settled',
                                'observations': [{'value': 7, 'available': True, 'missing': None}],
                                'interval': [-0.5, 7.5]}
    assert result['error'] is None
    assert [entry['table'] for entry in result['trace']] == ['events']
    legacy = execute(source, [case])[0]
    assert legacy['answer'] is None
    assert 'exactly findings, unresolved and ratio' in legacy['error']


@pytest.mark.parametrize('value,expected', [('None', None), ('False', False), ('-3', -3),
                                           ('0.5', 0.5), ('"reading"', 'reading'), ('[1, 2]', [1, 2])])
def test_json_answer_contract_accepts_top_level_scalars_and_arrays(value, expected):
    source = f'def investigate(context, acquire): return {value}'
    result = execute(source, [{'tables': {}}], answer_contract='json')[0]
    assert result['error'] is None
    assert result['answer'] == expected


@pytest.mark.parametrize('value', ['float("nan")', 'float("inf")', '-float("inf")'])
def test_json_answer_contract_rejects_nested_nonfinite_numbers(value):
    source = f'def investigate(context, acquire): return {{"observations": [{{"value": {value}}}]}}'
    result = execute(source, [{'tables': {}}], answer_contract='json')[0]
    assert result['answer'] is None
    assert 'numbers must be finite' in result['error']


@pytest.mark.parametrize('value', ['(1, 2)', '{1, 2}', '{1: "value"}'])
def test_json_answer_contract_rejects_python_values_outside_json(value):
    result = execute(f'def investigate(context, acquire): return {value}',
                     [{'tables': {}}], answer_contract='json')[0]
    assert result['answer'] is None
    assert result['error']


@pytest.mark.parametrize('executor', [execute, execute_local])
def test_invalid_answer_contract_is_rejected_before_execution(executor):
    with pytest.raises(ValueError, match='answer_contract'):
        executor('def investigate(context, acquire): return {}', [], answer_contract='observation')


@pytest.mark.parametrize('character,count', [('x', JSON_ANSWER_MAX_BYTES),
                                             ('\u2603', JSON_ANSWER_MAX_BYTES // 6)])
def test_json_answer_contract_limits_serialized_bytes(character, count):
    source = f'def investigate(context, acquire): return {character!r} * {count}'
    result = execute(source, [{'tables': {}}], answer_contract='json')[0]
    assert result['answer'] is None
    assert 'serialized size limit' in result['error']


def test_json_answer_contract_limits_depth_and_cyclic_answers():
    template = '''def investigate(context, acquire):
    value = 0
    for step in range({depth}):
        value = [value]
    return value
'''
    case = {'tables': {}}
    accepted = execute(template.format(depth=JSON_ANSWER_MAX_DEPTH), [case], answer_contract='json')[0]
    assert accepted['error'] is None
    rejected = execute(template.format(depth=JSON_ANSWER_MAX_DEPTH + 1), [case], answer_contract='json')[0]
    assert rejected['answer'] is None
    assert 'nesting depth limit' in rejected['error']
    cyclic = '''def investigate(context, acquire):
    value = []
    value.append(value)
    return value
'''
    result = execute(cyclic, [case], answer_contract='json')[0]
    assert result['answer'] is None
    assert 'nesting depth limit' in result['error']


def test_json_answer_contract_preserves_acquisition_limit():
    source = '''def investigate(context, acquire):
    for step in range(9):
        acquire("events")
    return {"value": 1}
'''
    result = execute(source, [{'tables': {'events': []}}], answer_contract='json')[0]
    assert result['answer'] is None
    assert 'acquisition limit exceeded' in result['error']
    assert len(result['trace']) == 8


def test_mapping_only_adapter_preserves_values_and_cannot_replace_program():
    native, key = make_case(99)
    foreign, key = make_case(99, schema='foreign')
    mapping = dict(zip(FIELDS['native'], FIELDS['foreign']))
    assert rename_fields(foreign, mapping, native['source_documentation']) == native
    with pytest.raises(ValueError):
        rename_fields(foreign, {'source': 'replacement solver'}, '')


@pytest.mark.parametrize('style', ['broad', 'compact'])
def test_rejected_candidate_error_reaches_next_actual_provider_request(tmp_path, monkeypatch, style):
    import json
    from research import investigation_learning_study as study
    calls = []
    class FakeProvider:
        def __init__(self, *args, **kwargs):
            pass
        def ask_ai(self, prompt, config):
            calls.append(json.loads(prompt))
            if len(calls) == 2:
                raise RuntimeError('stop after witnessing repair dependency')
            return json.dumps({'source': 'import os', 'scope': 'test', 'lesson': 'test'})
    monkeypatch.setattr(study, 'OpenRouterBudgetedProvider', FakeProvider)
    output = tmp_path/'campaign'
    study.prepare(output, model='deepseek/deepseek-v4.1-flash', feedback_style=style)
    env_file = tmp_path/'empty.env'; env_file.write_text('')
    with pytest.raises(RuntimeError, match='witnessing repair dependency'):
        study.run(output, env_file)
    delivered = calls[1]['previous_candidate_execution']
    assert delivered['proposal']['source'] == 'import os'
    assert delivered['accepted'] is False
    assert all('only function definitions' in row['error'] for row in delivered['candidate_failures'])
    assert calls[1]['incumbent']['source'] == INCUMBENT
    assert ('numerical_residual_actual_minus_expected' in delivered['candidate_failures'][0]) == (style == 'compact')
