"""Offline custody tests for complete native investigation exports."""
from copy import deepcopy
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import shutil
from zipfile import ZipFile, ZipInfo

import pytest

from research import conformance_study as study
from research.native_conformance_tasks import LRU_CONTRACT, LRU_REFERENCE
from scripts import build_conformance_report as publication

SECRET = 'sk-or-v1-privatefixturecredential0000000000000000'
PARENT = '''def investigate(context, acquire):
    calls = [e for e in context["events"] if e["op"] == "call"]
    return {"hits": 0, "misses": len(calls), "size": min(context["capacity"], len(calls))}
'''
QUERY = {'capacity': 1, 'events': [{'op':'call','key':7}, {'op':'call','key':7}]}
POLICY = '''def investigate(context, acquire):
    return {"query": {"capacity": 1, "events": [{"op": "call", "key": 7}, {"op": "call", "key": 7}]},
            "note": {"claim": "Check repeated calls in the same cache."}}
'''


def dataset():
    return {'schema':'offline-conformance-export-fixture', 'tasks':[{
        'id':'native-lru-0', 'source_id':'lru-0', 'contract':LRU_CONTRACT,
        'private':{'fixture':True}, 'reference_source':LRU_REFERENCE, 'parent_replicate':0,
        'examples':[{'input':{'capacity':1, 'events':[]}, 'expected':{'hits':0,'misses':0,'size':0}}],
        'fixed_queries':[deepcopy(QUERY)],
        'screen':[{'input':{'capacity':1,'events':[{'op':'call','key':22},{'op':'call','key':22}]},
                   'expected':{'hits':1,'misses':1,'size':1}}],
        'confirmation':[{'input':{'capacity':2,'events':[{'op':'call','key':23},{'op':'call','key':23},
                                                        {'op':'reset'},{'op':'call','key':23}]},
                         'expected':{'hits':0,'misses':1,'size':1}}],
    }]}


class FixtureProvider:
    def __init__(self, output):
        self.run_dir = output / 'providers/native-lru-0'
        self.output = output
        self.calls = []
        self.entries = {}

    def save_budget(self):
        study.write_json(self.output / 'budget/budget.json', {
            'total_reported_cost_usd':str(sum((Decimal(e['cost']) for e in self.entries.values() if e['cost'] is not None), Decimal(0))),
            'total_reserved_usd':str(sum((Decimal(e['reserved_cost_usd']) for e in self.entries.values()), Decimal(0))),
            'halted':any(e['status'] == 'failed' for e in self.entries.values()), 'entries':self.entries})

    def ask_ai(self, prompt, options, cancel=None):
        assert cancel is not None and not cancel.is_set()
        node = options['meta']['node_id']
        assert node not in [r['node'] for r in self.calls]
        source = PARENT if node.endswith('-parent') else POLICY if node.endswith('-policy') else LRU_REFERENCE
        raw = json.dumps({'source':source, 'scope':'Offline fixture.', 'change':'Fixture proposal.'})
        self.calls.append({'node':node, 'prompt':json.loads(prompt), 'options':deepcopy(options)})
        identity = hashlib.sha256(node.encode()).hexdigest()
        self.entries[identity] = {
            'call_id':identity, 'node_id':node, 'requested_model':'deepseek/deepseek-v4.1-flash',
            'requested_provider_slug':'fixture/endpoint', 'verified_provider_name':'Fixture',
            'actual_provider':'Fixture', 'status':'response_supplied', 'cost':'0.001',
            'reserved_cost_usd':'0.01', 'network_elapsed_seconds':0.1, 'reasoning_effort':'low',
            'prompt_sha256':hashlib.sha256(prompt.encode()).hexdigest(),
            'response_sha256':hashlib.sha256(raw.encode()).hexdigest(),
            'private_headers':{'Authorization':'Bearer ' + SECRET},
            'budget_dir':'/Users/private-account/private-budget',
            'provider_response':{'private_transport':SECRET, 'choices':[{'message':{'content':raw}}]},
            'provider_receipt':{'response_text':raw, 'endpoint':'https://private.example/keys/' + SECRET,
                                'usage':{'prompt_tokens':20,'completion_tokens':30,'total_tokens':50,
                                         'completion_tokens_details':{'reasoning_tokens':12},
                                         'untrusted_provider_text':SECRET}},
        }
        self.save_budget()
        return raw


@pytest.fixture(scope='module')
def completed(tmp_path_factory):
    root = tmp_path_factory.mktemp('conformance-export-fixture')
    output = root / 'private-study'
    study.prepare(output, 'deepseek/deepseek-v4.1-flash', ['fixture/endpoint'],
                  dataset=dataset(), arms=study.ARMS, workers=1, max_output_tokens=1024,
                  model_evidence={'authority':'offline fixture'})
    provider = FixtureProvider(output); provider.save_budget()
    study.run(output, provider_factory=lambda task, route:provider)
    study.evaluate(output, 'confirmation')
    for relative in ('.env', 'providers/native-lru-0/transport.json', 'prompts/provider-transport.json',
                     'responses/provider-transport.json', 'screen-private.json', 'confirmation-private.json'):
        path = output / relative; path.parent.mkdir(parents=True, exist_ok=True); path.write_text(SECRET)
    return output, provider


def rehash(output, name):
    manifest = study.read(output / 'manifest.json')
    manifest['files'][name] = publication.sha(output / name)
    study.write_json(output / 'manifest.json', manifest)


def test_export_copies_every_actual_call_and_excludes_private_transports(completed, tmp_path):
    source, provider = completed; output = tmp_path / 'public'
    result = publication.export(source, output)
    assert result['calls'] == len(provider.calls) == 6
    expected = set(publication.BASE_FILES) | {'billing.json'}
    for panel in publication.PANELS:
        expected.update(panel + suffix for suffix in ('.json','-selection.json','-summary.json'))
    nodes = {r['node'] for r in provider.calls}
    assert 'native-lru-0-parent' in nodes
    assert {'native-lru-0-ordinary-policy','native-lru-0-witness-policy'} <= nodes
    for directory in ('prompts','responses'):
        expected.update(f'{directory}/{node}.json' for node in nodes)
    manifest = study.read(output / 'manifest.json')
    assert set(manifest['files']) == expected
    for name, recorded in manifest['files'].items():
        assert publication.sha(output / name) == recorded
        if name != 'billing.json':
            assert (output / name).read_bytes() == (source / name).read_bytes()
    text = '\n'.join(p.read_text() for p in output.rglob('*.json'))
    for excluded in (SECRET, 'private_headers', 'provider_response', 'private_transport',
                     '/Users/private-account', 'https://private.example/keys/', 'untrusted_provider_text'):
        assert excluded not in text
    billing = study.read(output / 'billing.json')
    assert billing['entries'][0]['usage']['completion_tokens_details']['reasoning_tokens'] == 12
    assert {e['call_id'] for e in billing['entries']} == set(provider.entries)
    assert publication.verify_manifest(output)['calls'] == 6
    with pytest.raises(ValueError, match='immutable'):
        publication.export(source, output)


def test_archived_replay_works_without_original_study_or_live_runner(completed, tmp_path, monkeypatch):
    source, provider = completed; copy = tmp_path / 'private-copy'
    shutil.copytree(source, copy); output = tmp_path / 'public'
    publication.export(copy, output); shutil.rmtree(copy)
    def forbidden(*args, **kwargs):
        raise AssertionError('The current checkout must not provide the replay runner')
    monkeypatch.setattr(study, 'replay', forbidden)
    monkeypatch.setenv('OPENROUTER_API_KEY', SECRET)
    calls = len(provider.calls)
    assert publication.replay(output) == {
        'ok':True, 'model_calls_replayed':6, 'native_investigations':3,
        'protected_partitions':['screen','confirmation']}
    assert len(provider.calls) == calls


@pytest.mark.parametrize('mutation', ['replace','delete','add','symlink'])
def test_exact_manifest_rejects_modified_missing_extra_and_linked_payloads(completed, tmp_path, mutation):
    source, unused = completed; output = tmp_path / 'public'; publication.export(source, output)
    payload = output / 'responses/native-lru-0-parent.json'
    if mutation == 'replace': payload.write_text(payload.read_text() + ' ')
    elif mutation == 'delete': payload.unlink()
    elif mutation == 'add': (output / 'unlisted-transport.json').write_text(SECRET)
    else:
        payload.unlink(); payload.symlink_to(source / 'responses/native-lru-0-parent.json')
    with pytest.raises(ValueError, match='custody mismatch'):
        publication.replay(output)


def test_rehash_cannot_conceal_changed_actual_parent_response(completed, tmp_path):
    source, unused = completed; output = tmp_path / 'public'; publication.export(source, output)
    path = output / 'responses/native-lru-0-parent.json'
    row = study.read(path); row['raw'] += ' '; study.write_json(path, row)
    rehash(output, 'responses/native-lru-0-parent.json')
    with pytest.raises((ValueError, RuntimeError)):
        publication.replay(output)


@pytest.mark.parametrize('mutation', ['panel-summary','investigation-summary','billing-count','billing-total'])
def test_rehashed_claims_must_agree_with_individual_rows_receipts_and_calls(completed, tmp_path, mutation):
    source, unused = completed
    output = tmp_path / 'examples/conformance/fixture'; publication.export(source, output)
    if mutation in ('panel-summary','investigation-summary'):
        name = 'screen-summary.json'; row = study.read(output / name)
        if mutation == 'panel-summary':
            row['totals']['ordinary']['correct'] = 0
            row['by_task']['native-lru-0']['ordinary']['correct'] = 0
        else: row['detection']['ordinary']['native_probes'] += 1
    else:
        name = 'billing.json'; row = study.read(output / name)
        if mutation == 'billing-count': row['entries'].pop()
        else: row['total_reported_cost_usd'] = '0.007'
    study.write_json(output / name, row); rehash(output, name)
    with pytest.raises(ValueError): publication.campaign(tmp_path)
    with pytest.raises(ValueError): publication.replay(output)


@pytest.mark.parametrize('evidence', [
    {'api_key':SECRET}, {'authorization':'Bearer ' + SECRET},
    {'metadata_file':'/Users/private-account/private.env'},
])
def test_private_protocol_metadata_is_rejected_before_creating_export(completed, tmp_path, evidence):
    source, unused = completed; copy = tmp_path / 'copy'; shutil.copytree(source, copy)
    protocol = study.read(copy / 'protocol.json'); protocol['model_evidence'] = evidence
    study.write_json(copy / 'protocol.json', protocol)
    output = tmp_path / 'public'
    with pytest.raises(ValueError, match='private metadata'): publication.export(copy, output)
    assert not output.exists()


def test_absolute_source_locator_is_rejected_before_creating_export(completed, tmp_path):
    source, unused = completed; copy = tmp_path / 'copy'; shutil.copytree(source, copy)
    protocol = study.read(copy / 'protocol.json'); protocol['source']['path'] = '/Users/private/runtime-source.zip'
    study.write_json(copy / 'protocol.json', protocol)
    output = tmp_path / 'public'
    with pytest.raises(ValueError, match='portable relative'): publication.export(copy, output)
    assert not output.exists()


class FailingProvider(FixtureProvider):
    def ask_ai(self, prompt, options, cancel=None):
        node = options['meta']['node_id']
        if not node.endswith('-witness-repair'):
            return super().ask_ai(prompt, options, cancel)
        self.calls.append({'node':node, 'prompt':json.loads(prompt), 'options':deepcopy(options)})
        identity = hashlib.sha256(node.encode()).hexdigest()
        self.entries[identity] = {
            'call_id':identity, 'node_id':node, 'requested_model':'deepseek/deepseek-v4.1-flash',
            'requested_provider_slug':'fixture/endpoint', 'verified_provider_name':'Fixture',
            'actual_provider':'Fixture', 'status':'failed', 'cost':None,
            'reserved_cost_usd':'0.01', 'network_elapsed_seconds':0.1, 'reasoning_effort':'low',
            'prompt_sha256':hashlib.sha256(prompt.encode()).hexdigest(), 'response_sha256':None,
            'error':'Provider failure at https://private.example/keys/' + SECRET,
            'provider_response':{'usage':{'completion_tokens':12288,
                                          'completion_tokens_details':{'reasoning_tokens':12288}},
                                 'private_transport':SECRET},
        }
        self.save_budget()
        raise RuntimeError('Fixture paid response missing content')


def test_terminal_partial_export_preserves_orphan_response_and_failed_attempt(tmp_path):
    source = tmp_path / 'partial'
    study.prepare(source, 'deepseek/deepseek-v4.1-flash', ['fixture/endpoint'],
                  dataset=dataset(), arms=study.ARMS, workers=1, max_output_tokens=1024)
    provider = FailingProvider(source); provider.save_budget()
    result = study.run(source, provider_factory=lambda task, route:provider)
    assert not result['complete']
    output = tmp_path / 'public'; receipt = publication.export(source, output)
    assert receipt['complete'] is False
    assert receipt['calls'] == receipt['prompt_attempts'] == 5
    assert receipt['responses'] == 4
    assert not (output / 'screen.json').exists()
    orphan = 'native-lru-0-witness-policy'
    assert (output / 'responses' / (orphan + '.json')).read_bytes() == (source / 'responses' / (orphan + '.json')).read_bytes()
    billing = study.read(output / 'billing.json')
    failed = next(e for e in billing['entries'] if e['status'] == 'failed')
    assert failed['cost'] is None and failed['reserved_cost_usd'] == '0.01'
    assert failed['usage']['completion_tokens_details']['reasoning_tokens'] == 12288
    assert SECRET not in json.dumps(billing)
    replay = publication.replay(output)
    assert replay['complete'] is False
    assert replay['budget_attempts'] == 5 and replay['response_files_replayed'] == 4
    assert replay['known_cost_attempts'] == 4 and replay['unknown_cost_attempts'] == 1
    assert Decimal(replay['unknown_cost_reservations_usd']) == Decimal('0.01')
    assert replay['recorded_calls_replayed'] == 3 and replay['orphan_responses'] == 1
    assert replay['recorded_native_investigations'] == 1 and replay['protected_partitions'] == []
    # Rehashing cannot hide changes to an orphan output: it is bound to billing.
    path = output / 'responses' / (orphan + '.json')
    row = study.read(path); row['raw'] += ' '; study.write_json(path, row)
    rehash(output, str(path.relative_to(output)))
    with pytest.raises(ValueError, match='original output'):
        publication.replay(output)


def test_missing_final_freeze_recovers_exact_durable_records_without_inference(tmp_path):
    source = tmp_path / 'interrupted'
    study.prepare(source, 'deepseek/deepseek-v4.1-flash', ['fixture/endpoint'],
                  dataset=dataset(), arms=study.ARMS, workers=1, max_output_tokens=1024)
    provider = FailingProvider(source); provider.save_budget()
    study.run(source, provider_factory=lambda task, route:provider)
    (source / 'frozen.json').unlink(); (source / 'frozen-receipt.json').unlink()
    (source / '.env').write_text(SECRET)
    before = {str(p.relative_to(source)):publication.sha(p) for p in source.rglob('*') if p.is_file()}
    calls = len(provider.calls); output = tmp_path / 'public'
    result = publication.recover(source, output, reason='Fixture host could not write final metadata.')
    assert result['recovered_metadata'] and result['source_files_unchanged']
    assert result['calls'] == 5 and result['responses'] == 4
    assert result['known_cost_attempts'] == 4 and result['unknown_cost_attempts'] == 1
    assert len(provider.calls) == calls
    assert {str(p.relative_to(source)):publication.sha(p) for p in source.rglob('*') if p.is_file()} == before
    receipt = study.read(output / 'recovery.json')
    assert receipt['observed_missing'] == ['frozen.json','frozen-receipt.json']
    assert 'post-failure' in study.read(output / 'frozen.json')['recovery']['boundary'].lower()
    for name, recorded_hash in receipt['copied_source_files'].items():
        assert publication.sha(output / name) == recorded_hash == publication.sha(source / name)
        assert (output / name).read_bytes() == (source / name).read_bytes()
    assert study.read(output / 'frozen.json')['records'] == [study.read(source / 'records/native-lru-0.json')]
    assert SECRET not in '\n'.join(p.read_text() for p in output.rglob('*.json'))
    replay = publication.replay(output)
    assert replay['recovered_metadata'] and not replay['complete']
    assert replay['recorded_calls_replayed'] == 3 and replay['orphan_responses'] == 1
    assert replay['protected_partitions'] == []
    # The original per-task files remain separately bound even if somebody
    # legitimately refreshes the export manifest after an alteration.
    path = output / 'records/native-lru-0.json'; path.write_text(path.read_text() + ' ')
    rehash(output, str(path.relative_to(output)))
    with pytest.raises(ValueError, match='record custody'):
        publication.replay(output)


def test_recovery_cannot_replace_an_existing_freeze_or_hide_protected_results(completed, tmp_path):
    source, unused = completed
    with pytest.raises(ValueError, match='final metadata exists'):
        publication.recover(source, tmp_path / 'public')
    copy = tmp_path / 'damaged'; shutil.copytree(source, copy)
    (copy / 'frozen.json').unlink(); (copy / 'frozen-receipt.json').unlink()
    with pytest.raises(ValueError, match='Protected results already exist'):
        publication.recover(copy, tmp_path / 'public')


@pytest.mark.parametrize('member', ['../escape.py','/absolute.py','duplicate','symlink','credential'])
def test_source_archive_rejects_unsafe_members_and_credentials(tmp_path, member):
    path = tmp_path / 'source.zip'
    with ZipFile(path, 'w') as archive:
        if member == 'duplicate':
            archive.writestr('same.py', 'pass')
            with pytest.warns(UserWarning): archive.writestr('same.py', 'pass')
        elif member == 'symlink':
            info = ZipInfo('linked.py'); info.create_system = 3; info.external_attr = 0o120777 << 16
            archive.writestr(info, 'target.py')
        elif member == 'credential': archive.writestr('config.json', json.dumps({'api_key':SECRET}))
        else: archive.writestr(member, 'pass')
    with pytest.raises(ValueError, match='Unsafe|private metadata'): publication.archive_members(path)
