"""Reproduce the numerical claims in the 12 October Type B return, offline.

No fitting, outcome selection, provider calls or evaluation-set reads occur.
The inputs are the three already exposed development files in the return.
"""
import argparse
import hashlib
import json
import math
from collections import defaultdict
from decimal import Decimal as D
from pathlib import Path
from statistics import fmean


def load(path):
    raw = path.read_bytes()
    return json.loads(raw), {'path': str(path.resolve()), 'bytes': len(raw),
                             'sha256': hashlib.sha256(raw).hexdigest()}


def decomposition(rows, predictions):
    groups = defaultdict(list)
    for row in rows:
        prediction = predictions[row['sample_id']]
        actual = row['actual_return']
        if not all(math.isfinite(x) for x in (prediction, actual)):
            raise ValueError('Nonfinite prediction or outcome')
        groups[row['issue_date']].append(prediction - actual)
    daily = []
    for date, residuals in sorted(groups.items()):
        mean = fmean(residuals)
        mse = fmean(x * x for x in residuals)
        shape = fmean((x - mean) ** 2 for x in residuals)
        assert math.isclose(mse, mean * mean + shape, abs_tol=1e-15)
        daily.append({'issue_date': date, 'n': len(residuals), 'mse': mse,
                      'common_level_mse': mean * mean, 'relative_shape_mse': shape})
    return {'metrics': {k: fmean(r[k] for r in daily) for k in
                        ('mse', 'common_level_mse', 'relative_shape_mse')},
            'daily': daily}


def audit(packets, evaluator, controls):
    dates = controls['evaluated_issue_dates']
    assert len(dates) == len(set(dates))
    rows = [r for r in evaluator if r['issue_date'] in dates]
    ids = {r['sample_id'] for r in rows}
    assert len(ids) == len(rows)
    assert all(r['phase'] == 'training' for r in rows)
    anchors = {}
    for date in dates:
        for asset in packets[date]['assets']:
            identity = [e['content'].removeprefix('Fixed universe issuer code: ')
                        for e in asset['context_evidence']
                        if e['ref_id'].endswith(':identity')
                        and e['content'].startswith('Fixed universe issuer code: ')]
            assert len(identity) == 1
            sample_id = date + ':' + identity[0]
            assert sample_id not in anchors
            anchors[sample_id] = asset['anchor_mean_return']
    assert set(anchors) == ids
    preds = dict(controls['predictions'])
    preds['supplied_anchor'] = anchors
    results = {}
    for name, values in preds.items():
        assert set(values) == ids, (name, 'unmatched support')
        result = decomposition(rows, values)
        if name in controls['scores']:
            for key, value in result['metrics'].items():
                assert math.isclose(value, controls['scores'][name]['metrics'][key],
                                    rel_tol=1e-12, abs_tol=1e-15), (name, key)
        results[name] = result
    zero = results['zero']['metrics']['mse']
    base = results['ridge_numeric_metadata_identity_scaled']['metrics']
    text = results['scaled_numeric_plus_text']['metrics']
    differences = {k: text[k] - base[k] for k in base}
    daily_base = results['ridge_numeric_metadata_identity_scaled']['daily']
    daily_text = results['scaled_numeric_plus_text']['daily']
    wins = sum(t['mse'] < b['mse'] for t,b in zip(daily_text,daily_base,strict=True))
    ties = sum(t['mse'] == b['mse'] for t,b in zip(daily_text,daily_base,strict=True))
    return {'issue_dates': len(dates), 'asset_cases': len(rows), 'scores': results,
            'anchor_mse_above_zero_fraction': results['supplied_anchor']['metrics']['mse']/zero-1,
            'incremental_text_mse_reduction_fraction': 1-text['mse']/base['mse'],
            'incremental_text_minus_numeric': differences,
            'incremental_text_daily_wins': wins, 'incremental_text_daily_ties': ties,
            'incremental_text_active_dates': sorted({k.split(':')[0] for k in ids
                if preds['scaled_numeric_plus_text'][k] != preds['ridge_numeric_metadata_identity_scaled'][k]}),
            'identity': 'Per date MSE = squared mean residual + mean squared centered residual; dates equally weighted.',
            'claim_limit': 'Already exposed development. No LLM, untouched test, statistical-significance or trading claim.'}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--packets', type=Path, required=True)
    ap.add_argument('--evaluator', type=Path, required=True)
    ap.add_argument('--controls', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    args = ap.parse_args()
    values, sources = {}, {}
    for key in ('packets','evaluator','controls'):
        values[key], sources[key] = load(getattr(args,key))
    result = {'schema': 'zenith_fundamental_research_return_audit_v1',
              'sources': sources, 'ashare': audit(**values)}
    result['worked_arithmetic'] = {
        'aws_actual_growth_fraction': str(D('21.354')/D('18.441')-1),
        'aws_rounded_20pct_forecast_bn': str(D('18.441')*D('1.20')),
        'aws_fixed_15pct_forecast_bn': str(D('18.441')*D('1.15')),
        'adobe_earlier_implied_h2_bn': str(D('19.200')-D('4.655')-D('4.765')),
        'adobe_later_implied_h2_bn': str(D('19.300')-D('4.655')-D('4.816')),
        'adobe_implied_h2_change_bn': str((D('19.300')-D('19.200'))-(D('4.816')-D('4.765'))),
        'adobe_earlier_implied_h2_envelope_bn': [str(D('19.1')-D('4.655')-D('4.78')), str(D('19.3')-D('4.655')-D('4.75'))],
        'adobe_later_implied_h2_envelope_bn': [str(D('19.25')-D('4.655')-D('4.816')), str(D('19.35')-D('4.655')-D('4.816'))],
        'adobe_envelope_boundary_change_bn': ['0.114', '-0.016'],
        'adobe_range_limit': 'Arithmetic envelopes without a joint distribution, not probability intervals; earlier comparator mixes carried December annual guidance with March Q2 guidance.',
        'napco_persistence_relative_error': str(abs(D('21.153')-D('21.522'))/D('21.522')),
        'claim_limit': 'Decimal arithmetic on reported source values; source verification is separate. Exposed illustrations, not executed forecasts.'}
    episode = D('48000')*D('.30')/D('1000000') + D('3584')*D('1.20')/D('1000000')
    result['cost_arithmetic'] = {'assumed_two_call_episode_usd': str(episode),
        'pipelines': 152, 'pipeline_token_cost_usd': str(152*episode),
        'remainder_inside_claimed_3_402_total_usd': str(D('3.402')-152*episode),
        'claim_limit': 'Conditional token arithmetic at supplied rates, not a live quote or executable cost reservation. Exact teacher/probe sizes and serialization/provider bounds are unspecified.'}
    args.output.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({'ashare': {k:v for k,v in result['ashare'].items() if k != 'scores'},
                      'metrics': {k:v['metrics'] for k,v in result['ashare']['scores'].items()},
                      'worked_arithmetic': result['worked_arithmetic'],
                      'cost_arithmetic': result['cost_arithmetic']}, indent=2))


if __name__ == '__main__':
    main()
