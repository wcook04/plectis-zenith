"""Collect failed pairs explicitly and execute untouched independent later arms.

Never resume/retry a failed node. This explicit collection extension closes the
predeclared campaign even when a later pair has no valid forecast.
"""
import argparse,json
from pathlib import Path
from zenith import runtime
from zenith.providers import digest,write_json
from zenith.market_data import sha256
from zenith.market_graph import read_data
from zenith.basket_panel import Panel
from research.graph_failure_study import load,run_native,score


def collect(study,env_file):
    study=Path(study).resolve();p=load(study/'protocol.json')
    if p['implementation']!=runtime.implementation_hashes():raise ValueError('Frozen runtime changed')
    extension={'schema':'zenith_failure_collection_extension_v1','original_protocol_sha256':p['sha256'],
        'collector_sha256':sha256(__file__),'rule':'Preserve failures; no node retries. Execute remaining independent predeclared arms. Failed arms have no forecast or score.'}
    write_json(study/'collection-extension.json',extension)
    from system.lib.openrouter_free_runtime import load_env_file
    load_env_file(Path(env_file))
    panel=Panel(p['data']);later=[]
    followup='base_study' in p
    base=Path(p['base_study']) if followup else study
    for case in p['cases'][1:]:
        arms={}
        for arm in ['incumbent','revised']:
            owner=base if followup and arm=='incumbent' else study
            suffix=case['cutoff']+'-'+arm
            directory=runtime.runs_root(runtime.DEFAULT_ROOT)/(owner.name+'-'+suffix)
            if directory.exists():status=runtime.status(runtime.DEFAULT_ROOT,directory.name)
            else:
                try:
                    args={'policy':str(study/'revision.json')} if arm=='revised' else {}
                    directory=run_native(study,p,'lab',suffix,case,feed_source=case['source'],**args)
                except RuntimeError:pass
                status=runtime.status(runtime.DEFAULT_ROOT,directory.name)
            if status['status']=='completed':arms[arm]={'status':'completed',**score(directory,panel.outcome(case['cutoff']))}
            else:arms[arm]={'status':status['status'],'run_id':directory.name,'failure':status,'mse':None,'forecasts':None}
        later.append({'cutoff':case['cutoff'],'outcome':panel.outcome(case['cutoff']),'arms':arms})
        write_json(study/'later-comparison.json',later)
    evolve=runtime.runs_root(runtime.DEFAULT_ROOT)/(study.name+'-evolve')
    result={'schema':'zenith_full_graph_failure_result_v1','complete':True,'completion_meaning':'All planned arms attempted or collected; failures are retained, not successful forecasts.',
        'protocol_sha256':p['sha256'],'original':load(base/'original-score.json'),'oracle_run':base.name+'-oracle','evolve_run':evolve.name,
        'repair':read_data(evolve,'dossier_updater'),'replay':load(study/'replay-comparison.json'),'later':later,
        'adoption':'not_adopted; instruction is ineffective or case-specific and later evaluation includes a failed pair',
        'nodes':{m:x['node_count'] for m,x in p['plans'].items()},'collection_extension':extension,
        'source_checkpoint':'76a4cb1fd028db866a659ed3ff1989179ec9cb20'}
    if followup:result.update(context_policy=p['context_policy'],base_study=base.name,author_annotation='The context clarification was authored by the engineering agent, not the human user. Frozen protocol wording human-authored means external to the experimental model.')
    write_json(study/'result.json',result);print(json.dumps({'study':study.name,'complete':True,'failed_arms':sum(a['status']!='completed' for c in later for a in c['arms'].values())}),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--study',required=True);p.add_argument('--env-file',required=True)
    a=p.parse_args();collect(a.study,a.env_file)
