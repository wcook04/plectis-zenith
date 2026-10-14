import json
from pathlib import Path
import shutil

import pytest

from scripts.build_advance_report import build

ROOT = Path(__file__).resolve().parents[1]


def test_campaign_preserves_unknown_charge_and_unpooled_results():
    result = build()
    assert result['total_calls'] == 79
    assert result['total_reported_cost_usd'] == '0.114722219072'
    assert result['unresolved_attempts'] == 1
    studies = {s['id']: s for s in result['conformance_studies']}
    partial = studies['ling-interrupted-v3']
    assert not partial['complete'] and partial['panel_summary'] == {}
    assert partial['unresolved_reserved_usd'] == '0.0154065'
    assert studies['ling-full-v3b']['panel_summary']['confirmation']['totals']['fixed']['correct'] == 239
    assert result['memory']['ordinary_modules_calls'] == 3071
    assert sum(c['target_calls_saved'] for c in result['memory']['suffix_transfer_conditions']) == -470


def test_campaign_rejects_changed_published_charge(tmp_path):
    relative = Path('examples/conformance/ling-interrupted-v3')
    shutil.copytree(ROOT / relative, tmp_path / relative)
    path = tmp_path / relative / 'billing.json'
    billing = json.loads(path.read_text())
    billing['total_reported_cost_usd'] = '0'
    path.write_text(json.dumps(billing))
    with pytest.raises(ValueError, match='custody'):
        build(tmp_path)


def test_missing_studies_are_pending_instead_of_claiming_completion(tmp_path):
    result = build(tmp_path)
    assert result['status'] == 'pending'
    assert not result['conformance_studies'] and not result['memory']


def test_memory_projection_rejects_changed_protocol(tmp_path):
    relative = Path('examples/continuation-memory/leave-one-out-v1')
    shutil.copytree(ROOT / relative, tmp_path / relative)
    path = tmp_path / relative / 'protocol-v2.json'
    path.write_text('{}')
    with pytest.raises(ValueError, match='Memory artifact changed'):
        build(tmp_path)
