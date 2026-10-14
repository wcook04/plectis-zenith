"""Matched structural-revision experiments using the existing executor/provider.

The graph is an inspectable call structure, not a new execution engine. Prepare
freezes authored tasks and both later panels. Construction sees development only.
"""
from __future__ import annotations

import argparse
import ast
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
import os
from pathlib import Path
import threading
import time

from jsonschema import validate

from research.decomposition_tasks import build_dataset, public_task
from research.investigator_study import archive_runtime
from zenith.budgeted import OpenRouterBudgetedProvider, budget_options
from zenith.investigation_program import execute, validate_source
from zenith.providers import digest, now, write_json

ROOT = Path(__file__).resolve().parents[1]
VERSION = 'zenith_decomposition_study_v1'
ARMS = ('global', 'contextual', 'contracts', 'fixed')
SCHEMA = {'type': 'object', 'properties': {
    'source': {'type': 'string'}, 'scope': {'type': 'string'},
    'change': {'type': 'string'}},
    'required': ['source', 'scope', 'change'], 'additionalProperties': False}
LANGUAGE = '''Return one JSON object with source, scope and change strings.
source is the COMPLETE executable Python program defining investigate(context, acquire).
Return exactly the JSON value requested in the task contract. Each query starts
fresh. context contains the task input only. There are no external tables.
Use the measured development examples to infer the source-specific behaviour.
Do not hardcode the example outputs; later queries have new values/combinations.
Only function definitions at module level. No imports, annotations, decorators,
default arguments, private names, exceptions, while loops, I/O or global state.
The single local name _ is allowed; other leading-underscore names are not.
Use x*x and x*x*x rather than exponentiation (**); do not use function defaults.
For loops, comprehensions, lambda, nonlocal closure variables and arithmetic
except power are permitted. No classes, try/except, yield or recursion tricks.
Builtins: abs all any bool dict enumerate float int isinstance len list max min
range reversed round set sorted str sum tuple zip.
Methods: get items keys values append extend sort lower upper strip split
setdefault add discard copy count index pop remove clear update.
Limit 60000 UTF8 bytes. Use scope/change for concise technical claims, not a
chain-of-thought transcript. No source evaluator or hidden configuration is available.
'''
INSTRUCTIONS = {
 'global': 'Improve the whole ordinary program using the task specification and measured examples. You may freely refactor any function, change interfaces or retained state, add/remove helpers, or replace the whole implementation. Diagnose the actual cause; a local edit is not required. Preserve a correct program when no useful change is needed.',
 'contextual': 'Treat the functions and their callers/consumers as a revisable decomposition. Start from the indicated local focus and its surrounding context. Decide whether its current inputs, retained state and role suffice for its downstream obligation. You may change ANY function or interface, split/merge/remove helpers, add state, or replace the whole program. Make the smallest useful computational change; no graph growth is required.',
 'contracts': 'Improve the whole ordinary program using the function contracts and measured examples. Check whether the information passed across interfaces suffices for the requested result. You may change ANY function/interface/state, add/remove helpers or replace the whole program. Choose the simplest useful refactoring; preserving correct code is allowed.',
 'fixed': 'Diagnostic condition: you may edit ONLY the BODY of the named focus function. Keep its signature, all other functions, their order, and every other body unchanged. Do not add/delete functions. Infer the best valid local implementation from the examples. If that boundary cannot solve the task, preserve the best valid program and state the limitation in scope/change.'}


def read(path):
    return json.loads(Path(path).read_text())


def exclusive_json(path, value):
    """One process admits a run/panel; a crashed admission remains visible."""
    with Path(path).open('x', encoding='utf8') as stream:
        json.dump(value, stream, allow_nan=False, indent=2)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())


def training(task):
    return task['calibration'] + task['development']


def call_structure(source):
    tree = ast.parse(source)
    functions = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
    return [{'name': name, 'arguments': [a.arg for a in fn.args.args],
             'calls': sorted({n.func.id for n in ast.walk(fn)
                              if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                              and n.func.id in functions}),
             'called_by': sorted(other for other, body in functions.items()
                                 if any(isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                                        and n.func.id == name for n in ast.walk(body)))}
            for name, fn in functions.items()]


def fixed_error(initial, source, focus):
    """The restricted arm cannot silently escape its information boundary."""
    old, new = ast.parse(initial), ast.parse(source)
    if [n.name for n in old.body] != [n.name for n in new.body]:
        return 'Fixed interface: function set/order changed.'
    for a, b in zip(old.body, new.body):
        if a.name == focus:
            if ast.dump(a.args) != ast.dump(b.args):
                return 'Fixed interface: focus signature changed.'
        elif ast.dump(a) != ast.dump(b):
            return 'Fixed interface: non-focus function changed: ' + a.name
    return None


def score(source, examples, constraint_error=None):
    try:
        if constraint_error:
            raise ValueError(constraint_error)
        results = execute(source, [{'tables': {}, **x['input']} for x in examples], answer_contract='json')
    except (ValueError, SyntaxError) as error:
        results = [{'answer': None, 'trace': [], 'error': f'{type(error).__name__}: {error}'} for x in examples]
    rows = []
    for example, result in zip(examples, results, strict=True):
        rows.append({**result, 'input': example['input'], 'expected': example['expected'],
                     'correct': result['error'] is None and digest(result['answer']) == digest(example['expected'])})
    return {'correct': sum(x['correct'] for x in rows), 'total': len(rows),
            'errors': sum(x['error'] is not None for x in rows), 'rows': rows}


def constraint(task, arm, source):
    try:
        validate_source(source)
        return fixed_error(task['initial_source'], source, task['focus_function']) if arm == 'fixed' else None
    except (SyntaxError, ValueError) as e:
        return f'{type(e).__name__}: {e}'


def prompt_for(task, arm, current, trials):
    public = public_task(task)
    public.pop('initial_source', None)
    # These are measured outcomes for public development inputs only.
    prompt = {'task': public, 'instruction': INSTRUCTIONS[arm],
              'current_program': current['source'], 'current_development': current['development'],
              'prior_attempts': trials, 'required_return': SCHEMA}
    if arm == 'contextual':
        prompt['local_context'] = {'focus': task['focus_function'],
                                  'nodes': call_structure(current['source'])}
    elif arm == 'contracts':
        prompt['function_contracts'] = [
            f"{r['name']}({', '.join(r['arguments'])}); calls {r['calls']}; used by {r['called_by']}"
            for r in call_structure(current['source'])]
    return prompt


def dependencies():
    paths = ('research/decomposition_study.py', 'research/decomposition_tasks.py',
             'research/investigator_study.py', 'zenith/investigation_program.py',
             'zenith/budgeted.py', 'zenith/provider_policy.py', 'zenith/providers.py',
             'system/lib/openrouter_free_runtime.py')
    return {p: hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in paths}


def prepare(output, model, providers, *, seed=20261014, panel_size=24,
            arms=ARMS, proposals=2, max_cost_usd='0.75', max_output_tokens=6144,
            reasoning_effort='none', workers=3, model_evidence=None, dataset=None):
    output = Path(output).resolve()
    if not providers or len(set(arms)) != len(arms) or not set(arms) <= set(ARMS) or not arms:
        raise ValueError('Explicit routes and distinct known arms required.')
    if not 1 <= workers <= 3 or not 1 <= proposals <= 4:
        raise ValueError('Require 1..3 workers and 1..4 proposals.')
    if reasoning_effort not in ('none', 'low', 'medium', 'high'):
        raise ValueError('Unknown reasoning effort')
    data = dataset if dataset is not None else build_dataset(seed=seed, panel_size=panel_size)
    calls = len(data['tasks']) * len(arms) * proposals
    budget_options(model, max_cost_usd, calls, max_output_tokens, output/'budget')
    output.mkdir(parents=True, exist_ok=False)
    write_json(output/'datasets.json', data)
    source_archive = archive_runtime(output)
    source_archive['path'] = 'runtime-source.zip'
    protocol = {'schema': VERSION, 'created_at': now(), 'model': model,
        'providers': list(providers), 'task_routes': {t['id']: providers[i % len(providers)] for i,t in enumerate(data['tasks'])},
        'task_arm_order': {t['id']: list(arms[i % len(arms):]) + list(arms[:i % len(arms)])
                           for i,t in enumerate(data['tasks'])},
        'arms': list(arms), 'proposals': proposals, 'max_calls': calls, 'seed': seed,
        'max_cost_usd': str(max_cost_usd), 'max_output_tokens': max_output_tokens,
        'reasoning_effort': reasoning_effort, 'workers': workers,
        'dataset_sha256': digest(data), 'runtime_dependencies': dependencies(),
        'source': source_archive, 'model_evidence': model_evidence or {},
        'selection': 'All visible calibration+development (correct,-errors), later attempt on ties. Arm order rotated across tasks. All arms frozen before either protected panel. Fixed is diagnostic; global versus contextual/contracts is primary.',
        'boundary': 'Authored mechanism tasks; only allocator is native SQLite. No autonomous goal or representation-language invention, production-value or general intelligence claim. All model outputs preserved unedited.',
        'feedback': 'All arms share measured development inputs/labels; each receives its own complete candidate and actual execution outcomes. No protected labels in prompts.',
        'structure': 'Ordinary Python function calls; no forced code expansion or special graph execution.'}
    write_json(output/'protocol.json', protocol)
    write_json(output/'preparation.json', {'protocol_sha256': digest(protocol)})
    return protocol


def verify(output):
    output = Path(output)
    protocol, data = read(output/'protocol.json'), read(output/'datasets.json')
    if protocol['schema'] != VERSION or digest(protocol) != read(output/'preparation.json')['protocol_sha256'] or digest(data) != protocol['dataset_sha256']:
        raise ValueError('Frozen protocol/dataset mismatch')
    if protocol['runtime_dependencies'] != dependencies():
        raise ValueError('Runtime changed: use the archived source or prepare a new experiment.')
    if hashlib.sha256((output/'runtime-source.zip').read_bytes()).hexdigest() != protocol['source']['sha256']:
        raise ValueError('Runtime archive mismatch')
    return protocol, data


def run(output, env_file=None, *, provider_factory=None):
    output = Path(output).resolve()
    if (output/'started.json').exists():
        raise ValueError('This study already started; attempts cannot be retried.')
    protocol, data = verify(output)
    if provider_factory is None:
        from system.lib.openrouter_free_runtime import load_env_file
        if env_file is not None:
            load_env_file(Path(env_file))
        def provider_factory(task, route):
            return OpenRouterBudgetedProvider(output/'providers'/task['id'], protocol['model'],
                protocol['max_cost_usd'], protocol['max_calls'], protocol['max_output_tokens'],
                output/'budget', provider_slug=route, inference_mode='bounded')
    exclusive_json(output/'started.json', {'protocol_sha256': digest(protocol), 'at': now()})
    stop = threading.Event()
    records, failures = [], []

    def trajectory(task):
        provider = provider_factory(task, protocol['task_routes'][task['id']])
        record = {'task_id': task['id'], 'route': protocol['task_routes'][task['id']], 'arms': {}}
        for arm in protocol['task_arm_order'][task['id']]:
            if stop.is_set():
                break
            initial = {'source': task['initial_source'], 'scope': 'Authored initial program.', 'change': '',
                       'development': score(task['initial_source'], training(task))}
            current = initial
            trials = []
            record['arms'][arm] = {'initial': initial, 'trials': trials, 'selected': current}
            for step in range(protocol['proposals']):
                if stop.is_set():
                    break
                node = f'{task["id"]}-{arm}-{step}'
                prompt = prompt_for(task, arm, current, trials)
                envelope = {'prompt': prompt, 'system': LANGUAGE, 'response_schema': SCHEMA}
                write_json(output/'prompts'/f'{node}.json', envelope)
                before = time.monotonic()
                try:
                    raw = provider.ask_ai(json.dumps(prompt, ensure_ascii=False), {
                        'meta': {'session_id': provider.run_dir.name, 'node_id': node},
                        'system_prompt': LANGUAGE, 'reasoning_effort': protocol['reasoning_effort'],
                        'response_format': {'type': 'json_schema', 'json_schema': {
                            'name': 'decomposition_program', 'strict': True, 'schema': SCHEMA}}}, cancel=stop)
                except Exception as exc:
                    stop.set()
                    record['failure'] = {'node': node, 'error': f'{type(exc).__name__}: {exc}'}
                    write_json(output/'records'/f'{task["id"]}.json', record)
                    return record
                write_json(output/'responses'/f'{node}.json', {'raw': raw, 'prompt_sha256': digest(envelope)})
                response_error = None
                try:
                    proposal = json.loads(raw)
                    validate(proposal, SCHEMA)
                except Exception as exc:
                    proposal = {'source': '', 'scope': '', 'change': ''}
                    response_error = f'{type(exc).__name__}: {exc}'[:1000]
                error = response_error or constraint(task, arm, proposal['source'])
                result = score(proposal['source'], training(task), error)
                trial = {**proposal, 'node_id': node, 'response_error': response_error,
                    'constraint_error': error, 'development': result,
                    'prompt_sha256': digest(envelope), 'raw_sha256': hashlib.sha256(raw.encode()).hexdigest(),
                    'elapsed_seconds': time.monotonic()-before,
                    'structure': call_structure(proposal['source']) if error is None else None}
                trials.append(trial)
                if error is None and (result['correct'], -result['errors']) >= (current['development']['correct'], -current['development']['errors']):
                    current = trial
                record['arms'][arm]['selected'] = current
                write_json(output/'records'/f'{task["id"]}.json', record)
                print(f'{node}: development {result["correct"]}/{result["total"]}; errors {result["errors"]}', flush=True)
        return record

    with ThreadPoolExecutor(max_workers=protocol['workers']) as pool:
        jobs = {pool.submit(trajectory, task): task['id'] for task in data['tasks']}
        for future in as_completed(jobs):
            try:
                record = future.result()
                records.append(record)
                if 'failure' in record:
                    failures.append(record['failure'])
            except Exception as exc:
                stop.set()
                failures.append({'task_id': jobs[future], 'error': f'{type(exc).__name__}: {exc}'})
    records.sort(key=lambda r:r['task_id'])
    complete = not failures and len(records)==len(data['tasks']) and all(
        len(r['arms'])==len(protocol['arms']) and all(len(a['trials'])==protocol['proposals'] for a in r['arms'].values()) for r in records)
    frozen = {'protocol_sha256': digest(protocol), 'records': records, 'complete': complete, 'failures': failures}
    write_json(output/'frozen.json', frozen)
    write_json(output/'frozen-receipt.json', {'frozen_sha256': digest(frozen), 'at': now()})
    if complete:
        return evaluate(output, 'screen')
    return {'complete': False, 'failures': failures}


def evaluate(output, partition):
    if partition not in ('screen','confirmation'):
        raise ValueError('Unknown protected partition')
    output = Path(output)
    protocol, data = verify(output)
    frozen = read(output/'frozen.json')
    if digest(frozen) != read(output/'frozen-receipt.json')['frozen_sha256'] or not frozen['complete']:
        raise ValueError('Incomplete or modified construction cannot be evaluated.')
    target = output/f'{partition}.json'
    if target.exists():
        raise ValueError('Protected panel already evaluated; use replay, not reselection.')
    # The candidate selection is bound before any protected label is executed.
    selection = {r['task_id']: {a:digest(v['selected']) for a,v in r['arms'].items()} for r in frozen['records']}
    exclusive_json(output/f'{partition}-selection.json', {'frozen_sha256': digest(frozen), 'selection': selection})
    results = protected_results(data, frozen, partition)
    write_json(target, results)
    return summary(output, partition)


def protected_results(data, frozen, partition):
    tasks = {t['id']:t for t in data['tasks']}
    results = {}
    for record in frozen['records']:
        task = tasks[record['task_id']]
        results[task['id']] = {'initial': score(task['initial_source'], task[partition]), 'arms': {}, 'attempts': {}}
        for arm, state in record['arms'].items():
            selected = state['selected']
            results[task['id']]['arms'][arm] = score(selected['source'], task[partition],
                constraint(task, arm, selected['source']))
            results[task['id']]['attempts'][arm] = [score(trial['source'], task[partition],
                trial['constraint_error']) for trial in state['trials']]
    return {'frozen_sha256': digest(frozen), 'partition': partition, 'tasks': results}


def summary(output, partition='screen'):
    output=Path(output)
    data=read(output/f'{partition}.json')
    result={'partition':partition,'tasks':{},'totals':{}}
    for task,row in data['tasks'].items():
        result['tasks'][task]={}
        for arm,score_row in {'initial':row['initial'],**row['arms']}.items():
            values={k:score_row[k] for k in ('correct','total','errors')}
            result['tasks'][task][arm]=values
            total=result['totals'].setdefault(arm,dict.fromkeys(values,0))
            for k,v in values.items():total[k]+=v
    path=output/'budget/budget.json'
    if path.exists():
        budget=read(path)
        result['billing']={k:budget[k] for k in ('total_reported_cost_usd','total_reserved_usd','halted')}
        result['billing']['attempts']=len(budget['entries'])
    write_json(output/f'{partition}-summary.json',result)
    return result


def replay(output):
    output=Path(output)
    protocol,data=verify(output)
    frozen=read(output/'frozen.json')
    assert digest(frozen)==read(output/'frozen-receipt.json')['frozen_sha256']
    tasks={t['id']:t for t in data['tasks']}
    checked=0
    for record in frozen['records']:
        task=tasks[record['task_id']]
        for arm,state in record['arms'].items():
            current=state['initial']
            assert current['development']==score(current['source'],training(task))
            trials=[]
            for trial in state['trials']:
                node=trial['node_id']; response=read(output/'responses'/f'{node}.json')
                envelope=read(output/'prompts'/f'{node}.json')
                assert digest(envelope)==trial['prompt_sha256']==response['prompt_sha256']
                assert envelope=={'prompt':prompt_for(task,arm,current,trials),'system':LANGUAGE,'response_schema':SCHEMA}
                assert hashlib.sha256(response['raw'].encode()).hexdigest()==trial['raw_sha256']
                if trial['response_error'] is None:
                    proposal=json.loads(response['raw']); validate(proposal,SCHEMA)
                    assert all(proposal[k]==trial[k] for k in SCHEMA['required'])
                assert trial['development']==score(trial['source'],training(task),trial['constraint_error'])
                error=trial['response_error'] or constraint(task,arm,trial['source'])
                assert error==trial['constraint_error']
                if error is None and (trial['development']['correct'],-trial['development']['errors']) >= (current['development']['correct'],-current['development']['errors']):current=trial
                trials.append(trial); checked+=1
            assert current==state['selected']
    partitions=[]
    for partition in ('screen','confirmation'):
        if (output/f'{partition}.json').exists():
            assert read(output/f'{partition}.json')==protected_results(data,frozen,partition)
            selection=read(output/f'{partition}-selection.json')
            assert selection=={'frozen_sha256':digest(frozen),'selection':{r['task_id']:{a:digest(v['selected']) for a,v in r['arms'].items()} for r in frozen['records']}}
            partitions.append(partition)
    return {'ok':True,'construction_attempts':checked,'protected_partitions':partitions}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    subs=parser.add_subparsers(dest='command',required=True)
    p=subs.add_parser('prepare'); p.add_argument('output',type=Path)
    p.add_argument('--model',required=True); p.add_argument('--providers',nargs='+',required=True)
    p.add_argument('--dataset',choices=('structural','state','bindings'),default='structural')
    p.add_argument('--seed',type=int,default=20261014); p.add_argument('--panel-size',type=int,default=24)
    p.add_argument('--arms',nargs='+',choices=ARMS,default=ARMS); p.add_argument('--proposals',type=int,default=2)
    p.add_argument('--max-cost-usd',default='0.75'); p.add_argument('--max-output-tokens',type=int,default=6144)
    p.add_argument('--reasoning-effort',default='none'); p.add_argument('--workers',type=int,default=3)
    p.add_argument('--model-evidence',type=Path)
    for command in ('run','confirm','replay','summary'):
        p=subs.add_parser(command);p.add_argument('output',type=Path)
        if command=='run':p.add_argument('--env-file',type=Path)
        if command=='summary':p.add_argument('--partition',default='screen')
    args=vars(parser.parse_args());command=args.pop('command');output=args.pop('output')
    if command=='prepare':
        kind=args.pop('dataset')
        if kind!='structural':
            from research.state_discovery_tasks import build_dataset as state_dataset, build_transfer_dataset
            builder=state_dataset if kind=='state' else build_transfer_dataset
            args['dataset']=builder(seed=args['seed'],panel_size=args['panel_size'])
        args['model_evidence']=read(args['model_evidence']) if args['model_evidence'] else None
        result=prepare(output,**args)
    elif command=='run':result=run(output,**args)
    elif command=='confirm':result=evaluate(output,'confirmation')
    elif command=='replay':result=replay(output)
    else:result=summary(output,**args)
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
