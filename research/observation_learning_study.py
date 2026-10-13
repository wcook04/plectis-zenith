"""Learn source-bound observation programs and compare equal-budget memories.

The model proposes native experiments and ordinary Python. The host records
measurements, executes candidates and retains every revision. Protected tests
run only after every construction call has finished. No model-supplied answer
is an oracle, and no failed provider call is retried.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import random
import sqlite3
import threading
from zipfile import ZipFile

from jsonschema import ValidationError, validate

from zenith.budgeted import OpenRouterBudgetedProvider
from zenith.investigation_program import execute
from zenith.providers import digest, write_json
from research.investigator_study import archive_runtime
from research.observation_world import WorldConfig, cases, make_dataset, observe, task_spec, GOALS

VERSION = 'zenith_observation_learning_v4'
ARMS = ('incremental', 'archive', 'fresh')
UNKNOWN = {'source': 'def investigate(context, acquire):\n    return {"value": None, "unresolved": True}\n',
           'scope': 'No learned source model.', 'lesson': ''}
PROGRAM_SCHEMA = {'type': 'object', 'properties': {
    'source': {'type': 'string', 'description': 'Complete executable Python program defining investigate(context, acquire), including the function body. Never a label or bare signature.'},
    'scope': {'type': 'string', 'description': 'Short statement of the supported scope.'},
    'lesson': {'type': 'string', 'description': 'Short technical account of the revision.'}},
    'required': ['source', 'scope', 'lesson'], 'additionalProperties': False}
ACTION_SCHEMA = {'type': 'object', 'properties': {
    'op': {'type': 'string', 'enum': ['put', 'update', 'delete', 'begin', 'commit', 'rollback']},
    'connection': {'type': 'string', 'enum': ['main', 'other']},
    'key': {'type': ['string', 'null']}, 'value': {'type': ['integer', 'null']}},
    'required': ['op', 'connection', 'key', 'value'], 'additionalProperties': False}
PROBE_SCHEMA = {'type': 'object', 'properties': {
    'experiments': {'type': 'array', 'minItems': 3, 'maxItems': 3, 'items': {
        'type': 'array', 'maxItems': 32, 'items': ACTION_SCHEMA}},
    'purpose': {'type': 'string'}}, 'required': ['experiments', 'purpose'],
    'additionalProperties': False}
LANGUAGE = '''Write investigate(context, acquire) in ordinary restricted Python.
Put the COMPLETE EXECUTABLE PYTHON PROGRAM in the JSON source field. Include
the function definition and body, never a label, description or bare signature.
The scope and lesson fields contain short technical claims.
context has source_id, actions, goal and documentation. acquire("history") returns
all calibration receipts for this source. Use no case identifiers, private data,
external tools or imports. Infer behavior from the actual observations and public
documentation; generalize to new action combinations and values. Return exactly
{"value": integer or null, "unresolved": boolean}. Do not merely memorize probe
outputs. Resolve a goal only when the evidence supports it; source identity binds
the evidence, it does not explain behavior. scope and lesson are short technical
claims, not a chain-of-thought transcript.

Only function definitions at module level. No imports, annotations, decorators,
default arguments, private names, exceptions, while loops, I/O or global state.
For loops, comprehensions, lambda, nonlocal closure variables, del of local
names or container entries, and arithmetic except power are permitted.
Builtins: abs all any bool dict enumerate float int isinstance len list max min
range reversed round set sorted str sum tuple zip.
Methods: get items keys values append extend sort lower upper strip split
setdefault add discard copy count index pop remove clear update.
At most eight acquisitions per query. Source limit 60000 UTF8 bytes. Programs
run in a fresh resource-limited process. Emit one JSON object, never an array.
'''


def normalize_probe(actions):
    """Documented wire decoding, not a repair of invalid actions."""
    return [{k: v for k, v in action.items() if v is not None} for action in actions]


def development(config, receipts):
    # These labels are observed externally, not inferred from private variants.
    pairs = []
    for receipt in receipts:
        for goal in GOALS:
            case = {'id': digest([receipt['receipt_sha256'], goal]),
                    'source_id': config.source_id, 'actions': receipt['actions'],
                    'goal': goal, 'documentation': task_spec(), 'tables': {'history': receipts}}
            pairs.append((case, {'value': receipt['observed'][goal], 'unresolved': False}))
    return pairs


def score(source, pairs):
    try:
        rows = execute(source, [case for case, key in pairs], answer_contract='json')
    except (ValueError, SyntaxError) as error:
        rows = [{'answer': None, 'error': f'{type(error).__name__}: {error}', 'trace': []}
                for pair in pairs]
    for row, (case, key) in zip(rows, pairs):
        answer = row['answer']
        valid = (isinstance(answer, dict) and set(answer) == {'value', 'unresolved'}
                 and type(answer['unresolved']) is bool
                 and (answer['value'] is None or type(answer['value']) is int)
                 and ((answer['value'] is None) == answer['unresolved']))
        if not valid and row['error'] is None:
            row['error'] = 'Invalid observation answer: require integer value or explicit unresolved null.'
        row.update(id=case['id'], expected=key, correct=bool(valid and answer == key),
                   unsupported=bool(valid and not answer['unresolved'] and key['unresolved']))
    return {'correct': sum(r['correct'] for r in rows), 'total': len(rows),
            'unsupported': sum(r['unsupported'] for r in rows),
            'errors': sum(r['error'] is not None for r in rows), 'rows': rows}


def witnesses(pairs, result, count=6):
    records = [{'actions': case['actions'], 'goal': case['goal'], 'expected': key,
                'actual': row['answer'], 'error': row['error'], 'correct': row['correct']}
               for (case, key), row in zip(pairs, result['rows'])]
    return ([r for r in records if not r['correct']][:count]
            + [r for r in records if r['correct']][:2])


def adoption(old, candidate):
    """Global development score; ties allow neutral representation revisions.

    Regressions are reported, not a blanket veto. The development score is not
    evidence of protected generalization. Every arm uses this identical rule.
    """
    regressions = sum(a['correct'] and not b['correct']
                      for a, b in zip(old['rows'], candidate['rows']))
    accepted = candidate['errors'] == 0 and candidate['correct'] >= old['correct']
    return accepted, regressions


def compile_prompt(arm, history, champion, records, pairs, old):
    prompt = {'documentation': task_spec(), 'history': history,
              'champion': champion, 'champion_score': {k: old[k] for k in ('correct', 'total', 'errors')},
              'champion_feedback': witnesses(pairs, old),
              'request': 'Author a complete reusable observation program. Use the measured errors to change the computation, including coupled changes when necessary. A correct calibration score alone does not establish a correct model of new compositions. Preserve uncertainty where evidence cannot determine a goal.'}
    if arm == 'archive' or arm == 'fresh':
        prompt['construction_archive'] = [{'proposal': r['proposal'], 'accepted': r['accepted'],
            'development_score': r['candidate_summary'], 'feedback': r['feedback'],
            'response_error': r.get('response_error')}
            for r in records]
    elif records:
        # Search continues from the actual most recent candidate, even if rejected.
        last = records[-1]
        prompt['last_challenger'] = {'proposal': last['proposal'], 'accepted': last['accepted'],
            'development_score': last['candidate_summary'], 'feedback': last['feedback'],
            'response_error': last.get('response_error')}
    return prompt


def prepare(output, model, provider_slug, *, seed=20261013, worlds=6,
            max_cost_usd='2', max_output_tokens=8192, model_evidence=None,
            provider_slugs=None, workers=1, reasoning_effort='low'):
    routes = list(provider_slugs or [provider_slug])
    if type(workers) is not int or not 1 <= workers <= 3 or not routes or len(set(routes)) != len(routes):
        raise ValueError('one to three workers and distinct pinned routes required')
    if reasoning_effort not in ('none', 'low', 'medium', 'high'):
        raise ValueError('invalid reasoning effort')
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    dataset = make_dataset(seed, worlds)
    write_json(output/'datasets.json', dataset)
    protocol = {'schema': VERSION, 'model': model, 'provider_slug': provider_slug,
        'provider_slugs': routes,
        'world_providers': [routes[(i + 2 * (i // 3)) % len(routes)] for i in range(worlds)],
        'route_allocation': 'Cyclic counterbalance across three-source blocks; with six worlds and three routes each route sees both trigger states and different conflict/counter settings. Route is fixed within each paired source comparison.',
        'workers': workers, 'inference_mode': 'bounded' if workers > 1 else 'serial',
        'reasoning_effort': reasoning_effort, 'max_cost_usd': str(max_cost_usd),
        'max_output_tokens': max_output_tokens, 'max_calls': worlds * 21,
        'worlds': worlds, 'seed': seed, 'episodes': 3, 'probes_per_episode': 3,
        'proposals_per_episode': 2, 'arms': list(ARMS), 'dataset_sha256': digest(dataset),
        'source': archive_runtime(output),
        'acquisition': 'One independent model planner proposes three experiments per episode. Host executes these and one fixed challenge. Exact same resulting receipts are broadcast to all arms. Invalid probes are retained as failed experiments, never replaced. This isolates evidence organization, not a causal advantage of acquisition policy.',
        'construction': 'Incremental and execution-enabled archive each receive two proposals at each of three growing evidence prefixes. Fresh compiler receives all final evidence and six proposals. Identical program interface, development scoring, candidate acceptance and total proposal allowance; no cross-arm messages.',
        'promotion': 'Latest valid candidate with development exact score >= champion wins; record all regressions and unchanged hashes. Ties are revisions, not measured improvements. Rejected candidates remain available as search parents. No protected feedback.',
        'primary': 'Final protected exact accuracy per configured world, paired incremental minus archive and incremental minus fresh. Worlds are conditional replications in one native software family, not independent domains.',
        'checkpoint': 'After the first episode across all worlds, drain every request. Every world must have an executable candidate and a valid model probe, and the cohort must contain at least one correct observed answer. Retain difficult worlds with zero correct answers: learning success is an outcome, not a per-world admission requirement. This engineering gate uses development evidence only, never protected outcomes or a winning-arm selection. Finish all trajectories before judging the comparison.',
        'controls': 'Replay first accepted checkpoint with final raw evidence (freeze-and-grow), final program with empty evidence, and a cold abstaining program. Evaluate every checkpoint only after ALL model construction calls finish.',
        'oracle': 'Actual native SQLite execution and independent committed-state reader. Goal-specific identification conditional on a disclosed 18-member native family. Actual source configurations and protected outcomes never appear in model prompts; candidate programs and the evaluator implementation are not supplied.',
        'inference': 'At most three independent worlds in flight and one request per exact endpoint across the host. All arms of a world use the same pinned route. Dependencies within a world remain sequential. Shared budget reservations and settlement are atomic. No automatic retries or model/provider fallback. A failure stops admission and drains active requests. Raw content and actual schema errors reach subsequent repair prompts.',
        'uncertainty': 'World-level paired bootstrap is descriptive of these configured sources. Protected compositions are authored and bounded; no claim of arbitrary semantic discovery, broad intelligence or autonomous ontology invention.',
        'model_evidence': model_evidence or {}}
    write_json(output/'protocol.json', protocol)
    write_json(output/'preparation-receipt.json', {'protocol_sha256': digest(protocol),
                                                 'dataset_sha256': digest(dataset)})
    return protocol


def verify_frozen(output):
    output = Path(output)
    protocol = json.loads((output/'protocol.json').read_text())
    dataset = json.loads((output/'datasets.json').read_text())
    preparation = json.loads((output/'preparation-receipt.json').read_text())
    if digest(protocol) != preparation['protocol_sha256']:
        raise ValueError('frozen protocol changed')
    if digest(dataset) != protocol['dataset_sha256']:
        raise ValueError('frozen dataset changed')
    archive = Path(protocol['source']['path'])
    if hashlib.sha256(archive.read_bytes()).hexdigest() != protocol['source']['sha256']:
        raise ValueError('source archive changed')
    root = Path(__file__).resolve().parents[1]
    with ZipFile(archive) as frozen:
        for name in frozen.namelist():
            if (root/name).read_bytes() != frozen.read(name):
                raise ValueError('runtime changed after preparation: ' + name)
    return protocol, dataset


def paired_summary(rows, left, right):
    differences = [r[left]['correct']/r[left]['total'] - r[right]['correct']/r[right]['total']
                   for r in rows]
    rng = random.Random(81173)
    means = sorted(sum(rng.choices(differences, k=len(differences)))/len(differences)
                   for sample in range(10000))
    return {'worlds': len(rows), 'mean_accuracy_difference': sum(differences)/len(differences),
            'paired_bootstrap_95_percentile': [means[249], means[9749]],
            'wins': sum(d > 0 for d in differences), 'ties': sum(d == 0 for d in differences),
            'losses': sum(d < 0 for d in differences), 'per_world': differences}


def audit(output, protocol, dataset, frozen):
    """No calls and no learner feedback; consumes only frozen source objects."""
    results = []
    for stream, record in zip(dataset['public']['streams'], frozen):
        config = WorldConfig(**dataset['private']['configs'][stream['source_id']])
        history = record['history']
        pairs = cases(config, history, stream['partitions']['eval'])
        row = {'source_id': config.source_id, 'history_sha256': digest(history)}
        for arm in ARMS:
            current = record['arms'][arm]
            row[arm] = score(current['champion']['source'], pairs)
            row[arm + '_checkpoints'] = [score(checkpoint['program']['source'],
                cases(config, checkpoint['history'], stream['partitions']['eval']))
                for checkpoint in current['checkpoints']]
        initial = record['arms']['incremental']['checkpoints'][0]['program']['source']
        final = record['arms']['incremental']['champion']['source']
        row['freeze_and_grow'] = score(initial, pairs)
        # Key remains the final-evidence target: this is dependence on supplied
        # history, not a claim that deleting history invalidates compiled knowledge.
        empty = [(dict(case, tables={'history': []}), key) for case, key in pairs]
        row['empty_history'] = score(final, empty)
        row['cold'] = score(UNKNOWN['source'], pairs)
        results.append(row)
    summary = {'schema': VERSION, 'protocol_sha256': digest(protocol),
        'frozen_sha256': digest(frozen), 'worlds': results,
        'comparisons': {name: paired_summary(results, 'incremental', name)
                        for name in ('archive', 'fresh', 'freeze_and_grow')},
        'aggregate': {arm: {key: sum(row[arm][key] for row in results)
                           for key in ('correct', 'total', 'unsupported', 'errors')}
                      for arm in (*ARMS, 'freeze_and_grow', 'empty_history', 'cold')}}
    return summary


def engineering_checkpoint(records):
    """Predeclared admission gate; no protected cases, keys or arm selection."""
    diagnostics = []
    for record in records:
        rounds = [r for arm in ('incremental', 'archive') for r in record['arms'][arm]['rounds']]
        valid = sum(r['candidate_summary']['errors'] == 0 for r in rounds)
        useful = sum(r['candidate_summary']['errors'] == 0 and r['candidate_summary']['correct'] > 0
                     for r in rounds)
        probes = sum('receipt' in p and 'authority' not in p for p in record['probe_log'])
        diagnostics.append({'source_id': record['source_id'], 'valid_programs': valid,
                            'programs_above_cold_development': useful,
                            'measured_model_probes': probes})
    return {'continue': bool(records)
            and all(r['valid_programs'] > 0 and r['measured_model_probes'] > 0 for r in diagnostics)
            and any(r['programs_above_cold_development'] > 0 for r in diagnostics),
            'basis': 'first-prefix development execution only; no protected outcomes',
            'worlds': diagnostics}


def run(output, env_file=None, *, provider=None):
    output = Path(output).resolve()
    if (output/'started.json').exists():
        raise ValueError('study already started; preserve failures and prepare a new identity')
    protocol, dataset = verify_frozen(output)
    if provider is None:
        from system.lib.openrouter_free_runtime import load_env_file
        load_env_file(Path(env_file))
        providers = [OpenRouterBudgetedProvider(output/f'provider-world-{index:02d}',
            protocol['model'], protocol['max_cost_usd'], protocol['max_calls'],
            protocol['max_output_tokens'], output/'budget', provider_slug=route,
            inference_mode=protocol['inference_mode'])
            for index, route in enumerate(protocol['world_providers'])]
    else:
        providers = [provider] * protocol['worlds']
    stopped = threading.Event()
    failure_lock = threading.Lock()
    failures = []
    write_json(output/'started.json', {'protocol_sha256': digest(protocol),
                                     'dataset_sha256': digest(dataset)})

    response_errors = {}

    def ask(index, name, prompt, schema, system):
        if stopped.is_set():
            raise RuntimeError("campaign admission stopped after a prior failure")
        write_json(output/'prompts'/f'{name}.json', {'system': system, 'prompt': prompt, 'schema': schema})
        raw = providers[index].ask_ai(json.dumps(prompt, ensure_ascii=False), {
            'meta': {'session_id': getattr(providers[index], 'run_dir', output).name, 'node_id': name}, 'system_prompt': system,
            'reasoning_effort': protocol['reasoning_effort'], 'response_format': {
                'type': 'json_schema', 'json_schema': {'name': 'observation', 'strict': True, 'schema': schema}}}, cancel=stopped)
        write_json(output/'responses'/f'{name}-raw.json', {'content': raw})
        try:
            answer = json.loads(raw)
            validate(answer, schema)
        except (ValueError, ValidationError) as error:
            response_errors[name] = {'raw_content': raw, 'schema_error': f'{type(error).__name__}: {error}'}
            write_json(output/'responses'/f'{name}-invalid.json', response_errors[name])
            print(json.dumps({'event': 'response_invalid', 'name': name}), flush=True)
            return None
        write_json(output/'responses'/f'{name}.json', answer)
        print(json.dumps({'event': 'response', 'name': name}), flush=True)
        return answer

    frozen = []
    records = [{'source_id': stream['source_id'], 'provider_slug': protocol['world_providers'][index],
        'history': [], 'probe_log': [],
        'arms': {arm: {'champion': dict(UNKNOWN), 'rounds': [], 'checkpoints': []} for arm in ARMS}}
        for index, stream in enumerate(dataset['public']['streams'])]

    def construct(index, episode):
        stream = dataset['public']['streams'][index]
        config = WorldConfig(**dataset['private']['configs'][stream['source_id']])
        record = records[index]
        def proposals(arm, episode, count):
            state = record['arms'][arm]
            pairs = development(config, record['history'])
            for step in range(count):
                old = score(state['champion']['source'], pairs)
                prompt = compile_prompt(arm, record['history'], state['champion'], state['rounds'], pairs, old)
                name = f'world-{index:02d}-{arm}-{episode}-{step}'
                proposal = ask(index, name, prompt, PROGRAM_SCHEMA, LANGUAGE)
                response_error = response_errors.get(name)
                if proposal is None:
                    proposal = {'source': '', 'scope': 'Invalid model response; no repair.', 'lesson': ''}
                candidate = score(proposal['source'], pairs)
                if response_error is not None:
                    for row in candidate['rows']:
                        row['error'] = response_error['schema_error']
                accepted, regressions = adoption(old, candidate)
                entry = {'proposal': proposal, 'parent_sha256': digest(state['champion']),
                    'candidate_sha256': digest(proposal), 'accepted': accepted, 'regressions': regressions,
                    'unchanged': proposal['source'] == state['champion']['source'],
                    'candidate_summary': {k: candidate[k] for k in ('correct', 'total', 'errors')},
                    'feedback': witnesses(pairs, candidate), 'old': old, 'candidate': candidate,
                    'response_error': response_error}
                state['rounds'].append(entry)
                if accepted:
                    state['champion'] = proposal
                write_json(output/f'world-{index:02d}-partial.json', record)
            state['checkpoints'].append({'program': state['champion'],
                'history': list(record['history']), 'program_sha256': digest(state['champion'])})

        if episode is None:
            proposals('fresh', 0, protocol['episodes'] * protocol['proposals_per_episode'])
            write_json(output/f'world-{index:02d}-frozen.json', record)
            print(json.dumps({'event': 'world_frozen', 'index': index}), flush=True)
        else:
            plan = ask(index, f'world-{index:02d}-probes-{episode}', {
                'documentation': task_spec(), 'history': record['history'],
                'previous_experiments': record['probe_log'],
                'last_plan_response_error': response_errors.get(f'world-{index:02d}-probes-{episode-1}'),
                'request': 'Propose exactly three legal experiments that distinguish plausible source behaviors not yet separated by the observations. Use null for key/value on operations where those fields do not apply. Experiments each start fresh. Prefer informative combinations, including effects which may cancel in committed state but remain in the channel. No answers are requested.'},
                PROBE_SCHEMA, 'Design discriminating experiments for an unknown measurement source. Return one JSON object.')
            for probe in (plan or {}).get('experiments', []):
                actions = normalize_probe(probe)
                try:
                    receipt = observe(config, actions)
                    record['history'].append(receipt)
                    record['probe_log'].append({'episode': episode, 'actions': actions, 'receipt': receipt})
                except (ValueError, sqlite3.Error) as error:
                    record['probe_log'].append({'episode': episode, 'actions': actions, 'error': str(error)})
                write_json(output/f'world-{index:02d}-partial.json', record)
            challenge = stream['partitions']['challenge'][episode]
            receipt = observe(config, challenge)
            record['history'].append(receipt)
            record['probe_log'].append({'episode': episode, 'authority': 'independent fixed challenge', 'receipt': receipt})
            write_json(output/f'world-{index:02d}-partial.json', record)
            # Rotate temporal order without granting an arm another arm's output.
            order = ('incremental', 'archive') if (index + episode) % 2 == 0 else ('archive', 'incremental')
            for arm in order:
                proposals(arm, episode, protocol['proposals_per_episode'])

    def guarded(index, episode):
        try:
            construct(index, episode)
        except Exception as error:
            with failure_lock:
                failures.append(error)
                stopped.set()
            raise

    def wave(episode):
        # Exiting the executor drains running work before recording a decision.
        with ThreadPoolExecutor(max_workers=protocol['workers']) as pool:
            futures = [pool.submit(guarded, index, episode) for index in range(len(records))]
            for future in futures:
                try:
                    future.result()
                except Exception:
                    # Drain every worker, then report the initiating failure,
                    # rather than a lower-index sibling's cancellation.
                    pass
        if failures:
            raise failures[0]

    phase = 'construction'
    try:
        for episode in range(protocol['episodes']):
            wave(episode)
            if episode == 0:
                gate = engineering_checkpoint(records)
                write_json(output/'pilot-checkpoint.json', gate)
                print(json.dumps({'event': 'pilot_checkpoint', **gate}), flush=True)
                if not gate['continue']:
                    raise RuntimeError('first-episode engineering checkpoint failed; no further inference')
        wave(None)
        frozen = records
        write_json(output/'all-frozen.json', frozen)
        write_json(output/'all-frozen-receipt.json', {'frozen_sha256': digest(frozen),
            'protocol_sha256': digest(protocol), 'construction_complete': True,
            'protected_audit_started': False})
        phase = 'protected_audit'
        result = audit(output, protocol, dataset, frozen)
        if (output/'budget/budget.json').exists():
            budget = json.loads((output/'budget/budget.json').read_text())
            result['cost'] = {k: budget[k] for k in ('total_reported_cost_usd', 'total_reserved_usd') if k in budget}
            result['calls'] = len(budget['entries'])
        write_json(output/'results.json', result)
        return result
    except Exception as error:
        write_json(output/'failure.json', {'error': f'{type(error).__name__}: {error}', 'automatic_retry': False,
            'completed_worlds': len(list(output.glob('world-*-frozen.json'))), 'protected_evaluation_performed': phase == 'protected_audit'})
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    prep = commands.add_parser('prepare')
    prep.add_argument('output', type=Path)
    prep.add_argument('--model', required=True)
    prep.add_argument('--provider', required=True)
    prep.add_argument('--worlds', type=int, default=6)
    prep.add_argument('--providers', nargs='+')
    prep.add_argument('--workers', type=int, default=1)
    prep.add_argument('--reasoning-effort', choices=['none', 'low', 'medium', 'high'], default='low')
    prep.add_argument('--seed', type=int, default=20261013)
    prep.add_argument('--max-cost-usd', default='2')
    execute_parser = commands.add_parser('run')
    execute_parser.add_argument('output', type=Path)
    execute_parser.add_argument('--env-file', type=Path, required=True)
    replay = commands.add_parser('replay')
    replay.add_argument('output', type=Path)
    args = parser.parse_args()
    if args.command == 'prepare':
        result = prepare(args.output, args.model, args.provider, seed=args.seed,
                         worlds=args.worlds, max_cost_usd=args.max_cost_usd,
                         provider_slugs=args.providers, workers=args.workers, reasoning_effort=args.reasoning_effort)
        print(json.dumps({'protocol': str(args.output/'protocol.json'), 'max_calls': result['max_calls']}))
    elif args.command == 'run':
        result = run(args.output, args.env_file)
        print(json.dumps({k: result[k] for k in ('aggregate', 'comparisons', 'cost', 'calls')}))
    else:
        protocol, dataset = verify_frozen(args.output)
        original = json.loads((args.output/'results.json').read_text())
        frozen = json.loads((args.output/'all-frozen.json').read_text())
        freeze_receipt = json.loads((args.output/'all-frozen-receipt.json').read_text())
        if (freeze_receipt['frozen_sha256'] != digest(frozen)
                or freeze_receipt['protocol_sha256'] != digest(protocol)
                or original['frozen_sha256'] != digest(frozen)):
            raise ValueError('frozen programs changed')
        reproduced = audit(args.output, protocol, dataset, frozen)
        original_core = {k: v for k, v in original.items() if k not in ('cost', 'calls')}
        if digest(original_core) != digest(reproduced):
            raise ValueError('offline replay differs')
        print(json.dumps({'exact_replay': True, 'worlds': len(frozen)}))


if __name__ == '__main__':
    main()
