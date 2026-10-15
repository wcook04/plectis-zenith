"""Public scientific custody and archived replay, using no live provider."""
from copy import deepcopy
import json
from pathlib import Path
import shutil

import pytest

from research import decomposition_study as study
from scripts import build_decomposition_report as publication


INITIAL = '''def focus(value):
    return 0

def investigate(context, acquire):
    return focus(context["value"])
'''
CORRECT = INITIAL.replace('return 0', 'return value + 1')
TRANSPORT_SECRET = 'sk-or-v1-privatefixturecredential0000000000000000'


def dataset():
    return {'schema': 'offline-export-fixture', 'tasks': [{
        'id': 'task-0', 'family': 'fixture', 'description': 'Return the observed integer response.',
        'initial_source': INITIAL, 'focus_function': 'focus',
        'private': {'kind': 'fixture', 'reference_source': CORRECT},
        'calibration': [{'input': {'value': 0}, 'expected': 1}],
        'development': [{'input': {'value': 1}, 'expected': 2}],
        'screen': [{'input': {'value': 11}, 'expected': 12}],
        'confirmation': [{'input': {'value': 21}, 'expected': 22}],
    }]}


class FixtureProvider:
    def __init__(self, root):
        self.run_dir = Path(root)
        self.calls = []
        self.entries = {}

    def ask_ai(self, prompt, options, cancel=None):
        assert cancel is not None and not cancel.is_set()
        node = options['meta']['node_id']
        raw = json.dumps({'source': CORRECT, 'scope': 'Offline fixture only.', 'change': 'Fixture response.'})
        self.calls.append((json.loads(prompt), deepcopy(options)))
        self.entries[node] = {
            'node_id': node, 'requested_model': 'deepseek/deepseek-v4.1-flash',
            'requested_provider_slug': 'fixture/endpoint', 'verified_provider_name': 'Fixture',
            'actual_provider': 'Fixture', 'status': 'response_supplied',
            'cost': '0.001', 'reserved_cost_usd': '0.01', 'network_elapsed_seconds': 0.1,
            'private_headers': {'Authorization': 'Bearer ' + TRANSPORT_SECRET},
            'budget_dir': '/Users/private-account/private-budget',
            'provider_response': {'private_transport': TRANSPORT_SECRET,
                                  'choices': [{'message': {'content': raw}}]},
            'provider_receipt': {
                'response_text': raw, 'endpoint': 'https://private.example/keys/' + TRANSPORT_SECRET,
                'usage': {'prompt_tokens': 20, 'completion_tokens': 30, 'total_tokens': 50,
                          'completion_tokens_details': {'reasoning_tokens': 12}, 'cost': 0.001},
            },
        }
        return raw


@pytest.fixture(scope='module')
def completed(tmp_path_factory):
    root = tmp_path_factory.mktemp('decomposition-export-fixture')
    output = root / 'private-study'
    study.prepare(output, 'deepseek/deepseek-v4.1-flash', ['fixture/endpoint'],
                  dataset=dataset(), arms=('global',), proposals=2, workers=1,
                  max_output_tokens=1024, model_evidence={'authority': 'offline fixture'})
    provider = FixtureProvider(root / 'private-provider')
    study.run(output, provider_factory=lambda task, route: provider)
    study.evaluate(output, 'confirmation')
    study.write_json(output / 'budget' / 'budget.json', {
        'total_reported_cost_usd': '0.002', 'total_reserved_usd': '0.02',
        'halted': False, 'entries': provider.entries,
    })
    for relative in ('.env', 'providers/task-0/transport.json', 'prompts/.env',
                     'prompts/provider-transport.json', 'responses/.env',
                     'responses/provider-transport.json', 'screen-transport.json',
                     'confirmation-private.json'):
        path = output / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(TRANSPORT_SECRET)
    return output, provider


def test_export_has_exact_scientific_allowlist_and_original_content(completed, tmp_path):
    source, provider = completed
    output = tmp_path / 'public'
    result = publication.export(source, output)
    assert result['calls'] == len(provider.calls) == 2
    manifest = study.read(output / 'manifest.json')
    expected = {'protocol.json', 'datasets.json', 'preparation.json', 'frozen.json',
                'frozen-receipt.json', 'runtime-source.zip', 'billing.json'}
    for panel in ('screen', 'confirmation'):
        expected.update(panel + suffix for suffix in ('.json', '-selection.json', '-summary.json'))
    for directory in ('prompts', 'responses'):
        expected.update(f'{directory}/task-0-global-{round}.json' for round in range(2))
    assert set(manifest['files']) == expected
    assert result['files'] == len(expected)
    for relative, recorded_hash in manifest['files'].items():
        assert publication.sha(output / relative) == recorded_hash
        if relative != 'billing.json':
            assert (output / relative).read_bytes() == (source / relative).read_bytes()
    json_text = '\n'.join(path.read_text() for path in output.rglob('*.json'))
    for private in (TRANSPORT_SECRET, 'private_headers', 'provider_response', 'private_transport',
                    '/Users/private-account', 'https://private.example/keys/'):
        assert private not in json_text
    assert study.read(output / 'protocol.json')['source']['path'] == 'runtime-source.zip'
    billing = study.read(output / 'billing.json')
    assert billing['entries'][0]['usage']['completion_tokens'] == 30
    assert billing['entries'][0]['usage']['completion_tokens_details']['reasoning_tokens'] == 12
    with pytest.raises(ValueError, match='immutable'):
        publication.export(source, output)


def test_archive_replay_succeeds_after_original_records_are_removed(completed, tmp_path, monkeypatch):
    original, provider = completed
    copied = tmp_path / 'private-copy'
    shutil.copytree(original, copied)
    output = tmp_path / 'public'
    publication.export(copied, output)
    shutil.rmtree(copied)

    def forbidden_live_replay(*args, **kwargs):
        raise AssertionError('live checkout replay must not run')

    monkeypatch.setattr(study, 'replay', forbidden_live_replay)
    calls_before = len(provider.calls)
    result = publication.replay(output)
    assert result == {'ok': True, 'construction_attempts': 2,
                      'protected_partitions': ['screen', 'confirmation']}
    assert len(provider.calls) == calls_before


@pytest.mark.parametrize('mutation', ['replace', 'delete', 'add'])
def test_exact_manifest_rejects_modified_missing_and_extra_payloads(completed, tmp_path, mutation):
    source, provider = completed
    output = tmp_path / 'public'
    publication.export(source, output)
    payload = output / 'responses' / 'task-0-global-0.json'
    if mutation == 'replace':
        payload.write_text(payload.read_text() + ' ')
    elif mutation == 'delete':
        payload.unlink()
    else:
        (output / 'unlisted-transport.json').write_text(TRANSPORT_SECRET)
    with pytest.raises(ValueError, match='custody mismatch'):
        publication.replay(output)


def test_rebinding_manifest_cannot_conceal_changed_original_response(completed, tmp_path):
    source, provider = completed
    output = tmp_path / 'public'
    publication.export(source, output)
    payload = output / 'responses' / 'task-0-global-0.json'
    row = study.read(payload)
    row['raw'] += ' '
    study.write_json(payload, row)
    manifest = study.read(output / 'manifest.json')
    manifest['files'][str(payload.relative_to(output))] = publication.sha(payload)
    study.write_json(output / 'manifest.json', manifest)
    with pytest.raises(RuntimeError):
        publication.replay(output)


@pytest.mark.parametrize('evidence', [
    {'api_key': TRANSPORT_SECRET},
    {'authorization': 'Bearer ' + TRANSPORT_SECRET},
    {'metadata_file': '/Users/private-account/private.env'},
])
def test_private_model_selection_metadata_is_rejected_before_publication(completed, tmp_path, evidence):
    source, provider = completed
    copied = tmp_path / 'private-copy'
    shutil.copytree(source, copied)
    protocol = study.read(copied / 'protocol.json')
    protocol['model_evidence'] = evidence
    study.write_json(copied / 'protocol.json', protocol)
    output = tmp_path / 'public'
    with pytest.raises(ValueError, match='private metadata'):
        publication.export(copied, output)
    assert not output.exists()


def test_private_absolute_runtime_locator_is_rejected(completed, tmp_path):
    source, provider = completed
    copied = tmp_path / 'private-copy'
    shutil.copytree(source, copied)
    protocol = study.read(copied / 'protocol.json')
    protocol['source']['path'] = '/Users/private-account/private-study/runtime-source.zip'
    study.write_json(copied / 'protocol.json', protocol)
    output = tmp_path / 'public'
    with pytest.raises(ValueError, match='portable relative'):
        publication.export(copied, output)
    assert not output.exists()


def test_rehashed_summary_cannot_change_published_campaign_outcomes(completed, tmp_path):
    source, provider = completed
    output = tmp_path / 'examples' / 'decomposition' / 'fixture'
    publication.export(source, output)
    # Custody of these bytes can be legitimately refreshed while their claims
    # disagree with the unchanged individual protected outcomes. File hashes
    # alone therefore cannot certify the campaign's reported accuracy.
    summary_path = output / 'screen-summary.json'
    summary = study.read(summary_path)
    assert summary['totals']['global']['correct'] == 1
    summary['totals']['global']['correct'] = 0
    summary['tasks']['task-0']['global']['correct'] = 0
    study.write_json(summary_path, summary)
    manifest = study.read(output / 'manifest.json')
    manifest['files']['screen-summary.json'] = publication.sha(summary_path)
    study.write_json(output / 'manifest.json', manifest)
    with pytest.raises((ValueError, RuntimeError)):
        publication.campaign(tmp_path)
    with pytest.raises((ValueError, RuntimeError)):
        publication.replay(output)
