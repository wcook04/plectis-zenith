import hashlib
import json
from datetime import datetime, timedelta, timezone

import pytest

from research.diagnosis import _digest
from research.failure_windows import diagnose


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))
    return hashlib.sha256(path.read_bytes()).hexdigest()


def pair(tmp_path, number=0, *, length=1, graph='a', blocked=False, no_findings=False):
    tmp_path = tmp_path.resolve()
    lab, oracle = tmp_path/f'lab{number}', tmp_path/f'oracle{number}'
    start = datetime(2024, 1, 1, tzinfo=timezone.utc) + timedelta(days=number)
    manifest = {'schema': 'zenith_execution_manifest_v1', 'run_id': lab.name, 'mission': 'lab',
                'node_hashes': {'feed': '1'*64, 'director': graph*64}, 'scope': ['feed', 'director'],
                'time_anchor': start.isoformat(), 'horizon': (start+timedelta(days=length)).isoformat()}
    write(lab/'zenith_run.json', manifest)
    sources = {}
    for node, data in [('feed', {'signal': 'prior guidance was cut'}),
                       ('director', {'prediction': 'price rises'})]:
        path = f'artifacts/{node}.json'
        sources[path] = write(lab/path, {'id': node, 'node_hash': manifest['node_hashes'][node],
                                        'status': 'success', 'data': data})
    prompt = 'Read feed: prior guidance was cut. Predict the next price.'
    identity = {'run_id': lab.name, 'node_id': 'director',
                'prompt_sha256': hashlib.sha256(prompt.encode()).hexdigest()}
    packet = dict(identity, schema='zenith_agent_packet_v1', packet_id=_digest(identity), prompt=prompt)
    write(lab/'handoff/requests'/f'{packet["packet_id"]}.json', packet)
    om = dict(manifest, run_id=oracle.name, mission='oracle', subject_run=str(lab),
              node_hashes={k:'2'*64 for k in ('cp2_critique', 'prediction_reconciliation', 'oracle_subject_index')},
              source_hashes={str(lab): sources})
    write(oracle/'zenith_run.json', om)
    item = {'error_class': 'SYNTHESIS_BLIND', 'scope': 'thesis', 'target_or_claim': 'ACME',
            'subject_grounding_refs': ['E1'], 'realized_refs': ['prediction_reconciliation:ACME'],
            'what_was_wrong': 'Possible failure to compare against guidance.'}
    critique = {'status': 'AVAILABLE', 'root_failure_mode': 'Comparison hypothesis', 'critique_items': [item]}
    if no_findings:
        critique = {'status': 'AVAILABLE', 'root_failure_mode': 'No isolated defect',
                    'critique_items': [], 'finding_status': 'NO_FINDINGS', 'no_findings_review': {
            'review_summary': 'Wrong outcome does not isolate a reasoning defect.',
            'subject_grounding_refs': ['E1'], 'realized_refs': ['prediction_reconciliation:ACME']}}
    for node, data in [('cp2_critique', critique),
                       ('prediction_reconciliation', {'subject_run_id': lab.name,
                         'feed_health': {'status': 'BLOCKED' if blocked else 'READY'}}),
                       ('oracle_subject_index', {'subject_run_id': lab.name, 'eligible_ledger_ids': ['E1']})]:
        write(oracle/'artifacts'/f'{node}.json', {'id': node, 'node_hash': om['node_hashes'][node],
                                               'status': 'success', 'data': data})
    return oracle


def annotation(episode):
    from pathlib import Path
    lab = Path(episode['subject_run'])
    citations = []
    for role, path, pointer in [('subject', lab/'artifacts/feed.json', '/data/signal'),
                                ('node_input', next((lab/'handoff/requests').glob('*.json')), '/prompt'),
                                ('node_output', lab/'artifacts/director.json', '/data/prediction')]:
        value = json.loads(path.read_text())
        for k in pointer[1:].split('/'):
            value = value[k]
        citations.append({'role': role, 'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                          'pointer': pointer, 'value': value})
    return {'case_id': episode['cases'][0]['case_id'], 'node_id': 'director',
            'evidence_state': 'in_node_context', 'mechanism': 'guidance_comparison',
            'rationale': 'The input includes the guidance cut; the output predicts a rise. '
                         'This is only a hypothesis: other evidence may explain that forecast.',
            'reviewer': 'test reviewer', 'citations': citations}


def test_unannotated_oracle_cannot_localize_or_promote(tmp_path):
    report = diagnose([pair(tmp_path)])
    case = report['episodes'][0]['cases'][0]
    assert case['node_id'] is None and case['evidence_state'] == 'unknown'
    assert report['strata'][0]['unsupported_widths'] == [2, 5]
    assert report['strata'][0]['next_intervention_hypothesis'] is None
    assert report['promotion_authorized'] is False


def test_overlapping_windows_do_not_multiply_cases_or_independent_origins(tmp_path):
    runs = [pair(tmp_path, n, length=2) for n in range(4)]
    initial = diagnose(runs)
    annotations = [annotation(e) for e in initial['episodes']]
    report = diagnose(runs, widths=[1, 2, 3], annotations=annotations)
    stratum = report['strata'][0]
    assert len(stratum['windows']) == 9
    group = stratum['aggregate'][0]
    assert group['case_count'] == group['episode_count'] == 4
    assert group['nonoverlapping_episode_count'] == 2
    assert stratum['next_intervention_hypothesis'] == group
    assert report['promotion_authorized'] is False
    # Changing window density cannot change the aggregate priority.
    assert diagnose(runs, widths=[2, 4], stride=2, annotations=annotations)['strata'][0]['aggregate'] == stratum['aggregate']


def test_graph_revisions_stay_separate(tmp_path):
    report = diagnose([pair(tmp_path), pair(tmp_path, 1, graph='b')])
    assert len(report['strata']) == 2
    assert all(s['episode_count'] == 1 and s['unsupported_widths'] == [2, 5] for s in report['strata'])


def test_duplicate_oracle_review_is_not_an_extra_episode(tmp_path):
    run = pair(tmp_path)
    with pytest.raises(ValueError, match='Duplicate'):
        diagnose([run, run])


def test_rerun_in_another_directory_is_not_independent_evidence(tmp_path):
    run = pair(tmp_path)
    # Same issue/horizon/graph/input identity, different execution directory.
    other = pair(tmp_path/'retry')
    with pytest.raises(ValueError, match='Duplicate'):
        diagnose([run, other])


def test_native_display_refs_resolve_through_the_subject_dictionary(tmp_path):
    run = pair(tmp_path)
    path = run/'artifacts/cp2_critique.json'
    value = json.loads(path.read_text())
    value['data']['critique_items'][0]['subject_grounding_refs'] = ['[1]']
    write(path, value)
    path = run/'artifacts/oracle_subject_index.json'
    value = json.loads(path.read_text())
    value['data']['evidence_dictionary'] = [{'ref_id': '[1]', 'ledger_id': 'E1'}]
    write(path, value)
    assert diagnose([run])['episodes'][0]['status'] == 'hypotheses_recorded'


def test_data_gap_and_no_findings_are_preserved(tmp_path):
    report = diagnose([pair(tmp_path, blocked=True), pair(tmp_path, 1, no_findings=True)])
    assert [e['status'] for e in report['episodes']] == ['data_gap', 'reviewed_no_findings']
    assert report['strata'][0]['aggregate'] == []
    assert report['strata'][0]['windows'][-1]['unresolved_episode_count'] == 1


def test_abstention_is_neither_data_gap_nor_success(tmp_path):
    run = pair(tmp_path)
    path = run/'artifacts/prediction_reconciliation.json'
    value = json.loads(path.read_text())
    value['data']['feed_health']['status'] = 'ABSTAINED'
    write(path, value)
    report = diagnose([run])
    assert report['episodes'][0]['status'] == 'abstained'
    assert report['strata'][0]['episode_status_counts'] == {
        'hypotheses_recorded': 0, 'reviewed_no_findings': 0, 'abstained': 1, 'data_gap': 0, 'unresolved': 0}


def test_empty_unreviewed_critique_is_unknown(tmp_path):
    run = pair(tmp_path)
    path = run/'artifacts/cp2_critique.json'
    value = json.loads(path.read_text())
    value['data']['critique_items'] = []
    write(path, value)
    episode = diagnose([run])['episodes'][0]
    assert episode['status'] == 'unresolved' and episode['problems']


def test_unknown_grounding_and_changed_frozen_subject_are_unresolved(tmp_path):
    run = pair(tmp_path)
    path = run/'artifacts/cp2_critique.json'
    value = json.loads(path.read_text())
    value['data']['critique_items'][0]['subject_grounding_refs'] = ['invented']
    write(path, value)
    assert diagnose([run])['episodes'][0]['cases'] == []
    feed = tmp_path/'lab0/artifacts/feed.json'
    value = json.loads(feed.read_text())
    value['data']['signal'] = 'later revised guidance'
    write(feed, value)
    assert 'Frozen subject changed' in diagnose([run])['episodes'][0]['problems'][0]


@pytest.mark.parametrize('field,value', [('metadata', None), ('data', 'malformed')])
def test_malformed_record_is_unresolved_not_a_model_failure(tmp_path, field, value):
    run = pair(tmp_path)
    path = run/'artifacts/prediction_reconciliation.json'
    artifact = json.loads(path.read_text())
    artifact[field] = value
    write(path, artifact)
    episode = diagnose([run])['episodes'][0]
    assert episode['status'] == 'unresolved'
    assert episode['cases'] == [] and episode['problems']


@pytest.mark.parametrize('mutation,match', [
    ('hash', 'bytes changed'), ('quote', 'quote does not match'),
    ('input', 'citation roles'), ('node', 'recorded node')])
def test_annotation_requires_source_bound_node_io(tmp_path, mutation, match):
    run = pair(tmp_path)
    a = annotation(diagnose([run])['episodes'][0])
    if mutation == 'hash': a['citations'][0]['sha256'] = '0'*64
    if mutation == 'quote': a['citations'][0]['value'] = 'invented signal'
    if mutation == 'input': a['citations'] = [c for c in a['citations'] if c['role'] != 'node_input']
    if mutation == 'node': a['node_id'] = 'invented'
    with pytest.raises(ValueError, match=match):
        diagnose([run], annotations=[a])


def test_external_research_does_not_become_subject_evidence(tmp_path):
    run = pair(tmp_path)
    a = annotation(diagnose([run])['episodes'][0])
    external = tmp_path/'outside.json'
    sha = write(external, {'article': 'A previously unavailable report'})
    a['citations'] = [c for c in a['citations'] if c['role'] != 'subject']
    a['citations'].append({'role': 'external', 'path': str(external), 'sha256': sha,
        'pointer': '/article', 'value': 'A previously unavailable report', 'available_at': '2024-01-02T00:00:00Z'})
    a['evidence_state'] = 'outside_universe_pre_cutoff'
    with pytest.raises(ValueError, match='Later information'):
        diagnose([run], annotations=[a])
    a['evidence_state'] = 'in_node_context'
    with pytest.raises(ValueError, match='citation roles'):
        diagnose([run], annotations=[a])
    a['evidence_state'] = 'post_cutoff'
    report = diagnose([run], annotations=[a])
    assert report['episodes'][0]['cases'][0]['attribution_status'] == 'source_bound_reviewed_hypothesis'
    assert report['strata'][0]['next_intervention_hypothesis'] is None


def test_forecast_horizon_cannot_be_relabelled(tmp_path):
    run = pair(tmp_path)
    path = run/'zenith_run.json'
    value = json.loads(path.read_text())
    value['horizon'] = '2024-01-09T00:00:00Z'
    write(path, value)
    with pytest.raises(ValueError, match='share the frozen'):
        diagnose([run])


def test_multiple_claims_in_one_episode_are_not_repeated_episodes(tmp_path):
    run = pair(tmp_path)
    path = run/'artifacts/cp2_critique.json'
    value = json.loads(path.read_text())
    value['data']['critique_items'] *= 3
    write(path, value)
    row = diagnose([run])['strata'][0]['aggregate'][0]
    assert (row['case_count'], row['episode_count'], row['nonoverlapping_episode_count']) == (3, 1, 1)


def test_cli_reports_without_mutating_runs(tmp_path, capsys):
    from research.__main__ import main
    run = pair(tmp_path)
    before = {str(p): p.read_bytes() for p in tmp_path.rglob('*.json')}
    assert main(['failure-windows', '--oracle-run', str(run), '--widths', '1', '3']) == 0
    assert json.loads(capsys.readouterr().out)['promotion_authorized'] is False
    assert before == {str(p): p.read_bytes() for p in tmp_path.rglob('*.json')}
