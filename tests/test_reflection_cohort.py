"""Synthetic JSON-only reflection continuation; no provider calls or feedback DB."""
from copy import deepcopy
from pathlib import Path

import pytest

from feedback.demo import fixture_policy
from feedback.engine import digest
from research import cohort, reflection
from research.engine import digest_bytes, read_json, write_json
from research.reflection_cohort import candidate_fragment
from system.lib.hashing import hash_node
from zenith import runtime


@pytest.fixture
def prepared(tmp_path):
    issue = '2026-01-05T20:00:00+00:00'
    target = '2026-01-06T20:00:00+00:00'
    feed = tmp_path / 'feed'
    write_json(feed / 'runtime_context.json', {'as_of': issue})
    write_json(feed / 'artifacts/global_stock_feed.json', {
        'status': 'success', 'metadata': {'status': 'success', 'price_basis': 'synthetic_point_quote',
                                        'currency': 'USD', 'synthetic_fixture': True},
        'data': {'columns': ['Ticker', 'Price', 'timestamp'], 'rows': [['XOM', 100.0, issue]]}})
    feedback_policy = fixture_policy(tmp_path / 'feedback-policy.json')
    truth = tmp_path / 'truth.json'
    write_json(truth, {'metadata': {'status': 'success', 'price_basis': 'synthetic_point_quote',
                                   'currency': 'USD', 'synthetic_fixture': True},
                       'data': {'rows': [{'target_id': 'XOM', 'timestamp': target, 'price': 101.0}]}})
    baseline = {'candidate_id': 'baseline', 'hypothesis': 'synthetic fixture baseline', 'change': 'none',
                'source_commit': 'synthetic-fixture', 'model': 'requested-fixture', 'actual_model': 'actual-fixture',
                'execution_kind': 'captured_replay', 'provider': 'captured', 'graph_variant': None,
                'reasoning_policy': None, 'context_profile': 'compact_feeds', 'prompt_sha256': '0' * 64}
    raw = {'schema': cohort.SCHEMA,
           'issues': [{'issue_id': 'issue-0', 'feed_source': str(feed), 'time_anchor': issue,
                       'target_time': target, 'horizon_id': '24h', 'target_ids': ['XOM'], 'split': 'development'}],
           'candidates': [baseline], 'feedback_policy': str(feedback_policy), 'truth_source': str(truth),
           'truth_as_of': '2026-03-01T00:00:00+00:00', 'max_trials': 2, 'max_calls_per_run': 100,
           'minimum_improvement': .001, 'embargo_days': 1}
    spec_path, study = tmp_path / 'spec.json', tmp_path / 'parent-study'
    write_json(spec_path, raw)
    cohort.freeze(spec_path, study)
    state = read_json(study / 'cohort-state.json')
    # Synthetic membership only. No native run or forecasting claim is fabricated.
    state['attachments'] = {'baseline/issue-0': {
        'state': 'complete', 'forecasts': [{'issue_run_id': 'synthetic-development-run'}]}}
    write_json(study / 'cohort-state.json', state)
    graph = runtime.load_graph(runtime.DEFAULT_ROOT)
    forecast = tmp_path / 'synthetic-development-run/artifacts/lab_director.json'
    write_json(forecast, {'synthetic_fixture': True})
    write_json(forecast.parent.parent / 'zenith_run.json', {
        'mission': 'lab', 'run_id': 'synthetic-development-run', 'time_anchor': issue,
        'scope': sorted(runtime.scope_for(graph, 'lab_director')),
        'node_hashes': {key: hash_node(node) for key, node in graph.items()},
        'synthetic_fixture': True})
    proposal = {
        'schema': 'zenith_skill_feedback_proposal_v1', 'live_mutation_permission': False,
        'actual_model': 'actual-fixture', 'execution_kind': 'captured_replay', 'reasoning_policy_sha256': None,
        'analysis_window': {'as_of': raw['truth_as_of'], 'start_inclusive': issue},
        'total_registered_samples_in_window': 1, 'sample_status_counts': {'scored': 1},
        'total_resolved': 1, 'total_failures': 1, 'support_fraction': 1.0, 'distinct_resolved_issue_times': 1,
        'evidence': [{'forecast_id': 'synthetic-forecast', 'issue_run_id': 'synthetic-development-run',
                      'issue_time': issue, 'truth_observed_time': target, 'supports_candidate_class': True,
                      'forecast_ref': {'path': str(forecast), 'sha256': digest_bytes(forecast.read_bytes())},
                      'truth_ref': {'path': str(truth), 'sha256': digest_bytes(truth.read_bytes())}}],
        'participating_ancestors': [{'node_id': 'lab_director', 'node_sha256': hash_node(graph['lab_director']),
                                    'parent_ids': graph['lab_director'].dependencies}]}
    proposal['proposal_id'] = digest(proposal)
    proposal_path = tmp_path / 'proposal.json'
    write_json(proposal_path, proposal)

    def compile_current():
        scope = reflection.scope_from_study(study, raw['truth_as_of'])
        packet = reflection.build_packet(proposal_path, scope=scope, source_root=tmp_path)
        compiled = reflection.compile_candidate(packet, graph=graph, node_id='lab_director',
            parameter='skill_addon', value='Compare target prices to the no-change baseline.',
            hypothesis='Baseline comparison reduces relative target-price errors.', variant_id='comparison-skill')
        return packet, compiled

    packet, compiled = compile_current()
    options = {'study': study, 'policy_path': tmp_path / 'candidate/policy.json',
               'candidate_id': 'comparison-skill', 'source_commit': 'caller-declared-revision'}
    return {'root': tmp_path, 'study': study, 'raw': raw, 'packet': packet, 'compiled': compiled,
            'options': options, 'compile': compile_current}


def test_fragment_is_read_only_and_consumed_by_new_native_freeze(prepared):
    p = prepared
    before = {str(f.relative_to(p['root'])): f.read_bytes() for f in p['root'].rglob('*') if f.is_file()}
    result = candidate_fragment(p['packet'], p['compiled'], **p['options'])
    after = {str(f.relative_to(p['root'])): f.read_bytes() for f in p['root'].rglob('*') if f.is_file()}
    assert before == after
    row, review = result['candidate'], result['review']
    assert set(row) == {'candidate_id', 'hypothesis', 'change', 'source_commit', 'model', 'actual_model',
                        'provider', 'execution_kind', 'context_profile', 'graph_variant', 'reasoning_policy',
                        'prompt_sha256'}
    for key in ('model', 'actual_model', 'provider', 'execution_kind', 'context_profile', 'graph_variant'):
        assert row[key] == p['raw']['candidates'][0][key]
    assert row['prompt_sha256'] == p['packet']['packet_sha256']
    assert review['state'] == 'review_only' and review['live_mutation_permission'] is False
    assert review['policy_file_state'] == 'intended_not_written'
    assert review['source_commit_provenance'] == 'caller-declared; not a verified Git revision'
    write_json(Path(row['reasoning_policy']), p['compiled']['reasoning_policy'])
    fresh = deepcopy(p['raw'])
    fresh['candidates'].append(row)
    source = p['root'] / 'new-spec.json'
    write_json(source, fresh)
    receipt = cohort.freeze(source, p['root'] / 'new-study')
    assert receipt['state'] == 'frozen'
    frozen = read_json(p['root'] / 'new-study/cohort.json')['candidates'][1]
    assert frozen['reasoning_policy_payload'] == p['compiled']['reasoning_policy']
    assert frozen['prompt_sha256'] == p['packet']['packet_sha256']
    assert (p['study'] / 'cohort-state.json').read_bytes() == before['parent-study/cohort-state.json']


@pytest.mark.parametrize('candidate_id', ['baseline', '../escape', 'bad/name', '', 'other-safe-name'])
def test_rejects_unsafe_reused_or_unbound_id(prepared, candidate_id):
    with pytest.raises(ValueError):
        candidate_fragment(prepared['packet'], prepared['compiled'],
                           **dict(prepared['options'], candidate_id=candidate_id))


def test_rejects_tampered_policy_and_parent_bytes(prepared):
    p = prepared
    changed = deepcopy(p['compiled'])
    changed['reasoning_policy']['nodes']['lab_director']['skill_addon'] = 'Unreviewed addition'
    with pytest.raises(ValueError, match='compiled reflection'):
        candidate_fragment(p['packet'], changed, **p['options'])
    policy = Path(p['options']['policy_path'])
    write_json(policy, {'unreviewed': True})
    with pytest.raises(ValueError, match='existing reasoning policy'):
        candidate_fragment(p['packet'], p['compiled'], **p['options'])
    (p['study'] / 'inputs/issue-0/runtime_context.json').write_text('{}')
    with pytest.raises(ValueError, match='frozen cohort input'):
        candidate_fragment(p['packet'], p['compiled'], **p['options'])


def test_rejects_changed_authority_and_unbound_scope(prepared, monkeypatch):
    p = prepared
    monkeypatch.setattr(cohort, 'authorities', lambda: {})
    with pytest.raises(ValueError, match='source or Python changed'):
        candidate_fragment(p['packet'], p['compiled'], **p['options'])
    monkeypatch.undo()
    packet = deepcopy(p['packet'])
    packet['scope'].pop('cohort_sources')
    packet['scope_sha256'] = digest(packet['scope'])
    packet['packet_sha256'] = digest({k: v for k, v in packet.items() if k != 'packet_sha256'})
    with pytest.raises(ValueError, match='exact frozen cohort state'):
        candidate_fragment(packet, p['compiled'], **p['options'])


def test_rejects_full_graph_drift_and_consumed_final(prepared):
    p = prepared
    spec_path = p['study'] / 'cohort.json'
    spec = read_json(spec_path)
    spec['candidates'][0]['node_hashes']['delta_analyzer'] = '0' * 64
    write_json(spec_path, spec)
    state = read_json(p['study'] / 'cohort-state.json')
    state['spec_hash'] = digest_bytes(spec_path.read_bytes())
    write_json(p['study'] / 'cohort-state.json', state)
    packet, compiled = p['compile']()
    with pytest.raises(ValueError, match='full frozen source graph'):
        candidate_fragment(packet, compiled, **p['options'])
    state['final'] = {'state': 'pending'}
    write_json(p['study'] / 'cohort-state.json', state)
    # Reseal source refs only to exercise the independent final-consumption gate.
    for ref in packet['scope']['cohort_sources']:
        ref['sha256'] = digest_bytes(Path(ref['path']).read_bytes())
    packet['scope_sha256'] = digest(packet['scope'])
    packet['packet_sha256'] = digest({k: v for k, v in packet.items() if k != 'packet_sha256'})
    with pytest.raises(ValueError, match='final seal consumed'):
        candidate_fragment(packet, compiled, **p['options'])


def test_rejects_parent_output_path_and_empty_commit(prepared):
    p = prepared
    for changes in ({'policy_path': p['study'] / 'new-policy.json'}, {'source_commit': ''}):
        with pytest.raises(ValueError):
            candidate_fragment(p['packet'], p['compiled'], **dict(p['options'], **changes))


def test_selected_source_inherits_exact_frozen_graph_variant(prepared):
    p = prepared
    raw = deepcopy(p['raw'])
    variant_path = runtime.DEFAULT_ROOT / 'examples/variants/lab_evidence_check.json'
    raw['candidates'].append(dict(raw['candidates'][0], candidate_id='parent-variant',
                                  graph_variant=str(variant_path)))
    source, study = p['root'] / 'variant-spec.json', p['root'] / 'variant-study'
    write_json(source, raw)
    cohort.freeze(source, study)
    state = read_json(study / 'cohort-state.json')
    state['attachments'] = {'parent-variant/issue-0': {
        'state': 'complete', 'forecasts': [{'issue_run_id': 'synthetic-development-run'}]}}
    write_json(study / 'cohort-state.json', state)
    scope = reflection.scope_from_study(study, raw['truth_as_of'])
    packet = reflection.build_packet(p['root'] / 'proposal.json', scope=scope, source_root=p['root'])
    graph = runtime.load_graph(runtime.DEFAULT_ROOT, read_json(variant_path))
    compiled = reflection.compile_candidate(packet, graph=graph, node_id='lab_director',
        parameter='skill_addon', value='Compare target prices to the no-change baseline.',
        hypothesis='Baseline comparison reduces relative target-price errors.', variant_id='comparison-skill')
    fragment = candidate_fragment(packet, compiled, **dict(p['options'], study=study,
                                                         source_candidate_id='parent-variant'))
    assert fragment['candidate']['graph_variant'] == str(study / 'candidates/parent-variant/graph_variant.json')
    assert fragment['review']['source_candidate_id'] == 'parent-variant'
    assert read_json(Path(fragment['candidate']['graph_variant'])) == read_json(variant_path)


def test_measured_baseline_policy_must_match_source(prepared):
    p = prepared
    proposal_path = p['root'] / 'proposal.json'
    proposal = read_json(proposal_path)
    proposal['reasoning_policy_sha256'] = 'f' * 64
    proposal['proposal_id'] = digest({k: v for k, v in proposal.items() if k != 'proposal_id'})
    write_json(proposal_path, proposal)
    manifest_path = p['root'] / 'synthetic-development-run/zenith_run.json'
    manifest = read_json(manifest_path)
    manifest['reasoning_policy'] = {'policy_sha256': 'f' * 64}
    write_json(manifest_path, manifest)
    artifact_path = manifest_path.parent / 'artifacts/lab_director.json'
    artifact = read_json(artifact_path)
    artifact['metadata'] = {'reasoning_policy_sha256': 'f' * 64}
    write_json(artifact_path, artifact)
    proposal['evidence'][0]['forecast_ref']['sha256'] = digest_bytes(artifact_path.read_bytes())
    proposal['proposal_id'] = digest({k: v for k, v in proposal.items() if k != 'proposal_id'})
    write_json(proposal_path, proposal)
    scope = reflection.scope_from_study(p['study'], p['raw']['truth_as_of'])
    packet = reflection.build_packet(proposal_path, scope=scope, source_root=p['root'])
    with pytest.raises(ValueError, match='baseline policy differs'):
        candidate_fragment(packet, p['compiled'], **p['options'])
