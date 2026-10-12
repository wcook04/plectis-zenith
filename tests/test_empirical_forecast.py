"""Synthetic control arithmetic and chronology, not evidence of market skill."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
import pytest
from feedback.demo import fixture_run, fixture_policy
from feedback import engine as feedback
from research.engine import read_json, write_json
from system.lib.empirical_forecast import calculate, rule_errors
from system.lib.schema_validator import validate_cp1, validate_cp2
from system.core.engine import GodModeEngine


@pytest.fixture
def case(tmp_path):
    issue = datetime(2026, 1, 5, 21, tzinfo=timezone.utc)
    run = fixture_run(tmp_path/'subject', issue, issue+timedelta(days=1), target=101)
    p = read_json(run/'artifacts/lab_director.json')['data']
    e = p['evidence_dictionary'][0]
    p.update(forecast_basis='EMPIRICAL', dominant_evidence_track='EMPIRICAL', empirical_rule={
        'method':'trailing_mean_return_v1', 'lookback_returns':2, 'scale':.5, 'max_abs_return':.02,
        'target_ids':['XOM'], 'evidence_refs':[e['ref_id']],
        'selection_basis':'Synthetic preregistered control; no learned advantage.', 'calibration_status':'UNVALIDATED'})
    stock = read_json(run/'artifacts/global_stock_feed.json')
    stock['metadata']={'as_of':issue.isoformat()}
    stock['data']['price_history']={'XOM':[{'session_date':d,'price':v} for d,v in
        [('2025-12-31',98),('2026-01-02',99),('2026-01-05',100)]]}
    stock['data']['evidence_dictionary']=[e]
    write_json(run/'artifacts/global_stock_feed.json',stock)
    target=calculate(p['empirical_rule'],stock['data'],issue.isoformat(),(issue+timedelta(days=1)).isoformat())['XOM']['target_price']
    p['predictions_t'][0]['target_price']=target
    write_json(run/'artifacts/lab_director.json',{'status':'success','data':p})
    return run,p,stock,issue


def test_empirical_targets_are_recomputed_and_registered(case,tmp_path):
    run,p,_,issue=case
    assert validate_cp1(p).ok
    result=validate_cp2(p,subject_run_dir=run,expected_snapshot_time=issue.isoformat(),expected_target_time_iso=(issue+timedelta(days=1)).isoformat())
    assert result.ok,result.errors
    registered=feedback.register(tmp_path/'measure',run,fixture_policy(tmp_path/'policy.json'),'24h')
    assert registered['count']==1
    wrong=deepcopy(p);wrong['predictions_t'][0]['target_price']+=.01
    assert any('arithmetic mismatch' in e for e in validate_cp2(wrong,subject_run_dir=run).errors)
    assert not validate_cp2(p).ok  # A prose-only empirical declaration is insufficient.


@pytest.mark.parametrize('patch',[{'lookback_returns':True},{'scale':float('nan')},{'scale':0},
    {'max_abs_return':.5},{'evidence_refs':['[999]']},{'calibration_status':'VALIDATED'},
    {'target_ids':['XOM','XOM']},{'method':'invented'}])
def test_rule_rejects_unsupported_claims_and_malformed_parameters(case,patch):
    _,p,_,_=case;p=deepcopy(p);p['empirical_rule'].update(patch)
    assert rule_errors(p)


def test_history_cannot_skip_sessions_or_include_future(case):
    run,p,s,issue=case
    for day in ('2026-01-06','2026-01-01'):
        altered=deepcopy(s);altered['data']['price_history']['XOM'][-1]['session_date']=day
        write_json(run/'artifacts/global_stock_feed.json',altered)
        assert not validate_cp2(p,subject_run_dir=run).ok
    write_json(run/'artifacts/global_stock_feed.json',s)
    assert not validate_cp2(p,subject_run_dir=run,expected_target_time_iso='2026-01-07T21:00:00+00:00').ok
    p['evidence_dictionary'][0]['ledger_id']='S_DEADBEEF'
    assert not validate_cp2(p,subject_run_dir=run).ok


def test_cap_and_contrarian_scale_are_deterministic(case):
    _,p,s,issue=case;r=dict(p['empirical_rule'],scale=-1,max_abs_return=.001)
    x=calculate(r,s['data'],issue.isoformat(),(issue+timedelta(days=1)).isoformat())['XOM']
    assert x['predicted_return']==-.001
    assert x['target_price']==pytest.approx(99.9)


def test_native_director_and_oracle_cannot_refit_rule(case):
    run,p,_,issue=case
    engine=GodModeEngine.__new__(GodModeEngine)
    engine.run_dir=engine._subject_run_dir=run
    engine._run_anchor_iso=issue.isoformat();engine._target_time_iso=(issue+timedelta(days=1)).isoformat()
    engine._oracle_mode=False;engine._extract_cross_corr_v2_targets=lambda:{'XOM'}
    cp1=deepcopy(p);cp1['empirical_rule']['scale']=.25
    write_json(run/'artifacts/lab_decide.json',{'data':cp1})
    result=engine._validate_schema_output(SimpleNamespace(id='lab_director'),'isomorphic_cp2',p)
    assert any('FORECAST_RULE_MISMATCH' in e for e in result.errors)
    # The later Oracle cannot tune the scale even when its changed arithmetic is valid.
    changed=deepcopy(p);changed['empirical_rule']['scale']=.25
    engine._oracle_mode=True
    result=engine._validate_schema_output(SimpleNamespace(id='oracle_cp2_emitter'),'isomorphic_cp2',changed)
    assert any('FORECAST_RULE_MISMATCH' in e for e in result.errors)


def test_issuer_relabeling_is_not_source_grounding(case):
    run,p,s,_=case
    s['data']['evidence_dictionary'][0]=dict(s['data']['evidence_dictionary'][0],subject='HON')
    write_json(run/'artifacts/global_stock_feed.json',s)
    result=validate_cp2(p,subject_run_dir=run)
    assert any('issuer not bound' in e for e in result.errors)


@pytest.mark.parametrize('data',[[],None,{'evidence_dictionary':[None]}, {'evidence_dictionary':'wrong'}])
def test_malformed_source_fails_closed(case,data):
    run,p,s,_=case;s['data']=data;write_json(run/'artifacts/global_stock_feed.json',s)
    assert not validate_cp2(p,subject_run_dir=run).ok


def test_unbounded_json_integer_is_rejected_without_crash(case):
    _,p,_,_=case;p['empirical_rule']['scale']=10**400
    assert not validate_cp1(p).ok


def test_oracle_cannot_introduce_empirical_mapping_after_causal_subject(case):
    run,p,_,issue=case
    original=deepcopy(p);original.pop('forecast_basis');original.pop('empirical_rule')
    original['dominant_evidence_track']='FLOW_LED'
    write_json(run/'artifacts/lab_director.json',{'status':'success','data':original})
    engine=GodModeEngine.__new__(GodModeEngine)
    engine.run_dir=engine._subject_run_dir=run;engine._oracle_mode=True
    engine._run_anchor_iso=issue.isoformat();engine._target_time_iso=(issue+timedelta(days=1)).isoformat()
    engine._extract_cross_corr_v2_targets=lambda:{'XOM'}
    result=engine._validate_schema_output(SimpleNamespace(id='oracle_cp2_emitter'),'isomorphic_cp2',p)
    assert any('FORECAST_RULE_MISMATCH' in e for e in result.errors)
