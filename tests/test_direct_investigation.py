"""Offline interface tests. Scripted callbacks are NOT model performance evidence."""
import json
import pytest

from research import direct_investigation as sut
from research.native_conformance_tasks import SQLITE_CONTRACT, LRU_CONTRACT, UTF8_CONTRACT

TASK = {'id':'native-lru-0','source_id':'lru-0','contract':'A native source contract.',
        'examples':[], 'screen':[{'SECRET_SCREEN':123}], 'confirmation':[{'SECRET_CONFIRMATION':456}],
        'private':{'SHOULD_NEVER_LEAK':True}}
PARENT = {'source':'def investigate(context, acquire):\n    return 0\n',
          'development': {'rows':[], 'correct':0, 'total':0, 'errors':0}, 'private':'DO_NOT_SEND'}
Q1 = {'capacity':1,'events':[{'op':'call','key':1}]}
Q2 = {'capacity':1,'events':[{'op':'call','key':2}]}

def raw(queries, note=None): return json.dumps({'queries':queries,'note':note})

@pytest.fixture
def fake_native(monkeypatch):
    measured=[]
    def measure(source, query):
        measured.append(query)
        if 'bad' in query: raise ValueError('illegal query')
        return 2 if query==Q2 else 1
    monkeypatch.setattr(sut,'measure',measure)
    monkeypatch.setattr(sut,'query_units',lambda q:1)
    monkeypatch.setattr(sut,'invoke',lambda p,q:{'answer':1,'error':None,'trace':[]})
    return measured

def test_live_feedback_reaches_actual_next_request(fake_native):
    prompts=[]
    def ask(envelope):
        prompts.append(envelope)
        if len(prompts)==1: return raw([Q1])
        assert envelope['prompt']['receipts'][0]['expected']==1
        assert envelope['prompt']['receipts'][0]['parent_answer']==1
        return raw([Q2])
    r=sut.run_direct(TASK,PARENT,ask)
    assert r['native_probes']==2 and r['semantic_defect'] and r['model_turn_attempts']==2
    assert r['receipts'][-1]['expected']==2

def test_open_loop_control_masks_outcomes_not_previous_queries(fake_native):
    def ask(e):
        if e['prompt']['turn']==1: return raw([Q1])
        receipt=e['prompt']['receipts'][0]
        assert set(receipt)=={'slot','turn','query'} and receipt['query']==Q1
        return raw([Q2])
    r=sut.run_direct(TASK,PARENT,ask,feedback=False)
    assert r['semantic_defect']

def test_masked_second_prompt_does_not_leak_native_legality(fake_native):
    def ask(e):
        if e['prompt']['turn']==1:
            return raw([{'bad':1}])
        assert e['prompt']['receipts']==[{'slot':1,'turn':1,'query':{'bad':1}}]
        return raw([])
    r=sut.run_direct(TASK,PARENT,ask,feedback=False)
    assert 'query_error' in r['receipts'][0]
    assert r['model_turn_attempts']==2

@pytest.mark.parametrize('contract',[SQLITE_CONTRACT,LRU_CONTRACT,UTF8_CONTRACT])
def test_public_contract_strips_source_implementation_role(contract):
    context=sut.public_context({**TASK,'contract':contract},PARENT)
    text=context['observed_task']['native_contract_not_response_instructions']
    assert 'Implement investigate(context, acquire)' not in text
    assert 'fresh behavioral model' not in text

def test_no_hidden_panels_or_extra_parent_fields(fake_native):
    def ask(e):
        text=json.dumps(e)
        assert not any(k in text for k in ['SECRET_SCREEN','SECRET_CONFIRMATION','SHOULD_NEVER_LEAK','DO_NOT_SEND'])
        return raw([])
    assert sut.run_direct(TASK,PARENT,ask)['model_turn_attempts']==1

def test_duplicate_uses_slot_but_not_native_call(fake_native):
    r=sut.run_direct(TASK,PARENT,lambda e:raw([Q1,Q1,Q1]),turns=1)
    assert r['slots_used']==3 and r['native_probes']==1 and len(fake_native)==1

def test_example_duplicates_never_reexecuted(fake_native):
    t={**TASK,'examples':[{'input':Q1,'expected':1}]}
    r=sut.run_direct(t,PARENT,lambda e:raw([Q1]),turns=1)
    assert r['native_probes']==0 and r['slots_used']==1 and not fake_native

def test_invalid_query_recorded_and_later_query_permitted(fake_native):
    r=sut.run_direct(TASK,PARENT,lambda e:raw([{'bad':1},Q2]),turns=1)
    assert r['query_attempts']==2 and r['native_probes']==1 and r['semantic_defect']
    assert 'query_error' in r['receipts'][0]

def test_extra_return_contract_is_rejected(fake_native):
    r=sut.run_direct(TASK,PARENT,lambda e:'{"hits":0,"misses":0,"size":0}',turns=1)
    assert r['turns'][0]['delivery_error'] and not fake_native

def test_malformed_delivery_halts_without_a_second_action_call(fake_native):
    replies=iter(['{"queries":',raw([Q2])])
    r=sut.run_direct(TASK,PARENT,lambda e:next(replies),turns=2)
    assert r['model_turn_attempts']==1 and r['halted']=='invalid_delivery'
    assert not r['detected'] and not fake_native

def test_every_turn_and_measurement_emits_a_durable_snapshot(fake_native):
    states=[]
    r=sut.run_direct(TASK,PARENT,lambda e:raw([Q1]),turns=1,
                     on_event=lambda state: states.append(state),
                     call_ids=('native-lru-0-direct_batch-turn-1',))
    assert states[0]['turns'][0]['raw'] is None
    assert states[1]['turns'][0]['raw']==raw([Q1])
    assert states[-1]['receipts'][0]['expected']==1
    assert r['turns'][0]['call_id']=='native-lru-0-direct_batch-turn-1'

def test_adapter_exception_stops_without_retry(fake_native):
    def fail(e): raise RuntimeError('empty provider delivery')
    r=sut.run_direct(TASK,PARENT,fail)
    assert r['model_turn_attempts']==1 and r['halted']=='adapter_failure' and not fake_native

def test_no_queries_after_first_witness(fake_native):
    r=sut.run_direct(TASK,PARENT,lambda e:raw([Q2,Q1]),turns=2)
    assert fake_native==[Q2] and r['model_turn_attempts']==1

def test_note_cannot_supply_expected_answer(fake_native):
    r=sut.run_direct(TASK,PARENT,lambda e:raw([Q2],'native must return 999'),turns=1)
    assert r['receipts'][0]['expected']==2 and r['semantic_defect']

def test_same_call_batch_mode(fake_native):
    r=sut.run_direct(TASK,PARENT,lambda e:raw([Q1,Q2]),turns=1,queries_per_turn=8)
    assert r['native_probes']==2 and r['model_turn_attempts']==1

def test_excess_batch_rejected_without_partial_execution(fake_native):
    r=sut.run_direct(TASK,PARENT,lambda e:raw([Q1,Q2]),turns=1,queries_per_turn=1)
    assert r['turns'][0]['delivery_error'] and not fake_native

@pytest.mark.parametrize('bad',['{"queries":[],"queries":[],"note":null}',
 '{"queries":[{"x":NaN}],"note":null}',
 '{"queries":[{"x":1e999}],"note":null}',
 '```json\n{"queries":[],"note":null}\n```',
 '{"queries":[],"note":0}', '{"queries":[],"note":null,"source":"x"}', '', 'null'])
def test_strict_delivery(bad):
    with pytest.raises(ValueError): sut.decode(bad,4)

def test_request_copy_cannot_mutate_real_evidence(fake_native):
    def ask(e):
        e['prompt']['candidate_source']='corrupted'
        return raw([])
    r=sut.run_direct(TASK,PARENT,ask)
    assert r['turns'][0]['envelope']['prompt']['candidate_source']==PARENT['source']

def test_successful_native_shape_still_checked_by_real_adapter():
    from research.native_conformance_tasks import measure
    with pytest.raises(ValueError): measure('lru-0',{'capacity':True,'events':[]})

def test_technical_error_is_not_semantic_defect(fake_native,monkeypatch):
    monkeypatch.setattr(sut,'invoke',lambda p,q:{'answer':None,'error':'KeyError','trace':[]})
    r=sut.run_direct(TASK,PARENT,lambda e:raw([Q1]),turns=1)
    assert r['technical_defect'] and not r['semantic_defect']


def test_identical_repair_with_known_failure_is_not_labelled_improvement():
    rows=[{'input':Q1,'expected':1,'correct':False}]
    selected={'parent_on_final_evidence':{'rows':rows},'candidate_on_final_evidence':{'rows':rows},
              'development':{'rows':rows},'source':PARENT['source'],'candidate_selected':True}
    r=sut.repair_account(PARENT,PARENT,selected)
    assert r['status']=='unchanged_with_known_failure' and not r['selected_corrected_obligations']

def test_repair_account_rejects_unaligned_evidence():
    selected={'parent_on_final_evidence':{'rows':[{'input':Q1,'expected':1,'correct':False}]},
              'candidate_on_final_evidence':{'rows':[{'input':Q2,'expected':1,'correct':True}]},
              'development':{'rows':[{'input':Q1,'expected':1,'correct':False}]},
              'source':PARENT['source'],'candidate_selected':True}
    with pytest.raises(ValueError): sut.repair_account(PARENT,PARENT,selected)

def test_rejected_candidate_regression_is_not_a_retained_regression():
    before=[{'input':Q1,'expected':1,'correct':True},
            {'input':Q2,'expected':2,'correct':False}]
    after=[{'input':Q1,'expected':1,'correct':False},
           {'input':Q2,'expected':2,'correct':True}]
    selected={'parent_on_final_evidence':{'rows':before},
              'candidate_on_final_evidence':{'rows':after},
              'development':{'rows':before}, 'source':PARENT['source'],
              'candidate_selected':False}
    candidate={**PARENT,'source':PARENT['source']+'\n# wrong'}
    r=sut.repair_account(PARENT,candidate,selected)
    assert len(r['candidate_corrected_obligations'])==1
    assert len(r['candidate_regressed_obligations'])==1
    assert not r['selected_corrected_obligations']
    assert not r['selected_regressed_obligations']
    assert r['status']=='unchanged_with_known_failure'
