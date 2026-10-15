"""Surviving graph contracts still validate real overlays and reject unsafe ones."""
import json
from pathlib import Path
from zipfile import ZipFile

import pytest

from tools.meta.factory.validate_reasoning_contracts import build_report

ROOT = Path(__file__).resolve().parents[1]
STANDARD = ROOT / 'codex/standards/std_node_reasoning.json'
DIRECTOR = ROOT / 'codex/substrate/nodes/lab/director.json'


def checked_node(tmp_path, node):
    path = tmp_path / 'node.json'
    path.write_text(json.dumps(node), encoding='utf-8')
    return build_report(ROOT, node_paths=[path])


def test_runtime_schema_and_overlay_vocabulary_preserve_frozen_contracts():
    current = json.loads(STANDARD.read_text())
    archive = ROOT / 'examples/conformance/progress-diagnostic-v5/runtime-source.zip'
    with ZipFile(archive) as source:
        frozen = json.loads(source.read('codex/standards/std_node_reasoning.json'))
    assert current['schema'] == frozen['schema']
    assert current['context_class_vocabulary'] == frozen['context_class_vocabulary']
    assert current['meta_reasoning_contract']['shape'] == frozen['meta_reasoning_contract']['shape']


def test_declared_contract_owners_resolve_to_existing_source():
    standard = json.loads(STANDARD.read_text())
    for owner in standard['authority_surfaces'].values():
        assert (ROOT / owner.split('::', 1)[0]).is_file(), owner


def test_real_retained_node_overlays_pass_the_standalone_validator():
    report = build_report(ROOT)
    assert report['ok'], report
    assert report['rows']
    assert all(row['issues'] == [] for row in report['rows'])


@pytest.mark.parametrize('field,value,expected', [
    ('role', 'invented_role', 'unknown_enum_value'),
    ('context', 'unregistered_context', 'unknown_context_class'),
    ('commit', True, 'unsafe_commit_gate'),
    ('readonly', 'yes', 'not_boolean'),
])
def test_invalid_overlay_fields_remain_rejected(tmp_path, field, value, expected):
    node = json.loads(DIRECTOR.read_text())
    contract = node['meta']['reasoning_contract']
    if field == 'role':
        contract['role_contract']['role_class'] = value
    elif field == 'context':
        contract['injection_contract']['inject'].append(value)
    elif field == 'commit':
        contract['side_effect_contract']['commit_allowed'] = value
        contract['learning_contract']['mutation_gate'] = 'none'
    else:
        contract['side_effect_contract']['read_only'] = value
    report = checked_node(tmp_path, node)
    assert not report['ok']
    assert expected in {issue['code'] for row in report['rows'] for issue in row['issues']}


def test_duplicate_overlay_key_cannot_hide_behind_a_valid_last_value(tmp_path):
    node = json.loads(DIRECTOR.read_text())
    source = json.dumps(node)
    assert '"role_class":' in source
    # Ordinary json.loads would keep the valid original role and lose the first value.
    source = source.replace('"role_class":', '"role_class": "invented", "role_class":', 1)
    path = tmp_path / 'duplicate-node.json'
    path.write_text(source, encoding='utf-8')
    report = build_report(ROOT, node_paths=[path])
    assert not report['ok']
    assert 'duplicate_json_key' in {issue['code'] for row in report['rows'] for issue in row['issues']}
