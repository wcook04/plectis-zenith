"""Historical daily progression through the existing Lab, Oracle and Evolve.

This controller never calls a provider. Native agent packets are answered with
import-response; Evolve decisions are explicitly reviewed, retained and compiled
into a successor policy. Mechanical acceptance is not semantic endorsement.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import date, timedelta
import hashlib
import json
from pathlib import Path

from benchmarks import fnspid
from system.lib.reasoning_policy import policy_sha256, validate_reasoning_policy
from tools.refinement import run_evolve as evolve
from . import runtime
from .providers import write_json


def read(path):
    return json.loads(Path(path).read_text())


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def substrate_hashes(root):
    paths = [p for p in (root/'codex').rglob('*') if p.is_file() and p.suffix in {'.json', '.md'}]
    paths.append(root/'master_config.json')
    return {str(p.relative_to(root)): file_hash(p) for p in sorted(paths)}


def dataset_adapter(dataset):
    schema = read(Path(dataset)/'source-manifest.json').get('schema')
    if schema == 'fnspid_raw_source_v1':
        return fnspid
    raise ValueError('No native daily adapter for this source manifest')


def immutable(path, value):
    if path.exists():
        if read(path) != value:
            raise ValueError(f"Retain existing evidence; refusing to overwrite {path}")
    else:
        write_json(path, value)


def initialize(root, directory, dataset, start, end, policy=None, retention=None):
    """Freeze inclusive forecast dates plus the following session's truth."""
    root, directory, dataset = map(lambda p: Path(p).resolve(), (root, directory, dataset))
    adapter = dataset_adapter(dataset)
    first, last = date.fromisoformat(start), date.fromisoformat(end)
    if last < first or (last-first).days > 366:
        raise ValueError("Use an ordered daily range of at most one year")
    calendar = adapter.calendar_for(start, (last + timedelta(days=14)).isoformat())
    if not calendar.is_session(start) or not calendar.is_session(end):
        raise ValueError("Start and end must be source exchange sessions")
    retention_receipt = None
    if policy and retention:
        raise ValueError('Choose a baseline policy or a retained generation receipt, not both')
    if policy and Path(policy).name == 'retained-policy.json':
        raise ValueError('Use --retention to preserve the selected policy evidence cutoff')
    if retention:
        from research.daily_matchoff import retained_policy
        original, cutoff, retention_receipt = retained_policy(retention)
        if calendar.session_close(start).to_pydatetime() <= runtime.stamp(cutoff):
            raise ValueError('Next generation must start after selection evidence matured')
    else:
        original = read(policy) if policy else {"variant_id": "daily-baseline", "nodes": {}}
        if not policy:
            original['policy_sha256'] = policy_sha256(original)
    sessions = [s.date().isoformat() for s in calendar.sessions_in_range(start, end)]
    sessions.append(calendar.next_session(end).date().isoformat())
    with runtime.run_lock(directory):
        if (directory/'daily.json').exists():
            raise ValueError("Daily programme already exists; use daily next")
        baseline = validate_reasoning_policy(original, runtime.load_graph(root))
        snapshots = []
        for session in sessions:
            path = directory/'feeds'/session
            snapshot = adapter.snapshot(dataset, session, path)
            snapshots.append({"date": session, "anchor": snapshot['issue_at_utc'],
                              "observation_at": snapshot.get('observation_at_utc', snapshot['issue_at_utc']),
                              "path": str(path), "snapshot_sha256": snapshot['snapshot_sha256'],
                              "files": read(path/'artifact-manifest.json')['files']})
        immutable(directory/'policies/baseline.json', baseline)
        manifest = {"schema": "zenith_daily_programme_v1", "root": str(root),
                    "snapshots": snapshots, "baseline": baseline,
                    "controller_sha256": file_hash(Path(__file__)),
                    "native_implementation": runtime.implementation_hashes(),
                    "substrate_hashes": substrate_hashes(root),
                    "retention_receipt": retention_receipt,
                    "context_profile": "compact_feeds", "provider": "agent"}
        manifest['programme_sha256'] = digest(manifest)
        immutable(directory/'daily.json', manifest)
    return {"status": "prepared", "episodes": len(sessions)-1,
            "programme_sha256": manifest['programme_sha256'],
            "next": ["python", "-m", "zenith", "daily", "next", "--work-dir", str(directory)]}


def load(root, directory):
    manifest = read(directory/'daily.json')
    if manifest['programme_sha256'] != digest({k: v for k, v in manifest.items() if k != 'programme_sha256'}):
        raise ValueError("Daily programme identity changed")
    if manifest['root'] != str(root.resolve()):
        raise ValueError("Daily programme belongs to another checkout; initialize a new programme")
    if manifest['controller_sha256'] != file_hash(Path(__file__)) or manifest['native_implementation'] != runtime.implementation_hashes():
        raise ValueError("Daily implementation changed; retain this programme and initialize a new one")
    if manifest['substrate_hashes'] != substrate_hashes(root):
        raise ValueError("Frozen graph, contracts or configuration changed")
    for snapshot in manifest['snapshots']:
        for name, expected in snapshot['files'].items():
            if file_hash(Path(snapshot['path'])/name) != expected:
                raise ValueError("Frozen daily snapshot changed")
    if read(directory/'policies/baseline.json') != manifest['baseline']:
        raise ValueError("Frozen baseline policy changed")
    return manifest


def run_ids(manifest, index):
    prefix = 'DAILY_' + manifest['programme_sha256'][:12] + '_' + str(index)
    return prefix+'_LAB', prefix+'_ORACLE'


def checked_run(root, manifest, index, mission, policy_path):
    lab_id, oracle_id = run_ids(manifest, index)
    before, after = manifest['snapshots'][index:index+2]
    run_id = lab_id if mission == 'lab' else oracle_id
    expected = {'mission': mission, 'provider': 'agent', 'time_anchor': before['anchor'],
                'horizon': after.get('observation_at', after['anchor']), 'context_profile': manifest['context_profile']}
    if mission == 'lab':
        expected.update(feed_source=before['path'], policy=str(policy_path))
    else:
        expected.update(subject_run=str(runtime.runs_root(root)/lab_id), truth_run=after['path'])
    run_path = runtime.runs_root(root)/run_id
    if not (run_path/'zenith_run.json').exists():
        return runtime.start(root, run_id=run_id, **expected)
    spec = read(run_path/'zenith_run.json')
    for name, value in expected.items():
        key = 'policy_source' if name == 'policy' else name
        actual = spec.get(key)
        if name in {'time_anchor', 'horizon'}:
            actual, value = runtime.stamp(actual), runtime.stamp(value)
        if actual != value:
            raise ValueError(f"Daily run binding mismatch: {key}")
    if spec['node_hashes'].keys() != {n['id'] for n in runtime.plan(root, mission)['nodes']}:
        raise ValueError("Daily run must execute the full native mission")
    runtime._check_frozen_graph(root, spec)
    return runtime.status(root, run_id)


def make_review_packet(root, directory, manifest, index, policy_path):
    lab_id, oracle_id = run_ids(manifest, index)
    episode = directory/'episodes'/str(index)
    pair_path = episode/'evolve-input.json'
    result = evolve.export_agent_handoff(runtime.runs_root(root)/lab_id,
                                        runtime.runs_root(root)/oracle_id, pair_path)
    if result.get('error'):
        raise ValueError(result['error'])
    evolve.verify_agent_handoff(pair_path)
    binding = read(pair_path)
    sources = {'lab_director': str(runtime.runs_root(root)/lab_id/'artifacts/lab_director.json')}
    for canonical, names in evolve.ORACLE_ARTIFACTS:
        sources[canonical] = next(str(runtime.runs_root(root)/oracle_id/'artifacts'/f'{name}.json')
                                  for name in names if (runtime.runs_root(root)/oracle_id/'artifacts'/f'{name}.json').exists())
    packet = {'schema': 'zenith_daily_review_v1', 'programme_sha256': manifest['programme_sha256'],
              'episode': index, 'evolve_input': str(pair_path),
              'evolve_input_sha256': binding['packet_sha256'], 'sources': sources,
              'baseline_policy': read(policy_path), 'matured_at': manifest['snapshots'][index+1]['anchor'],
              'parent_review_sha256': read(directory/'episodes'/str(index-1)/'review.json')['review_sha256'] if index else None,
              'instructions': (
                  'Read the bound Evolve prompt and complete source artifacts. Distinguish observed error, '
                  'possible cause and transferable lesson. Do not treat a direction hit as causal proof. '
                  'Propose one short skill change to one Lab reasoning node, or no change. '
                  'Quote exact JSON values using source keys and RFC6901 pointers. Explain uncertainty '
                  'and a later-day test. This is reviewed development, not proof of learning. '
                  'Return the response contract below; the reviewing agent imports it with its identity.'),
              'response_contract': {
                  'packet_sha256': '<this packet hash>', 'decision': 'candidate or no_change',
                  'diagnosis': '<reasoned explanation>', 'uncertainty': '<limits and alternatives>',
                  'test': '<what later evidence would support or refute the lesson>',
                  'evidence': [{'source': '<one sources key>', 'pointer': '/data/<field>', 'value': '<exact JSON value>'}],
                  'change': {'node_id': '<Lab reasoning node>', 'skill_addon': '<at most 512 characters; replaces this node addon>'}
              }}
    packet['response_contract']['no_change_rule'] = 'For no_change set change to null; still explain and cite evidence.'
    packet['packet_sha256'] = digest(packet)
    immutable(episode/'review-packet.json', packet)
    return packet, episode


def pointer_value(value, pointer):
    if not isinstance(pointer, str) or not pointer.startswith('/'):
        raise ValueError("Evidence requires a non-root JSON pointer")
    try:
        for token in pointer[1:].split('/'):
            token = token.replace('~1', '/').replace('~0', '~')
            value = value[int(token)] if isinstance(value, list) else value[token]
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise ValueError("Evidence pointer does not resolve") from exc
    return value


def compile_review(root, packet, response):
    required = {'packet_sha256', 'decision', 'diagnosis', 'uncertainty', 'test', 'evidence', 'change'}
    if not isinstance(response, dict) or set(response) != required or response['packet_sha256'] != packet['packet_sha256']:
        raise ValueError("Review must match the exact packet and response contract")
    for name in ('diagnosis', 'uncertainty', 'test'):
        if not isinstance(response[name], str) or not response[name].strip():
            raise ValueError(f"Review requires {name}")
    if not isinstance(response['evidence'], list) or not response['evidence']:
        raise ValueError("Review requires source evidence")
    for row in response['evidence']:
        if not isinstance(row, dict) or set(row) != {'source', 'pointer', 'value'} or row['source'] not in packet['sources']:
            raise ValueError("Evidence source is outside this paired episode")
        actual = pointer_value(read(packet['sources'][row['source']]), row['pointer'])
        if digest(actual) != digest(row['value']):
            raise ValueError("Evidence quote does not match its source")
    policy = deepcopy(packet['baseline_policy'])
    if response['decision'] == 'no_change':
        if response['change'] is not None:
            raise ValueError("No-change review must not contain a change")
        return policy
    if response['decision'] != 'candidate':
        raise ValueError("Decision must be candidate or no_change")
    change = response['change']
    if not isinstance(change, dict) or set(change) != {'node_id', 'skill_addon'}:
        raise ValueError("Candidate requires exactly one node skill change")
    graph = runtime.load_graph(root)
    node_id = change['node_id']
    if node_id not in graph or graph[node_id].group != 'lab' or not isinstance(change['skill_addon'], str) or not change['skill_addon'].strip():
        raise ValueError("Candidate must change a Lab reasoning skill")
    if node_id not in runtime.scope_for(graph, 'lab_integrity'):
        raise ValueError("Candidate is outside the Lab")
    before = policy['nodes'].get(node_id, {}).get('skill_addon', '')
    if before == change['skill_addon']:
        raise ValueError("Unchanged skill is a no_change decision")
    policy['nodes'].setdefault(node_id, {})['skill_addon'] = change['skill_addon']
    policy['variant_id'] = 'daily-candidate-' + digest(response)[:16]
    policy['policy_sha256'] = policy_sha256(policy)
    return validate_reasoning_policy(policy, graph)


def checked_decision(root, packet, decision, candidate_path):
    required = {'schema', 'response', 'reviewer', 'policy_sha256', 'status', 'claim', 'review_sha256'}
    if (set(decision) != required or decision['schema'] != 'zenith_daily_review_receipt_v1'
        or not isinstance(decision['reviewer'], str) or not decision['reviewer'].strip()
        or decision['review_sha256'] != digest({k: v for k, v in decision.items() if k != 'review_sha256'})):
        raise ValueError('Reviewed decision receipt changed')
    policy = compile_review(root, packet, decision['response'])
    expected = 'reviewed_candidate' if decision['response']['decision'] == 'candidate' else 'reviewed_no_change'
    if decision['status'] != expected:
        raise ValueError('Reviewed decision status disagrees with response')
    if read(candidate_path) != policy or decision['policy_sha256'] != policy['policy_sha256']:
        raise ValueError('Reviewed successor policy changed')
    return policy


def reviewed_episode(root, directory, index):
    """Reconstruct a reviewed generation without progressing to a future episode."""
    root, directory = Path(root).resolve(), Path(directory).resolve()
    manifest = load(root, directory)
    if type(index) is not int or not 0 <= index < len(manifest['snapshots'])-1:
        raise ValueError('Unknown episode')
    policy_path = directory/'policies/baseline.json'
    for number in range(index+1):
        decision_path = directory/'episodes'/str(number)/'review.json'
        if not decision_path.exists():
            raise ValueError('Episode has no completed review')
        for mission, run_id in zip(('lab', 'oracle'), run_ids(manifest, number)):
            if not (runtime.runs_root(root)/run_id/'zenith_run.json').exists():
                raise ValueError('Reviewed episode has no native run manifest')
            if checked_run(root, manifest, number, mission, policy_path)['status'] != 'completed':
                raise ValueError('Reviewed native episode is incomplete')
        packet, _ = make_review_packet(root, directory, manifest, number, policy_path)
        decision = read(decision_path)
        candidate_path = directory/'policies'/f'after-{number}.json'
        checked_decision(root, packet, decision, candidate_path)
        if number == index:
            return manifest, packet, decision, policy_path, candidate_path
        policy_path = candidate_path


def advance(root, directory, review=None, reviewer=None):
    """Stop at genuine work; never manufacture responses or silently retry errors."""
    root, directory = Path(root).resolve(), Path(directory).resolve()
    with runtime.run_lock(directory):
        manifest = load(root, directory)
        policy_path = directory/'policies/baseline.json'
        for index in range(len(manifest['snapshots'])-1):
            for mission in ('lab', 'oracle'):
                status = checked_run(root, manifest, index, mission, policy_path)
                if status['status'] != 'completed':
                    if review is not None:
                        raise ValueError("Complete Lab and Oracle before importing Evolve review")
                    return {'stage': mission, 'episode': index, **status,
                            'instruction': 'Answer pending native packets with zenith import-response, then run daily next again.'}
            packet, episode = make_review_packet(root, directory, manifest, index, policy_path)
            decision_path = episode/'review.json'
            candidate_path = directory/'policies'/f'after-{index}.json'
            if decision_path.exists():
                decision = read(decision_path)
                checked_decision(root, packet, decision, candidate_path)
                policy_path = candidate_path
                continue
            if review is None:
                return {'stage': 'evolve', 'status': 'awaiting_review', 'episode': index,
                        'packet_path': str(episode/'review-packet.json'), 'packet_sha256': packet['packet_sha256'],
                        'instruction': 'Read the bound sources and return a reviewed response with daily review.'}
            if not isinstance(reviewer, str) or not reviewer.strip():
                raise ValueError("Disclose the reviewing agent or human identity")
            raw = Path(review).read_text()
            attempt = episode/'attempts'/hashlib.sha256(raw.encode()).hexdigest()
            immutable(attempt/'response.json', {'raw': raw, 'reviewer': reviewer})
            try:
                response = json.loads(raw)
                policy = compile_review(root, packet, response)
            except (ValueError, TypeError, KeyError) as exc:
                immutable(attempt/'result.json', {'status': 'rejected', 'reason': str(exc)})
                raise ValueError(f"Evolve review rejected; attempt retained: {exc}") from exc
            decision = {'schema': 'zenith_daily_review_receipt_v1', 'response': response,
                        'reviewer': reviewer, 'policy_sha256': policy['policy_sha256'],
                        'status': 'reviewed_candidate' if response['decision'] == 'candidate' else 'reviewed_no_change',
                        'claim': 'Structure and quoted evidence checked; semantic quality and learning gain are unproven.'}
            decision['review_sha256'] = digest(decision)
            immutable(candidate_path, policy)
            immutable(decision_path, decision)
            immutable(attempt/'result.json', {'status': decision['status']})
            return {**decision, 'episode': index, 'policy_path': str(candidate_path),
                    'instruction': 'Run daily next to prepare the following episode with this frozen policy.'}
        if review is not None:
            raise ValueError("All episodes already reviewed; no pending review")
        return {'stage': 'complete', 'status': 'completed', 'episodes': len(manifest['snapshots'])-1,
                'policy_path': str(policy_path), 'claim': 'Programme execution completed; this is not a measured learning advantage.'}
