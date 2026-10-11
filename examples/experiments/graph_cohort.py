"""Create twenty synthetic, complete graph-contract fixtures and compare CP2.

Run as `python -m examples.experiments.graph_cohort --destination /tmp/cohort-demo`.
No model or graph engine executes here. The outputs exercise the consumer only.
"""
import argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path

from feedback.demo import fixture_policy, fixture_run
from research import cohort
from research.engine import read_json, write_json
from zenith import runtime


def build(destination):
    destination = Path(destination).resolve()
    if destination.exists():
        raise ValueError('demo requires a fresh destination')
    destination.mkdir(parents=True)
    first = datetime(2026, 1, 5, 20, tzinfo=timezone.utc)
    policy = fixture_policy(destination / 'feedback-policy.json')
    issues, rows = [], []
    for index in range(20):
        issue, horizon = first + timedelta(days=7 * index), first + timedelta(days=7 * index + 1)
        source = destination / 'sources' / f'issue-{index}'
        write_json(source / 'runtime_context.json', {'as_of': issue.isoformat()})
        write_json(source / 'artifacts/global_stock_feed.json', {'status': 'success', 'metadata': {
            'status': 'success', 'price_basis': 'synthetic_point_quote', 'currency': 'USD', 'synthetic_fixture': True},
            'data': {'columns': ['Ticker', 'Price', 'timestamp'], 'rows': [['XOM', 100.0, issue.isoformat()]]}})
        issues.append({'issue_id': f'issue-{index}', 'feed_source': str(source), 'time_anchor': issue.isoformat(),
            'target_time': horizon.isoformat(), 'horizon_id': '24h', 'target_ids': ['XOM'], 'split': 'development'})
        rows.append({'target_id': 'XOM', 'timestamp': horizon.isoformat(), 'price': 101.0})
    truth = destination / 'truth.json'
    write_json(truth, {'metadata': {'status': 'success', 'price_basis': 'synthetic_point_quote',
        'currency': 'USD', 'synthetic_fixture': True}, 'data': {'rows': rows}})
    candidate = {'candidate_id': 'baseline', 'hypothesis': 'synthetic baseline', 'change': 'none',
        'source_commit': 'synthetic-fixture-only', 'model': 'offline-synthetic-fixture', 'provider': 'captured',
        'execution_kind': 'captured_replay', 'graph_variant': None, 'reasoning_policy': None,
        'context_profile': 'original', 'prompt_sha256': '0' * 64}
    # Real studies point these candidate fields at distinct admitted variant/policy
    # files. This fixture changes only its invented CP2 target price.
    other = dict(candidate, candidate_id='candidate', hypothesis='synthetic target correction', change='invented CP2 target fixture')
    spec = {'schema': cohort.SCHEMA, 'issues': issues, 'candidates': [candidate, other],
        'feedback_policy': str(policy), 'truth_source': str(truth), 'truth_as_of': '2026-10-01T00:00:00+00:00',
        'max_trials': 2, 'max_calls_per_run': 100, 'minimum_improvement': .001, 'embargo_days': 1}
    spec_path, study = destination / 'spec.json', destination / 'study'
    write_json(spec_path, spec)
    cohort.freeze(spec_path, study)
    frozen = read_json(study / 'cohort.json')
    for index, issue in enumerate(frozen['issues']):
        for candidate in frozen['candidates']:
            name = candidate['candidate_id']
            run = destination / 'synthetic-runs' / f'{name}-{index}'
            fixture_run(run, datetime.fromisoformat(issue['time_anchor']), datetime.fromisoformat(issue['target_time']),
                        target=110.0 if name == 'baseline' else 101.0)
            source = study / issue['feed_source']
            manifest = read_json(run / 'zenith_run.json')
            manifest.update(schema='zenith_execution_manifest_v1', target='lab_director', model=candidate['model'],
                feed_source=str(source), source_hashes=runtime._source_hashes([source]), context_profile='original',
                implementation_hashes=runtime.implementation_hashes())
            write_json(run / 'zenith_run.json', manifest)
            for node in candidate['scope']:
                if node != 'lab_director':
                    write_json(run / 'artifacts' / f'{node}.json', {'status': 'success', 'data': {}})
            (run / 'artifacts/global_stock_feed.json').write_bytes((source / 'artifacts/global_stock_feed.json').read_bytes())
            receipt = read_json(run / 'handoff/receipts/fixture.json')
            for node in candidate['reasoner_scope']:
                if node != 'lab_director':
                    write_json(run / 'handoff/receipts' / f'{node}.json', dict(receipt, node_id=node))
            result = cohort.attach(study, candidate_id=name, issue_id=issue['issue_id'], run=run)
            if result['state'] != 'complete':
                raise ValueError(result)
    return cohort.evaluate(study)


if __name__ == '__main__':
    import json
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--destination', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.destination), indent=2))
