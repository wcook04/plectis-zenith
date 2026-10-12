#!/usr/bin/env python3
"""Export an explicitly failed-cohort diagnostic from frozen native forecasts.

This does not attach, admit or select a rejected cohort arm. It recomputes the
already-frozen outputs and preserves the formal rejection alongside the losses.
"""
import argparse
from datetime import datetime
import json
import math
from pathlib import Path
import statistics
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from zenith import daily, runtime
from system.lib.judgmental_forecast import locked_evidence, score_quantiles, verify_truth
from system.lib.schema_validator import validate_cp2
from system.lib.run_compare import combined_prices
from tools.refinement.run_evolve import verify_agent_handoff


def bound(path):
    path = Path(path).resolve()
    return {'path': str(path.relative_to(ROOT)), 'sha256': daily.file_hash(path)}


def export(work):
    work = Path(work).resolve()
    frozen = daily.read(work/'both-forecasts-frozen.json')
    cohort = daily.read(work/'matchoff-v2/cohort/cohort.json')
    if daily.file_hash(work/'execution-daily_matchoff.py') != cohort['authorities']['research/daily_matchoff.py']:
        raise ValueError('Recovered execution adapter differs from frozen authority')
    for row in frozen['files']:
        if daily.file_hash(Path(row['path'])) != row['sha256']:
            raise ValueError('A pre-truth frozen artifact changed')
    cp_paths = [Path(r['path']) for r in frozen['files'] if Path(r['path']).name == 'lab_director.json']
    if len(cp_paths) != 2:
        raise ValueError('Exactly two frozen native CP2 artifacts required')
    runs = {('challenger' if '_challenger_' in p.parts[-3] else 'baseline'): p.parent.parent for p in cp_paths}
    if set(runs) != {'baseline', 'challenger'}:
        raise ValueError('Both named native arms required')
    oracle = runtime.runs_root(ROOT)/(runs['challenger'].name+'_ORACLE')
    manifests = {arm: daily.read(run/'zenith_run.json') for arm, run in runs.items()}
    for key in ('time_anchor', 'horizon', 'context_profile', 'model', 'provider', 'source_hashes', 'implementation_hashes'):
        if manifests['baseline'][key] != manifests['challenger'][key]:
            raise ValueError('Pair differs outside the declared policy: '+key)
    run_receipts = {}
    for label, run in {**runs, 'oracle': oracle}.items():
        status = runtime.status(ROOT, run.name)
        expected = 31 if label == 'oracle' else 28
        if status['status'] != 'completed' or status['completed_count'] != expected or status['scope_count'] != expected:
            raise ValueError('Complete native scope required')
        responses = sorted((run/'handoff/responses').glob('*.json'))
        for path in responses:
            validation = daily.read(run/'handoff/validation'/path.name)
            if validation.get('engine_accepted') is not True:
                raise ValueError('Accepted response requires native validation')
        supplied = [p for p in (run/'handoff/receipts').glob('*.json')
                    if daily.read(p).get('status') == 'response_supplied']
        run_receipts[label] = {'run_id': run.name, 'completed_nodes': expected,
            'accepted_response_count': len(responses), 'supplied_response_count': len(supplied),
            'manifest': bound(run/'zenith_run.json'),
            'responses': [bound(p) for p in responses],
            'rejected_response_files': [bound(p) for p in sorted((run/'handoff/rejected_responses').rglob('*')) if p.is_file()]}
        if label != 'oracle' and any(datetime.fromisoformat(daily.read(p)['imported_at']) > datetime.fromisoformat(frozen['frozen_at']) for p in responses):
            raise ValueError('Forward response arrived after the declared freeze')
    before = daily.read(runs['baseline']/'artifacts/global_stock_feed.json')['data']
    actual = combined_prices(oracle)
    controls = {r['target_id']: r for r in daily.read(work/'price-controls-frozen.json')}
    for target, control in controls.items():
        prices = [r['close'] for r in before['price_history'][target]]
        returns = [b/a-1 for a, b in zip(prices, prices[1:])]
        qs = statistics.quantiles(returns, n=10, method='inclusive')
        expected = {'target_id': target, 'snapshot_price': prices[-1], 'q10': qs[0],
                    'q50': statistics.median(returns), 'q90': qs[8], 'observed_return_count': len(returns)}
        if expected != control:
            raise ValueError('Frozen control differs from admitted earlier history')
    result = {}
    for arm, run in runs.items():
        cp1 = daily.read(run/'artifacts/lab_decide.json')['data']
        cp2 = daily.read(run/'artifacts/lab_director.json')['data']
        if not validate_cp2(cp2, subject_run_dir=run).ok:
            raise ValueError('Invalid original native CP2')
        if cp1['forecast_quantiles'] != cp2['forecast_quantiles'] or locked_evidence(cp1) != locked_evidence(cp2):
            raise ValueError('CP1 quantile or citation lock changed')
        verify_truth(cp2, run, oracle)
        if {r['target_id'] for r in cp2['forecast_quantiles']['targets']} != set(controls):
            raise ValueError('Complete identical target support required')
        result[arm] = cp2['forecast_quantiles']['targets']
    ideal = daily.read(oracle/'artifacts/ideal_cp2.json')['data']
    challenger = daily.read(runs['challenger']/'artifacts/lab_director.json')['data']
    if ideal['forecast_quantiles'] != challenger['forecast_quantiles'] or locked_evidence(ideal) != locked_evidence(challenger):
        raise ValueError('Oracle changed a frozen forecast')
    result['price_history'] = list(controls.values())
    result['persistence'] = [{**c, 'q10': 0., 'q50': 0., 'q90': 0.} for c in controls.values()]
    native = {r['target_id']: r for r in daily.read(oracle/'artifacts/prediction_reconciliation.json')['data']['rows']}
    arms = {}
    for arm, forecasts in result.items():
        rows = []
        for q in forecasts:
            t = q['target_id']; spot = controls[t]['snapshot_price']; price = actual[t]['Price']; y = price/spot-1
            score = score_quantiles(q, y)
            if arm == 'challenger' and any(native[t][k] != v for k, v in score.items()):
                raise ValueError('Diagnostic disagrees with native Oracle scoring')
            rows.append({'target_id': t, 'snapshot_price': spot, 'truth_price': price,
                **{k: q[k] for k in ('q10', 'q50', 'q90')},
                'median_absolute_return_error': abs(y-q['q50']),
                'relative_target_price_error': abs(y-q['q50'])/(1+y), **score})
        keys = ('median_absolute_return_error', 'relative_target_price_error', 'mean_quantile_pinball_loss', 'interval_80_covered', 'interval_80_width')
        arms[arm] = {'rows': rows, 'summary': {k: math.fsum(r[k] for r in rows)/len(rows) for k in keys}}
    if arms != daily.read(work/'frozen-pair-diagnostic.json')['arms']:
        raise ValueError('Saved diagnostic differs from reconstructed originals')
    rejected = daily.read(work/'attach-baseline.json'); accepted = daily.read(work/'attach-challenger.json')
    if rejected.get('state') != 'error' or 'budget exceeded' not in rejected.get('error', '') or accepted.get('state') != 'complete':
        raise ValueError('This exporter requires the preserved failed-cohort admission')
    verify_agent_handoff(work/'evolve-input.json')
    review = daily.read(work/'evolve-lead-review.json')
    if review['analysis_sha256'] != daily.file_hash(work/'evolve-lead-analysis.json'):
        raise ValueError('Lead review analysis changed')
    prefix = ('lab_seed_state', 'lab_miner_stock', 'lab_miner_news', 'lab_miner_etf', 'lab_miner_macro', 'lab_miner_poly', 'lab_miner_stockgrid', 'lab_miner_calc', 'lab_cross_corr_v1', 'lab_orient')
    bodies = {arm: {daily.read(p)['node_id']: daily.read(p)['response_text'] for p in (run/'handoff/responses').glob('*.json')} for arm, run in runs.items()}
    if any(bodies['baseline'][node] != bodies['challenger'][node] for node in prefix):
        raise ValueError('Declared common prefix differs')
    return {'schema': 'zenith_native_quantile_pair_diagnostic_v1',
        'issue_time': manifests['baseline']['time_anchor'], 'target_time': manifests['baseline']['horizon'],
        'execution_source_revision': daily.read(work/'matchoff-v2/matchoff.json')['source_commit'],
        'source_note': 'Execution included the then-uncommitted XSHG horizon adapter repair; native manifests bind executing implementation bytes. Later configurable response allowances do not alter this frozen cohort.',
        'formal_cohort': {'state': 'incomplete', 'accepted_comparison': False,
            'baseline_error': rejected['error'], 'max_calls_per_run': 21,
            'baseline_supplied_responses': run_receipts['baseline']['supplied_response_count'],
            'challenger_supplied_responses': run_receipts['challenger']['supplied_response_count'],
            'generation_retained': False},
        'runs': run_receipts, 'arms': arms,
        'metric_units': 'Simple-return fractions. Multiply losses and width by100 for percentage points. Native relative target-price error divides return error by1+realized return; it is a different metric.',
        'execution_disclosure': {'shared_current_day_prefix_responses': len(prefix), 'same_primary_author': True,
            'access_isolated_blind_study': False, 'new_paid_provider_calls': 0,
            'baseline_identity_corrections': 1, 'historical_forecast_response_replay': False},
        'sources': {name: bound(work/name) for name in ('development-plan.json', 'execution-amendment.json', 'both-forecasts-frozen.json', 'price-controls-frozen.json', 'init.json', 'attach-baseline.json', 'attach-challenger.json', 'cohort-evaluate.json', 'evolve-input.json', 'evolve-lead-analysis.json', 'evolve-lead-review.json', 'execution-daily_matchoff.py', 'execution-source.patch')},
        'review': {'decision': review['decision'], 'completion_boundary': review['completion_boundary'], 'next_experiment': review['next_experiment']},
        'claim': 'The revised instruction produced exactly the price-history quantiles and had higher descriptive median and pinball loss than the zero-median native baseline on one later date. Formal comparison failed admission. No text advantage, policy improvement or generation retention is established.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work-dir', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    receipt = export(args.work_dir)
    args.output.write_text(json.dumps(receipt, indent=2, ensure_ascii=False, allow_nan=False)+'\n')
    print(json.dumps({'output': str(args.output), 'sha256': daily.file_hash(args.output), 'accepted_comparison': False}))
