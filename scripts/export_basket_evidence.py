#!/usr/bin/env python3
"""Publish an explicit, path-free projection of a completed native basket study."""
from __future__ import annotations
import argparse
import json
import shutil
from decimal import Decimal
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from zenith.providers import digest, write_json
from research.basket_study import verify_protocol


def load(path):
    return json.loads(path.read_text())


def export(study, output, campaign=None):
    study, output = Path(study).resolve(), Path(output).resolve()
    protocol = verify_protocol(study)
    result = load(study/'result.json')
    if result.get('complete') is not True:
        raise ValueError('only a completed study can be published as a result')
    if result['protocol_sha256'] != protocol['sha256']:
        raise ValueError('result belongs to another protocol')
    cases, traces = [], []
    for case in protocol['cases']:
        score = load(study/'scores'/(case['cutoff']+'.json'))
        arms = {}
        for arm in case['arms']:
            record = load(study/'commitments'/case['cutoff']/(arm+'.json'))
            if record['sha256'] != digest({k:v for k,v in record.items() if k!='sha256'}):
                raise ValueError('changed forecast commitment')
            if score['commitment_hashes'][arm] != record['sha256']:
                raise ValueError('score/forecast binding differs')
            arms[arm] = {k: record[k] for k in ('run_id','status','forecasts','cp2','sha256')}
            # The first chronological holdout case is the fixed explanatory trace.
            if case['split']=='holdout' and not any(c['split']=='holdout' for c in cases):
                directory = Path(record['native_run'])/'artifacts'
                names = ['basket_serial_plan','basket_serial_investigations','basket_serial_director'] if arm=='serial' else ['basket_plan','basket_investigations','basket_director']
                traces.append({'arm':arm,'cutoff':case['cutoff'],'commitment_sha256':record['sha256'],
                    'nodes':{name:load(directory/(name+'.json'))['data'] for name in names if (directory/(name+'.json')).exists()},
                    'cp2':record['cp2']})
        cases.append({'cutoff':case['cutoff'],'target_date':case['target_date'],'split':case['split'],
                      'baseline':case['baseline'],'arms':arms,'score':score})
    fields = ('schema','sha256','model','max_cost_usd','max_calls','max_output_tokens','basket_manifest',
              'native_graph_sha256','substrate_sha256','study_code_sha256','score','failure_policy',
              'retention_policy','limit','budget','data_qualifications','import_audit')
    public_protocol = {k:protocol[k] for k in fields}
    public_protocol['projection_note'] = 'Public projection of the frozen private protocol; sha256 identifies the full original, including local locators.'
    public_protocol['cases'] = [{k:c[k] for k in ('cutoff','target_date','split','arms')} for c in protocol['cases']]
    public_result = dict(result)
    if campaign:
        campaign = load(Path(campaign))
        campaign['known_cost_usd'] = str(Decimal(result['cost_usd'])+Decimal(campaign['feasibility_cost_usd']))
        campaign['conservative_cost_ceiling_usd'] = str(Decimal(campaign['known_cost_usd'])+Decimal(campaign['prior_reserved_ceiling_usd']))
        campaign['total_attempts'] = result['model_calls']+campaign['prior_unknown_cost_calls']+1
        public_result['campaign'] = campaign
    values = {
        'protocol.json':public_protocol, 'result.json':public_result,
        'forecasts.json':{'protocol_sha256':protocol['sha256'],'cases':cases},
        'trace.json':{'selection':'first chronological holdout origin; every model arm', 'traces':traces,
                      'revision':load(study/'revision.json'),'revision_proposal':load(study/'revision-proposal.json')},
    }
    # No blanket redaction that could silently change evidence. These schemas export only reviewed fields.
    for name, value in values.items():
        serialized=json.dumps(value)
        if '/Users/' in serialized or 'sk-or-' in serialized:
            raise ValueError('private locator or credential-shaped string in publication projection')
        write_json(output/name,value)
    shutil.copyfile(study/'SOURCE_LICENSE.txt',output/'SOURCE_LICENSE.txt')
    write_json(output/'manifest.json',{'schema':'zenith_basket_public_projection_v1',
        'source_protocol_sha256':protocol['sha256'], 'files':{name:digest(value) for name,value in values.items()},
        'notice':'Historical observations from SocrateAI NEPSE Open Data; constructed research baskets. Retrospective execution experiment.'})
    return {'output':str(output),'cases':len(cases),'completed':True}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--study',type=Path,required=True)
    parser.add_argument('--output',type=Path,default=ROOT/'examples/baskets')
    parser.add_argument('--campaign',type=Path)
    args=parser.parse_args()
    print(json.dumps(export(args.study,args.output,args.campaign),indent=2))
