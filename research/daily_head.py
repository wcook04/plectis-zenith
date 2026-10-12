"""Train a numerical operator on dated native inputs; retain all feature ablations.

Economic encoding is a component call, never a full native Lab receipt.
Training/selection/assessment labels are opened in separate staged commands.
"""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
import hashlib
import importlib.metadata
import json
from pathlib import Path
import statistics

import numpy as np
from sklearn.linear_model import QuantileRegressor
from sklearn.preprocessing import StandardScaler

from benchmarks import traderharness_daily as daily
from research.ashare_study import spaced
from system.lib import learned_head as head
from system.lib.judgmental_forecast import score_quantiles
from zenith.budgeted import OpenRouterBudgetedProvider, _strict_json
from zenith.providers import digest, now, write_json

ROOT = Path(__file__).resolve().parents[1]
MODEL, PROVIDER = 'deepseek/deepseek-v4.1-flash', 'deepinfra/fp8'
PERIODS = {'training': ('2023-01-09', '2023-12-28'),
           'validation': ('2024-01-02', '2024-12-30'),
           'assessment': ('2025-01-02', '2025-10-30')}
ALPHAS = (.01, .05, .2)


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def immutable(path, value):
    path = Path(path)
    if path.exists():
        if read(path) != value:
            raise ValueError('Immutable record differs: '+str(path))
    else:
        write_json(path, value)


def pack(dataset, day, index=None):
    if index is None:
        manifest = daily.verify(dataset)
        index = daily.indexed(str(dataset), manifest['manifest_sha256'])
    values = daily.daily_inputs(index, day, profit_memory=True)
    return {'issue_date': day, 'issue_at': values['issue_at_utc'], 'symbols': sorted(r[0] for r in values['stock']['rows']),
            'stock': values['stock'], 'news': [{k: r[k] for k in ('ledger_id', 'text', 'entities', 'available_at', 'source_ref')}
                                             for r in values['news']['items']]}


def prepare(study, dataset, budget, count=48):
    study, dataset, budget = [Path(p).resolve() for p in (study, dataset, budget)]
    if (study/'spec.json').exists():
        raise ValueError('Fresh study required')
    manifest = daily.verify(dataset)
    if manifest.get('selection_profile') != 'issuer_profit_state_v1':
        raise ValueError('This experiment freezes the existing profit-state profile')
    index = daily.indexed(str(dataset), manifest['manifest_sha256'])
    # Admission uses only history available at issue, never future target validity.
    admitted, exclusions = {}, []
    for start, end in PERIODS.values():
        for day in (s for s in index['sessions'] if start <= s <= end):
            try:
                admitted[day] = pack(dataset, day, index)
            except ValueError as exc:
                exclusions.append({'day': day, 'reason': str(exc)})
    pilot = min(d for d in admitted if PERIODS['training'][0] <= d <= PERIODS['training'][1])
    phases = {name: spaced([d for d in sorted(admitted) if start <= d <= end and d != pilot], count)
              for name, (start, end) in PERIODS.items()}
    if any(len(dates) != count for dates in phases.values()):
        raise ValueError('Insufficient admissible forward dates')
    ledger = read(budget/'budget.json')
    planned = 1+sum(map(len, phases.values()))
    if ledger['halted'] or len(ledger['entries'])+planned > ledger['limits']['max_calls']:
        raise ValueError('Original budget lacks call capacity; never reset it')
    inputs = {}
    for day in [pilot, *[d for dates in phases.values() for d in dates]]:
        data = admitted[day]
        immutable(study/'inputs'/f'{day}.json', data)
        inputs[day] = sha(study/'inputs'/f'{day}.json')
    sources = ('research/daily_head.py', 'system/lib/learned_head.py', 'benchmarks/traderharness_daily.py',
               'benchmarks/traderharness.py', 'benchmarks/trading_task.py', 'zenith/budgeted.py',
               'system/lib/judgmental_forecast.py')
    spec = {'schema': 'zenith_daily_quantile_learning_v1', 'created_at': now(), 'dataset': str(dataset),
            'dataset_sha256': manifest['manifest_sha256'], 'budget': str(budget), 'limits': ledger['limits'],
            'model': MODEL, 'provider_slug': PROVIDER, 'pilot': pilot, 'phases': phases, 'inputs': inputs,
            'source_hashes': {p: sha(ROOT/p) for p in sources}, 'alphas': list(ALPHAS),
            'package_versions': {p: importlib.metadata.version(p) for p in ('numpy','scipy','scikit-learn','exchange-calendars')},
            'modes': list(head.MODES), 'encoder': head.ENCODER, 'maximum_calls': planned,
            'admission_exclusions': exclusions, 'admission_rule': 'Complete past-only input availability, then calendar-even spacing; no target filter.',
            'objective': 'date_equal_mean_unscaled_pinball_q10_q50_q90',
            'training_loss': 'Past-volatility-normalized target with volatility sample weights: raw pinball divided by training mean volatility, plus L1 penalty.',
            'selection': 'Lowest validation loss; fixed controls win exact ties, then simpler learned features/stronger regularization.',
            'assessment': 'Select once on 2024; refit each selected family on2023+2024; evaluate2025once. Report frozen2023 weights too.',
            'claims': 'Historical component learning, not model-unseen evidence, executable profit or full native graph benefit.'}
    immutable(study/'spec.json', spec)
    immutable(study/'spec-hash.json', {'sha256': sha(study/'spec.json')})
    return {'prepared': True, 'calls': planned, 'phases': {k: len(v) for k, v in phases.items()}, 'spec_sha256': sha(study/'spec.json')}


def load(study):
    spec = read(study/'spec.json')
    if sha(study/'spec.json') != read(study/'spec-hash.json')['sha256']:
        raise ValueError('Spec drift')
    for name, expected in spec['source_hashes'].items():
        if sha(ROOT/name) != expected:
            raise ValueError('Frozen source drift: '+name)
    for day, expected in spec['inputs'].items():
        if sha(study/'inputs'/f'{day}.json') != expected:
            raise ValueError('Frozen input drift')
    return spec


def encode_one(study, spec, day):
    data = read(study/'inputs'/f'{day}.json')
    run = study/'encoding'/day
    prompt = spec['encoder']+'\n'+json.dumps({'issue_at': data['issue_at'], 'issuers': data['symbols'],
                                            'news': data['news']}, ensure_ascii=False)
    immutable(run/'request.json', {'prompt': prompt, 'spec_sha256': sha(study/'spec.json')})
    if (run/'accepted.json').exists():
        raise ValueError('Existing attempt cannot be rerun')
    provider = OpenRouterBudgetedProvider(run, model=spec['model'], provider_slug=spec['provider_slug'],
        budget_dir=Path(spec['budget']), **{k: v for k, v in spec['limits'].items() if k != 'budget_dir'})
    # Transport, pricing, budget and provider identity failures stop the study.
    # Only a returned, accounted response can be a measured encoding failure.
    response = provider.ask_ai(prompt, {'meta': {'node_id': 'economic_state', 'session_id': day}})
    immutable(run/'response.json', {'text': response})
    try:
        state = head.parse_state(_strict_json(response), data)
        immutable(run/'accepted.json', {'state': state, 'accepted_at': now(), 'input_sha256': spec['inputs'][day],
                                        'response_sha256': sha(run/'response.json')})
        return {'day': day, 'accepted': True}
    except (ValueError, TypeError, KeyError) as exc:
        immutable(run/'rejected.json', {'at': now(), 'error': str(exc)})
        # One bad encoding is not a silently removed date: missingness is an explicit fixed fallback.
        immutable(run/'accepted.json', {'state': [[s, None, None, None, []] for s in data['symbols']],
            'accepted_at': now(), 'input_sha256': spec['inputs'][day], 'fallback': 'rejected_encoding_null_state',
            'response_sha256': sha(run/'response.json') if (run/'response.json').exists() else None})
        return {'day': day, 'accepted': False, 'error': str(exc)}


def encode(study, pilot=False, workers=3):
    spec = load(study)
    if not pilot and not (study/'pilot.json').exists():
        raise ValueError('Pilot required')
    if pilot:
        result = encode_one(study, spec, spec['pilot'])
        if not result['accepted']:
            raise ValueError('Pilot failed; stop before data collection')
        immutable(study/'pilot.json', result)
        return result
    days = [day for phase in spec['phases'].values() for day in phase]
    if (study/'encodings-sealed.json').exists():
        raise ValueError('Encodings already frozen')
    if not 1 <= workers <= 3:
        raise ValueError('One to three workers required')
    results = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        # Bounded batches stop dispatch after a failed call, preserving in-flight receipts.
        for offset in range(0, len(days), workers):
            results.extend(pool.map(lambda day: encode_one(study, spec, day), days[offset:offset+workers]))
    immutable(study/'encodings-sealed.json', {'at': now(), 'results': results,
        'files': {day: sha(study/'encoding'/day/'accepted.json') for day in days}})
    return {'encoded': len(results), 'valid': sum(r['accepted'] for r in results)}


def observations(study, spec, phase):
    """The ONLY outcome opening point; caller must choose the eligible phase."""
    if daily.verify(Path(spec['dataset']))['manifest_sha256'] != spec['dataset_sha256']:
        raise ValueError('Source dataset drift')
    index = daily.indexed(spec['dataset'], spec['dataset_sha256'])
    rows = []
    for day in spec['phases'][phase]:
        data = read(study/'inputs'/f'{day}.json')
        state = read(study/'encoding'/day/'accepted.json')['state']
        if [r[0] for r in data['stock']['rows']] != data['symbols']:
            raise ValueError('Target ordering differs')
        target = index['calendar'].next_session(day).date().isoformat()
        at = (index['calendar'].session_close(target).to_pydatetime()+timedelta(minutes=1)).isoformat()
        y = []
        for symbol, current in data['stock']['rows']:
            bar = index['prices'][symbol].get(target)
            if not daily.source.valid_bar(bar):
                raise ValueError('Missing target; never remove the date')
            y.append(bar['close']/current-1)
        rows.append({'data': data, 'state': state, 'y': y, 'outcome_at': at, 'target_date': target})
    immutable(study/'observed'/f'{phase}.json', rows)
    return rows


def fit(rows, mode, alpha):
    pairs = [head.features(r['data'], r['state'], mode) for r in rows]
    x = np.vstack([p[0] for p in pairs]); vol = np.concatenate([p[1] for p in pairs])
    y = np.concatenate([r['y'] for r in rows])/vol
    scaler = StandardScaler().fit(x)
    z = np.clip(scaler.transform(x), -10, 10)
    models = [QuantileRegressor(quantile=q, alpha=alpha, solver='highs').fit(z, y, sample_weight=vol) for q in head.LEVELS]
    model = {'schema': 'zenith_fitted_quantile_head_v1', 'mode': mode, 'alpha': alpha,
        'target': 'next_xshg_raw_close_simple_return', 'symbols': rows[0]['data']['symbols'],
        'fit_end': max(r['outcome_at'] for r in rows), 'training_dates': [r['data']['issue_date'] for r in rows],
        'training_sha256': digest([{'issue': r['data'], 'state': r['state'], 'target': r['y']} for r in rows]),
        'encoder_sha256': digest(head.ENCODER), 'feature_source_sha256': head.feature_source_sha256(),
        'mean': scaler.mean_.tolist(), 'scale': scaler.scale_.tolist(),
        'coefficients': [m.coef_.tolist() for m in models], 'intercepts': [float(m.intercept_) for m in models],
        'transform': 'training-only scaling; z clipping +/-10; normalize outcome by past20vol; q rearrangement; output clip +/-0.5'}
    model['model_sha256'] = digest(model)
    return model


def control(data, name):
    result = []
    for symbol in data['symbols']:
        bars = data['stock']['price_history'][symbol]
        returns = [b['close']/a['close']-1 for a,b in zip(bars,bars[1:])]
        q = statistics.quantiles(returns, n=10, method='inclusive')
        result.append({'target_id': symbol, 'q10': min(q[0], 0) if name == 'zero_median' else q[0],
                       'q50': 0. if name == 'zero_median' else statistics.median(returns),
                       'q90': max(q[8], 0) if name == 'zero_median' else q[8]})
    return result


def score(rows, model=None, name=None):
    details = []
    for r in rows:
        predictions = head.predict(model, r['data'], r['state']) if model else control(r['data'], name)
        daily_scores = [{'target_id': p['target_id'], 'prediction': p, 'actual': y,
                         'mae': abs(p['q50']-y), **score_quantiles(p, y)} for p, y in zip(predictions, r['y'], strict=True)]
        details.append({'issue_date': r['data']['issue_date'], 'target_date': r['target_date'], 'rows': daily_scores,
                        'mean_pinball': statistics.mean(s['mean_quantile_pinball_loss'] for s in daily_scores),
                        'median_mae': statistics.mean(s['mae'] for s in daily_scores)})
    return {'mean_pinball': statistics.mean(r['mean_pinball'] for r in details),
            'median_mae': statistics.mean(r['median_mae'] for r in details), 'dates': details}


def train(study):
    spec = load(study)
    verify_encodings(study, spec)
    if (study/'selection.json').exists():
        raise ValueError('Selection already made; no retuning')
    training = observations(study, spec, 'training')
    validation = observations(study, spec, 'validation')
    trials = []
    for mode in spec['modes']:
        for alpha in spec['alphas']:
            model = fit(training, mode, alpha)
            key = mode+'-'+str(alpha)
            immutable(study/'models'/f'{key}.json', model)
            result = score(validation, model=model)
            immutable(study/'validation'/f'{key}.json', result)
            trials.append({'key': key, 'mode': mode, 'alpha': alpha, 'mean_pinball': result['mean_pinball']})
    for name in ('zero_median', 'history'):
        result = score(validation, name=name)
        immutable(study/'validation'/f'{name}.json', result)
        trials.append({'key': name, 'mode': 'control', 'alpha': None, 'mean_pinball': result['mean_pinball']})
    order = {'control': 0, 'price': 1, 'metadata': 2, 'economic': 3}
    key = lambda r: (r['mean_pinball'], order[r['mode']], -(r['alpha'] or 0))
    selected = min(trials, key=key)
    families = {mode: min((r for r in trials if r['mode'] == mode), key=key) for mode in spec['modes']}
    for mode, trial in families.items():
        immutable(study/'refit'/f'{mode}.json', fit(training+validation, mode, trial['alpha']))
    result = {'at': now(), 'trials': trials, 'selected': selected, 'families': families,
              'refit_hashes': {mode: sha(study/'refit'/f'{mode}.json') for mode in families},
              'model_hashes': {r['key']: sha(study/'models'/f'{r["key"]}.json') for r in trials if r['mode'] != 'control'},
              'assessment_opened': False}
    immutable(study/'selection.json', result)
    immutable(study/'selection-hash.json', {'sha256': sha(study/'selection.json')})
    return result


def verify_encodings(study, spec):
    frozen = read(study/'encodings-sealed.json')
    if set(frozen['files']) != {d for dates in spec['phases'].values() for d in dates}:
        raise ValueError('Encoding seal support differs')
    for day, expected in frozen['files'].items():
        if sha(study/'encoding'/day/'accepted.json') != expected:
            raise ValueError('Encoding seal drift')


def assess(study):
    spec = load(study)
    verify_encodings(study, spec)
    selection = read(study/'selection.json')
    if sha(study/'selection.json') != read(study/'selection-hash.json')['sha256']:
        raise ValueError('Selection drift')
    if (study/'result.json').exists() or (study/'assessment-seal.json').exists():
        raise ValueError('Assessment already consumed')
    for mode, expected in selection['refit_hashes'].items():
        if sha(study/'refit'/f'{mode}.json') != expected:
            raise ValueError('Selected model drift')
    for key, expected in selection['model_hashes'].items():
        if sha(study/'models'/f'{key}.json') != expected:
            raise ValueError('Unrefitted model drift')
    # Produce and seal every assessment forecast before opening its labels.
    forecasts = {}
    for day in spec['phases']['assessment']:
        data = read(study/'inputs'/f'{day}.json')
        state = read(study/'encoding'/day/'accepted.json')['state']
        forecasts[day] = {name: control(data, name) for name in ('history','zero_median')}
        for mode, trial in selection['families'].items():
            forecasts[day][mode] = head.predict(read(study/'refit'/f'{mode}.json'), data, state)
            forecasts[day][mode+'_unrefitted'] = head.predict(read(study/'models'/f'{trial["key"]}.json'), data, state)
    immutable(study/'assessment-forecasts.json', forecasts)
    immutable(study/'assessment-seal.json', {'at': now(), 'forecasts_sha256': sha(study/'assessment-forecasts.json'),
                                          'selection_sha256': sha(study/'selection.json')})
    assessment = observations(study, spec, 'assessment')
    results = {name: score(assessment, name=name) for name in ('history', 'zero_median')}
    for mode, trial in selection['families'].items():
        results[mode] = score(assessment, model=read(study/'refit'/f'{mode}.json'))
        results[mode+'_unrefitted'] = score(assessment, model=read(study/'models'/f'{trial["key"]}.json'))
    for key, result in results.items():
        for date in result['dates']:
            if [r['prediction'] for r in date['rows']] != forecasts[date['issue_date']][key]:
                raise ValueError('Scored forecast differs from pre-label seal')
    selected = selection['selected']
    selected_key = selected['key'] if selected['mode'] == 'control' else selected['mode']
    result = {'schema': 'zenith_daily_head_result_v1', 'at': now(), 'selection_sha256': sha(study/'selection.json'),
              'selected': selected_key, 'results': results, 'native_lab_execution': False,
              'promotion': 'none', 'model_unseen_assessment_claimed': False}
    immutable(study/'result.json', result)
    return {'selected': selected_key, 'scores': {k: {f: v[f] for f in ('mean_pinball','median_mae')} for k,v in results.items()}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('prepare','pilot','encode','train','assess'))
    parser.add_argument('--study', type=Path, required=True)
    parser.add_argument('--dataset', type=Path)
    parser.add_argument('--budget', type=Path)
    parser.add_argument('--env-file', type=Path)
    parser.add_argument('--workers', type=int, default=3)
    args = parser.parse_args()
    if args.env_file:
        from system.lib.openrouter_free_runtime import load_env_file
        load_env_file(args.env_file)
    if args.command == 'prepare':
        if not args.dataset or not args.budget:
            parser.error('prepare requires existing dataset and authorized budget')
        result = prepare(args.study,args.dataset,args.budget)
    elif args.command in ('pilot','encode'):
        result = encode(args.study,pilot=args.command=='pilot',workers=args.workers)
    else:
        result = (train if args.command=='train' else assess)(args.study)
    print(json.dumps(result,indent=2))


if __name__ == '__main__':
    main()
