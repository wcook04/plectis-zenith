#!/usr/bin/env python3
"""Export the client-investigation pilot and replay its archived runtime offline.

Scientific files are copied byte-for-byte. Only the shared provider ledger is
projected: credentials, transport packets, local paths and request metadata do
not enter the public bundle. A terminal partial run remains terminal partial.
"""
from __future__ import annotations

import argparse
from collections import Counter
from decimal import Decimal, InvalidOperation
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

VERSION = 'zenith_client_investigation_study_v1'
PROTOCOL_DOCUMENTS = {
    VERSION: 'docs/client-investigation-protocol-20261014.md',
    'zenith_client_investigation_study_v2': 'docs/client-investigation-protocol-v2-20261015.md',
}
EXPORT_VERSION = 'zenith_client_investigation_export_v1'
BILLING_VERSION = 'zenith_client_investigation_billing_v1'
ARMS = ('procedure', 'ordinary_reuse', 'same_history', 'cold', 'fixed')
BASE = {'protocol.json', 'prepared-tasks.json', 'runtime-source.zip',
        'protocol-source.md', 'started.json', 'state.json', 'frozen.json'}
BILLING_FIELDS = ('call_id', 'node_id', 'requested_model', 'requested_provider_slug',
                  'verified_provider_name', 'actual_provider', 'status', 'cost',
                  'reserved_cost_usd', 'network_elapsed_seconds', 'reasoning_effort',
                  'prompt_sha256', 'response_sha256')
PRIVATE_METADATA = re.compile(r'/Users/|/home/|file://|"(?:api_key|password|authorization|token|access_token|secret)"', re.I)
SHA256 = re.compile(r'[0-9a-f]{64}\Z')


def read(path):
    return json.loads(Path(path).read_text())


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, ensure_ascii=False,
                                     allow_nan=False) + '\n')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def amount(value):
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError('Invalid billing amount') from exc
    if not number.is_finite() or number < 0:
        raise ValueError('Invalid billing amount')
    return number


def safe_relative(name):
    path = PurePosixPath(name)
    if not name or path.is_absolute() or '..' in path.parts or '\\' in name or ':' in name:
        raise ValueError('Unsafe export member')
    return path


def check_archive(path, protocol):
    if sha(path) != protocol['source_archive']['sha256']:
        raise ValueError('Frozen source archive hash mismatch')
    with ZipFile(path) as archive:
        members = set()
        for info in archive.infolist():
            name = info.filename
            safe_relative(name)
            if name in members or ((info.external_attr >> 16) & 0o170000) == 0o120000:
                raise ValueError('Unsafe archived source member')
            members.add(name)
            if info.is_dir():
                continue
            data = archive.read(info)
            text = data.decode('utf-8')
            if SECRET.search(text) or PRIVATE_URL.search(text):
                raise ValueError('Archived source contains private metadata')
        for name, expected in protocol['source_hashes'].items():
            safe_relative(name)
            if name not in members or hashlib.sha256(archive.read(name)).hexdigest() != expected:
                raise ValueError('Frozen implementation member mismatch')
        if 'research/client_investigation_study.py' not in members:
            raise ValueError('Archived client runtime missing')


def _node(envelope):
    prompt = envelope['prompt']
    task = prompt.get('public_task', {}).get('id', 'all')
    values = (envelope['phase'], envelope.get('kind', envelope.get('arm', '')),
              task, envelope.get('turn', 1))
    node = '-'.join(str(value) for value in values)
    if not re.fullmatch(r'[A-Za-z0-9_-]+', node):
        raise ValueError('Unsafe call node')
    return node


def _run_calls(run, task_id, arm):
    if run.get('task_id') != task_id or run.get('arm') != arm:
        raise ValueError('Recorded run task/arm mismatch')
    if run.get('model_call_attempts') != len(run.get('turns', [])) or (
            arm not in ('same_history', 'cold') and run['turns']):
        raise ValueError('Recorded model call count mismatch')
    if run.get('policy_executions', 0) < 0 or run.get('query_slots', 0) < run.get('valid_probes', 0):
        raise ValueError('Recorded work counter mismatch')
    if run.get('native_cost', {}).get('reference_calls') != run.get('valid_probes'):
        raise ValueError('Recorded native probe counter mismatch')
    for turn in run['turns']:
        envelope = turn['envelope']
        if envelope.get('phase') != 'target_query' or envelope.get('arm') != arm or (
                envelope.get('prompt', {}).get('public_task', {}).get('id') != task_id):
            raise ValueError('Recorded direct envelope membership mismatch')
        yield turn


def _recorded_calls(protocol, frozen):
    """Return all attempted call records, including a terminal active call."""
    calls = {}

    def add(row):
        envelope = row.get('envelope')
        if not isinstance(envelope, dict) or row.get('envelope_sha256') != digest(envelope):
            raise ValueError('Recorded envelope hash mismatch')
        node = _node(envelope)
        if node in calls:
            raise ValueError('Duplicate recorded call node')
        raw = row.get('raw')
        if raw is not None and (type(raw) is not str or row.get('raw_sha256') != hashlib.sha256(raw.encode()).hexdigest()):
            raise ValueError('Recorded raw response hash mismatch')
        calls[node] = row

    development = frozen['development_runs']
    if len(development) != len(frozen['development']) or len(development) > len(protocol['development_tasks']):
        raise ValueError('Development evidence count mismatch')
    for i, run in enumerate(development):
        task_id = protocol['development_tasks'][i]
        for row in _run_calls(run, task_id, 'same_history'):
            add(row)
        projection = {k: run[k] for k in ('public_task', 'receipts', 'query_slots',
                                         'model_call_attempts', 'native_cost')}
        if frozen['development'][i] != projection:
            raise ValueError('Development history differs from original run')
    if set(frozen['artifacts']) - {'procedure', 'ordinary_reuse'}:
        raise ValueError('Unknown retained artifact')
    for kind, artifact in frozen['artifacts'].items():
        if artifact.get('kind') != kind or artifact.get('envelope', {}).get('kind') != kind:
            raise ValueError('Artifact kind mismatch')
        add(artifact)
    for task_id, arms in frozen['targets'].items():
        if task_id not in protocol['target_tasks'] or set(arms) - set(ARMS):
            raise ValueError('Unknown target or arm')
        for arm, run in arms.items():
            if run.get('not_run') == 'invalid frozen artifact':
                if arm not in ('procedure', 'ordinary_reuse') or frozen['artifacts'][arm]['error'] is None:
                    raise ValueError('Invalid skipped artifact arm')
                continue
            for row in _run_calls(run, task_id, arm):
                add(row)
    active = frozen.get('active', {})
    if active:
        if frozen['complete'] or len(active) != 1:
            raise ValueError('Invalid terminal active state')
        phase, payload = next(iter(active.items()))
        if phase == 'development':
            if len(payload) != 1:
                raise ValueError('Invalid active development')
            task_id, run = next(iter(payload.items()))
            if task_id != protocol['development_tasks'][len(development)]:
                raise ValueError('Active development order mismatch')
            for row in _run_calls(run, task_id, 'same_history'):
                add(row)
        elif phase == 'artifact':
            if len(payload) != 1:
                raise ValueError('Invalid active artifact')
            kind, artifact = next(iter(payload.items()))
            if kind not in ('procedure', 'ordinary_reuse') or artifact.get('kind') != kind:
                raise ValueError('Active artifact kind mismatch')
            add(artifact)
        elif phase == 'target':
            if len(payload) != 1:
                raise ValueError('Invalid active target')
            task_id, by_arm = next(iter(payload.items()))
            if task_id not in protocol['target_tasks'] or len(by_arm) != 1:
                raise ValueError('Active target membership mismatch')
            arm, run = next(iter(by_arm.items()))
            for row in _run_calls(run, task_id, arm):
                add(row)
        else:
            raise ValueError('Unknown active study phase')
    return calls


def _files_and_calls(folder):
    folder = Path(folder)
    protocol, prepared, frozen = (read(folder / name) for name in
                                  ('protocol.json', 'prepared-tasks.json', 'frozen.json'))
    if protocol.get('schema') not in PROTOCOL_DOCUMENTS or frozen.get('schema') != protocol['schema']:
        raise ValueError('Unknown client study schema')
    if protocol.get('protocol_doc', PROTOCOL_DOCUMENTS[protocol['schema']]) != PROTOCOL_DOCUMENTS[protocol['schema']]:
        raise ValueError('Unexpected client protocol source path')
    if protocol.get('arms') != list(ARMS) or protocol.get('max_calls') != 92:
        raise ValueError('Client study protocol differs from declared arms/call ceiling')
    if protocol.get('prepared_tasks_sha256') != digest(prepared) or (
            set(prepared) != set(protocol['development_tasks'] + protocol['target_tasks'])):
        raise ValueError('Frozen prepared task pack mismatch')
    if frozen.get('protocol_sha256') != digest(protocol) or (
            read(folder / 'started.json').get('protocol_sha256') != digest(protocol)):
        raise ValueError('Started/frozen protocol custody mismatch')
    if read(folder / 'state.json') != frozen:
        raise ValueError('Durable state differs from terminal frozen state')
    if type(frozen.get('complete')) is not bool or frozen['complete'] == bool(frozen.get('failure')):
        raise ValueError('Complete/partial study status mismatch')
    if frozen['complete'] and (frozen.get('terminal_error') is not None or frozen.get('active')):
        raise ValueError('Completed study retains terminal failure')
    if not frozen['complete'] and not isinstance(frozen.get('terminal_error'), dict):
        raise ValueError('Partial study lacks terminal failure')
    artifact_freeze = frozen.get('artifact_freeze_sha256')
    scientific_artifacts = {kind: {key: row.get(key) for key in
                            ('source', 'scope', 'error', 'raw_sha256', 'envelope_sha256')}
                            for kind, row in frozen['artifacts'].items()}
    if artifact_freeze is not None and artifact_freeze != digest(scientific_artifacts):
        raise ValueError('Frozen artifacts changed after target start')
    if frozen['targets'] and artifact_freeze is None:
        raise ValueError('Target work preceded artifact freeze')
    calls = _recorded_calls(protocol, frozen)
    prompt_nodes = {p.stem for p in (folder / 'prompts').glob('*.json')}
    response_nodes = {p.stem for p in (folder / 'responses').glob('*.json')}
    if prompt_nodes != set(calls) or response_nodes != {n for n,r in calls.items() if r.get('raw') is not None}:
        raise ValueError('Prompt/raw response membership mismatch')
    for node, row in calls.items():
        frame = read(folder / 'prompts' / (node + '.json'))
        if frame != row['envelope']:
            raise ValueError('Sent prompt differs from recorded envelope')
        if row.get('raw') is not None and read(folder / 'responses' / (node + '.json')) != {
                'raw': row['raw'], 'envelope_sha256': digest(frame)}:
            raise ValueError('Saved raw response differs from recorded delivery')
    panel = folder / 'protected-panel.json'
    if panel.exists():
        if not frozen['complete'] or read(panel).get('frozen_sha256') != digest(frozen):
            raise ValueError('Protected panel opened before complete freeze or changed')
    check_archive(folder / 'runtime-source.zip', protocol)
    files = set(BASE)
    if panel.exists():
        files.add('protected-panel.json')
    files.update('prompts/' + node + '.json' for node in prompt_nodes)
    files.update('responses/' + node + '.json' for node in response_nodes)
    source = folder / 'protocol-source.md'
    if not source.is_file() or sha(source) != protocol['protocol_doc_sha256']:
        raise ValueError('Frozen human protocol source missing or changed')
    return protocol, prepared, frozen, calls, files


def _billing(ledger, calls, *, complete):
    if ledger.get('schema') != 'zenith_shared_budget_v1':
        raise ValueError('Unknown shared budget schema')
    raw_entries = ledger.get('entries')
    if not isinstance(raw_entries, dict):
        raise ValueError('Malformed metered ledger')
    entries = list(raw_entries.values())
    nodes = [e.get('node_id') for e in entries]
    missing = set(calls) - set(nodes)
    if len(set(nodes)) != len(entries) or not set(nodes) <= set(calls) or (
            complete and missing) or len(missing) > 1 or any(
                calls[node].get('raw') is not None or not str(calls[node].get('error')).startswith('adapter_failure:')
                for node in missing):
        raise ValueError('Metered attempt membership differs from scientific calls')
    if len(entries) > 92 or any(e.get('call_id') != key or not isinstance(key, str) or not SHA256.fullmatch(key)
                              for key,e in raw_entries.items()):
        raise ValueError('Metered call identity mismatch')
    if any(e.get('status') not in ('response_supplied', 'failed', 'attempt_started') for e in entries):
        raise ValueError('Unknown metered attempt status')
    if complete and any(e['status'] != 'response_supplied' or e.get('cost') is None for e in entries):
        raise ValueError('Completed study has unresolved metered call')
    if amount(ledger.get('total_reported_cost_usd')) != sum((amount(e['cost']) for e in entries
                                                               if e.get('cost') is not None), Decimal(0)) or (
            amount(ledger.get('total_reserved_usd')) != sum((amount(e.get('reserved_cost_usd')) for e in entries), Decimal(0))):
        raise ValueError('Metered cost totals disagree with attempts')
    for e in entries:
        node = e['node_id']; frame = calls[node]['envelope']
        sent = json.dumps(frame['prompt'], ensure_ascii=False)
        if e.get('prompt_sha256') and e['prompt_sha256'] != hashlib.sha256(sent.encode()).hexdigest():
            raise ValueError('Billed request differs from saved prompt')
        raw = calls[node].get('raw')
        if (e['status'] == 'response_supplied') != (raw is not None):
            raise ValueError('Billed response status differs from raw delivery')
        if raw is not None and e.get('response_sha256') != hashlib.sha256(raw.encode()).hexdigest():
            raise ValueError('Billed response hash differs from raw delivery')
    return {'schema': BILLING_VERSION,
            'total_reported_cost_usd': ledger['total_reported_cost_usd'],
            'total_reserved_usd': ledger['total_reserved_usd'],
            'halted': ledger['halted'],
            'entries': [{**{k:e.get(k) for k in BILLING_FIELDS},
                         'actual_model':e.get('provider_receipt', {}).get('model') or
                                        e.get('provider_response', {}).get('model'),
                         'finish_reasons':[c.get('finish_reason') for c in e.get('provider_response', {}).get('choices', [])
                                           if isinstance(c, dict)],
                         'usage':_numeric_usage(e.get('provider_receipt', {}).get('usage') or
                                                e.get('provider_response', {}).get('usage') or e.get('usage')),
                         'error':sanitize(e.get('error'), error=True)} for e in entries]}


def _check_public_payload(path):
    if not path.is_file() or path.is_symlink():
        raise ValueError('Scientific payload must be an existing regular file')
    if path.suffix in ('.json', '.md'):
        text = path.read_text()
        if SECRET.search(text) or PRIVATE_URL.search(text) or PRIVATE_METADATA.search(text):
            raise ValueError('Scientific payload contains private metadata')


NATIVE_FIELDS = ('reference_calls', 'client_calls', 'reference_sql', 'client_sql')


def _native_total(costs):
    costs = list(costs)
    return {field: sum(cost.get(field, 0) for cost in costs) for field in NATIVE_FIELDS}


def _run_summary(run):
    if 'not_run' in run:
        return {'not_run': run['not_run']}
    query_errors = [row['query_error'] for row in run['receipts'] if row.get('query_error')]
    duplicate = sum('duplicate of public example or earlier query' in error for error in query_errors)
    return {**{field: run[field] for field in (
        'detected', 'query_slots', 'valid_probes', 'model_call_attempts',
        'policy_executions', 'policy_elapsed_seconds', 'native_elapsed_seconds',
        'native_cost', 'halted')},
        'invalid_queries': len(query_errors) - duplicate,
        'duplicate_queries': duplicate,
        'delivery_errors': sum(bool(turn.get('error')) for turn in run['turns']),
        'query_errors': query_errors}


def _aggregate_runs(runs):
    rows = [_run_summary(run) for run in runs if 'not_run' not in run]
    fields = ('query_slots', 'valid_probes', 'model_call_attempts', 'policy_executions',
              'policy_elapsed_seconds', 'native_elapsed_seconds', 'invalid_queries',
              'duplicate_queries', 'delivery_errors')
    return {'runs': len(rows), **{field: sum(row[field] for row in rows) for field in fields},
            'native_cost': _native_total(row['native_cost'] for row in rows),
            'halted_counts': dict(sorted(Counter(row['halted'] for row in rows if row['halted']).items()))}


def _provider_total(entries):
    entries = list(entries)
    unknown = [entry for entry in entries if entry['cost'] is None]
    return {'attempts': len(entries), 'known_cost_attempts': len(entries) - len(unknown),
            'unknown_cost_attempts': len(unknown),
            'reported_model_cost_usd': str(sum((amount(entry['cost']) for entry in entries
                                                if entry['cost'] is not None), Decimal(0))),
            'unknown_cost_reservations_usd': str(sum((amount(entry['reserved_cost_usd']) for entry in unknown), Decimal(0))),
            'network_elapsed_seconds_observed': sum(entry.get('network_elapsed_seconds') or 0 for entry in entries),
            'billed_tokens': {field: sum((entry.get('usage') or {}).get(field, 0) for entry in entries)
                             for field in ('prompt_tokens', 'completion_tokens', 'total_tokens')},
            'reasoning_tokens': sum((entry.get('usage') or {}).get('completion_tokens_details', {}).get('reasoning_tokens', 0)
                                    for entry in entries)}


def _summary(protocol, prepared, frozen, billing, panel):
    runs = list(frozen['development_runs'])
    runs.extend(run for arms in frozen['targets'].values() for run in arms.values() if 'not_run' not in run)
    active = frozen.get('active', {})
    if 'development' in active:
        runs.extend(active['development'].values())
    if 'target' in active:
        runs.extend(run for by_arm in active['target'].values() for run in by_arm.values())
    targets = {task_id: {arm: _run_summary(run) for arm,run in arms.items()}
               for task_id,arms in frozen['targets'].items()}
    failing = ({task_id for task_id, score in panel['target_clients'].items()
                if score['correct'] < score['total']} if panel is not None else None)
    arm_metrics = {}
    for arm in ARMS:
        arm_runs = [arms[arm] for arms in frozen['targets'].values() if arm in arms]
        arm_metrics[arm] = {**_aggregate_runs(arm_runs),
                            'failed_targets_detected': (sum(bool(arms.get(arm, {}).get('detected'))
                                                         for task_id, arms in frozen['targets'].items()
                                                         if task_id in failing) if failing is not None else None),
                            'total_failing_targets': len(failing) if failing is not None else None,
                            'not_run_targets': sum('not_run' in run for run in arm_runs)}
    call_records = _recorded_calls(protocol, frozen)
    entries_by_phase = {'development': [], 'preparation': [], 'target': []}
    target_provider = {arm: [] for arm in ARMS}
    preparation_provider = {kind: [] for kind in ('procedure', 'ordinary_reuse')}
    for entry in billing['entries']:
        envelope = call_records[entry['node_id']]['envelope']
        if envelope['phase'] == 'prepare':
            entries_by_phase['preparation'].append(entry)
            preparation_provider[envelope['kind']].append(entry)
        elif envelope['prompt']['public_task']['id'] in protocol['development_tasks']:
            entries_by_phase['development'].append(entry)
        else:
            entries_by_phase['target'].append(entry)
            target_provider[envelope['arm']].append(entry)
    examples_cost = _native_total(task['audit']['example_receipt']['cost'] for task in prepared.values())
    panel_cost = (_native_total(score['validation_cost'] for score in panel['target_clients'].values())
                  if panel is not None else None)
    run_cost = _native_total(run['native_cost'] for run in runs)
    unknown = [e for e in billing['entries'] if e['cost'] is None]
    return {'schema':'zenith_client_investigation_report_v1',
            'study_schema':protocol['schema'], 'complete':frozen['complete'],
            'protected_panel_opened':panel is not None,
            'model':protocol['model'], 'provider_slug':protocol['provider_slug'],
            'reasoning_effort':protocol['reasoning_effort'],
            'target_count':len(protocol['target_tasks']),
            'total_failing_targets':len(failing) if failing is not None else None,
            'native_sqlite_versions':sorted({task['audit']['example_receipt']['sqlite_version'] for task in prepared.values()}),
            'protocol_sha256':digest(protocol), 'source_sha256':protocol['source_archive']['sha256'],
            'prepared_tasks_sha256':protocol['prepared_tasks_sha256'],
            'development_runs_completed':len(frozen['development_runs']),
            'target_runs_completed':sum('not_run' not in r for arms in frozen['targets'].values() for r in arms.values()),
            'native_reference_calls':sum(r['native_cost']['reference_calls'] for r in runs),
            'native_client_calls':sum(r['native_cost']['client_calls'] for r in runs),
            'query_slots':sum(r['query_slots'] for r in runs),
            'policy_executions':sum(r['policy_executions'] for r in runs),
            'policy_elapsed_seconds_observed':sum(r['policy_elapsed_seconds'] for r in runs),
            'native_elapsed_seconds_observed':sum(r['native_elapsed_seconds'] for r in runs),
            'prepared_example_receipts':len(prepared),
            'prepared_example_native_cost':examples_cost,
            'model_attempts':sum(run['model_call_attempts'] for run in runs) + len(frozen['artifacts']) +
                             len(frozen.get('active', {}).get('artifact', {})),
            'metered_attempts':len(billing['entries']),
            'known_cost_attempts':len(billing['entries'])-len(unknown),
            'unknown_cost_attempts':len(unknown),
            'unknown_cost_reservations_usd':str(sum((amount(e['reserved_cost_usd']) for e in unknown),Decimal(0))),
            'reported_model_cost_usd':billing['total_reported_cost_usd'],
            'targets':targets,
            'arm_metrics':arm_metrics,
            'artifacts':{kind:{key:row.get(key) for key in ('scope','error','raw_sha256','envelope_sha256')}
                         for kind,row in frozen['artifacts'].items()},
            'lifecycle':{
                'provider_discovery':{'evidence':protocol['model_evidence'],
                    'cost_boundary':'Official metadata lookup retained in protocol; no separately metered lookup charge or elapsed-time record. All inference attempts appear below.'},
                'provider_by_phase':{phase:_provider_total(entries) for phase,entries in entries_by_phase.items()},
                'preparation_provider_by_arm':{arm:_provider_total(entries) for arm,entries in preparation_provider.items()},
                'target_provider_by_arm':{arm:_provider_total(entries) for arm,entries in target_provider.items()},
                'all_provider':_provider_total(billing['entries']),
                'development':_aggregate_runs(frozen['development_runs']),
                'native_cost':{'study_queries':run_cost, 'shared_public_examples':examples_cost,
                    'protected_validation':panel_cost,
                    'total':_native_total([run_cost,examples_cost] + ([panel_cost] if panel_cost is not None else []))},
                'cost_boundary':'Shared development is charged once; each retained preparation and target arm is shown separately. Native execution has work counters and observed query/policy time, without a cash price. Human authoring and provider metadata lookup time were not metered.'},
            'panel':panel,
            'boundary':'Authored SQLite within-family feasibility. Detection is a host-verified discrepancy, not a model-authored diagnosis or independent transfer. Terminal partial evidence has no protected scoring; missing calls and results are not reconstructed.'}


def export(study, output):
    study, output = Path(study).resolve(), Path(output).resolve()
    if output.exists():
        raise ValueError('Evidence exports are immutable; choose a new output')
    protocol = read(study / 'protocol.json')
    if protocol.get('schema') not in PROTOCOL_DOCUMENTS:
        raise ValueError('Unknown client study schema')
    protocol_doc = ROOT / PROTOCOL_DOCUMENTS[protocol['schema']]
    if not protocol_doc.is_file() or sha(protocol_doc) != protocol.get('protocol_doc_sha256'):
        raise ValueError('Frozen protocol source differs from current document')
    if not (study / 'protocol-source.md').exists():
        # The preparation script freezes only the document hash; copy that
        # exact current version into a disposable export stage below.
        pass
    with tempfile.TemporaryDirectory(prefix='zenith-client-export-', dir=output.parent) as temporary:
        stage = Path(temporary) / 'evidence'
        stage.mkdir()
        for name in ('protocol.json','prepared-tasks.json','runtime-source.zip','started.json',
                     'state.json','frozen.json'):
            source = study / name
            _check_public_payload(source)
            shutil.copyfile(source, stage / name)
        shutil.copyfile(protocol_doc, stage / 'protocol-source.md')
        for directory in ('prompts','responses'):
            source_dir = study / directory
            if source_dir.exists():
                for source in source_dir.glob('*.json'):
                    _check_public_payload(source)
                    destination = stage / directory / source.name
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(source, destination)
        panel = study / 'protected-panel.json'
        if panel.exists():
            _check_public_payload(panel)
            shutil.copyfile(panel, stage / panel.name)
        protocol, prepared, frozen, calls, files = _files_and_calls(stage)
        ledger = read(study / 'budget/budget.json')
        billing = _billing(ledger, calls, complete=frozen['complete'])
        if SECRET.search(json.dumps(billing)) or PRIVATE_URL.search(json.dumps(billing)) or PRIVATE_METADATA.search(json.dumps(billing)):
            raise ValueError('Projected billing contains private metadata')
        write(stage / 'billing.json', billing)
        panel_data = read(stage / 'protected-panel.json') if panel.exists() else None
        write(stage / 'report.json', _summary(protocol, prepared, frozen, billing, panel_data))
        manifest = {'schema':EXPORT_VERSION,
                    'boundary':'Exact scientific prompts, raw outputs, frozen source and task evidence; allowlisted numeric provider billing only. No credentials or private transport metadata.',
                    'files':{str(p.relative_to(stage)):sha(p) for p in sorted(stage.rglob('*')) if p.is_file()}}
        write(stage / 'manifest.json', manifest)
        result = replay(stage)
        stage.rename(output)
    return {'output':str(output), **result}


def verify_manifest(output):
    output = Path(output).resolve()
    manifest = read(output / 'manifest.json')
    if manifest.get('schema') != EXPORT_VERSION or not isinstance(manifest.get('files'), dict):
        raise ValueError('Unknown client export manifest')
    for name in manifest['files']:
        safe_relative(name)
    if any(p.is_symlink() for p in output.rglob('*')):
        raise ValueError('Published evidence contains symlink')
    actual = {str(p.relative_to(output)) for p in output.rglob('*') if p.is_file()} - {'manifest.json'}
    if actual != set(manifest['files']) or any(sha(output / name) != expected for name,expected in manifest['files'].items()):
        raise ValueError('Published evidence hash/membership mismatch')
    protocol, prepared, frozen, calls, files = _files_and_calls(output)
    if set(manifest['files']) != files | {'billing.json','report.json'}:
        raise ValueError('Published scientific allowlist mismatch')
    billing = read(output / 'billing.json')
    if billing.get('schema') != BILLING_VERSION:
        raise ValueError('Unknown projected billing schema')
    _billing({'schema':'zenith_shared_budget_v1','entries':{e['call_id']:e for e in billing['entries']},
              'total_reported_cost_usd':billing['total_reported_cost_usd'],
              'total_reserved_usd':billing['total_reserved_usd'],'halted':billing['halted']},
             calls, complete=frozen['complete'])
    panel = read(output / 'protected-panel.json') if 'protected-panel.json' in files else None
    if read(output / 'report.json') != _summary(protocol, prepared, frozen, billing, panel):
        raise ValueError('Published report differs from exact evidence counters')
    return {'protocol':protocol,'prepared':prepared,'frozen':frozen,'billing':billing,
            'calls':len(calls),'complete':frozen['complete'],'panel_opened':panel is not None}


REPLAY_PROGRAM = '''
import json,socket,sqlite3,sys
from pathlib import Path
def denied(*args,**kwargs):
    raise RuntimeError("Network disabled for archived client replay")
socket.socket.connect=denied
socket.socket.connect_ex=denied
socket.create_connection=denied
socket.getaddrinfo=denied
sys.path.insert(0,sys.argv[1])
from research import client_investigation_study as study
from research.client_investigation_tasks import score
out=Path(sys.argv[2])
protocol=json.loads((out/'protocol.json').read_text())
mode=sys.argv[3]
frozen_versions=sorted({task['audit']['example_receipt']['sqlite_version']
    for task in json.loads((out/'prepared-tasks.json').read_text()).values()})
if mode=='behavioral':
    original=study._scientific_state
    def without_engine_identity(value):
        if isinstance(value,dict):
            return {key:without_engine_identity(item) for key,item in value.items() if key!='sqlite_version'}
        if isinstance(value,list):
            return [without_engine_identity(item) for item in value]
        return value
    def behavioral_state(value):
        return without_engine_identity(original(value))
    study._scientific_state=behavioral_state
panel=out/'protected-panel.json'
if panel.exists():
    published=json.loads(panel.read_text())
    expected={task_id:score(task_id) for task_id in protocol['target_tasks']}
    if published.get('target_clients') != expected:
        raise ValueError('protected panel differs from archived native scorer')
receipt=study.replay_study(out)
if mode=='behavioral':
    receipt['schema']='zenith_client_investigation_behavior_replay_v1'
    receipt['status']='behavioral_match' if receipt['status']=='exact' else 'partial_behavioral_match'
    receipt['ignored_runtime_fields']=['sqlite_version']
    receipt['frozen_sqlite_versions']=frozen_versions
    receipt['replay_sqlite_version']=sqlite3.sqlite_version
    receipt['environment_changed']=frozen_versions!=[sqlite3.sqlite_version]
    receipt['boundary']='Exact custody and model deliveries; all queries, outcomes, errors, work counters and costs compared. SQLite version identity and the original replay clock fields are excluded from state comparison. This is not exact runtime replay.'
print(json.dumps(receipt,allow_nan=False))
'''


def replay(output, *, mode='exact'):
    if mode not in ('exact', 'behavioral'):
        raise ValueError('Unknown archived replay mode')
    output = Path(output).resolve()
    checked = verify_manifest(output)
    with tempfile.TemporaryDirectory(prefix='zenith-client-replay-') as temporary:
        runtime = Path(temporary) / 'runtime'
        runtime.mkdir()
        with ZipFile(output / 'runtime-source.zip') as archive:
            archive.extractall(runtime)
        protocol_doc = runtime / PROTOCOL_DOCUMENTS[checked['protocol']['schema']]
        protocol_doc.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(output / 'protocol-source.md', protocol_doc)
        command = [sys.executable,'-I','-B','-c',REPLAY_PROGRAM,str(runtime),str(output),mode]
        result = subprocess.run(command,cwd=runtime,env={},capture_output=True,text=True,timeout=300)
        if result.returncode:
            raise RuntimeError('Archived client replay failed: ' + result.stderr[-3000:])
        receipt = json.loads(result.stdout)
        expected = (('exact' if checked['complete'] else 'partial_exact') if mode == 'exact' else
                    ('behavioral_match' if checked['complete'] else 'partial_behavioral_match'))
        if (receipt.get('status') != expected or
                receipt.get('network_calls') != 0 or
                receipt.get('model_attempts_replayed') != checked['calls']):
            raise ValueError('Archived replay status differs from frozen evidence')
        return {'ok':True,'complete':checked['complete'],'panel_opened':checked['panel_opened'],
                'calls':checked['calls'],'reported_cost_usd':checked['billing']['total_reported_cost_usd'],
                'replay_kind':mode,'archived_replay':receipt}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command',required=True)
    export_command = commands.add_parser('export')
    export_command.add_argument('study',type=Path)
    export_command.add_argument('output',type=Path)
    replay_command = commands.add_parser('replay')
    replay_command.add_argument('output',type=Path)
    behavior_command = commands.add_parser('replay-behavior', help='Compare behavior while explicitly excluding SQLite version identity')
    behavior_command.add_argument('output',type=Path)
    args = parser.parse_args()
    result = (export(args.study,args.output) if args.command == 'export' else
              replay(args.output,mode='behavioral' if args.command == 'replay-behavior' else 'exact'))
    print(json.dumps(result,indent=2))


if __name__ == '__main__':
    main()
