"""A-share forecast study: offline compilation, explicit execution, one selection.

The native Lab and the previous US study remain distinct experiments. This
owner reuses their JSON validation, node cache and budgeted provider. Compilation
does not call a model. Every runtime action requires a separately released,
hash-bound authorization; the recorded research hold is not spending authority.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path

import numpy as np

from benchmarks import traderharness as data
from benchmarks.stocknet import fit_ridge, ridge_predict
from research.engine import canonical, event_time, read_json, write_json
from research import ashare_protocol as protocol
from research import ashare_text
from research import trading_protocol as typed
from research.trading_study import _observe_node

ROOT = Path(__file__).resolve().parents[1]
ARMS = ('outcome', 'hindsight', 'blinded')


def source_hashes():
    paths = ['benchmarks/traderharness.py', 'benchmarks/trading_task.py', 'benchmarks/stocknet.py',
             'research/ashare_study.py', 'research/ashare_protocol.py', 'research/ashare_text.py', 'research/trading_protocol.py',
             'research/trading_study.py', 'research/engine.py', 'zenith/budgeted.py', 'zenith/providers.py']
    return {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in paths}


def groups(rows):
    result = defaultdict(list)
    for row in rows:
        result[row['issue_date']].append(row)
    return dict(sorted(result.items()))


def spaced(values, count):
    """Fixed even temporal coverage, chosen without prices, text or outcomes."""
    return [values[i] for i in np.linspace(0, len(values) - 1, min(count, len(values)), dtype=int)]


def execution_profile(name, rows):
    dates = {p: list(groups([r for r in rows if r['phase'] == p])) for p in data.SPLITS}
    if name not in ('full', 'first_learning'):
        raise ValueError('unknown execution profile')
    full = name == 'full'
    validation = dates['validation'] if full else spaced(dates['validation'], 24)
    return {'name': name, 'phase_dates': {**dates, 'validation': validation},
            'learning_arms': list(ARMS) if full else ['outcome', 'hindsight'],
            'information_modes': ['rich', 'metadata', 'price'] if full else ['rich'],
            'repeat': full, 'hindsight_metadata': full,
            'capability_dates': spaced(dates['training'], 6),
            'date_selection': 'evenly spaced integer positions including endpoints; no outcome ranking',
            'omitted_claims': [] if full else ['feedback versus a blinded proposal', 'assessment price/metadata contrast',
                                               'learned-skill metadata transfer', 'unchanged-model repeat'],
            'claim_unit': 'one realized artifact per learning arm on this fixed panel; not learning-procedure reliability'}


def phase_rows(rows, phase, spec):
    allowed = spec.get('profile', {}).get('phase_dates', {}).get(phase)
    return [r for r in rows if r['phase'] == phase and (allowed is None or r['issue_date'] in allowed)]


def score(rows, predictions):
    return {**evaluate(rows, predictions), 'predictions': predictions}


def correction_gain(rows, baseline, revised):
    """Exact date-equal identity: improvement = 2 residual*change - change²."""
    if not evaluate(rows, baseline)['complete'] or not evaluate(rows, revised)['complete']:
        return {'status': 'incomplete_support'}
    daily = []
    for stamp, batch in groups(rows).items():
        terms = []
        for r in batch:
            b, p = baseline[r['sample_id']], revised[r['sample_id']]
            residual, delta = r['actual_return'] - b, p - b
            terms.append((2 * residual * delta, delta ** 2, residual ** 2 - (r['actual_return'] - p) ** 2))
        means = [math.fsum(t[i] for t in terms) / len(terms) for i in range(3)]
        daily.append(dict(zip(('alignment', 'change_penalty', 'mse_improvement'), means), issue_date=stamp))
    return {'status': 'complete_descriptive_identity',
            **{k: math.fsum(d[k] for d in daily) / len(daily) for k in ('alignment', 'change_penalty', 'mse_improvement')},
            'daily': daily, 'interpretation': 'Positive alignment may still be outweighed by oversized changes; no causal diagnosis.'}


def fallback_system(rows, predictions):
    raw = evaluate(rows, predictions)
    failed = set(raw['missing'])
    completed = {r['sample_id']: 0. if r['sample_id'] in failed else predictions[r['sample_id']] for r in rows}
    return {'policy': 'zero market-relative forecast for missing, invalid or abstained output',
            'fallback_count': len(failed), 'raw_complete': raw['complete'], 'score': evaluate(rows, completed)}


def evaluate(rows, predictions):
    """Complete date support only; common + centered loss equals primary MSE."""
    daily, missing = [], []
    for stamp, batch in groups(rows).items():
        actual, predicted = [], []
        for row in batch:
            value = predictions.get(row['sample_id'])
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                missing.append(row['sample_id'])
            else:
                actual.append(row['actual_return'])
                predicted.append(value)
        if len(predicted) != len(batch):
            continue
        n = len(batch)
        pm, ym = math.fsum(predicted) / n, math.fsum(actual) / n
        common = (pm - ym) ** 2
        relative = math.fsum(((p - pm) - (y - ym)) ** 2 for p, y in zip(predicted, actual, strict=True)) / n
        total = math.fsum((p - y) ** 2 for p, y in zip(predicted, actual, strict=True)) / n
        # Pairwise ordering, with tied forecasts receiving half credit.
        concordance = []
        for i in range(n):
            for j in range(i):
                if actual[i] == actual[j]:
                    continue
                product = (predicted[i] - predicted[j]) * (actual[i] - actual[j])
                concordance.append(1.0 if product > 0 else 0.5 if product == 0 else 0.0)
        daily.append({'issue_date': stamp, 'mse': total, 'common_level_mse': common,
                      'relative_shape_mse': relative,
                      'pairwise_order_accuracy': math.fsum(concordance) / len(concordance) if concordance else None})
    complete = not missing and len(daily) == len(groups(rows)) and bool(rows)
    metrics = {key: math.fsum(r[key] for r in daily) / len(daily) if complete else None
               for key in ('mse', 'common_level_mse', 'relative_shape_mse')}
    order = [r['pairwise_order_accuracy'] for r in daily if r['pairwise_order_accuracy'] is not None]
    return {'complete': complete, 'allowances': len(rows), 'missing': missing,
            'issue_dates': len(groups(rows)), 'metrics': metrics,
            'pairwise_order_accuracy': math.fsum(order) / len(order) if complete and order else None,
            'daily': daily if complete else [], 'partial_daily_withheld_from_selection': not complete}


def paired(candidate, baseline, *, replicates=2000):
    if not candidate['complete'] or not baseline['complete']:
        return {'status': 'incomplete_support', 'mean_difference': None}
    left, right = candidate['daily'], baseline['daily']
    if [r['issue_date'] for r in left] != [r['issue_date'] for r in right]:
        raise ValueError('paired support differs')
    delta = np.array([a['mse'] - b['mse'] for a, b in zip(left, right, strict=True)])
    rng = np.random.default_rng(104729)
    # Five adjacent issue batches, not five assets or five individual sessions.
    block = min(5, len(delta))
    draws = []
    for _ in range(replicates):
        starts = rng.integers(0, len(delta), size=math.ceil(len(delta) / block))
        indices = [(int(s) + j) % len(delta) for s in starts for j in range(block)][:len(delta)]
        draws.append(float(delta[indices].mean()))
    return {'status': 'descriptive_dependent_comparison', 'mean_difference': float(delta.mean()),
            'percentile_interval_95': np.quantile(draws, [.025, .975]).tolist(),
            'paired_issue_differences': delta.tolist(), 'block_issue_batches': block,
            'replicates': replicates, 'interpretation': 'Descriptive unadjusted interval; not a superiority test or multiplicity correction.'}


def compile_study(dataset, study, *, profile='full', base_dates=None):
    if study.exists():
        raise ValueError('refuse to overwrite a study')
    tables, hashes = data.read_sources(dataset)
    built = data.build(tables)
    rows, packets = built['rows'], built['packets']
    if not rows or any(not [r for r in rows if r['phase'] == p] for p in data.SPLITS):
        raise ValueError('all three phases require admitted support')
    for packet in packets.values():
        typed.validate_packet(packet)
    counts = {p: len(groups([r for r in rows if r['phase'] == p])) for p in data.SPLITS}
    manifest = {k: built[k] for k in ('schedule', 'inventory', 'exclusions', 'clock_audit', 'fit_excluded_allowances', 'calendar')}
    manifest.update(schema='zenith_ashare_admission_v1', source_hashes=hashes,
                    phase_issue_counts=counts, admitted_asset_allowances=len(rows),
                    labels='separately stored in evaluator.json; never sent to forward nodes',
                    identity='retained; asset_N is a join key, not anonymization',
                    stock_volume='within-window normalized, share/lot transition not treated as a signal',
                    missing_amount='not used; never zero-filled',
                    text='source-token candidate links plus common headlines; entity links may conflate related companies; no full article/PDF prose',
                    rights='Original text and prices remain local under upstream terms.',
                    historical_vintage='unverified; source hashes establish bytes, not historical first availability')
    selection = {'candidate_allowance_per_arm': 1, 'skill_chars': 1200, 'memory_cases': 3,
                 'primary': 'date-equal mean squared error on complete common support',
                 'tie': 'unchanged wins', 'reject': 'any missing or schema-invalid validation forecast',
                 'mutation_slot': 'forecast skill; forecaster also receives original evidence',
                 'slot_basis': 'design choice; held inference means no empirical bottleneck-selection claim'}
    frozen = {'schema': 'zenith_ashare_study_v2', 'created_at': datetime.now(timezone.utc).isoformat(),
              'profile': execution_profile(profile, rows), 'library_versions': ashare_text.library_versions(),
              'input_revision': 'profit-prior-pairs-v2',
              'comparators': {'text': ashare_text.TEXT_CONFIG, 'ridge_alpha': 1., 'memory': ashare_text.RETRIEVAL_RULE,
                              'fallback': 'separate zero market-relative system policy; never raw-model selection'},
              'question': 'Does admitted text improve forecasts, and does hindsight teach a transferable skill beyond outcome learning and reflected memory?',
              'target': 'next-open through fifth-session close: gross stock wealth return minus CSI300 price return',
              'symbols': built['symbols'], 'splits': data.SPLITS, 'base_skill': protocol.BASE_SKILL,
              'anchor': built['anchor'], 'source_hashes': source_hashes(), 'selection': selection,
              'files': {'packets.json': data.sha(packets), 'evaluator.json': data.sha(rows), 'admission.json': data.sha(manifest)},
              'teacher_boundary': '2023-12-31T23:59:59+08:00',
              'information_arms': ['price', 'metadata', 'rich'], 'learning_arms': list(ARMS) + ['memory'],
              'teacher': 'Same full forward traces and asset residuals; hindsight alone adds subsequent reporting. One review per scheduled training batch in each treatment.',
              'exposure': 'Dataset quality inspection includes historical prices/actions; modern model pretraining unknown. No claim of globally unseen test data.',
              'execution_hold': True, 'execution_status': 'compiled_offline_unexecuted',
              'inference_settings': 'Reuse budgeted provider temperature 0; pin exact model/provider on released authorization; no silent retry.',
              'claim_limit': 'Forecast information and learning feasibility; no portfolio, trading advantage, causal diagnosis or novelty result.'}
    training_dates = list(groups([r for r in rows if r['phase'] == 'training']))
    chosen = sorted(set(base_dates or spaced(training_dates, 6)))
    if not chosen or not set(chosen) <= set(training_dates) or len(chosen) > 6:
        raise ValueError('base comparison requires at most six admitted training dates')
    frozen['base_comparison'] = {
        'dates': chosen, 'pilot_date': next((d for d in training_dates if d not in chosen), None),
        'selection': 'input-only development selection; explicit dates may target inspected recurring evidence challenges, never realized losses',
        'arms': ['direct', 'change_graph'], 'calls_per_date': 3,
        'signal_mapping': 'one nonnegative coefficient capped at 0.05; four mature-date warmup and four-date zero prior',
        'scope': 'base-system development; no teacher, skill proposal, validation or assessment calls'}
    study.mkdir(parents=True)
    for name, value in [('packets.json', packets), ('evaluator.json', rows), ('admission.json', manifest), ('frozen.json', frozen)]:
        write_json(study / name, value)
    write_json(study / 'binding.json', {'frozen_sha256': data.sha(frozen)})
    probes = protocol.semantic_probes(packets[min(packets)])
    write_json(study / 'semantic-probes.json', probes)
    examples = {}
    selectors = {'ordinary': lambda r: True, 'issuer_information': lambda r: r['issuer_retained'] > 0,
                 'thin_information': lambda r: r['issuer_retained'] == 0,
                 'action_boundary': lambda r: r['entry_at_ex_date'] or r['action_in_outcome']}
    for name, predicate in selectors.items():
        item = next((r for r in built['inventory'] if predicate(r)), None)
        examples[name] = {'selection': 'first chronological match by input/support property, never loss',
                          'inventory': item, 'packet': packets[item['issue_date']] if item else None}
    write_json(study / 'representative-inputs.json', examples)
    plan = cost_plan(frozen, packets)
    write_json(study / 'execution-plan.json', plan)
    write_json(study / 'base-plan.json', base_plan(frozen, packets))
    return {'study': str(study), 'frozen_sha256': data.sha(frozen), 'phase_issue_counts': counts,
            'asset_allowances': len(rows), 'excluded_windows': len(built['exclusions']),
            'inference_calls': 0, 'plan': plan}


def cost_plan(spec, packets, *, input_per_million=None, output_per_million=None, output_tokens=4096):
    counts = {p: sum(a <= stamp < b for stamp in packets) for p, (a, b) in spec['splits'].items()}
    profile = spec.get('profile', {})
    if profile:
        counts = {p: len(dates) for p, dates in profile['phase_dates'].items()}
    # Train base (2T), matched teachers (2T), three proposals. Validation:
    # three independent interpreters + base for each (6V), three skills + memory (4V).
    # Test adds repeat (1), learned-skill metadata transfer (1), same four learning arms.
    arms = len(profile.get('learning_arms', ARMS))
    modes = len(profile.get('information_modes', ['rich', 'metadata', 'price']))
    val_per_date = 2 * modes + arms + 1
    test_per_date = val_per_date + int(profile.get('repeat', True)) + int(profile.get('hindsight_metadata', True))
    calls = 4 * counts['training'] + val_per_date * counts['validation'] + test_per_date * counts['test'] + arms
    probe_calls = 2 * len(protocol.semantic_probes(packets[min(packets)]))
    capability_extra = 4 * len(profile.get('capability_dates', []))
    max_packet_bytes = max(len(canonical(p)) for p in packets.values())
    # Conservative UTF-8 byte bound, not an alleged tokenizer count. Include
    # original evidence twice in teacher case, two model responses and hindsight.
    forward_input = max_packet_bytes + 96000
    teacher_input = max_packet_bytes + 384000
    proposal_input = counts['training'] * 24000 + 12000
    total_input = ((2 * counts['training'] + val_per_date * counts['validation'] + test_per_date * counts['test']
                    + capability_extra + probe_calls) * forward_input
                   + 2 * counts['training'] * teacher_input + arms * proposal_input)
    total_output = (calls + capability_extra + probe_calls) * output_tokens
    sizes = [len(protocol.interpret_prompt(protocol.project(p, 'rich')).encode('utf-8')) for p in packets.values()]
    priced = input_per_million is not None and output_per_million is not None
    if priced and (input_per_million < 0 or output_per_million < 0):
        raise ValueError('negative price quote')
    return {'schema': 'zenith_ashare_execution_plan_v2', 'status': 'held_no_paid_execution',
            'profile': profile.get('name', 'full'),
            'phase_issue_counts': counts, 'maximum_core_calls': calls,
            'probes': {'additional_calls': probe_calls, 'included_in_core_budget': False, 'status': 'unexecuted'},
            'capability_extra_calls': capability_extra,
            'maximum_total_calls': calls + capability_extra + probe_calls,
            'stages': {'capability': probe_calls + 6 * len(profile.get('capability_dates', [])),
                       'development_and_learning_including_reused_capability_rich': 4 * counts['training'] + arms,
                       'validation': val_per_date * counts['validation'], 'assessment': test_per_date * counts['test']},
            'prepared_interpret_prompt_utf8_bytes': {'min': min(sizes), 'median': float(np.median(sizes)), 'max': max(sizes)},
            'unchanged_policy_reuse': 'Already cached interpretation and identical base skill reuse exact observations; maximum assumes every proposal is valid and different.',
            'expected_bill': None,
            'bill_uncertainty': 'No selected-model tokenization or real A-share usage receipt exists. Prepared bytes are measured; intermediate responses are bounded. No pilot average is invented.',
            'absolute_spending_limit': 'Only the existing immutable authorization ledger can supply remaining money/calls; this plan grants neither.',
            'max_packet_utf8_bytes': max_packet_bytes, 'max_output_tokens_per_call': output_tokens,
            'conservative_input_token_bound': total_input, 'maximum_output_tokens': total_output,
            'quote_input_usd_per_million': input_per_million, 'quote_output_usd_per_million': output_per_million,
            'conservative_cost_usd': (total_input * input_per_million + total_output * output_per_million) / 1e6 if priced else None,
            'cost_basis': 'One UTF-8 byte per token upper planning bound plus fixed response/teacher allowances; uncached prices. Quote is planning data, not spending authorization.',
            'stop_rule': 'No automatic retry; any unknown-cost/provider failure halts. One candidate per arm; selection once, assessment once. Shared ledger caps override this plan.',
            'context_note': 'Full review bank must fit the selected model context; never silently drop training cases.',
            'manual_teacher_cost': 'No manual web research enters training. This preparation and research are unpriced, not zero-cost evidence.'}


def load(study):
    spec = read_json(study / 'frozen.json')
    if data.sha(spec) != read_json(study / 'binding.json')['frozen_sha256'] or spec['source_hashes'] != source_hashes():
        raise ValueError('frozen study/source changed')
    if spec['library_versions'] != ashare_text.library_versions():
        raise ValueError('frozen numerical/text runtime versions changed')
    values = {}
    for name, expected in spec['files'].items():
        values[name] = read_json(study / name)
        if data.sha(values[name]) != expected:
            raise ValueError('frozen data changed: ' + name)
    return spec, values['evaluator.json'], values['packets.json']


def node(study, key, prompt, parser, spec):
    # Every exact request/response and schema rejection uses the existing cache
    # and provider ledger joins; no rewritten attempts or favorable retries.
    if spec.get('_cache_only') and not (study / 'nodes' / (key + '.json')).exists():
        raise ValueError('required source observation missing: ' + key)
    return _observe_node(study / 'nodes' / (key + '.json'), {'prompt_sha256': data.sha(prompt)}, parser,
                         study=study, key=key, prompt=prompt, spec=spec)


def save_stage(study, name, result):
    write_json(study / (name + '.json'), result)
    write_json(study / (name + '-binding.json'), {'sha256': data.sha(result),
               'frozen_sha256': read_json(study / 'binding.json')['frozen_sha256']})


def load_stage(study, name):
    result = read_json(study / (name + '.json'))
    binding = read_json(study / (name + '-binding.json'))
    if binding != {'sha256': data.sha(result), 'frozen_sha256': read_json(study / 'binding.json')['frozen_sha256']}:
        raise ValueError(name + ' stage changed')
    return result


def forecasts(study, phase, policies, spec, rows, packets, cases=(), reviews=()):
    records = {name: {} for name in policies}
    selected_rows = phase_rows(rows, phase, spec)
    for stamp, batch in groups(selected_rows).items():
        for name, policy in policies.items():
            mode = policy.get('mode', 'rich')
            packet = protocol.project(packets[stamp], mode)
            interpretation = node(study, f'interpret_{mode}_{stamp}', protocol.interpret_prompt(packet),
                                  lambda text: typed.parse_interpretation(text, packet), spec)
            memory = protocol.retrieve_memories(packet, cases, reviews) if name == 'memory' else []
            if name == 'memory' and not spec.get('_cache_only'):
                write_json(study / 'memory-receipts' / (stamp + '.json'), {
                    'selected_case_ids': [m['case_id'] for m in memory],
                    'serialized_bytes': len(canonical(memory)), 'max_bytes': 24000, 'max_cases': 3,
                    'retrieval': ashare_text.RETRIEVAL_RULE,
                    'input_packet_sha256': packet['packet_sha256']})
            prompt = protocol.forecast_prompt(packet, interpretation['value'], policy['skill'], memory)
            # Identical unchanged policies alias actual baseline draws; repeat
            # alone deliberately gets its own independent call key.
            call_name = ('base_' + mode if policy['skill'] == protocol.BASE_SKILL and name not in ('repeat', 'memory') else name)
            forecast = node(study, f'{call_name}_{stamp}', prompt,
                            lambda text: typed.parse_forecast(text, packet, interpretation['value']), spec)
            records[name][stamp] = forecast
    scores = {}
    for name, by_date in records.items():
        predicted = {}
        for stamp, record in by_date.items():
            values = (record['value'] or {}).get('forecasts', [])
            for f in values:
                symbol = spec['symbols'][int(f['asset_id'].split('_')[1]) - 1]
                predicted[stamp + ':' + symbol] = f['mean_expected_return']
        scores[name] = evaluate(selected_rows, predicted)
        scores[name]['predictions'] = predicted
    return scores


def development(study, spec, rows, packets):
    if (study / 'selection.json').exists() or (study / 'final-seal.json').exists():
        raise ValueError('development closed')
    scores = forecasts(study, 'training', {'base': {'skill': protocol.BASE_SKILL}}, spec, rows, packets)
    save_stage(study, 'training', scores)
    return scores


def learn(study, spec, rows, packets, *, verify=False):
    if not verify and ((study / 'selection.json').exists() or (study / 'final-seal.json').exists()):
        raise ValueError('learning closed')
    if not (study / 'training.json').exists():
        raise ValueError('complete scheduled development attempts before learning')
    training = load_stage(study, 'training')
    cached_spec = {**spec, '_cache_only': True}
    if training != forecasts(study, 'training', {'base': {'skill': protocol.BASE_SKILL}}, cached_spec, rows, packets):
        raise ValueError('training projection differs from recorded responses')
    if verify:
        spec = cached_spec
    banks, cases = {}, {}
    for arm in ('outcome', 'hindsight'):
        bank, source_cases = [], []
        for stamp, batch in groups([r for r in rows if r['phase'] == 'training']).items():
            # Revalidate the existing baseline cache through exactly the same node
            # path before trusting any trace in a teacher packet.
            packet = protocol.project(packets[stamp], 'rich')
            interpretation = node(study, f'interpret_rich_{stamp}', protocol.interpret_prompt(packet),
                                  lambda text: typed.parse_interpretation(text, packet), spec)
            forecast = node(study, f'base_rich_{stamp}', protocol.forecast_prompt(packet, interpretation['value']),
                            lambda text: typed.parse_forecast(text, packet, interpretation['value']), spec)
            case = protocol.teacher_case(packet, forecast['value'], interpretation['value'], batch,
                                         spec['teacher_boundary'], hindsight=arm == 'hindsight')
            review = node(study, f'review_{arm}_{stamp}', protocol.review_prompt(case),
                          lambda text: protocol.parse_review(text, case), spec)
            bank.append(review['value'] or {'case_id': stamp, 'status': 'rejected'})
            source_cases.append(case)
        banks[arm], cases[arm] = bank, source_cases
    candidates = {}
    for arm in spec.get('profile', {}).get('learning_arms', ARMS):
        bank = banks.get(arm, [])
        record = node(study, 'proposal_' + arm, protocol.skill_prompt(arm, bank),
                      lambda text: typed.parse_skill_update(text, [r['case_id'] for r in bank]), spec)
        candidates[arm] = record
    result = {'banks': banks, 'cases': cases, 'candidates': candidates}
    if verify:
        if result != load_stage(study, 'learning'):
            raise ValueError('learning projection differs from recorded responses')
        return result
    save_stage(study, 'learning', result)
    return {'proposal_statuses': {k: v['status'] for k, v in candidates.items()},
            'scheduled_training_cases_per_treatment': len(cases['hindsight'])}


def policies(learning, spec=None):
    modes = (spec or {}).get('profile', {}).get('information_modes', ['rich', 'metadata', 'price'])
    result = {mode: {'skill': protocol.BASE_SKILL, 'mode': mode} for mode in modes}
    for arm, record in learning['candidates'].items():
        if record['value'] is not None:
            result[arm] = {'skill': record['value']['skill']}
    result['memory'] = {'skill': protocol.BASE_SKILL}
    return result


def select(study, spec, rows, packets, *, verify=False):
    if not verify and ((study / 'selection.json').exists() or (study / 'final-seal.json').exists()):
        raise ValueError('selection already frozen')
    if verify:
        spec = {**spec, '_cache_only': True}
    learning = learn(study, spec, rows, packets, verify=True)
    proposed = policies(learning, spec)
    scores = forecasts(study, 'validation', proposed, spec, rows, packets,
                       learning['cases']['hindsight'], learning['banks']['hindsight'])
    choices = {}
    base = scores['rich']['metrics']['mse']
    for arm in spec.get('profile', {}).get('learning_arms', ARMS):
        candidate = scores.get(arm, {}).get('metrics', {}).get('mse')
        choices[arm] = arm if base is not None and candidate is not None and candidate < base else 'rich'
    # Keep the raw memory arm even if worse: it is a mechanism comparator, not
    # a silently suppressed result. Every proposed/rejected skill stays recorded.
    result = {'choices': choices, 'scores': scores, 'learning_sha256': data.sha(learning),
              'policies': proposed, 'frozen_sha256': read_json(study / 'binding.json')['frozen_sha256']}
    result['selection_sha256'] = data.sha(result)
    if verify:
        if result != read_json(study / 'selection.json'):
            raise ValueError('selection differs from recorded validation and candidates')
        return result
    write_json(study / 'selection.json', result)
    return result


def numerical_controls(rows, training_predictions):
    training = [r for r in rows if r['phase'] == 'training']
    fit = fit_ridge(training)
    fit['feature_names'] = data.FEATURES
    complete = all(isinstance(training_predictions.get(r['sample_id']), (int, float)) for r in training)
    # Intercept+slope calibration, fixed ridge penalty, trained only once.
    calibration = None
    if complete:
        x = np.column_stack((np.ones(len(training)), [training_predictions[r['sample_id']] for r in training]))
        y = np.array([r['actual_return'] for r in training])
        calibration = np.linalg.solve(x.T @ x + np.diag([0., 1.]), x.T @ y).tolist()
    return fit, calibration


def final(study, spec, rows, packets):
    selection = select(study, spec, rows, packets, verify=True)
    unsigned = {k: v for k, v in selection.items() if k != 'selection_sha256'}
    if data.sha(unsigned) != selection['selection_sha256']:
        raise ValueError('selection changed')
    learning = learn(study, spec, rows, packets, verify=True)
    if data.sha(learning) != selection['learning_sha256']:
        raise ValueError('teacher/candidate bank changed after selection')
    seal = {'selection_sha256': data.sha(selection), 'frozen_sha256': read_json(study / 'binding.json')['frozen_sha256']}
    seal_path = study / 'final-seal.json'
    replay = False
    if seal_path.exists():
        if read_json(seal_path) != seal:
            raise ValueError('assessment seal changed')
        if (study / 'result.json').exists():
            replay = True
            spec = {**spec, '_cache_only': True}
        else:
            raise ValueError('interrupted assessment is spent; no automatic resampling')
    else:
        write_json(seal_path, seal)
    profile = spec.get('profile', {})
    chosen = {mode: {'skill': protocol.BASE_SKILL, 'mode': mode}
              for mode in profile.get('information_modes', ['rich', 'metadata', 'price'])}
    chosen.update({arm: selection['policies'][name] for arm, name in selection['choices'].items()})
    chosen['memory'] = {'skill': protocol.BASE_SKILL}
    if profile.get('repeat', True):
        chosen['repeat'] = {'skill': protocol.BASE_SKILL}
    if profile.get('hindsight_metadata', True):
        chosen['hindsight_metadata'] = {**chosen['hindsight'], 'mode': 'metadata'}
    scores = forecasts(study, 'test', chosen, spec, rows, packets,
                       learning['cases']['hindsight'], learning['banks']['hindsight'])
    fit, calibration = numerical_controls(rows, load_stage(study, 'training')['base']['predictions'])
    test = phase_rows(rows, 'test', spec)
    for name, predict in [('zero', lambda r: 0.), ('momentum', lambda r: r['momentum']),
                          ('ridge_2021', lambda r: ridge_predict(r, spec['anchor'])),
                          ('ridge_training', lambda r: ridge_predict(r, fit))]:
        scores[name] = score(test, {r['sample_id']: predict(r) for r in test})
    if calibration is not None:
        scores['calibration'] = score(test, {k: calibration[0] + calibration[1] * v
                                               for k, v in scores['rich']['predictions'].items() if v is not None})
    control_fits = {}
    for use_text, name in [(False, 'ridge_numeric_metadata_identity'), (True, 'ridge_character_text')]:
        control = ashare_text.fit_control(phase_rows(rows, 'training', spec), packets, use_text=use_text)
        scores[name] = score(test, ashare_text.predict_control(control, test, packets))
        control_fits[name] = control['receipt']
    result = {'status': 'completed_historical_forecast_assessment', 'selection': selection['choices'],
              'scores': scores, 'paired_vs_rich': {k: paired(v, scores['rich']) for k, v in scores.items() if k != 'rich'},
              'correction_vs_rich': {k: correction_gain(test, scores['rich']['predictions'], v['predictions'])
                                     for k, v in scores.items() if k != 'rich'},
              'system_zero_fallback': {k: fallback_system(test, v['predictions']) for k, v in scores.items()},
              'text_control_fits': control_fits,
              'calibration': calibration, 'seal': seal, 'claim_limit': spec['claim_limit']}
    if replay:
        if load_stage(study, 'result') != result:
            raise ValueError('final projection differs from recorded responses')
    else:
        save_stage(study, 'result', result)
    return result


def probes(study, spec, rows, packets):
    """Real model behavior; no historical labels and no automatic semantic grade."""
    if (study / 'training.json').exists():
        raise ValueError('run behavioral compatibility probes before study development; later revisions need a new study')
    results = []
    # Recreate from bound source packet, never trust an edited probe sidecar.
    for probe in protocol.semantic_probes(packets[min(packets)]):
        packet = probe['packet']
        interp = node(study, 'probe_interpret_' + probe['probe_id'], protocol.interpret_prompt(packet),
                      lambda text: typed.parse_interpretation(text, packet), spec)
        predicted = node(study, 'probe_forecast_' + probe['probe_id'],
                         protocol.forecast_prompt(packet, interp['value']),
                         lambda text: typed.parse_forecast(text, packet, interp['value']), spec)
        results.append({'probe_id': probe['probe_id'], 'expected_distinction': probe['expected_distinction'],
                        'interpretation': interp, 'forecast': predicted,
                        'semantic_assessment': 'requires recorded review; schema acceptance is not semantic success'})
    save_stage(study, 'probe-results', results)
    return results


def capability(study, spec, rows, packets):
    """Declared probes and development contrasts; no assessment consumption."""
    behavior = probes(study, spec, rows, packets)
    dates = spec['profile']['capability_dates']
    local_spec = {**spec, 'profile': {**spec['profile'], 'phase_dates': {'training': dates}}}
    scores = forecasts(study, 'training', {mode: {'skill': protocol.BASE_SKILL, 'mode': mode}
                        for mode in ('rich', 'metadata', 'price')}, local_spec, rows, packets)
    result = {'probe_count': len(behavior), 'development_dates': dates, 'scores': scores,
              'next_decision': 'Inspect supplied-evidence behavior and operational failures before continuing the released budget; no automatic semantic pass.'}
    save_stage(study, 'capability', result)
    return result


def base_plan(spec, packets, *, input_per_million=None, output_per_million=None):
    config = spec['base_comparison']
    dates = ([config['pilot_date']] if config['pilot_date'] else []) + config['dates']
    bounds = []
    for stamp in dates:
        packet = protocol.project(packets[stamp], 'rich')
        direct = len(protocol.direct_prompt(packet).encode())
        change = len(protocol.change_prompt(packet).encode())
        # Parser admits at most 16,000 raw JSON characters, each at most four
        # UTF-8 bytes. Include padding for canonicalization and the nonnull hash;
        # control-character escaping can exceed the ordinary-summary estimate.
        forecast = len(protocol.forecast_prompt(packet, None).encode()) + 65536
        bounds += [direct + 4096, change + 4096, forecast + 4096]
    total = sum(bounds)
    quote = None if input_per_million is None or output_per_million is None else (
        total * input_per_million + len(bounds) * 4096 * output_per_million) / 1e6
    return {'schema': 'zenith_base_development_plan_v1', 'status': 'held', **config,
            'pilot_calls': 3 if config['pilot_date'] else 0, 'comparison_calls': 3*len(config['dates']),
            'maximum_calls': len(bounds), 'max_output_tokens': 4096,
            'input_token_reservation_bound': total, 'conservative_cost_usd': quote,
            'quote_rates': {'input_per_million': input_per_million, 'output_per_million': output_per_million},
            'expected_bill': None, 'authority': 'plan only; existing paid hold remains',
            'stop': 'pilot before comparison; schema/provider failures retained, never silently retried',
            'cost_comparison': 'direct uses one call/date; graph uses two, measured provider receipts retained'}


def base_comparison(study, spec, rows, packets, *, pilot=False):
    """Actual base outputs through the existing response and provider authority."""
    if not spec.get('_cache_only') and ((study / 'selection.json').exists() or (study / 'final-seal.json').exists()):
        raise ValueError('development closed')
    config = spec['base_comparison']
    if not config['pilot_date']:
        raise ValueError('an excluded compatibility date is required')
    if not pilot:
        prior = base_comparison(study, {**spec, '_cache_only': True}, rows, packets, pilot=True)
        if not prior['complete']:
            raise ValueError('compatibility pilot incomplete or rejected')
    dates = [config['pilot_date']] if pilot else config['dates']
    selected = [r for r in rows if r['phase'] == 'training' and r['issue_date'] in dates]
    predictions = {'direct': {}, 'change_graph': {}, 'economic_signal': {}}
    observations = {}
    for stamp in dates:
        packet = protocol.project(packets[stamp], 'rich')
        direct = node(study, 'base_direct_' + stamp, protocol.direct_prompt(packet),
                      lambda text: typed.parse_forecast(text, packet, None), spec)
        change = node(study, 'base_change_' + stamp, protocol.change_prompt(packet),
                      lambda text: protocol.parse_change(text, packet), spec)
        interpretation = (change['value'] or {}).get('interpretation')
        graph = (node(study, 'base_graph_' + stamp, protocol.forecast_prompt(packet, interpretation),
                      lambda text: typed.parse_forecast(text, packet, interpretation), spec)
                 if interpretation is not None else {'value': None, 'status': 'skipped_invalid_dependency'})
        observations[stamp] = {'direct': direct, 'change': change, 'graph': graph}
        for name, record in [('direct', direct), ('change_graph', graph)]:
            for f in (record['value'] or {}).get('forecasts', []):
                symbol = spec['symbols'][int(f['asset_id'].split('_')[1])-1]
                predictions[name][stamp + ':' + symbol] = f['mean_expected_return']
        for signal in (change['value'] or {}).get('signals', []):
            symbol = spec['symbols'][int(signal['asset_id'].split('_')[1])-1]
            predictions['economic_signal'][stamp + ':' + symbol] = signal['economic_change']
        if any(r.get('value') is None for r in observations[stamp].values()):
            break
    complete = len(observations) == len(dates) and all(r.get('value') is not None for group in observations.values() for r in group.values())
    result = {'dates': dates, 'complete': complete, 'observations': observations,
              'status': 'compatibility_only_excluded_from_scores' if pilot else 'development_only',
              'assessment_consumed': False, 'predictions': predictions,
              'semantic_review': 'Read FACT/CHANGE/CHANNEL/PRICED/UNKNOWN against original evidence; schema acceptance is not an entailment verdict.'}
    if not pilot:
        result['scores'] = {name: evaluate(selected, p) for name, p in predictions.items() if name != 'economic_signal'}
        result['scores']['zero'] = evaluate(selected, {r['sample_id']: 0. for r in selected})
        result['calibration'] = {}
        signals = predictions['economic_signal']
        result['signal_missing_count'] = sum(v is None for v in signals.values())
        mapped = {**predictions, 'economic_signal': {k: 0. if v is None else v for k, v in signals.items()}}
        result['signal_fallback'] = 'Unknown signals remain null in raw outputs; the numerical system applies zero correction and includes every opportunity.'
        for name, p in mapped.items():
            if not evaluate(selected, p)['complete']:
                continue
            scaled, fit = ashare_text.chronological_scale(selected, p, max_scale=.05 if name == 'economic_signal' else 1.)
            result['scores'][name + '_scaled'] = evaluate(selected, scaled)
            result['calibration'][name] = fit
            later = [r for r in selected if r['issue_date'] in {f['query_issue'] for f in fit['fits'] if not f['warmup']}]
            result['scores'][name + '_scaled_after_warmup'] = evaluate(later, scaled)
            result.setdefault('matched_after_warmup', {})[name] = {
                'zero': evaluate(later, {r['sample_id']: 0. for r in later}),
                'direct': evaluate(later, predictions['direct']),
                'change_graph': evaluate(later, predictions['change_graph']),
                'scaled': evaluate(later, scaled)}
        result['claim_limit'] = 'Small behavior-first development batch, selected using inputs. No superiority, learned-reasoning or trading conclusion.'
    if not spec.get('_cache_only'):
        save_stage(study, 'base-pilot' if pilot else 'base-comparison', result)
    return result


def base_pilot(study, spec, rows, packets):
    return base_comparison(study, spec, rows, packets, pilot=True)


def offline_controls(study):
    """Chronological development-only numeric/text comparison, never test loss."""
    spec, rows, packets = load(study)
    training = phase_rows(rows, 'training', spec)
    dates = list(groups(training))
    if len(dates) <= 8:
        raise ValueError('offline controls need more than eight training issue dates')
    predictions = {'zero': {}, 'ridge_numeric_metadata_identity': {}, 'ridge_character_text': {}}
    evaluated, fits = [], []
    for stamp in dates[8:]:
        query = [r for r in training if r['issue_date'] == stamp]
        fitted = [r for r in training if r['issue_date'] < stamp
                  and event_time(r['outcome_available_at']) < event_time(query[0]['issue_at'])]
        evaluated += query
        predictions['zero'].update({r['sample_id']: 0. for r in query})
        for use_text, name in [(False, 'ridge_numeric_metadata_identity'), (True, 'ridge_character_text')]:
            fit = ashare_text.fit_control(fitted, packets, use_text=use_text)
            predictions[name].update(ashare_text.predict_control(fit, query, packets))
            fits.append({'query_issue': stamp, 'name': name, **fit['receipt']})
    diagnoses = {name: ashare_text.signal_diagnosis(evaluated, p)
                 for name, p in predictions.items() if name != 'zero'}
    diagnoses['incremental_text'] = ashare_text.signal_diagnosis(
        evaluated, predictions['ridge_character_text'], predictions['ridge_numeric_metadata_identity'])
    calibration = {}
    for name in ('ridge_numeric_metadata_identity', 'ridge_character_text'):
        predictions[name + '_scaled'], calibration[name] = ashare_text.chronological_scale(evaluated, predictions[name])
    numeric = predictions['ridge_numeric_metadata_identity_scaled']
    increment = {key: numeric[key] + predictions['ridge_character_text'][key]
                 - predictions['ridge_numeric_metadata_identity'][key] for key in numeric}
    predictions['scaled_numeric_plus_text'], calibration['incremental_text'] = ashare_text.chronological_scale(
        evaluated, increment, baseline=numeric)
    scores = {name: evaluate(evaluated, p) for name, p in predictions.items()}
    result = {'schema': 'zenith_ashare_development_controls_v1', 'status': 'development_only_measured',
              'frozen_sha256': read_json(study / 'binding.json')['frozen_sha256'],
              'training_warmup_issues': 8, 'evaluated_issue_dates': dates[8:], 'scores': scores,
              'correction_text_vs_metadata': correction_gain(evaluated, predictions['ridge_numeric_metadata_identity'], predictions['ridge_character_text']),
              'signal_diagnoses': diagnoses, 'calibration': calibration,
              'design_exposure': 'Scaling designed after observing the prior 33-date aggregate losses; chronological fits do not make this an untouched test.',
              'fits': fits, 'inference_calls': 0, 'assessment_consumed': False,
              'claim_limit': 'Expanding chronological training-only diagnostic of fixed cheap comparators. No LLM, learned-skill, heldout or trading result.'}
    save_stage(study, 'offline-controls', {**result, 'predictions': predictions})
    return result


def report(study, *, input_per_million=None, output_per_million=None):
    """Text-free public projection of an actual offline admission, not model results."""
    spec, rows, packets = load(study)
    admission = read_json(study / 'admission.json')
    phases = {}
    for phase in spec['splits']:
        items = [r for r in admission['inventory'] if r['phase'] == phase]
        dates = sorted({r['issue_date'] for r in items})
        phases[phase] = {'issue_dates': len(dates), 'asset_allowances': len(items),
                         'first_issue': dates[0], 'last_issue': dates[-1],
                         'without_issuer_tagged_text': sum(r['issuer_retained'] == 0 for r in items),
                         'issuer_items_retained': sum(r['issuer_retained'] for r in items),
                         'common_items_retained': sum(r['common_retained'] for r in items),
                         'prior_comparison_items': sum(r.get('prior_comparison_items', 0) for r in items),
                         'asset_windows_with_comparison': sum(bool(r.get('comparison_pairs')) for r in items),
                         'min_text_characters': min(r['retained_characters'] for r in items),
                         'max_text_characters': max(r['retained_characters'] for r in items)}
    return {'schema': 'zenith_ashare_offline_receipt_v1', 'status': 'compiled_offline_unexecuted',
            'inference_calls': 0, 'frozen_sha256': read_json(study / 'binding.json')['frozen_sha256'],
            'profile': spec['profile'], 'input_revision': spec['input_revision'],
            'source_hashes': spec['source_hashes'], 'data_hashes': admission['source_hashes'],
            'calendar': admission['calendar'], 'phases': phases, 'scheduled_windows': len(admission['schedule']),
            'excluded_windows': admission['exclusions'], 'clock_audit': admission['clock_audit'],
            'prior_ridge_fit': spec['anchor'],
            'plan': cost_plan(spec, packets, input_per_million=input_per_million, output_per_million=output_per_million),
            'boundary': spec['claim_limit'], 'text_limit': admission['text'],
            'review_input': 'Original forward packet, complete forecast/interpretation, per-asset residuals; hindsight adds capped full-outcome-window reporting.',
            'exposure': spec['exposure']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    p = sub.add_parser('compile')
    p.add_argument('--dataset', type=Path, required=True)
    p.add_argument('--study', type=Path, required=True)
    p.add_argument('--profile', choices=('full', 'first_learning'), default='full')
    p.add_argument('--base-date', action='append', dest='base_dates')
    p = sub.add_parser('plan')
    p.add_argument('--study', type=Path, required=True)
    p.add_argument('--input-usd-per-million', type=float)
    p.add_argument('--output-usd-per-million', type=float)
    p = sub.add_parser('base-plan')
    p.add_argument('--study', type=Path, required=True)
    p.add_argument('--input-usd-per-million', type=float)
    p.add_argument('--output-usd-per-million', type=float)
    p = sub.add_parser('report')
    p.add_argument('--study', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--input-usd-per-million', type=float)
    p.add_argument('--output-usd-per-million', type=float)
    p = sub.add_parser('offline-controls')
    p.add_argument('--study', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    for action in ('development', 'learn', 'select', 'final', 'probes', 'capability', 'base-pilot', 'base-comparison'):
        p = sub.add_parser(action)
        p.add_argument('--study', type=Path, required=True)
        p.add_argument('--authorization', type=Path, required=True)
        p.add_argument('--env-file', type=Path)
    args = parser.parse_args()
    if args.action == 'compile':
        result = compile_study(args.dataset, args.study, profile=args.profile, base_dates=args.base_dates)
    else:
        spec, rows, packets = load(args.study)
        if args.action == 'offline-controls':
            result = offline_controls(args.study)
            write_json(args.output, result)
        elif args.action == 'report':
            result = report(args.study, input_per_million=args.input_usd_per_million,
                            output_per_million=args.output_usd_per_million)
            write_json(args.output, result)
        elif args.action == 'plan':
            result = cost_plan(spec, packets, input_per_million=args.input_usd_per_million,
                               output_per_million=args.output_usd_per_million)
        elif args.action == 'base-plan':
            result = base_plan(spec, packets, input_per_million=args.input_usd_per_million,
                               output_per_million=args.output_usd_per_million)
        else:
            auth = read_json(args.authorization)
            binding = read_json(args.study / 'binding.json')['frozen_sha256']
            if auth.get('research_hold_released') is not True or auth.get('frozen_sha256') != binding:
                raise ValueError('paid execution held: requires explicit operator release bound to this study')
            actions = auth.get('allowed_actions', [args.action])
            if not isinstance(actions, list) or not all(isinstance(a, str) for a in actions):
                raise ValueError('allowed_actions must be an explicit list')
            if args.action not in actions:
                raise ValueError('action outside released scope')
            budget = auth.get('budget', {})
            if args.action in ('base-pilot', 'base-comparison'):
                if args.action not in auth.get('allowed_actions', []):
                    raise ValueError('base development requires an explicit action scope')
                if budget.get('max_output_tokens') != 4096:
                    raise ValueError('base plan requires its declared 4096 output-token cap')
            if not isinstance(budget.get('provider_slug'), str) or not budget['provider_slug'].strip():
                raise ValueError('exact upstream provider tag is required')
            # Freeze the one released authorization across all phases. Never
            # replace a halted/shared ledger or silently change provider caps.
            auth_path = args.study / 'execution-authorization.json'
            if auth_path.exists() and read_json(auth_path) != auth:
                raise ValueError('execution authorization changed')
            write_json(auth_path, auth)
            spec['budget'] = auth['budget']
            if args.env_file:
                from dotenv import load_dotenv
                load_dotenv(args.env_file, override=False)
            result = globals()[args.action.replace('-', '_')](args.study, spec, rows, packets)
    print(json.dumps(result, sort_keys=True, indent=2, allow_nan=False))


if __name__ == '__main__':
    main()
