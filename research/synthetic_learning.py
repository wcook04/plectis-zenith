"""A constructed, deterministic learning example, not a native Lab/model run.

Train by bounded search over three operators; use later validation to accept
one proposal and later assessment to measure the frozen choice. The correct
rule is deliberately in the bank. This tests the procedure, not discovery.
"""
from __future__ import annotations

from datetime import date, timedelta
from itertools import product
import json
import math
from pathlib import Path
import random

from feedback.selection import score_panel
from zenith.providers import digest, text_digest, write_json

SPLITS = {'training': (0, 64), 'validation': (64, 96), 'assessment': (96, 160)}
BASELINE = {'comparison': 'year_ago', 'ranking': 'headline', 'scale': .24}
BUDGET = 2
MARGIN = .10


def candidates():
    return [{'comparison': c, 'ranking': r, 'scale': s}
            for c, r, s in product(('year_ago', 'prior_guidance'), ('headline', 'signal'), (0., .08, .24))]


def make_day(index, seed, *, signal=True):
    """Two dated feeds and separate future truth; missing prior is not neutral news.

    This deliberately known world makes returns depend on a guidance revision,
    plus an unpredictable shared shock and asset noise. All dates/entities are
    synthetic. Source clocks and comparison periods are known by construction.
    """
    rng = random.Random(seed * 10000 + index)
    day = date(2030, 1, 1) + timedelta(days=index)
    forward = {'issue_id': day.isoformat(), 'synthetic': True, 'prices': {}, 'reports': {}}
    truth = {}
    common = rng.gauss(0, .003)
    for i in range(8):
        ticker = f'SYN{i}'
        last_year = rng.uniform(80, 120)
        growth = rng.uniform(.2, .9)
        revision = rng.uniform(-.35, .35)
        actual = last_year * (1 + growth)
        prior = actual / (1 + revision)
        spot = rng.uniform(50, 150)
        forward['prices'][ticker] = {'close': spot, 'available': day.isoformat()}
        forward['reports'][ticker] = {
            'year_ago_profit': last_year, 'new_guidance': actual,
            'prior_guidance': None if (index + i) % 11 == 0 else prior,
            'new_available': day.isoformat(), 'prior_available': (day - timedelta(days=20)).isoformat(),
            'year_ago_period': 'synthetic_previous_year', 'guidance_period': 'synthetic_current_year',
        }
        outcome = (.08 * revision if signal else 0.) + common + rng.gauss(0, .006)
        truth[ticker] = outcome
    return forward, truth


def forecast(forward, policy):
    """Pure forward-only operators: interpret, predict for all, select up to K.

    Shadow predictions make ranking measurable without changing prediction
    rules. They are not free in a model-backed experiment; account for that cost.
    """
    if policy not in candidates():
        raise ValueError('candidate outside the frozen bank')
    interpretation, forecasts, ranking = {}, {}, {}
    for ticker, row in forward['reports'].items():
        reference = row['year_ago_profit'] if policy['comparison'] == 'year_ago' else row['prior_guidance']
        change = None if reference is None else row['new_guidance'] / reference - 1
        interpretation[ticker] = {'comparison': policy['comparison'], 'change': change,
                                  'status': 'missing_comparison' if change is None else 'observed'}
        forecasts[ticker] = 0. if change is None else policy['scale'] * change
        ranking[ticker] = (abs(row['new_guidance'] / row['year_ago_profit'] - 1)
                           if policy['ranking'] == 'headline' else abs(forecasts[ticker]))
    selected = sorted(forecasts, key=lambda k: (-ranking[k], k))[:BUDGET]
    return {'issue_id': forward['issue_id'], 'policy': policy, 'interpretation': interpretation,
            'shadow_forecasts': forecasts, 'ranking': ranking, 'selected': selected,
            'target_prices': {k: forward['prices'][k]['close'] * (1 + forecasts[k]) for k in selected}}


def evaluate(forwards, labels, policy):
    # Generate the complete prediction set before joining any labels.
    traces = [forecast(row, policy) for row in forwards]
    cases = [{'issue_id': row['issue_id'], 'universe': sorted(row['shadow_forecasts']),
              'selected': row['selected'], 'forecasts': row['shadow_forecasts'],
              'fallback': {k: 0. for k in row['shadow_forecasts']}, 'truth': labels[row['issue_id']],
              'budget': BUDGET, 'loss': 'squared'} for row in traces]
    return score_panel(cases), traces


def choose(training_rows):
    """Training alone proposes; validation and assessment are not arguments."""
    valid = [row for row in training_rows if row['status'] == 'completed']
    if not valid:
        raise ValueError('no completed development trials')
    return min(valid, key=lambda row: (row['loss'], digest(row['policy'])))['policy']


def single_edit_search(training_rows):
    """A local-search control using only losses already measured on training.

    Strictly improving one-coordinate edits cannot cross a neutral plateau.
    Record this limitation instead of treating a zero effect as node innocence.
    """
    rows = [row for row in training_rows if row['status'] == 'completed']
    current = next((row for row in rows if row['policy'] == BASELINE), None)
    if current is None:
        return {'state': 'pending', 'reason': 'baseline trial failed'}
    path = [current]
    while True:
        neighbors = [row for row in rows
                     if sum(row['policy'][key] != current['policy'][key] for key in BASELINE) == 1
                     and row['loss'] < current['loss'] - 1e-15]
        if not neighbors:
            return {'state': 'completed', 'path': path, 'selected': current['policy'],
                    'training_loss': current['loss'], 'additional_evaluations': 0}
        current = min(neighbors, key=lambda row: (row['loss'], digest(row['policy'])))
        path.append(current)


def _mean_shadow(score, field):
    return math.fsum(row['shadow_selection'][field] for row in score['issues']) / score['issue_count']


def run(output, *, seed=1729, signal=True):
    if type(seed) is not int or not 0 <= seed < 1000000 or type(signal) is not bool:
        raise ValueError('integer seed in [0,1000000) and boolean signal required')
    output = Path(output)
    root = Path(__file__).resolve().parents[1]
    source = {p: text_digest((root / p).read_text())
              for p in ('feedback/selection.py', 'research/synthetic_learning.py')}
    spec = {'schema': 'zenith_synthetic_learning_v1', 'seed': seed, 'signal': signal,
            'splits': SPLITS, 'universe_size': 8, 'selection_budget': BUDGET,
            'loss': 'equal_date_universe_squared_error_with_zero_fallback',
            'baseline': BASELINE, 'candidate_bank': candidates(), 'validation_margin': MARGIN,
            'source_hashes': source, 'kind': 'constructed deterministic operator example',
            'known_mechanism': 'return = 0.08 * (new/prior_guidance - 1) + noise; signal=False removes term',
            'boundary': 'Known generator and correct rule in bank. No LLM, native graph execution, market or discovery claim.'}
    # A fresh directory is the reservation. Failed/partial studies cannot be overwritten.
    output.mkdir(parents=True, exist_ok=False)
    write_json(output / 'spec.json', spec)
    datasets = {}
    for split, (start, end) in SPLITS.items():
        pairs = [make_day(index, seed, signal=signal) for index in range(start, end)]
        forwards = [pair[0] for pair in pairs]
        labels = {pair[0]['issue_id']: pair[1] for pair in pairs}
        datasets[split] = (forwards, labels)
        write_json(output / split / 'inputs.json', forwards)
        write_json(output / split / 'truth.json', labels)

    training = []
    ledger = output / 'trials.jsonl'

    def record(row):
        with ledger.open('a') as stream:
            stream.write(json.dumps(row, sort_keys=True, allow_nan=False) + '\n')

    for index, policy in enumerate(candidates()):
        row = {'trial': index, 'policy': policy, 'status': 'reserved'}
        record(row)
        try:
            score, traces = evaluate(*datasets['training'], policy)
            write_json(output / 'training' / f'trial-{index}.json', {'score': score, 'traces': traces})
            row = {**row, 'status': 'completed', 'loss': score['metrics']['universe_loss']}
        except (ValueError, KeyError, ArithmeticError) as exc:
            row = {**row, 'status': 'failed', 'error': str(exc)}
        record(row)
        training.append(row)

    proposal = choose(training)
    local_search = single_edit_search(training)
    validation = {}
    for name, policy in [('baseline', BASELINE), ('proposal', proposal)]:
        score, traces = evaluate(*datasets['validation'], policy)
        write_json(output / 'validation' / f'{name}.json', {'score': score, 'traces': traces})
        validation[name] = score['metrics']['universe_loss']
    accepted = validation['proposal'] < validation['baseline'] * (1 - MARGIN)
    selected = proposal if accepted else BASELINE
    decision = {'proposal': proposal, 'selected': selected, 'accepted_on_validation': accepted,
                'validation_losses': validation, 'assessment_used': False}
    write_json(output / 'decision.json', decision)
    assessment = {}
    for name, policy in [('baseline', BASELINE), ('selected', selected)]:
        score, traces = evaluate(*datasets['assessment'], policy)
        write_json(output / 'assessment' / f'{name}.json', {'score': score, 'traces': traces})
        assessment[name] = {**score['metrics'],
            'selection_gain_over_uniform': _mean_shadow(score, 'selection_gain_over_uniform'),
            'hindsight_regret': _mean_shadow(score, 'hindsight_regret')}
    files = {str(p.relative_to(output)): text_digest(p.read_text())
             for p in sorted(output.rglob('*')) if p.is_file()}
    report = {'schema': 'zenith_synthetic_learning_receipt_v1', 'spec_sha256': digest(spec),
              'kind': spec['kind'], 'boundary': spec['boundary'], 'source_hashes': source,
              'seed': seed, 'signal': signal, 'dates': {k: b-a for k, (a, b) in SPLITS.items()},
              'trial_count': len(training), 'training_trials': training, 'decision': decision,
              'single_edit_search_control': local_search,
              'assessment': assessment, 'model_calls': 0, 'live_mutation_permission': False,
              'files': files}
    write_json(output / 'report.json', report)
    return report
