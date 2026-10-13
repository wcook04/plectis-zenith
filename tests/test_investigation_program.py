import pytest

from zenith.investigation_program import execute, validate_source
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
