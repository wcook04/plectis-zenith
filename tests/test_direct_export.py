"""The public replay retains direct actions and one shared paid first turn."""
from copy import deepcopy
import hashlib
import json

from research import conformance_study as study
from scripts import build_conformance_report as publication
from tests.test_conformance_export import FixtureProvider, dataset, PARENT, LRU_REFERENCE


class DirectProvider(FixtureProvider):
    def ask_ai(self, prompt, options, cancel=None):
        node = options['meta']['node_id']
        # Reuse realistic settled billing, then bind it to the actual direct reply.
        raw = super().ask_ai(prompt, options, cancel)
        if '-turn-' in node:
            query = {'capacity':1, 'events':[{'op':'call','key':7}]}
            if node.endswith('turn-2'):
                query['events'].append({'op':'call','key':7})
            raw = json.dumps({'queries':[query], 'note':None})
            entry = self.entries[hashlib.sha256(node.encode()).hexdigest()]
            entry['response_sha256'] = hashlib.sha256(raw.encode()).hexdigest()
            entry['provider_receipt']['response_text'] = raw
            self.save_budget()
        return raw


def test_direct_public_export_binds_shared_calls_and_replays(tmp_path):
    private = tmp_path/'private'
    study.prepare(private, 'deepseek/deepseek-v4.1-flash', ['fixture/endpoint'],
                  arms=('direct_adaptive','direct_masked','repair_only'),
                  dataset=dataset(), workers=1, max_output_tokens=1024)
    provider = DirectProvider(private); provider.save_budget()
    study.run(private, provider_factory=lambda task,route: provider)
    study.evaluate(private, 'confirmation')
    public = tmp_path/'public'
    result = publication.export(private, public)
    assert result['complete']
    assert result['calls'] == 7
    assert len(list((public/'responses').glob('*shared*'))) == 1
    assert (public/'records/native-lru-0.json').is_file()
    checked = publication.replay(public)
    assert checked['ok'] and checked['model_calls_replayed'] == 7
    assert checked['protected_partitions'] == ['screen','confirmation']


def test_direct_export_rejects_changed_persisted_record(tmp_path):
    import pytest
    private = tmp_path/'private'
    study.prepare(private, 'deepseek/deepseek-v4.1-flash', ['fixture/endpoint'],
                  arms=('direct_batch',), dataset=dataset(), workers=1, max_output_tokens=1024)
    provider = DirectProvider(private); provider.save_budget()
    study.run(private, provider_factory=lambda task,route: provider)
    record = study.read(private/'records/native-lru-0.json')
    record['arms']['direct_batch']['investigation']['receipts'][0]['query']['capacity'] = 77
    study.write_json(private/'records/native-lru-0.json',record)
    with pytest.raises(ValueError, match='Durable task record'):
        publication.export(private,tmp_path/'public')
