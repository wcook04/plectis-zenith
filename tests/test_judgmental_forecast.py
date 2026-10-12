"""Native uncertainty arithmetic, immutable beliefs and source boundaries."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
import pytest
from feedback.demo import fixture_run, fixture_policy
from feedback import engine as feedback
from research.engine import read_json, write_json
from system.lib.judgmental_forecast import score_quantiles
from system.lib.schema_validator import validate_cp1, validate_cp2, validate_prediction_reconciliation
from system.core.engine import GodModeEngine
from tools.oracle import truth_diff_equity

@pytest.fixture
def case(tmp_path):
    issue=datetime(2026,1,5,21,tzinfo=timezone.utc)
    run=fixture_run(tmp_path/'subject',issue,issue+timedelta(days=1),target=100)
    p=read_json(run/'artifacts/lab_director.json')['data'];e=p['evidence_dictionary'][0]
    p.update(forecast_basis='JUDGMENTAL',dominant_evidence_track='JUDGMENTAL',forecast_quantiles={
      'method':'evidence_conditioned_quantiles_v1','calendar':'XNYS','units':'simple_return_fraction',
      'calibration_status':'UNVALIDATED','targets':[{'target_id':'XOM','q10':-.02,'q50':0.,'q90':.03,
      'evidence_refs':[e['ref_id']],'reasoning':'Synthetic zero median with uncertainty; not a point mass or observed skill.'}]})
    p['predictions_t'][0]['direction']='FLAT'
    stock=read_json(run/'artifacts/global_stock_feed.json');stock['metadata']['as_of']=issue.isoformat()
    stock['data']['price_history']={'XOM':[{'session_date':'2026-01-05','price':100}]}
    stock['data']['evidence_dictionary']=[e];write_json(run/'artifacts/global_stock_feed.json',stock)
    write_json(run/'artifacts/lab_director.json',{'status':'success','data':p})
    return run,p,stock,issue


def test_zero_median_registers_and_scores_the_same_in_oracle_and_feedback(case,tmp_path):
    run,p,_,issue=case
    assert validate_cp1(p).ok
    result=validate_cp2(p,subject_run_dir=run);assert result.ok,result.errors
    truth=fixture_run(tmp_path/'truth',issue+timedelta(days=1),issue+timedelta(days=2),target=101)
    s=read_json(truth/'artifacts/global_stock_feed.json');s['data']['rows'][0][1]=101
    write_json(truth/'artifacts/global_stock_feed.json',s)
    x=truth_diff_equity.run({'runtime':{'oracle_subject_run_dir':str(run),'oracle_truth_run_dir':str(truth)}})['data']
    assert validate_prediction_reconciliation(x).ok
    row=x['rows'][0]
    assert row['mean_quantile_pinball_loss']==pytest.approx((.003+.005+.002)/3)
    assert row['interval_80_covered'] is True
    assert row['prediction_direction']=='FLAT'
    assert row['directional_correct'] is False  # sign diagnostic; not a probability claim
    assert row['forecast_quantiles']==p['forecast_quantiles']['targets'][0]
    reg=feedback.register(tmp_path/'feedback',run,fixture_policy(tmp_path/'policy.json'),'24h')
    assert reg['count']==1
    out=feedback.score(tmp_path/'feedback',truth/'artifacts/global_stock_feed.json',(issue+timedelta(days=2)).isoformat())
    assert out['statuses']=={'scored':1}
    assert out['evaluations'][0]['metrics']['mean_quantile_pinball_loss']==row['mean_quantile_pinball_loss']

@pytest.mark.parametrize('field,value',[('q10',.1),('q50',True),('q90',float('nan')),('q10',-1),('q90',10**400),('evidence_refs',['[999]']),('target_id','XOM '),('reasoning','')])
def test_malformed_beliefs_fail_closed(case,field,value):
    run,p,_,_=case;p=deepcopy(p);p['forecast_quantiles']['targets'][0][field]=value
    assert not validate_cp1(p).ok


def test_freeze_median_and_all_quantiles_through_director_and_oracle(case):
    run,p,_,issue=case
    engine=GodModeEngine.__new__(GodModeEngine);engine.run_dir=engine._subject_run_dir=run
    engine._run_anchor_iso=issue.isoformat();engine._target_time_iso=(issue+timedelta(days=1)).isoformat()
    engine._extract_cross_corr_v2_targets=lambda:{'XOM'}
    write_json(run/'artifacts/lab_decide.json',{'data':p})
    changed=deepcopy(p);changed['forecast_quantiles']['targets'][0]['q90']=.04
    for oracle,node in [(False,'lab_director'),(True,'oracle_cp2_emitter')]:
        engine._oracle_mode=oracle
        r=engine._validate_schema_output(SimpleNamespace(id=node),'isomorphic_cp2',changed)
        assert any('FORECAST_RULE_MISMATCH' in e for e in r.errors)


def test_original_citations_target_set_arithmetic_and_clock_are_binding(case):
    run,p,_,_=case
    for mutation in ('citation','arithmetic','missing','horizon','source_ref'):
        bad=deepcopy(p)
        if mutation=='citation':bad['evidence_dictionary'][0]['ledger_id']='S_DEADBEEF'
        if mutation=='source_ref':bad['evidence_dictionary'][0]['source_ref']='invented'
        if mutation=='arithmetic':bad['predictions_t'][0]['target_price']=100.001
        if mutation=='missing':bad['predictions_t']=[]
        if mutation=='horizon':bad['predictions_t'][0]['target_time_iso']='2026-01-07T21:00:00+00:00'
        assert not validate_cp2(bad,subject_run_dir=run).ok,mutation
    assert not validate_cp2(p).ok


def test_holiday_and_numeric_issuer_source_calendar(case):
    run,p,stock,_=case;p=deepcopy(p);stock=deepcopy(stock)
    issue='2023-09-28T07:01:00+00:00';target='2023-10-09T07:00:00+00:00'
    p['evidence_dictionary'][0]['subject']='000858'
    p['forecast_quantiles']['calendar']='XSHG';p['forecast_quantiles']['targets'][0]['target_id']='000858'
    p['predictions_t'][0].update(target_id='000858',snapshot_time=issue,target_time_iso=target)
    stock['data']['rows'][0][0]='000858';stock['data']['evidence_dictionary']=p['evidence_dictionary']
    stock['data']['price_history']={'000858':[{'session_date':'2023-09-28','close':100}]};stock['metadata']['as_of']=issue
    write_json(run/'artifacts/global_stock_feed.json',stock)
    assert validate_cp2(p,subject_run_dir=run).ok
    p['forecast_quantiles']['calendar']='XNYS'
    assert not validate_cp2(p,subject_run_dir=run).ok


def test_interval_boundary_and_wrong_units_are_not_hidden(case):
    _,p,_,_=case;r=p['forecast_quantiles']['targets'][0]
    assert score_quantiles(r,-.02)['interval_80_covered']
    assert not score_quantiles(r,.03001)['interval_80_covered']
    assert score_quantiles(r,.5)['mean_quantile_pinball_loss']>score_quantiles(r,0)['mean_quantile_pinball_loss']
    p['forecast_quantiles']['units']='percent';assert not validate_cp1(p).ok


def test_legacy_cannot_smuggle_quantiles_or_flat(case):
    run,p,_,_=case;p=deepcopy(p);p.pop('forecast_basis');p['dominant_evidence_track']='FLOW_LED'
    assert not validate_cp1(p).ok
    p.pop('forecast_quantiles');assert not validate_cp2(p,subject_run_dir=run).ok


def test_citation_mapping_cannot_change_to_another_valid_source_after_cp1(case):
    run,p,s,issue=case
    p=deepcopy(p);original=deepcopy(p)
    extra=dict(p['evidence_dictionary'][0],ledger_id='S_00000002')
    s['data']['evidence_dictionary'].append(extra);write_json(run/'artifacts/global_stock_feed.json',s)
    p['evidence_dictionary'][0]['ledger_id']='S_00000002'
    assert validate_cp2(p,subject_run_dir=run).ok  # source-valid alone is weaker than the freeze
    write_json(run/'artifacts/lab_decide.json',{'data':original})
    write_json(run/'artifacts/lab_director.json',{'data':original})
    engine=GodModeEngine.__new__(GodModeEngine);engine.run_dir=engine._subject_run_dir=run
    engine._run_anchor_iso=issue.isoformat();engine._target_time_iso=(issue+timedelta(days=1)).isoformat()
    engine._extract_cross_corr_v2_targets=lambda:{'XOM'}
    for oracle,node in [(False,'lab_director'),(True,'oracle_cp2_emitter')]:
        engine._oracle_mode=oracle
        assert any('FORECAST_RULE_MISMATCH' in e for e in engine._validate_schema_output(SimpleNamespace(id=node),'isomorphic_cp2',p).errors)

@pytest.mark.parametrize('text',['Unresolved [999]','Malformed [1,2]'])
def test_reasoning_citations_must_resolve(case,text):
    _,p,_,_=case;p=deepcopy(p);p['forecast_quantiles']['targets'][0]['reasoning']=text
    assert not validate_cp1(p).ok

@pytest.mark.parametrize('defect',['date','currency','basis','duplicate'])
def test_oracle_refuses_wrong_horizon_or_price_definition(case,tmp_path,defect):
    run,p,_,issue=case
    truth=fixture_run(tmp_path/'truth',issue+timedelta(days=1),issue+timedelta(days=2))
    path=truth/'artifacts/global_stock_feed.json';s=read_json(path)
    if defect=='date':s['data']['rows'][0][2]=(issue+timedelta(days=2)).isoformat()
    if defect=='currency':s['metadata']['currency']='CNY'
    if defect=='basis':s['metadata']['price_basis']='rebased_wealth'
    if defect=='duplicate':s['data']['rows'].append(s['data']['rows'][0])
    write_json(path,s)
    with pytest.raises(ValueError,match='Judgmental truth'):
        truth_diff_equity.run({'runtime':{'oracle_subject_run_dir':str(run),'oracle_truth_run_dir':str(truth)}})


def test_reasoning_cannot_use_unbound_but_resolved_reference(case):
    _,p,_,_=case;p=deepcopy(p)
    p['evidence_dictionary'].append(dict(p['evidence_dictionary'][0],ref_id='[2]',ledger_id='N_00000002'))
    p['forecast_quantiles']['targets'][0]['reasoning']='This otherwise valid reference is outside frozen evidence_refs [2].'
    assert not validate_cp1(p).ok
