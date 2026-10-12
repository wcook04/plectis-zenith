"""Synthetic learning signal and provenance tests; not financial evidence."""
from copy import deepcopy
from datetime import date, timedelta
import pytest
from research import daily_head as study
from system.lib import learned_head as head
from zenith.providers import digest
from zenith.budgeted import reservation_prices


def data(day='2024-01-31'):
    end = date.fromisoformat(day)
    bars = [{'session_date': (end-timedelta(days=20-i)).isoformat(), 'open':100.,'high':102.,'low':98.,
             'close':100.+(i%2),'volume':1000.} for i in range(21)]
    return {'issue_date':day,'issue_at':day+'T07:01:00+00:00','symbols':['000001','000002'],
        'stock':{'rows':[['000001',100.],['000002',100.]],'price_history':{'000001':deepcopy(bars),'000002':deepcopy(bars)},
                 'csi300_history':deepcopy(bars)},
        'news':[{'ledger_id':'N_00000001','entities':['000001','000002'],'available_at':day+'T07:00:00+00:00',
                 'text':'synthetic evidence','source_ref':'synthetic'}]}


def state(sign=1):
    return [[s,sign,None,None,['N_00000001']] for s in ('000001','000002')]


def trained(mode='economic'):
    rows=[]
    for i in range(36):
        day=(date(2023,1,31)+timedelta(days=i)).isoformat(); sign=(-1,0,1)[i%3]
        rows.append({'data':data(day), 'state':state(sign), 'y':[sign*.02,sign*.02],
                     'outcome_at':(date.fromisoformat(day)+timedelta(days=1)).isoformat()+'T07:00:00+00:00'})
    return study.fit(rows,mode,.001)


def test_known_economic_signal_is_learned_and_ablations_ignore_it():
    model=trained(); plus=head.predict(model,data(),state(1)); minus=head.predict(model,data(),state(-1))
    assert plus[0]['q50']==pytest.approx(.02,abs=.001)
    assert minus[0]['q50']==pytest.approx(-.02,abs=.001)
    for mode in ('price','metadata'):
        control=trained(mode)
        assert head.predict(control,data(),state(1))==head.predict(control,data(),state(-1))


@pytest.mark.parametrize('defect',['future','bool','uncited','issuer','unknown_cites','duplicate'])
def test_invalid_forward_states_fail(defect):
    d,s=data(),state()
    if defect=='future':d['news'][0]['available_at']='2025-01-01T00:00:00+00:00'
    if defect=='bool':s[0][1]=True
    if defect=='uncited':s[0][4]=[]
    if defect=='issuer':d['news'][0]['entities']=['000002']
    if defect=='unknown_cites':s[0][1]=None
    if defect=='duplicate':d['news'].append(deepcopy(d['news'][0]))
    with pytest.raises(ValueError):head.features(d,s,'price')


def test_model_and_source_binding_and_fit_maturity():
    m=trained()
    for field,value in [('fit_end','2025-01-01T07:00:00+00:00'),('feature_source_sha256','bad')]:
        bad=deepcopy(m);bad[field]=value;bad['model_sha256']=digest({k:v for k,v in bad.items() if k!='model_sha256'})
        with pytest.raises(ValueError):head.predict(bad,data(),state())
    m['coefficients'][0][0]+=1
    with pytest.raises(ValueError):head.predict(m,data(),state())


def test_quote_and_window_alignment():
    for defect in ('quote','window','future'):
        d=data()
        if defect=='quote':d['stock']['rows'][0][1]=99.
        if defect=='window':d['stock']['price_history']['000001'][0]['session_date']='2000-01-01'
        if defect=='future':d['stock']['csi300_history'][-1]['session_date']='2025-01-01'
        with pytest.raises(ValueError):head.features(d,state(),'price')


def test_transport_failure_is_never_null_state_or_completed_encoding(tmp_path,monkeypatch):
    d=data();study.immutable(tmp_path/'inputs'/f'{d["issue_date"]}.json',d)
    study.immutable(tmp_path/'spec.json',{})
    spec={'encoder':head.ENCODER,'model':'test/model','provider_slug':'test','budget':str(tmp_path/'budget'),
          'limits':{},'inputs':{d['issue_date']:'hash'}}
    class Provider:
        def __init__(self,*a,**kw):pass
        def ask_ai(self,*a):raise RuntimeError('unknown cost, halted ledger')
    monkeypatch.setattr(study,'OpenRouterBudgetedProvider',Provider)
    with pytest.raises(RuntimeError,match='halted'):study.encode_one(tmp_path,spec,d['issue_date'])
    assert not (tmp_path/'encoding'/d['issue_date']/'accepted.json').exists()


def test_conditional_price_ceiling_is_reserved_even_outside_current_window():
    from decimal import Decimal
    p=reservation_prices({'prompt':'0.1','completion':'0.2','overrides':[
        {'utc_days':['monday'],'utc_start':100,'utc_end':400,'prompt':'0.3','completion':'0.5'},
        {'utc_start':400,'utc_end':100,'prompt':'0.05','completion':'0.1'}]})
    assert p['prompt']==Decimal('.3') and p['completion']==Decimal('.5')
    for bad in ({'overrides':[{'new_charge':'1'}]}, {'overrides':'unknown'}, {'overrides':[{'prompt':'NaN'}]}):
        with pytest.raises(ValueError):reservation_prices(bad)


def test_sealed_encoding_drift_and_incomplete_support_are_rejected(tmp_path):
    spec={'phases':{'training':['2023-01-01'],'assessment':['2025-01-01']}}
    for day in ('2023-01-01','2025-01-01'):
        study.immutable(tmp_path/'encoding'/day/'accepted.json',{'state':[]})
    files={d:study.sha(tmp_path/'encoding'/d/'accepted.json') for dates in spec['phases'].values() for d in dates}
    study.immutable(tmp_path/'encodings-sealed.json',{'files':files})
    study.verify_encodings(tmp_path,spec)
    (tmp_path/'encoding'/'2025-01-01'/'accepted.json').write_text('{"state":[1]}')
    with pytest.raises(ValueError,match='drift'):study.verify_encodings(tmp_path,spec)


def test_assessment_attempt_seal_cannot_be_reopened(tmp_path,monkeypatch):
    monkeypatch.setattr(study,'load',lambda p:{})
    monkeypatch.setattr(study,'verify_encodings',lambda *a:None)
    study.immutable(tmp_path/'selection.json',{})
    study.immutable(tmp_path/'selection-hash.json',{'sha256':study.sha(tmp_path/'selection.json')})
    study.immutable(tmp_path/'assessment-seal.json',{})
    with pytest.raises(ValueError,match='consumed'):study.assess(tmp_path)
