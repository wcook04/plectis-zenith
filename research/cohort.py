"""Preregister and compare complete native Lab CP2 runs; never execute live calls."""
from __future__ import annotations

from contextlib import contextmanager
import copy
import fcntl
import math
from pathlib import Path
import sys

from feedback import engine as feedback
from research.engine import digest_bytes, event_time, read_json, write_json
from system.lib.hashing import hash_node
from zenith import runtime

SCHEMA = 'zenith_graph_cohort_v1'


def hashes(directory):
    directory = Path(directory)
    return {str(p.relative_to(directory)): digest_bytes(p.read_bytes())
            for p in sorted(directory.rglob('*.json')) if p.is_file()}


def authorities():
    result = runtime.implementation_hashes()
    base = Path(__file__).resolve().parents[1]
    for folder in ('feedback', 'research'):
        result.update({str(p.relative_to(base)): digest_bytes(p.read_bytes()) for p in sorted((base / folder).glob('*.py'))})
    return result


@contextmanager
def locked(study):
    study = Path(study)
    with (study / '.cohort.lock').open('a+') as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        spec, state = read_json(study / 'cohort.json'), read_json(study / 'cohort-state.json')
        if digest_bytes((study / 'cohort.json').read_bytes()) != state['spec_hash']:
            raise ValueError('frozen cohort hash mismatch')
        if spec['authorities'] != authorities() or spec['python_version'] != sys.version:
            raise ValueError('frozen evaluator/runtime source or Python changed')
        for relative, expected in spec['frozen_hashes'].items():
            if digest_bytes((study / relative).read_bytes()) != expected:
                raise ValueError('frozen cohort input or candidate changed')
        yield spec, state
        write_json(study / 'cohort-state.json', state)


def freeze(spec_path, study):
    spec_path, study = Path(spec_path).resolve(), Path(study).resolve()
    raw = read_json(spec_path)
    required = {'schema', 'issues', 'candidates', 'feedback_policy', 'truth_source', 'truth_as_of',
                'max_trials', 'max_calls_per_run', 'minimum_improvement', 'embargo_days'}
    if set(raw) != required or raw['schema'] != SCHEMA:
        raise ValueError('cohort requires exactly the documented v1 fields')
    if study.exists():
        raise ValueError('cohort already exists')
    for key in ('max_trials', 'max_calls_per_run'):
        if type(raw[key]) is not int or raw[key] < 1:
            raise ValueError(f'{key} must be a positive integer')
    if type(raw['embargo_days']) is not int or raw['embargo_days'] < 0:
        raise ValueError('embargo_days must be nonnegative')
    if type(raw['minimum_improvement']) not in (float, int) or not math.isfinite(raw['minimum_improvement']) or raw['minimum_improvement'] < 0:
        raise ValueError('minimum_improvement must be finite and nonnegative')
    if not isinstance(raw['candidates'], list) or not 1 <= len(raw['candidates']) <= raw['max_trials']:
        raise ValueError('preregistered candidates spend the fixed trial budget')
    frozen = copy.deepcopy(raw)
    base = spec_path.parent
    root = runtime.DEFAULT_ROOT
    prepared = []
    names = set()
    identity = None
    for candidate in frozen['candidates']:
        keys = {'candidate_id', 'hypothesis', 'change', 'source_commit', 'model', 'execution_kind',
                'provider', 'graph_variant', 'reasoning_policy', 'context_profile', 'prompt_sha256'}
        if not keys <= set(candidate) or set(candidate) - keys - {'actual_model'}:
            raise ValueError('candidate provenance requires documented fields')
        for key in keys - {'graph_variant', 'reasoning_policy'}:
            if not isinstance(candidate[key], str) or not candidate[key].strip():
                raise ValueError(f'candidate {key} must be a nonempty string')
        candidate.setdefault('actual_model', candidate['model'])
        if not isinstance(candidate['actual_model'], str) or not candidate['actual_model'].strip():
            raise ValueError('expected actual_model must be a nonempty string')
        name = candidate['candidate_id']
        if name in names or not name.replace('-', '').replace('_', '').isalnum():
            raise ValueError('candidate ids must be unique safe identifiers')
        names.add(name)
        if candidate['context_profile'] not in {'original', 'compact_feeds'}:
            raise ValueError('unknown context profile')
        if len(candidate['prompt_sha256']) != 64 or any(c not in '0123456789abcdef' for c in candidate['prompt_sha256']):
            raise ValueError('candidate prompt_sha256 requires a SHA256 digest')
        current = (candidate['model'], candidate['actual_model'], candidate['execution_kind'], candidate['provider'])
        if identity is not None and current != identity:
            raise ValueError('candidates require identical declared model/provider/execution kind')
        identity = current
        for key in ('graph_variant', 'reasoning_policy'):
            if candidate[key] is not None and (not isinstance(candidate[key], str) or not candidate[key]):
                raise ValueError(f'candidate {key} must be a path string or null')
        variant = read_json(base / candidate['graph_variant']) if candidate['graph_variant'] else None
        graph = runtime.load_graph(root, variant)
        if candidate['reasoning_policy']:
            from system.lib.reasoning_policy import validate_reasoning_policy
            policy = validate_reasoning_policy(read_json(base / candidate['reasoning_policy']), graph)
        else:
            policy = None
        candidate['graph_variant_payload'], candidate['reasoning_policy_payload'] = variant, policy
        candidate['node_hashes'] = {key: hash_node(value) for key, value in graph.items()}
        candidate['scope'] = sorted(runtime.scope_for(graph, 'lab_director'))
        candidate['reasoner_scope'] = sorted(k for k in candidate['scope'] if graph[k].type.value == 'reasoning')
        for key in ('graph_variant', 'reasoning_policy'):
            if candidate[key]:
                relative = f'candidates/{name}/{key}.json'
                prepared.append((relative, (base / candidate[key]).read_bytes()))
                candidate[key] = relative
    if frozen['candidates'][0]['candidate_id'] != 'baseline':
        raise ValueError('first preregistered candidate must be baseline')
    if not isinstance(frozen['issues'], list) or not frozen['issues']:
        raise ValueError('nonempty fixed cohort required')
    issue_ids, times, weeks = set(), set(), {}
    truth_as_of = event_time(raw['truth_as_of'])
    for issue in frozen['issues']:
        if set(issue) != {'issue_id', 'feed_source', 'time_anchor', 'target_time', 'horizon_id', 'target_ids', 'split'}:
            raise ValueError('issue requires documented input, time, horizon, support and split fields')
        name = issue['issue_id']
        if not isinstance(name, str) or not name.replace('-', '').replace('_', '').isalnum() or name in issue_ids:
            raise ValueError('issue ids must be unique safe identifiers')
        issue_ids.add(name)
        for key in ('feed_source', 'time_anchor', 'target_time', 'horizon_id'):
            if not isinstance(issue[key], str) or not issue[key]:
                raise ValueError(f'issue {key} must be a nonempty string')
        start, end = event_time(issue['time_anchor']), event_time(issue['target_time'])
        if start in times or not start < end <= truth_as_of:
            raise ValueError('distinct issue times and mature declared horizons required')
        times.add(start)
        issue['time_anchor'], issue['target_time'] = start.isoformat(), end.isoformat()
        from system.core.engine import GodModeEngine
        if event_time(GodModeEngine.resolve_horizon(issue['horizon_id'], start)['target_time']) != end:
            raise ValueError('declared horizon does not resolve to the frozen target time')
        if issue['split'] not in {'development', 'holdout'}:
            raise ValueError('issue split must be development or holdout')
        week = start.isocalendar()[:2]
        if week in weeks and weeks[week] != issue['split']:
            raise ValueError('clustered calendar week cannot cross splits')
        weeks[week] = issue['split']
        targets = issue['target_ids']
        if not isinstance(targets, list) or not targets or any(not isinstance(t, str) or not t or t != t.upper() for t in targets) or len(set(targets)) != len(targets):
            raise ValueError('unique uppercase target support required')
        source = (base / issue['feed_source']).resolve()
        runtime.forward_preflight(root, source, start)
        refs = runtime._source_hashes([source])[str(source)]
        if not any(p.startswith('artifacts/') for p in refs):
            raise ValueError('recorded feed artifacts required')
        for relative in refs:
            prepared.append((f'inputs/{name}/{relative}', (source / relative).read_bytes()))
        issue['feed_source'] = f'inputs/{name}'
    dev = [event_time(i['target_time']) for i in frozen['issues'] if i['split'] == 'development']
    hold = [event_time(i['time_anchor']) for i in frozen['issues'] if i['split'] == 'holdout']
    from datetime import timedelta
    if not dev or (hold and max(dev) + timedelta(days=raw['embargo_days']) > min(hold)):
        raise ValueError('development horizons plus embargo must precede holdout')
    # Native feedback freezes the exact price basis/calendar definition.
    feedback.policy_from(base / raw['feedback_policy'])
    for key in ('feedback_policy', 'truth_source'):
        relative = f'inputs/{key}.json'
        prepared.append((relative, (base / raw[key]).read_bytes()))
        frozen[key] = relative
    frozen.update(authorities=authorities(), python_version=sys.version,
                  frozen_hashes={p: digest_bytes(data) for p, data in prepared})
    study.mkdir(parents=True)
    for relative, data in prepared:
        path = study / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    write_json(study / 'cohort.json', frozen)
    write_json(study / 'cohort-state.json', {'spec_hash': digest_bytes((study / 'cohort.json').read_bytes()),
        'attachments': {}, 'attempts': 0, 'final': None})
    return {'schema': SCHEMA, 'state': 'frozen', 'candidate_attempts_spent': len(raw['candidates']),
            'issue_count': len(issue_ids), 'frozen_manifest': str(study / 'cohort.json')}


def select(spec, candidate_id, issue_id):
    candidate = next((c for c in spec['candidates'] if c['candidate_id'] == candidate_id), None)
    issue = next((i for i in spec['issues'] if i['issue_id'] == issue_id), None)
    if candidate is None or issue is None:
        raise ValueError('candidate and issue must be preregistered')
    return candidate, issue


def validate_run(study, spec, candidate, issue, run):
    manifest = read_json(run / 'zenith_run.json')
    required = {'schema': 'zenith_execution_manifest_v1', 'mission': 'lab',
                'time_anchor': issue['time_anchor'], 'horizon': issue['target_time'],
                'provider': candidate['provider'], 'model': candidate['model'],
                'context_profile': candidate['context_profile']}
    if any(manifest.get(k) != v for k, v in required.items()) or manifest.get('run_id') != run.name or manifest.get('target') not in {'lab_director', 'lab_integrity'}:
        raise ValueError('native manifest identity/model/input time/horizon differs from cohort')
    expected_scope = candidate['scope']
    if sorted(manifest.get('scope', [])) != expected_scope or manifest.get('node_hashes') != {k: candidate['node_hashes'][k] for k in expected_scope}:
        raise ValueError('native full CP2 ancestor graph scope/hash differs')
    if manifest.get('graph_variant') != candidate['graph_variant_payload'] or manifest.get('reasoning_policy') != candidate['reasoning_policy_payload']:
        raise ValueError('native graph or policy candidate differs')
    frozen_source = (Path(study) / issue['feed_source']).resolve()
    source = Path(manifest.get('feed_source') or '').resolve()
    observed = runtime._source_hashes([source])
    expected = runtime._source_hashes([frozen_source])[str(frozen_source)]
    recorded = manifest.get('source_hashes')
    normalized = {str(Path(path).resolve()): values for path, values in recorded.items()} if isinstance(recorded, dict) else None
    if normalized != observed or len(recorded) != len(observed) or observed[str(source)] != expected:
        raise ValueError('native frozen feed input snapshot differs')
    if manifest.get('implementation_hashes') != runtime.implementation_hashes():
        raise ValueError('native executing implementation hash differs')
    complete = True
    for node in expected_scope:
        path = run / 'artifacts' / f'{node}.json'
        if not path.is_file():
            complete = False
            continue
        envelope = read_json(path)
        if envelope.get('status') == 'failure' and not str(envelope.get('metadata', {}).get('error', '')).startswith('Agent response pending:'):
            raise ValueError(f'native node failed: {node}')
        if envelope.get('status') not in {'success', 'loaded'}:
            complete = False
    if not complete:
        return manifest, False, None
    identity = feedback.model_identity(run)
    if identity.get('actual_model') != candidate['actual_model'] or identity.get('execution_kind') != candidate['execution_kind'] or identity.get('provider') != candidate['provider']:
        raise ValueError('observed CP2 model differs from preregistered comparable model')
    calls = list((run / 'handoff/api_calls').rglob('*.json'))
    receipts = [read_json(p) for p in (run / 'handoff/receipts').glob('*.json')]
    supplied = [r for r in receipts if r.get('schema') == 'zenith_provider_attempt_v1' and r.get('status') in {'response_supplied', 'replayed'}]
    if any(r.get('run_id') != run.name or r.get('actual_model') != candidate['actual_model'] or r.get('execution_kind') != candidate['execution_kind'] or r.get('provider') != candidate['provider'] for r in supplied):
        raise ValueError('node provider model lineage is not comparable')
    if not set(candidate['reasoner_scope']) <= {r.get('node_id') for r in supplied}:
        raise ValueError('complete native reasoning node provider receipts required')
    call_count = len(calls) if calls else len(supplied)
    if not supplied or call_count > spec['max_calls_per_run']:
        raise ValueError('missing provider receipts or audited call budget exceeded')
    return manifest, True, call_count


def attach(study, *, candidate_id, issue_id, run):
    study, run = Path(study).resolve(), Path(run).resolve()
    with locked(study) as (spec, state):
        state['attempts'] += 1
        number = state['attempts']
        receipt = {'schema': 'zenith_cohort_import_v1', 'attempt': number, 'candidate_id': candidate_id,
                   'issue_id': issue_id, 'run': str(run)}
        try:
            if state['final'] is not None:
                raise ValueError('heldout final seal consumed; imports closed')
            candidate, issue = select(spec, candidate_id, issue_id)
            key = f'{candidate_id}/{issue_id}'
            old = state['attachments'].get(key)
            if old and old['state'] == 'complete':
                if old['run'] != str(run) or old['output_hashes'] != hashes(run):
                    raise ValueError('accepted native run outputs changed')
                receipt.update(state='complete', attachment=old, idempotent=True)
            else:
                manifest, complete, calls = validate_run(study, spec, candidate, issue, run)
                manifest_hash = digest_bytes((run / 'zenith_run.json').read_bytes())
                if old and (old['run'] != str(run) or old['manifest_hash'] != manifest_hash):
                    raise ValueError('pending native manifest changed')
                item = {'run': str(run), 'manifest_hash': manifest_hash, 'state': 'pending', 'calls': calls}
                if complete:
                    measurement_store = f'measurements/{key}/{number}'
                    registration = feedback.register(study / measurement_store, run,
                        study / spec['feedback_policy'], issue['horizon_id'])
                    forecasts = registration['forecasts']
                    support = {(f['target_id'], f['issue_time'], f['target_time']) for f in forecasts}
                    expected = {(target, issue['time_anchor'], issue['target_time']) for target in issue['target_ids']}
                    if support != expected or any(f['subject_data_gaps'] for f in forecasts):
                        raise ValueError('complete CP2 forecast support or prediction-time evidence differs')
                    item.update(state='complete', output_hashes=hashes(run), forecasts=forecasts,
                                measurement_store=measurement_store,
                                synthetic_fixture=all(f['synthetic_fixture'] for f in forecasts))
                state['attachments'][key] = item
                receipt.update(state=item['state'], attachment=item)
        except (ValueError, OSError, KeyError, TypeError) as exc:
            receipt.update(state='error', error=f'{type(exc).__name__}: {exc}')
        # Diagnosis observes the attempted run, including pre-CP2 failures. It is
        # additive evidence, never an acceptance gate or an attachment mutation.
        try:
            from research.diagnosis import observe_run
            observation = observe_run(run)
            if not isinstance(observation, dict):
                raise ValueError('diagnostic observation must be an object')
            feedback.canonical(observation)  # Reject unserializable diagnostic values independently.
            receipt['diagnostics'] = observation
        except Exception as exc:
            receipt['diagnostics'] = {
                'schema': 'zenith_run_diagnosis_v1', 'status': 'unknown', 'run_path': str(run),
                'manifest_ref': None, 'observations': [{
                    'code': 'diagnostic_observer_unavailable',
                    'details': f'{type(exc).__name__}: {exc}', 'verification': 'unknown'}],
                'verification_boundary': 'Additive observation failed; cohort acceptance result is unchanged.',
                'causal_claims': False}
        write_json(study / 'imports' / f'{number}.json', receipt)
    return receipt


def _compare(study, spec, state, phase):
    issues = [i for i in spec['issues'] if i['split'] == phase]
    if not issues:
        raise ValueError('no preregistered issues for this phase')
    values, pending, fixture_flags = {}, [], set()
    per_issue_scores, per_issue_coverage = {}, {}
    for candidate in spec['candidates']:
        candidate_id = candidate['candidate_id']
        per_issue_scores[candidate_id], per_issue_coverage[candidate_id] = {}, {}
        rows = []
        for issue in issues:
            issue_id = issue['issue_id']
            key = f"{candidate_id}/{issue_id}"
            item = state['attachments'].get(key)
            coverage = {'expected_target_count': len(issue['target_ids']),
                        'expected_target_ids': sorted(issue['target_ids']),
                        'forecast_target_count': len(item.get('forecasts', [])) if item else 0,
                        'scored_target_count': 0, 'scored_target_ids': [],
                        'missing_target_ids': sorted(issue['target_ids']), 'status': 'forecast_pending'}
            per_issue_coverage[candidate_id][issue_id] = coverage
            if not item or item['state'] != 'complete':
                pending.append(key)
                continue
            if item['output_hashes'] != hashes(item['run']):
                raise ValueError('accepted native run outputs changed')
            fixture_flags.add(item['synthetic_fixture'])
            result = feedback.score(study / item['measurement_store'], study / spec['truth_source'], spec['truth_as_of'])
            scored = [r for r in result['evaluations'] if r['status'] == 'scored']
            forecast_targets = {forecast['forecast_id']: forecast['target_id'] for forecast in item['forecasts']}
            scored_ids = [forecast_targets[r['forecast_id']] for r in scored]
            coverage.update(scored_target_count=len(scored), scored_target_ids=sorted(scored_ids),
                            missing_target_ids=sorted(set(issue['target_ids']) - set(scored_ids)),
                            status='truth_pending')
            if (any(r['status'] != 'scored' for r in result['evaluations'])
                    or len(scored) != len(issue['target_ids']) or set(scored_ids) != set(issue['target_ids'])):
                pending.append(key + ':truth')
                continue
            # Equal weight per issue, then per preregistered target within issue.
            loss = sum(r['metrics']['target_price_relative_error'] for r in result['evaluations']) / len(result['evaluations'])
            per_issue_scores[candidate_id][issue_id] = loss
            coverage['status'] = 'complete'
            rows.append(loss)
        if len(rows) == len(issues):
            values[candidate_id] = sum(rows) / len(rows)
    if pending:
        return {'state': 'pending', 'pending_support': pending, 'scores': None, 'decision': None,
                'per_issue_scores': None, 'paired_issue_deltas': None, 'per_issue_coverage': per_issue_coverage}
    if len(fixture_flags) != 1:
        raise ValueError('synthetic and non-synthetic cohorts cannot be pooled')
    weeks = {event_time(i['time_anchor']).isocalendar()[:2] for i in issues}
    result = {'state': 'complete', 'phase': phase, 'scores': values, 'issue_count': len(issues),
              'per_issue_scores': per_issue_scores,
              'paired_issue_deltas': {candidate: {issue_id: loss - per_issue_scores['baseline'][issue_id]
                                                 for issue_id, loss in scores.items()}
                                      for candidate, scores in per_issue_scores.items()},
              'paired_delta_interpretation': 'candidate minus baseline issue loss; negative favors candidate; descriptive, not uncertainty or causal attribution',
              'per_issue_coverage': per_issue_coverage,
              'clustered_weeks': len(weeks), 'synthetic_fixture': fixture_flags == {True},
              'metric': 'mean_issue_mean_target_price_relative_error',
              'interpretation': 'CP2 target-price error; no return, significance, or LLM forecasting claim',
              'decisions': {}, 'live_mutation_permission': False}
    result['identity_basis'] = 'declared_agent_response_metadata' if spec['candidates'][0]['provider'] == 'agent' else 'captured_replay_metadata' if spec['candidates'][0]['provider'] == 'captured' else 'provider_attempt_metadata'
    result['evaluation_posture'] = 'matured_frozen_cohort; no prospective preregistration claim'
    for candidate, loss in values.items():
        result['decisions'][candidate] = 'baseline' if candidate == 'baseline' else 'insufficient_issues' if len(issues) < 20 else 'candidate_proposal' if values['baseline'] - loss > spec['minimum_improvement'] else 'discard'
    return result


def evaluate(study, *, final_key=None):
    study = Path(study).resolve()
    with locked(study) as (spec, state):
        if final_key is None:
            if state['final'] is not None:
                raise ValueError('heldout final seal consumed; development comparisons closed')
            result = _compare(study, spec, state, 'development')
            write_json(study / 'development-comparison.json', result)
            return result
        if not isinstance(final_key, str) or not final_key:
            raise ValueError('nonempty final idempotency key required')
        if state['final'] is not None:
            if state['final']['key'] != final_key:
                raise ValueError('heldout final seal already consumed')
            return state['final']['receipt']
        development = _compare(study, spec, state, 'development')
        if development['state'] != 'complete' or development['issue_count'] < 20:
            raise ValueError('complete development cohort of at least 20 issues required before final')
        eligible = [name for name, decision in development['decisions'].items() if decision == 'candidate_proposal']
        selected = min(eligible, key=lambda name: (development['scores'][name], name)) if eligible else 'baseline'
        final_spec = dict(spec, candidates=[c for c in spec['candidates'] if c['candidate_id'] in {'baseline', selected}])
        # Seal durably before opening heldout outcomes, including errors/pending.
        state['final'] = {'key': final_key, 'receipt': {'state': 'interrupted', 'phase': 'holdout'}}
        write_json(study / 'cohort-state.json', state)
        try:
            result = _compare(study, final_spec, state, 'holdout')
            result['development_selected_candidate'] = selected
        except (ValueError, OSError) as exc:
            result = {'state': 'error', 'phase': 'holdout', 'error': f'{type(exc).__name__}: {exc}'}
        state['final']['receipt'] = result
        write_json(study / 'final-comparison.json', result)
        return result


def next_actions(study):
    """Machine-readable native commands; this function performs no model calls."""
    study = Path(study).resolve()
    with locked(study) as (spec, state):
        actions = []
        if state['final'] is not None:
            return {'state': 'sealed', 'actions': [], 'final': state['final']['receipt']}
        for candidate in spec['candidates']:
            for issue in spec['issues']:
                key = f"{candidate['candidate_id']}/{issue['issue_id']}"
                item = state['attachments'].get(key)
                if item and item['state'] == 'complete':
                    continue
                run_id = 'COHORT_' + state['spec_hash'][:12] + '_' + candidate['candidate_id'] + '_' + issue['issue_id']
                run = Path(item['run']) if item else runtime.runs_root(runtime.DEFAULT_ROOT) / run_id
                attach_command = [sys.executable, '-m', 'research', 'cohort-attach', '--study', str(study),
                    '--candidate-id', candidate['candidate_id'], '--issue-id', issue['issue_id'], '--run', str(run)]
                if item:
                    native = [sys.executable, '-m', 'zenith', 'resume', run.name]
                    action = 'resume_native_then_attach'
                elif (run / 'zenith_run.json').exists():
                    native, action = None, 'attach_existing_native_run'
                else:
                    native = [sys.executable, '-m', 'zenith', 'run', 'lab', '--target', 'lab_director',
                        '--run-id', run_id, '--provider', candidate['provider'], '--model', candidate['model'],
                        '--feed-source', str(study / issue['feed_source']), '--time-anchor', issue['time_anchor'],
                        '--horizon', issue['horizon_id'], '--context-profile', candidate['context_profile']]
                    for field, flag in (('graph_variant', '--graph-variant'), ('reasoning_policy', '--policy')):
                        if candidate[field]:
                            native += [flag, str(study / candidate[field])]
                    action = 'run_native_then_attach'
                row = {'candidate_id': candidate['candidate_id'], 'issue_id': issue['issue_id'],
                       'split': issue['split'], 'action': action, 'native_argv': native, 'attach_argv': attach_command,
                       'model_calls_here': False, 'call_budget': spec['max_calls_per_run'],
                       'call_budget_enforcement': 'audited_at_import; native commands have no pre-call limit'}
                if candidate['provider'] == 'captured' and native is not None and action == 'run_native_then_attach':
                    row['required_native_arguments'] = {'--responses': 'path to exact prompt-bound captured responses'}
                actions.append(row)
        return {'schema': 'zenith_cohort_actions_v1', 'state': 'pending' if actions else 'ready_for_comparison',
                'actions': actions, 'candidate_attempts_spent': len(spec['candidates']),
                'import_attempts': state['attempts'], 'compare_argv': [sys.executable, '-m', 'research',
                    'cohort-evaluate', '--study', str(study)], 'claim_boundary': 'commands only; no optimizer or provider execution'}
