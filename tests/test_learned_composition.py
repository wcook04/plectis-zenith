"""Native CP composition regression fixtures; no model/provider performance claim."""
from copy import deepcopy
from datetime import datetime
import json
from types import SimpleNamespace
import pytest
from test_daily_head import data, state, trained
from feedback.demo import fixture_run
from system.lib import learned_composition as composition
from system.lib.schema_validator import validate_cp1, validate_cp2
from system.lib.reasoning_policy import validate_reasoning_policy, policy_sha256
from system.core.engine import GodModeEngine
from zenith.providers import write_json


@pytest.fixture
def native(tmp_path):
    issue='2024-01-31T07:01:00+00:00';target='2024-02-01T07:00:00+00:00'
    run=fixture_run(tmp_path/'native',datetime.fromisoformat(issue),datetime.fromisoformat(target))
    raw=json.loads((run/'artifacts/lab_director.json').read_text())['data']
    d=data();d['stock']['columns']=['Ticker','Price']
    d['stock']['evidence_dictionary']=[{'ledger_id':f'S_{i:08X}','subject':s,'signal_summary':'Synthetic source price.'}
                                      for i,s in enumerate(d['symbols'],1)]
    news={'items':d['news'],'evidence_dictionary':[{'ledger_id':'N_00000001','subject':'000001,000002',
          'source_ref':'synthetic','signal_summary':'Synthetic economic information.'}]}
    for name,value in [('global_stock_feed',d['stock']),('global_news_feed',news)]:
        write_json(run/'artifacts'/f'{name}.json',{'metadata':{'as_of':issue},'data':value})
    raw['evidence_dictionary']=[{**d['stock']['evidence_dictionary'][0],'ref_id':'[1]'}]
    raw.update(forecast_basis='JUDGMENTAL',dominant_evidence_track='JUDGMENTAL',economic_state=state())
    model=trained()
    spec=json.loads((run/'zenith_run.json').read_text())
    spec['reasoning_policy']={'nodes':{'lab_decide':{'learned_head':model}}}
    write_json(run/'zenith_run.json',spec)
    return run,raw,model,issue,target


def materialized(native):
    run,raw,model,issue,target=native
    p=composition.materialize(raw,model,run,issue)
    p['predictions_t']=[{'target_id':r['target_id'],'direction':'UP' if r['q50']>0 else 'DOWN' if r['q50']<0 else 'FLAT',
                        'snapshot_price':100.,'target_price':100*(1+r['q50']),'snapshot_time':issue,
                        'target_time_iso':target,'invalidation':'Synthetic declared target.'}
                       for r in p['forecast_quantiles']['targets']]
    return p


def test_raw_state_is_preserved_and_native_quantiles_independently_replay(native):
    run,raw,model,issue,target=native;before=deepcopy(raw)
    p=materialized(native)
    assert raw==before and 'forecast_quantiles' not in raw
    assert validate_cp1(p).ok
    r=validate_cp2(p,subject_run_dir=run,expected_snapshot_time=issue,expected_target_time_iso=target)
    assert r.ok,r.errors
    assert composition.replay_errors(p,run,issue)==[]
    p['forecast_quantiles']['targets'][0]['q90']+=.01
    assert any('replayed' in e for e in composition.replay_errors(p,run,issue))


def test_raw_numerical_submission_conflicts_with_fitted_operator(native):
    run,raw,m,issue,_=native;raw['forecast_quantiles']={}
    with pytest.raises(ValueError,match='must not submit'):composition.materialize(raw,m,run,issue)


@pytest.mark.parametrize('defect',['source','state','model','origin'])
def test_derived_provenance_cannot_change(native,defect):
    run,_,_,issue,_=native;p=materialized(native)
    if defect=='source':
        path=run/'artifacts/global_news_feed.json';e=json.loads(path.read_text());e['data']['items'][0]['text']='different';write_json(path,e)
    if defect=='state':p['economic_state'][0][1]=-1
    if defect=='model':p['learned_head_derivation']['model']['coefficients'][0][0]+=1
    if defect=='origin':p['learned_head_derivation']['numerical_origin']='LLM'
    assert composition.replay_errors(p,run,issue)


def test_director_and_oracle_lock_representation_and_derivation(native):
    run,_,_,issue,target=native;p=materialized(native)
    write_json(run/'artifacts/lab_decide.json',{'data':p});write_json(run/'artifacts/lab_director.json',{'data':p})
    engine=GodModeEngine.__new__(GodModeEngine);engine.run_dir=engine._subject_run_dir=run
    engine._run_anchor_iso=issue;engine._target_time_iso=target
    engine._extract_cross_corr_v2_targets=lambda:{'000001','000002'}
    for oracle,node in [(False,'lab_director'),(True,'oracle_cp2_emitter')]:
        engine._oracle_mode=oracle
        bad=deepcopy(p);bad.pop('economic_state');bad.pop('learned_head_derivation')
        result=engine._validate_schema_output(SimpleNamespace(id=node),'isomorphic_cp2',bad)
        assert any('FORECAST_RULE_MISMATCH' in e for e in result.errors)


def test_policy_requires_declared_unabridged_sources(native):
    _,_,model,_,_=native
    p={'variant_id':'fixture','nodes':{'lab_decide':{'learned_head':model}}};p['policy_sha256']=policy_sha256(p)
    graph={'lab_decide':SimpleNamespace(dependencies=tuple(composition.SOURCE_EDGES))}
    assert validate_reasoning_policy(p,graph)==p
    graph['lab_decide'].dependencies=()
    with pytest.raises(ValueError,match='explicit'):validate_reasoning_policy(p,graph)
