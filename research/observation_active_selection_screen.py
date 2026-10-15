"""Zero-inference probe and candidate-selection assay on a frozen inventory."""
from __future__ import annotations
import argparse
import hashlib
import itertools
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
from zipfile import ZipFile

from research import observation_candidate_pool_screen as pool
from research import observation_repair_screen as repair
from zenith.providers import digest, write_json

VERSION = 'zenith_observation_active_selection_v1'
POLICIES = ('fixed', 'disagreement')
SELECTORS = ('initial', 'reselect')
ARMS = tuple(p + '_' + s for p in POLICIES for s in SELECTORS)
REFERENCES = ('historical_initial', 'historical_reselect')


def parent_inventory(path):
    """Replay the completed parent with its original bytes, independent of live edits."""
    old,data,frozen = [repair.read(path/f'{name}.json') for name in ('protocol','datasets','all-frozen')]
    prepared,receipt = [repair.read(path/f'{name}.json') for name in ('preparation-receipt','all-frozen-receipt')]
    archive = path/'runtime-source.zip'
    if (digest(old)!=prepared['protocol_sha256'] or digest(data)!=old['dataset_sha256'] or
        digest(data)!=prepared['dataset_sha256'] or digest(frozen)!=receipt['frozen_sha256'] or
        digest(old)!=receipt['protocol_sha256'] or not (path/'results.json').exists() or
        hashlib.sha256(archive.read_bytes()).hexdigest()!=old['source']['sha256']):
        raise ValueError('completed parent custody differs')
    raw = {p.name.removesuffix('-raw.json'):repair.read(p)['content'] for p in (path/'responses').glob('*-raw.json')}
    prompts = {p.stem:repair.read(p) for p in (path/'prompts').glob('*.json')}
    ledger=repair.read(path/'budget/budget.json'); bindings=[]
    for node,content in raw.items():
        matches=[e for e in ledger['entries'].values() if e['node_id']==node]
        if len(matches)!=1: raise ValueError('parent attempt delivery missing or duplicated')
        call=matches[0]; request=prompts[node]
        response_format={'type':'json_schema','json_schema':{'name':'observation','strict':True,'schema':request['schema']}}
        if (hashlib.sha256(content.encode()).hexdigest()!=call['response_sha256'] or
            call['provider_response']['choices'][0]['message']['content']!=content or
            hashlib.sha256(json.dumps(request['prompt'],ensure_ascii=False).encode()).hexdigest()!=call['prompt_sha256'] or
            hashlib.sha256(request['system'].encode()).hexdigest()!=call['system_prompt_sha256'] or
            digest(response_format)!=call['response_format_sha256']): raise ValueError('parent delivery binding differs')
        bindings.append({'call_id':call['call_id'],'node_id':node,'original_entry_sha256':digest(call),
            'response_sha256':call['response_sha256'],'prompt_sha256':call['prompt_sha256']})
    worker = '''import json,socket,sys
from pathlib import Path
sys.path.insert(0,sys.argv[1])
def forbidden(*a,**k): raise RuntimeError("network disabled")
socket.create_connection=forbidden
socket.socket.connect=forbidden
from research.observation_candidate_pool_screen import replay_records
print(json.dumps(replay_records(*json.loads(Path(sys.argv[2]).read_text()))))
'''
    with tempfile.TemporaryDirectory(prefix='active-parent-replay-') as temporary:
        root=Path(temporary)/'runtime'
        with ZipFile(archive) as source:
            names=source.namelist()
            if len(names)!=len(set(names)) or any(Path(n).is_absolute() or '..' in Path(n).parts for n in names):
                raise ValueError('unsafe parent archive')
            for name,expected in old['runtime_dependencies'].items():
                if hashlib.sha256(source.read(name)).hexdigest()!=expected: raise ValueError('parent source dependency differs')
            source.extractall(root)
        inputs=Path(temporary)/'input.json'; inputs.write_text(json.dumps([old,data,frozen,raw,prompts]))
        result=subprocess.run([sys.executable,'-I','-c',worker,str(root),str(inputs)],env={},text=True,capture_output=True)
        if result.returncode: raise ValueError('archived parent construction replay failed: '+result.stderr[-1000:])
        custody=json.loads(result.stdout)
        custody['new_delivery_bindings']=sorted(bindings,key=lambda b:b['node_id'])
    return old,data,frozen,custody


def historical_inventory(path, targets):
    """Bind every same-source V5 proposal to original delivery, never its score."""
    path = Path(path); protocol = repair.read(path/'protocol.json'); data = repair.read(path/'datasets.json')
    frozen = repair.read(path/'all-frozen.json'); prepared = repair.read(path/'preparation-receipt.json')
    receipt = repair.read(path/'all-frozen-receipt.json')
    if (digest(protocol) != prepared['protocol_sha256'] or digest(data) != protocol['dataset_sha256'] or
        digest(data) != prepared['dataset_sha256'] or digest(frozen) != receipt['frozen_sha256'] or
        digest(protocol) != receipt['protocol_sha256'] or
        hashlib.sha256((path/'runtime-source.zip').read_bytes()).hexdigest() != protocol['source']['sha256']):
        raise ValueError('historical source custody differs')
    ledger = repair.read(path/'budget/budget.json')
    calls = {e['node_id']: e for e in ledger['entries'].values()}
    if len(calls) != len(ledger['entries']): raise ValueError('duplicate historical call node')
    inventories = []
    for target in targets:
        matched = [(i,r) for i,r in enumerate(frozen) if r['source_id'] == target['source_id']]
        if len(matched) != 1 or data['private']['configs'][target['source_id']] != target['config']:
            raise ValueError('historical source identity or configuration differs')
        index, record = matched[0]; slots = []
        for arm in ('incremental','archive','fresh'):
            rounds = record['arms'][arm]['rounds']
            if len(rounds) != 6: raise ValueError('all eighteen historical attempts required')
            for step, trial in enumerate(rounds):
                episode, local = (0,step) if arm == 'fresh' else divmod(step,2)
                node = f'world-{index:02d}-{arm}-{episode}-{local}'
                call = calls[node]; prompt = repair.read(path/'prompts'/f'{node}.json')
                raw = repair.read(path/'responses'/f'{node}-raw.json')['content']
                response_format = {'type':'json_schema','json_schema':{'name':'observation','strict':True,'schema':prompt['schema']}}
                if (hashlib.sha256(raw.encode()).hexdigest() != call['response_sha256'] or
                    call['provider_response']['choices'][0]['message']['content'] != raw or
                    hashlib.sha256(json.dumps(prompt['prompt'],ensure_ascii=False).encode()).hexdigest() != call['prompt_sha256'] or
                    hashlib.sha256(prompt['system'].encode()).hexdigest() != call['system_prompt_sha256'] or
                    digest(response_format) != call['response_format_sha256']):
                    raise ValueError('historical model delivery differs')
                try:
                    proposal = json.loads(raw); pool.validate(proposal, repair.PROGRAM_SCHEMA)
                except (ValueError,pool.ValidationError):
                    if not trial.get('response_error') or trial['response_error']['raw_content'] != raw:
                        raise ValueError('historical malformed response differs')
                else:
                    if proposal != trial['proposal']: raise ValueError('historical proposal differs from response')
                slots.append({'slot_id':node,'proposal':trial['proposal'],'response_error':trial.get('response_error'),
                    'lineage':{'call_id':call['call_id'],'node_id':node,'original_entry_sha256':digest(call),
                        'model':call['requested_model'],'provider_slug':call['requested_provider_slug'],
                        'response_sha256':call['response_sha256'],'prompt_sha256':call['prompt_sha256']}})
        inventories.append(slots)
    return inventories, {'protocol_sha256':digest(protocol),'dataset_sha256':digest(data),
        'frozen_sha256':digest(frozen),'source_archive_sha256':protocol['source']['sha256']}


def prepare(output, parent, *, archive_parent=None, seed=20261019, probe_budget=2, probe_pool_size=8, final_size=32):
    if probe_budget != 2 or not 2 <= probe_pool_size <= 16:
        raise ValueError('exactly two probes and a pool of 2..16 actions required')
    parent, output = Path(parent).resolve(), Path(output).resolve()
    old, data, frozen, custody = parent_inventory(parent)
    if old['schema'] != pool.VERSION:
        raise ValueError('completed candidate-pool parent required')
    forbidden = {tuple(tuple(a) for a in s) for s in data['excluded_structures']}
    forbidden.update(repair.shape(a) for key in ('screen_actions', 'confirmation_actions') for a in data[key])
    targets = []
    for target, record in zip(data['targets'], frozen):
        if target['id'] != record['id']:
            raise ValueError('parent target order differs')
        slots = [s for label in pool.MODELS for s in record['arms'][label+'4']['slots']]
        if len(slots) != 8 or len({s['slot_id'] for s in slots}) != 8:
            raise ValueError('eight distinct attempt slots required')
        inventory = [{k: s[k] for k in ('slot_id', 'model_label', 'origin', 'proposal', 'response_error')}
                     for s in slots]
        targets.append({k: target[k] for k in ('id', 'source_id', 'config', 'history')} | {'inventory': inventory})
        forbidden.update(repair.shape(r['actions']) for r in target['history'])
    if archive_parent is None:
        archive_parent = repair.read(Path(data['inputs']['deepseek']['path'])/'protocol.json')['parent']
    historical, lineage = historical_inventory(archive_parent,targets)
    if any(lineage[k] != data['ancestor'][k] for k in ('protocol_sha256','dataset_sha256','frozen_sha256')):
        raise ValueError('historical archive differs from candidate ancestor')
    for target, inventory in zip(targets,historical): target['historical_inventory'] = inventory
    probes = repair.action_pool(seed, probe_pool_size, forbidden)
    final = repair.action_pool(seed+1, final_size, forbidden | {repair.shape(a) for a in probes})
    dataset = {'targets': targets, 'probe_actions': probes, 'final_actions': final,
        'excluded_structures': sorted(forbidden), 'parent_custody': custody}
    required = repair.dependencies()
    for module in (pool, sys.modules[__name__]):
        path = Path(module.__file__).resolve()
        required[str(path.relative_to(repair.ROOT))] = hashlib.sha256(path.read_bytes()).hexdigest()
    output.mkdir(parents=True, exist_ok=False)
    protocol = {'schema': VERSION, 'seed': seed, 'probe_budget': probe_budget, 'arms': list(ARMS),
        'dataset_sha256': digest(dataset), 'runtime_dependencies': required, 'source': repair.archive(output, required),
        'python_version': sys.version, 'sqlite_version': sqlite3.sqlite_version, 'calls': 0,
        'parent': {'protocol_sha256': digest(old), 'dataset_sha256': digest(data),
                   'frozen_sha256': digest(frozen), 'source_archive_sha256': old['source']['sha256'],
                   'models': old['models'], 'construction_replay': custody},
        'inventory_sha256': digest([t['inventory'] for t in targets]),
        'historical': {'lineage':lineage,'inventory_sha256':digest(historical),'attempts_per_source':18,
            'arms':list(REFERENCES),'boundary':'Unequal historical eighteen-proposal search budget versus eight current slots. Zero new inference; development selection only; identical fixed-policy receipts and no additional probes.'},
        'selection': old['selection_rule'],
        'probe_rule': 'Fixed: first unused pool index. Disagreement: maximum unequal pairs of valid answers, summed across three goals, then first index. Errors excluded; identical source bytes have one vote. No unchosen native labels are executed.',
        'matching': 'Eight frozen attempt slots/source in every condition. Two native probes/policy/source. Initial and reselect share identical receipt histories within each policy. Only reselect can change the initial candidate. No new inference.',
        'boundary': 'Authored disagreement and development selection, not LLM active learning. Same retrospectively selected sources and disclosed native family; no new generation, domain replication or open-world identification claim.',
        'primary': 'Supported correct resolved count and coverage on the fixed final query denominator; report supported denominator, wrong, unsupported, abstentions and errors separately. Exact family-conditional score is secondary.'}
    write_json(output/'datasets.json', dataset); write_json(output/'protocol.json', protocol)
    write_json(output/'preparation-receipt.json', {'protocol_sha256': digest(protocol), 'dataset_sha256': digest(dataset)})
    return protocol


def selection(target, history, inventory='inventory'):
    chosen = pool.select(target[inventory], repair.development(repair.WorldConfig(**target['config']), history))
    return {'selected_slot': chosen['selected_slot'], 'source_sha256':
        hashlib.sha256(chosen['champion']['source'].encode()).hexdigest(),
        'development_summary': chosen['development_summary'],
        'slots': [{'slot_id': s['slot_id'], 'development': s['development']} for s in chosen['slots']]}


def program(target, selected, inventory='inventory'):
    return next((s['proposal'] for s in target[inventory] if s['slot_id'] == selected['selected_slot']), repair.UNKNOWN)


def predictions(target, history, actions):
    """Public contexts only: never call cases, compatible, observe or native SQL."""
    contexts = [{'id': digest([target['source_id'], history, a, g]), 'source_id': target['source_id'],
        'actions': a, 'goal': g, 'documentation': repair.task_spec(), 'tables': {'history': history}}
        for a in actions for g in repair.GOALS]
    # Reuse the existing answer validator/process limits; this explicit dummy key
    # is discarded. It requires no evaluator or numerical native outcomes.
    dummy = {'value': None, 'unresolved': True}
    result = []
    for slot in target['inventory']:
        rows = repair.score(slot['proposal']['source'], [(c, dummy) for c in contexts])['rows']
        if slot.get('response_error'):
            for row in rows: row['error'] = slot['response_error']['schema_error']
        result.append({'slot_id': slot['slot_id'], 'source_sha256': hashlib.sha256(slot['proposal']['source'].encode()).hexdigest(),
                       'rows': [{k: r[k] for k in ('answer', 'error', 'trace')} for r in rows]})
    return result


def choose(policy, predicted, remaining):
    votes = list({p['source_sha256']: p for p in predicted}.values())
    values = {}
    for index in remaining:
        count = 0
        for goal in range(len(repair.GOALS)):
            answers = [p['rows'][index*len(repair.GOALS)+goal]['answer'] for p in votes
                       if p['rows'][index*len(repair.GOALS)+goal]['error'] is None]
            count += sum(a != b for a, b in itertools.combinations(answers, 2))
        values[index] = count
    if policy not in POLICIES:
        raise ValueError('unknown probe policy')
    return min(remaining, key=lambda i: (-values[i] if policy == 'disagreement' else 0, i)), values


def construct(protocol, dataset, saved=None, record_round=None):
    records, measured = [], 0
    for target_index, target in enumerate(dataset['targets']):
        config = repair.WorldConfig(**target['config'])
        initial = selection(target, target['history'])
        record = {'id': target['id'], 'initial': initial, 'policies': {},
                  'historical_initial':selection(target,target['history'],'historical_inventory')}
        for policy in POLICIES:
            history = json.loads(json.dumps(target['history'])); rounds = []; remaining = list(range(len(dataset['probe_actions'])))
            selected = initial
            for step in range(protocol['probe_budget']):
                predicted = predictions(target, history, dataset['probe_actions'])
                index, scores = choose(policy, predicted, remaining)
                if saved is None:
                    receipt = repair.observe(config, dataset['probe_actions'][index]); measured += 1
                else:
                    receipt = saved[target_index]['policies'][policy]['rounds'][step]['receipt']
                    if receipt != repair.observe(config, dataset['probe_actions'][index]):
                        raise ValueError('chosen native receipt replay differs')
                history.append(receipt); selected = selection(target, history)
                rounds.append({'step': step, 'predictions': predicted, 'disagreement_scores':
                    {str(k): v for k, v in scores.items()}, 'chosen_index': index, 'receipt': receipt,
                    'reselection': selected})
                if record_round is not None: record_round(target['id'], policy, step, rounds[-1])
                remaining.remove(index)
            record['policies'][policy] = {'rounds': rounds, 'history': history,
                                          'initial': initial, 'reselect': selected}
            if policy == 'fixed': record['historical_reselect'] = selection(target,history,'historical_inventory')
        records.append(record)
    return records, measured


def metrics(result):
    rows = result['rows']; valid = [r for r in rows if r['error'] is None]
    supported = [r for r in valid if not r['expected']['unresolved']]
    return {**{k: result[k] for k in ('correct', 'total', 'unsupported', 'errors')},
        'supported_queries': sum(not r['expected']['unresolved'] for r in rows),
        'supported_correct_resolved': sum(r['correct'] and not r['expected']['unresolved'] for r in valid),
        'supported_resolved': sum(not r['answer']['unresolved'] for r in supported),
        'supported_wrong_resolved': sum(not r['answer']['unresolved'] and not r['correct'] for r in supported),
        'supported_abstentions': sum(r['answer']['unresolved'] for r in supported),
        'abstentions': sum(r['answer']['unresolved'] for r in valid),
        'unsupported_queries': sum(r['expected']['unresolved'] for r in rows),
        'unsupported_abstentions': sum(r['expected']['unresolved'] and r['answer']['unresolved'] for r in valid)}


def audit(protocol, dataset, frozen):
    if len(frozen) != len(dataset['targets']) or not frozen: raise ValueError('complete nonempty frozen inventory required')
    worlds = []
    for target, record in zip(dataset['targets'], frozen):
        if target['id'] != record['id']: raise ValueError('frozen target order differs')
        row = {'id': target['id'], 'arms': {}}
        for policy in POLICIES:
            state = record['policies'][policy]
            pairs = repair.cases(repair.WorldConfig(**target['config']), state['history'], dataset['final_actions'])
            for selector in SELECTORS:
                selected = state[selector]
                result = repair.score(program(target, selected)['source'], pairs)
                row['arms'][policy+'_'+selector] = {'selection': selected['selected_slot'],
                    'metrics': metrics(result), 'result': result}
        for reference in REFERENCES:
            pairs = repair.cases(repair.WorldConfig(**target['config']),record['policies']['fixed']['history'],dataset['final_actions'])
            result = repair.score(program(target,record[reference],'historical_inventory')['source'],pairs)
            row['arms'][reference] = {'selection':record[reference]['selected_slot'],'metrics':metrics(result),'result':result}
        worlds.append(row)
    aggregate = {a: {k: sum(w['arms'][a]['metrics'][k] for w in worlds)
                    for k in worlds[0]['arms'][a]['metrics']} for a in (*ARMS,*REFERENCES)}
    for counts in aggregate.values():
        counts['supported_resolved_coverage'] = counts['supported_resolved']/counts['supported_queries'] if counts['supported_queries'] else None
        counts['supported_correct_coverage_all_queries'] = counts['supported_correct_resolved']/counts['total'] if counts['total'] else None
    return {'schema': VERSION, 'protocol_sha256': digest(protocol), 'frozen_sha256': digest(frozen),
        'worlds': worlds, 'aggregate': aggregate, 'calls': 0, 'new_reported_cost_usd': '0',
        'native_probe_measurements': len(worlds)*len(POLICIES)*protocol['probe_budget'],
        'inventory': [{'id': t['id'], 'attempt_slots': len(t['inventory']), 'distinct_sources':
            len({s['proposal']['source'] for s in t['inventory']})} for t in dataset['targets']]}


def replay_records(protocol, dataset, frozen, raw_responses=None, prompts=None):
    if raw_responses or prompts: raise ValueError('zero-inference construction has no new model responses or prompts')
    expected, _ = construct(protocol, dataset, frozen)
    if digest(expected) != digest(frozen): raise ValueError('prediction, native acquisition or selection replay differs')
    checks = sum(len(p['rows']) for r in frozen for s in r['policies'].values()
                 for step in s['rounds'] for p in step['predictions'])
    return {'exact_construction_replay': True, 'construction_checks': checks,
        'construction_check_unit': 'individual unlabelled candidate query predictions',
        'native_receipts_replayed': len(frozen)*len(POLICIES)*protocol['probe_budget'],
        'protected_evaluation_performed': False, 'calls': 0}


def run(output):
    output = Path(output)
    if (output/'started.json').exists(): raise ValueError('already started; preserve original host experiment')
    protocol, data = repair.verify(output)
    write_json(output/'started.json', {'protocol_sha256': digest(protocol), 'dataset_sha256': digest(data)})
    phase = 'acquisition'
    try:
        frozen, measured = construct(protocol, data, record_round=lambda target, policy, step, row:
            write_json(output/'probes'/f'{target}-{policy}-{step}.json', row))
        repair.verify(output)
        write_json(output/'all-frozen.json', frozen)
        write_json(output/'all-frozen-receipt.json', {'protocol_sha256': digest(protocol),
            'frozen_sha256': digest(frozen), 'construction_complete': True, 'native_probe_measurements': measured})
        phase = 'final_audit'
        result = audit(protocol, data, frozen)
        write_json(output/'results.json', result)
        return result
    except BaseException as error:
        write_json(output/'failure.json', {'phase': phase, 'error': f'{type(error).__name__}: {error}', 'calls': 0})
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__); sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('prepare'); p.add_argument('output', type=Path); p.add_argument('--parent', type=Path, required=True)
    p.add_argument('--seed', type=int, default=20261019); p.add_argument('--archive-parent',type=Path)
    p = sub.add_parser('run'); p.add_argument('output', type=Path)
    args = parser.parse_args()
    result = prepare(args.output,args.parent,archive_parent=args.archive_parent,seed=args.seed) if args.command == 'prepare' else run(args.output)
    print(json.dumps(result, indent=2))


if __name__ == '__main__': main()
