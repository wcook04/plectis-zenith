"""Export selected completed study evidence, excluding private paths and prompts."""
import argparse
import json
from pathlib import Path
import shutil
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from zenith import runtime
from zenith.providers import digest,write_json
from zenith.market_graph import read_data


def scrub(value):
    if isinstance(value,dict): return {k:scrub(v) for k,v in value.items()}
    if isinstance(value,list): return [scrub(v) for v in value]
    if isinstance(value,str) and value.startswith('/Users/'): return Path(value).name
    return value


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--study',type=Path,required=True)
    args=parser.parse_args();study=args.study.resolve()
    protocol=json.loads((study/'protocol.json').read_text())
    result=json.loads((study/'result.json').read_text())
    if not result.get('complete') or result['protocol_sha256']!=protocol['sha256']: raise ValueError('study is not complete and bound')
    if digest({k:v for k,v in protocol.items() if k!='sha256'})!=protocol['sha256']:raise ValueError('protocol hash mismatch')
    destination=runtime.DEFAULT_ROOT/'examples/full-graph'
    budget=json.loads((study/'budget/budget.json').read_text())
    exported=scrub(result)
    exported['run_accounting']={'attempted_calls':len(budget['entries']),
        'reported_cost_usd':budget['total_reported_cost_usd'],
        'repeated_node_attempts':len(budget['entries'])-len({(e['run_id'],e['node_id']) for e in budget['entries'].values()})}
    exported['study_id']=study.name
    exported['boundary']=protocol['purpose']
    write_json(destination/'result.json',exported)
    runs=runtime.runs_root(runtime.DEFAULT_ROOT)
    subject=runs/result['original']['run_id'];oracle=runs/result['oracle_run'];evolve=runs/result['evolve_run']
    trace={'schema':'zenith_full_graph_trace_v1','study_id':study.name,'model':protocol['model'],
        'initial_case':{k:v for k,v in protocol['cases'][0].items() if k!='source'},
        'lab':{n['id']:read_data(subject,n['id']) for n in protocol['plans']['lab']['nodes'] if n['type']=='reasoning'},
        'oracle':{n['id']:read_data(oracle,n['id']) for n in protocol['plans']['oracle']['nodes'] if n['type']=='reasoning'},
        'numeric_errors':read_data(oracle,'oracle_truth_diff_observations'),
        'subject_record':read_data(oracle,'oracle_subject_index'),
        'evolve':{n:read_data(evolve,n) for n in ('delta_analyzer','dossier_updater','version_committer')},
        'replays':{}}
    for arm,score in result['replay'].items():
        directory=runs/score['run_id']
        trace['replays'][arm]={'receipt':scrub(score['replay_receipt']),
            'changed_outputs':score['changed_outputs'],
            'rerun_records':{n:read_data(directory,n) for n in score['replay_receipt']['rerun_nodes']}}
    # Parsed model records retain source IDs: do not apply path/key scrubbing to them.
    write_json(destination/'trace.json',trace)
    public_protocol={k:v for k,v in protocol.items() if k not in {'root','data','cases','input_hashes'}}
    public_protocol['cases']=[{k:v for k,v in c.items() if k!='source'} for c in protocol['cases']]
    public_protocol['input_content_hashes']=[h for h in protocol['input_hashes'].values()]
    public_protocol['note']='Selected public projection; original protocol SHA binds the local full protocol, not this redacted projection.'
    write_json(destination/'protocol.json',scrub(public_protocol))
    shutil.copyfile(Path(protocol['data'])/'SOURCE_LICENSE.txt',destination/'SOURCE_LICENSE.txt')
    history=[]
    for name in ('zenith-full-graph-20261013','zenith-full-v2-20261013','zenith-full-v3-20261013','zenith-evidence-ids-20261013','zenith-typed-graph-20261013'):
        previous=study.parent/name
        if not (previous/'protocol.json').exists():continue
        prior=json.loads((previous/'protocol.json').read_text())
        ledger_path=previous/'budget/budget.json'
        ledger=json.loads(ledger_path.read_text()) if ledger_path.exists() else {'entries':{}}
        failures=[]
        for run in runs.glob(name+'-*'):
            for path in (run/'artifacts').glob('*.json'):
                env=json.loads(path.read_text())
                if env.get('status')=='failure':
                    meta=env.get('metadata',{})
                    failures.append({'run_id':run.name,'node_id':path.stem,
                        'error':meta.get('error'),'attempts':meta.get('validation_attempts_executed'),
                        'invalid_output_sha256':meta.get('last_invalid_output_sha256')})
        history.append({'study_id':name,'model':prior['model'],'protocol_sha256':prior['sha256'],
            'attempted_calls':len(ledger['entries']),'failures':failures,
            'disposition':'Interrupted after provider-schema alias defect constrained prose fields to node names; not a valid diagnosis or repair.' if name=='zenith-typed-graph-20261013' else 'Stopped on input contract validation failure.'})
    write_json(destination/'development-history.json',{'schema':'zenith_interface_development_history_v1',
        'studies':history,'boundary':'Failed input-interface development runs remain separate from the completed experiment. Some older versions used automatic retries; the current contract permits one attempt.'})
    write_json(destination/'manifest.json',{'schema':'zenith_public_evidence_manifest_v1',
        'study_id':study.name,'files':{p.name:digest(json.loads(p.read_text())) for p in destination.glob('*.json') if p.name!='manifest.json'},
        'retained_earlier_failed_studies':['zenith-full-graph-20261013','zenith-full-v2-20261013','zenith-full-v3-20261013','zenith-evidence-ids-20261013','zenith-typed-graph-20261013'],
        'failure_history':'Earlier input contracts made models author source pointers and produced invalid references. Automatic retries in two development versions were removed. The first evidence-ID version exposed inherited unqualified IDs. This version uses node-scoped IDs, provider-enforced schemas, complete subject-graph context and one attempt per node.'})
    print(json.dumps({'exported_to':str(destination),'complete':True}))


if __name__=='__main__':main()
