"""A bounded direct-query alternative for a NEW conformance protocol.

No provider, credentials, automatic retry, parent repair or protected scoring lives
here. The existing experiment owner supplies a metered ask(envelope) callback.
Every dispatched turn and native observation is emitted before the next action.
Original frozen studies must continue using their archived runtimes.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Callable
import hashlib
import json

from research.conformance_study import invoke
from research.native_conformance_tasks import measure, public_task, query_units
from zenith.providers import digest

SYSTEM = '''You are investigating a candidate program, not implementing it.
Return JSON with exactly "queries" (a list of native input objects) and "note"
(a short string or null). Do not return Python, predicted answers, or source/scope/
change fields. The host executes queries and measures both native and candidate
outputs. The native contract below defines the object under test, NOT your reply.
Choose revealing legal inputs from code inspection and evidence. Do not repeat
examples or earlier queries. An empty queries list stops. Notes are unverified
hypotheses: observed evidence takes precedence. The request states your remaining
query allowance. Your note may be null; a long explanation is not required.'''


def response_schema(limit: int) -> dict[str, Any]:
    if type(limit) is not int or not 1 <= limit <= 8:
        raise ValueError('query limit must be an integer in 1..8')
    return {'type': 'object', 'properties': {
        'queries': {'type': 'array', 'maxItems': limit, 'items': {'type': 'object'}},
        'note': {'anyOf': [{'type': 'string', 'maxLength': 500}, {'type': 'null'}]}},
        'required': ['queries', 'note'], 'additionalProperties': False}


def decode(raw: str, limit: int) -> dict[str, Any]:
    """Fail closed: no code-fence stripping, invented JSON or semantic repairs."""
    def pairs(items):
        value = {}
        for k, v in items:
            if k in value:
                raise ValueError('duplicate JSON key')
            value[k] = v
        return value
    def nonfinite(value):
        raise ValueError('non-finite JSON constant')
    if type(raw) is not str or not raw.strip() or len(raw.encode()) > 64000:
        raise ValueError('delivery must be nonempty JSON within 64000 bytes')
    result = json.loads(raw, object_pairs_hook=pairs, parse_constant=nonfinite)
    if type(result) is not dict or set(result) != {'queries', 'note'}:
        raise ValueError('reply requires exactly queries and note')
    queries, note = result['queries'], result['note']
    if type(queries) is not list or len(queries) > limit or any(type(q) is not dict for q in queries):
        raise ValueError('queries must be a bounded list of objects')
    if note is not None and (type(note) is not str or len(note) > 500 or len(note.encode()) > 2048):
        raise ValueError('note must be null or at most 500 characters / 2048 bytes')
    # Also reject overflowing numeric literals, which json.loads can map to inf.
    json.dumps(result, allow_nan=False)
    return result


def public_context(task: dict, parent: dict) -> dict:
    """Explicit allowlist: never serialise a whole task with protected panels."""
    observed = public_task(task)
    # Remove only role directives, not source semantics. Keep original contract
    # in the archived experiment; record this deterministic projection's version.
    contract = observed.pop('contract')
    contract = contract.replace('Implement investigate(context, acquire), returning a JSON\ninteger. No initial program is supplied; author a fresh behavioral model.', '')
    contract = contract.replace('Implement investigate(context, acquire), returning\nthat JSON object.', '')
    contract = contract.replace('Implement investigate(context, acquire).', '')
    contract = contract.replace('No initial program is supplied.', '')
    if 'Implement investigate(context, acquire)' in contract:
        raise ValueError('Unremoved source-implementation instruction in direct context')
    observed['native_contract_not_response_instructions'] = contract
    return {'observed_task': observed, 'candidate_source': parent['source'],
            'candidate_on_examples': deepcopy(parent['development'])}


def run_direct(task: dict, parent: dict, ask: Callable[[dict], str], *,
               turns: int = 2, queries_per_turn: int = 4,
               probe_cap: int = 8, feedback: bool = True,
               on_event: Callable[[dict], None] | None = None,
               call_ids: tuple[str, ...] | None = None) -> dict:
    """Direct batches or closed-loop actions under the existing native contract.

    feedback=False masks native/parent outcomes in subsequent decision prompts
    while retaining prior chosen inputs and delivery errors. This is an equal-
    opportunity open-loop control, not a claim that missing feedback is ideal.
    With turns=1 and queries_per_turn=8 this is the no-extra-call batch arm.
    The caller MUST persist each on_event snapshot before continuing; returning
    only the final value is insufficient if the process is interrupted. The
    caller reserves/pays model calls via the existing provider.
    """
    if type(turns) is not int or not 1 <= turns <= 8:
        raise ValueError('turns must be in 1..8')
    if type(probe_cap) is not int or not 1 <= probe_cap <= 8:
        raise ValueError('probe_cap must be in 1..8')
    response_schema(queries_per_turn)
    if type(feedback) is not bool:
        raise ValueError('feedback must be Boolean')
    if call_ids is not None and (len(call_ids) != turns or
            any(type(value) is not str or not value for value in call_ids)):
        raise ValueError('call_ids must identify each planned turn')
    receipts, calls = [], []
    seen = {digest(row['input']) for row in task['examples']}
    native_probes = query_attempts = work_units = 0
    slots = 0
    detection = None
    halted = None
    common = public_context(task, parent)
    def snapshot():
        state = {'receipts': deepcopy(receipts), 'turns': deepcopy(calls),
                 'model_turn_attempts': len(calls), 'native_probes': native_probes,
                 'query_attempts': query_attempts, 'query_units': work_units,
                 'slots_used': slots, 'halted': halted}
        if on_event is not None:
            on_event(state)

    for turn in range(turns):
        if slots >= probe_cap or detection is not None:
            break
        limit = min(queries_per_turn, probe_cap - slots)
        visible = deepcopy(receipts) if feedback else [
            {k: deepcopy(v) for k, v in r.items() if k in ('slot', 'turn', 'query')}
            for r in receipts]
        prompt = {**deepcopy(common), 'turn': turn + 1,
                  'remaining_slots': probe_cap - slots, 'max_queries_this_turn': limit,
                  'receipts': visible, 'outcomes_available': feedback and turn > 0,
                  'earlier_delivery_errors': [r['delivery_error'] for r in calls if r.get('delivery_error')],
                  'response_example': {'queries': [], 'note': None}}
        envelope = {'prompt': prompt, 'system': SYSTEM, 'response_schema': response_schema(limit)}
        call = {'turn': turn + 1, 'envelope': deepcopy(envelope),
                'envelope_sha256': digest(envelope), 'raw': None, 'delivery_error': None}
        if call_ids is not None:
            call['call_id'] = call_ids[turn]
        calls.append(call)  # Attempt is retained even if the adapter raises.
        snapshot()
        try:
            raw = ask(deepcopy(envelope))
        except Exception as exc:
            call['delivery_error'] = f'{type(exc).__name__}: {exc}'[:500]
            halted = 'adapter_failure'
            snapshot()
            break  # No automatic paid retry or substitution.
        call['raw'] = raw
        if isinstance(raw, str):
            call['raw_sha256'] = hashlib.sha256(raw.encode()).hexdigest()
        snapshot()
        try:
            reply = decode(raw, limit)
        except (ValueError, TypeError, RecursionError) as exc:
            call['delivery_error'] = f'{type(exc).__name__}: {exc}'[:500]
            halted = 'invalid_delivery'
            snapshot()
            break
        call['action'] = deepcopy(reply)
        snapshot()
        if not reply['queries']:
            call['stopped'] = True
            snapshot()
            break
        for query in reply['queries']:
            slots += 1
            row = {'slot': slots, 'turn': turn + 1, 'query': deepcopy(query), 'note': reply['note']}
            receipts.append(row)
            identity = digest(query)
            if identity in seen:
                row['query_error'] = 'Duplicate of an example or earlier query; slot consumed.'
                snapshot()
                continue
            seen.add(identity)
            query_attempts += 1
            try:
                if len(json.dumps(query, ensure_ascii=True, allow_nan=False).encode()) > 16000:
                    raise ValueError('Query exceeds 16000 serialized bytes.')
                expected = measure(task['source_id'], query)
                units = query_units(query)
            except (ValueError, TypeError, KeyError, OverflowError) as exc:
                row['query_error'] = f'{type(exc).__name__}: {exc}'[:500]
                snapshot()
                continue
            native_probes += 1
            work_units += units
            actual = invoke(parent['source'], query)
            wrong = actual['error'] is not None or digest(actual['answer']) != digest(expected)
            row.update(expected=expected, parent_answer=actual['answer'],
                       parent_error=actual['error'], verified_counterexample=wrong, query_units=units)
            snapshot()
            if wrong:
                detection = row
                break
    return {'receipts': receipts, 'turns': calls, 'model_turn_attempts': len(calls),
            'native_probes': native_probes, 'query_attempts': query_attempts,
            'query_units': work_units, 'policy_executions': 0,
            'invalid_query_attempts': sum('query_error' in row and
                not row['query_error'].startswith('Duplicate') for row in receipts),
            'slots_used': slots,
            'detected': detection is not None,
            'semantic_defect': detection is not None and detection['parent_error'] is None,
            'technical_defect': detection is not None and detection['parent_error'] is not None,
            'witness_sha256': digest(detection) if detection else None, 'halted': halted,
            'feedback': feedback,
            'boundary': 'Source work excludes partial work of dynamically illegal queries; attempts remain counted.'}


def repair_account(parent: dict, candidate: dict, selected: dict) -> dict:
    """Separate candidate changes from the actually retained programme.

    Takes selected_candidate(...) from the existing conformance owner. This is
    reporting only: it neither changes incumbent selection nor invents a retry.
    """
    before = selected['parent_on_final_evidence']['rows']
    after = selected['candidate_on_final_evidence']['rows']
    if len(before) != len(after):
        raise ValueError('repair evidence rows must align')
    retained = selected['development']['rows']
    if len(retained) != len(before):
        raise ValueError('selected repair evidence rows must align')
    def changes(rows):
        remaining, corrected, regressed = [], [], []
        for old, new in zip(before, rows, strict=True):
            if digest(old['input']) != digest(new['input']) or digest(old['expected']) != digest(new['expected']):
                raise ValueError('repair evidence identity mismatch')
            identity = digest({'input': old['input'], 'expected': old['expected']})
            if not new['correct']: remaining.append(identity)
            if not old['correct'] and new['correct']: corrected.append(identity)
            if old['correct'] and not new['correct']: regressed.append(identity)
        return corrected, remaining, regressed
    candidate_corrected, candidate_remaining, candidate_regressed = changes(after)
    selected_corrected, selected_remaining, selected_regressed = changes(retained)
    unchanged = parent['source'] == selected['source']
    return {'candidate_byte_identical': parent['source'] == candidate['source'],
            'candidate_corrected_obligations': candidate_corrected,
            'candidate_remaining_obligations': candidate_remaining,
            'candidate_regressed_obligations': candidate_regressed,
            'selected_byte_identical': unchanged,
            'selected_corrected_obligations': selected_corrected,
            'selected_remaining_obligations': selected_remaining,
            'selected_regressed_obligations': selected_regressed,
            'candidate_selected': selected['candidate_selected'],
            'status': 'unchanged_with_known_failure' if unchanged and selected_remaining else
                      'observed_failures_remain' if selected_remaining else 'observed_set_satisfied',
            'boundary': 'Status concerns the retained programme on measured obligations only.'}
