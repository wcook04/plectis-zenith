"""Check Evolve after separating its active instructions from the quoted graph."""
import argparse
from pathlib import Path
from zenith import runtime
from zenith.market_graph import read_data
from zenith.market_data import sha256
from zenith.providers import digest,write_json
from research.graph_failure_study import load,run_native


def run(base,study,env_file):
    base=Path(base).resolve();study=Path(study).resolve()
    if study.exists():raise ValueError('Preserve existing check')
    study.mkdir(parents=True)
    original=load(base/'protocol.json');first=original['cases'][0]
    p={**original,'implementation':runtime.implementation_hashes(),'check_code_sha256':sha256(__file__),
        'base_study':str(base),'purpose':'Engineering repair to context hierarchy and citation grammar. The experimental model then writes a new candidate instruction from the unchanged February evidence.'}
    p.pop('sha256',None);p['sha256']=digest(p);write_json(study/'protocol.json',p)
    from system.lib.openrouter_free_runtime import load_env_file
    load_env_file(Path(env_file))
    case={**first,'cutoff':first['target_date'],'target_date':p['cases'][1]['cutoff']}
    evolve=run_native(study,p,'refinement','evolve',case,feed_source=str(base/'evolve-input'))
    write_json(study/'revision.json',load(evolve/'candidate_policy.json'))
    write_json(study/'evolve-result.json',{'protocol_sha256':p['sha256'],'run_id':evolve.name,
        'analysis':read_data(evolve,'delta_analyzer'),'repair':read_data(evolve,'dossier_updater'),
        'boundary':'Context separation was engineered outside this experimental model. Candidate remains unadopted pending replay and later evaluation.'})

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--base',required=True);p.add_argument('--study',required=True);p.add_argument('--env-file',required=True)
    a=p.parse_args();run(a.base,a.study,a.env_file)
