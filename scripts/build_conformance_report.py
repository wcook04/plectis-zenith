#!/usr/bin/env python3
"""Publish native investigation evidence and replay its frozen source offline."""
from __future__ import annotations

import argparse
from decimal import Decimal
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import tempfile
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.build_observation_report import PRIVATE_URL, SECRET, _numeric_usage, digest, sanitize
from research.conformance_study import summarize_results

PANELS = ('screen', 'confirmation')
BASE_FILES = {'protocol.json', 'datasets.json', 'preparation.json', 'frozen.json',
              'frozen-receipt.json', 'runtime-source.zip'}
BILLING_FIELDS = ('call_id', 'node_id', 'requested_model', 'requested_provider_slug',
                  'verified_provider_name', 'actual_provider', 'status', 'cost',
                  'reserved_cost_usd', 'network_elapsed_seconds', 'reasoning_effort',
                  'prompt_sha256', 'response_sha256')
PRIVATE_METADATA = re.compile(r'/Users/|/home/|file://|"(?:api_key|password|authorization|token|access_token|secret)"', re.I)


def read(path):
    return json.loads(Path(path).read_text())


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + '\n')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def amount(value):
    try:
        result = Decimal(str(value))
    except ArithmeticError as exc:
        raise ValueError('Invalid billing amount') from exc
    if not result.is_finite() or result < 0:
        raise ValueError('Invalid billing amount')
    return result


def safe_relative(name):
    path = PurePosixPath(name)
    if not name or path.is_absolute() or '..' in path.parts or '\\' in name or ':' in name:
        raise ValueError('Unsafe artifact member')
    return path


def archive_members(path):
    with ZipFile(path) as archive:
        seen = set()
        for info in archive.infolist():
            safe_relative(info.filename)
            if info.filename in seen or ((info.external_attr >> 16) & 0o170000) == 0o120000:
                raise ValueError('Unsafe archived source member')
            seen.add(info.filename)
            if not info.is_dir():
                text = archive.read(info).decode('utf-8')
                if SECRET.search(text) or PRIVATE_URL.search(text):
                    raise ValueError('Archived source contains private metadata')


def calls_and_files(folder):
    """Bind the allowlist to actual parents, policies and repair calls."""
    folder = Path(folder)
    protocol, data, frozen = (read(folder / name) for name in
                              ('protocol.json', 'datasets.json', 'frozen.json'))
    if frozen['complete'] and frozen['failures']:
        raise ValueError('Complete study has recorded failures')
    if not frozen['complete'] and not frozen['failures']:
        raise ValueError('Incomplete evidence needs terminal failure diagnostics')
    if protocol['source']['path'] != 'runtime-source.zip':
        raise ValueError('Protocol must bind a portable relative source archive')
    evidence = json.dumps(protocol.get('model_evidence', {}))
    if SECRET.search(evidence) or PRIVATE_URL.search(evidence) or PRIVATE_METADATA.search(evidence):
        raise ValueError('Model evidence contains private metadata')
    if (digest(protocol) != read(folder / 'preparation.json')['protocol_sha256'] or
            digest(data) != protocol['dataset_sha256'] or
            frozen['protocol_sha256'] != digest(protocol) or
            digest(frozen) != read(folder / 'frozen-receipt.json')['frozen_sha256'] or
            sha(folder / 'runtime-source.zip') != protocol['source']['sha256']):
        raise ValueError('Frozen evidence custody mismatch')
    task_ids = [t['id'] for t in data['tasks']]
    records = frozen['records']
    if (len(set(task_ids)) != len(task_ids) or len({r['task_id'] for r in records}) != len(records) or
            not {r['task_id'] for r in records} <= set(task_ids) or
            (frozen['complete'] and len(records) != len(task_ids))):
        raise ValueError('Frozen task membership mismatch')
    nodes = []
    for record in records:
        if (not set(record['arms']) <= set(protocol['arms']) or
                (frozen['complete'] and set(record['arms']) != set(protocol['arms']))):
            raise ValueError('Frozen arm membership mismatch')
        if 'parent' not in record:
            if frozen['complete'] or record['arms']:
                raise ValueError('Missing parent for recorded construction')
            continue
        nodes.append(record['parent']['call_id'])
        for arm, item in record['arms'].items():
            if (item['policy'] is None) != (arm == 'fixed'):
                raise ValueError('Frozen policy call mismatch')
            if item['policy'] is not None:
                nodes.append(item['policy']['call_id'])
            nodes.append(item['candidate']['call_id'])
            if item['selected']['call_id'] not in (record['parent']['call_id'], item['candidate']['call_id']):
                raise ValueError('Selected program is not an actual candidate')
    if ((frozen['complete'] and len(nodes) != protocol['max_calls']) or len(set(nodes)) != len(nodes) or
            any(not isinstance(n, str) or not re.fullmatch(r'[A-Za-z0-9_-]+', n) for n in nodes)):
        raise ValueError('Scientific call membership mismatch')
    allowed = {task + '-parent' for task in task_ids}
    for task in task_ids:
        for arm in protocol['arms']:
            allowed.add(task + '-' + arm + '-repair')
            if arm != 'fixed': allowed.add(task + '-' + arm + '-policy')
    if not set(nodes) <= allowed or len(allowed) != protocol['max_calls']:
        raise ValueError('Scientific calls do not match protocol')
    prompts = {n for n in allowed if (folder / 'prompts' / (n + '.json')).is_file()}
    responses = {n for n in allowed if (folder / 'responses' / (n + '.json')).is_file()}
    if not responses <= prompts or not set(nodes) <= responses or (frozen['complete'] and prompts != set(nodes)):
        raise ValueError('Scientific prompt/response membership mismatch')
    files = set(BASE_FILES)
    if frozen['complete'] and not (folder / 'screen.json').is_file():
        raise ValueError('Completed protected screen is required')
    for panel in PANELS:
        if (folder / (panel + '.json')).exists():
            if not frozen['complete']:
                raise ValueError('Incomplete studies cannot publish protected panels')
            files.update(panel + suffix for suffix in ('.json', '-selection.json', '-summary.json'))
    files.update(f'prompts/{node}.json' for node in prompts)
    files.update(f'responses/{node}.json' for node in responses)
    if (folder / 'recovery.json').exists():
        recovery = read(folder / 'recovery.json')
        if recovery['schema'] != 'zenith_conformance_recovery_v1' or frozen['complete']:
            raise ValueError('Invalid terminal recovery provenance')
        record_files = recovery['record_files']
        expected_records = []
        for name, recorded_hash in sorted(record_files.items()):
            safe_relative(name)
            if not re.fullmatch(r'records/[A-Za-z0-9_-]+\.json', name) or sha(folder / name) != recorded_hash:
                raise ValueError('Recovered original record custody mismatch')
            record = read(folder / name)
            if name != 'records/' + record['task_id'] + '.json':
                raise ValueError('Recovered record filename mismatch')
            expected_records.append(record)
        expected_records.sort(key=lambda r:r['task_id'])
        if frozen['records'] != expected_records or digest(frozen) != recovery['recovered_frozen_sha256']:
            raise ValueError('Recovered metadata disagrees with original records')
        files.update(record_files)
        if recovery['copied_started_record']:
            files.add('started.json')
        original = files - {'frozen.json', 'frozen-receipt.json'}
        if set(recovery['copied_source_files']) != original or any(sha(folder / n) != h for n,h in recovery['copied_source_files'].items()):
            raise ValueError('Recovered source file custody mismatch')
        files.add('recovery.json')
    return protocol, data, frozen, sorted(prompts), files


def checked_billing(billing, nodes, *, complete=True):
    entries = billing['entries']
    entries = list(entries.values()) if isinstance(entries, dict) else entries
    paid_nodes = {e['node_id'] for e in entries}
    if (not paid_nodes <= set(nodes) or len(paid_nodes) != len(entries) or
            (complete and paid_nodes != set(nodes))):
        raise ValueError('Billing call membership mismatch')
    identities = [e.get('call_id') for e in entries]
    if len(set(identities)) != len(identities) or any(not isinstance(c, str) or not re.fullmatch(r'[0-9a-f]{64}', c) for c in identities):
        raise ValueError('Billing attempt identity mismatch')
    if any(e['status'] not in ('response_supplied', 'failed', 'attempt_started') for e in entries):
        raise ValueError('Unknown billing attempt status')
    if complete and any(e['status'] != 'response_supplied' or e['cost'] is None for e in entries):
        raise ValueError('Completed evidence requires complete billing receipts')
    if sum((amount(e['cost']) for e in entries if e['cost'] is not None), Decimal(0)) != amount(billing['total_reported_cost_usd']):
        raise ValueError('Reported billing total disagrees with individual calls')
    if sum((amount(e['reserved_cost_usd']) for e in entries), Decimal(0)) != amount(billing['total_reserved_usd']):
        raise ValueError('Reserved billing total disagrees with individual calls')
    return entries


def checked_call_frames(folder, entries):
    folder = Path(folder)
    responses = {p.stem for p in (folder / 'responses').glob('*.json')
                 if p.stem in {e['node_id'] for e in entries}}
    expected = {e['node_id'] for e in entries if e['status'] == 'response_supplied'}
    if responses != expected:
        raise ValueError('Billed response membership mismatch')
    for entry in entries:
        node = entry['node_id']; frame = read(folder / 'prompts' / (node + '.json'))
        sent = json.dumps(frame['prompt'], ensure_ascii=False)
        if entry.get('prompt_sha256') and hashlib.sha256(sent.encode()).hexdigest() != entry['prompt_sha256']:
            raise ValueError('Billed prompt disagrees with scientific prompt')
        response = folder / 'responses' / (node + '.json')
        if response.exists() and entry.get('response_sha256'):
            if hashlib.sha256(read(response)['raw'].encode()).hexdigest() != entry['response_sha256']:
                raise ValueError('Billed response disagrees with original output')


def checked_investigations(data, frozen):
    tasks = {t['id']: t for t in data['tasks']}
    for record in frozen['records']:
        for arm, item in record['arms'].items():
            investigation = item['investigation']; rows = investigation['receipts']
            seen = {digest(e['input']) for e in tasks[record['task_id']]['examples']}
            attempted = 0
            for index, row in enumerate(rows, start=1):
                if row['slot'] != index:
                    raise ValueError('Investigation slot custody mismatch')
                if 'query' in row:
                    identity = digest(row['query'])
                    attempted += identity not in seen
                    seen.add(identity)
                if 'expected' in row:
                    wrong = row['parent_error'] is not None or digest(row['parent_answer']) != digest(row['expected'])
                    if type(row['verified_counterexample']) is not bool or row['verified_counterexample'] != wrong:
                        raise ValueError('Counterexample claim disagrees with observation')
            measured = [r for r in rows if 'expected' in r]
            witness = next((r for r in measured if r['verified_counterexample']), None)
            derived = {'native_probes': len(measured), 'query_attempts': attempted,
                       'query_units': sum(r['query_units'] for r in measured),
                       'policy_executions': 0 if arm == 'fixed' else len(rows),
                       'slots_used': len(rows), 'detected': witness is not None,
                       'semantic_defect': witness is not None and witness['parent_error'] is None,
                       'technical_defect': witness is not None and witness['parent_error'] is not None,
                       'witness_sha256': digest(witness) if witness else None}
            if any(investigation[k] != v for k, v in derived.items()):
                raise ValueError('Investigation totals disagree with receipts')


def checked_summaries(folder, data, frozen, billing):
    checked_investigations(data, frozen)
    results = {}
    for panel in PANELS:
        if not (Path(folder) / (panel + '.json')).exists():
            continue
        raw = read(Path(folder) / (panel + '.json'))
        if raw['partition'] != panel or raw['frozen_sha256'] != digest(frozen):
            raise ValueError('Protected panel binding mismatch')
        if set(raw['tasks']) != {t['id'] for t in data['tasks']}:
            raise ValueError('Protected task membership mismatch')
        tasks = {t['id']:t for t in data['tasks']}
        records = {r['task_id']:r for r in frozen['records']}
        for task_id, task in raw['tasks'].items():
            if task['source_id'] != tasks[task_id]['source_id'] or set(task['arms']) != set(records[task_id]['arms']):
                raise ValueError('Protected source/arm membership mismatch')
            scores = [task['parent']] + [v[name] for v in task['arms'].values() for name in ('selected','attempt')]
            for score in scores:
                rows = score['rows']; examples = tasks[task_id][panel]
                if len(rows) != len(examples):
                    raise ValueError('Protected row membership mismatch')
                for row, example in zip(rows, examples, strict=True):
                    correct = row['error'] is None and digest(row['answer']) == digest(example['expected'])
                    if (row['input'] != example['input'] or row['expected'] != example['expected'] or
                            type(row['correct']) is not bool or row['correct'] != correct):
                        raise ValueError('Protected correctness claim disagrees with its observation')
                derived = {'correct': sum(r['correct'] for r in rows), 'total': len(rows),
                           'errors': sum(r['error'] is not None for r in rows)}
                if derived != {k:score[k] for k in derived}:
                    raise ValueError('Protected score totals disagree with rows')
        derived = summarize_results(raw, frozen, billing)
        if read(Path(folder) / (panel + '-summary.json')) != derived:
            raise ValueError('Published summary disagrees with protected rows and receipts')
        results[panel] = derived
    return results


def export(study, output):
    study, output = Path(study).resolve(), Path(output).resolve()
    if output.exists():
        raise ValueError('Evidence exports are immutable; choose a new output')
    protocol, data, frozen, nodes, files = calls_and_files(study)
    budget = read(study / 'budget/budget.json')
    entries = checked_billing(budget, nodes, complete=frozen['complete'])
    checked_call_frames(study, entries)
    response_nodes = {Path(n).stem for n in files if n.startswith('responses/')}
    if response_nodes != {e['node_id'] for e in entries if e['status'] == 'response_supplied'}:
        raise ValueError('Scientific response lacks an actual billed attempt')
    checked_summaries(study, data, frozen, budget)
    archive_members(study / 'runtime-source.zip')
    for name in files:
        path = study / name
        if not path.is_file() or path.is_symlink():
            raise ValueError('Scientific payload must be an existing regular file')
        if name.endswith('.json'):
            text = path.read_text()
            if SECRET.search(text) or PRIVATE_URL.search(text):
                raise ValueError('Scientific payload contains private metadata')
    billing = {'schema': 'zenith_conformance_billing_v1',
               **{k:budget[k] for k in ('total_reported_cost_usd', 'total_reserved_usd', 'halted')},
               'entries': [{**{k:e.get(k) for k in BILLING_FIELDS},
                            'usage': _numeric_usage(e.get('provider_receipt', {}).get('usage') or
                                                    e.get('provider_response', {}).get('usage') or e.get('usage')),
                            'error':sanitize(e.get('error'), error=True)}
                           for e in entries]}
    if SECRET.search(json.dumps(billing)) or PRIVATE_URL.search(json.dumps(billing)):
        raise ValueError('Allowlisted billing contains private metadata')
    output.mkdir(parents=True)
    for name in sorted(files):
        target = output / name; target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(study / name, target)
    write(output / 'billing.json', billing)
    manifest = {'schema': 'zenith_conformance_export_v1',
                'boundary': 'Exact scientific records and original outputs; explicit numeric billing projection. No credentials, private provider transports or account records.',
                'files': {str(p.relative_to(output)):sha(p) for p in sorted(output.rglob('*')) if p.is_file()}}
    write(output / 'manifest.json', manifest)
    return {'output':str(output), 'files':len(manifest['files']), 'calls':len(entries),
            'complete':frozen['complete'], 'prompt_attempts':len(nodes),
            'responses':sum(name.startswith('responses/') for name in files),
            'known_cost_attempts':sum(e['cost'] is not None for e in entries),
            'unknown_cost_attempts':sum(e['cost'] is None for e in entries),
            'unknown_cost_reservations_usd':str(sum((amount(e['reserved_cost_usd']) for e in entries if e['cost'] is None), Decimal(0))),
            'reported_cost_usd':billing['total_reported_cost_usd']}


def recover(study, output, *, reason='Final evidence file missing after interrupted construction.'):
    """Copy durable records to a new partial export; never resume inference.

    Only collection metadata is rebuilt. Raw responses, saved investigation
    receipts and selected programs come exclusively from original files.
    Missing programs, measurements and protected outcomes stay absent.
    """
    study, output = Path(study).resolve(), Path(output).resolve()
    if output.exists():
        raise ValueError('Evidence exports are immutable; choose a new output')
    if (study / 'frozen.json').exists() or (study / 'frozen-receipt.json').exists():
        raise ValueError('Original final metadata exists; use ordinary export or inspect the damaged artifact')
    if any((study / (panel + '.json')).exists() for panel in PANELS):
        raise ValueError('Protected results already exist; do not discard them through partial recovery')
    if SECRET.search(reason) or PRIVATE_URL.search(reason) or PRIVATE_METADATA.search(reason):
        raise ValueError('Recovery reason contains private metadata')
    protocol, data = read(study / 'protocol.json'), read(study / 'datasets.json')
    if (digest(protocol) != read(study / 'preparation.json')['protocol_sha256'] or
            digest(data) != protocol['dataset_sha256'] or
            sha(study / 'runtime-source.zip') != protocol['source']['sha256']):
        raise ValueError('Original preparation custody mismatch')
    allowed = {t['id'] + '-parent' for t in data['tasks']}
    for task in data['tasks']:
        for arm in protocol['arms']:
            allowed.add(task['id'] + '-' + arm + '-repair')
            if arm != 'fixed': allowed.add(task['id'] + '-' + arm + '-policy')
    files = BASE_FILES - {'frozen.json', 'frozen-receipt.json'}
    files = set(files)
    for directory in ('prompts', 'responses'):
        files.update(f'{directory}/{node}.json' for node in allowed if (study / directory / (node + '.json')).is_file())
    task_ids = {t['id'] for t in data['tasks']}; records = []; record_files = {}
    for path in sorted((study / 'records').glob('*.json')):
        record = read(path)
        if record['task_id'] not in task_ids or path.name != record['task_id'] + '.json':
            raise ValueError('Original record membership mismatch')
        records.append(record); name = str(path.relative_to(study)); record_files[name] = sha(path); files.add(name)
    records.sort(key=lambda r:r['task_id'])
    by_task = {r['task_id']:r for r in records}; failures = []
    for task in data['tasks']:
        record = by_task.get(task['id'])
        if record is None or set(record['arms']) != set(protocol['arms']) or 'failure' in record:
            failures.append({'task_id':task['id'],
                             'error': record.get('failure') if record and record.get('failure') else 'Recovery: no durable complete construction for this task.',
                             'provenance':'Original task failure when present; otherwise metadata derived from missing durable construction.'})
    if not failures:
        failures.append({'task_id':None, 'error':'Recovery: original final evidence file missing; study retained as partial.'})
    copied_started = (study / 'started.json').is_file()
    if copied_started: files.add('started.json')
    before = {n:sha(study / n) for n in sorted(files)}
    budget_hash = sha(study / 'budget/budget.json')
    frozen = {'complete':False, 'failures':failures, 'records':records,
              'protocol_sha256':digest(protocol),
              'recovery':{'receipt':'recovery.json', 'boundary':'Post-failure collection metadata from exact original record files; no inferred model outputs or observations.'}}
    receipt = {'schema':'zenith_conformance_recovery_v1',
               'created_at':datetime.now(timezone.utc).isoformat(),
               'source_label':study.name, 'declared_reason':reason,
               'observed_missing':['frozen.json','frozen-receipt.json'],
               'record_files':record_files, 'copied_source_files':before,
               'original_budget_sha256':budget_hash, 'copied_started_record':copied_started,
               'recovered_frozen_sha256':digest(frozen),
               'boundary':'New immutable partial export. Collection metadata is derived; original selected programs, raw responses and saved probe receipts are unchanged. Missing calls, observations and protected panels are not inferred.'}
    with tempfile.TemporaryDirectory(prefix='zenith-conformance-recovery-') as directory:
        stage = Path(directory)
        for name in sorted(files):
            source = study / name
            if source.is_symlink(): raise ValueError('Original payload must be a regular file')
            target = stage / name; target.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(source, target)
        (stage / 'budget').mkdir(); shutil.copyfile(study / 'budget/budget.json', stage / 'budget/budget.json')
        write(stage / 'frozen.json', frozen)
        write(stage / 'frozen-receipt.json', {'frozen_sha256':digest(frozen), 'recovered':True})
        write(stage / 'recovery.json', receipt)
        result = export(stage, output)
    if before != {n:sha(study / n) for n in sorted(files)} or budget_hash != sha(study / 'budget/budget.json'):
        raise ValueError('Original study changed during recovery; do not treat this export as stable')
    return {**result, 'recovered_metadata':True, 'source_files_unchanged':True}


def verify_manifest(output):
    output = Path(output).resolve(); manifest = read(output / 'manifest.json')
    if manifest['schema'] != 'zenith_conformance_export_v1':
        raise ValueError('Unknown export manifest')
    for name in manifest['files']:
        safe_relative(name)
    if any(p.is_symlink() for p in output.rglob('*')):
        raise ValueError('Published file custody mismatch: symlink')
    actual = {str(p.relative_to(output)) for p in output.rglob('*') if p.is_file()} - {'manifest.json'}
    if actual != set(manifest['files']) or any(sha(output / n) != h for n,h in manifest['files'].items()):
        raise ValueError('Published file custody mismatch')
    protocol, data, frozen, nodes, files = calls_and_files(output)
    if set(manifest['files']) != files | {'billing.json'}:
        raise ValueError('Published scientific allowlist mismatch')
    billing = read(output / 'billing.json'); entries = checked_billing(billing, nodes, complete=frozen['complete'])
    checked_call_frames(output, entries)
    if {Path(n).stem for n in files if n.startswith('responses/')} != {e['node_id'] for e in entries if e['status'] == 'response_supplied'}:
        raise ValueError('Scientific response lacks an actual billed attempt')
    panels = checked_summaries(output, data, frozen, billing)
    archive_members(output / 'runtime-source.zip')
    return {'protocol':protocol, 'panels':panels, 'calls':len(entries), 'billing':billing,
            'complete':frozen['complete'], 'prompt_attempts':len(nodes)}


PARTIAL_REPLAY = '''
import hashlib,json,socket,sys
from pathlib import Path
def denied(*args,**kwargs):
    raise RuntimeError("Network disabled for offline partial replay")
socket.socket.connect=denied
socket.socket.connect_ex=denied
socket.create_connection=denied
socket.getaddrinfo=denied
sys.path.insert(0,sys.argv[1])
from research import conformance_study as s
out=Path(sys.argv[2])
protocol,data=s.verify(out)
frozen=s.read(out/"frozen.json")
assert not frozen["complete"] and frozen["failures"]
assert s.digest(frozen)==s.read(out/"frozen-receipt.json")["frozen_sha256"]
tasks={t["id"]:t for t in data["tasks"]}
records={r["task_id"]:r for r in frozen["records"]}
labels={}
for task_id in tasks:
    labels[task_id+"-parent"]=(task_id,"parent",None)
    for arm in protocol["arms"]:
        labels[task_id+"-"+arm+"-repair"]=(task_id,"repair",arm)
        if arm!="fixed": labels[task_id+"-"+arm+"-policy"]=(task_id,"policy",arm)
frames={p.stem:s.read(p) for p in (out/"prompts").glob("*.json")}
responses={p.stem:s.read(p) for p in (out/"responses").glob("*.json")}
assert set(responses)<=set(frames)<=set(labels)
for node,response in responses.items():
    assert response["prompt_sha256"]==s.digest(frames[node])
parsed={node:s.parse_model_response(response["raw"]) for node,response in responses.items()}
def parent_for(task_id):
    parent=records.get(task_id,{}).get("parent")
    if parent is not None: return parent
    node=task_id+"-parent"
    assert node in parsed
    parent={**parsed[node],"call_id":node}
    parent["development"]=s.score_program(parent["source"],tasks[task_id]["examples"],parent["error"])
    return parent
for node,frame in frames.items():
    task_id,kind,arm=labels[node]
    task=tasks[task_id]
    if kind=="parent": prompt=s.parent_prompt(task)
    elif kind=="policy": prompt=s.policy_prompt(task,parent_for(task_id),arm)
    else:
        parent=parent_for(task_id)
        policy_node=task_id+"-"+arm+"-policy"
        policy=None if arm=="fixed" else parsed[policy_node]
        investigation=s.investigate(task,parent["source"],policy["source"] if policy else None,
                                    fixed=arm=="fixed",cap=protocol["probe_cap"])
        prompt=s.repair_prompt(task,parent,investigation)
    assert frame=={"prompt":prompt,"system":s.POLICY_LANGUAGE if kind=="policy" else s.LANGUAGE,
                   "response_schema":s.SCHEMA}
recorded=set();investigations=0
def check_trial(trial):
    node=trial["call_id"];recorded.add(node)
    assert node in responses
    assert trial["prompt_sha256"]==s.digest(frames[node])
    assert trial["raw_sha256"]==hashlib.sha256(responses[node]["raw"].encode()).hexdigest()
    assert all(trial[k]==parsed[node][k] for k in (*s.SCHEMA["required"],"error"))
for record in frozen["records"]:
    if "parent" not in record:
        assert not record["arms"]
        continue
    task=tasks[record["task_id"]];parent=record["parent"]
    check_trial(parent)
    assert parent["development"]==s.score_program(parent["source"],task["examples"],parent["error"])
    for arm,item in record["arms"].items():
        policy=item["policy"]
        if policy is not None: check_trial(policy)
        investigation=s.investigate(task,parent["source"],policy["source"] if policy else None,
                                    fixed=arm=="fixed",cap=protocol["probe_cap"])
        assert investigation==item["investigation"]
        check_trial(item["candidate"])
        assert s.selected_candidate(parent,item["candidate"],s.repair_examples(task,investigation))==item["selected"]
        investigations+=1
assert not any((out/(p+".json")).exists() for p in ("screen","confirmation"))
billing=s.read(out/"billing.json")
from decimal import Decimal
unknown=[e for e in billing["entries"] if e["cost"] is None]
print(json.dumps({"ok":True,"complete":False,"prompt_attempts":len(frames),
    "budget_attempts":len(billing["entries"]),"known_cost_attempts":len(billing["entries"])-len(unknown),
    "unknown_cost_attempts":len(unknown),
    "unknown_cost_reservations_usd":str(sum((Decimal(e["reserved_cost_usd"]) for e in unknown),Decimal(0))),
    "response_files_replayed":len(responses),
    "recorded_calls_replayed":len(recorded),"orphan_responses":len(set(responses)-recorded),
    "recorded_native_investigations":investigations,"protected_partitions":[],
    "recovered_metadata":(out/"recovery.json").exists(),
    "scope":"Terminal partial evidence: frozen parsing, prompts, original responses and recorded investigations replayed; missing calls/outcomes not reconstructed; no protected scoring."}))
'''


def replay(output):
    output = Path(output).resolve(); checked = verify_manifest(output)
    with tempfile.TemporaryDirectory(prefix='zenith-conformance-replay-') as directory:
        runtime = Path(directory) / 'runtime'; runtime.mkdir()
        with ZipFile(output / 'runtime-source.zip') as archive:
            archive.extractall(runtime)
        script = (('import sys,json;sys.path.insert(0,sys.argv[1]);'
                   'from research.conformance_study import replay;print(json.dumps(replay(sys.argv[2])))')
                  if checked['complete'] else PARTIAL_REPLAY)
        result = subprocess.run([sys.executable, '-I', '-B', '-c', script, str(runtime), str(output)],
                                cwd=runtime, env={}, capture_output=True, text=True, timeout=300)
        if result.returncode:
            raise RuntimeError('Archived replay failed: ' + result.stderr[-3000:])
        return json.loads(result.stdout)


def campaign(root=ROOT):
    """Keep distinct studies/panels separate; sum only their new call costs."""
    root = Path(root); rows = []; total = Decimal(0); calls = 0
    for manifest in sorted((root / 'examples/conformance').glob('*/manifest.json')):
        folder = manifest.parent; checked = verify_manifest(folder)
        protocol = checked['protocol']; billing = checked['billing']
        calls += checked['calls']; total += amount(billing['total_reported_cost_usd'])
        rows.append({'id':folder.name, 'evidence':str(folder.relative_to(root)),
                     'model':protocol['model'], 'reasoning_effort':protocol['reasoning_effort'],
                     'dataset_sha256':protocol['dataset_sha256'], 'source_sha256':protocol['source']['sha256'],
                     'complete':checked['complete'], 'calls':checked['calls'],
                     'prompt_attempts':checked['prompt_attempts'],
                     'reported_cost_usd':billing['total_reported_cost_usd'],
                     'panels':checked['panels']})
    return {'schema':'zenith_conformance_campaign_v1', 'calls':calls,
            'reported_cost_usd':str(total), 'studies':rows,
            'boundary':'Distinct new calls are summed; source lineages, repeated model parents and shared panels are not independent replications or pooled accuracies.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    e = sub.add_parser('export'); e.add_argument('study', type=Path); e.add_argument('output', type=Path)
    recovery = sub.add_parser('recover'); recovery.add_argument('study', type=Path); recovery.add_argument('output', type=Path)
    recovery.add_argument('--reason', default='Final evidence file missing after interrupted construction.')
    r = sub.add_parser('replay'); r.add_argument('output', type=Path)
    c = sub.add_parser('campaign'); c.add_argument('--root', type=Path, default=ROOT); c.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.command == 'campaign':
        result = campaign(args.root); write(args.output, result)
    elif args.command == 'recover':
        result = recover(args.study, args.output, reason=args.reason)
    else:
        result = export(args.study, args.output) if args.command == 'export' else replay(args.output)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
