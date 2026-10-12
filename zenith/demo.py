"""Construct an independently authored abstract-system example offline."""
from __future__ import annotations
import hashlib
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from tools.observations.derived import run as calculate
LANES = ('measurements','subsystems','environment','events','interventions')
EARLIER = '2026-07-20T12:00:00+00:00'
LATER = '2026-07-21T12:00:00+00:00'

def write(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False)+'\n')

def sha(data):
    return hashlib.sha256(data).hexdigest()

def state_at(anchor):
    """Disclosed toy recurrence, seed 17; demonstrates protocol, not blind forecasting."""
    import random
    clock=datetime.fromisoformat(anchor.replace('Z','+00:00'))
    step=(clock-datetime.fromisoformat(EARLIER)).days
    if step < 0: raise ValueError('Toy observation precedes disclosed origin')
    rng=random.Random(17)
    state=-0.4
    for index in range(step):
        context=(index%3-1)*0.2
        control=0.3 if index%2 else -0.1
        state=0.7*state+0.2*context+control+rng.uniform(-0.02,0.02)
    return {'signal_a':round(state,6),'signal_b':round(2*state,6),
            'context_a':round((step%3-1)*0.2,6),'control_a':0.3 if step%2 else -0.1}


def synthetic(lane, anchor, later=False):
    state=state_at(anchor)
    numeric={'measurements':[('SIGNAL_A',state['signal_a']),('SIGNAL_B',state['signal_b'])],
             'subsystems':[('SUBSYSTEM_A',state['signal_a']/2),('SUBSYSTEM_B',-state['signal_a'])],
             'environment':[('CONTEXT_A',state['context_a'])]}
    if lane in numeric:
        observations=[{'target_id':target,'value':value,'unit':'dimensionless',
                       'observed_at':anchor,'available_at':anchor} for target,value in numeric[lane]]
        data={'observations':observations,'columns':['target_id','Value','unit','observed_at','available_at'],
              'rows':[[r['target_id'],r['value'],r['unit'],anchor,anchor] for r in observations]}
    else:
        clock=datetime.fromisoformat(anchor.replace('Z','+00:00'))
        item={'id':lane+'-system-a','system_id':'System A','observed_at':anchor,'available_at':anchor}
        if lane=='interventions':
            item.update(control_a=state['control_a'],unit='dimensionless',command_status='planned',
                        effective_at=(clock+timedelta(days=1)).isoformat(),
                        text='Authored plan: apply the disclosed control input during the next state transition.')
            items=[item]
            if anchor!=EARLIER:
                previous=(clock-timedelta(days=1)).isoformat()
                items.append({'id':'executed-system-a','system_id':'System A','control_a':state_at(previous)['control_a'],
                              'unit':'dimensionless','command_status':'executed','issued_at':previous,
                              'effective_at':anchor,'observed_at':anchor,'available_at':anchor,
                              'text':'Authored record: the previously issued control was applied in this transition.'})
        else:
            category='negative' if state['context_a']<0 else 'positive' if state['context_a']>0 else 'neutral'
            item.update(text='Authored qualitative record: current context is '+category+'.',
                        event_kind='context_observation',context_category=category,
                        interpretation_boundary='A qualitative view of the existing context input, not independent corroboration.')
            items=[item]
        data={'items':items}
    # One deliberately missing later reading illustrates incomplete target support.
    # The underlying toy state remains disclosed; absence is never a scored outcome.
    if lane=='measurements' and anchor!=EARLIER:
        data['observations'][1].update(value=None,observation_status='missing')
        data['rows'][1][1]=None
        data['missingness']=[{'target_id':'SIGNAL_B','reason':'Authored example of an unavailable sensor reading.'}]
    prefix={'measurements':'S','subsystems':'E','environment':'M','events':'N','interventions':'P'}[lane]
    records=data.get('observations',data.get('items',[]))
    data['evidence_dictionary']=[{'ledger_id':prefix+'_'+sha((lane+'|'+anchor+'|'+str(index)).encode())[:8].upper(),
                                 'subject':record.get('target_id','System A'),
                                 'signal_summary':json.dumps(record,sort_keys=True),
                                 'source_ref':'authored_synthetic/'+lane+'/'+anchor,
                                 'observed_at':anchor,'available_at':anchor}
                                for index,record in enumerate(records)]
    data['synthetic_fixture']=True
    return {'id':f'global_{lane}_feed','status':'success',
            'metadata':{'status':'success','as_of':anchor,'timestamp_iso':anchor,
                        'synthetic_fixture':True,'data_origin':'authored_synthetic',
                        'observation_basis':'explicit_observation','unit':'dimensionless',
                        'notice':'Disclosed synthetic System A generator. Protocol example, not blind forecasting evidence.'},'data':data}


def prepare(root, earlier=None, later=None, output=None):
    if output is None:
        raise ValueError('A new output directory is required')
    if earlier is not None or later is not None:
        raise ValueError('Synthetic demo accepts no source snapshots; no existing data is relabelled')
    output=Path(output).resolve()
    if output.exists(): raise ValueError('Demo output must be a new directory; existing evidence is never overwritten')
    receipt={'schema':'zenith_synthetic_demo_v1','data_mode':'authored_synthetic',
             'scenario':'abstract System A','snapshots':[], 'model_calls':0,
             'execution_status':'inputs_prepared','claim_boundary':'Input preparation only; no model forecasts or improvement evidence.'}
    fixtures={'schema':'zenith_synthetic_observations_v1','snapshots':[]}
    for name,anchor,is_later in (('earlier',EARLIER,False),('later',LATER,True)):
        directory=output/name
        write(directory/'runtime_context.json',{'as_of':anchor,'time_anchor':anchor,'subject_group':'feeds','data_mode':'authored_synthetic'})
        artifacts={}
        for lane in LANES:
            artifact=synthetic(lane,anchor,is_later)
            write(directory/'artifacts'/f'global_{lane}_feed.json',artifact)
            artifacts[artifact['id']]=artifact
        derived=calculate({},run_dir=directory)
        derived.update(id='global_derived_feed',status='success')
        derived['metadata'].update(as_of=anchor,timestamp_iso=anchor)
        write(directory/'artifacts/global_derived_feed.json',derived)
        artifacts[derived['id']]=derived
        lanes=[{'node_id':key,'input_origin':'derived_synthetic_inputs' if key=='global_derived_feed' else 'authored_synthetic',
                'input_sha256':sha((directory/'artifacts'/f'{key}.json').read_bytes()),'public_payload':'included',
                'permission_status':'original_fixture'} for key in artifacts]
        receipt['snapshots'].append({'id':name,'as_of':anchor,'lanes':lanes})
        fixtures['snapshots'].append({'id':name,'as_of':anchor,'artifacts':artifacts})
    write(output/'public/provenance.json',receipt)
    write(output/'public/observations.json',fixtures)
    write(output/'public/replacements.json',fixtures)
    return receipt
