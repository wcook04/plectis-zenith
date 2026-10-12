#!/usr/bin/env python3
"""Export an already reviewed no-call episode; does not execute or judge one."""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from zenith import daily, runtime


def bound(path):
    return {'path': str(path.relative_to(ROOT)), 'sha256': daily.file_hash(path)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work-dir', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--predecessor', type=Path, action='append', default=[])
    args = parser.parse_args()
    work = args.work_dir.resolve()
    manifest, packet, decision, _, _ = daily.reviewed_episode(ROOT, work, 0)
    lab_id, oracle_id = daily.run_ids(manifest, 0)
    artifacts = {key: daily.read(path)['data'] for key, path in packet['sources'].items()}
    if (artifacts['lab_director'].get('decision_status') != 'ABSTAIN'
            or artifacts['prediction_reconciliation']['status'] != 'ABSTAINED'
            or decision['status'] != 'reviewed_no_change'):
        raise ValueError('Expected an actual reviewed abstention, not a forecast or candidate')
    runs = {}
    for run_id in (lab_id, oracle_id):
        path = runtime.runs_root(ROOT)/run_id
        status = runtime.status(ROOT, run_id)
        validations = [daily.read(p) for p in (path/'handoff/validation').glob('*.json')]
        responses = [daily.read(p) for p in (path/'handoff/responses').glob('*.json')]
        runs[run_id] = {'manifest': bound(path/'zenith_run.json'),
            'completed_nodes': status['completed_count'], 'scope_nodes': status['scope_count'],
            'status': status['status'], 'accepted_response_nodes': sorted({v['node_id'] for v in validations if v['engine_accepted']}),
            'disclosed_response_models': sorted({r['actual_model'] for r in responses}),
            'artifacts': {p.stem: bound(p) for p in sorted((path/'artifacts').glob('*.json'))}}
    reuse = daily.read(work/'response-reuse.json')
    # Bind exact reused answers without publishing original upstream summaries.
    for row in reuse['responses']:
        if daily.file_hash(ROOT/row['source']) != row['sha256']:
            raise ValueError('Reused response source changed')
    predecessors = []
    for directory in args.predecessor:
        source = directory.resolve()/'daily.json'
        prior = daily.read(source)
        if prior['programme_sha256'] != daily.digest({k: v for k, v in prior.items() if k != 'programme_sha256'}):
            raise ValueError('Predecessor programme identity changed')
        predecessors.append({**bound(source), 'programme_sha256': prior['programme_sha256'],
            'disposition': 'Preserved at its original source identity; superseded for this contract pilot.'})
    result = {'schema': 'zenith_abstention_pilot_v1', 'predecessors': predecessors,
        'programme': bound(work/'daily.json'), 'programme_sha256': manifest['programme_sha256'],
        'issue_at': manifest['snapshots'][0]['anchor'], 'matured_at': packet['matured_at'],
        'runtime_implementation_sha256': daily.digest(manifest['native_implementation']),
        'authored_substrate_sha256': daily.digest(manifest['substrate_hashes']),
        'runs': runs, 'response_reuse': {**bound(work/'response-reuse.json'),
            'count': len(reuse['responses']), 'purpose': reuse['purpose']},
        'evolve_review': {**bound(work/'episodes/0/review.json'),
            'status': decision['status'], 'review_sha256': decision['review_sha256'],
            'policy_sha256': decision['policy_sha256']},
        'decision': {'lab': 'ABSTAIN', 'oracle': artifacts['ideal_cp2']['decision_status'],
            'critique': artifacts['cp2_critique']['finding_status'],
            'prediction_rows': len(artifacts['prediction_reconciliation']['rows']),
            'grading': artifacts['prediction_reconciliation']['grading_summary'],
            'observed_moves': artifacts['prediction_reconciliation']['top_movers']},
        'claim_boundaries': [
            'Exposed primary-agent development case and contract replay, not independent model or untouched performance evidence.',
            'Reused responses are exact earlier answers, not new reasoning samples.',
            'No forecast score, causal proof, optimal-abstention claim, learned advantage or new paid provider call.',
            'Provider response receipts disclose agent identity; historical artifact metadata.model may retain a node platform label.',
            'Local source hashes establish custody, not public availability or independent reproduction of original transcripts.']}
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True)+'\n')
    print(json.dumps({'output': str(args.output), 'nodes': [r['completed_nodes'] for r in runs.values()],
                      'response_reuse_count': len(reuse['responses']), 'evolve': decision['status']}))


if __name__ == '__main__':
    main()
