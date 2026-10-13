"""Synthetic integration witnesses, not language-model learning evidence."""
import copy
import json
import shutil
from pathlib import Path
from unittest.mock import patch
import numpy as np
import pytest
from jsonschema import Draft202012Validator
from zenith import runtime
from zenith.providers import Provider, write_json
from zenith.basket_panel import Panel, InvestigationStore, investigator_snapshot, ridge
from zenith.investigator import read, subject_record
from zenith.investigator_contracts import PROFILE, DEFAULT_PROCEDURE, action_schema, review_schema
from system.lib.reasoning_policy import investigation_policy, validate_investigation_policy
from research.investigator_study import measured_receipt, review_feed, score
from test_basket_panel import synthetic_panel

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def setup(tmp_path):
    root=tmp_path/'root';root.mkdir();shutil.copytree(ROOT/'codex',root/'codex')
    write_json(root/'master_config.json',{'paths':{'runs_dir':'state/runs'},'execution':{'max_workers':2}})
    folder,dates=synthetic_panel(tmp_path/'data');panel=Panel(folder,formation=dates[300])
    source=tmp_path/'snapshot';payload=investigator_snapshot(panel,dates[550],source)
    return root,source,payload,panel,dates


def test_quantities_and_reference_fold_clocks(setup):
    _,_,payload,panel,dates=setup
    s=InvestigationStore(payload)
    for b,row in s.inspect('ALL')['baskets'].items():
        assert sum(r['start_value_weight'] for r in row['rows'])==pytest.approx(1)
        assert sum(r['return_contribution'] for r in row['rows'])==pytest.approx(panel.baskets.iloc[550][b]/panel.baskets.iloc[545][b]-1)
    assert s.context()['validation_last_label_date'] < s.context()['training_last_label_date'] <= dates[550]
    assert all(r['last_training_label_date']<=r['origin']<r['target_end']<=dates[550] for r in s.folds)
    assert s.inspect('INDEX')['values']
    references=s.context()['references']
    assert len(references)==18
    assert all(s.options[s.defaults[b]]['validation_mse']==min(r['validation_mse'] for r in references if r['target']==b) for b in s.baskets)


def test_future_mutation_does_not_change_predictions_or_composition(setup,tmp_path):
    _,_,payload,panel,dates=setup
    before=InvestigationStore(payload)
    panel.x[551:]*=10000;panel.y[546:]=999
    panel.marked.iloc[551:]*=900;panel.age.iloc[551:]=100
    after=InvestigationStore(investigator_snapshot(panel,dates[550],tmp_path/'other'))
    assert before.inspect('ALL')==after.inspect('ALL')
    assert before.compare('B04','top3_abs_contribution_share',1)==after.compare('B04','top3_abs_contribution_share',1)


def test_representation_contrast_retains_normalization_and_all_targets(setup):
    s=InvestigationStore(setup[2]);r=s.compare('B06','positive_value_weight',1)
    assert r['spec']['common_normalizer']==s.h['x'].shape[1]
    assert len(r['candidates'])==6 and len(r['folds'])==48
    # Reference ridge implementation is unchanged by the optional denominator.
    np.testing.assert_array_equal(ridge(s.h['x'],s.h['y'],s.h['current']),ridge(s.h['x'],s.h['y'],s.h['current'],normalizer=s.h['x'].shape[1]))
    r2=s.compare('B01','fresh_endpoints_value_weight',2)
    assert not {r['candidate_id'] for r in r['candidates']} & {r['candidate_id'] for r in r2['candidates']}
    final=s.commit([r['candidate_id'] for r in r2['candidates']],r['candidates']+r2['candidates'])
    assert set(final['forecasts'])==set(s.baskets)


@pytest.mark.parametrize('ids',[[],['MISSING']*6,['R:zero:B01']*6,['R:zero:B01','R:ridge:B01','R:zero:B03','R:zero:B04','R:zero:B05','R:zero:B06']])
def test_invalid_selection_never_falls_back(setup,ids):
    with pytest.raises(ValueError):InvestigationStore(setup[2]).commit(ids,[])


def test_array_tamper_is_rejected(setup):
    Path(setup[2]['composition']).write_bytes(b'not a cutoff store')
    with pytest.raises(ValueError,match='hash mismatch'):InvestigationStore(setup[2])


def test_policy_is_replacement_and_hash_bound():
    p=investigation_policy('x'*2000)
    assert validate_investigation_policy(p)==p
    p['procedure']+='tamper'
    with pytest.raises(ValueError):validate_investigation_policy(p)
    with pytest.raises(ValueError):investigation_policy('x'*4097)


def test_schema_specializations_are_independent():
    a=action_schema(['B01'],['case'],['R:zero:B01'])
    b=action_schema(['B02'],['result'],['R:zero:B02'])
    assert a['properties']['evidence_refs']['items']['enum']==['case']
    assert b['properties']['evidence_refs']['items']['enum']==['result']


def response(action,evidence='case'):
    return {'purpose':'Scripted software test, not an intelligent investigation.','evidence_refs':[evidence],
            'decision_if':'Use this measured result to choose the next action.','action':action}


def review(procedure=DEFAULT_PROCEDURE+'\nFixture: inspect B04 first.'):
    return {'diagnosis':'Fixture witnesses a different inspection; it does not diagnose a real model.',
        'witness_steps':['investigator_turn_01'],'alternative':'Sampling variation.','disposition':'propose' if procedure else 'no_change',
        'replacement_procedure':procedure,'expected_effect':{'action':'inspect' if procedure else 'none','source':'B04' if procedure else 'none',
            'quantity':'none','interpretation':'B04 is inspected first in this scripted positive control.'},
        'counterexample':'Unrelated cases need not inspect B04.','disconfirmer':'No changed inspection.',
        'feedback_assessment':'No prior receipt in first review.'}


def test_review_phase_and_action_signatures_match_executable_actions():
    initial=Draft202012Validator(review_schema(['investigator_turn_01'],['B01','B04']))
    feedback=Draft202012Validator(review_schema(['investigator_turn_01'],['B01','B04'],feedback=True))
    value=review()
    assert initial.is_valid(value) and not feedback.is_valid(value)
    value['disposition']='revise'
    assert feedback.is_valid(value) and not initial.is_valid(value)
    value['expected_effect'].update(action='commit',source='ALL')
    assert not feedback.is_valid(value) # A commit has no source field to match.
    value['expected_effect']['source']='none'
    assert feedback.is_valid(value)


class Fixture(Provider):
    calls=[]
    invalid=False
    def ask_ai(self,prompt,config=None,cancel=None):
        nid=config['meta']['node_id'];self.calls.append((self.run_dir.name,nid))
        if self.invalid:return '{}'
        if nid=='investigator_review':
            packet=read(self.run_dir,'investigator_review_feed')
            value=review()
            if packet['repair_history']:
                value=review('');value['disposition']='reject'
                value['feedback_assessment']='Measured receipt '+packet['repair_history'][0]['sha256']+' was supplied; fixture rejects.'
            return json.dumps(value)
        turn=int(nid[-2:]);patched='Fixture: inspect B04 first.' in config['system_prompt']
        if turn==1:value=response({'kind':'inspect','source':'B04' if patched else 'B01'})
        elif turn==2:
            earlier=read(self.run_dir,'investigator_result_01')
            source=next(iter(earlier['receipt']['baskets']))
            value=response({'kind':'compare','source':source,'quantity':'top3_abs_contribution_share'},'investigator_result_01')
        else:
            prior=read(self.run_dir,'investigator_result_02')['receipt']['candidates']
            value=response({'kind':'commit','candidate_ids':[r['candidate_id'] for r in prior]},'investigator_result_02')
        Draft202012Validator(config['response_format']['json_schema']['schema']).validate(value)
        return json.dumps(value)


def test_native_complete_loop_exact_feedback_and_whole_replay(setup,tmp_path):
    root,source,payload,panel,dates=setup
    common=dict(root=root,task_profile=PROFILE,time_anchor=dates[550]+'T23:59:59+00:00',horizon=dates[555]+'T23:59:59+00:00')
    Fixture.calls=[];Fixture.invalid=False
    with patch.object(runtime,'provider_for',side_effect=lambda d,s:Fixture(d)):
        assert runtime.start(**common,mission='lab',run_id='subject',feed_source=str(source))['status']=='completed'
        runs=runtime.runs_root(root);subject=runs/'subject'
        assert read(subject,'investigator_final')['action_count']==3
        assert len(subject_record(subject)['contexts'])==3
        outcome=panel.outcome(dates[550]);policy=investigation_policy(DEFAULT_PROCEDURE)
        feed=review_feed(tmp_path/'review',subject,policy,outcome,[])
        audit=read(feed,'investigator_review_feed')['decision_audit']
        capability=read(feed,'investigator_review_feed')['capability_audit']
        assert capability['legal_recipe_count']==21
        assert capability['executed_comparisons']==1
        assert capability['untried_recipe_count']==20
        for row in audit['rows']:
            options=row['ordered_available_options']
            assert [o['validation_mse'] for o in options]==sorted(o['validation_mse'] for o in options)
            assert row['selected_is_validation_minimum']==(row['selected_mse']==options[0]['validation_mse'])
            assert len(options)==4 # Three references plus the executed comparison.
        assert runtime.start(root,task_profile=PROFILE,mission='refinement',run_id='review',feed_source=str(feed))['status']=='completed'
        proposal=read(runs/'review','investigator_review')
        assert json.loads((runs/'review/candidate_policy.json').read_text())['procedure']==proposal['replacement_procedure']
        for name,pp in [('control',None),('candidate',str(runs/'review/candidate_policy.json'))]:
            status=runtime.start(**common,mission='lab',run_id=name,feed_source=str(source),policy=pp,replay_from=str(subject),replay_node='investigator_entry')
            assert status['status']=='completed',status
        receipt=measured_receipt(proposal,subject,runs/'control',runs/'candidate',outcome)
        assert receipt['first_action_difference_subject_control'] is None
        assert receipt['first_action_difference_control_candidate']==1
        assert receipt['expected_signature_positions']=={'subject':None,'control':None,'candidate':1}
        feed=review_feed(tmp_path/'feedback',subject,policy,outcome,[receipt])
        assert runtime.start(root,task_profile=PROFILE,mission='refinement',run_id='feedback',feed_source=str(feed))['status']=='completed'
        ctx=json.loads((runs/'feedback/artifacts/context/investigator_review.json').read_text())
        assert ctx['inputs']['investigator_review_feed']['data']['repair_history']==[receipt]
        assert json.dumps(receipt,separators=(',',':'),ensure_ascii=False) in ctx['prompt']
        assert read(runs/'feedback','investigator_review')['disposition']=='reject'
        assert len(Fixture.calls)==11 # 3 Lab calls in each of three runs, two review calls.


def test_invalid_native_attempt_is_terminal_no_baseline(setup):
    root,source,_,_,dates=setup
    Fixture.calls=[];Fixture.invalid=True
    try:
        with patch.object(runtime,'provider_for',side_effect=lambda d,s:Fixture(d)):
            status=runtime.start(root,task_profile=PROFILE,mission='lab',run_id='bad',feed_source=str(source),
                time_anchor=dates[550]+'T23:59:59+00:00',horizon=dates[555]+'T23:59:59+00:00')
        assert status['status']=='failed'
        assert len(Fixture.calls)==1
        assert not (runtime.runs_root(root)/'bad/artifacts/investigator_final.json').exists()
    finally:Fixture.invalid=False


def test_score_rejects_unmatched_interval():
    with pytest.raises(ValueError,match='interval'):
        score({'cutoff':'a','forecasts':{'B01':.1},'target_time':'2025-01-02'},
              {'cutoff':'a','returns':{'B01':.2},'target_date':'2025-01-03'})


@pytest.mark.parametrize('no_change',[False,True])
def test_documented_coordinator_uses_same_native_path(setup,tmp_path,no_change):
    from research import investigator_study as study
    root,source,payload,panel,dates=setup
    class EpisodeFixture(Fixture):
        def ask_ai(self,prompt,config=None,cancel=None):
            if no_change and config['meta']['node_id']=='investigator_review':
                return json.dumps(review(''))
            return super().ask_ai(prompt,config,cancel)
    env=tmp_path/'local.env';env.write_text('# no external calls in this fixture\n')
    dest=tmp_path/'episode';Fixture.invalid=False
    with patch.object(study,'Panel',return_value=panel),patch.object(runtime,'DEFAULT_ROOT',root),patch.object(runtime,'provider_for',side_effect=lambda d,s:EpisodeFixture(d)):
        study.prepare(panel.folder,dest,model="deepseek/fixture",cutoff=dates[550])
        result=study.run(dest,env)
        assert result['feedback_delivered_exactly'] and not result['adopted']
        assert (result['candidate'] is None)==no_change
        assert json.loads((dest/'numerical-comparator.json').read_text())['comparison_count']==21
        # Re-entering a completed study consumes evidence, not new model samples.
        before=len(Fixture.calls)
        assert study.run(dest,env)==result
        assert len(Fixture.calls)==before
        if not no_change:
            original=(dest/'result.json').read_bytes()
            continuation=tmp_path/'interface-revision'
            next_result=study.continue_review(dest,continuation,env)
            assert next_result['feedback_delivered_exactly'] and not next_result['adopted']
            assert next_result['decision']['disposition']=='reject'
            assert len(Fixture.calls)==before+1
            assert study.continue_review(dest,continuation,env)==next_result
            assert len(Fixture.calls)==before+1
            assert (dest/'result.json').read_bytes()==original


def test_agent_handoff_can_import_without_retrying_invalid_response(setup,tmp_path):
    root,source,_,_,dates=setup
    result=runtime.start(root,task_profile=PROFILE,mission='lab',run_id='handoff',feed_source=str(source),
        time_anchor=dates[550]+'T23:59:59+00:00',horizon=dates[555]+'T23:59:59+00:00')
    assert result['status']=='awaiting_agent'
    packet_path=Path(result['pending'][0]['packet_path']);packet=json.loads(packet_path.read_text())
    supplied={k:packet[k] for k in ('packet_id','run_id','node_id','prompt_sha256')}
    supplied['schema']='zenith_agent_response_v1'
    supplied['response_text']=json.dumps(response({'kind':'commit','candidate_ids':[f'R:zero:B{i:02}' for i in range(1,7)]}))
    response_path=tmp_path/'response.json';write_json(response_path,supplied)
    result=runtime.import_response(root,packet_path=packet_path,response_path=response_path,model='scripted-test')
    assert result['import']['engine_accepted'],result
    assert runtime.status(root,'handoff')['status']=='completed'


def test_comparison_allowance_is_global_and_failed_attempt_cannot_resume(setup):
    root,source,_,_,dates=setup
    calls=[]
    class OverBudget(Provider):
        def ask_ai(self,prompt,config=None,cancel=None):
            calls.append(config['meta']['node_id'])
            return json.dumps(response({'kind':'compare','source':'ALL','quantity':'positive_value_weight'}))
    with patch.object(runtime,'provider_for',side_effect=lambda d,s:OverBudget(d)):
        result=runtime.start(root,task_profile=PROFILE,mission='lab',run_id='limit',feed_source=str(source),
            time_anchor=dates[550]+'T23:59:59+00:00',horizon=dates[555]+'T23:59:59+00:00')
        assert result['status']=='failed' and len(calls)==7
        with pytest.raises(ValueError,match='terminal'):runtime.resume(root,'limit')
    assert read(runtime.runs_root(root)/'limit','investigator_result_06')['receipt']['candidates'][0]['candidate_id']=='C06:B01'
