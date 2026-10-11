"""Scientific boundaries exercise the real admitted-event replay evaluator."""
from concurrent.futures import ThreadPoolExecutor
import copy
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest import mock

from research import engine

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / 'examples/experiments/offline'


class ResearchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.inputs = self.root / 'input'
        self.inputs.mkdir()
        for name in ('calculator.json', 'prices.json', 'spec.json'):
            (self.inputs / name).write_bytes((EXAMPLE / name).read_bytes())
        self.spec_path = self.inputs / 'spec.json'
        self.study = self.root / 'study'

    def freeze(self, **changes):
        spec = engine.read_json(self.spec_path)
        spec.update(changes)
        engine.write_json(self.spec_path, spec)
        return engine.freeze(self.spec_path, self.study)

    def candidate(self, code):
        path = self.root / 'custom.py'
        path.write_text(code)
        return path

    def attempt(self, candidate='baseline.py', key='baseline', **kwargs):
        path = candidate if isinstance(candidate, Path) else EXAMPLE / candidate
        return engine.trial(self.study, path, key=key, hypothesis='test hypothesis',
                            change='test declared change', **kwargs)

    def test_actual_evaluator_baseline_keep_discard_final(self):
        frozen = self.freeze()
        self.assertEqual(frozen['membership_counts'], {'development': 4, 'purged': 1, 'holdout': 2})
        baseline = self.attempt(prompt=b'original prompt')
        self.assertEqual(baseline['decision'], 'baseline')
        self.assertEqual(baseline['result']['score'], .41)
        improved = self.attempt('shrink.py', key='shrink', prompt=b'candidate prompt')
        self.assertEqual(improved['decision'], 'keep')
        self.assertEqual(improved['result']['score'], .3284)
        self.assertEqual(improved['result']['event_keys'], baseline['result']['event_keys'])
        envelope = engine.read_json(self.study / 'attempts/2/candidate/envelope.json')
        self.assertEqual(envelope['metadata']['tool'], 'finance_historical_replay')
        self.assertFalse(envelope['data']['experiment_ledger']['variant_decision']['calculator_mutation_permission'])
        self.assertTrue((self.study / 'attempts/2/promotion-proposal.json').exists())
        self.assertEqual(self.attempt('baseline.py', key='loser')['decision'], 'discard')
        final = engine.finalize(self.study, key='sealed-final')
        self.assertEqual(final['decision'], 'final_report')
        self.assertEqual(final['provenance']['prompt_hash'], improved['provenance']['prompt_hash'])
        self.assertEqual(final['result']['counts']['resolved'], 2)
        self.assertEqual(engine.finalize(self.study, key='sealed-final')['attempt'], 4)
        with self.assertRaisesRegex(ValueError, 'already consumed'):
            engine.finalize(self.study, key='new-final')
        with self.assertRaisesRegex(ValueError, 'sealed'):
            self.attempt(key='post-final')

    def test_candidate_projection_excludes_truth_holdout_and_provider_fields(self):
        artifact = engine.read_json(self.inputs / 'calculator.json')
        for card in engine.cards_in(artifact):
            card['future_return'] = 9999
            card['provider_prompt'] = 'secret'
        engine.write_json(self.inputs / 'calculator.json', artifact)
        self.freeze()
        result = self.attempt()
        rows = engine.read_json(self.study / 'attempts/1/candidate-input.json')
        self.assertEqual(len(rows), 4)
        self.assertTrue(all(set(r) == {'forecast_id', 'subject_as_of', 'direction', 'probability'} for r in rows))
        self.assertEqual(result['state'], 'complete')
        self.assertFalse(any(r['subject_as_of'].startswith('2025-02') for r in rows))

    def test_future_availability_and_split_week_rejected_before_execution(self):
        artifact = engine.read_json(self.inputs / 'calculator.json')
        artifact['data']['candidate_forecast_cards'][0]['identity']['available_at'] = '2025-01-07T00:00:00+00:00'
        engine.write_json(self.inputs / 'calculator.json', artifact)
        with self.assertRaisesRegex(ValueError, 'available at event'):
            self.freeze()
        self.assertFalse(self.study.exists())

    def test_week_boundary_cannot_split_group(self):
        artifact = engine.read_json(self.inputs / 'calculator.json')
        extra = copy.deepcopy(artifact['data']['candidate_forecast_cards'][-2])
        extra['identity']['forecast_id'] = 'extra-group-member'
        extra['identity']['as_of'] = extra['identity']['available_at'] = '2025-02-11T00:00:00+00:00'
        artifact['data']['candidate_forecast_cards'].append(extra)
        engine.write_json(self.inputs / 'calculator.json', artifact)
        with self.assertRaisesRegex(ValueError, 'clustered calendar week'):
            self.freeze(holdout_start='2025-02-11T00:00:00+00:00')

    def test_all_failed_attempts_spend_budget_and_are_durable(self):
        self.freeze(max_trials=2)
        bad = self.candidate("raise RuntimeError('intentional fixture failure')\n")
        first = self.attempt(bad, key='crash')
        self.assertEqual(first['state'], 'error')
        self.assertTrue((self.study / 'attempts/1/receipt.json').exists())
        second = self.attempt(self.root / 'missing.py', key='missing')
        self.assertEqual(second['state'], 'error')
        self.assertEqual(engine.status(self.study)['development_attempts'], 2)
        with self.assertRaisesRegex(ValueError, 'budget exhausted'):
            self.attempt(key='over-budget')

    def test_missing_prompt_input_error_is_a_spent_attempt(self):
        self.freeze()
        result = self.attempt(input_error='prompt file unavailable')
        self.assertEqual(result['state'], 'error')
        self.assertEqual(result['provenance']['input_error'], 'prompt file unavailable')
        self.assertEqual(engine.status(self.study)['development_attempts'], 1)

    def test_timeout_is_recorded(self):
        self.freeze(timeout_seconds=.2)
        slow = self.candidate('import time\ntime.sleep(10)\n')
        result = self.attempt(slow, key='timeout')
        self.assertEqual(result['decision'], 'error')
        self.assertIn('timed out', result['error'])
        self.assertEqual(engine.status(self.study)['development_attempts'], 1)

    def test_data_mutation_recorded_as_failed_attempt(self):
        self.freeze()
        path = self.study / 'inputs/prices.json'
        path.write_text('{}')
        result = self.attempt()
        self.assertEqual(result['state'], 'error')
        self.assertIn('input hash mismatch', result['error'])
        self.assertEqual(engine.status(self.study)['development_attempts'], 1)

    def test_spec_mutation_rejected(self):
        self.freeze()
        spec = engine.read_json(self.study / 'frozen.json')
        spec['minimum_improvement'] = -100
        engine.write_json(self.study / 'frozen.json', spec)
        with self.assertRaisesRegex(ValueError, 'spec hash mismatch'):
            self.attempt()

    def test_evaluator_mutation_recorded_as_failed_attempt(self):
        self.freeze()
        with mock.patch.object(engine, 'evaluator_hashes', return_value={'tampered': 'hash'}):
            result = self.attempt()
        self.assertIn('source hash mismatch', result['error'])

    def test_invalid_probability_not_accepted_as_score(self):
        self.freeze()
        bad = self.candidate("print('[NaN, 0.5, 0.5, 0.5]')\n")
        result = self.attempt(bad, key='invalid')
        self.assertIn('finite numbers', result['error'])
        score = self.candidate("print('{\"mean_brier\": 0.0}')\n")
        result = self.attempt(score, key='fake-score')
        self.assertIn('one probability per frozen event', result['error'])

    def test_concurrent_same_key_and_resume_count_once(self):
        self.freeze()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: self.attempt(), range(2)))
        self.assertEqual(engine.status(self.study)['development_attempts'], 1)
        self.assertTrue(any(r.get('decision') == 'baseline' for r in results))
        self.assertEqual(self.attempt()['attempt'], 1)
        with self.assertRaisesRegex(ValueError, 'different candidate'):
            self.attempt('shrink.py')

    def test_baseline_first_and_holdout_failure_consumes_seal(self):
        self.freeze()
        rejected = self.attempt('shrink.py', key='too-soon')
        self.assertEqual(rejected['state'], 'error')
        self.assertIn('baseline', rejected['error'])
        self.attempt()
        (self.study / 'inputs/prices.json').write_text('{}')
        result = engine.finalize(self.study, key='fail-final')
        self.assertEqual(result['state'], 'error')
        self.assertTrue(engine.status(self.study)['holdout_consumed'])
        with self.assertRaisesRegex(ValueError, 'already consumed'):
            engine.finalize(self.study, key='retry-final')

    def test_champion_follows_completion_not_reservation_order(self):
        self.freeze()
        self.attempt()
        slow = self.root / 'slow.py'
        slow.write_text("import json,sys,time\nrows=json.load(sys.stdin)\ntime.sleep(.5)\njson.dump([.5 for _ in rows],sys.stdout)\n")
        fast = self.root / 'fast.py'
        fast.write_text("import json,sys\nrows=json.load(sys.stdin)\njson.dump([.6 for _ in rows],sys.stdout)\n")
        with ThreadPoolExecutor(max_workers=2) as pool:
            slow_future = pool.submit(self.attempt, slow, key='slow')
            limit = time.monotonic() + 2
            while engine.status(self.study)['development_attempts'] < 2:
                self.assertLess(time.monotonic(), limit)
                time.sleep(.01)
            fast_future = pool.submit(self.attempt, fast, key='fast')
            self.assertEqual(fast_future.result()['decision'], 'keep')
            self.assertEqual(slow_future.result()['decision'], 'keep')
        with engine.connect(self.study) as db:
            self.assertEqual(engine.champion(db)['id'], 2)
        final = engine.finalize(self.study, key='final-order-check')
        self.assertEqual(final['result']['score'], .25)

    def test_interrupted_owner_recovery_keeps_attempt_spent(self):
        self.freeze(max_trials=1)
        with mock.patch.object(engine, 'source_commit', return_value=None):
            with mock.patch.object(engine.subprocess, 'Popen', side_effect=KeyboardInterrupt):
                with self.assertRaises(KeyboardInterrupt):
                    self.attempt()
        self.assertEqual(engine.status(self.study)['trials'][0]['state'], 'running')
        self.assertEqual(engine.recover(self.study)['recovered_attempts'], [])
        with mock.patch.object(engine.os, 'kill', side_effect=ProcessLookupError):
            self.assertEqual(engine.recover(self.study)['recovered_attempts'], [1])
        self.assertEqual(engine.status(self.study)['trials'][0]['state'], 'error')
        self.assertTrue((self.study / 'attempts/1/receipt.json').exists())
        with self.assertRaisesRegex(ValueError, 'budget exhausted'):
            self.attempt(key='after-interruption')

    def test_frozen_intervention_artifact_linkage(self):
        (self.inputs / 'node-skill.md').write_text('Frozen upstream node instructions')
        intervention = {'parameter_kind': 'node_skill', 'node_ids': ['oracle'],
                        'incoming_edge_ids': ['calculator-to-oracle'], 'source_artifacts': ['node-skill.md']}
        self.freeze(intervention=intervention)
        spec, _ = engine.binding(self.study)
        self.assertEqual(spec['intervention']['node_ids'], ['oracle'])
        ref = spec['intervention']['source_artifacts'][0]
        self.assertEqual(ref['sha256'], engine.digest_bytes((self.inputs / 'node-skill.md').read_bytes()))
        (self.study / ref['path']).write_text('changed after freezing')
        result = self.attempt()
        self.assertIn('input hash mismatch', result['error'])


if __name__ == '__main__':
    unittest.main()
