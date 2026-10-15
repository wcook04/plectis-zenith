"""Bounded, source-bound client investigation pilot; no inference at import time.

The caller supplies a metered ask(envelope)->raw JSON callback. This owner keeps
model-visible evidence separate from custody fields and persists every attempt
through on_event before proceeding. The authored SQLite tasks are a feasibility
pilot, not independent transfer evidence.
"""
from __future__ import annotations

from copy import deepcopy
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import time
from typing import Callable

from research.client_investigation_tasks import (ProbeOracle, model_visible_receipt,
                                                 prepare_task, task_ids)
from research.decomposition_study import LANGUAGE
from research.direct_investigation import decode, response_schema
from zenith.investigation_program import execute, validate_source
from zenith.providers import digest, now, write_json


VERSION_V1 = 'zenith_client_investigation_study_v1'
VERSION = 'zenith_client_investigation_study_v2'
PROMPT_VERSIONS = ('v1', 'v2')
ARMS = ('procedure', 'ordinary_reuse', 'same_history', 'cold', 'fixed')
QUERY_CAP = 6
MODEL_TURNS = 6
QUERIES_PER_TURN = 1
MAX_CALLS = 5 * MODEL_TURNS + 2 + 5 * 2 * MODEL_TURNS
PUBLIC_TASK_KEYS = frozenset(('id', 'family', 'contract', 'query_shape',
                              'example', 'probe_limit'))

DIRECT_SYSTEM_V1 = '''Investigate the opaque client under its public contract.
Return exactly JSON {"queries": [legal query objects], "note": string or null}.
You may use measured reference/client results from earlier turns. Do not assert
unmeasured expected outputs. Do not repeat the public example or earlier queries.
Queries are actions, not a repaired implementation. Empty queries stops.'''

RESTRICTED_PYTHON = LANGUAGE[
    LANGUAGE.index('Only function definitions at module level.'):
    LANGUAGE.index('Use scope/change for concise technical claims')]

ARTIFACT_SYSTEM_V1 = '''Write one small restricted-Python investigation function:
def investigate(context, acquire): ...
The function returns {"query": a legal query object or null, "note": string or null}.
context contains public_task, development_receipts, target_receipts, remaining_slots.
Use only that measured evidence. Do not embed hidden implementation labels,
target answers, repaired client code or old exact answers as target answers.
Return JSON with exactly source and scope strings. The source is run under
Zenith's restricted investigation executor, with no ambient files/network.
The target-family contract/grammar are known before target outcomes, but no
target implementation, ID, example or result is supplied during preparation.
''' + RESTRICTED_PYTHON


ACTION_PERMISSION = '''Distinguish measured observations from proposed experiments.
You may design new legal queries from the public contract and full query grammar,
including before any target receipt exists. Development receipts may motivate
questions and measured target receipts may guide later choices. A proposed query
does not assert its outcome. Never present an unmeasured reference/client outcome
or an old exact answer as a measured target result. Stopping remains allowed.'''

DIRECT_SYSTEM = '''Investigate the opaque client under its public contract.
Return exactly JSON {"queries": [legal query objects], "note": string or null}.
''' + ACTION_PERMISSION + '''
Do not repeat the public example or earlier queries. Queries are actions, not a
repaired implementation. Empty queries stops.'''

ARTIFACT_SYSTEM = '''Write one small restricted-Python investigation function:
def investigate(context, acquire): ...
The function returns {"query": a legal query object or null, "note": string or null}.
context contains public_task, development_receipts, target_receipts, remaining_slots.
''' + ACTION_PERMISSION + '''
The function may emit its first legal query when target_receipts is empty; it need
not wait for target evidence before testing a public contractual obligation.
Do not embed hidden implementation labels, target answers or repaired client code.
Return JSON with exactly source and scope strings. The source is run under
Zenith's restricted investigation executor, with no ambient files/network.
The target-family contract/grammar are known before target outcomes, but no
target implementation, ID, example or result is supplied during preparation.
''' + RESTRICTED_PYTHON


def _profile(prompt_version: str) -> dict:
    if prompt_version not in PROMPT_VERSIONS:
        raise ValueError('unknown client prompt version')
    if prompt_version == 'v1':
        return {'schema': VERSION_V1, 'direct': DIRECT_SYSTEM_V1,
                'artifact': ARTIFACT_SYSTEM_V1,
                'protocol_doc': 'docs/client-investigation-protocol-20261014.md'}
    return {'schema': VERSION, 'direct': DIRECT_SYSTEM, 'artifact': ARTIFACT_SYSTEM,
            'protocol_doc': 'docs/client-investigation-protocol-v2-20261015.md'}


def _protocol_profile(protocol: dict) -> tuple[str, dict]:
    # Historical v1 manifests predate the explicit prompt_version field.
    prompt_version = protocol.get('prompt_version', 'v1')
    profile = _profile(prompt_version)
    if protocol.get('schema') != profile['schema']:
        raise ValueError('client study schema differs from prompt version')
    return prompt_version, profile


def _prompt_hashes(profile: dict) -> dict[str, str]:
    return {kind: hashlib.sha256(profile[kind].encode()).hexdigest()
            for kind in ('direct', 'artifact')}


def _visible_receipt(receipt: dict) -> dict:
    measured = receipt.get('measurement')
    result = model_visible_receipt(measured) if isinstance(measured, dict) else {}
    for key in ('slot', 'query', 'note', 'query_error'):
        if key in receipt:
            result[key] = deepcopy(receipt[key])
    return result


def _model_task(task: dict) -> dict:
    """Allow only the exact public task projection, without host cost fields."""
    if type(task) is not dict or set(task) != PUBLIC_TASK_KEYS:
        raise ValueError('unexpected public task fields')
    if task.get('id') not in task_ids() or type(task.get('example')) is not dict or (
            set(task['example']) != {'query', 'reference', 'client', 'discrepancy'}):
        raise ValueError('invalid public task projection')
    return deepcopy(task)


def _history(development: list[dict] | None) -> list[dict]:
    """Project an old trajectory onto model-visible material, never full records."""
    if development is None:
        return []
    if type(development) is not list:
        raise ValueError('development history must be a list')
    result = []
    for row in development:
        if type(row) is not dict or 'public_task' not in row or 'receipts' not in row:
            raise ValueError('development row requires public_task and receipts')
        task = row['public_task']
        _model_task(task)
        if task['family'] != 'batch' or task['id'] not in task_ids('batch'):
            raise ValueError('development row must contain a batch task')
        result.append({'public_task': _model_task(task),
                       'receipts': [_visible_receipt(r) for r in row['receipts']]})
    return result


def artifact_schema() -> dict:
    return {'type': 'object', 'properties': {
        'source': {'type': 'string', 'maxLength': 60000},
        'scope': {'type': 'string', 'maxLength': 500}},
        'required': ['source', 'scope'], 'additionalProperties': False}


def _strict_object(raw: str) -> dict:
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('duplicate JSON key')
            result[key] = value
        return result
    def nonfinite(value):
        raise ValueError('non-finite JSON constant')
    if type(raw) is not str or not raw.strip() or len(raw.encode()) > 70000:
        raise ValueError('delivery must be nonempty JSON within 70000 bytes')
    body = json.loads(raw, object_pairs_hook=pairs, parse_constant=nonfinite)
    json.dumps(body, allow_nan=False)
    if type(body) is not dict:
        raise ValueError('delivery must be a JSON object')
    return body


def compile_artifact(development: list[dict], ask: Callable[[dict], str], *,
                     kind: str, target_family_spec: dict,
                     prompt_version: str = 'v2',
                     on_event: Callable[[dict], None] | None = None) -> dict:
    """One charged preparation attempt per kind; invalid source is preserved."""
    if kind not in ('procedure', 'ordinary_reuse'):
        raise ValueError('unknown retained artifact kind')
    profile = _profile(prompt_version)
    history = _history(development)
    if type(target_family_spec) is not dict or set(target_family_spec) != {
            'family', 'contract', 'query_shape', 'probe_limit'} or target_family_spec['family'] != 'transfer':
        raise ValueError('static transfer family specification required before compilation')
    envelope = {'phase': 'prepare', 'kind': kind, 'system': profile['artifact'],
                'response_schema': artifact_schema(),
                'prompt': {'development_history': history,
                           'prospective_target_family': deepcopy(target_family_spec),
                           'future_policy_context': {
                               'public_task': 'opaque target public task at deployment, including measured benign example',
                               'development_receipts': 'same visible development history supplied here',
                               'target_receipts': 'new measured target queries so far',
                               'remaining_slots': QUERY_CAP},
                           'role': ('Retain an adaptive diagnostic procedure.' if kind == 'procedure'
                                    else 'Retain the strongest ordinary reusable tester/code from this history.'),
                           'return_contract': 'investigate(context, acquire) returns query and note'}}
    result = {'kind': kind, 'envelope': deepcopy(envelope),
              'envelope_sha256': digest(envelope), 'raw': None,
              'source': None, 'scope': None, 'error': None,
              'model_call_attempts': 1}
    if on_event:
        on_event(deepcopy(result))
    started = time.monotonic()
    try:
        raw = ask(deepcopy(envelope))
    except Exception as exc:
        result['error'] = f'adapter_failure: {type(exc).__name__}: {exc}'[:500]
        result['elapsed_seconds'] = time.monotonic() - started
        if on_event:
            on_event(deepcopy(result))
        raise RuntimeError('artifact provider failure; study is incomplete') from exc
    result['elapsed_seconds'] = time.monotonic() - started
    result['raw'] = raw
    if isinstance(raw, str):
        result['raw_sha256'] = hashlib.sha256(raw.encode()).hexdigest()
    if on_event:
        on_event(deepcopy(result))
    try:
        body = _strict_object(raw)
        if set(body) != {'source', 'scope'} or type(body['source']) is not str or type(body['scope']) is not str:
            raise ValueError('artifact requires source and scope strings')
        if len(body['scope']) > 500 or len(body['scope'].encode()) > 2048:
            raise ValueError('scope exceeds 500 characters / 2048 bytes')
        validate_source(body['source'])
        result['source'], result['scope'] = body['source'], body['scope']
    except (ValueError, SyntaxError, TypeError, RecursionError) as exc:
        result['error'] = f'{type(exc).__name__}: {exc}'[:500]
    if on_event:
        on_event(deepcopy(result))
    return result


def fixed_queries(family: str) -> tuple[dict, ...]:
    """Predeclared ordinary tests for success, failure, ownership and recovery."""
    if family == 'batch':
        return (
            {'outer': True, 'initial': [1], 'steps': [[2, 2], [3]], 'continuation': 4},
            {'outer': True, 'initial': [1], 'steps': [[2], [10, 3], [4]], 'continuation': 5},
            {'outer': True, 'initial': [1], 'steps': [[2], [3]], 'continuation': 4},
            {'outer': False, 'initial': [1], 'steps': [[2, 2], [3]], 'continuation': 4},
        )
    if family == 'transfer':
        return (
            {'outer': True, 'initial': [[1, 5], [2, 1]],
             'steps': [[1, 2, 2], [1, 10, 1], [2, 1, 1]], 'continuation': [2, 1]},
            {'outer': True, 'initial': [[1, 5], [2, 1]],
             'steps': [[1, 2, 2], [2, 1, 1]], 'continuation': [2, 1]},
            {'outer': False, 'initial': [[1, 5], [2, 1]],
             'steps': [[1, 10, 2], [2, 1, 1]], 'continuation': [2, 1]},
        )
    raise ValueError('unknown client family')


def run_arm(task_id: str, arm: str, *, ask: Callable[[dict], str] | None = None,
            development: list[dict] | None = None, artifact: dict | None = None,
            prepared: dict | None = None,
            prompt_version: str = 'v2',
            on_event: Callable[[dict], None] | None = None,
            query_cap: int = QUERY_CAP) -> dict:
    """Run one fresh opaque task/arm, preserving each attempt before next action."""
    if arm not in ARMS or task_id not in task_ids():
        raise ValueError('unknown arm or task')
    profile = _profile(prompt_version)
    if type(query_cap) is not int or not 1 <= query_cap <= QUERY_CAP:
        raise ValueError('query cap must be 1..6')
    if arm in ('procedure', 'ordinary_reuse') and (
            not isinstance(artifact, dict) or artifact.get('kind') != arm or
            artifact.get('error') is not None or type(artifact.get('source')) is not str):
        raise ValueError('valid frozen artifact required for retained arm')
    if arm in ('same_history', 'cold') and ask is None:
        raise ValueError('direct arms require a metered ask callback')
    if arm == 'cold' and development:
        raise ValueError('cold arm cannot receive development history')
    prepared = prepared if prepared is not None else prepare_task(task_id)
    if type(prepared) is not dict or set(prepared) != {'public', 'audit'}:
        raise ValueError('task preparation must include public and audit')
    public = _model_task(prepared['public'])
    if public['id'] != task_id:
        raise ValueError('prepared task does not match target')
    if public['probe_limit'] != QUERY_CAP:
        raise ValueError('public task query allowance differs from frozen study')
    history = _history(development) if arm != 'cold' else []
    oracle = ProbeOracle(task_id)
    seen = {digest(public['example']['query'])}
    result = {'version': profile['schema'], 'task_id': task_id, 'arm': arm,
              'public_task': deepcopy(public), 'development_history_sha256': digest(history),
              'example_audit': deepcopy(prepared['audit']),
              'artifact_sha256': digest({'source': artifact['source'], 'scope': artifact['scope']}) if artifact else None,
              'receipts': [], 'turns': [], 'query_slots': 0, 'valid_probes': 0,
              'model_call_attempts': 0, 'detected': False, 'halted': None,
              'policy_executions': 0, 'policy_elapsed_seconds': 0.0,
              'native_elapsed_seconds': 0.0,
              'native_cost': vars(oracle.meter).copy()}

    def snapshot():
        result['native_cost'] = vars(oracle.meter).copy()
        if on_event:
            on_event(deepcopy(result))

    def probe(query, note):
        result['query_slots'] += 1
        row = {'slot': result['query_slots'], 'query': deepcopy(query), 'note': note}
        result['receipts'].append(row)
        snapshot()
        try:
            if digest(query) in seen:
                raise ValueError('duplicate of public example or earlier query')
            seen.add(digest(query))
            if len(json.dumps(query, ensure_ascii=True, allow_nan=False).encode()) > 16000:
                raise ValueError('query exceeds 16000 serialized bytes')
            started = time.monotonic()
            try:
                receipt = oracle.ask(query)
            finally:
                result['native_elapsed_seconds'] += time.monotonic() - started
        except (ValueError, TypeError, KeyError, OverflowError) as exc:
            row['query_error'] = f'{type(exc).__name__}: {exc}'[:500]
            snapshot()
            return
        row['measurement'] = receipt  # Full source custody stays out of later prompts.
        result['valid_probes'] += 1
        result['detected'] = result['detected'] or receipt['discrepancy']
        snapshot()

    direct_turn = 0
    while result['query_slots'] < query_cap and not result['detected']:
        remaining = query_cap - result['query_slots']
        if arm == 'fixed':
            queries = fixed_queries(public['family'])
            if result['query_slots'] >= len(queries):
                break
            probe(queries[result['query_slots']], None)
            continue
        if arm in ('procedure', 'ordinary_reuse'):
            context = {'public_task': _model_task(public), 'development_receipts': history,
                       'target_receipts': [_visible_receipt(r) for r in result['receipts']],
                       'remaining_slots': remaining}
            try:
                started = time.monotonic()
                result['policy_executions'] += 1
                snapshot()
                try:
                    output = execute(artifact['source'], [{'tables': {}, **context}], answer_contract='json')[0]
                finally:
                    result['policy_elapsed_seconds'] += time.monotonic() - started
                if output['error']:
                    raise ValueError(output['error'])
                body = output['answer']
                if type(body) is not dict or set(body) != {'query', 'note'} or (
                        body['note'] is not None and (type(body['note']) is not str or len(body['note']) > 500)):
                    raise ValueError('policy must return query and bounded note')
            except (ValueError, SyntaxError, RuntimeError) as exc:
                result['halted'] = f'policy_error: {exc}'[:500]
                snapshot()
                break
            if body['query'] is None:
                result['halted'] = 'policy_stop'
                snapshot()
                break
            probe(body['query'], body['note'])
            continue
        if direct_turn >= MODEL_TURNS:
            break
        direct_turn += 1
        limit = min(QUERIES_PER_TURN, remaining)
        envelope = {'phase': 'target_query', 'arm': arm, 'turn': direct_turn,
                    'system': profile['direct'], 'response_schema': response_schema(limit),
                    'prompt': {'public_task': _model_task(public),
                               'development_history': deepcopy(history),
                               'target_receipts': [_visible_receipt(r) for r in result['receipts']],
                               'remaining_slots': remaining, 'max_queries_this_turn': limit}}
        call = {'turn': direct_turn, 'envelope': deepcopy(envelope),
                'envelope_sha256': digest(envelope), 'raw': None, 'error': None}
        result['turns'].append(call)
        result['model_call_attempts'] += 1
        snapshot()
        started = time.monotonic()
        try:
            raw = ask(deepcopy(envelope))
        except Exception as exc:
            call['error'] = f'adapter_failure: {type(exc).__name__}: {exc}'[:500]
            call['elapsed_seconds'] = time.monotonic() - started
            result['halted'] = 'adapter_failure'
            snapshot()
            raise RuntimeError('client investigation provider failure; study is incomplete') from exc
        call['elapsed_seconds'] = time.monotonic() - started
        call['raw'] = raw
        if isinstance(raw, str):
            call['raw_sha256'] = hashlib.sha256(raw.encode()).hexdigest()
        snapshot()
        try:
            plan = decode(raw, limit)
        except (ValueError, TypeError, RecursionError) as exc:
            call['error'] = f'{type(exc).__name__}: {exc}'[:500]
            result['halted'] = 'model_delivery_error'
            snapshot()
            break
        if not plan['queries']:
            result['halted'] = 'model_stop'
            snapshot()
            break
        for query in plan['queries']:
            if result['query_slots'] >= query_cap or result['detected']:
                break
            probe(query, plan['note'])
    snapshot()
    return result


def run_development(ask: Callable[[dict], str], *,
                    ids: tuple[str, ...] | None = None,
                    prepared_tasks: dict | None = None,
                    prompt_version: str = 'v2',
                    on_event: Callable[[dict], None] | None = None) -> list[dict]:
    """Acquire development traces once, before compiling either retained arm."""
    selected = ids or task_ids('batch')
    if len(set(selected)) != len(selected) or not selected or any(x not in task_ids('batch') for x in selected):
        raise ValueError('development must use distinct opaque batch tasks')
    rows = []
    for task_id in selected:
        prepared = prepared_tasks[task_id] if prepared_tasks is not None else None
        run = run_arm(task_id, 'same_history', ask=ask, prepared=prepared,
                      prompt_version=prompt_version,
                      on_event=on_event)
        rows.append({'public_task': run['public_task'], 'receipts': run['receipts'],
                     'query_slots': run['query_slots'], 'model_call_attempts': run['model_call_attempts'],
                     'native_cost': run['native_cost']})
    return rows


def source_hashes() -> dict[str, str]:
    root = Path(__file__).resolve().parents[1]
    paths = ('research/client_investigation_study.py',
             'research/client_investigation_tasks.py',
             'research/decomposition_study.py',
             'research/direct_investigation.py',
             'zenith/investigation_program.py', 'zenith/budgeted.py',
             'zenith/provider_policy.py', 'zenith/providers.py')
    return {name: hashlib.sha256((root/name).read_bytes()).hexdigest() for name in paths}


def prepare_study(output: str | Path, *, model: str, provider_slug: str,
                  reasoning_effort: str = 'low', max_cost_usd: str = '2',
                  max_output_tokens: int = 8192,
                  prompt_version: str = 'v2',
                  model_evidence: dict | None = None) -> dict:
    """Freeze all ten opaque tasks and source before any provider request."""
    from zenith.budgeted import budget_options
    from zenith.source_snapshot import archive_runtime
    profile = _profile(prompt_version)
    output = Path(output).resolve()
    if not provider_slug or reasoning_effort not in ('none', 'low', 'medium', 'high'):
        raise ValueError('pin provider and supported reasoning effort')
    if type(model_evidence) is not dict or not model_evidence:
        raise ValueError('current official model/endpoint/price evidence required')
    if float(max_cost_usd) > 2:
        raise ValueError('client pilot has a $2 hard ceiling')
    budget_options(model, max_cost_usd, MAX_CALLS, max_output_tokens, output/'budget')
    output.mkdir(parents=True, exist_ok=False)
    prepared = {task_id: prepare_task(task_id) for task_id in task_ids()}
    from research.client_investigation_tasks import public_family_spec
    target_family_spec = public_family_spec('transfer')
    write_json(output/'prepared-tasks.json', prepared)
    archive = archive_runtime(output)
    archive['path'] = 'runtime-source.zip'
    protocol_doc = Path(__file__).resolve().parents[1]/profile['protocol_doc']
    protocol = {'schema': profile['schema'], 'created_at': now(),
                'model': model, 'provider_slug': provider_slug,
                'reasoning_effort': reasoning_effort,
                'max_cost_usd': max_cost_usd,
                'max_output_tokens': max_output_tokens,
                'max_calls': MAX_CALLS, 'max_calls_is_ceiling': True,
                'development_tasks': list(task_ids('batch')),
                'target_tasks': list(task_ids('transfer')),
                'prospective_target_family': target_family_spec,
                'arms': list(ARMS), 'query_cap': QUERY_CAP,
                'model_turns': MODEL_TURNS,
                'queries_per_turn': QUERIES_PER_TURN,
                'first_example_cost_shared_per_task': True,
                'prepared_tasks_sha256': digest(prepared),
                'source_hashes': source_hashes(), 'source_archive': archive,
                'protocol_doc_sha256': hashlib.sha256(protocol_doc.read_bytes()).hexdigest(),
                'model_evidence': deepcopy(model_evidence),
                'claim_boundary': 'Authored SQLite within-family feasibility; no independent transfer or policy-learning result.'}
    if prompt_version == 'v2':
        protocol.update({'prompt_version': prompt_version,
                         'prompt_sha256': _prompt_hashes(profile),
                         'protocol_doc': profile['protocol_doc'],
                         'claim_boundary': 'Prompt-delivery engineering check on the already exposed authored SQLite population; no independent efficacy or transfer result.'})
    write_json(output/'protocol.json', protocol)
    return protocol


def verify_study(output: str | Path) -> tuple[dict, dict]:
    output = Path(output).resolve()
    protocol = json.loads((output/'protocol.json').read_text())
    prepared = json.loads((output/'prepared-tasks.json').read_text())
    prompt_version, profile = _protocol_profile(protocol)
    if protocol['source_hashes'] != source_hashes():
        raise ValueError('study source differs from frozen source')
    if prompt_version == 'v2' and (
            protocol.get('prompt_sha256') != _prompt_hashes(profile) or
            protocol.get('protocol_doc') != profile['protocol_doc']):
        raise ValueError('client prompt profile differs from freeze')
    protocol_doc = Path(__file__).resolve().parents[1]/profile['protocol_doc']
    if protocol['protocol_doc_sha256'] != hashlib.sha256(protocol_doc.read_bytes()).hexdigest():
        raise ValueError('client protocol differs from frozen source')
    if protocol['prepared_tasks_sha256'] != digest(prepared):
        raise ValueError('prepared task evidence differs from freeze')
    if hashlib.sha256((output/'runtime-source.zip').read_bytes()).hexdigest() != protocol['source_archive']['sha256']:
        raise ValueError('archived source differs from freeze')
    if protocol['development_tasks'] != list(task_ids('batch')) or protocol['target_tasks'] != list(task_ids('transfer')):
        raise ValueError('opaque task population differs from freeze')
    return protocol, prepared


def execute_study(output: str | Path, ask: Callable[[dict], str]) -> dict:
    """Execute frozen pilot once; caller must make ask metered and source-bound."""
    output = Path(output).resolve()
    protocol, prepared = verify_study(output)
    prompt_version, _ = _protocol_profile(protocol)
    if (output/'started.json').exists():
        raise ValueError('started study cannot be retried')
    with (output/'started.json').open('x') as handle:
        json.dump({'at': now(), 'protocol_sha256': digest(protocol)}, handle)
    state = {'schema': protocol['schema'], 'protocol_sha256': digest(protocol),
             'development': [], 'development_runs': [],
             'artifacts': {}, 'targets': {}, 'complete': False,
             'failure': None, 'terminal_error': None}
    write_json(output/'state.json', state)

    def save():
        write_json(output/'state.json', state)

    try:
        for task_id in protocol['development_tasks']:
            def snapshot_development(snapshot, key=task_id):
                state.setdefault('active', {})['development'] = {key: snapshot}
                save()
            run = run_arm(task_id, 'same_history', ask=ask,
                          prompt_version=prompt_version,
                          prepared=prepared[task_id], on_event=snapshot_development)
            state['development_runs'].append(run)
            state['development'].append({'public_task': run['public_task'],
                                         'receipts': run['receipts'],
                                         'query_slots': run['query_slots'],
                                         'model_call_attempts': run['model_call_attempts'],
                                         'native_cost': run['native_cost']})
            state.pop('active', None)
            save()
        for kind in ('procedure', 'ordinary_reuse'):
            def snapshot_artifact(snapshot, key=kind):
                state.setdefault('active', {})['artifact'] = {key: snapshot}
                save()
            state['artifacts'][kind] = compile_artifact(state['development'], ask,
                kind=kind, target_family_spec=protocol['prospective_target_family'],
                prompt_version=prompt_version,
                on_event=snapshot_artifact)
            state.pop('active', None)
            save()
        # All retained artifacts are frozen before a target query is executed.
        state['artifact_freeze_sha256'] = digest({kind: {
            key: row.get(key) for key in ('source', 'scope', 'error',
                                           'raw_sha256', 'envelope_sha256')}
            for kind, row in state['artifacts'].items()})
        save()
        for task_id in protocol['target_tasks']:
            state['targets'][task_id] = {}
            for arm in protocol['arms']:
                if arm in ('procedure', 'ordinary_reuse') and state['artifacts'][arm]['error']:
                    state['targets'][task_id][arm] = {'not_run': 'invalid frozen artifact'}
                    save()
                    continue
                def snapshot_target(snapshot, key=task_id, label=arm):
                    state.setdefault('active', {})['target'] = {key: {label: snapshot}}
                    save()
                state['targets'][task_id][arm] = run_arm(
                    task_id, arm, ask=ask if arm in ('same_history', 'cold') else None,
                    development=state['development'] if arm != 'cold' else None,
                    artifact=state['artifacts'].get(arm), prepared=prepared[task_id],
                    prompt_version=prompt_version,
                    on_event=snapshot_target)
                state.pop('active', None)
                save()
        state['complete'] = True
    except Exception as exc:
        state['failure'] = f'{type(exc).__name__}: {exc}'[:1000]
        state['terminal_error'] = {
            'kind': type(exc).__name__, 'message': str(exc)[:500],
            'at': now(), 'active_phase': next(iter(state.get('active', {})), None),
            'partial_active_retained': bool(state.get('active'))}
    if state['complete']:
        state.pop('active', None)
    save()
    write_json(output/'frozen.json', state)
    return state


def open_panel(output: str | Path) -> dict:
    """Open the finite target panel only after the full target study is frozen."""
    from research.client_investigation_tasks import score
    output = Path(output).resolve()
    protocol, _ = verify_study(output)
    frozen = json.loads((output/'frozen.json').read_text())
    if not frozen.get('complete') or frozen.get('failure'):
        raise ValueError('cannot open panel for incomplete study')
    target = output/'protected-panel.json'
    if target.exists():
        raise ValueError('protected panel already opened')
    result = {'schema': protocol['schema'], 'frozen_sha256': digest(frozen),
              'target_clients': {task_id: score(task_id)
                                 for task_id in protocol['target_tasks']}}
    with target.open('x') as handle:
        json.dump(result, handle, indent=2)
        handle.write('\n')
    return result


def _recorded_attempts(frozen: dict, protocol: dict) -> list[dict]:
    """Dispatch order of provider attempts, including a terminal partial one."""
    attempts = []
    def turns(run):
        attempts.extend(run.get('turns', []))
    for run in frozen.get('development_runs', []):
        turns(run)
    active = frozen.get('active', {})
    if 'development' in active:
        turns(next(iter(active['development'].values())))
    for kind in ('procedure', 'ordinary_reuse'):
        row = frozen.get('artifacts', {}).get(kind)
        if row is not None:
            attempts.append(row)
        elif active.get('artifact', {}).get(kind) is not None:
            attempts.append(active['artifact'][kind])
    for task_id in protocol['target_tasks']:
        for arm in protocol['arms']:
            row = frozen.get('targets', {}).get(task_id, {}).get(arm)
            if isinstance(row, dict):
                turns(row)
            elif active.get('target', {}).get(task_id, {}).get(arm) is not None:
                turns(active['target'][task_id][arm])
    return attempts


def _scientific_state(value):
    """Ignore clocks and provider exception wording, never queries or costs."""
    timing = {'elapsed_seconds', 'policy_elapsed_seconds',
              'native_elapsed_seconds', 'at'}
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            if key in timing or key == 'failure':
                continue
            if key == 'message' and 'active_phase' in value:
                continue
            if key == 'error' and isinstance(item, str) and item.startswith('adapter_failure:'):
                result[key] = 'adapter_failure'
            else:
                result[key] = _scientific_state(item)
        return result
    if isinstance(value, list):
        return [_scientific_state(item) for item in value]
    return value


def replay_study(output: str | Path) -> dict:
    """Exact offline rerun of frozen model replies, native probes and policies.

    The callback never constructs a provider. A changed SQLite runtime/source,
    unexpected model envelope, lost partial attempt or changed native result
    makes replay fail instead of silently downgrading its claim.
    """
    output = Path(output).resolve()
    protocol, _ = verify_study(output)
    frozen = json.loads((output/'frozen.json').read_text())
    attempts = _recorded_attempts(frozen, protocol)
    if len(attempts) > protocol['max_calls']:
        raise ValueError('recorded model attempts exceed frozen ceiling')
    index = 0
    mismatch = None
    def recorded_ask(envelope):
        nonlocal index, mismatch
        if index >= len(attempts):
            mismatch = 'replay requested an unrecorded model attempt'
            raise RuntimeError(mismatch)
        attempt = attempts[index]
        index += 1
        if attempt.get('envelope') != envelope or attempt.get('envelope_sha256') != digest(envelope):
            mismatch = f'model envelope differs at attempt {index}'
            raise RuntimeError(mismatch)
        if str(attempt.get('error') or '').startswith('adapter_failure:'):
            raise RuntimeError('recorded provider failure, replayed without network')
        return attempt.get('raw')

    with tempfile.TemporaryDirectory(prefix='client-study-replay-', dir=output.parent) as folder:
        replay_output = Path(folder)
        for name in ('protocol.json', 'prepared-tasks.json', 'runtime-source.zip'):
            shutil.copyfile(output/name, replay_output/name)
        repeated = execute_study(replay_output, recorded_ask)
    if mismatch is not None:
        raise ValueError(mismatch)
    if index != len(attempts):
        raise ValueError('recorded model attempt was not replayed')
    expected = _scientific_state(frozen)
    actual = _scientific_state(repeated)
    if expected != actual:
        raise ValueError('offline rerun differs from frozen scientific state')
    native_probes = sum(run.get('valid_probes', 0) for run in frozen.get('development_runs', []))
    native_probes += sum(run.get('valid_probes', 0)
                         for arms in frozen.get('targets', {}).values()
                         for run in arms.values() if isinstance(run, dict))
    return {'schema': 'zenith_client_investigation_replay_v1',
            'frozen_sha256': digest(frozen), 'status': 'exact' if frozen['complete'] else 'partial_exact',
            'model_attempts_replayed': index,
            'native_probes_replayed': native_probes,
            'scientific_state_sha256': digest(expected),
            'network_calls': 0}


def provider_callback(output: str | Path, protocol: dict, *, env_file: str | None = None):
    """Bind the existing paid provider/budget; returned callback makes no call yet."""
    from zenith.budgeted import OpenRouterBudgetedProvider
    if env_file:
        from system.lib.openrouter_free_runtime import load_env_file
        load_env_file(Path(env_file))
    output = Path(output).resolve()
    provider = OpenRouterBudgetedProvider(
        output/'providers'/'client-study', protocol['model'],
        protocol['max_cost_usd'], protocol['max_calls'],
        protocol['max_output_tokens'], output/'budget',
        provider_slug=protocol['provider_slug'], inference_mode='bounded')

    def ask(envelope):
        prompt = envelope['prompt']
        task = prompt.get('public_task', {}).get('id', 'all')
        node = '-'.join(str(value) for value in (
            envelope['phase'], envelope.get('kind', envelope.get('arm', '')), task,
            envelope.get('turn', 1)))
        write_json(output/'prompts'/f'{node}.json', envelope)
        raw = provider.ask_ai(json.dumps(prompt, ensure_ascii=False), {
            'meta': {'session_id': provider.run_dir.name, 'node_id': node},
            'system_prompt': envelope['system'],
            'reasoning_effort': protocol['reasoning_effort'],
            'response_format': {'type': 'json_schema', 'json_schema': {
                'name': 'client_investigation', 'strict': True,
                'schema': envelope['response_schema']}}})
        write_json(output/'responses'/f'{node}.json',
                   {'raw': raw, 'envelope_sha256': digest(envelope)})
        return raw
    return ask


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    prep = commands.add_parser('prepare')
    prep.add_argument('output')
    prep.add_argument('--model', required=True)
    prep.add_argument('--provider-slug', required=True)
    prep.add_argument('--reasoning-effort', default='low')
    prep.add_argument('--max-cost-usd', default='2')
    prep.add_argument('--max-output-tokens', type=int, default=8192)
    prep.add_argument('--prompt-version', choices=PROMPT_VERSIONS, default='v2')
    prep.add_argument('--model-evidence', required=True,
                      help='JSON file of checked current official model/endpoint/pricing metadata')
    run = commands.add_parser('run')
    run.add_argument('output')
    run.add_argument('--env-file')
    panel = commands.add_parser('open-panel')
    panel.add_argument('output')
    replay = commands.add_parser('replay')
    replay.add_argument('output')
    args = parser.parse_args()
    if args.command == 'prepare':
        result = prepare_study(args.output, model=args.model,
                               provider_slug=args.provider_slug,
                               reasoning_effort=args.reasoning_effort,
                               max_cost_usd=args.max_cost_usd,
                               max_output_tokens=args.max_output_tokens,
                               prompt_version=args.prompt_version,
                               model_evidence=json.loads(Path(args.model_evidence).read_text()))
    elif args.command == 'run':
        protocol, _ = verify_study(args.output)
        result = execute_study(args.output,
                               provider_callback(args.output, protocol, env_file=args.env_file))
    elif args.command == 'replay':
        result = replay_study(args.output)
    else:
        result = open_panel(args.output)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
