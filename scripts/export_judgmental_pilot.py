#!/usr/bin/env python3
"""Recompute a reviewed native quantile episode from original frozen sources."""
import argparse
import math
from pathlib import Path
import statistics
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from zenith import daily,runtime
from system.lib.judgmental_forecast import score_quantiles,verify_truth
from system.lib.schema_validator import validate_cp2
from system.lib.run_compare import combined_prices


def bound(path):
    path=Path(path)
    return {'path':str(path.relative_to(ROOT)),'sha256':daily.file_hash(path)}


def export(work):
    m,p,decision,incumbent,candidate=daily.reviewed_episode(ROOT,work/'programme',0)
    lab,oracle=daily.run_ids(m,0);lp=runtime.runs_root(ROOT)/lab;op=runtime.runs_root(ROOT)/oracle
    runs={}
    for run,count in [(lab,28),(oracle,31)]:
        root=runtime.runs_root(ROOT)/run;status=runtime.status(ROOT,run)
        if status['status']!='completed' or status['completed_count']!=count or status['scope_count']!=count:
            raise ValueError('Full original native mission required')
        receipts=[daily.read(f) for f in (root/'handoff/responses').glob('*.json')]
        runs[run]={'completed_nodes':count,'scope_nodes':count,'accepted_responses':len(receipts),
            'actual_models':sorted({r['actual_model'] for r in receipts}),
            'manifest':bound(root/'zenith_run.json'),
            'responses':[bound(f) for f in sorted((root/'handoff/responses').glob('*.json'))],
            'rejected_responses':[bound(f) for f in sorted((root/'handoff/rejected_responses').rglob('*')) if f.is_file()],
            'artifacts':{f.stem:bound(f) for f in sorted((root/'artifacts').glob('*.json'))}}
    for path,expected in daily.read(work/'forward-freeze.json')['files'].items():
        if daily.file_hash(ROOT/path)!=expected:raise ValueError('Frozen forward data or controls changed')
    cp=daily.read(lp/'artifacts/lab_director.json')['data']
    if cp.get('forecast_basis')!='JUDGMENTAL' or not validate_cp2(cp,subject_run_dir=lp).ok:raise ValueError('Valid native quantile forecasts required')
    verify_truth(cp,lp,op)
    stock=daily.read(lp/'artifacts/global_stock_feed.json')['data'];truth=combined_prices(op)
    frozen_controls={r['target_id']:r for r in daily.read(work/'price-controls-frozen.json')}
    reconciliation=daily.read(p['sources']['prediction_reconciliation'])['data']['rows'];native={r['target_id']:r for r in reconciliation}
    if set(native)!=set(frozen_controls) or len(native)!=10:raise ValueError('Complete ten-target comparison required')
    rows=[]
    for q in cp['forecast_quantiles']['targets']:
        t=q['target_id'];prices=[r['close'] for r in stock['price_history'][t]]
        returns=[b/a-1 for a,b in zip(prices,prices[1:])];quantiles=statistics.quantiles(returns,n=10,method='inclusive')
        control={'target_id':t,'snapshot_price':prices[-1],'q10':quantiles[0],'q50':statistics.median(returns),'q90':quantiles[8],'observed_return_count':len(returns)}
        if control!=frozen_controls[t]:raise ValueError('Price control differs from frozen pre-truth history')
        y=truth[t]['Price']/prices[-1]-1;a=score_quantiles(q,y);b=score_quantiles(control,y)
        for key,value in a.items():
            if native[t][key]!=value:raise ValueError('Oracle quantile score mismatch')
        rows.append({'target_id':t,'snapshot_price':prices[-1],'realized_price':truth[t]['Price'],'realized_return':y,
            'forecast_quantiles':{k:q[k] for k in ('q10','q50','q90')},
            'history_quantiles':{k:control[k] for k in ('q10','q50','q90')},
            'model_mae':abs(y-q['q50']),'persistence_mae':abs(y),'history_mae':abs(y-control['q50']),
            'model_pinball':a['mean_quantile_pinball_loss'],'history_pinball':b['mean_quantile_pinball_loss'],
            'model_covered':a['interval_80_covered'],'history_covered':b['interval_80_covered'],
            'model_width':a['interval_80_width'],'history_width':b['interval_80_width']})
    keys=('model_mae','persistence_mae','history_mae','model_pinball','history_pinball','model_covered','history_covered','model_width','history_width')
    means={k:statistics.mean(row[k] for row in rows) for k in keys}
    if means!=daily.read(work/'comparison.json')['means']:raise ValueError('Published comparison differs from recomputed originals')
    snapshots=[]
    for shot in m['snapshots']:
        root=Path(shot['path']);issue=daily.read(root/'issue-packet.json');news=daily.read(root/'artifacts/global_news_feed.json')['data']['items']
        if any(runtime.stamp(r['available_at'])>runtime.stamp(issue['observation_at_utc']) for r in news):raise ValueError('Late text')
        snapshots.append({'date':shot['date'],'issue_at':shot['anchor'],'observation_at':shot['observation_at'],'issue_packet':bound(root/'issue-packet.json'),'text_items':len(news)})
    return {'schema':'zenith_native_quantile_pilot_v1','programme_sha256':m['programme_sha256'],'programme':bound(work/'programme/daily.json'),
        'snapshots':snapshots,'runs':runs,'forward_freeze':bound(work/'forward-freeze.json'),'development_plan':bound(work/'development-plan.json'),
        'forecast_count':len(rows),'rows':rows,'means':means,
        'metric_units':'Simple-return fractions; multiply losses and widths by100 for percentage points. Unscaled pinball convention.',
        'review':{'receipt':bound(work/'programme/episodes/0/review.json'),'status':decision['status'],'reviewer':decision['reviewer'],'change':decision['response']['change'],'uncertainty':decision['response']['uncertainty']},
        'incumbent':bound(incumbent),'candidate':bound(candidate),
        'execution_disclosure':{'new_paid_provider_calls':0,'prior_run_response_reuse':0,'generation_selected':False,'candidate_later_tested':False},
        'claim':'One full native rich-input forecast episode. Median errors beat persistence but lost to earlier-price medians; quantile loss also lost to earlier-price quantiles. No learned, news or graph advantage established.',
        'limitations':['One exposed historical issue with correlated targets, not a holdout or prospective model test.','Controls are deterministic arithmetic, not separate native model arms.','Subjective quantiles are uncalibrated; three levels do not specify a complete distribution.','Source vintage and issuer-association uncertainty remain.','The later discovery of omitted earlier guidance is a retrieval diagnosis, not evidence of a missed profitable trade.']}

if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--work-dir',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);args=ap.parse_args()
    value=export(args.work_dir.resolve());daily.write_json(args.output,value);print(value['claim'])
