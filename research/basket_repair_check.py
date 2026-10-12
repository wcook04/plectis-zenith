"""One new cutoff checks an output-contract repair; never upgrades pilot evidence."""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
import json
from pathlib import Path
import shutil

from research.basket_study import load, run_arm, score_case, verify_protocol
from zenith import runtime
from zenith.basket_panel import Panel
from zenith.daily import substrate_hashes
from zenith.market_data import sha256
from zenith.providers import digest, write_json
from system.lib.openrouter_free_runtime import load_env_file
from system.lib.reasoning_policy import validate_reasoning_policy


def run(previous, destination, env_file, cutoff='2025-02-01'):
    previous, destination = Path(previous).resolve(), Path(destination).resolve()
    if destination.exists():
        raise ValueError('repair check already exists; no automatic paid retry')
    old = load(previous/'protocol.json')
    if not load(previous/'result.json')['complete']:
        raise ValueError('original comparison must be complete and preserved')
    campaign = load(runtime.DEFAULT_ROOT/'examples/baskets/result.json')['campaign']
    if campaign['total_attempts']+26>260 or Decimal(campaign['conservative_cost_ceiling_usd'])+Decimal('1.90')>2:
        raise ValueError('insufficient remaining campaign allowance')
    panel = Panel(old['data'])
    if panel.manifest != old['basket_manifest']:
        raise ValueError('repair check cannot change basket formation')
    day = next(str(d) for d in panel.dates if d >= cutoff)
    if day <= max(c['target_date'] for c in old['cases']):
        raise ValueError('repair check requires a later, previously unscored cutoff')
    destination.mkdir(parents=True)
    case = {'cutoff':day, 'target_date':str(panel.dates[panel.cutoff_index(day)+5]),
            'split':'holdout', 'arms':['directed','undirected','revised','serial']}
    for arm in case['arms']:
        source = destination/'inputs'/day/arm
        overview = panel.snapshot(day, source, mode='undirected' if arm=='undirected' else 'directed')
        case[arm] = str(source)
    case['baseline'] = overview['baseline']
    policy = load(previous/'revision.json')
    validate_reasoning_policy(policy,runtime.load_graph(runtime.DEFAULT_ROOT))
    write_json(destination/'revision.json',policy)
    protocol = dict(old, cases=[case], max_cost_usd='1.90', max_calls=26,
        native_graph_sha256=digest(runtime.implementation_hashes()),
        substrate_sha256=digest(substrate_hashes(runtime.DEFAULT_ROOT)),
        repair_code_sha256=sha256(__file__), prior_protocol_sha256=old['sha256'],
        frozen_revision_sha256=policy['policy_sha256'],
        retention_policy='No policy adoption from this engineering check.',
        limit='One new cutoff after output-contract repair; not a confirmatory replication or evidence of predictive improvement.')
    protocol.pop('sha256',None);protocol['sha256']=digest(protocol)
    write_json(destination/'protocol.json',protocol)
    shutil.copyfile(previous/'SOURCE_LICENSE.txt',destination/'SOURCE_LICENSE.txt')
    verify_protocol(destination)
    load_env_file(Path(env_file))
    with ThreadPoolExecutor(max_workers=2) as pool:
        records = list(pool.map(lambda arm:run_arm(destination,protocol,case,arm),case['arms']))
    budget=load(destination/'budget/budget.json')
    if budget['halted']:raise RuntimeError('repair-check budget halted; preserve attempts')
    score=score_case(destination,protocol,case,panel)
    trace={}
    for r in records:
        directory=Path(r['native_run'])/'artifacts'
        names = ['basket_serial_plan','basket_serial_director'] if r['arm']=='serial' else ['basket_plan','basket_director']
        trace[r['arm']]={n:load(directory/(n+'.json'))['data'] for n in names if (directory/(n+'.json')).exists()}
    result={'schema':'zenith_basket_repair_check_v1','complete':True,'cutoff':day,'target_date':case['target_date'],
        'purpose':protocol['limit'],'protocol_sha256':protocol['sha256'],
        'prior_protocol_sha256':old['sha256'],'frozen_revision_sha256':policy['policy_sha256'],
        'model':protocol['model'],'model_calls':len(budget['entries']),'cost_usd':budget['total_reported_cost_usd'],
        'failed_arms':[r['arm'] for r in records if r['status']!='completed'],
        'arms':{r['arm']:{k:r[k] for k in ('status','forecasts','cp2','sha256')} for r in records},
        'trace':trace,'score':score,'decision':'engineering_check_only'}
    original_public=load(runtime.DEFAULT_ROOT/'examples/baskets/result.json')['campaign']
    known=Decimal(original_public['known_cost_usd'])+Decimal(result['cost_usd'])
    result['campaign']={'total_attempts':original_public['total_attempts']+result['model_calls'],
        'known_cost_usd':str(known),'conservative_cost_ceiling_usd':str(known+Decimal(original_public['prior_reserved_ceiling_usd'])),
        'unknown_cost_calls':original_public['prior_unknown_cost_calls'],'maximum_total_usd':'2','maximum_total_calls':260}
    if result['campaign']['total_attempts']>260 or Decimal(result['campaign']['conservative_cost_ceiling_usd'])>2:
        raise ValueError('campaign ceiling exceeded')
    write_json(destination/'result.json',result)
    print(json.dumps(result),flush=True)
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--previous',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--env-file',type=Path,required=True)
    p.add_argument('--cutoff',default='2025-02-01')
    args=p.parse_args()
    run(args.previous,args.output,args.env_file,args.cutoff)
