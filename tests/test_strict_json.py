"""Generic JSON parsing remains independent of repository policy machinery."""
import json

import pytest

from system.lib.strict_json import (
    DuplicateJsonKeyError, StrictJsonError, StrictJsonObjectError,
    loads_json_strict, read_json_strict, read_jsonl_strict,
)


def test_distinct_objects_can_reuse_keys_and_preserve_ordinary_json_values():
    raw = '{"items": [{"id": 1}, {"id": 2}], "text": "λ", "flag": true, "empty": null}'
    assert loads_json_strict(raw) == json.loads(raw)
    assert loads_json_strict('[0, false, null, "value"]') == [0, False, None, 'value']


@pytest.mark.parametrize('raw', [
    '{"id": 1, "id": 2}',
    '{"outer": {"id": 1, "id": 2}}',
    '[{"id": 1, "id": 2}]',
    '{"id": 1, "\\u0069d": 2}',
])
def test_duplicate_keys_fail_even_when_nested_or_escaped(raw):
    with pytest.raises(DuplicateJsonKeyError, match="receipt: duplicate JSON key 'id'") as caught:
        loads_json_strict(raw, source='receipt')
    assert isinstance(caught.value, StrictJsonError)
    assert isinstance(caught.value, ValueError)


@pytest.mark.parametrize('raw', ['', '{', '{"id":}', '{"id": 1} trailing'])
def test_invalid_syntax_uses_the_generic_error_with_source_context(raw):
    with pytest.raises(StrictJsonError, match='response: invalid JSON:') as caught:
        loads_json_strict(raw, source='response')
    assert not isinstance(caught.value, DuplicateJsonKeyError)
    assert isinstance(caught.value.__cause__, json.JSONDecodeError)


def test_json_file_reader_retains_exact_values_and_names_the_bad_file(tmp_path):
    path = tmp_path / 'receipt.json'
    path.write_text('{"source": "λ", "values": [1, 2]}', encoding='utf-8')
    assert read_json_strict(path) == {'source': 'λ', 'values': [1, 2]}
    path.write_text('{"source": 1, "source": 2}', encoding='utf-8')
    with pytest.raises(DuplicateJsonKeyError) as caught:
        read_json_strict(path)
    assert str(path) in str(caught.value)


def test_jsonl_missing_and_blank_files_are_empty_without_creating_a_log(tmp_path):
    missing = tmp_path / 'missing.jsonl'
    assert read_jsonl_strict(missing) == []
    assert not missing.exists()
    blank = tmp_path / 'blank.jsonl'
    blank.write_text('\n \n\t\n', encoding='utf-8')
    assert read_jsonl_strict(blank) == []


def test_jsonl_rows_preserve_order_and_allow_keys_to_recur_between_objects(tmp_path):
    path = tmp_path / 'events.jsonl'
    path.write_text('\n{"id": 1}\n \n{"id": 2}\n', encoding='utf-8')
    assert read_jsonl_strict(path) == [{'id': 1}, {'id': 2}]


@pytest.mark.parametrize('row', ['1', 'null', '[]', '"text"'])
def test_jsonl_object_policy_reports_the_actual_nonblank_line(tmp_path, row):
    path = tmp_path / 'events.jsonl'
    path.write_text('{"id": 1}\n\n' + row + '\n', encoding='utf-8')
    with pytest.raises(StrictJsonObjectError) as caught:
        read_jsonl_strict(path)
    assert str(caught.value) == f'{path}:3 is not a JSON object'
    assert isinstance(caught.value, StrictJsonError)
    assert read_jsonl_strict(path, require_object=False) == [{'id': 1}, json.loads(row)]


def test_jsonl_duplicate_error_preserves_file_and_line_context(tmp_path):
    path = tmp_path / 'events.jsonl'
    path.write_text('\n{"id": 1}\n{"id": 2, "id": 3}\n', encoding='utf-8')
    with pytest.raises(DuplicateJsonKeyError) as caught:
        read_jsonl_strict(path)
    assert str(caught.value) == f"{path}:3: duplicate JSON key 'id'"
