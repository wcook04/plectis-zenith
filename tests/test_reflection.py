"""Synthetic native feedback -> reflection -> policy compilation regressions."""
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import hashlib
from pathlib import Path
import shutil
import tempfile
import unittest

from feedback import engine
from feedback.demo import fixture_policy, fixture_run
from research import reflection
from system.lib.reasoning_policy import policy_sha256
from zenith import runtime
from zenith.providers import write_json


class ReflectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Native references are repository-relative; preserve that real boundary.
        cls.temp = tempfile.TemporaryDirectory(prefix='.reflection-test-', dir=engine.ROOT)
        cls.addClassCleanup(cls.temp.cleanup)
        cls.native_folder = Path(cls.temp.name)
        store = cls.native_folder / 'feedback'
        policy_path = fixture_policy(cls.native_folder / 'feedback-policy.json')
        truth_rows, cls.native_run_ids = [], []
        issue = datetime(2026, 1, 5, 20, tzinfo=timezone.utc)
        for index in range(20):
            start = issue + timedelta(days=2 * index)
            target = start + timedelta(days=1)
            run = fixture_run(cls.native_folder / f'LAB_{index}', start, target)
            registered = engine.register(store, run, policy_path, '24h')
            cls.native_run_ids.append(registered['forecasts'][0]['issue_run_id'])
            truth_rows.append({'target_id': 'XOM', 'timestamp': target.isoformat(),
                               'price': 99.0 if index in (0, 8, 16) else 101.0})
        cls.truth = cls.native_folder / 'truth.json'
        write_json(cls.truth, {'metadata': {'status': 'success', 'price_basis': 'synthetic_point_quote',
                                            'currency': 'USD'}, 'data': {'rows': truth_rows}})
        cls.as_of = '2026-03-01T00:00:00+00:00'
        engine.score(store, cls.truth, cls.as_of)
        cls.native_proposal = engine.propose(store, cls.as_of)['proposals'][0]
        cls.native_graph = runtime.load_graph(engine.ROOT)

    def setUp(self):
        self.folder = self.native_folder / self._testMethodName
        self.folder.mkdir()
        self.run_ids = list(self.native_run_ids)
        self.proposal = deepcopy(self.native_proposal)
        self.proposal_path = self.folder / 'proposal.json'
        write_json(self.proposal_path, self.proposal)
        self.scope = {'schema': 'zenith_reflection_scope_v1', 'as_of': self.as_of,
                      'development_run_ids': self.run_ids, 'heldout_run_ids': []}
        self.graph = deepcopy(self.native_graph)

    def packet(self):
        return reflection.build_packet(self.proposal_path, scope=self.scope)

    def compile(self, packet=None, **changes):
        options = {'graph': self.graph, 'node_id': 'lab_director', 'parameter': 'skill_addon',
                   'value': 'Check the no-change benchmark before finalizing target prices.',
                   'hypothesis': 'The comparator reduces target-price error on new complete matched support.',
                   'variant_id': 'comparison-skill'}
        options.update(changes)
        return reflection.compile_candidate(packet or self.packet(), **options)

    def update_proposal(self, edit):
        edit(self.proposal)
        self.proposal['proposal_id'] = engine.digest({k: v for k, v in self.proposal.items() if k != 'proposal_id'})
        write_json(self.proposal_path, self.proposal)

    def replace_native(self, path, value):
        original = path.read_bytes()
        self.addCleanup(path.write_bytes, original)
        write_json(path, value)

    def handoff(self, *, prompt=None, response='{"result":"Synthetic response"}'):
        row = min(self.proposal['evidence'], key=lambda r: (r['issue_time'], r['forecast_id']))
        run = (engine.ROOT / row['forecast_ref']['path']).parent.parent
        prompt = prompt or 'Synthetic original node input context. ' * 100
        identity = {'run_id': row['issue_run_id'], 'node_id': 'lab_director',
                    'prompt_sha256': hashlib.sha256(prompt.encode()).hexdigest()}
        packet = {'schema': 'zenith_agent_packet_v1', **identity, 'packet_id': engine.digest(identity),
                  'prompt': prompt, 'engine_config': {}}
        for directory in ('requests', 'responses', 'validation'):
            self.addCleanup(shutil.rmtree, run / 'handoff' / directory, True)
        request_path = run / 'handoff/requests' / f'{packet["packet_id"]}.json'
        write_json(request_path, packet)
        response_path = run / 'handoff/responses' / request_path.name
        response_payload = {'schema': 'zenith_agent_response_v1', **identity,
                            'packet_id': packet['packet_id'], 'response_text': response}
        write_json(response_path, response_payload)
        validation_path = run / 'handoff/validation' / request_path.name
        write_json(validation_path, {'schema': 'zenith_import_validation_v1', 'run_id': row['issue_run_id'],
                                    'node_id': 'lab_director', 'packet_id': packet['packet_id'],
                                    'response_sha256': hashlib.sha256(response.encode()).hexdigest(),
                                    'engine_accepted': True})
        return request_path, response_path, validation_path

    def test_native_packet_keeps_successes_denominator_and_exact_change(self):
        packet = self.packet()
        proposal = packet['proposal']
        self.assertEqual(len(proposal['evidence']), 20)
        self.assertEqual(sum(e['supports_candidate_class'] for e in proposal['evidence']), 3)
        self.assertEqual(proposal['total_resolved'], 20)
        self.assertEqual(proposal['support_fraction'], 3 / 20)
        compiled = self.compile(packet)
        self.assertEqual(set(compiled['reasoning_policy']['nodes']), {'lab_director'})
        self.assertEqual(set(compiled['reasoning_policy']['nodes']['lab_director']), {'skill_addon'})
        self.assertFalse(compiled['candidate']['live_mutation_permission'])
        self.assertEqual(compiled['candidate']['change']['before'], {'present': False, 'value': None})
        self.assertEqual(compiled, self.compile(packet))

    def test_holdout_and_unlisted_runs_are_rejected_without_filtering(self):
        self.scope['heldout_run_ids'] = [self.run_ids[0]]
        with self.assertRaisesRegex(ValueError, 'overlap'):
            self.packet()
        self.scope['development_run_ids'] = self.run_ids[1:]
        with self.assertRaisesRegex(ValueError, 'nondevelopment or heldout'):
            self.packet()
        self.scope['heldout_run_ids'] = []
        with self.assertRaisesRegex(ValueError, 'nondevelopment or heldout'):
            self.packet()

    def test_future_analysis_and_truth_cannot_enter_packet(self):
        self.scope['as_of'] = '2026-02-01T00:00:00+00:00'
        with self.assertRaisesRegex(ValueError, 'analysis is after'):
            self.packet()
        self.scope['as_of'] = self.as_of
        self.update_proposal(lambda p: p['evidence'][0].update(truth_observed_time='2026-04-01T00:00:00+00:00'))
        with self.assertRaisesRegex(ValueError, 'future or out-of-window'):
            self.packet()

    def test_source_drift_and_packet_tampering_fail_closed(self):
        packet = self.packet()
        tampered = deepcopy(packet)
        tampered['proposal']['evidence'].pop()
        with self.assertRaisesRegex(ValueError, 'packet hash mismatch'):
            self.compile(tampered)
        self.truth.write_text(self.truth.read_text() + ' ')
        self.addCleanup(self.truth.write_text, self.truth.read_text()[:-1])
        with self.assertRaisesRegex(ValueError, 'source hash mismatch'):
            self.compile(packet)

    def test_changed_proposal_and_denominator_mismatch_are_rejected(self):
        packet = self.packet()
        self.proposal_path.write_text(self.proposal_path.read_text() + ' ')
        with self.assertRaisesRegex(ValueError, 'source hash mismatch'):
            self.compile(packet)
        self.update_proposal(lambda p: p.update(total_resolved=19))
        with self.assertRaisesRegex(ValueError, 'denominator'):
            self.packet()

    def test_policy_mismatch_graph_drift_and_invalid_edits_rejected(self):
        baseline = {'variant_id': 'unmeasured', 'nodes': {'lab_director': {'skill_addon': 'Existing rule.'}}}
        baseline['policy_sha256'] = policy_sha256(baseline)
        with self.assertRaisesRegex(ValueError, 'baseline policy differs'):
            self.compile(baseline_policy=baseline)
        graph = deepcopy(self.graph)
        graph['lab_director'] = replace(graph['lab_director'], instruction=graph['lab_director'].instruction + '\nChanged instruction')
        with self.assertRaisesRegex(ValueError, 'frozen ancestry'):
            self.compile(graph=graph)
        with self.assertRaisesRegex(ValueError, 'one skill/context parameter'):
            self.compile(parameter='topology')
        with self.assertRaisesRegex(ValueError, 'must be text'):
            self.compile(value={'unexpected': 'compound mutation'})
        with self.assertRaisesRegex(ValueError, 'declared incoming edge'):
            self.compile(parameter='incoming_weights', edge_id='oracle_truth_map', value=0)
        with self.assertRaisesRegex(ValueError, 'finite and nonnegative'):
            self.compile(parameter='incoming_weights', edge_id=self.graph['lab_director'].dependencies[0], value=-1)

    def test_other_ancestor_drift_malformed_data_and_effective_noops_rejected(self):
        graph = deepcopy(self.graph)
        ancestor_id = self.proposal['participating_ancestors'][0]['node_id']
        self.assertNotEqual(ancestor_id, 'lab_director')
        graph[ancestor_id] = replace(graph[ancestor_id], instruction='Changed unrelated ancestor')
        with self.assertRaisesRegex(ValueError, 'frozen ancestry'):
            self.compile(graph=graph)
        with self.assertRaisesRegex(ValueError, 'no-op'):
            self.compile(value='')
        with self.assertRaisesRegex(ValueError, 'no-op'):
            self.compile(parameter='incoming_weights', edge_id=self.graph['lab_director'].dependencies[0], value=1)
        malformed = deepcopy(self.packet())
        malformed['proposal']['evidence'][0].pop('issue_time')
        malformed['packet_sha256'] = engine.digest({k: v for k, v in malformed.items() if k != 'packet_sha256'})
        # Source/embedded equality still catches a rehashed malformed packet.
        with self.assertRaises(ValueError):
            self.compile(malformed)
        self.scope['development_run_ids'] = None
        with self.assertRaises(ValueError):
            self.packet()

    def test_matching_measured_baseline_preserved_except_one_edge(self):
        edge = self.graph['lab_director'].dependencies[0]
        baseline = {'variant_id': 'measured', 'nodes': {'lab_director': {
            'skill_addon': 'Existing rule.', 'incoming_weights': {edge: 1}, 'max_context_chars': 4096}}}
        baseline['policy_sha256'] = policy_sha256(baseline)
        for evidence in self.proposal['evidence']:
            artifact_path = engine.ROOT / evidence['forecast_ref']['path']
            manifest_path = artifact_path.parent.parent / 'zenith_run.json'
            manifest = engine.read_object(manifest_path)
            manifest['reasoning_policy'] = baseline
            self.replace_native(manifest_path, manifest)
            artifact = engine.read_object(artifact_path)
            artifact['metadata']['reasoning_policy_sha256'] = baseline['policy_sha256']
            self.replace_native(artifact_path, artifact)
            evidence['forecast_ref']['sha256'] = reflection._file_hash(artifact_path)
        self.update_proposal(lambda p: p.update(reasoning_policy_sha256=baseline['policy_sha256']))
        result = self.compile(parameter='incoming_weights', edge_id=edge, value=0.5, baseline_policy=baseline)
        row = result['reasoning_policy']['nodes']['lab_director']
        self.assertEqual(row['skill_addon'], 'Existing rule.')
        self.assertEqual(row['max_context_chars'], 4096)
        self.assertEqual(row['incoming_weights'], {edge: 0.5})
        self.assertEqual(result['candidate']['change']['before'], {'present': True, 'value': 1})
        with self.assertRaisesRegex(ValueError, 'no-op'):
            self.compile(parameter='incoming_weights', edge_id=edge, value=1, baseline_policy=baseline)

    def test_trace_sample_is_deterministic_bounded_and_keeps_full_support(self):
        packet = self.packet()
        trace = packet['trace_context']
        self.assertEqual(len(trace['cases']), 5)
        self.assertEqual(sum(c['supports_candidate_class'] for c in trace['cases']), 3)
        self.assertEqual(len(trace['omitted_forecast_ids']), 15)
        self.assertEqual(len(packet['proposal']['evidence']), 20)
        self.assertEqual(trace, self.packet()['trace_context'])
        for case in trace['cases']:
            self.assertEqual(case['input_status'], 'missing_handoff_prompt')
            self.assertEqual(case['node_artifact']['status'], 'present')
            self.assertLessEqual(case['node_artifact']['output']['retained_chars'], 2048)
            self.assertTrue(case['node_artifact']['output']['original_sha256'])

    def test_hydrated_prompt_response_validation_binding_and_drift(self):
        request, response, validation = self.handoff(response='Synthetic response. ' * 200)
        packet = self.packet()
        case = packet['trace_context']['cases'][0]
        exchange = case['handoff_exchanges'][0]
        self.assertTrue(exchange['prompt']['truncated'])
        self.assertTrue(exchange['response']['truncated'])
        self.assertEqual(exchange['prompt']['retained_chars'], 2048)
        self.assertTrue(exchange['engine_accepted'])
        self.assertTrue(exchange['validation_source']['sha256'])
        self.assertFalse(case['node_artifact']['embedded_node_identity_available'])
        self.compile(packet)
        validation.write_text(validation.read_text() + ' ')
        with self.assertRaisesRegex(ValueError, 'trace sources or deterministic excerpts changed'):
            self.compile(packet)
        payload = engine.read_object(response)
        payload['run_id'] = 'WRONG_RUN'
        write_json(response, payload)
        with self.assertRaisesRegex(ValueError, 'response run_id mismatch'):
            self.packet()

    def test_missing_responses_and_future_response_are_explicit_or_rejected(self):
        request, response, validation = self.handoff()
        payload = engine.read_object(response)
        payload['imported_at'] = '2026-04-01T00:00:00Z'
        write_json(response, payload)
        with self.assertRaisesRegex(ValueError, 'future handoff response'):
            self.packet()
        response.unlink()
        exchange = self.packet()['trace_context']['cases'][0]['handoff_exchanges'][0]
        self.assertEqual(exchange['response_status'], 'missing')
        self.assertNotIn('response', exchange)

    def test_selected_node_must_match_candidate_and_have_measured_identity(self):
        packet = reflection.build_packet(self.proposal_path, scope=self.scope, node_id='global_stock_feed')
        self.assertEqual(packet['trace_context']['node_id'], 'global_stock_feed')
        with self.assertRaisesRegex(ValueError, 'selected reflection trace node'):
            self.compile(packet)
        with self.assertRaisesRegex(ValueError, 'did not participate'):
            reflection.build_packet(self.proposal_path, scope=self.scope, node_id='oracle_truth_map')
        case = self.packet()['trace_context']['cases'][0]
        manifest_path = Path(case['manifest_source']['path'])
        manifest = engine.read_object(manifest_path)
        manifest['run_id'] = 'WRONG_RUN'
        self.replace_native(manifest_path, manifest)
        with self.assertRaisesRegex(ValueError, 'development evidence identity'):
            self.packet()

    def test_frozen_study_membership_is_pinned_and_final_closes_reflection(self):
        study = self.folder / 'study'
        study.mkdir()
        spec = {'schema': 'zenith_graph_cohort_v1', 'issues': [{'issue_id': 'development', 'split': 'development'},
                           {'issue_id': 'heldout', 'split': 'holdout'}]}
        write_json(study / 'cohort.json', spec)
        state = {'spec_hash': reflection._file_hash(study / 'cohort.json'), 'final': None,
                 'attachments': {'baseline/development': {'state': 'complete',
                   'forecasts': [{'issue_run_id': run} for run in self.run_ids]},
                   'baseline/heldout': {'state': 'complete', 'forecasts': [{'issue_run_id': 'HOLDOUT'}]}}}
        write_json(study / 'cohort-state.json', state)
        self.scope = reflection.scope_from_study(study, self.as_of)
        self.assertEqual(self.scope['heldout_run_ids'], ['HOLDOUT'])
        packet = self.packet()
        state['final'] = {'state': 'sealed'}
        write_json(study / 'cohort-state.json', state)
        with self.assertRaisesRegex(ValueError, 'source hash mismatch'):
            self.compile(packet)
        with self.assertRaisesRegex(ValueError, 'seal consumed'):
            reflection.scope_from_study(study, self.as_of)


if __name__ == '__main__':
    unittest.main()
