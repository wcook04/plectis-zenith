"""Learn an executable investigator, measure its questions, and repair a program.

Adapts the offline probe host from ADVANCE return14 to Zenith's existing
executor, provider and immutable evidence. The unit is a fresh parent program;
native source queries are measurements, not independent experimental subjects.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
from pathlib import Path
import threading
import time

from jsonschema import ValidationError, validate

from research.decomposition_study import (
    LANGUAGE, SCHEMA, call_structure, exclusive_json, read, score,
)
from research.native_conformance_tasks import build_dataset, measure, public_task, query_units
from zenith.budgeted import OpenRouterBudgetedProvider, budget_options
from zenith.investigation_program import execute, validate_source
from zenith.providers import digest, now, write_json
from zenith.source_snapshot import archive_runtime

ROOT = Path(__file__).resolve().parents[1]
VERSION = 'zenith_conformance_study_v3'
ARMS = ('ordinary', 'witness', 'fixed')
PROBE_CAP = 8
POLICY_LANGUAGE = '''You write an EXPERIMENT SELECTOR, not the program being tested.
Return one JSON object with source, scope and change strings. source defines
investigate(context, acquire). Its result MUST be an object with query and
optional note: {"query": a legal native input object or null, "note": short JSON}.
Never return the native source's answer shape. The quoted native contract and
examples describe the system you are testing, not your own return contract.
context contains source_id, contract, parent_source, examples, receipts,
remaining_slots. Inspect this context to choose one revealing input. The host
executes that input on the native source and parent program, then invokes you
again with the resulting receipt. No API calls or external tables are available.
Past receipts include query errors, native expected values, parent answers/errors,
and verified_counterexample. Do not supply an expected answer yourself. Avoid
queries already in examples or receipts. Null stops. You have eight query slots.
Optional notes are hypotheses for later whole-program repair, at most2048bytes.
Write a concise selector; do not recreate the entire native library unless a
small local simulation actually helps select a discriminating input.
''' + LANGUAGE[LANGUAGE.index('Only function definitions at module level.'):]
POLICY_INSTRUCTIONS = {
    'ordinary': 'Write the strongest small adaptive investigation program you can. Inspect the whole parent code and public native contract. Seek a legal input on which the parent disagrees with the native source. Use code inspection, examples, receipts, stateful testing and boundaries freely. Avoid duplicate queries; null stops. Up to eight native query slots are available. You may include a brief note useful for a later repair. No particular decomposition is required.',
    'witness': 'Write a small adaptive investigator. Use the functions, callers and downstream obligation to find what the parent overlooks. Consider a wrong readout of sufficient state, a wrong update, or genuinely missing information; do not assume any one diagnosis. Choose a legal native query that could reveal the issue. Return the normal query plus, when useful, a compact note stating the obligation, suspected boundary/assumption, evidence and proposed change. Your note is a hypothesis; measured results decide whether there is a defect. You may propose removing or bypassing a decomposition. Avoid duplicate queries; null stops. Up to eight native query slots are available.',
}


def dependencies():
    paths = ('research/conformance_study.py', 'research/native_conformance_tasks.py',
             'research/decomposition_study.py', 'research/decomposition_tasks.py',
             'zenith/source_snapshot.py', 'zenith/investigation_program.py',
             'zenith/budgeted.py', 'zenith/provider_policy.py', 'zenith/providers.py',
             'system/lib/openrouter_free_runtime.py')
    return {p: hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in paths}


def score_program(source, examples, error=None):
    try:
        return score(source, examples, error)
    except RuntimeError as exc:
        return score('', examples, 'Execution resource failure: '+str(exc)[:400])


def invoke(source, context):
    try:
        return execute(source, [{'tables': {}, **context}], answer_contract='json')[0]
    except (ValueError, SyntaxError, RuntimeError) as exc:
        return {'answer': None, 'trace': [], 'error': f'{type(exc).__name__}: {exc}'[:500]}


def parse_model_response(raw):
    """Keep malformed delivery as an outcome, with identical replay semantics."""
    body = {'source': '', 'scope': '', 'change': ''}
    try:
        decoded = json.loads(raw)
        validate(decoded, SCHEMA)
        body = decoded
        validate_source(body['source'])
    except (ValueError, SyntaxError, ValidationError) as exc:
        return {**body, 'error': f'{type(exc).__name__}: {exc}'[:1000]}
    return {**body, 'error': None}


def investigate(task, parent, policy=None, *, fixed=False, cap=PROBE_CAP):
    """An invalid or duplicate proposal consumes its slot; stop on a real defect.

    Only a valid native input can refute a parent. Native decoder errors are
    observations under the public contract, not host failures. Reports are
    bounded model hypotheses delivered with the measured evidence to repair.
    No privileged graph routing or certified diagnosis is implied.
    """
    receipts, seen = [], {digest(e['input']) for e in task['examples']}
    measured = units = executions = attempted = 0
    for slot in range(cap):
        note = None
        if fixed:
            if slot >= len(task['fixed_queries']):
                break
            query = task['fixed_queries'][slot]
        else:
            executions += 1
            context = {'source_id': task['source_id'], 'contract': task['contract'],
                       'parent_source': parent, 'examples': task['examples'],
                       'receipts': receipts, 'remaining_slots': cap-slot}
            output = invoke(policy or '', context)
            if output['error'] is not None:
                receipts.append({'slot': slot+1, 'policy_error': output['error']})
                break
            body = output['answer']
            if type(body) is not dict or 'query' not in body or set(body)-{'query', 'note'}:
                receipts.append({'slot': slot+1, 'policy_error': 'Return query and optional note.'})
                break
            query, note = body['query'], body.get('note')
            if note is not None and len(json.dumps(note, ensure_ascii=True).encode()) > 2048:
                receipts.append({'slot': slot+1, 'policy_error': 'Note exceeds 2048 serialized bytes.'})
                break
            if query is None:
                receipts.append({'slot': slot+1, 'stopped': True, 'note': note})
                break
        identity = digest(query)
        if identity in seen:
            receipts.append({'slot': slot+1, 'query': query, 'query_error': 'Duplicate of an example or earlier query; slot consumed.', 'note': note})
            continue
        seen.add(identity)
        attempted += 1
        try:
            if len(json.dumps(query, ensure_ascii=True).encode()) > 16000:
                raise ValueError('Query exceeds 16000 serialized bytes.')
            expected = measure(task['source_id'], query)
            work = query_units(query)
        except (ValueError, TypeError, KeyError, OverflowError) as exc:
            receipts.append({'slot': slot+1, 'query': query, 'query_error': f'{type(exc).__name__}: {exc}'[:500], 'note': note})
            continue
        measured += 1
        units += work
        actual = invoke(parent, query)
        wrong = actual['error'] is not None or digest(actual['answer']) != digest(expected)
        row = {'slot': slot+1, 'query': query, 'expected': expected,
               'parent_answer': actual['answer'], 'parent_error': actual['error'],
               'verified_counterexample': wrong, 'query_units': work, 'note': note}
        receipts.append(row)
        if wrong:
            break
    witness = next((r for r in receipts if r.get('verified_counterexample')), None)
    return {'receipts': receipts, 'native_probes': measured, 'query_attempts': attempted,
            'query_units': units, 'policy_executions': executions,
            'slots_used': len(receipts), 'detected': witness is not None,
            'semantic_defect': witness is not None and witness['parent_error'] is None,
            'technical_defect': witness is not None and witness['parent_error'] is not None,
            'witness_sha256': digest(witness) if witness else None}


def parent_prompt(task):
    return {'task': public_task(task), 'instruction':
        'Implement the native behavior in ordinary restricted Python from this public contract and measured examples. You may use arbitrary helpers and state within a query. Return the simplest correct whole program. This is your first proposal; no source oracle or hidden evaluator is available.'}


def policy_prompt(task, parent, arm):
    return {'task': public_task(task), 'parent_source': parent['source'],
            'parent_examples': parent['development'],
            'functions': call_structure(parent['source']) if not parent['error'] else [],
            'instruction': POLICY_INSTRUCTIONS[arm], 'probe_slots': PROBE_CAP,
            'context_fields': ['source_id', 'contract', 'parent_source', 'examples', 'receipts', 'remaining_slots'],
            'note_status': 'Optional proposal, not verified introspection or evidence.'}


def repair_examples(task, investigation):
    return task['examples'] + [{'input': r['query'], 'expected': r['expected']}
                               for r in investigation['receipts'] if 'expected' in r]


def repair_prompt(task, parent, investigation):
    return {'task': public_task(task), 'parent_source': parent['source'],
            'parent_examples': parent['development'],
            'investigation': investigation,
            'instruction': 'Repair the complete ordinary program using all measured outcomes. Investigator notes are hypotheses: inspect the code and receipts yourself. You may change any function, interface or state, remove the decomposition or preserve correct code. Retain all previously correct obligations, not only the latest witness. Return source, scope and change.'}


def selected_candidate(parent, candidate, examples):
    before = score_program(parent['source'], examples, parent['error'])
    after = score_program(candidate['source'], examples, candidate['error'])
    preserves = all(not old['correct'] or new['correct']
                    for old, new in zip(before['rows'], after['rows'], strict=True))
    retain = candidate['error'] is None and preserves and (after['correct'], -after['errors']) >= (before['correct'], -before['errors'])
    return {'source': (candidate if retain else parent)['source'],
            'call_id': (candidate if retain else parent)['call_id'],
            'error': (candidate if retain else parent)['error'],
            'development': after if retain else before, 'candidate_selected': retain,
            'preserves_measured_parent_successes': preserves,
            'parent_on_final_evidence': before, 'candidate_on_final_evidence': after}


def prepare(output, model, providers, *, seed=20261015, panel_size=48,
            arms=ARMS, max_cost_usd='0.60', max_output_tokens=12288,
            reasoning_effort='low', workers=3, model_evidence=None, dataset=None):
    output = Path(output).resolve()
    if not providers or not arms or len(set(arms)) != len(arms) or not set(arms) <= set(ARMS):
        raise ValueError('Explicit routes and distinct known arms required.')
    if not 1 <= workers <= 3:
        raise ValueError('One to three workers required.')
    if reasoning_effort not in ('none', 'low', 'medium', 'high'):
        raise ValueError('Unknown reasoning effort.')
    data = dataset if dataset is not None else build_dataset(seed=seed, panel_size=panel_size)
    calls = len(data['tasks']) * (1 + len(arms) + sum(a != 'fixed' for a in arms))
    budget_options(model, max_cost_usd, calls, max_output_tokens, output/'budget')
    output.mkdir(parents=True, exist_ok=False)
    write_json(output/'datasets.json', data)
    archive = archive_runtime(output); archive['path'] = 'runtime-source.zip'
    protocol = {'schema': VERSION, 'created_at': now(), 'model': model,
        'providers': providers, 'arms': list(arms), 'max_calls': calls,
        'max_cost_usd': str(max_cost_usd), 'max_output_tokens': max_output_tokens,
        'reasoning_effort': reasoning_effort, 'workers': workers, 'probe_cap': PROBE_CAP,
        'task_routes': {t['id']: providers[(i+i//len(providers)) % len(providers)] for i,t in enumerate(data['tasks'])},
        'task_arm_order': {t['id']:list(arms[i % len(arms):])+list(arms[:i % len(arms)]) for i,t in enumerate(data['tasks'])},
        'dataset_sha256': digest(data), 'dependencies': dependencies(), 'source': archive,
        'model_evidence': model_evidence or {},
        'selection': 'Fresh unfiltered first parents; native counterexamples; repair selected on supplied examples plus its own measured probes only, preserving every measured parent success. Every arm receives repair even without a counterexample; repair gains alone do not identify probe value.',
        'comparison': 'Ordinary/witness each use one generated policy call plus one repair; fixed uses no policy call and one repair. Each has eight probe slots, no mandatory shared probe floor. First parent is the no-change control. Notes differ in prompting only; no privileged routing.',
        'boundary': 'Exploratory comparison on authored wrappers for native software semantics. Six model parents are not six independent source mechanisms. No acquired update rule, protected novelty or production-value claim.'}
    write_json(output/'protocol.json', protocol)
    write_json(output/'preparation.json', {'protocol_sha256': digest(protocol)})
    return protocol


def verify(output):
    output = Path(output)
    protocol, data = read(output/'protocol.json'), read(output/'datasets.json')
    if protocol['schema'] != VERSION or digest(protocol) != read(output/'preparation.json')['protocol_sha256'] or digest(data) != protocol['dataset_sha256']:
        raise ValueError('Frozen protocol or data changed.')
    if dependencies() != protocol['dependencies']:
        raise ValueError('Runtime changed; replay with the archived source.')
    if hashlib.sha256((output/'runtime-source.zip').read_bytes()).hexdigest() != protocol['source']['sha256']:
        raise ValueError('Archived source changed.')
    return protocol, data


def run(output, env_file=None, *, provider_factory=None):
    output = Path(output).resolve(); protocol, data = verify(output)
    if (output/'started.json').exists():
        raise ValueError('A started study cannot be retried.')
    if provider_factory is None:
        from system.lib.openrouter_free_runtime import load_env_file
        if env_file is not None: load_env_file(Path(env_file))
        def provider_factory(task, route):
            return OpenRouterBudgetedProvider(output/'providers'/task['id'], protocol['model'],
                protocol['max_cost_usd'], protocol['max_calls'], protocol['max_output_tokens'],
                output/'budget', provider_slug=route, inference_mode='bounded')
    exclusive_json(output/'started.json', {'at': now(), 'protocol_sha256': digest(protocol)})
    stop = threading.Event(); records = []; failures = []

    def trajectory(task):
        record = {'task_id': task['id'], 'source_id': task['source_id'], 'arms': {}}
        provider = provider_factory(task, protocol['task_routes'][task['id']])
        def call(label, prompt, policy=False):
            if stop.is_set():
                raise RuntimeError('Study halted before dispatch.')
            node = task['id']+'-'+label
            system = POLICY_LANGUAGE if policy else LANGUAGE
            envelope = {'prompt': prompt, 'system': system, 'response_schema': SCHEMA}
            write_json(output/'prompts'/f'{node}.json', envelope)
            before = time.monotonic()
            raw = provider.ask_ai(json.dumps(prompt, ensure_ascii=False), {
                'meta': {'session_id': provider.run_dir.name, 'node_id': node},
                'system_prompt': system, 'reasoning_effort': protocol['reasoning_effort'],
                'response_format': {'type': 'json_schema', 'json_schema': {
                    'name': 'conformance_program', 'strict': True, 'schema': SCHEMA}}}, cancel=stop)
            write_json(output/'responses'/f'{node}.json', {'raw': raw, 'prompt_sha256': digest(envelope)})
            body = parse_model_response(raw)
            result = {**body, 'call_id': node,
                      'prompt_sha256': digest(envelope), 'raw_sha256': hashlib.sha256(raw.encode()).hexdigest(),
                      'elapsed_seconds': time.monotonic()-before}
            print(node+': '+('valid source' if body['error'] is None else body['error'][:120]), flush=True)
            return result
        try:
            parent = call('parent', parent_prompt(task))
            parent['development'] = score_program(parent['source'], task['examples'], parent['error'])
            record['parent'] = parent
            write_json(output/'records'/f'{task["id"]}.json', record)
            for arm in protocol['task_arm_order'][task['id']]:
                if stop.is_set(): break
                policy = None if arm == 'fixed' else call(arm+'-policy', policy_prompt(task, parent, arm), True)
                before = time.monotonic()
                investigation = investigate(task, parent['source'], policy['source'] if policy else None,
                                            fixed=arm == 'fixed', cap=protocol['probe_cap'])
                elapsed = time.monotonic()-before
                candidate = call(arm+'-repair', repair_prompt(task, parent, investigation))
                selected = selected_candidate(parent, candidate, repair_examples(task, investigation))
                record['arms'][arm] = {'policy': policy, 'investigation': investigation,
                    'investigation_elapsed_seconds': elapsed, 'candidate': candidate, 'selected': selected}
                write_json(output/'records'/f'{task["id"]}.json', record)
                print(task['id']+' '+arm+': '+str(investigation['native_probes'])+' probes; semantic defect '+str(investigation['semantic_defect'])+'; selected '+str(selected['candidate_selected']), flush=True)
        except Exception as exc:
            stop.set(); record['failure'] = f'{type(exc).__name__}: {exc}'[:1500]
            write_json(output/'records'/f'{task["id"]}.json', record)
        return record

    with ThreadPoolExecutor(max_workers=protocol['workers']) as pool:
        jobs = {pool.submit(trajectory, task): task['id'] for task in data['tasks']}
        for future in as_completed(jobs):
            try:
                record = future.result(); records.append(record)
                if 'failure' in record: failures.append({'task_id': record['task_id'], 'error': record['failure']})
            except Exception as exc:
                stop.set(); failures.append({'task_id': jobs[future], 'error': f'{type(exc).__name__}: {exc}'})
    records.sort(key=lambda r:r['task_id'])
    complete = not failures and len(records) == len(data['tasks']) and all(len(r['arms']) == len(protocol['arms']) for r in records)
    frozen = {'complete': complete, 'failures': failures, 'records': records, 'protocol_sha256': digest(protocol)}
    write_json(output/'frozen.json', frozen)
    write_json(output/'frozen-receipt.json', {'frozen_sha256': digest(frozen), 'at': now()})
    return evaluate(output, 'screen') if complete else {'complete': False, 'failures': failures}


def protected_results(data, frozen, partition):
    tasks = {t['id']: t for t in data['tasks']}; result = {}
    for record in frozen['records']:
        task = tasks[record['task_id']]; parent = record['parent']
        result[task['id']] = {'source_id':task['source_id'],
            'parent': score_program(parent['source'], task[partition], parent['error']), 'arms': {}}
        for arm, item in record['arms'].items():
            selected = item['selected']; candidate = item['candidate']
            result[task['id']]['arms'][arm] = {
                'selected': score_program(selected['source'], task[partition], selected['error']),
                'attempt': score_program(candidate['source'], task[partition], candidate['error'])}
    return {'partition': partition, 'frozen_sha256': digest(frozen), 'tasks': result}


def summarize_results(data, frozen, budget=None):
    """Derive public totals from rows and receipts, not stored aggregate claims."""
    totals = {}; by_task = {}
    for task_id, task in data['tasks'].items():
        by_task[task_id] = {'source_id': task['source_id']}
        for arm, item in {'parent':task['parent'], **{a:v['selected'] for a,v in task['arms'].items()}}.items():
            values = {'correct':sum(r['correct'] for r in item['rows']),
                      'total':len(item['rows']), 'errors':sum(r['error'] is not None for r in item['rows'])}
            if values != {k:item[k] for k in values}:
                raise ValueError('Panel totals differ from its rows.')
            by_task[task_id][arm] = values; total = totals.setdefault(arm, dict(correct=0,total=0,errors=0))
            for k,v in values.items(): total[k] += v
    detection = {}
    for record in frozen['records']:
        for arm, item in record['arms'].items():
            target = detection.setdefault(arm, dict(episodes=0,detected=0,semantic_defects=0,technical_defects=0,native_probes=0,query_attempts=0,query_units=0))
            target['episodes'] += 1
            for out,src in [('detected','detected'),('semantic_defects','semantic_defect'),('technical_defects','technical_defect'),('native_probes','native_probes'),('query_attempts','query_attempts'),('query_units','query_units')]:
                target[out] += item['investigation'][src]
    result = {'partition': data['partition'], 'totals': totals, 'by_task': by_task, 'detection': detection}
    if budget is not None:
        result['billing'] = {k:budget[k] for k in ('total_reported_cost_usd','total_reserved_usd','halted')}
        result['billing']['attempts'] = len(budget['entries'])
    return result


def summary(output, partition):
    output = Path(output)
    budget = output/'budget/budget.json'
    if not budget.exists(): budget = output/'billing.json'
    result = summarize_results(read(output/(partition+'.json')), read(output/'frozen.json'),
                               read(budget) if budget.exists() else None)
    write_json(output/(partition+'-summary.json'), result)
    return result


def evaluate(output, partition):
    if partition not in ('screen','confirmation'): raise ValueError('Unknown partition.')
    output = Path(output); protocol, data = verify(output); frozen = read(output/'frozen.json')
    if not frozen['complete'] or digest(frozen) != read(output/'frozen-receipt.json')['frozen_sha256']:
        raise ValueError('Incomplete or changed construction.')
    if (output/(partition+'.json')).exists(): raise ValueError('Panel already opened; replay rather than reselect.')
    selection = {r['task_id']:{a:digest(v['selected']) for a,v in r['arms'].items()} for r in frozen['records']}
    exclusive_json(output/(partition+'-selection.json'), {'frozen_sha256':digest(frozen),'selection':selection})
    write_json(output/(partition+'.json'), protected_results(data, frozen, partition))
    return summary(output, partition)


def replay(output):
    output = Path(output); protocol, data = verify(output); frozen = read(output/'frozen.json')
    assert frozen['complete'] and digest(frozen) == read(output/'frozen-receipt.json')['frozen_sha256']
    tasks = {t['id']:t for t in data['tasks']}; calls = 0
    def check_call(trial, prompt, policy=False):
        nonlocal calls
        envelope = {'prompt':prompt,'system':POLICY_LANGUAGE if policy else LANGUAGE,'response_schema':SCHEMA}
        assert read(output/'prompts'/(trial['call_id']+'.json')) == envelope
        raw = read(output/'responses'/(trial['call_id']+'.json'))
        assert raw['prompt_sha256'] == digest(envelope) == trial['prompt_sha256']
        assert hashlib.sha256(raw['raw'].encode()).hexdigest() == trial['raw_sha256']
        body = parse_model_response(raw['raw'])
        assert all(body[k] == trial[k] for k in (*SCHEMA['required'], 'error'))
        calls += 1
    for record in frozen['records']:
        task = tasks[record['task_id']]; parent = record['parent']
        check_call(parent, parent_prompt(task))
        assert parent['development'] == score_program(parent['source'], task['examples'], parent['error'])
        for arm,item in record['arms'].items():
            policy = item['policy']
            if policy is not None: check_call(policy, policy_prompt(task,parent,arm), True)
            investigation = investigate(task,parent['source'],policy['source'] if policy else None,fixed=arm=='fixed',cap=protocol['probe_cap'])
            assert investigation == item['investigation']
            check_call(item['candidate'], repair_prompt(task,parent,investigation))
            assert selected_candidate(parent,item['candidate'],repair_examples(task,investigation)) == item['selected']
    assert calls == protocol['max_calls']
    assert len(frozen['records']) == len(tasks)
    assert {r['task_id'] for r in frozen['records']} == set(tasks)
    assert all(set(r['arms']) == set(protocol['arms']) for r in frozen['records'])
    partitions=[]
    for name in ('screen','confirmation'):
        if (output/(name+'.json')).exists():
            assert read(output/(name+'.json')) == protected_results(data,frozen,name)
            selection={r['task_id']:{a:digest(v['selected']) for a,v in r['arms'].items()} for r in frozen['records']}
            assert read(output/(name+'-selection.json')) == {'frozen_sha256':digest(frozen),'selection':selection}
            budget=output/'budget/budget.json'
            if not budget.exists(): budget=output/'billing.json'
            assert read(output/(name+'-summary.json')) == summarize_results(
                read(output/(name+'.json')),frozen,read(budget) if budget.exists() else None)
            partitions.append(name)
    return {'ok':True,'model_calls_replayed':calls,'native_investigations':sum(len(r['arms']) for r in frozen['records']),'protected_partitions':partitions}


def main():
    parser=argparse.ArgumentParser(description=__doc__); subs=parser.add_subparsers(dest='command',required=True)
    p=subs.add_parser('prepare'); p.add_argument('output',type=Path);p.add_argument('--model',required=True);p.add_argument('--providers',nargs='+',required=True)
    p.add_argument('--seed',type=int,default=20261015);p.add_argument('--panel-size',type=int,default=48);p.add_argument('--arms',nargs='+',choices=ARMS,default=ARMS)
    p.add_argument('--max-cost-usd',default='0.60');p.add_argument('--max-output-tokens',type=int,default=12288);p.add_argument('--reasoning-effort',default='low');p.add_argument('--workers',type=int,default=3);p.add_argument('--model-evidence',type=Path)
    for name in ('run','confirm','replay','summary'):
        p=subs.add_parser(name);p.add_argument('output',type=Path)
        if name=='run':p.add_argument('--env-file',type=Path)
        if name=='summary':p.add_argument('--partition',default='screen')
    args=vars(parser.parse_args());command=args.pop('command');output=args.pop('output')
    if command=='prepare':
        args['model_evidence']=read(args['model_evidence']) if args['model_evidence'] else None
        result=prepare(output,**args)
    elif command=='run':result=run(output,**args)
    elif command=='confirm':result=evaluate(output,'confirmation')
    elif command=='replay':result=replay(output)
    else:result=summary(output,**args)
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
