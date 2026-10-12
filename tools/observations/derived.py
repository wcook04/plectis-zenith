"""Recompute transparent summaries from the actual authored measurement inputs."""
import json
import hashlib
import math
from collections import defaultdict
from pathlib import Path

def run(config, run_dir=None, **kwargs):
    directory = Path(run_dir)
    inputs = {}
    for lane in ('measurements', 'subsystems', 'environment'):
        payload = json.loads((directory/'artifacts'/f'global_{lane}_feed.json').read_text())
        inputs[lane] = payload['data']['observations']
    summaries = [{'target_id': row['target_id'], 'value': row['value'], 'unit': row['unit'],
                  'observed_at': row['observed_at'], 'available_at': row['available_at'], 'observation_status':row.get('observation_status','observed')}
                 for rows in inputs.values() for row in rows]
    by_unit=defaultdict(list)
    for row in summaries:
        value=row['value']
        if value is None:continue
        if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value):
            raise ValueError('Derived input requires finite numeric observations or explicit missingness')
        by_unit[row['unit']].append(value)
    statistics={unit:{'observed_count':len(values),'mean':math.fsum(values)/len(values),'minimum':min(values),'maximum':max(values)} for unit,values in sorted(by_unit.items())}
    return {'metadata': {'status':'success', 'synthetic_fixture':True,
                         'data_origin':'derived_synthetic_inputs'},
            'data': {'input_count':len(summaries), 'missing_count':sum(row['value'] is None for row in summaries), 'statistics_by_unit':statistics, 'observations':summaries,
                     'evidence_dictionary':[{'ledger_id':'C_'+hashlib.sha256(json.dumps(row,sort_keys=True).encode()).hexdigest()[:8].upper(), 'subject':row['target_id'], 'signal_summary':'Derived identity summary; not independent evidence.', 'source_ref':'derived_synthetic_inputs', 'observed_at':row['observed_at'], 'available_at':row['available_at']} for row in summaries],
                     'derivation':'Counts and arithmetic summaries recomputed per unit from actual source observations; missing values remain missing. Correlated source views do not provide independent corroboration.'}}
