"""Development-only reflection and one-parameter native policy proposals.

These functions make no provider calls or writes. A packet preserves the complete
feedback proposal, including successes and unresolved denominators. Participation
is a routing signal, never causal attribution or a numerical gradient.
"""
from __future__ import annotations

from copy import deepcopy
from functools import wraps
import hashlib
from pathlib import Path

from feedback.engine import ROOT, canonical, digest, read_object, timestamp
from system.lib.hashing import hash_node
from system.lib.reasoning_policy import policy_sha256, validate_reasoning_policy
from zenith.providers import verify_packet, verify_response

TRACE_CHAR_CAP = 2048
TRACE_EXCHANGE_LIMIT = 2


def _validated(function):
    @wraps(function)
    def checked(*args, **kwargs):
        try:
            return function(*args, **kwargs)
        except (KeyError, TypeError, AttributeError, IndexError, OSError) as exc:
            raise ValueError(f'malformed or unavailable reflection evidence: {exc}') from exc
    return checked


def _file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _check_ref(ref, source_root):
    if not isinstance(ref, dict) or not isinstance(ref.get('path'), str) or not ref['path']:
        raise ValueError('source reference requires a path')
    path = Path(source_root) / ref['path']
    if _file_hash(path) != ref.get('sha256'):
        raise ValueError(f'source hash mismatch: {ref["path"]}')


def _excerpt(value):
    text = value if isinstance(value, str) else canonical(value)
    excerpt = text[:TRACE_CHAR_CAP]
    return {'encoding': 'text' if isinstance(value, str) else 'canonical_json',
            'text': excerpt, 'original_chars': len(text), 'retained_chars': len(excerpt),
            'original_sha256': hashlib.sha256(text.encode()).hexdigest(),
            'truncated': len(excerpt) < len(text)}


def _trace_source(path):
    return {'path': str(path.resolve()), 'sha256': _file_hash(path),
            'original_bytes': path.stat().st_size}


def _trace_case(row, proposal, node_id, source_root):
    forecast_path = (Path(source_root) / row['forecast_ref']['path']).resolve()
    if forecast_path.parent.name != 'artifacts' or forecast_path.name != 'lab_director.json':
        raise ValueError('trace forecast must identify the native CP2 artifact')
    run = forecast_path.parent.parent
    manifest_path = run / 'zenith_run.json'
    manifest = read_object(manifest_path)
    if (manifest['run_id'] != row['issue_run_id'] or manifest['run_id'] != run.name
            or timestamp(manifest['time_anchor']) != timestamp(row['issue_time'])
            or manifest.get('mission') != 'lab'):
        raise ValueError('trace run differs from development evidence identity')
    versions = {p['node_sha256'] for p in proposal['participating_ancestors'] if p['node_id'] == node_id}
    if len(versions) != 1 or node_id not in manifest['scope'] or manifest['node_hashes'].get(node_id) not in versions:
        raise ValueError('trace node differs from measured frozen ancestry')
    expected_policy = proposal.get('reasoning_policy_sha256')
    if (manifest.get('reasoning_policy') or {}).get('policy_sha256') != expected_policy:
        raise ValueError('trace reasoning policy differs from measured policy')
    case = {'forecast_id': row['forecast_id'], 'issue_run_id': row['issue_run_id'],
            'issue_time': row['issue_time'], 'supports_candidate_class': row['supports_candidate_class'],
            'manifest_source': _trace_source(manifest_path), 'node_id': node_id,
            'node_sha256': next(iter(versions)), 'handoff_exchanges': []}
    artifact_path = run / 'artifacts' / f'{node_id}.json'
    if artifact_path.exists():
        artifact = read_object(artifact_path)
        if artifact.get('id', node_id) != node_id or artifact.get('node_hash', next(iter(versions))) not in versions:
            raise ValueError('trace artifact node binding mismatch')
        if expected_policy and artifact.get('metadata', {}).get('reasoning_policy_sha256') != expected_policy:
            raise ValueError('trace artifact reasoning policy binding mismatch')
        case['node_artifact'] = {'status': 'present', 'source': _trace_source(artifact_path),
                                 'binding': 'frozen manifest and named node artifact; embedded node identity checked where present',
                                 'embedded_node_identity_available': 'id' in artifact and 'node_hash' in artifact,
                                 'artifact_status': artifact.get('status'),
                                 'output': _excerpt(artifact.get('data')),
                                 'metadata': _excerpt(artifact.get('metadata', {}))}
    else:
        case['node_artifact'] = {'status': 'missing', 'expected_path': str(artifact_path),
                                 'reason': 'No selected-node artifact is available; no output trajectory is inferred.'}
    requests = []
    for path in sorted((run / 'handoff' / 'requests').glob('*.json')):
        request = read_object(path)
        if request.get('node_id') != node_id:
            continue
        verify_packet(request)
        if request['run_id'] != row['issue_run_id'] or path.stem != request['packet_id']:
            raise ValueError('trace handoff request run or filename binding mismatch')
        requests.append((path, request))
    case['handoff_request_count'] = len(requests)
    case['omitted_request_count'] = max(0, len(requests) - TRACE_EXCHANGE_LIMIT)
    case['input_status'] = 'observed_prompt_excerpts' if requests else 'missing_handoff_prompt'
    for request_path, request in requests[:TRACE_EXCHANGE_LIMIT]:
        exchange = {'packet_id': request['packet_id'], 'request_source': _trace_source(request_path),
                    'prompt_sha256': request['prompt_sha256'], 'prompt': _excerpt(request['prompt'])}
        response_path = run / 'handoff' / 'responses' / request_path.name
        validation_path = run / 'handoff' / 'validation' / request_path.name
        if response_path.exists():
            response = read_object(response_path)
            verify_response(request, response)
            if response.get('imported_at') and timestamp(response['imported_at']) > timestamp(proposal['analysis_window']['as_of']):
                raise ValueError('future handoff response cannot enter reflection')
            response_hash = hashlib.sha256(response['response_text'].encode()).hexdigest()
            exchange.update(response_status='present', response_source=_trace_source(response_path),
                            response=_excerpt(response['response_text']),
                            output_binding='request/response identity verified; engine acceptance unavailable')
            if validation_path.exists():
                validation = read_object(validation_path)
                if (validation.get('schema') != 'zenith_import_validation_v1'
                        or validation.get('packet_id') != request['packet_id'] or validation.get('run_id') != row['issue_run_id']
                        or validation.get('node_id') != node_id or validation.get('response_sha256') != response_hash):
                    raise ValueError('trace handoff validation binding mismatch')
                exchange.update(validation_source=_trace_source(validation_path),
                                engine_accepted=validation.get('engine_accepted'),
                                output_binding='native import validation binds this response; final artifact equivalence is not independently inferred')
            else:
                exchange['validation_status'] = 'missing'
        else:
            exchange.update(response_status='missing', output_binding='request only; no response inferred')
        case['handoff_exchanges'].append(exchange)
    case['trajectory_boundary'] = 'Selected-node output and available identity-bound handoff exchanges only. '
    case['trajectory_boundary'] += 'Missing prompts, omitted exchanges and truncated fields prevent any full-trajectory claim.'
    return case


def _trace_context(proposal, node_id, source_root):
    if not isinstance(node_id, str) or not node_id or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-' for c in node_id):
        raise ValueError('selected trace node must be a safe node identifier')
    if not any(p['node_id'] == node_id for p in proposal['participating_ancestors']):
        raise ValueError('selected trace node did not participate in measured ancestry')
    rows = sorted(proposal['evidence'], key=lambda row: (timestamp(row['issue_time']), row['forecast_id']))
    selected, seen_runs = [], set()
    for failed, limit in ((True, 3), (False, 2)):
        matches = 0
        for row in rows:
            if row['supports_candidate_class'] is failed and row['issue_run_id'] not in seen_runs and matches < limit:
                selected.append(row)
                seen_runs.add(row['issue_run_id'])
                matches += 1
    selected_ids = {row['forecast_id'] for row in selected}
    return {'schema': 'zenith_reflection_trace_context_v1', 'node_id': node_id,
            'selection': {'strategy': 'first distinct runs by issue_time then forecast_id within failure/success classes',
                          'failure_case_limit': 3, 'success_case_limit': 2,
                          'field_char_cap': TRACE_CHAR_CAP, 'exchange_limit_per_case': TRACE_EXCHANGE_LIMIT},
            'cases': [_trace_case(row, proposal, node_id, source_root) for row in selected],
            'omitted_forecast_ids': [row['forecast_id'] for row in rows if row['forecast_id'] not in selected_ids],
            'claim_boundary': 'Illustrative, deterministic development search context only. The full proposal '
            'retains measured support and denominators; sampled traces are not representative statistical evidence or causal attribution.'}


@_validated
def scope_from_study(study, as_of):
    """Derive membership from complete native attachments and frozen issue splits.

    This reads attachment metadata only; heldout metrics are never included.
    It cannot prove that an operator or another process has not seen holdout data.
    """
    study = Path(study).resolve()
    spec_path, state_path = study / 'cohort.json', study / 'cohort-state.json'
    spec, state = read_object(spec_path), read_object(state_path)
    if spec.get('schema') != 'zenith_graph_cohort_v1':
        raise ValueError('native frozen cohort specification required')
    if _file_hash(spec_path) != state.get('spec_hash'):
        raise ValueError('frozen cohort specification hash mismatch')
    if state.get('final') is not None:
        raise ValueError('heldout final seal consumed; reflection closed')
    splits = {row['issue_id']: row['split'] for row in spec['issues']}
    if any(split not in {'development', 'holdout'} for split in splits.values()):
        raise ValueError('invalid frozen issue split')
    membership = {'development': set(), 'holdout': set()}
    for key, attachment in state['attachments'].items():
        if attachment.get('state') != 'complete':
            continue
        issue_id = key.split('/', 1)[1]
        if issue_id not in splits:
            raise ValueError('attachment issue is absent from frozen cohort')
        membership[splits[issue_id]].update(f['issue_run_id'] for f in attachment['forecasts'])
    return {'schema': 'zenith_reflection_scope_v1', 'as_of': timestamp(as_of).isoformat(),
            'development_run_ids': sorted(membership['development']),
            'heldout_run_ids': sorted(membership['holdout']),
            'membership_authority': 'frozen cohort issue splits and complete native attachment records',
            'cohort_sources': [
                {'path': str(spec_path), 'sha256': _file_hash(spec_path)},
                {'path': str(state_path), 'sha256': _file_hash(state_path)}]}


def _validate_scope(scope, source_root):
    required = {'schema', 'as_of', 'development_run_ids', 'heldout_run_ids'}
    if not isinstance(scope, dict) or not required.issubset(scope) or scope['schema'] != 'zenith_reflection_scope_v1':
        raise ValueError('explicit reflection development scope required')
    if set(scope) - required - {'membership_authority', 'cohort_sources'}:
        raise ValueError('unknown reflection scope fields')
    for field in ('development_run_ids', 'heldout_run_ids'):
        values = scope[field]
        if not isinstance(values, list) or any(not isinstance(v, str) or not v for v in values) or len(values) != len(set(values)):
            raise ValueError('scope run ids must be unique nonempty strings')
    if not scope['development_run_ids']:
        raise ValueError('reflection scope has no development runs')
    if set(scope['development_run_ids']) & set(scope['heldout_run_ids']):
        raise ValueError('development and holdout scopes overlap')
    for ref in scope.get('cohort_sources', []):
        _check_ref(ref, source_root)
    return timestamp(scope['as_of'])


def _validate_proposal(proposal, scope, source_root):
    cutoff = _validate_scope(scope, source_root)
    if proposal.get('schema') != 'zenith_skill_feedback_proposal_v1' or proposal.get('live_mutation_permission') is not False:
        raise ValueError('native review-only feedback proposal required')
    if proposal.get('proposal_id') != digest({k: v for k, v in proposal.items() if k != 'proposal_id'}):
        raise ValueError('feedback proposal hash mismatch')
    window = proposal['analysis_window']
    analysis_time = timestamp(window['as_of'])
    if analysis_time > cutoff:
        raise ValueError('proposal analysis is after reflection cutoff')
    evidence = proposal['evidence']
    if not isinstance(evidence, list) or not evidence:
        raise ValueError('proposal needs complete resolved evidence')
    identities = [row['forecast_id'] for row in evidence]
    if len(identities) != len(set(identities)):
        raise ValueError('duplicate forecast evidence')
    development = set(scope['development_run_ids'])
    for row in evidence:
        if row['issue_run_id'] not in development or row['issue_run_id'] in scope['heldout_run_ids']:
            raise ValueError('proposal contains nondevelopment or heldout evidence')
        issue, observed = timestamp(row['issue_time']), timestamp(row['truth_observed_time'])
        if not timestamp(window['start_inclusive']) <= issue <= observed <= analysis_time:
            raise ValueError('future or out-of-window evidence')
        if type(row['supports_candidate_class']) is not bool:
            raise ValueError('failure membership must be boolean')
        _check_ref(row['forecast_ref'], source_root)
        _check_ref(row['truth_ref'], source_root)
    failures = sum(row['supports_candidate_class'] for row in evidence)
    statuses = proposal['sample_status_counts']
    if any(type(count) is not int or count < 0 for count in statuses.values()):
        raise ValueError('invalid sample status denominator')
    if (proposal['total_resolved'] != len(evidence) or proposal['total_failures'] != failures
            or statuses.get('scored') != len(evidence)
            or sum(statuses.values()) != proposal['total_registered_samples_in_window']
            or proposal['support_fraction'] != failures / len(evidence)):
        raise ValueError('proposal denominator or failure counts differ from evidence')
    if proposal['distinct_resolved_issue_times'] != len({row['issue_time'] for row in evidence}):
        raise ValueError('proposal issue count differs from evidence')
    for participant in proposal['participating_ancestors']:
        for ref in participant.get('context_policy_receipts', []):
            _check_ref(ref, source_root)


@_validated
def build_packet(proposal_path, *, scope, source_root=ROOT, node_id='lab_director'):
    """Seal full, source-verified development evidence for an agent to reflect on."""
    proposal_path = Path(proposal_path).resolve()
    proposal = read_object(proposal_path)
    scope = deepcopy(scope)
    _validate_proposal(proposal, scope, source_root)
    packet = {'schema': 'zenith_reflection_packet_v1', 'scope': scope,
              'scope_sha256': digest(scope), 'source_root': str(Path(source_root).resolve()),
              'proposal_source': {'path': str(proposal_path), 'sha256': _file_hash(proposal_path)},
              'proposal': proposal, 'trace_context': _trace_context(proposal, node_id, source_root),
              'live_mutation_permission': False,
              'reflection_instruction': 'Review failures together with successes and unresolved denominators. '
              'Choose one participating node and one falsifiable skill/context parameter change. '
              'Structural ancestry is not causal blame. This is development evidence, not heldout validation.',
              'membership_boundary': 'Explicit scope declares membership; cohort-derived scope verifies frozen '
              'attachment membership. Neither proves holdout secrecy outside this consumer.'}
    packet['packet_sha256'] = digest(packet)
    return packet


@_validated
def validate_packet(packet):
    if packet.get('schema') != 'zenith_reflection_packet_v1' or packet.get('live_mutation_permission') is not False:
        raise ValueError('review-only reflection packet required')
    if packet.get('packet_sha256') != digest({k: v for k, v in packet.items() if k != 'packet_sha256'}):
        raise ValueError('reflection packet hash mismatch')
    if packet.get('scope_sha256') != digest(packet['scope']):
        raise ValueError('reflection scope hash mismatch')
    _check_ref(packet['proposal_source'], packet['source_root'])
    if read_object(packet['proposal_source']['path']) != packet['proposal']:
        raise ValueError('embedded proposal differs from source')
    _validate_proposal(packet['proposal'], packet['scope'], packet['source_root'])
    trace = packet['trace_context']
    if trace != _trace_context(packet['proposal'], trace['node_id'], packet['source_root']):
        raise ValueError('reflection trace sources or deterministic excerpts changed')
    return packet


@_validated
def compile_candidate(packet, *, graph, node_id, parameter, value, hypothesis,
                      variant_id, edge_id=None, baseline_policy=None):
    """Compile one declared change into a validated native policy, for review only."""
    validate_packet(packet)
    if not isinstance(hypothesis, str) or not hypothesis.strip():
        raise ValueError('a falsifiable hypothesis is required')
    proposal = packet['proposal']
    if node_id != packet['trace_context']['node_id']:
        raise ValueError('candidate node differs from selected reflection trace node')
    participants = proposal['participating_ancestors']
    if node_id not in graph or not any(p['node_id'] == node_id for p in participants):
        raise ValueError('candidate node did not participate in measured ancestry')
    for participant in participants:
        ancestor = graph.get(participant['node_id'])
        if (ancestor is None or participant['node_sha256'] != hash_node(ancestor)
                or sorted(participant['parent_ids']) != sorted(ancestor.dependencies)):
            raise ValueError('candidate graph differs from measured frozen ancestry')
    if baseline_policy is not None:
        baseline = validate_reasoning_policy(baseline_policy, graph)
    else:
        baseline = None
    expected = proposal.get('reasoning_policy_sha256')
    if (baseline or {}).get('policy_sha256') != expected:
        raise ValueError('baseline policy differs from measured reasoning policy')
    if parameter not in {'skill_addon', 'max_context_chars', 'incoming_weights'}:
        raise ValueError('candidate must change one skill/context parameter')
    if parameter == 'incoming_weights':
        if not isinstance(edge_id, str) or edge_id not in graph[node_id].dependencies:
            raise ValueError('candidate requires one declared incoming edge')
    elif edge_id is not None:
        raise ValueError('edge_id is only valid for incoming_weights')
    policy = deepcopy(baseline) if baseline else {'nodes': {}}
    row = policy['nodes'].setdefault(node_id, {})
    fields = row.setdefault('incoming_weights', {}) if parameter == 'incoming_weights' else row
    key = edge_id if parameter == 'incoming_weights' else parameter
    before = {'present': key in fields, 'value': deepcopy(fields.get(key))}
    effective_default = 1 if parameter == 'incoming_weights' else ('' if parameter == 'skill_addon' else None)
    if (before['value'] if before['present'] else effective_default) == value:
        raise ValueError('candidate change is a no-op')
    fields[key] = deepcopy(value)
    policy['variant_id'] = variant_id
    policy['policy_sha256'] = policy_sha256(policy)
    policy = validate_reasoning_policy(policy, graph)
    change = {'node_id': node_id, 'parameter': parameter, 'edge_id': edge_id,
              'before': before, 'after': deepcopy(value)}
    candidate = {'schema': 'zenith_reflection_candidate_v1', 'variant_id': variant_id,
                 'hypothesis': hypothesis, 'packet_sha256': packet['packet_sha256'],
                 'proposal_id': proposal['proposal_id'], 'baseline_policy_sha256': expected,
                 'reasoning_policy_sha256': policy['policy_sha256'], 'change': change,
                 'state': 'review_only', 'live_mutation_permission': False,
                 'requires': 'Preregister in a new bounded frozen study; compare complete matched development '
                 'support and separately sealed holdout or prospective evidence before promotion.',
                 'claim_boundary': 'A proposed discrete text/context intervention, not a gradient or demonstrated improvement.'}
    candidate['candidate_sha256'] = digest(candidate)
    return {'reasoning_policy': policy, 'candidate': candidate}
