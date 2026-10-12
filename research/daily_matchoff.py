"""Bind a reviewed daily challenger to the existing matched native cohort.

No new evaluator and no inference calls. Retention remains an explicit reviewed
development decision, with source-bound complete comparison evidence.
"""
from __future__ import annotations

from datetime import date, timedelta
import importlib.metadata
import json
from pathlib import Path
import subprocess

from feedback import engine as feedback
from research import cohort
from zenith import daily, runtime


def freeze(root, directory, episode, dataset, start, end, output, model, minimum_improvement,
           max_calls_per_run=21):
    root, directory, output = Path(root).resolve(), Path(directory).resolve(), Path(output).resolve()
    if root != runtime.DEFAULT_ROOT.resolve():
        raise ValueError('Native cohort currently uses this source checkout root')
    if output.exists():
        raise ValueError('Matchoff exists; retain its frozen evidence')
    if not model.strip():
        raise ValueError('Disclose the agent identity for both arms')
    if type(max_calls_per_run) is not int or max_calls_per_run < 21:
        raise ValueError('Response allowance must be an integer of at least 21 for the full Lab')
    manifest, packet, decision, incumbent_path, challenger_path = daily.reviewed_episode(root, directory, episode)
    if decision['status'] != 'reviewed_candidate':
        raise ValueError('No-change does not create a challenger')
    adapter = daily.dataset_adapter(dataset)
    first, last = date.fromisoformat(start), date.fromisoformat(end)
    if last < first or (last-first).days > 366:
        raise ValueError('Use an ordered matchoff range of at most one year')
    calendar = adapter.calendar_for(start, (last+timedelta(days=14)).isoformat())
    if not calendar.is_session(start) or not calendar.is_session(end):
        raise ValueError('Matchoff boundaries must be exchange sessions')
    dates = [s.date().isoformat() for s in calendar.sessions_in_range(start, end)]
    if calendar.session_close(start).to_pydatetime() <= runtime.stamp(packet['matured_at']):
        raise ValueError('Matchoff must follow the teacher episode horizon')
    dates.append(calendar.next_session(end).date().isoformat())
    output.mkdir(parents=True)
    snapshots = []
    for day in dates:
        path = output/'feeds'/day
        snapshot = adapter.snapshot(Path(dataset), day, path)
        snapshots.append((path, snapshot))
    issues, truth = [], []
    basis, currency = set(), set()
    for i, (before, after) in enumerate(zip(snapshots, snapshots[1:])):
        subject_rows = feedback.dated_rows(before[0]/'artifacts/global_stock_feed.json')
        truth_rows = feedback.dated_rows(after[0]/'artifacts/global_stock_feed.json')
        targets = sorted(r['target_id'] for r in subject_rows)
        if targets != sorted(r['target_id'] for r in truth_rows):
            raise ValueError('Complete identical asset support required across an episode')
        for row in subject_rows+truth_rows:
            basis.add(row['price_basis']); currency.add(row['currency'])
        target_time = after[1].get('observation_at_utc', after[1]['issue_at_utc'])
        # The native engine accepts next_us_close or an exact timestamp. The
        # source adapter already resolved other exchanges' holidays and closes.
        issues.append({'issue_id': 'day-'+dates[i].replace('-', ''), 'feed_source': str(before[0]),
                       'time_anchor': before[1]['issue_at_utc'],
                       'target_time': target_time,
                       'horizon_id': 'next_us_close' if calendar.name == 'XNYS' else target_time,
                       'target_ids': targets, 'split': 'development'})
        truth.extend({'target_id': r['target_id'], 'date': r['observed'], 'price': r['price'],
                      'source': r['source']} for r in truth_rows)
    if len(basis) != 1 or None in basis or len(currency) != 1 or None in currency:
        raise ValueError('One explicit price basis and currency required')
    price_basis, price_currency = next(iter(basis)), next(iter(currency))
    policy = {'schema': 'zenith_forecast_feedback_policy_v1', 'policy_id': 'daily-matchoff-v1',
              'price_basis': price_basis, 'currency': price_currency, 'observation_precision': 'session_close',
              'calendar_id': calendar.name, 'calendar_version': importlib.metadata.version('exchange_calendars'),
              'relative_error_threshold': 0.05}
    daily.immutable(output/'feedback-policy.json', policy)
    daily.immutable(output/'truth.json', {'metadata': {'status': 'success', 'price_basis': price_basis, 'currency': price_currency},
                                         'data': {'rows': truth}})
    source_commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip()
    rows = []
    for name, path in [('baseline', incumbent_path), ('challenger', challenger_path)]:
        rows.append({'candidate_id': name, 'hypothesis': 'Retain incumbent' if name == 'baseline' else decision['response']['diagnosis'],
                     'change': 'none' if name == 'baseline' else json.dumps(decision['response']['change'], sort_keys=True),
                     'source_commit': source_commit, 'model': model, 'actual_model': model,
                     'execution_kind': 'agent', 'provider': 'agent', 'graph_variant': None,
                     'reasoning_policy': str(path), 'context_profile': 'compact_feeds',
                     'prompt_sha256': packet['packet_sha256']})
    spec = {'schema': cohort.SCHEMA, 'issues': issues, 'candidates': rows,
            'feedback_policy': str(output/'feedback-policy.json'), 'truth_source': str(output/'truth.json'),
            'truth_as_of': snapshots[-1][1]['issue_at_utc'], 'max_trials': 2, 'max_calls_per_run': max_calls_per_run,
            'minimum_improvement': minimum_improvement, 'embargo_days': 0}
    daily.immutable(output/'spec.json', spec)
    cohort.freeze(output/'spec.json', output/'cohort')
    binding = {'schema': 'zenith_daily_matchoff_v1', 'daily_directory': str(directory), 'episode': episode,
               'programme_sha256': manifest['programme_sha256'], 'review_sha256': decision['review_sha256'],
               'packet_sha256': packet['packet_sha256'], 'source_commit': source_commit,
               'cohort_sha256': daily.file_hash(output/'cohort/cohort.json'),
               'incumbent': daily.read(incumbent_path), 'challenger': daily.read(challenger_path),
               'issues': len(issues), 'reasoning_responses_planned': 2*21*len(issues),
               'max_calls_per_run': max_calls_per_run,
               'response_allowance_total': 2*max_calls_per_run*len(issues),
               'comparison': 'development; no untouched or prospective assessment claim',
               'selection': 'complete common support; at least twenty issues; declared target-price error margin; separate review'}
    binding['matchoff_sha256'] = daily.digest(binding)
    daily.immutable(output/'matchoff.json', binding)
    return {'status': 'prepared', **binding, 'next': ['python', '-m', 'research', 'cohort-next', '--study', str(output/'cohort')]}


def retain(root, output, reviewer):
    output = Path(output).resolve()
    if not isinstance(reviewer, str) or not reviewer.strip():
        raise ValueError('Disclose reviewer identity')
    with runtime.run_lock(output/'retention-lock'):
        binding = daily.read(output/'matchoff.json')
        if binding['matchoff_sha256'] != daily.digest({k: v for k,v in binding.items() if k != 'matchoff_sha256'}):
            raise ValueError('Matchoff identity changed')
        _, packet, decision, incumbent_path, challenger_path = daily.reviewed_episode(root, binding['daily_directory'], binding['episode'])
        if packet['packet_sha256'] != binding['packet_sha256'] or decision['review_sha256'] != binding['review_sha256']:
            raise ValueError('Teacher review changed')
        if daily.file_hash(output/'cohort/cohort.json') != binding['cohort_sha256']:
            raise ValueError('Frozen matchoff changed')
        if binding['incumbent'] != daily.read(incumbent_path) or binding['challenger'] != daily.read(challenger_path):
            raise ValueError('Matchoff policies differ from their reviewed sources')
        frozen = daily.read(output/'cohort/cohort.json')
        for row in frozen['candidates']:
            key = 'incumbent' if row['candidate_id'] == 'baseline' else 'challenger'
            if row['reasoning_policy_payload'] != binding[key]:
                raise ValueError('Scored policy differs from bound contender')
        result = cohort.evaluate(output/'cohort')
        if result['state'] != 'complete' or result['issue_count'] < 20:
            raise ValueError('Complete matched comparison of at least twenty issues required; incumbent retained')
        selected = 'challenger' if result['decisions']['challenger'] == 'candidate_proposal' else 'incumbent'
        receipt = {'schema': 'zenith_daily_retention_v1', 'matchoff_sha256': binding['matchoff_sha256'],
                   'comparison_sha256': daily.digest(result), 'selected': selected, 'reviewer': reviewer,
                   'policy_sha256': binding[selected]['policy_sha256'],
                   'matchoff_directory': str(output), 'evidence_through': frozen['truth_as_of'],
                   'claim': 'Reviewed development selection only; no live promotion or significance claim.'}
        daily.immutable(output/'retained-policy.json', binding[selected])
        receipt['policy_file_sha256'] = daily.file_hash(output/'retained-policy.json')
        receipt['receipt_sha256'] = daily.digest(receipt)
        daily.immutable(output/'retention.json', receipt)
        return {**receipt, 'policy_path': str(output/'retained-policy.json'),
                'instruction': 'Initialize the next generation using --retention retention.json; its first issue must follow the comparison evidence cutoff.'}


def retained_policy(receipt_path):
    """Load recorded selection evidence without silently replaying an old evaluator."""
    receipt_path = Path(receipt_path).resolve()
    receipt = daily.read(receipt_path)
    if receipt.get('schema') != 'zenith_daily_retention_v1' or receipt.get('receipt_sha256') != daily.digest({k:v for k,v in receipt.items() if k != 'receipt_sha256'}):
        raise ValueError('Retention receipt identity changed')
    output = Path(receipt['matchoff_directory'])
    if receipt_path != (output/'retention.json').resolve():
        raise ValueError('Use the original retention receipt with its comparison evidence')
    binding = daily.read(output/'matchoff.json')
    if binding['matchoff_sha256'] != receipt['matchoff_sha256'] or binding['matchoff_sha256'] != daily.digest({k:v for k,v in binding.items() if k != 'matchoff_sha256'}):
        raise ValueError('Retention matchoff binding changed')
    frozen = daily.read(output/'cohort/cohort.json')
    if daily.file_hash(output/'cohort/cohort.json') != binding['cohort_sha256'] or frozen['truth_as_of'] != receipt['evidence_through']:
        raise ValueError('Retention evidence cutoff changed')
    comparison = daily.read(output/'cohort/development-comparison.json')
    if daily.digest(comparison) != receipt['comparison_sha256'] or comparison['state'] != 'complete' or comparison['issue_count'] < 20:
        raise ValueError('Retention comparison changed or incomplete')
    selected = 'challenger' if comparison['decisions']['challenger'] == 'candidate_proposal' else 'incumbent'
    policy = daily.read(output/'retained-policy.json')
    if (receipt['selected'] != selected or policy != binding[selected]
        or policy['policy_sha256'] != receipt['policy_sha256']
        or daily.file_hash(output/'retained-policy.json') != receipt['policy_file_sha256']):
        raise ValueError('Retained policy changed')
    return policy, receipt['evidence_through'], receipt
