#!/usr/bin/env python3
"""Export/replay a structural-revision study without credentials or live calls."""
from __future__ import annotations

import argparse
from decimal import Decimal
import hashlib
import json
import re
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.build_observation_report import SECRET, _numeric_usage


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def export(study, output):
    study, output = Path(study).resolve(), Path(output).resolve()
    if output.exists():
        raise ValueError('Evidence exports are immutable; choose a new output.')
    frozen = json.loads((study/'frozen.json').read_text())
    if not frozen['complete']:
        raise ValueError('Only completed studies can be published by this command.')
    protocol = json.loads((study/'protocol.json').read_text())
    if protocol['source']['path'] != 'runtime-source.zip':
        raise ValueError('Protocol must bind its portable relative source archive before inference.')
    evidence = json.dumps(protocol.get('model_evidence', {}))
    if SECRET.search(evidence) or re.search(r'/Users/|/home/|"(?:api_key|password|authorization|token|access_token|secret)"', evidence, re.I):
        raise ValueError('Model evidence contains private metadata; do not publish it.')
    if not (study/'screen.json').exists():
        raise ValueError('Completed protected screening is required.')
    output.mkdir(parents=True)
    names = ['protocol.json', 'datasets.json', 'preparation.json', 'frozen.json',
             'frozen-receipt.json', 'runtime-source.zip']
    for partition in ('screen','confirmation'):
        if (study/(partition+'.json')).exists():
            names += [partition+suffix for suffix in ('.json', '-selection.json', '-summary.json')]
    for name in names:
        shutil.copyfile(study/name, output/name)
    nodes = [trial['node_id'] for record in frozen['records'] for arm in record['arms'].values()
             for trial in arm['trials']]
    for directory in ('prompts','responses'):
        (output/directory).mkdir()
        for node in nodes:
            if not re.fullmatch(r'[a-zA-Z0-9_-]+', node):
                raise ValueError('Invalid scientific record filename')
            shutil.copyfile(study/directory/(node+'.json'),output/directory/(node+'.json'))
    budget = json.loads((study/'budget/budget.json').read_text())
    billing = {'schema': 'zenith_decomposition_billing_v1',
               'total_reported_cost_usd':budget['total_reported_cost_usd'],
               'total_reserved_usd':budget['total_reserved_usd'], 'halted':budget['halted'],
               'entries':[{**{k:e.get(k) for k in ('node_id','requested_model','requested_provider_slug',
                           'verified_provider_name','actual_provider','status','cost','usage',
                           'reserved_cost_usd','network_elapsed_seconds')},
                           'usage':_numeric_usage(e.get('provider_receipt',{}).get('usage',e.get('usage')))}
                          for e in budget['entries'].values()]}
    (output/'billing.json').write_text(json.dumps(billing,indent=2)+'\n')
    manifest = {'schema':'zenith_decomposition_export_v1',
                'boundary':'Exact scientific artifacts and original responses; explicit billing allowlist. No credentials, provider transport records or account keys.',
                'files':{str(p.relative_to(output)):sha(p) for p in sorted(output.rglob('*')) if p.is_file()}}
    (output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    return {'output':str(output),'files':len(manifest['files']),'calls':len(billing['entries']),
            'reported_cost_usd':billing['total_reported_cost_usd']}


def verify_manifest(output):
    output=Path(output).resolve()
    manifest=json.loads((output/'manifest.json').read_text())
    paths={str(p.relative_to(output)) for p in output.rglob('*') if p.is_file()}-{'manifest.json'}
    if paths!=set(manifest['files']) or any(sha(output/p)!=h for p,h in manifest['files'].items()):
        raise ValueError('Published file custody mismatch')


def panel_counts(raw):
    def counts(score):
        rows=score['rows']
        values={'correct':sum(row['correct'] for row in rows),'total':len(rows),
                'errors':sum(row['error'] is not None for row in rows)}
        if values!={key:score[key] for key in values}:
            raise ValueError('Protected score counts disagree with answer rows')
        return values
    def add(totals,arm,values):
        target=totals.setdefault(arm,dict(correct=0,total=0,errors=0))
        for key in target:target[key]+=values[key]
    selected={};first={};by_task={}
    for task_id,task in raw['tasks'].items():
        by_task[task_id]={}
        for arm,score in {'initial':task['initial'],**task['arms']}.items():
            values=counts(score);by_task[task_id][arm]=values;add(selected,arm,values)
        for arm,attempts in task['attempts'].items():
            add(first,arm,counts(attempts[0]))
    return {'selected':selected,'first_proposal':first,'by_task':by_task}


def checked_panel(folder,name):
    read=lambda suffix:json.loads((Path(folder)/(name+suffix)).read_text())
    result=panel_counts(read('.json'));saved=read('-summary.json')
    if saved['totals']!=result['selected'] or saved['tasks']!=result['by_task']:
        raise ValueError('Published summary disagrees with protected answer rows')
    return result


def replay(output):
    output=Path(output).resolve()
    verify_manifest(output)
    for name in ('screen','confirmation'):
        if (output/(name+'.json')).exists():checked_panel(output,name)
    with tempfile.TemporaryDirectory(prefix='zenith-decomposition-replay-') as directory:
        runtime=Path(directory)/'runtime';runtime.mkdir()
        with ZipFile(output/'runtime-source.zip') as archive:
            for info in archive.infolist():
                p=Path(info.filename)
                if p.is_absolute() or '..' in p.parts or ((info.external_attr>>16)&0o170000)==0o120000:
                    raise ValueError('Unsafe archived source member')
            archive.extractall(runtime)
        script='import sys,json;sys.path.insert(0,sys.argv[1]);from research.decomposition_study import replay;print(json.dumps(replay(sys.argv[2])))'
        result=subprocess.run([sys.executable,'-I','-c',script,str(runtime),str(output)],
                              cwd=runtime,env={},capture_output=True,text=True,timeout=300)
        if result.returncode:raise RuntimeError(result.stderr[-3000:])
        return json.loads(result.stdout)


def campaign(root=ROOT):
    """Summarize retained studies without pooling their different panels."""
    root=Path(root); studies=[]; total=Decimal('0'); calls=0
    for path in sorted((root/'examples/decomposition').glob('*/manifest.json')):
        folder=path.parent
        verify_manifest(folder)
        read=lambda name: json.loads((folder/name).read_text())
        protocol=read('protocol.json'); data=read('datasets.json'); frozen=read('frozen.json')
        billing=read('billing.json'); count=len(billing['entries'])
        total+=Decimal(billing['total_reported_cost_usd']); calls+=count
        panels={}
        for name in ('screen','confirmation'):
            if not (folder/(name+'.json')).exists(): continue
            panels[name]=checked_panel(folder,name)
        reference=None
        if data['schema'].startswith('zenith-state-discovery-'):
            from research.state_discovery_tasks import compatible_configs, oracle
            # Fit only public calibration rows, never the private truth field.
            reference={'kind':'authored exhaustive fitter within the supplied family',
                       'model_calls':0,'by_task':{}}
            for task in data['tasks']:
                matches=compatible_configs(task['calibration'])
                counts={}
                for name in panels:
                    rows=task[name]
                    correct=sum(len(matches)==1 and oracle({'private':matches[0]},row['input'])==row['expected']
                                for row in rows)
                    counts[name]={'correct':correct,'total':len(rows)}
                reference['by_task'][task['id']]={'compatible_configurations':len(matches),**counts}
        studies.append({'id':folder.name,'evidence':str(folder.relative_to(root)),
            'dataset_schema':data['schema'],'dataset_sha256':protocol['dataset_sha256'],
            'source_sha256':protocol['source']['sha256'],'model':protocol['model'],
            'reasoning_effort':protocol['reasoning_effort'],'max_output_tokens':protocol['max_output_tokens'],
            'task_count':len(data['tasks']),'calls':count,
            'reported_cost_usd':billing['total_reported_cost_usd'],
            'invalid_proposals':sum(t['constraint_error'] is not None for r in frozen['records']
                                    for arm in r['arms'].values() for t in arm['trials']),
            'panels':panels,'authored_reference':reference})
    return {'schema':'zenith_decomposition_campaign_v1',
            'boundary':'Separate authored mechanism and synthetic source-rule studies. Costs sum distinct new calls; accuracies and source counts are not pooled. Reused panels and repeated model settings are not independent replications.',
            'calls':calls,'reported_cost_usd':str(total),'studies':studies}


def main():
    p=argparse.ArgumentParser(description=__doc__);s=p.add_subparsers(dest='command',required=True)
    e=s.add_parser('export');e.add_argument('study',type=Path);e.add_argument('output',type=Path)
    r=s.add_parser('replay');r.add_argument('output',type=Path)
    c=s.add_parser('campaign');c.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    if a.command=='campaign':
        result=campaign();a.output.write_text(json.dumps(result,indent=2)+'\n')
    else:result=export(a.study,a.output) if a.command=='export' else replay(a.output)
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
