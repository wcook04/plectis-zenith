"""Native full-ancestor CP2 forecasts, not submitted scores, drive comparisons."""
import copy
from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import unittest

from feedback.demo import fixture_policy, fixture_run
from research import cohort
from research.engine import read_json, write_json
from zenith import runtime


class CohortTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.study = self.base / 'cohort'
        self.policy = fixture_policy(self.base / 'policy.json')
        self.first = datetime(2026, 1, 5, 20, tzinfo=timezone.utc)

    def prepare(self, count=1, holdout=0, truth=True, **changes):
        issues, rows = [], []
        for index in range(count + holdout):
            issue = self.first + timedelta(days=7 * index)
            horizon = issue + timedelta(days=1)
            feed = self.base / f'feed-{index}'
            write_json(feed / 'runtime_context.json', {'as_of': issue.isoformat()})
            write_json(feed / 'artifacts/global_stock_feed.json', {'status': 'success',
                'metadata': {'status': 'success', 'price_basis': 'synthetic_point_quote', 'currency': 'USD', 'synthetic_fixture': True},
                'data': {'columns': ['Ticker', 'Price', 'timestamp'], 'rows': [['XOM', 100.0, issue.isoformat()]]}})
            issues.append({'issue_id': f'issue-{index}', 'feed_source': str(feed), 'time_anchor': issue.isoformat(),
                'target_time': horizon.isoformat(), 'horizon_id': '24h', 'target_ids': ['XOM'],
                'split': 'development' if index < count else 'holdout'})
            if truth:
                rows.append({'target_id': 'XOM', 'timestamp': horizon.isoformat(), 'price': 101.0})
        write_json(self.base / 'truth.json', {'metadata': {'status': 'success', 'price_basis': 'synthetic_point_quote',
            'currency': 'USD', 'synthetic_fixture': True}, 'data': {'rows': rows}})
        candidate = {'candidate_id': 'baseline', 'hypothesis': 'fixed fixture baseline', 'change': 'none',
            'source_commit': 'offline-fixture', 'model': 'offline-synthetic-fixture', 'execution_kind': 'captured_replay',
            'provider': 'captured', 'graph_variant': None, 'reasoning_policy': None,
            'context_profile': 'original', 'prompt_sha256': '0' * 64}
        other = dict(candidate, candidate_id='candidate', hypothesis='fixed fixture target correction', change='synthetic target fixture')
        raw = {'schema': cohort.SCHEMA, 'issues': issues, 'candidates': [candidate, other], 'feedback_policy': str(self.policy),
            'truth_source': str(self.base / 'truth.json'), 'truth_as_of': '2027-01-01T00:00:00+00:00',
            'max_trials': 2, 'max_calls_per_run': 100, 'minimum_improvement': .001, 'embargo_days': 1}
        raw.update(changes)
        path = self.base / 'spec.json'
        write_json(path, raw)
        cohort.freeze(path, self.study)
        self.spec = read_json(self.study / 'cohort.json')
        return self.spec

    def run_fixture(self, candidate_id='baseline', index=0, pending=False, target=None):
        candidate, issue = cohort.select(self.spec, candidate_id, f'issue-{index}')
        run = self.base / f'{candidate_id}-{index}'
        fixture_run(run, datetime.fromisoformat(issue['time_anchor']), datetime.fromisoformat(issue['target_time']),
                    target=target if target is not None else 110.0 if candidate_id == 'baseline' else 101.0)
        source = (self.study / issue['feed_source']).resolve()
        manifest = read_json(run / 'zenith_run.json')
        manifest.update(schema='zenith_execution_manifest_v1', target='lab_director', model=candidate['model'],
            feed_source=str(source), source_hashes=runtime._source_hashes([source]), context_profile='original',
            implementation_hashes=runtime.implementation_hashes())
        write_json(run / 'zenith_run.json', manifest)
        cp2 = run / 'artifacts/lab_director.json'
        for node in candidate['scope']:
            if node != 'lab_director':
                write_json(run / 'artifacts' / f'{node}.json', {'status': 'success', 'data': {}})
        (run / 'artifacts/global_stock_feed.json').write_bytes((source / 'artifacts/global_stock_feed.json').read_bytes())
        template = read_json(run / 'handoff/receipts/fixture.json')
        template.update(actual_model=candidate['actual_model'], requested_model=candidate['model'])
        write_json(run / 'handoff/receipts/fixture.json', template)
        for node in candidate['reasoner_scope']:
            if node != 'lab_director':
                write_json(run / 'handoff/receipts' / f'{node}.json', dict(template, node_id=node))
        if pending:
            cp2.unlink()
        return run

    def attach(self, candidate='baseline', index=0, **kwargs):
        run = self.run_fixture(candidate, index, **kwargs)
        return cohort.attach(self.study, candidate_id=candidate, issue_id=f'issue-{index}', run=run)

    def test_real_cp2_comparison_twenty_issues_gate_and_idempotency(self):
        self.prepare(20, holdout=1)
        for index in range(20):
            for candidate in ('baseline', 'candidate'):
                self.assertEqual(self.attach(candidate, index)['state'], 'complete')
        result = cohort.evaluate(self.study)
        self.assertEqual(result['issue_count'], 20)
        self.assertEqual(result['clustered_weeks'], 20)
        self.assertAlmostEqual(result['scores']['baseline'], 9 / 101)
        self.assertEqual(result['scores']['candidate'], 0.0)
        self.assertEqual(result['decisions']['candidate'], 'candidate_proposal')
        self.assertFalse(result['live_mutation_permission'])
        self.assertTrue(result['synthetic_fixture'])
        self.assertTrue(cohort.attach(self.study, candidate_id='candidate', issue_id='issue-0',
            run=self.base / 'candidate-0')['idempotent'])
        self.attach('baseline', 20)
        self.attach('candidate', 20)
        final = cohort.evaluate(self.study, final_key='final-complete')
        self.assertEqual(final['state'], 'complete')
        self.assertEqual(final['phase'], 'holdout')
        self.assertEqual(final['development_selected_candidate'], 'candidate')

    def test_same_frozen_input_bytes_at_original_location_are_importable(self):
        self.prepare()
        run = self.run_fixture()
        manifest = read_json(run / 'zenith_run.json')
        source = self.base / 'feed-0'
        manifest.update(feed_source=str(source), source_hashes=runtime._source_hashes([source]))
        write_json(run / 'zenith_run.json', manifest)
        self.assertEqual(cohort.attach(self.study, candidate_id='baseline', issue_id='issue-0', run=run)['state'], 'complete')

    def test_pending_native_and_truth_do_not_select_partial_support(self):
        self.prepare(2)
        self.attach('baseline', 0)
        self.attach('candidate', 0)
        self.attach('baseline', 1)
        self.assertEqual(self.attach('candidate', 1, pending=True)['state'], 'pending')
        result = cohort.evaluate(self.study)
        self.assertEqual(result['state'], 'pending')
        self.assertIsNone(result['scores'])
        self.assertIn('candidate/issue-1', result['pending_support'])
        run = self.run_fixture('candidate', 1)
        self.assertEqual(cohort.attach(self.study, candidate_id='candidate', issue_id='issue-1', run=run)['state'], 'complete')
        self.assertEqual(cohort.evaluate(self.study)['decisions']['candidate'], 'insufficient_issues')

    def test_missing_truth_remains_pending(self):
        self.prepare(truth=False)
        self.attach('baseline')
        self.attach('candidate')
        result = cohort.evaluate(self.study)
        self.assertEqual(result['state'], 'pending')
        self.assertTrue(all(key.endswith(':truth') for key in result['pending_support']))

    def test_manifest_model_wronginput_horizon_and_receipts_refused_durably(self):
        self.prepare()
        for field, value in [('model', 'different'), ('horizon', '2026-01-08T20:00:00+00:00'), ('feed_source', '/wrong')]:
            run = self.run_fixture()
            manifest = read_json(run / 'zenith_run.json')
            manifest[field] = value
            write_json(run / 'zenith_run.json', manifest)
            result = cohort.attach(self.study, candidate_id='baseline', issue_id='issue-0', run=run)
            self.assertEqual(result['state'], 'error')
            self.assertTrue((self.study / 'imports' / f"{result['attempt']}.json").exists())
        run = self.run_fixture()
        receipt = read_json(run / 'handoff/receipts/fixture.json')
        receipt['actual_model'] = 'different'
        write_json(run / 'handoff/receipts/fixture.json', receipt)
        self.assertEqual(cohort.attach(self.study, candidate_id='baseline', issue_id='issue-0', run=run)['state'], 'error')
        run = self.run_fixture()
        node = next(n for n in self.spec['candidates'][0]['reasoner_scope'] if n != 'lab_director')
        receipt_path = run / 'handoff/receipts' / f'{node}.json'
        receipt = read_json(receipt_path)
        receipt['actual_model'] = 'routed-different-model'
        write_json(receipt_path, receipt)
        result = cohort.attach(self.study, candidate_id='baseline', issue_id='issue-0', run=run)
        self.assertEqual(result['state'], 'error')
        self.assertIn('model lineage', result['error'])

    def test_wrong_complete_target_support_and_failed_node_refused(self):
        self.prepare()
        run = self.run_fixture()
        cp2_path = run / 'artifacts/lab_director.json'
        cp2 = read_json(cp2_path)
        extra = dict(cp2['data']['predictions_t'][0], target_id='MISSING')
        cp2['data']['predictions_t'].append(extra)
        write_json(cp2_path, cp2)
        self.assertEqual(cohort.attach(self.study, candidate_id='baseline', issue_id='issue-0', run=run)['state'], 'error')
        run = self.run_fixture()
        write_json(cp2_path, {'status': 'failure', 'metadata': {'error': 'native provider timeout'}})
        result = cohort.attach(self.study, candidate_id='baseline', issue_id='issue-0', run=run)
        self.assertEqual(result['state'], 'error')
        self.assertIn('native node failed', result['error'])

    def test_mutated_input_output_and_preregistered_trial_budget_refused(self):
        self.prepare()
        accepted = self.attach()
        self.assertEqual(accepted['state'], 'complete')
        write_json(self.base / 'baseline-0/artifacts/lab_director.json', {'arbitrary_score': 0})
        with self.assertRaisesRegex(ValueError, 'outputs changed'):
            cohort.evaluate(self.study)
        frozen_input = self.study / self.spec['issues'][0]['feed_source'] / 'artifacts/global_stock_feed.json'
        frozen_input.write_text('{}')
        with self.assertRaisesRegex(ValueError, 'input or candidate changed'):
            cohort.evaluate(self.study)
        other = self.base / 'other'
        raw = read_json(self.base / 'spec.json')
        raw['max_trials'] = 1
        write_json(self.base / 'spec.json', raw)
        with self.assertRaisesRegex(ValueError, 'trial budget'):
            cohort.freeze(self.base / 'spec.json', other)

    def test_complete_target_support_and_audited_calls_required(self):
        self.prepare(max_calls_per_run=1)
        result = self.attach()
        self.assertEqual(result['state'], 'error')
        self.assertIn('call budget', result['error'])

    def test_next_commands_preserve_frozen_native_arguments_without_calls(self):
        self.prepare()
        result = cohort.next_actions(self.study)
        self.assertEqual(len(result['actions']), 2)
        row = result['actions'][0]
        self.assertFalse(row['model_calls_here'])
        argv = row['native_argv']
        self.assertEqual(argv[argv.index('--model') + 1], 'offline-synthetic-fixture')
        self.assertEqual(argv[argv.index('--time-anchor') + 1], self.spec['issues'][0]['time_anchor'])
        self.assertEqual(argv[argv.index('--feed-source') + 1], str((self.study / self.spec['issues'][0]['feed_source']).resolve()))
        self.assertEqual(row['required_native_arguments'], {'--responses': 'path to exact prompt-bound captured responses'})

    def test_requested_alias_requires_distinct_frozen_actual_model_expectation(self):
        self.prepare()
        other_study = self.base / 'other-study'
        raw = read_json(self.base / 'spec.json')
        for candidate in raw['candidates']:
            candidate.update(model='requested-free-alias', actual_model='offline-synthetic-fixture')
        write_json(self.base / 'spec.json', raw)
        cohort.freeze(self.base / 'spec.json', other_study)
        self.study = other_study
        self.spec = read_json(self.study / 'cohort.json')
        self.assertEqual(self.attach()['state'], 'complete')

    def test_heldout_selected_once_after_development_and_seals_pending(self):
        self.prepare(20, holdout=1)
        with self.assertRaisesRegex(ValueError, 'complete development'):
            cohort.evaluate(self.study, final_key='final')
        for index in range(20):
            self.attach('baseline', index)
            self.attach('candidate', index)
        final = cohort.evaluate(self.study, final_key='final')
        self.assertEqual(final['state'], 'pending')
        self.assertEqual(final['development_selected_candidate'], 'candidate')
        self.assertEqual(final, cohort.evaluate(self.study, final_key='final'))
        with self.assertRaisesRegex(ValueError, 'already consumed'):
            cohort.evaluate(self.study, final_key='second')
        self.assertEqual(self.attach('baseline', 20)['state'], 'error')
