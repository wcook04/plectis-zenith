#!/usr/bin/env python3
"""Verify and summarize the two-issue empirical development pilot, without running it."""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from zenith import daily, runtime
from system.lib.empirical_forecast import calculate


def bound(path):
    return {'path': str(path.relative_to(ROOT)), 'sha256': daily.file_hash(path)}


def export(work):
    result = {'schema': 'zenith_empirical_pilot_v1', 'episodes': []}
    original_rule = None
    for index in range(2):
        manifest, packet, decision, policy, successor = daily.reviewed_episode(ROOT, work, index)
        if len(manifest['snapshots']) != 3:
            raise ValueError('This report requires exactly two reviewed issues')
        lab, oracle = daily.run_ids(manifest, index)
        artifacts = {k: daily.read(p)['data'] for k, p in packet['sources'].items()}
        cp = artifacts['lab_director']
        if cp.get('forecast_basis') != 'EMPIRICAL':
            raise ValueError('Expected an empirical forecast')
        rule = cp['empirical_rule']
        original_rule = original_rule or rule
        stock = daily.read(runtime.runs_root(ROOT)/lab/'artifacts/global_stock_feed.json')['data']
        before, after = manifest['snapshots'][index:index+2]
        expected = calculate(rule, stock, before['anchor'], after['anchor'])
        unchanged = calculate(original_rule, stock, before['anchor'], after['anchor'])
        rows = []
        for row in artifacts['prediction_reconciliation']['rows']:
            target = row['target_id']
            price, observed = row['subject_snapshot_price'], row['realized_truth_price']
            predicted = row['predicted_target_price']
            if expected[target]['target_price'] != predicted:
                raise ValueError('Frozen forecast differs from source arithmetic')
            fixed = unchanged[target]['target_price']
            rows.append({'target_id': target, 'snapshot_price': price, 'realized_price': observed,
                         'native_target': predicted, 'unchanged_rule_target': fixed,
                         'native_error': (predicted-observed)/price,
                         'unchanged_error': (fixed-observed)/price,
                         'persistence_error': (price-observed)/price,
                         'direction_hit': row['directional_correct']})
        if {r['target_id'] for r in rows} != set(rule['target_ids']):
            raise ValueError('Incomplete prediction support')
        metrics = {kind: {'mean_absolute_normalized_error': sum(abs(r[kind+'_error']) for r in rows)/len(rows),
                          'mean_squared_normalized_error': sum(r[kind+'_error']**2 for r in rows)/len(rows)}
                   for kind in ('native', 'unchanged', 'persistence')}
        runs = {}
        for run in (lab, oracle):
            path = runtime.runs_root(ROOT)/run
            status = runtime.status(ROOT, run)
            responses = [daily.read(p) for p in (path/'handoff/responses').glob('*.json')]
            validations = [daily.read(p) for p in (path/'handoff/validation').glob('*.json')]
            runs[run] = {'manifest': bound(path/'zenith_run.json'), 'status': status['status'],
                'completed_nodes': status['completed_count'], 'scope_nodes': status['scope_count'],
                'accepted_response_nodes': sorted(v['node_id'] for v in validations if v['engine_accepted']),
                'disclosed_response_models': sorted({r['actual_model'] for r in responses}),
                'response_receipts': [bound(p) for p in sorted((path/'handoff/responses').glob('*.json'))],
                'rejected_response_files': [bound(p) for p in sorted((path/'handoff/rejected_responses').rglob('*')) if p.is_file()],
                'artifacts': {p.stem: bound(p) for p in sorted((path/'artifacts').glob('*.json'))}}
        result['episodes'].append({'issue_at': before['anchor'], 'matured_at': after['anchor'],
            'rule': rule, 'policy': bound(policy), 'successor_policy': bound(successor),
            'runs': runs, 'rows': rows, 'metrics': metrics,
            'review': {**bound(work/f'episodes/{index}/review.json'),
                       'review_sha256': decision['review_sha256'], 'status': decision['status'],
                       'reviewer': decision['reviewer'], 'response': decision['response']}})
    first = daily.read(work/'episodes/0/review.json')
    change = first['response']['change']
    lab, _ = daily.run_ids(manifest, 1)
    requests = [p for p in (runtime.runs_root(ROOT)/lab/'handoff/requests').glob('*.json')
                if daily.read(p)['node_id'] == change['node_id']]
    if len(requests) != 1 or change['skill_addon'] not in daily.read(requests[0])['prompt']:
        raise ValueError('Reviewed change absent from actual successor prompt')
    result.update(programme=bound(work/'daily.json'), programme_sha256=manifest['programme_sha256'],
        diagnostic_plan=bound(work/'diagnostic-plan.json'),
        runtime_implementation_sha256=daily.digest(manifest['native_implementation']),
        authored_substrate_sha256=daily.digest(manifest['substrate_hashes']),
        transition={'node_id': change['node_id'], 'skill_addon': change['skill_addon'],
                    'actual_successor_packet': bound(requests[0]), 'addon_present': True},
        execution_disclosure={'reasoner': 'primary agent via native import',
                              'new_paid_provider_calls': 0, 'declared_prior_run_response_reuses': 0,
                              'generation_retention_performed': False},
        conclusion='The reviewed shrinkage candidate lost to unchanged-rule arithmetic on its next issue; no promotion or learned advantage.',
        claim_boundaries=[
            'Two exposed historical development issues; three correlated issuers per issue, not six independent trials.',
            'The numerical operator uses prices only although the full graph also reads news; no incremental news value measured.',
            'Unchanged-rule and persistence controls are deterministic calculations, not separate native model arms.',
            'Daily no_change preserves experimental lineage; it does not select the candidate as a winner.',
            'Source hashes bind local evidence; full upstream text and agent transcripts are not publicly redistributed.',
            'Historical availability, model memory and revised prices remain unresolved. No prospective or profitability claim.'])
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work-dir', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = export(args.work_dir.resolve())
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True)+'\n')
    print(json.dumps({'output': str(args.output), 'episodes': len(result['episodes']),
                      'transition_verified': result['transition']['addon_present'],
                      'conclusion': result['conclusion']}))
