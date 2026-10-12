#!/usr/bin/env python3
"""Export a component-study receipt from sealed originals, without account data."""
import argparse
from decimal import Decimal
import hashlib
import math
from pathlib import Path
import statistics
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from research.guidance_intervention import read, sha
from system.lib.judgmental_forecast import score_quantiles
from zenith.providers import write_json


def export(work, revision):
    spec, frozen, result = [read(work/name) for name in ('spec.json', 'forecasts-sealed.json', 'results.json')]
    revision = subprocess.check_output(['git', 'rev-parse', revision], cwd=ROOT, text=True).strip()
    for name, expected in spec['source_hashes'].items():
        blob = subprocess.check_output(['git', 'show', revision+':'+name], cwd=ROOT)
        if hashlib.sha256(blob).hexdigest() != expected:
            raise ValueError('Original implementation revision does not match: '+name)
    if sha(work/'spec.json') != frozen['spec_sha256'] or result['spec_sha256'] != frozen['spec_sha256']:
        raise ValueError('Specification binding differs')
    for name, expected in frozen['files'].items():
        if sha(work/name) != expected:
            raise ValueError('Sealed response differs')
    for day, expected in spec['inputs'].items():
        if sha(work/'inputs'/day/'material.json') != expected:
            raise ValueError('Frozen input differs')
    calls = []
    for directory in sorted((work/'calls').iterdir()):
        validation = read(directory/'validation.json')
        request, response = directory/'request.json', directory/'response.json'
        if not validation['valid'] or any(sha(path) != validation[key] for path, key in
                                         ((request, 'request_sha256'), (response, 'response_sha256'))):
            raise ValueError('Accepted call differs from original validation')
        receipts = list(directory.glob('handoff/api_calls/openrouter_budgeted/*.json'))
        if len(receipts) != 1:
            raise ValueError('One attempted provider call required per component')
        receipt = read(receipts[0]); provider = receipt['provider_receipt']
        if (receipt['status'] != 'response_supplied' or receipt['actual_provider'] != 'DeepInfra'
                or receipt['requested_provider_slug'] != spec['provider_slug']
                or provider['response_text'] != read(response)['text']):
            raise ValueError('Provider response/identity mismatch')
        calls.append({'run_id': directory.name, 'request_sha256': sha(request), 'response_sha256': sha(response),
                      'validated_at': validation['at'], 'requested_model': receipt['requested_model'],
                      'actual_model': provider['model'], 'actual_provider': provider['actual_provider'],
                      'provider_slug': receipt['requested_provider_slug'], 'usage': provider['usage'],
                      'cost_usd': str(receipt['cost']), 'reserved_cost_usd': receipt['reserved_cost_usd']})
    if len(calls) != 11:
        raise ValueError('Complete eleven-attempt study required')
    outputs, comparisons = {}, []
    for day in (spec['development'], spec['later']):
        data = read(work/'inputs'/day/'material.json')
        rubric = spec['rubric'][day]
        arms = ('baseline', 'challenger', 'direct') if day == spec['development'] else ('baseline', 'challenger')
        values = {}
        for arm in arms:
            root = work/'calls'/f'{day}-{arm}'
            forecast = read(Path(str(root)+'-forecast')/'accepted.json')['value']['forecast_quantiles']['targets']
            values[arm] = {r['target_id']: {q: r[q] for q in ('q10', 'q50', 'q90')} for r in forecast}
            news_path = Path(str(root)+'-news')/'accepted.json'
            news = read(news_path)['value'].splitlines() if news_path.exists() else []
            if any(len(line[1:-1].split(',')) == 4 and line[1:-1].split(',')[-1].strip()
                   not in ('C:HIGH', 'C:LOW', 'C:DERIVED') for line in news):
                raise ValueError('Supplementary confidence enum audit failed')
            outputs[f'{day}-{arm}'] = {'forecast': forecast, 'news_tuple_count': len(news),
                'focus_news_lines': [line for line in news if rubric['new'] in line or rubric['prior'] in line],
                'issuer_association_audit': {'source_records': [r for r in data['news'] if r['ledger_id'] == 'N_A36FDE73'],
                    'output_lines': [line for line in news if 'N_A36FDE73' in line]},
                'evidence_dictionary': [{k: e[k] for k in ('ref_id', 'ledger_id', 'subject', 'source_ref')}
                                        for e in data['evidence_dictionary']]}
        comparisons.append({'issue_date': day, 'baseline_challenger_quantiles_identical': values['baseline'] == values['challenger'],
                            'direct_identical': values['baseline'] == values.get('direct') if 'direct' in values else None,
                            'baseline_equals_four_decimal_price_control': all(row[q] == round(data['price_only'][s][q], 4)
                                 for s, row in values['baseline'].items() for q in row),
                            'max_absolute_deviation_from_price_control': max(abs(row[q]-data['price_only'][s][q])
                                 for s, row in values['baseline'].items() for q in row)})
        # Recompute all published scores from frozen forecasts and saved raw quotes.
        truth_rows = [r for r in result['results'] if r['issue_date'] == day]
        target = truth_rows[0]['target_date']
        current = dict(data['stock']['rows'])
        later = dict(read(work/'truth'/target/'artifacts/global_stock_feed.json')['data']['rows'])
        historical = {}
        for symbol, bars in data['stock']['price_history'].items():
            returns = [b['close']/a['close']-1 for a, b in zip(bars, bars[1:])]
            deciles = statistics.quantiles(returns, n=10, method='inclusive')
            historical[symbol] = {'q10': deciles[0], 'q50': statistics.median(returns), 'q90': deciles[8]}
        if historical != data['price_only']:
            raise ValueError('Frozen history control does not reproduce')
        values['price_only'] = historical
        values['zero_median'] = {s: {'q10': min(q['q10'], 0), 'q50': 0., 'q90': max(q['q90'], 0)}
                                 for s, q in historical.items()}
        for arm in values:
            rows = next(r for r in truth_rows if r['arm'] == arm)['scores']
            for row in rows:
                symbol = row['target_id']; y = later[symbol]/current[symbol]-1
                q = values[arm][symbol]
                if row['actual_return'] != y or row['median_absolute_error'] != abs(q['q50']-y):
                    raise ValueError('Forecast/outcome arithmetic mismatch')
                if any(row[k] != v for k, v in score_quantiles(q, y).items()):
                    raise ValueError('Native quantile score differs')
            means = next(r for r in truth_rows if r['arm'] == arm)['mean']
            if any(not math.isclose(value, statistics.mean(row[key] for row in rows), abs_tol=1e-14)
                   for key, value in means.items()):
                raise ValueError('Aggregate score differs')
    return {'schema': 'zenith_guidance_component_public_receipt_v1', 'implementation_revision': revision,
            'source_hashes': spec['source_hashes'], 'spec_sha256': frozen['spec_sha256'],
            'frozen_at': spec['created_at'], 'forecasts_sealed_at': frozen['at'], 'evaluated_at': result['created_at'],
            'source_manifest_sha256': data['issue']['source_manifest_sha256'],
            'native_lab_execution': False, 'promotion': 'none', 'pilot_date': spec['pilot'],
            'lead_review': {'decision': 'no_change', 'native_evolve_execution': False,
                           'reason': 'Partial comparison compliance and no forecast change; no evidence of improvement.'},
            'baseline_addon': spec['baseline_addon'], 'intervention': spec['intervention'],
            'common_forecast_instruction': spec['forecast_prompt'], 'rubric': spec['rubric'],
            'provider_calls': calls, 'new_attempt_count': len(calls),
            'reported_cost_usd': str(sum((Decimal(c['cost_usd']) for c in calls), Decimal(0))),
            'reserved_cost_usd': str(sum((Decimal(c['reserved_cost_usd']) for c in calls), Decimal(0))),
            'supplementary_confidence_enum_audit': 'all five NEWS outputs pass; no response altered',
            'outputs': outputs, 'comparisons': comparisons, 'results': result['results'],
            'metric_units': 'Simple-return fractions; multiply loss/width by 100 for percentage points.',
            'interpretation_review': {'reviewer': 'primary agent; provisional source review during frozen execution, final review after sealing',
                'current_and_prior_numerical_claims_in_one_result_tuple': {'baseline': '0/2', 'challenger': '2/2'},
                'both_source_ids_in_comparison_tuple': {'baseline': '0/2', 'challenger': '0/2'},
                'explicit_numerical_delta': {'baseline': '0/2', 'challenger': '0/2'},
                'unsupported_market_explanations': 'present in both arms; format acceptance is not factual validation'},
            'claim': 'Partial interpretation response; every paired forecast quantile unchanged. No demonstrated numerical news contribution or policy improvement.',
            'limitations': ['Two input-selected historical issues, not a representative cohort or model-unseen holdout.',
                'One response per arm; correlated stocks and no uncertainty estimate for an intervention effect.',
                'The common forecaster sees historical quantiles and may anchor on them; this does not prove news is useless.',
                'Same raw inputs in each arm; no isolated retrieval effect or full-graph performance claim.',
                'Issuer title ambiguity, unavailable consensus and unverified historical data/model exposure remain.']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work-dir', required=True, type=Path)
    parser.add_argument('--source-revision', required=True)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    receipt = export(args.work_dir, args.source_revision)
    write_json(args.output, receipt)
    print(receipt['claim'])
