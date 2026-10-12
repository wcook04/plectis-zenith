"""A small, source-bound execution-repair example over original feed snapshots.

This reuses the native prompt assembler, provider budget and schema validator.
A node replay is a controlled component intervention, never a completed Lab.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path

from system.lib.reasoning_policy import policy_sha256, validate_reasoning_policy
from system.lib.types import StepStatus
from zenith import runtime
from zenith.providers import now, text_digest, write_json

NODE = "lab_cross_corr_v1"


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def checked_change(baseline, candidate, graph):
    """Exactly one supplemental instruction changes; edges/data/schema stay fixed."""
    validate_reasoning_policy(baseline, graph)
    validate_reasoning_policy(candidate, graph)
    if set(baseline['nodes']) != set(candidate['nodes']):
        raise ValueError('candidate must preserve the baseline policy node set')
    changed = [n for n in baseline['nodes'] if baseline['nodes'][n] != candidate['nodes'][n]]
    if changed != [NODE]:
        raise ValueError('candidate must change only lab_cross_corr_v1')
    before, after = deepcopy(baseline['nodes'][NODE]), deepcopy(candidate['nodes'][NODE])
    before.pop('skill_addon', None)
    after.pop('skill_addon', None)
    if before != after or not candidate['nodes'][NODE].get('skill_addon'):
        raise ValueError('only the supplemental instruction may change')


def observe(run_dir, node_id=NODE):
    run_dir = Path(run_dir)
    artifact = run_dir / 'artifacts' / (node_id + '.json')
    envelope = read(artifact) if artifact.exists() else {}
    calls = [read(p) for p in sorted((run_dir / 'handoff/api_calls/openrouter_budgeted').glob('*.json'))]
    calls = [c for c in calls if c.get('node_id') == node_id]
    completions = []
    for call in calls:
        response = call.get('provider_response') or {}
        completions.append({
            'call_id': call.get('call_id'), 'prompt_sha256': call.get('prompt_sha256'),
            'response_sha256': call.get('response_sha256'), 'cost_usd': call.get('cost'),
            'finish_reasons': [c.get('finish_reason') for c in response.get('choices', [])],
            'completion_tokens': (response.get('usage') or {}).get('completion_tokens'),
        })
    status = envelope.get('status', 'not_reached')
    capped = any('length' in c['finish_reasons'] for c in completions)
    failure = ('output_capacity' if capped and status == 'failure' else
               'other_execution_failure' if status == 'failure' else
               'none' if status in ('success', 'loaded') else 'not_reached')
    shape = None
    data = envelope.get('data')
    fields = ('swarms', 'bifurcations', 'orphans', 'confidence_asymmetries')
    if status in ('success', 'loaded') and isinstance(data, dict) and all(isinstance(data.get(k), list) for k in fields):
        records = [item for key in fields for item in data[key]]
        shape = {'record_counts': {k: len(data[k]) for k in fields},
                 'max_subjects': max((len(item.get('subjects', [])) for item in records), default=0),
                 'max_summary_words': max((len(str(item.get('summary', '')).split()) for item in records), default=0)}
        shape['requested_numeric_bounds_met'] = (all(n <= 3 for n in shape['record_counts'].values())
                                               and shape['max_subjects'] <= 4 and shape['max_summary_words'] <= 24)
    return {'run_id': run_dir.name, 'node_id': node_id, 'status': status,
            'native_contract_pass': status in ('success', 'loaded'),
            'failure_mode': failure, 'artifact_sha256': sha(artifact) if artifact.exists() else None,
            'error': envelope.get('metadata', {}).get('error'), 'calls': completions, 'output_shape': shape}


def verify_baseline(plan, episode, run_dir):
    """Reject a mixed-graph/window comparison before reporting any counts."""
    spec = read(Path(run_dir) / 'zenith_run.json')
    expected_hashes = {n['id']: n['node_hash'] for n in plan['graph']['nodes']}
    if spec['node_hashes'] != expected_hashes or spec['implementation_hashes'] != plan['implementation_hashes']:
        raise ValueError('baseline graph or implementation differs from frozen plan')
    for key in ('model', 'provider_slug', 'context_profile'):
        if spec.get(key) != plan[key]:
            raise ValueError('baseline differs from frozen ' + key)
    for key in ('time_anchor', 'horizon'):
        if runtime.stamp(spec[key]) != runtime.stamp(episode[key]):
            raise ValueError('baseline differs from frozen ' + key)
    if spec['source_hashes'] != episode['source_hashes']:
        raise ValueError('baseline feed source differs from frozen snapshot')
    if spec['policy_source_sha256'] != plan['baseline_policy_sha256']:
        raise ValueError('baseline policy differs from frozen policy')
    return spec


def verify_candidate(subject_run, candidate_run, frozen_candidate_sha256):
    subject_run, candidate_run = Path(subject_run), Path(candidate_run)
    spec = read(subject_run / 'zenith_run.json')
    receipt = read(candidate_run / 'node_replay.json')
    if receipt.get('schema') != 'zenith_controlled_node_replay_v1' or receipt.get('full_graph_run') is not False:
        raise ValueError('later candidate must be an explicitly labelled component replay')
    if receipt['subject_manifest_sha256'] != sha(subject_run / 'zenith_run.json'):
        raise ValueError('candidate subject manifest differs')
    if receipt['candidate_file_sha256'] != frozen_candidate_sha256:
        raise ValueError('candidate differs from the one frozen intervention')
    if receipt['implementation_hashes'] != spec['implementation_hashes']:
        raise ValueError('candidate implementation changed')
    for key in ('model', 'provider_slug'):
        if receipt[key] != spec[key]:
            raise ValueError('candidate provider or model changed')
    if receipt['budget']['max_output_tokens'] != spec['paid_budget']['max_output_tokens']:
        raise ValueError('candidate output allowance changed')
    graph = runtime.graph_for_manifest(runtime.DEFAULT_ROOT, spec)
    expected = {str((subject_run / 'artifacts' / (n + '.json')).resolve()):
                sha(subject_run / 'artifacts' / (n + '.json')) for n in graph[NODE].dependencies}
    if receipt['input_artifact_sha256'] != expected:
        raise ValueError('candidate did not retain the exact upstream artifacts')
    checked_change(spec['reasoning_policy'], receipt['candidate_policy'], graph)


def replay(root, *, subject_run, candidate_path, run_id, budget, frozen_at=None, reservation_cap=None):
    """One paid native node execution with byte-identical upstream artifacts.

    No upstream responses are regenerated or relabelled as candidate outputs.
    The distinct node_replay.json receipt prevents confusion with a native DAG run.
    """
    root, subject_run = Path(root).resolve(), Path(subject_run).resolve()
    baseline = read(subject_run / 'zenith_run.json')
    runtime._check_frozen_graph(root, baseline)
    if baseline['mission'] != 'lab' or baseline.get('context_profile') != 'compact_feeds':
        raise ValueError('example requires an original-feed compact_feeds Lab subject')
    if baseline['provider'] != 'openrouter_budgeted' or budget['max_output_tokens'] != baseline['paid_budget']['max_output_tokens']:
        raise ValueError('candidate must preserve provider and output allowance')
    graph = runtime.graph_for_manifest(root, baseline)
    candidate = read(candidate_path)
    checked_change(baseline['reasoning_policy'], candidate, graph)
    inputs, sources = {}, {}
    for dependency in graph[NODE].dependencies:
        source = subject_run / 'artifacts' / (dependency + '.json')
        envelope = read(source)
        if envelope.get('status') not in ('success', 'loaded'):
            raise ValueError('all original upstream dependencies must have succeeded')
        inputs[dependency] = envelope
        sources[str(source)] = sha(source)
    run_dir = runtime.runs_root(root) / runtime.safe_run_id(run_id)
    if run_dir.exists():
        raise ValueError('node replay already exists; never overwrite an attempt')
    spec = {**baseline, 'run_id': run_id, 'reasoning_policy': candidate,
            'provider': 'openrouter_budgeted', 'paid_budget': budget}
    receipt = {
        'schema': 'zenith_controlled_node_replay_v1', 'created_at': now(),
        'candidate_frozen_at': frozen_at, 'subject_run': str(subject_run),
        'subject_manifest_sha256': sha(subject_run / 'zenith_run.json'),
        'candidate_policy': candidate, 'candidate_file_sha256': sha(candidate_path),
        'input_artifact_sha256': sources, 'implementation_hashes': runtime.implementation_hashes(),
        'node_hash': baseline['node_hashes'][NODE], 'node_id': NODE,
        'model': baseline['model'], 'provider_slug': baseline.get('provider_slug'),
        'budget': budget, 'full_graph_run': False, 'new_forecast': False,
        'interpretation': 'conditional intervention on frozen upstream outputs; no claim about downstream or forecasting benefit',
    }
    with runtime.run_lock(run_dir):
        engine = runtime._engine(root, run_dir, spec, resume=False)
        engine._universe = graph
        write_json(run_dir / 'node_replay.json', receipt)
        try:
            config = engine._merge_runtime_config(graph[NODE])
            prompt, _ = engine.prepare_reasoning_prompt(graph[NODE], inputs, config)
            write_json(run_dir / 'replay_prompt.json', {'prompt': prompt, 'prompt_sha256': text_digest(prompt)})
            if reservation_cap is not None:
                from decimal import Decimal
                from zenith.budgeted import INPUT_OVERHEAD_TOKENS, verified_model
                _, prices, _ = verified_model(baseline['model'])
                estimate = (prices['prompt'] * (len(prompt.encode('utf-8')) + INPUT_OVERHEAD_TOKENS)
                            + prices['completion'] * budget['max_output_tokens']
                            + prices.get('request', Decimal(0)))
                write_json(run_dir / 'reservation_preflight.json', {
                    'estimated_reservation_usd': str(estimate), 'cap_usd': str(reservation_cap),
                    'catalogue_prices': {k: str(v) for k, v in prices.items()}})
                if estimate > Decimal(str(reservation_cap)):
                    raise ValueError('node reservation preflight exceeds allocated remainder')
            metadata, data = engine._exec_reasoning(graph[NODE], inputs, config)
            engine._write_artifact(graph[NODE], StepStatus.SUCCESS, metadata, data)
        except Exception as exc:
            metadata = {**getattr(exc, 'artifact_metadata', {}), 'error': str(exc)}
            engine._write_artifact(graph[NODE], StepStatus.FAILURE, metadata, getattr(exc, 'artifact_data', None))
        finally:
            engine.shutdown()
    if any(sha(Path(path)) != digest for path, digest in sources.items()):
        raise ValueError('original upstream artifacts changed during replay')
    result = observe(run_dir)
    write_json(run_dir / 'replay_result.json', result)
    return result


def aggregate(episodes, widths=(1, 2, 3)):
    """Overlapping windows describe sensitivity, not additional replications."""
    ids = [e['id'] for e in episodes]
    if len(ids) != len(set(ids)):
        raise ValueError('duplicate episode identity')
    groups = {}
    for e in episodes:
        mode = e['baseline']['failure_mode']
        if mode not in ('none', 'not_reached'):
            groups.setdefault(mode, []).append(e['id'])
    windows = []
    for width in sorted(set(widths)):
        if isinstance(width, bool) or not isinstance(width, int) or width < 1:
            raise ValueError('positive integer window widths required')
        for start in range(len(episodes) - width + 1):
            rows = episodes[start:start + width]
            windows.append({'width': width, 'episode_ids': [r['id'] for r in rows],
                            'failure_modes': sorted({r['baseline']['failure_mode'] for r in rows})})
    later = [e for e in episodes if e['split'] == 'later' and 'candidate' in e]
    return {'episodes': episodes, 'failure_modes': groups, 'windows': windows,
            'paired_later_episodes': len(later),
            'later_baseline_passes': sum(e['baseline']['native_contract_pass'] for e in later),
            'later_candidate_passes': sum(e['candidate']['native_contract_pass'] for e in later),
            'later_candidate_numeric_bounds_met': sum(bool((e['candidate'].get('output_shape') or {}).get('requested_numeric_bounds_met')) for e in later),
            'interpretation': 'descriptive overlapping windows; count unique episodes, not windows, as repetitions',
            'promotion_allowed': False, 'forecast_improvement': None}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--candidate', type=Path)
    parser.add_argument('--subject-run', type=Path)
    parser.add_argument('--run-id')
    parser.add_argument('--env-file', type=Path)
    args = parser.parse_args(argv)
    plan = read(args.plan)
    if args.candidate:
        if not args.subject_run or not args.run_id or not args.env_file:
            parser.error('paid replay requires --subject-run, --run-id and --env-file')
        from system.lib.openrouter_free_runtime import load_env_file
        load_env_file(args.env_file)
        result = replay(runtime.DEFAULT_ROOT, subject_run=args.subject_run,
                        candidate_path=args.candidate, run_id=args.run_id,
                        budget=plan['budget'], frozen_at=plan.get('candidate_frozen_at'))
    else:
        episodes = []
        for e in plan['episodes']:
            verify_baseline(plan, e, runtime.runs_root(runtime.DEFAULT_ROOT) / e['run_id'])
            row = {k: e[k] for k in ('id', 'split', 'source_name', 'time_anchor', 'horizon')}
            row['baseline'] = observe(runtime.runs_root(runtime.DEFAULT_ROOT) / e['run_id'])
            if e.get('candidate_run_id'):
                verify_candidate(runtime.runs_root(runtime.DEFAULT_ROOT) / e['run_id'],
                                 runtime.runs_root(runtime.DEFAULT_ROOT) / e['candidate_run_id'],
                                 plan['candidate_sha256'])
                row['candidate'] = observe(runtime.runs_root(runtime.DEFAULT_ROOT) / e['candidate_run_id'])
            episodes.append(row)
        result = aggregate(episodes, plan['widths'])
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
