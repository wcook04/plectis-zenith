"""Compare four-proposal search pools using two frozen model restart prefixes.

Mixed reuses two attempts per model; homogeneous pools add two same-model
continuations. Selection uses native development only, never old screen winners.
This is search diversity on selected failures, not learned graph composition.
"""
from __future__ import annotations
import argparse
import copy
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import threading

from jsonschema import validate, ValidationError
from research import observation_repair_screen as repair
from zenith.budgeted import OpenRouterBudgetedProvider
from zenith.providers import digest, text_digest, write_json

VERSION = 'zenith_observation_candidate_pool_v1'
MODELS = ('deepseek', 'qwen')
ARMS = ('mixed', 'deepseek4', 'qwen4')


def select(slots, pairs):
    """Maximum executable development accuracy; smallest source hash breaks ties."""
    scored = []
    for slot in slots:
        result = repair.score(slot['proposal']['source'], pairs)
        if slot.get('response_error'):
            for row in result['rows']:
                row['error'] = slot['response_error']['schema_error']
                row['correct'] = False
            result['correct'], result['errors'], result['unsupported'] = 0, result['total'], 0
        scored.append({**slot, 'development': result})
    eligible = [s for s in scored if s['development']['errors'] == 0]
    winner = min(eligible, key=lambda s: (-s['development']['correct'],
        hashlib.sha256(s['proposal']['source'].encode()).hexdigest(), s['slot_id'])) if eligible else None
    champion = winner['proposal'] if winner else dict(repair.UNKNOWN)
    best = winner['development'] if winner else repair.score(champion['source'], pairs)
    chosen = winner['slot_id'] if winner else None
    return {'champion': champion, 'selected_slot': chosen, 'slots': scored,
            'development_summary': {k: best[k] for k in ('correct', 'total', 'errors')}}


def prepare(output, deepseek, qwen, *, seed=20261018, pool_size=16, confirmation_size=32,
            max_cost_usd='0.50'):
    output = Path(output).resolve(); output.mkdir(parents=True, exist_ok=False)
    inputs, models, datasets, parent_dependencies = {}, {}, [], []
    for label, path in zip(MODELS, (deepseek, qwen)):
        path = Path(path).resolve()
        protocol, data, frozen = repair.load_final(path)
        assert len(frozen) == 3, 'exactly three shared failure seeds required'
        inputs[label] = {'path': str(path), 'protocol_sha256': digest(protocol),
            'frozen_sha256': digest(frozen), 'results_sha256': hashlib.sha256((path/'results.json').read_bytes()).hexdigest(),
            'parent_protocol_sha256': protocol['parent_protocol_sha256'],
            'parent_frozen_sha256': protocol['parent_frozen_sha256']}
        models[label] = {k: protocol[k] for k in ('model', 'provider_slug', 'reasoning_effort', 'max_output_tokens')}
        parent_dependencies.append(protocol['runtime_dependencies'])
        datasets.append(data)
        inputs[label]['restart_prefixes'] = [copy.deepcopy(record['arms']['restart']) for record in frozen]
    if digest(datasets[0]) != digest(datasets[1]):
        raise ValueError('parent native evidence and pools differ')
    if parent_dependencies[0] != parent_dependencies[1]:
        raise ValueError('parent executing dependencies differ')
    if any(inputs['deepseek'][k] != inputs['qwen'][k] for k in ('parent_protocol_sha256', 'parent_frozen_sha256')):
        raise ValueError('parent ancestor bindings differ')
    if any(models['deepseek'][k] != models['qwen'][k] for k in ('max_output_tokens', 'reasoning_effort')):
        raise ValueError('matched output allowances and reasoning settings required')
    targets = copy.deepcopy(datasets[0]['targets'])
    old = repair.read(Path(deepseek)/'protocol.json')
    ancestor_path = Path(old['parent'])
    ancestor_protocol = repair.read(ancestor_path/'protocol.json')
    ancestor = repair.read(ancestor_path/'datasets.json')
    ancestor_frozen = repair.read(ancestor_path/'all-frozen.json')
    preparation = repair.read(ancestor_path/'preparation-receipt.json')
    receipt = repair.read(ancestor_path/'all-frozen-receipt.json')
    ancestry = {'protocol_sha256': digest(ancestor_protocol), 'dataset_sha256': digest(ancestor),
                'frozen_sha256': digest(ancestor_frozen)}
    if (ancestry['protocol_sha256'] != old['parent_protocol_sha256'] or
            ancestry['frozen_sha256'] != old['parent_frozen_sha256'] or
            preparation['protocol_sha256'] != ancestry['protocol_sha256'] or
            preparation['dataset_sha256'] != ancestry['dataset_sha256'] or
            ancestor_protocol['dataset_sha256'] != ancestry['dataset_sha256'] or
            receipt['protocol_sha256'] != ancestry['protocol_sha256'] or
            receipt['frozen_sha256'] != ancestry['frozen_sha256'] or
            repair.read(ancestor_path/'results.json')['frozen_sha256'] != ancestry['frozen_sha256']):
        raise ValueError('V5 ancestor custody mismatch')
    forbidden = set()
    for stream in ancestor['public']['streams']:
        forbidden.update(repair.shape(r['actions']) for r in stream['receipts'])
        for partition in stream['partitions'].values():
            forbidden.update(repair.shape(a) for a in partition)
    for record in ancestor_frozen:
        forbidden.update(repair.shape(r['actions']) for r in record['history'])
    for data in datasets:
        for key in ('screen_actions', 'confirmation_actions'):
            forbidden.update(repair.shape(a) for a in data[key])
        for target in data['targets']:
            forbidden.update(repair.shape(r['actions']) for r in target['history'])
            forbidden.update(repair.shape(t['actions']) for t in target['diagnostic']['reduction_trials'])
    screen = repair.action_pool(seed, pool_size, forbidden)
    confirmation = repair.action_pool(seed + 1, confirmation_size, forbidden | {repair.shape(a) for a in screen})
    reused = []
    for label in MODELS:
        parent = Path(inputs[label]['path'])
        api = {r['node_id']: r for r in (repair.read(p) for p in
            (parent/'handoff/api_calls/openrouter_budgeted').glob('*.json'))}
        inputs[label]['parent_cost'] = repair.read(parent/'results.json').get('cost')
        for index, prefix in enumerate(inputs[label]['restart_prefixes']):
            assert len(prefix['rounds']) == 2, 'exact two original restart attempts required'
            for step, entry in enumerate(prefix['rounds']):
                node = f'{targets[index]["id"]}-restart-{step}'
                raw_path = parent/'responses'/f'{node}-raw.json'
                call = api[node]
                raw = repair.read(raw_path)['content']
                assert call['provider_receipt']['response_text'] == raw
                saved_prompt = repair.read(parent/'prompts'/f'{node}.json')
                assert call['prompt_sha256'] == text_digest(json.dumps(saved_prompt['prompt'], ensure_ascii=False))
                assert call['requested_model'] == models[label]['model']
                assert call['requested_provider_slug'] == models[label]['provider_slug']
                try:
                    parsed = json.loads(raw); validate(parsed, repair.PROGRAM_SCHEMA)
                except (ValueError, ValidationError):
                    assert entry['response_error']['raw_content'] == raw
                else:
                    assert parsed == entry['proposal'], 'reused source differs from original response'
                reused.append({'target': targets[index]['id'], 'model_label': label, 'step': step,
                    'entry': entry, 'raw_response_sha256': hashlib.sha256(raw_path.read_bytes()).hexdigest(),
                    'raw_content': raw, 'prompt': saved_prompt, 'reported_cost_usd': call['cost'],
                    'provider_call_id': call['call_id'], 'provider_response_sha256': call['response_sha256'],
                    'provider_projection': {k: call[k] for k in
                        ('run_id', 'node_id', 'requested_model', 'requested_provider_slug', 'prompt_sha256')},
                    'parent_starting_program_sha256': targets[index]['parent_program_sha256']})
    dataset = {'targets': targets, 'screen_actions': screen, 'confirmation_actions': confirmation,
               'inputs': inputs, 'reused': reused, 'ancestor': ancestry,
               'excluded_structures': sorted(forbidden)}
    for index, target in enumerate(targets):
        pairs = repair.development(repair.WorldConfig(**target['config']), target['history'])
        for label in MODELS:
            state = prefix_state(dataset, target, label, pairs)
            if digest(state) != digest(inputs[label]['restart_prefixes'][index]):
                raise ValueError('parent prefix incumbent differs from native development selection')
    write_json(output/'datasets.json', dataset)
    required = repair.dependencies()
    relative = str(Path(__file__).resolve().relative_to(repair.ROOT))
    required[relative] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    protocol = {'schema': VERSION, 'seed': seed, 'models': models, 'max_calls': 12,
        'source_author_model': old['source_author_model'],
        'max_cost_usd': str(max_cost_usd), 'max_output_tokens': models['deepseek']['max_output_tokens'],
        'dataset_sha256': digest(dataset), 'runtime_dependencies': required,
        'source': repair.archive(output, required), 'python_version': sys.version,
        'sqlite_version': sqlite3.sqlite_version,
        'proposal_pools': 'mixed=original two DeepSeek plus original two Qwen; each homogeneous=its original two plus two new same-model continuations. Every pool has four proposal slots/source.',
        'selection_rule': 'Executable candidate with maximum native development-correct; ties choose smallest source SHA256, then smallest slot ID for identical source bytes. No protected outcomes, manual edits or best-old-screen routing.',
        'primary_selection_rule': 'Maximum aggregate screening-correct, then fewer execution errors, then smallest SHA256 of the ordered champion source hashes, then arm ID only for identical programs.',
        'confirmation_comparators': ['unchanged', *ARMS],
        'accounting': {'new_calls': 12, 'reused_unique_calls': 12, 'pool_slot_references': 36,
                       'previous_parent_campaign_calls': 36},
        'selection_boundary': 'Selected V5 failures; shared historical prefixes and differing generation histories/new-versus-old calls. This tests search diversity, not independent trials, zero-cost diversity, learned graph composition or general model superiority.',
        'confirmation_boundary': 'Uniform primary pool fixed by the screening rule and committed before untouched new-structure evaluation of all three frozen pools and unchanged. No further calls, reselection or program edits; conditional local validation on these selected sources.'}
    write_json(output/'protocol.json', protocol)
    write_json(output/'preparation-receipt.json', {'protocol_sha256': digest(protocol), 'dataset_sha256': digest(dataset)})
    return protocol


def audit(protocol, dataset, frozen, partition='screen'):
    result = repair.audit(protocol, dataset, frozen, partition)
    result['schema'] = VERSION
    result['accounting'] = protocol['accounting']
    if partition == 'screen': result['primary_pool'] = primary_pool(frozen, result)
    return result


def primary_pool(frozen, result):
    return min(ARMS, key=lambda arm: (-result['aggregate'][arm]['correct'],
        result['aggregate'][arm]['errors'],
        digest([text_digest(r['arms'][arm]['champion']['source']) for r in frozen]), arm))


def continuation_prompt(target, state, pairs):
    prompt = repair.prompt_for('generic', target, state, pairs, repair.score(state['champion']['source'], pairs))
    prompt['request'] += ' Continue this model\'s own restart trajectory using its incumbent and challenger; no other model\'s source is supplied.'
    return {'system': repair.LANGUAGE, 'prompt': prompt, 'schema': repair.PROGRAM_SCHEMA}


def transition(state, raw, pairs):
    """Preserve raw schema failures and apply the existing development adoption rule."""
    response_error = None
    try:
        proposal = json.loads(raw); validate(proposal, repair.PROGRAM_SCHEMA)
    except (ValueError, ValidationError) as error:
        response_error = {'raw_content': raw, 'schema_error': f'{type(error).__name__}: {error}'}
        proposal = {'source': '', 'scope': 'Invalid response; no repair.', 'lesson': ''}
    old, candidate = repair.score(state['champion']['source'], pairs), repair.score(proposal['source'], pairs)
    if response_error:
        for row in candidate['rows']: row['error'] = response_error['schema_error']
    accepted, regressions = repair.adoption(old, candidate)
    entry = {'proposal': proposal, 'accepted': accepted,
        'unchanged': proposal['source'] == state['champion']['source'], 'regressions': regressions,
        'candidate_summary': {k: candidate[k] for k in ('correct', 'total', 'errors')},
        'feedback': repair.witnesses(pairs, candidate), 'response_error': response_error,
        'old': old, 'candidate': candidate}
    state['rounds'].append(entry)
    if accepted: state['champion'] = proposal
    return entry


def prefix_state(dataset, target, label, pairs):
    state = {'champion': dict(repair.UNKNOWN), 'rounds': []}
    records = sorted((r for r in dataset['reused'] if r['target'] == target['id'] and
                      r['model_label'] == label), key=lambda r: r['step'])
    if [r['step'] for r in records] != [0, 1]: raise ValueError('exact reused prefix required')
    for record in records:
        prompt = repair.prompt_for('restart', target, state, pairs, repair.score(state['champion']['source'], pairs))
        if digest(record['prompt']) != digest({'system': repair.LANGUAGE, 'prompt': prompt, 'schema': repair.PROGRAM_SCHEMA}):
            raise ValueError('reused request evidence or feedback differs')
        if digest(transition(state, record['raw_content'], pairs)) != digest(record['entry']):
            raise ValueError('reused development trajectory differs')
    return state


def replay_records(protocol, dataset, frozen, raw_responses, prompts=None):
    """Portable development replay; no source files or protected action pools read."""
    expected = []; required = set(); checks = 0
    for target in dataset['targets']:
        pairs = repair.development(repair.WorldConfig(**target['config']), target['history'])
        slots, continuations = {}, {}
        for label in MODELS:
            state = prefix_state(dataset, target, label, pairs); slots[label] = []
            for step in range(4):
                node = f'{target["id"]}-{label}-{step}'
                if step >= 2:
                    required.add(node)
                    if prompts is not None and digest(prompts[node]) != digest(continuation_prompt(target, state, pairs)):
                        raise ValueError('construction request evidence or own feedback differs')
                    entry = transition(state, raw_responses[node], pairs)
                else: entry = state['rounds'][step]
                slots[label].append({'slot_id': f'{label}-{step}', 'model_label': label,
                    'origin': 'reused' if step < 2 else 'new', 'proposal': entry['proposal'],
                    'response_error': entry.get('response_error')})
            continuations[label] = state
            checks += sum(len(r['old']['rows']) + len(r['candidate']['rows']) for r in state['rounds'])
        pools = {'mixed': slots['deepseek'][:2] + slots['qwen'][:2],
                 'deepseek4': slots['deepseek'], 'qwen4': slots['qwen']}
        expected.append({'id': target['id'], 'continuations': continuations,
            'arms': {arm: select(pool, pairs) for arm, pool in pools.items()}})
        checks += sum(len(s['development']['rows']) for arm in expected[-1]['arms'].values() for s in arm['slots'])
    if set(raw_responses) != required: raise ValueError('exactly twelve new raw responses required')
    if prompts is not None and set(prompts) != required: raise ValueError('exactly twelve new construction prompts required')
    if digest(expected) != digest(frozen): raise ValueError('development or pool selection replay differs')
    return {'exact_development_replay': True, 'reused_attempts': 12, 'new_attempts': 12,
            'pool_slot_references': 36, 'construction_checks': checks,
            'construction_prompt_checks': len(required) if prompts is not None else 0,
            'protected_evaluation_performed': False}


def run(output, env_file=None, *, providers=None):
    output = Path(output).resolve()
    if (output/'started.json').exists():
        raise ValueError('already started; preserve attempts')
    protocol, dataset = repair.verify(output)
    if providers is None:
        from system.lib.openrouter_free_runtime import load_env_file
        load_env_file(Path(env_file)); providers = {}
        for label, model in protocol['models'].items():
            providers[label] = OpenRouterBudgetedProvider(output/(output.name+'-'+label), model['model'],
                protocol['max_cost_usd'], 12, protocol['max_output_tokens'], output/'budget',
                provider_slug=model['provider_slug'], inference_mode='bounded')
    write_json(output/'started.json', {'protocol_sha256': digest(protocol)})
    stopped, frozen = threading.Event(), []
    try:
        for index, target in enumerate(dataset['targets']):
            pairs = repair.development(repair.WorldConfig(**target['config']), target['history'])
            slots = {label: [] for label in MODELS}; continuations = {}
            for label in MODELS:
                state = copy.deepcopy(dataset['inputs'][label]['restart_prefixes'][index])
                for step, entry in enumerate(state['rounds']):
                    slots[label].append({'slot_id': f'{label}-{step}', 'model_label': label,
                        'origin': 'reused', 'proposal': entry['proposal'], 'response_error': entry.get('response_error')})
                for step in (2, 3):
                    repair.verify(output)
                    artifact = continuation_prompt(target, state, pairs); prompt = artifact['prompt']
                    node = f'{target["id"]}-{label}-{step}'
                    write_json(output/'prompts'/f'{node}.json', artifact)
                    provider = providers[label]
                    run_id = getattr(provider, 'run_dir', output).name
                    raw = provider.ask_ai(json.dumps(prompt, ensure_ascii=False), {
                        'meta': {'session_id': run_id, 'node_id': node}, 'system_prompt': repair.LANGUAGE,
                        'reasoning_effort': protocol['models'][label]['reasoning_effort'],
                        'response_format': {'type': 'json_schema', 'json_schema': {'name': 'observation', 'strict': True, 'schema': repair.PROGRAM_SCHEMA}}}, cancel=stopped)
                    write_json(output/'responses'/f'{node}-raw.json', {'content': raw})
                    entry = transition(state, raw, pairs)
                    proposal, response_error = entry['proposal'], entry['response_error']
                    write_json(output/'responses'/f'{node}-invalid.json' if response_error else
                        output/'responses'/f'{node}.json', response_error or proposal)
                    slots[label].append({'slot_id': f'{label}-{step}', 'model_label': label,
                        'origin': 'new', 'proposal': proposal, 'response_error': response_error})
                    write_json(output/f'{target["id"]}-{label}-partial.json', state)
                continuations[label] = state
            pools = {'mixed': slots['deepseek'][:2] + slots['qwen'][:2],
                     'deepseek4': slots['deepseek'], 'qwen4': slots['qwen']}
            frozen.append({'id': target['id'], 'continuations': continuations,
                'arms': {arm: select(pool, pairs) for arm, pool in pools.items()}})
        repair.verify(output)
        write_json(output/'all-frozen.json', frozen)
        write_json(output/'all-frozen-receipt.json', {'frozen_sha256': digest(frozen),
            'protocol_sha256': digest(protocol), 'construction_complete': True, 'confirmation_started': False})
        result = audit(protocol, dataset, frozen)
        if (output/'budget/budget.json').exists():
            ledger = repair.read(output/'budget/budget.json'); result['calls'] = len(ledger['entries'])
            result['cost'] = {k: ledger[k] for k in ('total_reported_cost_usd', 'total_reserved_usd')}
        write_json(output/'results.json', result); return result
    except BaseException as error:
        stopped.set()
        write_json(output/'failure.json', {'error': f'{type(error).__name__}: {error}', 'automatic_retry': False, 'confirmation_performed': False})
        raise


def confirm(output, arm):
    if arm not in ARMS: raise ValueError('unknown pool')
    output = Path(output)
    protocol, dataset, frozen = repair.load_final(output)
    if arm != primary_pool(frozen, repair.read(output/'results.json')):
        raise ValueError('primary pool must follow the frozen screening rule')
    selection = {'arm': arm, 'protocol_sha256': digest(protocol), 'frozen_sha256': digest(frozen),
        'confirmation_pool_sha256': digest(dataset['confirmation_actions']),
        'comparators': protocol['confirmation_comparators']}
    with (output/'confirmation-selection.json').open('x') as handle: json.dump(selection, handle, sort_keys=True)
    result = replay_confirmation(protocol, dataset, frozen, selection)
    write_json(output/'confirmation.json', result); return result


def replay_confirmation(protocol, dataset, frozen, selection, saved=None):
    if (selection['protocol_sha256'] != digest(protocol) or selection['frozen_sha256'] != digest(frozen) or
            selection['confirmation_pool_sha256'] != digest(dataset['confirmation_actions']) or
            selection['comparators'] != protocol['confirmation_comparators']):
        raise ValueError('confirmation selection custody differs')
    if selection['arm'] != primary_pool(frozen, audit(protocol, dataset, frozen)):
        raise ValueError('confirmation primary differs from the screening rule')
    result = audit(protocol, dataset, frozen, 'confirmation'); result['selection'] = selection
    if saved is not None and digest(result) != digest(saved): raise ValueError('confirmation replay differs')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__); sub = parser.add_subparsers(dest='command', required=True)
    prep = sub.add_parser('prepare'); prep.add_argument('output', type=Path)
    prep.add_argument('--deepseek', type=Path, required=True); prep.add_argument('--qwen', type=Path, required=True)
    prep.add_argument('--seed', type=int, default=20261018); prep.add_argument('--max-cost-usd', default='0.50')
    prep.add_argument('--pool-size', type=int, default=16); prep.add_argument('--confirmation-size', type=int, default=32)
    execute = sub.add_parser('run'); execute.add_argument('output', type=Path); execute.add_argument('--env-file', type=Path, required=True)
    replay = sub.add_parser('replay'); replay.add_argument('output', type=Path)
    confirmation = sub.add_parser('confirm'); confirmation.add_argument('output', type=Path); confirmation.add_argument('--arm', choices=ARMS, required=True)
    args = parser.parse_args()
    if args.command == 'prepare': result = prepare(args.output, args.deepseek, args.qwen, seed=args.seed, max_cost_usd=args.max_cost_usd, pool_size=args.pool_size, confirmation_size=args.confirmation_size)
    elif args.command == 'run': result = run(args.output, args.env_file)
    elif args.command == 'confirm': result = confirm(args.output, args.arm)
    else:
        protocol, dataset, frozen = repair.load_final(args.output)
        raw = {p.name.removesuffix('-raw.json'): repair.read(p)['content']
            for p in (args.output/'responses').glob('*-raw.json')}
        prompts = {p.stem: repair.read(p) for p in (args.output/'prompts').glob('*.json')}
        replay_records(protocol, dataset, frozen, raw, prompts)
        result = audit(protocol, dataset, frozen)
        original = repair.read(args.output/'results.json')
        if digest(result) != digest({k:v for k,v in original.items() if k not in ('cost','calls')}): raise ValueError('screen replay differs')
        result = {'exact_replay': True, 'confirmation_performed': False}
    print(json.dumps({k:v for k,v in result.items() if k not in ('worlds','runtime_dependencies')}, indent=2))


if __name__ == '__main__': main()
