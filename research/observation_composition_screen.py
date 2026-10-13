"""A bounded native savepoint composition screen; no inference during prepare.

Reuse the frozen native SQLite fixture, ordinary Python executor and budgeted
provider. Nodes contain model-written code and exact dependencies, never native
settings. Flat and fresh controls receive the same learned primitive code.
"""
from __future__ import annotations

import argparse
import ast
from dataclasses import asdict
from functools import lru_cache
import hashlib
import itertools
import json
from pathlib import Path
import random
import re
import sqlite3
from zipfile import ZipFile

from jsonschema import ValidationError, validate

from research.investigator_study import archive_runtime
from research.observation_learning_study import LANGUAGE, UNKNOWN, adoption, score, witnesses
from research.observation_world import (CONFLICTS, COUNTERS, GOALS, MAX_ACTIONS, WorldConfig,
    _actions, _run_native, discovery_sequences, task_spec as ordinary_spec, world)
from zenith.budgeted import OpenRouterBudgetedProvider
from zenith.investigation_program import validate_source
from zenith.providers import digest, write_json

VERSION = 'zenith_native_composition_screen_v1'
ARMS = ('graph', 'flat', 'fresh')
SCHEMA = {'type': 'object', 'properties': {
    'source': {'type': 'string', 'description': 'Complete ordinary Python function bodies.'},
    'scope': {'type': 'string'}, 'lesson': {'type': 'string'},
    'dependencies': {'type': 'array', 'items': {'type': 'string'}, 'uniqueItems': True}},
    'required': ['source', 'scope', 'lesson', 'dependencies'], 'additionalProperties': False}


def transport_schema(schema):
    """Only omit provider-unsupported uniqueness; host validation retains it."""
    if isinstance(schema, dict):
        return {key: transport_schema(value) for key, value in schema.items() if key != 'uniqueItems'}
    if isinstance(schema, list):
        return [transport_schema(value) for value in schema]
    return schema


TRANSPORT_SCHEMA = transport_schema(SCHEMA)
PRIMITIVE_INTERFACE = '''Additionally define transition(state, action, context, acquire)
and readout(state, context, acquire). transition initializes your own state when
state is None, and applies ONE ordinary action. readout returns the requested
value/unresolved answer. investigate runs your transitions and readout. State
representation, source inference and numerical semantics are yours to implement.
The qualification driver starts with state=None, passes each action to transition,
then calls readout on the resulting state. For ZERO actions it calls readout(None,
context, acquire) directly: readout MUST handle this empty-source initial state.
context is always the normal query object, including actions, source_id and goal;
context is never None. The driver is exactly:
    state = None
    for action in context["actions"]:
        state = transition(state, action, context, acquire)
    return readout(state, context, acquire)
Your exports and investigate must agree on every observed sequence, including [];
do not depend on investigate-only initialization before readout can run.
Infer a source only from receipts. Cache acquired evidence in your own state if
needed: the whole query permits eight acquisitions. These two exports will be
reused by a later caller. No savepoint implementation is requested at this stage.
dependencies must be []. No module imports or external solver code are provided.'''


def task_spec():
    return ordinary_spec().replace('Transactions cannot nest.',
        'BEGIN transactions cannot nest; the additional savepoint interface below can nest.').replace(
        'no candidate programs, simulator or solver library are supplied.',
        'private settings and oracle implementations are never supplied. Some arms receive previously model-written primitives as described in their prompt.') + '''
Additional legal actions: savepoint(name), rollback_to(name), release(name), with
name one of s0, s1, s2. They issue native SQLite SAVEPOINT, ROLLBACK TO and RELEASE
on the selected connection. Names are unique while active, at most three deep.
These are actual SQL operations, not source-dependent macros. Native savepoint
behavior is fixed across the disclosed family; actual insertion/counter settings
remain private. Infer behavior from observed experiments and native SQL semantics.
The separate reader sees only committed state. Some queries end with an open
savepoint or transaction. Evaluation is conditional on this family, never an
equivalence claim about unrestricted SQL. Preserve irreversible measurement
effects when reasoning about reversible row effects.
'''


def normalize(actions):
    """Validate the entire transaction stack before generating ANY SQL text."""
    actions = list(actions)
    if len(actions) > MAX_ACTIONS:
        raise ValueError('action budget exceeded')
    active, explicit, stack = None, False, []
    public, native = [], []
    for raw in actions:
        if not isinstance(raw, dict):
            raise ValueError('actions must be objects')
        op, connection = raw.get('op'), raw.get('connection', 'main')
        if connection not in ('main', 'other'):
            raise ValueError('unknown connection')
        if active is not None and active != connection:
            raise ValueError('cross-connection operation during transaction')
        if op in ('put', 'update', 'delete'):
            _actions([raw])  # Reuse established key/value validation.
        elif op in ('begin', 'commit', 'rollback'):
            if set(raw) - {'op', 'connection'}:
                raise ValueError('unexpected transaction fields')
            if op == 'begin':
                if active is not None:
                    raise ValueError('BEGIN cannot nest')
                active, explicit = connection, True
            else:
                if active != connection:
                    raise ValueError('completion without open transaction')
                active, explicit, stack = None, False, []
        elif op in ('savepoint', 'rollback_to', 'release'):
            if set(raw) - {'op', 'connection', 'name'} or raw.get('name') not in ('s0', 's1', 's2'):
                raise ValueError('invalid savepoint name or fields')
            name = raw['name']
            if op == 'savepoint':
                if name in stack or len(stack) >= 3:
                    raise ValueError('duplicate name or excessive depth')
                active = connection
                stack.append(name)
            else:
                if active != connection or name not in stack:
                    raise ValueError('savepoint target not active')
                offset = stack.index(name)
                stack = stack[:offset + (op == 'rollback_to')]
                if not stack and not explicit:
                    active = None
        else:
            raise ValueError('unsupported operation')
        action = json.loads(json.dumps(raw))
        public.append(action)
        translated = dict(action)
        if op in ('savepoint', 'rollback_to', 'release'):
            translated['op'] = {'savepoint': 'SAVEPOINT', 'rollback_to': 'ROLLBACK TO',
                                'release': 'RELEASE'}[op] + ' ' + raw['name']
        native.append(translated)
    return public, native


def observe(config, actions):
    public, native = normalize(actions)
    values = _run_native(config, native)
    receipt = {'source_id': config.source_id, 'actions': public, 'observed': dict(zip(GOALS, values)),
        'authority': 'native SQLite; independent committed-state connection',
        'sqlite_version': sqlite3.sqlite_version}
    receipt['receipt_sha256'] = digest(receipt)
    return receipt


@lru_cache(maxsize=8192)
def native_values(conflict, trigger, counter, actions_json):
    measured = observe(WorldConfig('oracle', conflict, trigger, counter), json.loads(actions_json))
    return tuple(measured['observed'][g] for g in GOALS)


def compatible(config, receipts):
    for receipt in receipts:
        if receipt['source_id'] != config.source_id or receipt['receipt_sha256'] != digest(
                {k: v for k, v in receipt.items() if k != 'receipt_sha256'}):
            raise ValueError('receipt source/content mismatch')
        values = native_values(config.conflict, config.insert_trigger, config.counter,
                               json.dumps(receipt['actions'], sort_keys=True))
        if dict(zip(GOALS, values)) != receipt['observed']:
            raise ValueError('receipt disagrees with actual native source')
    return [WorldConfig(config.source_id, conflict, trigger, counter)
        for conflict, trigger, counter in itertools.product(CONFLICTS, (False, True), COUNTERS)
        if all(dict(zip(GOALS, native_values(conflict, trigger, counter,
            json.dumps(r['actions'], sort_keys=True)))) == r['observed'] for r in receipts)]


def panels(config, receipts, sequences=None, nodes=()):
    """Observed development keys; private family consensus only for protected queries."""
    hypotheses = compatible(config, receipts)
    sequences = [r['actions'] for r in receipts] if sequences is None else sequences
    pairs = []
    for actions in sequences:
        normalize(actions)
        for index, goal in enumerate(GOALS):
            values = {native_values(c.conflict, c.insert_trigger, c.counter,
                                    json.dumps(actions, sort_keys=True))[index] for c in hypotheses}
            key = {'value': next(iter(values)) if len(values) == 1 else None, 'unresolved': len(values) != 1}
            case = {'id': digest([config.source_id, receipts, actions, goal]), 'source_id': config.source_id,
                'actions': actions, 'goal': goal, 'documentation': task_spec(),
                'tables': {'history': receipts, **{'dependency:' + n + ':' + function: []
                    for n in nodes for function in ('transition_initialization', 'readout')}}}
            pairs.append((case, key))
    return pairs


def put(key, value, connection='main'):
    return {'op': 'put', 'key': key, 'value': value, 'connection': connection}


def sp(op, name):
    return {'op': op, 'name': name}


def teaching_sequences():
    one = [[sp('savepoint', 's0'), put('p', 7), sp('release', 's0')],
           [sp('savepoint', 's0'), put('p', 7), sp('rollback_to', 's0'), sp('release', 's0')],
           [sp('savepoint', 's0'), put('p', 7)],
           [{'op': 'begin'}, sp('savepoint', 's0'), put('p', 7), sp('release', 's0')],
           [{'op': 'begin'}, sp('savepoint', 's0'), put('p', 7), sp('release', 's0'), {'op': 'commit'}]]
    two = [[sp('savepoint', 's0'), put('p', 7), sp('savepoint', 's1'), put('p', 11),
            sp('rollback_to', 's1'), sp('release', 's1'), sp('release', 's0')],
           [sp('savepoint', 's0'), put('p', 7), sp('savepoint', 's1'), put('q', 11),
            sp('release', 's1'), sp('rollback_to', 's0'), sp('release', 's0')],
           [{'op': 'begin'}, sp('savepoint', 's0'), put('p', 7), sp('savepoint', 's1'),
            put('q', 11), sp('release', 's0'), {'op': 'rollback'}]]
    more = [[sp('savepoint', 's0'), put('p', 13), sp('savepoint', 's1'),
             {'op': 'delete', 'key': 'p'}, sp('rollback_to', 's0'), put('q', 17), sp('release', 's0')],
            [sp('savepoint', 's0'), put('p', 13), sp('savepoint', 's1'), put('q', 17),
             sp('release', 's0'), put('r', 19, 'other')]]
    return one, two, more


def protected_sequences(seed, family='screen'):
    rng = random.Random(seed)
    sequences = []
    for index in range(16):
        a, b, c = rng.sample(range(23, 100), 3)
        key = f'protected-{index}'
        sequence = [sp('savepoint', 's0'), put(key, a), sp('savepoint', 's1'), put(key, b),
            sp('savepoint', 's2'), put('other-' + key, c)]
        if index % 4 == 0:
            sequence += [sp('rollback_to', 's1'), put('later-' + key, c), sp('release', 's0')]
        elif index % 4 == 1:
            sequence += [sp('release', 's2'), sp('rollback_to', 's0'), sp('release', 's0')]
        elif index % 4 == 2:
            sequence += [sp('release', 's1'), sp('release', 's0'), put('later-' + key, c, 'other')]
        else:
            sequence += [sp('release', 's2'), sp('release', 's1')]
        sequences.append(sequence)
    if family == 'confirmation':
        sequences = []
        for index in range(16):
            a, b, c, d = rng.sample(range(101, 300), 4)
            key = f'confirmation-{index}'
            if index % 4 == 0:
                sequence = [put(key, a, 'other'), {'op': 'begin'}, sp('savepoint', 's0'), put('b', b),
                    sp('savepoint', 's1'), {'op': 'update', 'key': key, 'value': c},
                    sp('savepoint', 's2'), {'op': 'delete', 'key': 'b'}, sp('rollback_to', 's1'),
                    sp('release', 's1'), put('later', d), {'op': 'commit'}]
            elif index % 4 == 1:
                sequence = [put(key, a), sp('savepoint', 's2'), {'op': 'delete', 'key': key},
                    sp('savepoint', 's0'), put('b', b), sp('savepoint', 's1'),
                    {'op': 'update', 'key': 'b', 'value': c}, sp('rollback_to', 's2'),
                    sp('savepoint', 's0'), put('c', d), sp('release', 's2'), put('later', c, 'other')]
            elif index % 4 == 2:
                sequence = [{'op': 'begin', 'connection': 'other'}, put(key, a, 'other'),
                    {**sp('savepoint', 's2'), 'connection': 'other'}, put(key, b, 'other'),
                    {**sp('savepoint', 's0'), 'connection': 'other'},
                    {'op': 'delete', 'key': key, 'connection': 'other'},
                    {**sp('savepoint', 's1'), 'connection': 'other'}, put('b', c, 'other'),
                    {**sp('release', 's2'), 'connection': 'other'}, {'op': 'rollback', 'connection': 'other'},
                    put('later', d)]
            else:
                sequence = [put(key, a), {'op': 'begin'}, sp('savepoint', 's1'),
                    {'op': 'update', 'key': key, 'value': b}, sp('savepoint', 's2'), put('b', c),
                    sp('savepoint', 's0'), {'op': 'update', 'key': 'b', 'value': d},
                    sp('rollback_to', 's2'), {'op': 'delete', 'key': key}, sp('release', 's2')]
            sequences.append(sequence)
    elif family != 'screen':
        raise ValueError('unknown protected structure family')
    return sequences


class NodeStore:
    """Immutable Python nodes, mechanically linked; hashes certify identity only."""
    def __init__(self):
        self.nodes = {}

    def add(self, program, dependencies=()):
        dependencies = list(dependencies)
        if len(set(dependencies)) != len(dependencies) or any(d not in self.nodes for d in dependencies):
            raise ValueError('missing or duplicate node dependency')
        tree = validate_source(program['source'])
        names = {n.name for n in tree.body}
        # Avoid a text-substitution linker: reject ambiguous shadowed globals.
        for function in tree.body:
            if any(a.arg in names for a in ast.walk(function) if isinstance(a, ast.arg)):
                raise ValueError('function global shadowed by argument')
            if any(n.id in names for n in ast.walk(function)
                   if isinstance(n, ast.Name) and isinstance(n.ctx, (ast.Store, ast.Del))):
                raise ValueError('function global shadowed by local')
            if any(n is not function and isinstance(n, ast.FunctionDef) and n.name in names
                   for n in ast.walk(function)):
                raise ValueError('function global shadowed by nested definition')
        identity = digest({'program': program, 'dependencies': dependencies})
        if identity in self.nodes:
            return identity
        node = {'id': identity, 'program': json.loads(json.dumps(program)),
                'source_sha256': hashlib.sha256(program['source'].encode()).hexdigest(),
                'dependencies': dependencies}
        self.nodes[identity] = node
        return identity

    def link(self, program, dependencies):
        emitted, parts = set(), []

        def emit(identity):
            if identity in emitted:
                return
            node = self.nodes[identity]
            for child in node['dependencies']:
                emit(child)
            emitted.add(identity)
            tree = ast.parse(node['program']['source'])
            names = {n.name: 'module' + identity[:12] + n.name for n in tree.body}
            class Rename(ast.NodeTransformer):
                def visit_FunctionDef(self, n):
                    n.name = names.get(n.name, n.name)
                    return self.generic_visit(n)
                def visit_Name(self, n):
                    n.id = names.get(n.id, n.id)
                    return n
            parts.append(ast.unparse(Rename().visit(tree)))
            for name, args in (('transition', 'state, action, context, acquire'),
                               ('readout', 'state, context, acquire')):
                if name in names:
                    marker = ('    if state is None:\n        acquire(' + repr('dependency:' + identity + ':transition_initialization') + ')\n'
                              if name == 'transition' else '    acquire(' + repr('dependency:' + identity + ':readout') + ')\n')
                    parts.append(f'def unit{identity[:12]}{name}({args}):\n' + marker +
                                 f'    return {names[name]}({args})\n')
        for identity in dependencies:
            if identity not in self.nodes:
                raise ValueError('missing linked node')
            emit(identity)
        parts.append(program['source'])
        linked = '\n\n'.join(parts)
        validate_source(linked)
        return linked

    def reachable(self, dependencies):
        result = set()
        def visit(identity):
            if identity in result:
                return
            result.add(identity)
            for child in self.nodes[identity]['dependencies']:
                visit(child)
        for identity in dependencies:
            visit(identity)
        return sorted(result)


def exports(source):
    functions = {n.name: n for n in validate_source(source).body}
    names = set(functions)
    if not {'transition', 'readout'} <= names:
        raise ValueError('primitive must export transition and readout')
    for name, count in (('transition', 4), ('readout', 3)):
        args = functions[name].args
        if len(args.args) != count or args.vararg or args.kwarg or args.posonlyargs or args.kwonlyargs:
            raise ValueError('primitive export has incorrect positional interface')


def primitive_driver(source):
    """Qualification driver, not semantic code or a repair of model functions."""
    exports(source)
    tree = ast.parse(source)
    helpers = [ast.unparse(n) for n in tree.body if n.name != 'investigate']
    return '\n\n'.join(helpers) + '''
def investigate(context, acquire):
    state = None
    for action in context["actions"]:
        state = transition(state, action, context, acquire)
    return readout(state, context, acquire)
'''


def node_score(store, program, dependencies, pairs):
    try:
        qualification = NodeStore()
        qualification.nodes = dict(store.nodes)
        qualification.add(program, dependencies)
        linked = store.link(program, dependencies)
    except (ValueError, SyntaxError) as error:
        result = score(UNKNOWN['source'], pairs)
        for row in result['rows']:
            row.update(correct=False, error=f'{type(error).__name__}: {error}')
        result.update(correct=0, errors=len(pairs))
        return result
    return score(linked, pairs)


def dependency_usage(result):
    counts = {}
    for row in result['rows']:
        for trace in row['trace']:
            if trace['table'].startswith('dependency:'):
                _, identity, function = trace['table'].split(':')
                functions = counts.setdefault(identity, {})
                functions[function] = functions.get(function, 0) + 1
    return counts


def prepare(output, model, provider_slug, *, seed=20261031, max_cost_usd='1', max_output_tokens=8192,
            reasoning_effort='none', model_evidence=None, panel_family='screen', primitive_proposals=2, worlds=3):
    if reasoning_effort not in ('none', 'low') or panel_family != 'screen':
        raise ValueError('prepare uses the screen family; confirmation is a separate sealed structural panel')
    if type(primitive_proposals) is not int or not 2 <= primitive_proposals <= 4:
        raise ValueError('primitive_proposals must be a predeclared integer between two and four')
    if type(worlds) is not int or not 1 <= worlds <= 3:
        raise ValueError('worlds must be a predeclared integer between one and three')
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    rng = random.Random(seed)
    conflicts, counters = list(CONFLICTS), list(COUNTERS)
    rng.shuffle(conflicts)
    rng.shuffle(counters)
    data = {'public': {'documentation': task_spec(), 'streams': []}, 'private': {'configs': {}}}
    for index in range(worlds):
        cfg = WorldConfig(world(seed * 100 + index).source_id, conflicts[index], bool(index % 2), counters[index])
        base = [observe(cfg, actions) for actions in discovery_sequences()]
        stages = [[observe(cfg, actions) for actions in batch] for batch in teaching_sequences()]
        data['public']['streams'].append({'source_id': cfg.source_id, 'base': base, 'stages': stages,
            'eval': protected_sequences(seed * 100 + index, panel_family),
            'confirmation': protected_sequences(seed * 100 + index + 91000, 'confirmation')})
        data['private']['configs'][cfg.source_id] = asdict(cfg)
    protocol = {'schema': VERSION, 'model': model, 'provider_slug': provider_slug,
        'reasoning_effort': reasoning_effort, 'max_cost_usd': str(max_cost_usd),
        'inference_mode': 'bounded',
        'max_output_tokens': max_output_tokens, 'max_calls': worlds * (primitive_proposals + 10),
        'primitive_proposals': primitive_proposals, 'worlds': worlds, 'seed': seed,
        'request_interface_version': 2, 'host_schema_sha256': digest(SCHEMA),
        'transport_schema_sha256': digest(TRANSPORT_SCHEMA),
        'arms': list(ARMS), 'dataset_sha256': digest(data), 'source': archive_runtime(output),
        'panel_family': panel_family,
        'model_evidence': model_evidence or {},
        'schedule': f'Per source: {primitive_proposals} fixed shared ordinary primitive proposals; three graph/flat assembly proposals on growing fixed evidence; three same-library fresh proposals on final evidence; one no-library fresh proposal on final evidence. {worlds * (primitive_proposals + 10)} calls total. All primitive attempts and qualification failures are retained; none is a silent retry or host-repaired output.',
        'matching': 'Identical learned primitives, receipts, linker, executor and three assembly allowances. Flat may inline, rewrite, reuse and retain complete programs; fresh may use the same primitives.',
        'graph': 'Content-addressed Python nodes and exact declared edges; initialization and readout calls are recorded by executor traces (not every transition step). A declared name or unused edge is not learned composition.',
        'promotion': 'Latest valid candidate with development score >= incumbent, all regressions retained. Development labels are native observations. No protected feedback.',
        'controls': 'Early graph program with final history/library, shared primitive with final history, empty history, cold, and single-shot no-library fresh (one rather than three proposals, diagnostic only). Neutral learned-child substitutions test effective dependence separately from invocation. All construction sealed before protected audit.',
        'boundary': f'{worlds} predeclared configured source(s), the fixed prefix of the three-source design, in the disclosed native family; authored depth-three SQL compositions. No arbitrary semantic discovery or graph benefit implied by storage.'}
    protocol['confirmation_boundary'] = 'One-time arm commitment before evaluating a separately frozen further-structure panel on the same configured sources. This is conditional further-case confirmation, not independent domain or learner replication. A new three-source paid run is a separate stronger replication.'
    write_json(output/'datasets.json', data)
    write_json(output/'protocol.json', protocol)
    write_json(output/'preparation-receipt.json', {'protocol_sha256': digest(protocol), 'dataset_sha256': digest(data)})
    return protocol


def verify_frozen(output):
    output = Path(output)
    protocol = json.loads((output/'protocol.json').read_text())
    data = json.loads((output/'datasets.json').read_text())
    receipt = json.loads((output/'preparation-receipt.json').read_text())
    if digest(protocol) != receipt['protocol_sha256'] or digest(data) != protocol['dataset_sha256']:
        raise ValueError('source-bound protocol or dataset changed')
    if (protocol.get('request_interface_version') != 2 or protocol.get('host_schema_sha256') != digest(SCHEMA)
            or protocol.get('transport_schema_sha256') != digest(TRANSPORT_SCHEMA)):
        raise ValueError('frozen request schema custody changed')
    archive = output/'runtime-source.zip'
    if hashlib.sha256(archive.read_bytes()).hexdigest() != protocol['source']['sha256']:
        raise ValueError('runtime archive changed')
    root = Path(__file__).resolve().parents[1]
    with ZipFile(archive) as frozen:
        for name in frozen.namelist():
            if (root/name).read_bytes() != frozen.read(name):
                raise ValueError('runtime changed after freeze: ' + name)
    return protocol, data


def audit(protocol, data, records, partition='eval'):
    if partition not in ('eval', 'confirmation'):
        raise ValueError('invalid protected partition')
    worlds = []
    for record in records:
        cfg = WorldConfig(**data['private']['configs'][record['source_id']])
        stream = next(s for s in data['public']['streams'] if s['source_id'] == cfg.source_id)
        store = NodeStore()
        store.nodes = record['nodes']
        pairs = panels(cfg, record['history'], stream[partition], store.nodes)
        row = {'source_id': cfg.source_id}
        for arm in ARMS:
            current = record['arms'][arm]
            row[arm] = node_score(store, current['champion']['program'], current['champion']['dependencies'], pairs)
            row[arm]['dependency_usage'] = dependency_usage(row[arm])
            row[arm + '_checkpoints'] = [node_score(store, c['program'], c['dependencies'],
                panels(cfg, c['history'], stream[partition], store.nodes)) for c in current['checkpoints']]
        early = record['arms']['graph']['checkpoints'][0]
        row['freeze_and_grow'] = node_score(store, early['program'], early['dependencies'], pairs)
        primitive = store.nodes[record['primitive_ids'][-1]]
        row['primitive_only'] = node_score(store, primitive['program'], [], pairs)
        last = record['arms']['graph']['champion']
        empty = [(dict(case, tables={**case['tables'], 'history': []}), key) for case, key in pairs]
        row['empty_history'] = node_score(store, last['program'], last['dependencies'], empty)
        row['cold'] = score(UNKNOWN['source'], pairs)
        row['fresh_no_library'] = score(record['fresh_no_library']['program']['source'], pairs)
        if record['fresh_no_library']['response_error']:
            for item in row['fresh_no_library']['rows']:
                item.update(correct=False, error=record['fresh_no_library']['response_error']['error'])
            row['fresh_no_library'].update(correct=0, errors=len(pairs))
        neutral = {'source': 'def transition(state, action, context, acquire):\n    return state\n\ndef readout(state, context, acquire):\n    return {"value": None, "unresolved": True}\n\ndef investigate(context, acquire):\n    return {"value": None, "unresolved": True}',
                   'scope': 'Counterfactual neutral child, not a learned version.', 'lesson': 'offline ablation'}
        ablations = []
        for identity in store.reachable(last['dependencies']):
            for mode in ('whole_child', 'readout_only'):
                replacement = neutral
                if mode == 'readout_only':
                    original = store.nodes[identity]['program']
                    tree = ast.parse(original['source'])
                    for function in tree.body:
                        if function.name == 'readout':
                            function.body = ast.parse('return {"value": None, "unresolved": True}').body
                    replacement = {**original, 'source': ast.unparse(tree)}
                altered = NodeStore()
                altered.nodes = json.loads(json.dumps(store.nodes))
                altered.nodes[identity]['program'] = replacement
                ablated = node_score(altered, last['program'], last['dependencies'], pairs)
                changed = sum((old['answer'], old['error']) != (new['answer'], new['error'])
                              for old, new in zip(row['graph']['rows'], ablated['rows']))
                ablations.append({'child_id': identity, 'mode': mode, 'counterfactual_source_sha256':
                    hashlib.sha256(replacement['source'].encode()).hexdigest(), 'changed_answers_or_errors': changed,
                    'lost_correct_without_error': sum(old['correct'] and not new['correct'] and new['error'] is None
                        for old, new in zip(row['graph']['rows'], ablated['rows'])),
                    'lost_correct': sum(old['correct'] and not new['correct'] for old, new in
                                        zip(row['graph']['rows'], ablated['rows'])), 'result': ablated,
                    'boundary': 'Whole-child neutralization includes state-interface sensitivity. Readout-only preserves learned initialization; error-free accuracy loss is stronger evidence of effective use. Neither establishes graph advantage.'})
        row['dependency_ablations'] = ablations
        worlds.append(row)
    arms = (*ARMS, 'fresh_no_library', 'freeze_and_grow', 'primitive_only', 'empty_history', 'cold')
    return {'schema': VERSION, 'partition': partition, 'protocol_sha256': digest(protocol), 'frozen_sha256': digest(records),
        'worlds': worlds, 'aggregate': {a: {k: sum(w[a][k] for w in worlds)
            for k in ('correct', 'total', 'unsupported', 'errors')} for a in arms}}


def run(output, env_file=None, *, provider=None):
    output = Path(output).resolve()
    if (output/'started.json').exists():
        raise ValueError('preserve prior attempts; use a new experiment identity')
    protocol, data = verify_frozen(output)
    if provider is None:
        from system.lib.openrouter_free_runtime import load_env_file
        load_env_file(Path(env_file))
        provider = OpenRouterBudgetedProvider(output/'provider', protocol['model'], protocol['max_cost_usd'],
            protocol['max_calls'], protocol['max_output_tokens'], output/'budget', provider_slug=protocol['provider_slug'],
            inference_mode=protocol['inference_mode'])
    write_json(output/'started.json', {'protocol_sha256': digest(protocol), 'dataset_sha256': digest(data)})

    def ask(node_id, prompt):
        write_json(output/'prompts'/f'{node_id}.json', {'prompt': prompt, 'schema': TRANSPORT_SCHEMA, 'system': LANGUAGE})
        raw = provider.ask_ai(json.dumps(prompt, ensure_ascii=False), {'meta': {
            'session_id': getattr(provider, 'run_dir', output).name, 'node_id': node_id}, 'system_prompt': LANGUAGE,
            'reasoning_effort': protocol['reasoning_effort'], 'response_format': {
                'type': 'json_schema', 'json_schema': {'name': 'composition', 'strict': True, 'schema': TRANSPORT_SCHEMA}}})
        write_json(output/'responses'/f'{node_id}-raw.json', {'content': raw})
        try:
            answer = json.loads(raw)
            validate(answer, SCHEMA)
        except (ValueError, ValidationError) as error:
            failure = {'raw_content': raw, 'error': f'{type(error).__name__}: {error}'}
            write_json(output/'responses'/f'{node_id}-invalid.json', failure)
            return {**UNKNOWN, 'dependencies': []}, failure, hashlib.sha256(raw.encode()).hexdigest()
        write_json(output/'responses'/f'{node_id}.json', answer)
        return answer, None, hashlib.sha256(raw.encode()).hexdigest()

    records, phase = [], 'construction'
    try:
        for index, stream in enumerate(data['public']['streams']):
            cfg = WorldConfig(**data['private']['configs'][stream['source_id']])
            store = NodeStore()
            record = {'source_id': cfg.source_id, 'primitive_ids': [], 'primitive_rounds': [],
                'history': list(stream['base']), 'nodes': {}, 'arms': {a: {'champion': {
                    'program': dict(UNKNOWN), 'dependencies': []}, 'rounds': [], 'checkpoints': []} for a in ARMS}}
            pairs = panels(cfg, record['history'])
            for step in range(protocol['primitive_proposals']):
                answer, response_error, content_sha = ask(f'world-{index:02d}-primitive-{step}', {
                    'documentation': ordinary_spec(), 'history': record['history'],
                    'interface': PRIMITIVE_INTERFACE, 'prior_trials': record['primitive_rounds']})
                program = {k: answer[k] for k in ('source', 'scope', 'lesson')}
                result = score(program['source'], pairs)
                interface_error = None
                interface_result = None
                try:
                    exports(program['source'])
                    if answer['dependencies'] or response_error:
                        raise ValueError('primitive cannot have external dependencies or malformed response')
                    if result['errors']:
                        raise ValueError('primitive has measured execution errors')
                    interface_result = score(primitive_driver(program['source']), pairs)
                    if interface_result['errors'] or any(a['answer'] != b['answer'] for a, b in
                            zip(result['rows'], interface_result['rows'])):
                        raise ValueError('exported state transitions/readout disagree with investigate')
                    if interface_result['correct'] == 0:
                        raise ValueError('primitive has no correct observed computation to compose')
                    identity = store.add(program)
                    record['primitive_ids'].append(identity)
                except (ValueError, SyntaxError) as error:
                    interface_error = f'{type(error).__name__}: {error}'
                record['primitive_rounds'].append({'proposal': answer, 'result': result,
                    'interface_result': interface_result,
                    'response_content_sha256': content_sha,
                    'response_error': response_error, 'interface_error': interface_error})
                record['nodes'] = dict(store.nodes)
                write_json(output/f'world-{index:02d}-partial.json', record)
            if not record['primitive_ids']:
                raise RuntimeError('no executable composable primitive; no further inference')

            def propose(arm, step, history):
                current = record['arms'][arm]
                pairs = panels(cfg, history, nodes=store.nodes)
                old = node_score(store, current['champion']['program'], current['champion']['dependencies'], pairs)
                library = [{'id': n, 'program': store.nodes[n]['program'],
                    'dependencies': store.nodes[n]['dependencies'], 'exports': {
                        'transition': 'unit' + n[:12] + 'transition', 'readout': 'unit' + n[:12] + 'readout'}}
                    for n in record['primitive_ids']]
                prompt = {'documentation': task_spec(), 'history': history, 'library': library,
                    'champion': current['champion'], 'prior_trials': current['rounds'],
                    'measured_feedback': witnesses(pairs, old), 'arm': arm,
                    'interface': 'Return ordinary investigate(context, acquire) and helper bodies. dependencies lists exact library IDs to mechanically link; use the advertised transition/readout names. transition returns learned state which a later operation/readout consumes; do not route complete predictions. Same linker is available to every arm. Include COMPLETE EXECUTABLE CODE.',
                    'representation': 'Retain exact child versions and compose their learned state transition/readout. Record actual calls; declaring an edge alone is insufficient.' if arm == 'graph' else
                        'Competent flat executable library: reuse any advertised primitive, inline or rewrite any body, and retain complete previous programs. No composition restriction.'}
                answer, response_error, content_sha = ask(f'world-{index:02d}-{arm}-{step}', prompt)
                program = {k: answer[k] for k in ('source', 'scope', 'lesson')}
                deps = answer['dependencies']
                # Only shared primitives are available to either representation.
                if any(d not in record['primitive_ids'] for d in deps):
                    response_error = {'error': 'unadvertised primitive dependency', 'raw_content': json.dumps(answer)}
                candidate = node_score(store, program, deps, pairs)
                if response_error:
                    for row in candidate['rows']:
                        row.update(correct=False, error=response_error['error'])
                    candidate.update(correct=0, errors=len(pairs))
                accepted, regressions = adoption(old, candidate)
                parent_sha = digest(current['champion'])
                identity = None
                if accepted:
                    try:
                        identity = store.add(program, deps)
                    except (ValueError, SyntaxError) as error:
                        accepted = False
                        response_error = {'error': f'{type(error).__name__}: {error}'}
                    else:
                        # The flat control retains the exact equivalent expanded
                        # executable, while graph retains immutable child links.
                        # This is mechanical compilation, never model repair.
                        current['champion'] = ({'program': {**program, 'source': store.link(program, deps)},
                                               'dependencies': []} if arm == 'flat' else
                                              {'program': program, 'dependencies': deps})
                current['rounds'].append({'proposal': answer, 'old': old, 'candidate': candidate,
                    'accepted': accepted, 'regressions': regressions, 'parent_sha256': parent_sha,
                    'response_error': response_error, 'node_id': identity,
                    'response_content_sha256': content_sha,
                    'actual_dependency_usage': dependency_usage(candidate), 'history': list(history)})
                current['checkpoints'].append({**current['champion'], 'history': list(history),
                    'sha256': digest(current['champion'])})
                record['nodes'] = dict(store.nodes)
                write_json(output/f'world-{index:02d}-partial.json', record)

            for step, batch in enumerate(stream['stages']):
                record['history'].extend(batch)
                for arm in ('graph', 'flat'):
                    propose(arm, step, record['history'])
            for step in range(3):
                propose('fresh', step, record['history'])
            answer, response_error, content_sha = ask(f'world-{index:02d}-fresh-no-library', {
                'documentation': task_spec(), 'history': record['history'], 'library': [],
                'interface': 'Write a complete reusable investigate(context, acquire) from the evidence. No prior program/library is supplied. dependencies must be []. This single-shot diagnostic has one proposal, not the three-proposal comparison allowance.'})
            record['fresh_no_library'] = {'program': {k: answer[k] for k in ('source', 'scope', 'lesson')},
                'proposal': answer, 'response_error': response_error, 'dependencies': answer['dependencies']}
            record['fresh_no_library']['response_content_sha256'] = content_sha
            if answer['dependencies']:
                record['fresh_no_library']['program'] = dict(UNKNOWN)
                record['fresh_no_library']['response_error'] = {'error': 'no-library baseline requested unavailable dependency',
                    'raw_content': json.dumps(answer)}
            records.append(record)
            write_json(output/f'world-{index:02d}-frozen.json', record)
        write_json(output/'all-frozen.json', records)
        write_json(output/'all-frozen-receipt.json', {'protocol_sha256': digest(protocol),
            'frozen_sha256': digest(records), 'construction_complete': True, 'protected_audit_started': False})
        phase = 'protected_audit'
        result = audit(protocol, data, records)
        if (output/'budget/budget.json').exists():
            budget = json.loads((output/'budget/budget.json').read_text())
            result['cost'] = {k: budget[k] for k in ('total_reported_cost_usd', 'total_reserved_usd') if k in budget}
            result['calls'] = len(budget['entries'])
        write_json(output/'results.json', result)
        return result
    except Exception as error:
        write_json(output/'failure.json', {'error': f'{type(error).__name__}: {error}',
            'completed_worlds': len(records), 'protected_evaluation_performed': phase == 'protected_audit', 'automatic_retry': False})
        raise


def replay_records(protocol, data, records, raw_responses=None):
    """Archived worker callable: compare every individual construction result.

    raw_responses optionally maps saved request node IDs to original content.
    The publication worker independently verifies ZIP, datasets and paid delivery.
    No provider call, proposal selection, or protected feedback occurs here.
    """
    checks = 0
    def check_content(node_id, trial):
        if raw_responses is None:
            return
        raw = raw_responses[node_id]
        if hashlib.sha256(raw.encode()).hexdigest() != trial['response_content_sha256']:
            raise ValueError('original model content hash mismatch')
        if trial.get('response_error') and trial['response_error'].get('raw_content') is not None:
            if raw != trial['response_error']['raw_content']:
                raise ValueError('original malformed content changed')
        else:
            if json.loads(raw) != trial['proposal']:
                raise ValueError('original proposal differs from raw model content')
    for index, record in enumerate(records):
        cfg = WorldConfig(**data['private']['configs'][record['source_id']])
        store = NodeStore()
        store.nodes = record['nodes']
        for identity, node in store.nodes.items():
            if identity != digest({'program': node['program'], 'dependencies': node['dependencies']}):
                raise ValueError('immutable node content changed')
            if node['source_sha256'] != hashlib.sha256(node['program']['source'].encode()).hexdigest():
                raise ValueError('original node source changed')
        stream = next(s for s in data['public']['streams'] if s['source_id'] == record['source_id'])
        base = panels(cfg, stream['base'])
        for step, trial in enumerate(record['primitive_rounds']):
            check_content(f'world-{index:02d}-primitive-{step}', trial)
            if score(trial['proposal']['source'], base) != trial['result']:
                raise ValueError('primitive individual answer/trace/error mismatch')
            checks += 1
            if trial['interface_result'] is not None:
                if score(primitive_driver(trial['proposal']['source']), base) != trial['interface_result']:
                    raise ValueError('primitive interface answer/trace/error mismatch')
                checks += 1
        for arm in ARMS:
            champion = {'program': dict(UNKNOWN), 'dependencies': []}
            for step, trial in enumerate(record['arms'][arm]['rounds']):
                check_content(f'world-{index:02d}-{arm}-{step}', trial)
                if digest(champion) != trial['parent_sha256']:
                    raise ValueError('construction parent mismatch')
                pairs = panels(cfg, trial['history'], nodes=store.nodes)
                proposal = trial['proposal']
                program = {k: proposal[k] for k in ('source', 'scope', 'lesson')}
                old = node_score(store, champion['program'], champion['dependencies'], pairs)
                candidate = node_score(store, program, proposal['dependencies'], pairs)
                if trial['response_error']:
                    for row in candidate['rows']:
                        row.update(correct=False, error=trial['response_error']['error'])
                    candidate.update(correct=0, errors=len(pairs))
                if old != trial['old'] or candidate != trial['candidate']:
                    raise ValueError('construction individual answer/trace/error mismatch')
                if adoption(old, candidate) != (trial['accepted'], trial['regressions']):
                    raise ValueError('construction adoption mismatch')
                if trial['accepted']:
                    champion = ({'program': {**program, 'source': store.link(program, proposal['dependencies'])},
                                 'dependencies': []} if arm == 'flat' else
                                {'program': program, 'dependencies': proposal['dependencies']})
                checks += 2
            if champion != record['arms'][arm]['champion']:
                raise ValueError('final retained program mismatch')
        check_content(f'world-{index:02d}-fresh-no-library', record['fresh_no_library'])
    return {'construction_checks': checks, 'inference_calls': 0}


def confirmation_selection(protocol, data, records, arm):
    if arm not in ARMS:
        raise ValueError('choose a primary arm')
    return {'arm': arm, 'protocol_sha256': digest(protocol), 'frozen_sha256': digest(records),
            'confirmation_pool_sha256': digest([s['confirmation'] for s in data['public']['streams']])}


def replay_confirmation(protocol, data, records, selection, saved):
    if selection != confirmation_selection(protocol, data, records, selection['arm']):
        raise ValueError('confirmation selection custody mismatch')
    result = confirmation_result(protocol, data, records, selection)
    if result != saved:
        raise ValueError('confirmation individual answer/trace/error mismatch')
    return {'exact_replay': True, 'inference_calls': 0}


def confirmation_result(protocol, data, records, selection):
    """Only the committed arm consumes the untouched confirmation outcomes."""
    arm, worlds = selection['arm'], []
    for record in records:
        cfg = WorldConfig(**data['private']['configs'][record['source_id']])
        stream = next(s for s in data['public']['streams'] if s['source_id'] == record['source_id'])
        store = NodeStore()
        store.nodes = record['nodes']
        chosen = record['arms'][arm]['champion']
        result = node_score(store, chosen['program'], chosen['dependencies'],
            panels(cfg, record['history'], stream['confirmation'], store.nodes))
        worlds.append({'source_id': record['source_id'], arm: result})
    return {'schema': VERSION, 'partition': 'confirmation', 'selection': selection,
        'worlds': worlds, 'aggregate': {arm: {k: sum(row[arm][k] for row in worlds)
            for k in ('correct', 'total', 'unsupported', 'errors')}},
        'boundary': protocol['confirmation_boundary']}


def confirm(output, arm):
    output = Path(output)
    protocol, data = verify_frozen(output)
    records = json.loads((output/'all-frozen.json').read_text())
    result = json.loads((output/'results.json').read_text())
    if result['frozen_sha256'] != digest(records) or result['protocol_sha256'] != digest(protocol):
        raise ValueError('screen result custody mismatch')
    selection = confirmation_selection(protocol, data, records, arm)
    with (output/'confirmation-selection.json').open('x') as handle:
        json.dump(selection, handle, sort_keys=True)
    confirmed = confirmation_result(protocol, data, records, selection)
    write_json(output/'confirmation.json', confirmed)
    return confirmed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('prepare', 'run', 'confirm'))
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--model')
    parser.add_argument('--provider-slug')
    parser.add_argument('--seed', type=int, default=20261031)
    parser.add_argument('--max-cost-usd', default='1')
    parser.add_argument('--max-output-tokens', type=int, default=8192)
    parser.add_argument('--primitive-proposals', type=int, default=2, choices=(2, 3, 4))
    parser.add_argument('--worlds', type=int, default=3, choices=(1, 2, 3))
    parser.add_argument('--reasoning-effort', default='none', choices=('none', 'low'))
    parser.add_argument('--panel-family', default='screen', choices=('screen',))
    parser.add_argument('--env-file', type=Path)
    parser.add_argument('--arm', choices=ARMS)
    args = parser.parse_args()
    if args.command == 'prepare':
        if not args.model or not args.provider_slug:
            parser.error('prepare requires model and exact provider route')
        result = prepare(args.output, args.model, args.provider_slug, seed=args.seed,
            max_cost_usd=args.max_cost_usd, max_output_tokens=args.max_output_tokens,
            reasoning_effort=args.reasoning_effort, panel_family=args.panel_family,
            primitive_proposals=args.primitive_proposals, worlds=args.worlds)
    elif args.command == 'run':
        if not args.env_file:
            parser.error('run requires explicit env-file; no fallback')
        result = run(args.output, args.env_file)
    else:
        if not args.arm:
            parser.error('confirm requires one explicit frozen arm commitment')
        result = confirm(args.output, args.arm)
    print(json.dumps(result if args.command == 'prepare' else result['aggregate'], indent=2))


if __name__ == '__main__':
    main()
