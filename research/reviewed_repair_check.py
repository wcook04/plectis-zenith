"""A labelled reviewer-authored intervention, not a model-authored repair."""
import argparse,json
from pathlib import Path
from zenith import runtime
from zenith.providers import digest,write_json
from zenith.market_data import sha256
from research.graph_failure_study import load,run_native,score
from system.lib.reasoning_policy import policy_sha256


def run(root,base,study,env_file):
    runtime.DEFAULT_ROOT=Path(root).resolve();base=Path(base).resolve();study=Path(study).resolve()
    if study.exists():raise ValueError('Preserve prior check')
    p=load(base/'protocol.json')
    if runtime.implementation_hashes()!=p['implementation']:raise ValueError('Run with the archived experiment runtime on PYTHONPATH')
    study.mkdir(parents=True)
    addon=('Before changing a target from its numerical baseline, check the candidate validation_gain and validation_cases. '
        'Reject nonpositive gain. A higher predicted return is not evidence of greater accuracy. '
        'Name the supplied validation receipt supporting each retained change; treat eight cases as weak evidence.')
    repair={'variant_id':'reviewed-validation-distinction','nodes':{'lab_director':{'skill_addon':addon}}}
    repair['policy_sha256']=policy_sha256(repair);write_json(study/'revision.json',repair)
    control={'variant_id':'reviewed-repair-control','nodes':{'lab_director':{'skill_addon':''}}}
    control['policy_sha256']=policy_sha256(control);write_json(study/'control.json',control)
    protocol={'schema':'zenith_reviewed_repair_protocol_v1','base_protocol_sha256':p['sha256'],
        'runtime_source_checkpoint':'76a4cb1fd028db866a659ed3ff1989179ec9cb20','runtime_hashes':p['implementation'],
        'runner_sha256':sha256(__file__),'author':'engineering assistant reviewing the experimental model outputs',
        'intervention':repair,'boundary':'Outcome-informed local diagnostic intervention, not autonomous Evolve learning or held-out validation.'}
    protocol['sha256']=digest(protocol);write_json(study/'protocol.json',protocol)
    from system.lib.openrouter_free_runtime import load_env_file
    load_env_file(Path(env_file));case=p['cases'][0]
    subject=runtime.runs_root(runtime.DEFAULT_ROOT)/(base.name+'-subject')
    original=load(base/'original-score.json');outcome={'returns':{b:r['realised'] for b,r in original['rows'].items()}}
    arms={}
    for arm,path in [('control',study/'control.json'),('repair',study/'revision.json')]:
        run=run_native(study,p,'lab',arm,case,feed_source=case['source'],policy=str(path),replay_from=str(subject),replay_node='lab_director')
        arms[arm]={**score(run,outcome),'replay_receipt':load(run/'replay_receipt.json')}
    result={'schema':'zenith_reviewed_repair_result_v1','complete':True,'protocol_sha256':protocol['sha256'],
        'protocol':protocol,'original':original,'arms':arms,'adoption':'not_adopted; one outcome-informed local check',
        'model_authored_repair':False}
    write_json(study/'result.json',result);print(json.dumps({'complete':True,'mse':{k:v['mse'] for k,v in arms.items()}}),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',required=True);p.add_argument('--base',required=True);p.add_argument('--study',required=True);p.add_argument('--env-file',required=True)
    a=p.parse_args();run(a.root,a.base,a.study,a.env_file)
