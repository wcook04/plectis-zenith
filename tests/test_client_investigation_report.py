"""Public custody, metered projection and exact offline client replay."""
from __future__ import annotations

from decimal import Decimal
import hashlib
import json
from pathlib import Path

import pytest

from research import client_investigation_study as study
from scripts import build_client_investigation_report as publication
from zenith.providers import digest, write_json


BATCH_QUERY = {'outer': True, 'initial': [1], 'steps': [[2, 2], [3]], 'continuation': 4}
TRANSFER_QUERY = {'outer': True, 'initial': [[1, 5], [2, 1]],
                  'steps': [[1, 2, 2], [1, 10, 1], [2, 1, 1]],
                  'continuation': [2, 1]}
SOURCE = '''def investigate(context, acquire):
    return {"query": None, "note": "no measured reason to continue"}
'''


@pytest.mark.parametrize('bundle_name', [
    'client-reuse-v1', 'client-reuse-v2', 'client-reuse-v2-low',
])
def test_canonical_published_report_is_in_verified_client_bundle(bundle_name):
    bundle = publication.ROOT/'examples/conformance'/bundle_name
    checked = publication.verify_manifest(bundle)
    assert checked['complete'] and checked['panel_opened']
    assert checked['calls'] == publication.read(bundle/'report.json')['model_attempts']


def _node(envelope):
    return publication._node(envelope)


def _save_budget(output: Path, prompts: dict, responses: dict):
    entries = {}
    for node, envelope in prompts.items():
        raw = responses.get(node)
        key = hashlib.sha256(node.encode()).hexdigest()
        entry = {'schema':'zenith_api_call_v1','call_id':key,'node_id':node,
                 'requested_model':'deepseek/offline-test','requested_provider_slug':'offline-test',
                 'status':'response_supplied' if raw is not None else 'failed',
                 'cost':'0.0001' if raw is not None else None,
                 'reserved_cost_usd':'0.001',
                 'prompt_sha256':hashlib.sha256(json.dumps(envelope['prompt'],ensure_ascii=False).encode()).hexdigest(),
                 'response_sha256':hashlib.sha256(raw.encode()).hexdigest() if raw is not None else None,
                 'provider_response':{'model':'offline-test','usage':{'prompt_tokens':3,'completion_tokens':4},
                                      'choices':[{'finish_reason':'stop'}]} if raw is not None else {},
                 'endpoint_metadata':{'private_request_header':'must not publish'},
                 'budget_dir':'/Users/private/budget',
                 'error':'transport interrupted' if raw is None else None}
        entries[key] = entry
    known = sum(e['cost'] is not None for e in entries.values())
    write_json(output/'budget'/'budget.json',{
        'schema':'zenith_shared_budget_v1','entries':entries,'halted':bool(known != len(entries)),
        'total_reported_cost_usd':str(Decimal('0.0001')*known),
        'total_reserved_usd':str(Decimal('0.001')*len(entries))})


def _run(tmp_path, *, fail=False, unbilled=False, prompt_version='v1'):
    output = tmp_path/'private-run'
    study.prepare_study(output,model='deepseek/offline-test',provider_slug='offline-test',
                        model_evidence={'source':'offline fixture; no inference'},prompt_version=prompt_version)
    prompts, responses = {}, {}
    count = 0
    def ask(envelope):
        nonlocal count
        count += 1
        node = _node(envelope)
        prompts[node] = envelope
        write_json(output/'prompts'/f'{node}.json',envelope)
        if fail and count == 1:
            raise RuntimeError('simulated provider failure')
        if envelope['phase'] == 'prepare':
            raw = json.dumps({'source':SOURCE,'scope':'ordinary static pilot'})
        elif envelope['prompt']['target_receipts']:
            raw = json.dumps({'queries':[],'note':None})
        else:
            query = BATCH_QUERY if envelope['prompt']['public_task']['family'] == 'batch' else TRANSFER_QUERY
            raw = json.dumps({'queries':[query],'note':None})
        responses[node] = raw
        write_json(output/'responses'/f'{node}.json',
                   {'raw':raw,'envelope_sha256':digest(envelope)})
        return raw
    frozen = study.execute_study(output,ask)
    if frozen['complete']:
        study.open_panel(output)
    if unbilled:
        prompts = {n:p for n,p in prompts.items() if n in responses}
    _save_budget(output,prompts,responses)
    return output, frozen


@pytest.mark.parametrize('prompt_version', ['v1', 'v2'])
def test_complete_export_is_allowlisted_and_replays_archived_source(tmp_path, prompt_version):
    private, frozen = _run(tmp_path,prompt_version=prompt_version)
    assert frozen['complete']
    published = tmp_path/'public'
    receipt = publication.export(private,published)
    assert receipt['archived_replay']['status'] == 'exact'
    assert receipt['archived_replay']['network_calls'] == 0
    assert receipt['calls'] > 0
    report = publication.read(published/'report.json')
    assert report['complete'] and report['protected_panel_opened']
    assert report['prepared_example_receipts'] == 10
    assert report['prepared_example_native_cost']['reference_calls'] == 10
    assert report['prepared_example_native_cost']['client_calls'] == 10
    assert report['policy_executions'] == 10
    assert report['metered_attempts'] == receipt['calls']
    assert report['targets']['transfer-b8']['fixed']['detected']
    assert not report['targets']['transfer-m6']['fixed']['detected']
    assert report['target_count'] == 5 and report['total_failing_targets'] == 4
    assert report['arm_metrics']['fixed']['failed_targets_detected'] == 4
    assert report['arm_metrics']['procedure']['halted_counts'] == {'policy_stop': 5}
    assert report['lifecycle']['all_provider']['attempts'] == report['metered_attempts']
    assert sum(phase['attempts'] for phase in report['lifecycle']['provider_by_phase'].values()) == report['metered_attempts']
    assert report['lifecycle']['native_cost']['protected_validation']['reference_calls'] == 400
    serialized = json.dumps(publication.read(published/'billing.json'))
    assert '/Users/' not in serialized and 'private_request_header' not in serialized
    assert 'prompt_tokens' in serialized
    assert not (published/'providers').exists() and not (published/'budget').exists()
    assert publication.replay(published)['archived_replay']['status'] == 'exact'
    with pytest.raises(ValueError,match='immutable'):
        publication.export(private,published)


def test_terminal_partial_export_retains_attempt_without_scoring(tmp_path):
    private, frozen = _run(tmp_path,fail=True,unbilled=True)
    assert not frozen['complete'] and frozen['active']
    published = tmp_path/'partial'
    receipt = publication.export(private,published)
    assert not receipt['complete']
    assert receipt['archived_replay']['status'] == 'partial_exact'
    assert receipt['calls'] == 1
    report = publication.read(published/'report.json')
    assert report['model_attempts'] == 1 and report['metered_attempts'] == 0
    assert not report['protected_panel_opened'] and report['panel'] is None
    assert not (published/'protected-panel.json').exists()


def test_export_rejects_orphan_response_and_changed_raw(tmp_path):
    private, _ = _run(tmp_path)
    write_json(private/'responses'/'orphan.json',{'raw':'{}','envelope_sha256':'x'})
    with pytest.raises(ValueError,match='membership'):
        publication.export(private,tmp_path/'rejected')
    (private/'responses'/'orphan.json').unlink()
    first = sorted((private/'responses').glob('*.json'))[0]
    payload = publication.read(first)
    payload['raw'] = '{}'
    write_json(first,payload)
    with pytest.raises(ValueError,match='Saved raw response'):
        publication.export(private,tmp_path/'rejected-raw')


def test_published_hash_and_membership_reject_tampering(tmp_path):
    private, _ = _run(tmp_path)
    published = tmp_path/'public'
    publication.export(private,published)
    (published/'prompts'/'new.json').write_text('{}')
    with pytest.raises(ValueError,match='hash/membership'):
        publication.replay(published)


def test_archived_native_scorer_rejects_rehashed_false_panel(tmp_path):
    private, _ = _run(tmp_path)
    published = tmp_path/'public'
    publication.export(private,published)
    panel = publication.read(published/'protected-panel.json')
    panel['target_clients']['transfer-b8']['correct'] = 0
    publication.write(published/'protected-panel.json',panel)
    report = publication.read(published/'report.json')
    report['panel'] = panel
    publication.write(published/'report.json',report)
    manifest = publication.read(published/'manifest.json')
    for name in ('protected-panel.json','report.json'):
        manifest['files'][name] = publication.sha(published/name)
    publication.write(published/'manifest.json',manifest)
    with pytest.raises(RuntimeError,match='protected panel differs'):
        publication.replay(published)


def test_behavior_replay_explicitly_excludes_only_engine_identity(tmp_path, monkeypatch):
    private, _ = _run(tmp_path)
    published = tmp_path/'public'
    publication.export(private,published)
    monkeypatch.setattr(publication, 'REPLAY_PROGRAM', publication.REPLAY_PROGRAM.replace(
        'import json,socket,sqlite3,sys',
        "import json,socket,sqlite3,sys\nsqlite3.sqlite_version='different-test-runtime'"))
    with pytest.raises(RuntimeError, match='differs from frozen scientific state'):
        publication.replay(published)
    receipt = publication.replay(published, mode='behavioral')['archived_replay']
    assert receipt['status'] == 'behavioral_match'
    assert receipt['environment_changed']
    assert receipt['ignored_runtime_fields'] == ['sqlite_version']
    assert receipt['network_calls'] == 0
    # A changed native behavior cannot be hidden by the engine-identity exception.
    monkeypatch.setattr(publication, 'REPLAY_PROGRAM', publication.REPLAY_PROGRAM.replace(
        "receipt=study.replay_study(out)",
        "from research.client_investigation_tasks import ProbeOracle\n"
        "old_ask=ProbeOracle.ask\n"
        "def wrong_ask(self,query):\n"
        "    row=old_ask(self,query)\n"
        "    row['cost']['reference_sql']+=1\n"
        "    return row\n"
        "ProbeOracle.ask=wrong_ask\n"
        "receipt=study.replay_study(out)"))
    with pytest.raises(RuntimeError, match='differs from frozen scientific state'):
        publication.replay(published, mode='behavioral')
