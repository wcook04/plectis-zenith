"""Small, matched repair screen over three retrospectively selected V5 failures.

No authored predictor or repair is supplied. Preparation is offline; run makes
exactly two planned full-program proposals per arm/target, without retries.
Confirmation is separate and cannot influence screening or repair prompts.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import random
import sqlite3
import sys
import threading
from zipfile import ZipFile, ZIP_DEFLATED

from jsonschema import ValidationError, validate

from research.investigator_study import archive_runtime
from research.observation_learning_study import (LANGUAGE, PROGRAM_SCHEMA, UNKNOWN,
    adoption, development, score, witnesses)
from research.observation_world import GOALS, WorldConfig, cases, observe, task_spec
from zenith.budgeted import OpenRouterBudgetedProvider
from zenith.providers import digest, write_json

VERSION = 'zenith_observation_repair_screen_v1'
ARMS = ('generic', 'contrastive', 'restart')
TARGETS = ((4, 'incremental'), (1, 'archive'), (5, 'archive'))
ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return json.loads(Path(path).read_text())


def shape(actions):
    """Ignore literal values/names, retain operations, connections and key equality."""
    keys = {}
    return tuple((a['op'], a.get('connection', 'main'),
                  keys.setdefault(a['key'], len(keys)) if 'key' in a else None) for a in actions)


def action_pool(seed, count, forbidden=()):
    if type(count) is not int or not 1 <= count <= 64:
        raise ValueError('pool size must be between 1 and 64')
    rng = random.Random(seed)
    used, pool = set(forbidden), []
    for attempt in range(count * 200):
        actions, active = [], None
        for step in range(rng.randint(2, 16)):
            connection = active or rng.choice(('main', 'other'))
            op = rng.choice(['put', 'put', 'update', 'delete'] +
                            (['commit', 'rollback'] if active else ['begin']))
            action = {'op': op, 'connection': connection}
            if op in ('put', 'update', 'delete'):
                action['key'] = 'k' + str(rng.randrange(4))
            if op in ('put', 'update'):
                action['value'] = rng.randrange(101)
            if op == 'begin':
                active = connection
            elif op in ('commit', 'rollback'):
                active = None
            actions.append(action)
        identity = shape(actions)
        if identity not in used:
            used.add(identity)
            pool.append(actions)
            if len(pool) == count:
                return pool
    raise ValueError('could not generate enough new action structures')


def diagnose(config, source, history):
    """Minimize a development failure; retain native measurements for every trial."""
    pairs = development(config, history)
    result = score(source, pairs)
    first = next((i for i, row in enumerate(result['rows']) if not row['correct']), None)
    if first is None:
        raise ValueError('selected seed has no development failure')
    case, key = pairs[first]
    original, goal = case['actions'], case['goal']
    measured, trials = {}, []

    def trial(actions):
        try:
            receipt = observe(config, actions)
        except (ValueError, sqlite3.Error) as error:
            trials.append({'actions': actions, 'legal': False, 'error': str(error)})
            return None
        measured[receipt['receipt_sha256']] = receipt
        pair = cases(config, history, [actions], [goal])
        row = score(source, pair)['rows'][0]
        item = {'actions': actions, 'legal': True, 'expected_before_new_measurement': pair[0][1],
                'prediction': row['answer'], 'error': row['error'], 'fails': not row['correct'],
                'native_observed': receipt['observed']}
        trials.append(item)
        return item

    current = list(original)
    # Deterministic one-action deletion reaches a 1-minimal legal witness.
    while current:
        reduced = False
        for index in range(len(current)):
            candidate = current[:index] + current[index + 1:]
            item = trial(candidate)
            if item is not None and item['fails']:
                current, reduced = candidate, True
                break
        if not reduced:
            break
    minimum = trial(current)
    prefixes = [trial(original[:length]) for length in range(len(original) + 1)]
    combined = {r['receipt_sha256']: r for r in history}
    combined.update(measured)
    return list(combined.values()), {
        'goal': goal, 'original_actions': original, 'original_expected': key,
        'original_prediction': result['rows'][first]['answer'], 'minimum': minimum,
        'prefixes': prefixes, 'reduction_trials': trials,
        'boundary': 'Black-box predictions of unchanged model code versus native observations. Empty minima from global abstention are not informative semantic diagnoses; retain original nonempty prefix contrasts.'}


def dependencies():
    """Bound executing imports while retaining the complete historical archive."""
    paths = set()
    for folder in ('zenith', 'system', 'feedback', 'tools', 'variants'):
        paths.update(p for p in (ROOT / folder).rglob('*.py') if p.is_file())
    paths.update(ROOT / 'research' / name for name in
                 ('observation_repair_screen.py', 'observation_world.py',
                  'observation_learning_study.py', 'investigator_study.py'))
    paths.update((ROOT / 'codex').rglob('*.json'))
    paths.add(ROOT / 'master_config.json')
    return {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths)}


def archive(output, required):
    snapshot = archive_runtime(output)
    path = Path(snapshot['path'])
    with ZipFile(path, 'a', compression=ZIP_DEFLATED) as frozen:
        present = set(frozen.namelist())
        for name in required:
            if name not in present:
                frozen.write(ROOT/name, name)
    snapshot['sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
    return snapshot


def prepare(output, parent, model, provider_slug, *, seed=20261017, pool_size=16,
            confirmation_size=32, max_cost_usd='1', max_output_tokens=8192,
            reasoning_effort='none', targets=TARGETS, model_evidence=None):
    if not targets or len(set(targets)) != len(targets):
        raise ValueError('distinct nonempty targets required')
    if not provider_slug or reasoning_effort not in ('none', 'low', 'medium', 'high'):
        raise ValueError('explicit provider route and reasoning effort required')
    output, parent = Path(output).resolve(), Path(parent).resolve()
    output.mkdir(parents=True, exist_ok=False)
    old_protocol, old_data = read(parent/'protocol.json'), read(parent/'datasets.json')
    old_frozen, old_receipt = read(parent/'all-frozen.json'), read(parent/'all-frozen-receipt.json')
    preparation = read(parent/'preparation-receipt.json')
    if (digest(old_protocol) != preparation['protocol_sha256'] or
            digest(old_data) != old_protocol['dataset_sha256'] or
            digest(old_frozen) != old_receipt['frozen_sha256'] or
            digest(old_protocol) != old_receipt['protocol_sha256'] or
            read(parent/'results.json')['frozen_sha256'] != digest(old_frozen)):
        raise ValueError('parent custody mismatch')
    records, forbidden = [], set()
    for stream in old_data['public']['streams']:
        for actions in [r['actions'] for r in stream['receipts']]:
            forbidden.add(shape(actions))
        for partition in stream['partitions'].values():
            forbidden.update(shape(actions) for actions in partition)
    for index, arm in targets:
        saved = old_frozen[index]
        config = WorldConfig(**old_data['private']['configs'][saved['source_id']])
        program = saved['arms'][arm]['champion']
        history, diagnostic = diagnose(config, program['source'], saved['history'])
        forbidden.update(shape(r['actions']) for r in history)
        records.append({'id': f'world-{index:02d}-{arm}', 'source_id': config.source_id,
            'config': old_data['private']['configs'][saved['source_id']],
            'starting_program': program, 'history': history, 'diagnostic': diagnostic,
            'parent_program_sha256': digest(program)})
    screen = action_pool(seed, pool_size, forbidden)
    confirmation = action_pool(seed + 1, confirmation_size, forbidden | {shape(a) for a in screen})
    dataset = {'targets': records, 'screen_actions': screen, 'confirmation_actions': confirmation}
    write_json(output/'datasets.json', dataset)
    required = dependencies()
    protocol = {'schema': VERSION, 'model': model, 'provider_slug': provider_slug,
        'source_author_model': old_protocol['model'], 'parent': str(parent),
        'parent_protocol_sha256': digest(old_protocol), 'parent_frozen_sha256': digest(old_frozen),
        'seed': seed, 'arms': list(ARMS), 'proposals_per_arm': 2, 'max_calls': len(records) * 6,
        'max_cost_usd': str(max_cost_usd), 'max_output_tokens': max_output_tokens,
        'reasoning_effort': reasoning_effort, 'inference_mode': 'bounded',
        'python_version': sys.version, 'sqlite_version': sqlite3.sqlite_version,
        'dataset_sha256': digest(dataset), 'runtime_dependencies': required,
        'source': archive(output, required), 'model_evidence': model_evidence or {},
        'selection_boundary': 'Known V5 failures selected retrospectively. Same measured evidence and two full-code proposals per arm. New structural screening pool; no confirmation evaluation during construction/screening.',
        'confirmation_boundary': 'Explicit one-time frozen program/arm selection before untouched further-structure evaluation on these same selected sources; not general repair-policy or model superiority.',
        'repair_boundary': 'Model-authored code only, no authored solver/repair. No retries/fallback. Cross-model repair is disclosed by source_author_model. Preserve zero scores, unchanged sources, failures and regressions.'}
    write_json(output/'protocol.json', protocol)
    write_json(output/'preparation-receipt.json', {'protocol_sha256': digest(protocol), 'dataset_sha256': digest(dataset)})
    return protocol


def verify(output):
    output = Path(output)
    protocol, dataset = read(output/'protocol.json'), read(output/'datasets.json')
    receipt = read(output/'preparation-receipt.json')
    if digest(protocol) != receipt['protocol_sha256'] or digest(dataset) != protocol['dataset_sha256']:
        raise ValueError('frozen protocol or data changed')
    if protocol['python_version'] != sys.version or protocol['sqlite_version'] != sqlite3.sqlite_version:
        raise ValueError('frozen Python or SQLite version changed')
    archive = Path(protocol['source']['path'])
    if hashlib.sha256(archive.read_bytes()).hexdigest() != protocol['source']['sha256']:
        raise ValueError('frozen archive changed')
    with ZipFile(archive) as frozen:
        for name, expected in protocol['runtime_dependencies'].items():
            if (hashlib.sha256((ROOT/name).read_bytes()).hexdigest() != expected or
                    hashlib.sha256(frozen.read(name)).hexdigest() != expected):
                raise ValueError('executing dependency changed: ' + name)
    return protocol, dataset


def audit(protocol, dataset, frozen, partition='screen'):
    rows = []
    for target, programs in zip(dataset['targets'], frozen):
        config = WorldConfig(**target['config'])
        pairs = cases(config, target['history'], dataset[partition + '_actions'])
        row = {'id': target['id'], 'source_id': target['source_id'],
               'unchanged': score(target['starting_program']['source'], pairs)}
        for arm, state in programs['arms'].items():
            row[arm] = score(state['champion']['source'], pairs)
            row[arm]['code_changed'] = state['champion']['source'] != target['starting_program']['source']
        rows.append(row)
    arms = ('unchanged', *frozen[0]['arms'])
    return {'schema': VERSION, 'partition': partition, 'protocol_sha256': digest(protocol),
        'dataset_sha256': digest(dataset), 'frozen_sha256': digest(frozen), 'worlds': rows,
        'aggregate': {arm: {key: sum(row[arm][key] for row in rows)
                           for key in ('correct', 'total', 'unsupported', 'errors')} for arm in arms},
        'boundary': protocol['confirmation_boundary' if partition == 'confirmation' else 'selection_boundary']}


def prompt_for(arm, target, state, pairs, old):
    prompt = {'documentation': task_spec(), 'history': target['history'],
        'diagnostic_evidence': target['diagnostic'], 'feedback': witnesses(pairs, old),
        'request': 'Author a complete reusable observation program, correcting measured computation failures. Return the full source, scope and lesson; no hand-authored solver is supplied.'}
    if arm != 'restart':
        prompt['champion'] = state['champion']
    if state['rounds']:
        last = state['rounds'][-1]
        prompt['last_challenger'] = {k: last[k] for k in ('proposal', 'accepted', 'candidate_summary', 'feedback', 'response_error')}
    if arm == 'contrastive':
        prompt['focus'] = {'minimum': target['diagnostic']['minimum'],
            'prefixes': target['diagnostic']['prefixes'],
            'instruction': 'Compare native observations with predictions from the supplied code. Inspect which computation prevents any hypothesis from fitting. Empty failure witnesses alone are not semantic explanations. Make a coupled code repair when needed.'}
    elif arm == 'restart':
        prompt['request'] += ' Start afresh from measurements; prior seed source is deliberately not supplied.'
    return prompt


def run(output, env_file=None, *, provider=None):
    output = Path(output).resolve()
    if (output/'started.json').exists():
        raise ValueError('already started; preserve attempts and use a new identity')
    protocol, dataset = verify(output)
    if provider is None:
        from system.lib.openrouter_free_runtime import load_env_file
        load_env_file(Path(env_file))
        provider = OpenRouterBudgetedProvider(output, protocol['model'], protocol['max_cost_usd'],
            protocol['max_calls'], protocol['max_output_tokens'], output/'budget',
            provider_slug=protocol['provider_slug'], inference_mode=protocol['inference_mode'])
    write_json(output/'started.json', {'protocol_sha256': digest(protocol)})
    frozen, phase = [], 'construction'
    stopped = threading.Event()
    try:
        for index, target in enumerate(dataset['targets']):
            config = WorldConfig(**target['config'])
            pairs = development(config, target['history'])
            record = {'id': target['id'], 'arms': {}}
            for offset in range(len(ARMS)):
                arm = ARMS[(index + offset) % len(ARMS)]
                state = {'champion': dict(UNKNOWN) if arm == 'restart' else target['starting_program'], 'rounds': []}
                record['arms'][arm] = state
                for step in range(2):
                    old = score(state['champion']['source'], pairs)
                    prompt = prompt_for(arm, target, state, pairs, old)
                    name = f'{target["id"]}-{arm}-{step}'
                    verify(output)
                    write_json(output/'prompts'/f'{name}.json', {'system': LANGUAGE, 'prompt': prompt, 'schema': PROGRAM_SCHEMA})
                    raw = provider.ask_ai(json.dumps(prompt, ensure_ascii=False), {
                        'meta': {'session_id': output.name, 'node_id': name}, 'system_prompt': LANGUAGE,
                        'reasoning_effort': protocol['reasoning_effort'], 'response_format': {'type': 'json_schema',
                            'json_schema': {'name': 'observation', 'strict': True, 'schema': PROGRAM_SCHEMA}}}, cancel=stopped)
                    write_json(output/'responses'/f'{name}-raw.json', {'content': raw})
                    response_error = None
                    try:
                        proposal = json.loads(raw)
                        validate(proposal, PROGRAM_SCHEMA)
                        write_json(output/'responses'/f'{name}.json', proposal)
                    except (ValueError, ValidationError) as error:
                        response_error = {'raw_content': raw, 'schema_error': f'{type(error).__name__}: {error}'}
                        write_json(output/'responses'/f'{name}-invalid.json', response_error)
                        proposal = {'source': '', 'scope': 'Invalid response; no repair.', 'lesson': ''}
                    candidate = score(proposal['source'], pairs)
                    if response_error:
                        for row in candidate['rows']:
                            row['error'] = response_error['schema_error']
                    accepted, regressions = adoption(old, candidate)
                    state['rounds'].append({'proposal': proposal, 'accepted': accepted,
                        'unchanged': proposal['source'] == state['champion']['source'], 'regressions': regressions,
                        'candidate_summary': {k: candidate[k] for k in ('correct', 'total', 'errors')},
                        'feedback': witnesses(pairs, candidate), 'response_error': response_error,
                        'old': old, 'candidate': candidate})
                    if accepted:
                        state['champion'] = proposal
                    write_json(output/f'target-{index:02d}-partial.json', record)
            frozen.append(record)
        verify(output)
        write_json(output/'all-frozen.json', frozen)
        write_json(output/'all-frozen-receipt.json', {'frozen_sha256': digest(frozen),
            'protocol_sha256': digest(protocol), 'construction_complete': True, 'screening_started': False,
            'confirmation_started': False})
        phase = 'screening'
        result = audit(protocol, dataset, frozen)
        if (output/'budget/budget.json').exists():
            ledger = read(output/'budget/budget.json')
            result['calls'] = len(ledger['entries'])
            result['cost'] = {k: ledger[k] for k in ('total_reported_cost_usd', 'total_reserved_usd')}
        write_json(output/'results.json', result)
        return result
    except BaseException as error:
        stopped.set()
        write_json(output/'failure.json', {'error': f'{type(error).__name__}: {error}', 'phase': phase,
            'automatic_retry': False, 'confirmation_performed': False})
        raise


def load_final(output):
    protocol, dataset = verify(output)
    frozen, receipt = read(Path(output)/'all-frozen.json'), read(Path(output)/'all-frozen-receipt.json')
    if (digest(frozen) != receipt['frozen_sha256'] or digest(protocol) != receipt['protocol_sha256']
            or read(Path(output)/'results.json')['frozen_sha256'] != digest(frozen)):
        raise ValueError('frozen programs changed')
    return protocol, dataset, frozen


def confirm(output, arm):
    if arm not in ARMS:
        raise ValueError('unknown arm')
    output = Path(output)
    protocol, dataset, frozen = load_final(output)
    selection = {'arm': arm, 'protocol_sha256': digest(protocol), 'frozen_sha256': digest(frozen),
                 'confirmation_pool_sha256': digest(dataset['confirmation_actions'])}
    # Exclusive creation commits the choice before touching confirmation outcomes.
    with (output/'confirmation-selection.json').open('x') as handle:
        json.dump(selection, handle, sort_keys=True)
    chosen = [{'id': record['id'], 'arms': {arm: record['arms'][arm]}} for record in frozen]
    result = audit(protocol, dataset, chosen, 'confirmation')
    result['selection'] = selection
    write_json(output/'confirmation.json', result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    prep = sub.add_parser('prepare')
    prep.add_argument('output', type=Path)
    prep.add_argument('--parent', type=Path, required=True)
    prep.add_argument('--model', required=True)
    prep.add_argument('--provider', required=True)
    prep.add_argument('--seed', type=int, default=20261017)
    prep.add_argument('--pool-size', type=int, default=16)
    prep.add_argument('--confirmation-size', type=int, default=32)
    prep.add_argument('--max-cost-usd', default='1')
    prep.add_argument('--max-output-tokens', type=int, default=8192)
    prep.add_argument('--reasoning-effort', choices=('none', 'low', 'medium', 'high'), default='none')
    execute = sub.add_parser('run'); execute.add_argument('output', type=Path); execute.add_argument('--env-file', type=Path, required=True)
    replay = sub.add_parser('replay'); replay.add_argument('output', type=Path)
    confirmation = sub.add_parser('confirm'); confirmation.add_argument('output', type=Path); confirmation.add_argument('--arm', choices=ARMS, required=True)
    args = parser.parse_args()
    if args.command == 'prepare':
        result = prepare(args.output, args.parent, args.model, args.provider, seed=args.seed,
            pool_size=args.pool_size, confirmation_size=args.confirmation_size,
            max_cost_usd=args.max_cost_usd, max_output_tokens=args.max_output_tokens, reasoning_effort=args.reasoning_effort)
    elif args.command == 'run':
        result = run(args.output, args.env_file)
    elif args.command == 'confirm':
        result = confirm(args.output, args.arm)
    else:
        protocol, dataset, frozen = load_final(args.output)
        result = audit(protocol, dataset, frozen)
        original = read(args.output/'results.json')
        if digest(result) != digest({k: v for k, v in original.items() if k not in ('cost', 'calls')}):
            raise ValueError('screen replay differs')
        result = {'exact_replay': True, 'confirmation_performed': False}
    print(json.dumps({k: v for k, v in result.items() if k not in ('worlds', 'runtime_dependencies')}, indent=2))


if __name__ == '__main__':
    main()
