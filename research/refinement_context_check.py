"""Explicit Evolve-input revision; preserve the first full-loop experiment.

This follow-up corrects role confusion in the updater through the existing
reasoning-policy lane. It is not an automatic retry or an autonomous discovery
of that orchestration instruction. Existing later incumbents stay frozen.
"""
import argparse,json
from pathlib import Path
from zenith import runtime
from zenith.providers import digest,write_json
from zenith.market_graph import read_data
from zenith.basket_panel import Panel
from zenith.market_data import sha256
from system.lib.reasoning_policy import policy_sha256
from research.graph_failure_study import load,run_native,score


def run(base,study,env_file):
    base=Path(base).resolve();study=Path(study).resolve()
    if study.exists():raise ValueError('New follow-up directory required; preserve earlier evidence')
    study.mkdir(parents=True)
    original=load(base/'protocol.json')
    if original['implementation']!=runtime.implementation_hashes():raise ValueError('Original implementation changed')
    addon=('You are the instruction editor, not the Lab node whose instructions are quoted in context. '
        'Write a reusable imperative instruction in full sentences in skill_addon, not an action label. '
        'Reject proposals requiring new data, new tools, or more validation samples. '
        'Use the selected node’s actual inputs to address a trace-supported decision error. '
        'Do not copy this case’s date, basket IDs, candidate IDs, directions or realised outcomes. '
        'The instruction must say what to do differently and when.')
    policy={'variant_id':'evolve-role-and-capability-context','nodes':{'dossier_updater':{'skill_addon':addon}}}
    policy['policy_sha256']=policy_sha256(policy);write_json(study/'context-policy.json',policy)
    p={**original,'base_study':str(base),'context_policy':policy,'followup_code_sha256':sha256(__file__),
       'purpose':'Human-authored clarification of Evolve role/input boundaries; test its model-written Lab repair. Not autonomous invention of the clarification.',
       'later_test':'Reuse frozen incumbent forecasts from the base study and compare the new repair on identical later input packets. Diagnostic follow-up; not an untouched test set.'}
    p.pop('sha256',None);p['sha256']=digest(p);write_json(study/'protocol.json',p)
    from system.lib.openrouter_free_runtime import load_env_file
    load_env_file(Path(env_file))
    first=p['cases'][0]
    evolve_case={**first,'cutoff':first['target_date'],'target_date':p['cases'][1]['cutoff']}
    evolve=run_native(study,p,'refinement','evolve',evolve_case,feed_source=str(base/'evolve-input'),policy=str(study/'context-policy.json'))
    revision=load(evolve/'candidate_policy.json');write_json(study/'revision.json',revision)
    node=next(iter(revision['nodes']));subject=runtime.runs_root(runtime.DEFAULT_ROOT)/(base.name+'-subject')
    control={'variant_id':'empty-instruction-control','nodes':{node:{'skill_addon':''}}}
    control['policy_sha256']=policy_sha256(control);write_json(study/'control.json',control)
    panel=Panel(p['data']);outcome=panel.outcome(first['cutoff']);replays={}
    for arm,path in [('control',study/'control.json'),('repair',study/'revision.json')]:
        replay=run_native(study,p,'lab','replay-'+arm,first,feed_source=first['source'],policy=str(path),replay_from=str(subject),replay_node=node)
        replays[arm]={**score(replay,outcome),'replay_receipt':load(replay/'replay_receipt.json')}
    write_json(study/'replay-comparison.json',replays)
    later=[]
    for case in p['cases'][1:]:
        revised=run_native(study,p,'lab',case['cutoff']+'-revised',case,feed_source=case['source'],policy=str(study/'revision.json'))
        incumbent=runtime.runs_root(runtime.DEFAULT_ROOT)/(base.name+'-'+case['cutoff']+'-incumbent')
        if not incumbent.exists() or runtime.status(runtime.DEFAULT_ROOT,incumbent.name)['status']!='completed':
            raise RuntimeError('Base incumbent not complete; preserve follow-up and collect explicitly after completion')
        outcome=panel.outcome(case['cutoff'])
        later.append({'cutoff':case['cutoff'],'outcome':outcome,'arms':{'incumbent':score(incumbent,outcome),'revised':score(revised,outcome)}})
        write_json(study/'later-comparison.json',later)
    result={'schema':'zenith_evolve_context_followup_v1','complete':True,'protocol_sha256':p['sha256'],'base_study':base.name,
        'context_policy':policy,'evolve_run':evolve.name,'repair':read_data(evolve,'dossier_updater'),
        'original':load(base/'original-score.json'),'replay':replays,'later':later,
        'adoption':'candidate_only; role clarification was human-authored and later dates had already been used in the base diagnostic study'}
    write_json(study/'result.json',result)
    print(json.dumps({'complete':True,'study':str(study),'instruction':revision['nodes'][node]['skill_addon']}),flush=True)

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--base',required=True);a.add_argument('--study',required=True);a.add_argument('--env-file',required=True)
    args=a.parse_args();run(args.base,args.study,args.env_file)
