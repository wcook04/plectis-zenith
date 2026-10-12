#!/usr/bin/env python3
"""Verify a completed native rich-input pilot; export hashes, not source text."""
import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from zenith import daily, runtime
from benchmarks import traderharness_daily as adapter


def bound(path):
    path = Path(path)
    return {'path': str(path.relative_to(ROOT)), 'sha256': daily.file_hash(path)}


def verify_coverage(dataset, receipt):
    manifest = adapter.verify(dataset)
    index = adapter.indexed(str(dataset), manifest['manifest_sha256'])
    sessions, valid = index['sessions'], []
    for number, day in enumerate(sessions):
        if not '2023-02-01' <= day <= '2025-12-31':
            continue
        dates = sessions[number-20:number+1]
        if len(dates) == 21 and all(adapter.source.valid_bar(series.get(d))
                for series in [*index['prices'].values(), index['market']] for d in dates):
            valid.append(day)
    counts = {}
    for year in ('2023', '2024', '2025'):
        dates = [d for d in valid if d.startswith(year)]
        count = sum(sessions[sessions.index(d)+1] in valid for d in dates)
        counts[year] = {'usable_snapshot_sessions': len(dates), 'first': dates[0], 'last': dates[-1],
                        'forecast_dates_with_next_source_close': count}
    if (receipt['counts'] != counts or receipt['source_manifest_sha256'] != manifest['manifest_sha256']
            or receipt['symbols'] != adapter.source.SYMBOLS):
        raise ValueError('Coverage differs from pinned original source bars')


def export(work, dataset):
    programme = work/'programme'
    manifest, packet, decision, incumbent, candidate = daily.reviewed_episode(ROOT, programme, 0)
    if len(manifest['snapshots']) != 2:
        raise ValueError('This receipt requires one complete reviewed episode')
    lab, oracle = daily.run_ids(manifest, 0)
    runs = {}
    for run, expected in [(lab, 28), (oracle, 31)]:
        path = runtime.runs_root(ROOT)/run
        status = runtime.status(ROOT, run)
        if status['status'] != 'completed' or status['completed_count'] != expected or status['scope_count'] != expected:
            raise ValueError('Incomplete original native mission')
        receipts = [daily.read(p) for p in (path/'handoff/responses').glob('*.json')]
        validations = [daily.read(p) for p in (path/'handoff/validation').glob('*.json')]
        runs[run] = {'manifest': bound(path/'zenith_run.json'), 'status': status['status'],
                     'completed_nodes': expected, 'scope_nodes': expected,
                     'accepted_response_nodes': sorted(v['node_id'] for v in validations if v['engine_accepted']),
                     'disclosed_models': sorted({v['actual_model'] for v in receipts}),
                     'response_receipts': [bound(p) for p in sorted((path/'handoff/responses').glob('*.json'))],
                     'rejected_responses': [bound(p) for p in sorted((path/'handoff/rejected_responses').rglob('*')) if p.is_file()],
                     'artifacts': {p.stem: bound(p) for p in sorted((path/'artifacts').glob('*.json'))}}
    lab_cp2 = daily.read(packet['sources']['lab_director'])['data']
    reconciliation = daily.read(packet['sources']['prediction_reconciliation'])['data']
    if lab_cp2['decision_status'] != 'ABSTAIN' or lab_cp2['predictions_t'] or reconciliation['status'] != 'ABSTAINED':
        raise ValueError('Expected preserved no-call, not a measured forecasting success')
    snapshots = []
    for snapshot in manifest['snapshots']:
        feed = Path(snapshot['path'])
        issue = daily.read(feed/'issue-packet.json')
        news = daily.read(feed/'artifacts/global_news_feed.json')['data']['items']
        if any(runtime.stamp(row['available_at']) > runtime.stamp(issue['observation_at_utc']) for row in news):
            raise ValueError('Post-close text crossed the observation boundary')
        snapshots.append({'issue': bound(feed/'issue-packet.json'), 'date': issue['issue_date'],
                          'issue_at': issue['issue_at_utc'], 'observation_at': issue['observation_at_utc'],
                          'symbols': issue['symbols'], 'text_items': len(news),
                          'headline_items': sum(r['kind'] == 'news' for r in news),
                          'announcement_titles': sum(r['kind'] == 'filing' for r in news)})
    coverage = daily.read(work/'coverage.json')
    verify_coverage(dataset, coverage)
    source_hash = daily.read(Path(manifest['snapshots'][0]['path'])/'issue-packet.json')['source_manifest_sha256']
    if coverage['source_manifest_sha256'] != source_hash:
        raise ValueError('Coverage belongs to another source policy')
    return {'schema': 'zenith_traderharness_native_pilot_v1',
            'programme': bound(programme/'daily.json'), 'programme_sha256': manifest['programme_sha256'],
            'source_manifest_sha256': source_hash, 'snapshots': snapshots, 'runs': runs,
            'runtime_implementation_sha256': daily.digest(manifest['native_implementation']),
            'substrate_sha256': daily.digest(manifest['substrate_hashes']),
            'coverage': coverage, 'coverage_receipt': bound(work/'coverage.json'),
            'decision_status': lab_cp2['decision_status'], 'forecast_count': 0,
            'common_observed_stocks': reconciliation['comparison_summary']['common_ticker_count'],
            'hit_rate': reconciliation['grading_summary']['hit_rate'],
            'review': {**bound(programme/'episodes/0/review.json'), 'status': decision['status'],
                       'review_sha256': decision['review_sha256'], 'reviewer': decision['reviewer'],
                       'diagnosis': decision['response']['diagnosis'], 'uncertainty': decision['response']['uncertainty'],
                       'test': decision['response']['test'], 'change': decision['response']['change']},
            'incumbent_policy': bound(incumbent), 'candidate_policy': bound(candidate),
            'execution_disclosure': {'reasoner': 'primary agent via native import',
                                     'new_paid_provider_calls': 0, 'prior_run_response_reuses': 0,
                                     'generation_retention_performed': False,
                                     'candidate_later_evaluation_completed': False},
            'claim': 'One full rich-input Lab/Oracle episode and reviewed procedure candidate; no forecast coverage or demonstrated learning advantage.',
            'limitations': ['Exposed historical training date; not a holdout or independent model evaluation.',
                            'Candidate codifies behavior already partly present; incremental benefit is unknown.',
                            'Source identity/publication clocks do not establish historical revision vintages.',
                            'Local source and response hashes are audit locators, not public redistribution of raw data.',
                            'Separate external issuer verification did not enter the frozen native evidence.']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work-dir', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--dataset', type=Path, default=ROOT/'work/datasets/traderharness-daily')
    args = parser.parse_args()
    result = export(args.work_dir.resolve(), args.dataset.resolve())
    daily.write_json(args.output, result)
    print(result['claim'])
