"""Synthetic no-call boundaries; no forecast performance evidence."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
import pytest

from feedback.demo import fixture_run, fixture_policy
from feedback import engine as feedback
from research.engine import read_json, write_json
from system.lib.schema_validator import validate_cp1, validate_cp2, validate_prediction_reconciliation
from system.core.engine import GodModeEngine
from tools.oracle import truth_diff_equity
from tools.refinement.run_evolve import _oracle_input_readiness
from system.lib.schema_validator import validate_realized_hindsight_brief, validate_cp2_critique


def abstain(payload):
    payload = deepcopy(payload)
    payload.update(decision_status='ABSTAIN', dominant_evidence_track='INSUFFICIENT',
                   predictions_t=[], abstention={
        'reason': 'Synthetic source shows an observed price but no supported forward transmission [1].',
        'evidence_refs': ['[1]'], 'unsupported_claims': 'A price observation alone cannot establish a cause [1].',
        'missing_information': 'No independently supported incremental driver in this fixture.',
        'reconsider_when': 'An as-of source establishes a material issuer change and its forward mechanism.'})
    return payload


@pytest.fixture
def subject(tmp_path):
    run = tmp_path/'subject'
    issue = datetime(2026, 1, 5, 20, tzinfo=timezone.utc)
    fixture_run(run, issue, issue+timedelta(days=1), target=101)
    cp2 = run/'artifacts/lab_director.json'
    envelope = read_json(cp2)
    envelope['data'] = abstain(envelope['data'])
    write_json(cp2, envelope)
    return run, envelope['data']


def test_explicit_abstention_keeps_citations_and_refuses_numeric_predictions(subject):
    run, payload = subject
    assert validate_cp1(payload).ok
    assert validate_cp2(payload, subject_run_dir=run).ok
    for change in ({'decision_status': 'unknown'}, {'dominant_evidence_track': 'FLOW_LED'},
                   {'predictions_t': [{'target_id': 'XOM', 'direction': 'UP'}]},
                   {'abstention': {'reason': 'unsupported'}}):
        assert not validate_cp2(dict(payload, **change)).ok
    changed = deepcopy(payload)
    changed['abstention']['evidence_refs'] = ['[999]']
    assert not validate_cp1(changed).ok


def test_empty_forecast_does_not_gain_abstention_semantics(subject):
    _, payload = subject
    del payload['abstention']
    del payload['decision_status']
    assert not validate_cp2(payload).ok


def test_feedback_registers_no_numeric_observations(subject, tmp_path):
    run, _ = subject
    result = feedback.register(tmp_path/'measurement', run, fixture_policy(tmp_path/'policy.json'), '24h')
    assert result['decision_status'] == 'ABSTAIN'
    assert result['count'] == 0 and result['forecasts'] == []


def test_oracle_distinguishes_valid_abstention_from_missing_forecast(subject, tmp_path):
    run, payload = subject
    truth = tmp_path/'truth'
    issue = datetime(2026, 1, 6, 20, tzinfo=timezone.utc)
    fixture_run(truth, issue, issue+timedelta(days=1), target=102)
    config = {'runtime': {'oracle_subject_run_dir': str(run), 'oracle_truth_run_dir': str(truth)}}
    result = truth_diff_equity.run(config)['data']
    assert result['status'] == 'ABSTAINED' and result['rows'] == []
    assert result['summary']['row_count'] == 0
    assert result['grading_summary']['hit_rate'] is None
    assert result['feed_health']['status'] == 'ABSTAINED'
    readiness = _oracle_input_readiness({'missing_artifacts': [], 'feed_health': result['feed_health']})
    assert readiness['status'] != 'BLOCKED'
    assert validate_prediction_reconciliation(result).ok
    assert not validate_prediction_reconciliation(dict(result, status='AVAILABLE')).ok
    assert not validate_prediction_reconciliation(dict(result, subject_decision_status='FORECAST')).ok
    envelope = read_json(run/'artifacts/lab_director.json')
    envelope['status'] = 'failure'
    write_json(run/'artifacts/lab_director.json', envelope)
    with pytest.raises(ValueError, match='Invalid subject abstention'):
        truth_diff_equity.run(config)
    envelope['status'] = 'success'
    envelope['data']['abstention']['evidence_refs'] = ['[999]']
    write_json(run/'artifacts/lab_director.json', envelope)
    with pytest.raises(ValueError, match='Invalid subject abstention'):
        truth_diff_equity.run(config)


def test_director_cannot_change_locked_decision_mode(subject):
    run, payload = subject
    engine = GodModeEngine.__new__(GodModeEngine)
    engine.run_dir, engine._subject_run_dir = run, run
    engine._run_anchor_iso = '2026-01-05T20:00:00+00:00'
    engine._target_time_iso = '2026-01-06T20:00:00+00:00'
    engine._oracle_mode = False
    engine._extract_cross_corr_v2_targets = lambda: set()
    write_json(run/'artifacts/lab_decide.json', {'data': {'decision_status': 'FORECAST'}})
    result = engine._validate_schema_output(SimpleNamespace(id='lab_director'), 'isomorphic_cp2', payload)
    assert not result.ok and any('DECISION_STATUS_MISMATCH' in e for e in result.errors)
    write_json(run/'artifacts/lab_decide.json', {'data': {'decision_status': 'ABSTAIN'}})
    assert engine._validate_schema_output(SimpleNamespace(id='lab_director'), 'isomorphic_cp2', payload).ok


def test_unknown_realized_cause_is_not_forced_into_surprise_or_pricing():
    brief = {'status': 'AVAILABLE', 'realized_dominant_force': 'Unresolved from supplied evidence.',
             'regime_summary': 'Synthetic observed move with unestablished cause.',
             'driver_classification': [{'driver': 'Observed stock move', 'classification': 'UNRESOLVED',
                 'why': 'Price movement alone does not establish surprise or remaining pricing.',
                 'supporting_lanes': ['STOCK'], 'affected_targets': ['XOM']}],
             'already_priced_packages': [], 'surprise_packages': [], 'partial_repricing_packages': [],
             'unresolved_packages': ['Observed stock move'], 'prediction_target_outcomes': []}
    assert validate_realized_hindsight_brief(brief).ok
    brief['surprise_packages'] = ['Observed stock move']
    assert not validate_realized_hindsight_brief(brief).ok


def test_nonempty_prediction_reconciliation_cannot_claim_subject_abstained(tmp_path):
    subject, truth = tmp_path/'subject', tmp_path/'truth'
    issue = datetime(2026, 1, 5, 20, tzinfo=timezone.utc)
    fixture_run(subject, issue, issue+timedelta(days=1), target=101)
    fixture_run(truth, issue+timedelta(days=1), issue+timedelta(days=2), target=102)
    result = truth_diff_equity.run({'runtime': {'oracle_subject_run_dir': str(subject),
        'oracle_truth_run_dir': str(truth)}})['data']
    assert validate_prediction_reconciliation(result).ok
    assert not validate_prediction_reconciliation(dict(result, subject_decision_status='ABSTAIN')).ok


def test_no_evidenced_error_requires_explicit_bound_review():
    payload = {'status': 'AVAILABLE', 'root_failure_mode': 'No evidenced earlier error.',
        'finding_status': 'NO_FINDINGS', 'critique_items': [], 'no_findings_review': {
            'review_summary': 'A later positive return establishes no earlier supported opportunity.',
            'subject_grounding_refs': ['S_12345678'],
            'realized_refs': ['realized_hindsight_brief:unresolved_move']}}
    assert validate_cp2_critique(payload).ok
    for field in ('review_summary', 'subject_grounding_refs', 'realized_refs'):
        invalid = deepcopy(payload)
        invalid['no_findings_review'].pop(field)
        assert not validate_cp2_critique(invalid).ok
    for patch in ({'finding_status': 'ERRORS_FOUND'}, {'critique_items': [{}]},
                  {'no_findings_review': None}, {'finding_status': 'unknown'}):
        assert not validate_cp2_critique(dict(payload, **patch)).ok
    legacy = {'status': 'AVAILABLE', 'root_failure_mode': 'Unspecified', 'critique_items': []}
    assert not validate_cp2_critique(legacy).ok
