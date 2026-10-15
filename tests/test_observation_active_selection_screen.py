"""Native offline controls and custody; no real model calls."""
import copy
import hashlib
import json

import pytest

from research import observation_active_selection_screen as active
from research import observation_candidate_pool_screen as pool
from research import observation_repair_screen as repair
from zenith.providers import digest, write_json
from test_observation_candidate_pool_screen import parents, FixtureProvider, LOOKUP


@pytest.fixture(scope='module')
def parent(tmp_path_factory):
    root=tmp_path_factory.mktemp('active-parent'); paths,_=parents(root)
    ancestor=root/'v5'; targets=repair.read(paths[0]/'datasets.json')['targets']
    data=repair.read(ancestor/'datasets.json'); frozen=repair.read(ancestor/'all-frozen.json'); calls={}
    data['private']={'configs':{t['source_id']:t['config'] for t in targets}}
    for index,(record,target) in enumerate(zip(frozen,targets)):
        record['source_id']=target['source_id']; record['arms']={}
        for arm in ('incremental','archive','fresh'):
            trials=[]
            for step in range(6):
                episode,local=(0,step) if arm=='fresh' else divmod(step,2)
                node=f'world-{index:02d}-{arm}-{episode}-{local}'
                proposal={'source':LOOKUP+f'# {arm} {step}','scope':'fixture','lesson':''}; raw=json.dumps(proposal)
                prompt={'prompt':{'history':target['history']},'system':'fixture','schema':repair.PROGRAM_SCHEMA}
                write_json(ancestor/'prompts'/f'{node}.json',prompt); write_json(ancestor/'responses'/f'{node}-raw.json',{'content':raw})
                calls[node]={'node_id':node,'call_id':digest(node),'requested_model':'fixture','requested_provider_slug':'fixture',
                    'response_sha256':hashlib.sha256(raw.encode()).hexdigest(),
                    'prompt_sha256':hashlib.sha256(json.dumps(prompt['prompt'],ensure_ascii=False).encode()).hexdigest(),
                    'system_prompt_sha256':hashlib.sha256(prompt['system'].encode()).hexdigest(),
                    'response_format_sha256':digest({'type':'json_schema','json_schema':{'name':'observation','strict':True,'schema':prompt['schema']}}),
                    'provider_response':{'choices':[{'message':{'content':raw}}]}}
                trials.append({'proposal':proposal,'response_error':None})
            record['arms'][arm]={'rounds':trials}
    protocol={'dataset_sha256':digest(data),'source':repair.archive(ancestor,repair.dependencies())}
    for name,value in [('datasets',data),('protocol',protocol),('all-frozen',frozen),
        ('preparation-receipt',{'protocol_sha256':digest(protocol),'dataset_sha256':digest(data)}),
        ('all-frozen-receipt',{'protocol_sha256':digest(protocol),'frozen_sha256':digest(frozen)}),
        ('results',{'frozen_sha256':digest(frozen)}),('budget/budget',{'entries':calls})]:
        write_json(ancestor/f'{name}.json',value)
    for path in paths:
        p=repair.read(path/'protocol.json'); p.update(parent_protocol_sha256=digest(protocol),parent_frozen_sha256=digest(frozen))
        f=repair.read(path/'all-frozen.json'); d=repair.read(path/'datasets.json')
        write_json(path/'protocol.json',p)
        write_json(path/'preparation-receipt.json',{'protocol_sha256':digest(p),'dataset_sha256':digest(d)})
        write_json(path/'all-frozen-receipt.json',{'protocol_sha256':digest(p),'frozen_sha256':digest(f)})
    output=root/'pool'; pool.prepare(output,*paths,pool_size=2,confirmation_size=3)
    pool.run(output, providers={m: FixtureProvider(m) for m in pool.MODELS})
    calls={}
    for raw_path in (output/'responses').glob('*-raw.json'):
        node=raw_path.name.removesuffix('-raw.json'); raw=repair.read(raw_path)['content']; prompt=repair.read(output/'prompts'/f'{node}.json')
        calls[node]={'node_id':node,'call_id':digest(node),'response_sha256':hashlib.sha256(raw.encode()).hexdigest(),
            'prompt_sha256':hashlib.sha256(json.dumps(prompt['prompt'],ensure_ascii=False).encode()).hexdigest(),
            'system_prompt_sha256':hashlib.sha256(prompt['system'].encode()).hexdigest(),
            'response_format_sha256':digest({'type':'json_schema','json_schema':{'name':'observation','strict':True,'schema':prompt['schema']}}),
            'provider_response':{'choices':[{'message':{'content':raw}}]}}
    write_json(output/'budget/budget.json',{'entries':calls})
    return output


def forbidden(*args, **kwargs):
    raise AssertionError('unchosen native label touched')


def test_preparation_seals_inventory_and_disjoint_actions_without_native_labels(tmp_path, parent, monkeypatch):
    monkeypatch.setattr(repair, 'observe', forbidden); monkeypatch.setattr(repair, 'cases', forbidden)
    output = tmp_path/'active'
    protocol = active.prepare(output, parent, probe_pool_size=3, final_size=4)
    data = repair.read(output/'datasets.json')
    assert protocol['calls'] == 0 and protocol['inventory_sha256'] == digest([t['inventory'] for t in data['targets']])
    assert len(data['targets']) == 3 and all(len(t['inventory']) == 8 for t in data['targets'])
    assert all(len(t['historical_inventory'])==18 for t in data['targets'])
    assert protocol['historical']['attempts_per_source']==18
    forbidden_shapes = {tuple(tuple(a) for a in shape) for shape in data['excluded_structures']}
    probes = {repair.shape(a) for a in data['probe_actions']}; final = {repair.shape(a) for a in data['final_actions']}
    assert len(probes) == 3 and len(final) == 4
    assert not (probes & final or probes & forbidden_shapes or final & forbidden_shapes)
    assert 'research/observation_active_selection_screen.py' in protocol['runtime_dependencies']


def test_candidate_predictions_never_construct_native_keys(parent, monkeypatch):
    data = repair.read(parent/'datasets.json'); frozen = repair.read(parent/'all-frozen.json')
    target = {**data['targets'][0], 'inventory': frozen[0]['arms']['deepseek4']['slots']+frozen[0]['arms']['qwen4']['slots']}
    monkeypatch.setattr(repair, 'observe', forbidden); monkeypatch.setattr(repair, 'cases', forbidden)
    predicted = active.predictions(target, target['history'], [[{'op':'put','key':'new','value':7}]])
    assert len(predicted) == 8 and all(len(p['rows']) == 3 for p in predicted)
    assert all(set(row) == {'answer','error','trace'} for p in predicted for row in p['rows'])


def test_disagreement_excludes_errors_and_duplicate_code_votes():
    def candidate(source, values, error=None):
        return {'source_sha256': source, 'rows': [{'answer':{'value':v,'unresolved':v is None}, 'error':error}
            for v in values for goal in range(3)]}
    predicted = [candidate('a',[0,1]), candidate('b',[0,2]), candidate('b',[0,2]),
                 candidate('broken',[99,99],'different arbitrary error'), candidate('abstain',[None,None])]
    choice, scores = active.choose('disagreement', predicted, [0,1])
    assert choice == 1 and scores == {0:6,1:9}
    assert active.choose('fixed', predicted, [0,1])[0] == 0


def test_full_native_run_freezes_before_audit_and_exact_replays(tmp_path, parent, monkeypatch):
    output = tmp_path/'active'; active.prepare(output,parent,probe_pool_size=2,final_size=3)
    original_observe, original_audit = repair.observe, active.audit
    measured = []
    def observe(config, actions):
        assert not (output/'all-frozen.json').exists()
        measured.append((config.source_id, actions)); return original_observe(config,actions)
    def audit(protocol,data,frozen):
        assert len(measured) == 12 and (output/'all-frozen-receipt.json').exists()
        return original_audit(protocol,data,frozen)
    monkeypatch.setattr(repair,'observe',observe); monkeypatch.setattr(active,'audit',audit)
    result = active.run(output)
    assert result['calls'] == 0 and result['native_probe_measurements'] == 12
    assert len(list((output/'probes').glob('*.json'))) == 12
    protocol,data = repair.verify(output); frozen = repair.read(output/'all-frozen.json')
    for r in frozen:
        for state in r['policies'].values():
            assert state['history'][-2:] == [s['receipt'] for s in state['rounds']]
            assert state['initial'] == r['initial']
    assert {v['total'] for v in result['aggregate'].values()} == {27}
    monkeypatch.setattr(repair,'observe',original_observe)
    replay = active.replay_records(protocol,data,frozen,{}, {})
    assert replay['native_receipts_replayed'] == 12 and not replay['protected_evaluation_performed']
    assert digest(result) == digest(original_audit(protocol,data,frozen))
    altered = copy.deepcopy(frozen); altered[0]['policies']['fixed']['rounds'][0]['receipt']['observed']['channel'] += 1
    with pytest.raises(ValueError,match='receipt replay'): active.replay_records(protocol,data,altered)
    altered = copy.deepcopy(frozen); altered[0]['policies']['fixed']['rounds'][0]['chosen_index'] = 999
    with pytest.raises(ValueError,match='selection replay'): active.replay_records(protocol,data,altered)
    with pytest.raises(ValueError,match='already started'): active.run(output)


def test_supported_metrics_do_not_credit_new_easy_abstentions():
    rows = []
    for expected,answer,error in [(1,1,None),(1,2,None),(1,None,None),(None,None,None),(None,2,None),(1,None,'broken')]:
        key={'value':expected,'unresolved':expected is None}; prediction={'value':answer,'unresolved':answer is None}
        rows.append({'expected':key,'answer':prediction,'error':error,'correct':error is None and key==prediction})
    result={'rows':rows,'correct':2,'total':6,'unsupported':1,'errors':1}
    m=active.metrics(result)
    assert m['correct']==2 and m['supported_correct_resolved']==1 and m['supported_queries']==4
    assert m['supported_resolved']==2 and m['supported_wrong_resolved']==1 and m['supported_abstentions']==1
    assert m['unsupported_queries']==2 and m['unsupported_abstentions']==1 and m['errors']==1


def test_native_reselection_can_improve_without_changing_program_or_receipt_information():
    good = '''def investigate(context, acquire):
    table = {}
    last = 0
    for action in context["actions"]:
        if action["op"] in ("put", "update"):
            table[action["key"]] = action["value"]
            last = 1
    if context["goal"] == "channel":
        return {"value":last,"unresolved":False}
    if context["goal"] == "committed_count":
        return {"value":len(table),"unresolved":False}
    total = 0
    for value in table.values():
        total += value
    return {"value":total,"unresolved":False}
'''
    bad = 'def investigate(context, acquire):\n    return {"value":0,"unresolved":False}\n'
    i=0
    while hashlib.sha256((bad+f'# {i}').encode()).hexdigest() > hashlib.sha256(good.encode()).hexdigest(): i+=1
    bad+=f'# {i}'
    config=repair.WorldConfig('fixture','upsert',False,'main_direct')
    target={'id':'fixture','source_id':config.source_id,'config':vars(config),'history':[repair.observe(config,[])],
        'inventory':[{'slot_id':str(i),'proposal':{'source':source,'scope':'fixture','lesson':''},'response_error':None}
                     for i,source in enumerate([bad,good]) ]}
    actions=[[{'op':'put','key':'a','value':2},{'op':'put','key':'b','value':3}],
             [{'op':'put','key':'a','value':4},{'op':'update','key':'a','value':5}]]
    data={'targets':[target],'probe_actions':actions,'final_actions':[
        [{'op':'put','key':'a','value':7},{'op':'put','key':'b','value':4},{'op':'update','key':'a','value':2}]]}
    target['historical_inventory']=copy.deepcopy(target['inventory'])
    protocol={'probe_budget':2}; frozen, measured=active.construct(protocol,data)
    result=active.audit(protocol,data,frozen)
    assert measured==4 and frozen[0]['initial']['selected_slot']=='0'
    for policy in active.POLICIES:
        assert frozen[0]['policies'][policy]['reselect']['selected_slot']=='1'
        assert result['aggregate'][policy+'_reselect']['supported_correct_resolved'] > result['aggregate'][policy+'_initial']['supported_correct_resolved']


def test_frozen_runtime_tampering_rejected_before_any_host_measurement(tmp_path,parent,monkeypatch):
    output=tmp_path/'active'; active.prepare(output,parent,probe_pool_size=2,final_size=2)
    protocol=repair.read(output/'protocol.json'); data=repair.read(output/'datasets.json')
    data['targets'][0]['inventory'][0]['proposal']['source']='changed'
    write_json(output/'datasets.json',data)
    monkeypatch.setattr(repair,'observe',forbidden)
    with pytest.raises(ValueError,match='protocol or data changed'): active.run(output)
    assert not (output/'started.json').exists()
