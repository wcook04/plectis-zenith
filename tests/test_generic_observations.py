"""Generic protocol boundaries, independent of any domain-specific data."""
from datetime import datetime,timedelta,timezone
import json
from pathlib import Path
import pytest
from zenith import demo,runtime,daily
from zenith.providers import write_json
from feedback import engine
from feedback.demo import fixture_run,fixture_policy
from system.core.engine import GodModeEngine
from system.lib.schema_validator import validate_cp2
ROOT=Path(__file__).resolve().parents[1]

def test_fresh_demo_is_reproducible_and_wholly_authored(tmp_path):
    a,b=tmp_path/'a',tmp_path/'b'
    left=demo.prepare(ROOT,output=a);right=demo.prepare(ROOT,output=b)
    assert left==right and left['model_calls']==0
    assert all(len(s['lanes'])==6 for s in left['snapshots'])
    assert all(l['public_payload']=='included' for s in left['snapshots'] for l in s['lanes'])
    assert (a/'public/observations.json').read_bytes()==(b/'public/observations.json').read_bytes()
    assert (a/'public/replacements.json').read_bytes()==(a/'public/observations.json').read_bytes()
    with pytest.raises(ValueError,match='no source'):demo.prepare(ROOT,a,b,tmp_path/'c')
    with pytest.raises(ValueError,match='new directory'):demo.prepare(ROOT,output=a)

def test_cutoff_enforces_observation_and_availability(tmp_path):
    demo.prepare(ROOT,output=tmp_path/'pair')
    source=tmp_path/'pair/earlier';anchor=runtime.stamp(demo.EARLIER)
    runtime.forward_preflight(ROOT,source,anchor)
    path=source/'artifacts/global_measurements_feed.json';payload=json.loads(path.read_text())
    payload['data']['observations'][0]['available_at']=demo.LATER
    write_json(path,payload)
    with pytest.raises(ValueError,match='later than cutoff'):runtime.forward_preflight(ROOT,source,anchor)
    payload['data']['observations'][0]['available_at']=demo.EARLIER
    write_json(path,payload)
    event_path=source/'artifacts/global_events_feed.json'
    events=json.loads(event_path.read_text());events['data']['items'][0]['available_at']=demo.LATER
    write_json(event_path,events)
    with pytest.raises(ValueError,match='later than cutoff'):runtime.forward_preflight(ROOT,source,anchor)

def test_explicit_horizon_and_zero_negative_feedback(tmp_path):
    issue=datetime(2026,1,5,12,tzinfo=timezone.utc);horizon=issue+timedelta(days=1)
    assert GodModeEngine.resolve_horizon(horizon.isoformat(),issue)['target_time']==horizon.isoformat()
    with pytest.raises(ValueError,match='timezone'):GodModeEngine.resolve_horizon('2026-01-06T12:00:00',issue)
    with pytest.raises(ValueError,match='follow'):GodModeEngine.resolve_horizon(issue.isoformat(),issue)
    policy=fixture_policy(tmp_path/'policy.json')
    for index,(snapshot,target,actual) in enumerate(((-2,-1,0),(0,1,-1))):
        source=fixture_run(tmp_path/f'lab{index}',issue,horizon,snapshot=snapshot,target=target)
        store=tmp_path/f'store{index}';engine.register(store,source,policy,'24h')
        truth=tmp_path/f'truth{index}.json'
        write_json(truth,{'status':'success','data':{'observations':[{'target_id':'SIGNAL_A','value':actual,'unit':'dimensionless','observed_at':horizon.isoformat(),'available_at':horizon.isoformat()}]}})
        score=engine.score(store,truth,horizon.isoformat())
        assert score['evaluations'][0]['status']=='scored'
        assert score['evaluations'][0]['metrics']['target_value_absolute_error']==abs(target-actual)

def test_missing_truth_and_unit_mismatch_never_score(tmp_path):
    issue=datetime(2026,1,5,12,tzinfo=timezone.utc);horizon=issue+timedelta(days=1)
    source=fixture_run(tmp_path/'lab',issue,horizon);store=tmp_path/'store'
    engine.register(store,source,fixture_policy(tmp_path/'policy.json'),'24h')
    truth=tmp_path/'truth.json'
    write_json(truth,{'status':'success','data':{'observations':[]}})
    assert engine.score(store,truth,horizon.isoformat())['evaluations'][0]['status']=='data_gap'
    write_json(truth,{'status':'success','data':{'observations':[{'target_id':'SIGNAL_A','value':101,'unit':'other','observed_at':horizon.isoformat(),'available_at':horizon.isoformat()}]}})
    assert engine.score(store,truth,horizon.isoformat())['evaluations'][0]['status']=='data_gap'

def test_generic_daily_uses_authored_snapshots_without_calendar_dependency(tmp_path):
    dataset=tmp_path/'dataset';write_json(dataset/'source-manifest.json',{'schema':'zenith_synthetic_source_v1','start_date':'2026-07-20'})
    result=daily.initialize(ROOT,tmp_path/'programme',dataset,'2026-07-20','2026-07-21')
    manifest=json.loads((tmp_path/'programme/daily.json').read_text())
    assert len(manifest['snapshots'])==3
    assert all(len(s['files'])==6 for s in manifest['snapshots'])


def test_perspectives_have_meaningful_overlap_controls_and_missingness():
    earlier=demo.synthetic('interventions',demo.EARLIER)['data']['items']
    later=demo.synthetic('interventions',demo.LATER)['data']['items']
    assert earlier[0]['command_status']=='planned' and earlier[0]['effective_at']==demo.LATER
    assert {item['command_status'] for item in later}=={'planned','executed'}
    assert later[1]['control_a']==earlier[0]['control_a']
    event=demo.synthetic('events',demo.EARLIER)['data']['items'][0]
    assert event['context_category']=='negative'
    missing=demo.synthetic('measurements',demo.LATER)['data']['observations'][1]
    assert missing['value'] is None and missing['observation_status']=='missing'
    graph=runtime.load_graph(ROOT)
    assert 'Temporal association with a control' in graph['lab_miner_interventions'].instruction
    assert 'not independent corroboration' in graph['lab_miner_derived'].instruction


def test_truth_availability_is_required_and_ordered(tmp_path):
    issue=datetime(2026,1,5,12,tzinfo=timezone.utc);horizon=issue+timedelta(days=1)
    source=fixture_run(tmp_path/'lab',issue,horizon);store=tmp_path/'store'
    engine.register(store,source,fixture_policy(tmp_path/'policy.json'),'24h')
    truth=tmp_path/'truth.json'
    row={'target_id':'SIGNAL_A','value':101,'unit':'dimensionless','observed_at':horizon.isoformat()}
    for availability in (None,'invalid',issue.isoformat()):
        candidate=dict(row)
        if availability is not None:candidate['available_at']=availability
        write_json(truth,{'status':'success','data':{'observations':[candidate]}})
        result=engine.score(store,truth,horizon.isoformat())['evaluations'][0]
        assert result['status']=='data_gap' and result['metrics'] is None
