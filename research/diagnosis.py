"""Read-only mechanical observations; no acceptance, inference or causal verdicts."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import re

MAX_BYTES = 8 * 1024 * 1024
MAX_FILES = 128
SAFE_ID = re.compile(r'[A-Za-z0-9][A-Za-z0-9_-]{0,119}\Z')
SHA = re.compile(r'[0-9a-f]{64}\Z')


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                    ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate JSON key')
        result[key] = value
    return result


def _read(path, root):
    ref = {'path': str(path), 'sha256': None}
    try:
        if not path.resolve().is_relative_to(root):
            return None, ref, 'outside_run'
        with path.open('rb') as stream:
            raw = stream.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            return None, ref, 'size_limit'
        ref['sha256'] = hashlib.sha256(raw).hexdigest()
        value = json.loads(raw, object_pairs_hook=_pairs,
                           parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite JSON')))
        if not isinstance(value, dict):
            raise ValueError('JSON object required')
        # Escaped lone surrogates parse as JSON but cannot bind native UTF-8 hashes.
        json.dumps(value, ensure_ascii=False, allow_nan=False).encode('utf-8')
        return value, ref, None
    except FileNotFoundError:
        return None, ref, 'missing'
    except (OSError, ValueError, UnicodeError, RuntimeError):
        return None, ref, 'unreadable_or_malformed'


def _files(folder, root, emit):
    try:
        if not folder.resolve().is_relative_to(root):
            raise ValueError('outside_run')
        paths = sorted(folder.glob('*.json'))
        if len(paths) > MAX_FILES:
            emit('observability_unknown', details={'reason': 'file_limit', 'folder': str(folder)})
        return paths[:MAX_FILES]
    except (OSError, ValueError, RuntimeError):
        emit('observability_unknown', details={'reason': 'unreadable_folder', 'folder': str(folder)})
        return []


def _packet(value, path, manifest):
    identity = {key: value.get(key) for key in ('run_id', 'node_id', 'prompt_sha256')}
    return (value.get('schema') == 'zenith_agent_packet_v1'
            and identity['run_id'] == manifest['run_id'] and isinstance(identity['node_id'], str)
            and identity['node_id'] in manifest['scope']
            and isinstance(value.get('prompt'), str)
            and hashlib.sha256(value['prompt'].encode()).hexdigest() == identity['prompt_sha256']
            and value.get('packet_id') == path.stem == _digest(identity))


def _response(value, packet):
    return (all(value.get(k) == packet.get(k) for k in ('packet_id', 'run_id', 'node_id', 'prompt_sha256'))
            and isinstance(value.get('response_text'), str) and bool(value['response_text'].strip()))


def _policy_receipt(value, path, manifest):
    policy = manifest.get('reasoning_policy')
    node = value.get('node_id')
    if not isinstance(policy, dict) or not isinstance(policy.get('nodes'), dict):
        return False
    row = policy['nodes'].get(node)
    if not isinstance(row, dict) or node not in manifest['scope']:
        return False
    if (not isinstance(policy.get('variant_id'), str) or not policy['variant_id'].strip()
            or set(row) - {'skill_addon', 'incoming_weights', 'max_context_chars'}
            or not isinstance(row.get('skill_addon', ''), str) or len(row.get('skill_addon', '')) > 512
            or not isinstance(row.get('incoming_weights', {}), dict)
            or ('max_context_chars' in row and (type(row['max_context_chars']) is not int or row['max_context_chars'] < 256))):
        return False
    for dependency, weight in row.get('incoming_weights', {}).items():
        if (dependency not in manifest['scope'] or type(weight) not in (int, float)
                or not math.isfinite(weight) or weight < 0):
            return False
    if (set(policy) != {'nodes', 'variant_id', 'policy_sha256'}
            or policy['policy_sha256'] != _digest({k: v for k, v in policy.items() if k != 'policy_sha256'})
            or value.get('schema_version') != 'zenith_context_policy_receipt_v1'
            or value.get('policy_sha256') != policy['policy_sha256']
            or value.get('variant_id') != policy['variant_id']
            or value.get('receipt_sha256') != _digest({k: v for k, v in value.items() if k != 'receipt_sha256'})
            or path.stem != node + '.' + value['receipt_sha256']
            or value.get('max_context_chars') != row.get('max_context_chars')
            or value.get('skill_addon_sha256') != hashlib.sha256(row.get('skill_addon', '').encode()).hexdigest()):
        return False
    edges, missing = value.get('incoming_edges'), value.get('missing_dependency_ids')
    if not isinstance(edges, list) or not isinstance(missing, list):
        return False
    ids = [edge.get('dependency_id') for edge in edges if isinstance(edge, dict)]
    if (len(ids) != len(edges) or any(not isinstance(k, str) or k not in manifest['scope'] for k in ids + missing)
            or len(set(ids)) != len(ids) or len(set(missing)) != len(missing) or set(ids) & set(missing)):
        return False
    kept = 0
    for edge in edges:
        original, retained, weight = edge.get('original_chars'), edge.get('retained_source_chars'), edge.get('weight')
        if (type(original) is not int or type(retained) is not int or not 0 <= retained <= original
                or type(weight) not in (int, float) or not math.isfinite(weight) or weight < 0
                or weight != row.get('incoming_weights', {}).get(edge['dependency_id'], 1)
                or not isinstance(edge.get('original_sha256'), str) or not SHA.fullmatch(edge['original_sha256'])):
            return False
        expected = 'omitted' if weight == 0 else 'full' if retained == original else 'excerpt'
        if edge.get('view') != expected or (weight == 0 and retained != 0):
            return False
        kept += retained
    return (type(value.get('retained_source_chars')) is int and value['retained_source_chars'] == kept
            and (row.get('max_context_chars') is None or kept <= row['max_context_chars'])
            and all(value.get(field) == [e['dependency_id'] for e in edges if e['view'] == view]
                    for field, view in [('omitted_dependency_ids', 'omitted'), ('excerpt_dependency_ids', 'excerpt')]))


def observe_run(run: str | Path) -> dict:
    """Project recorded facts, including absent runs, without changing any substrate.

    Receipt verification checks internal hashes and declared manifest/policy
    binding. It does not independently certify source code, node ancestry, actual
    input consumption, model identity, engine execution or forecast accuracy.
    """
    result = {'schema': 'zenith_run_diagnosis_v1', 'status': 'unknown', 'run_path': None,
              'manifest_ref': None, 'observations': [], 'causal_claims': False,
              'verification_boundary': 'Recorded bytes and declared manifest/policy binding only; '
              'no independent execution, input-consumption, model, accuracy or causal certification.'}

    def emit(code, node_id=None, source_ref=None, details=None, verification='recorded_bytes'):
        result['observations'].append({'code': code, 'node_id': node_id, 'source_ref': source_ref,
                                       'details': details or {}, 'verification': verification})

    try:
        root = Path(run).resolve()
    except (OSError, TypeError, ValueError, RuntimeError):
        emit('observability_unknown', details={'reason': 'invalid_run_path'}, verification='none')
        return result
    result['run_path'] = str(root)
    manifest, ref, problem = _read(root / 'zenith_run.json', root)
    result['manifest_ref'] = ref
    if problem:
        result['status'] = 'missing' if problem == 'missing' else 'unknown'
        emit('manifest_missing' if problem == 'missing' else 'observability_unknown', source_ref=ref,
             details={'reason': problem}, verification='filesystem_presence' if problem == 'missing' else 'none')
        return result
    scope, hashes = manifest.get('scope'), manifest.get('node_hashes')
    if (manifest.get('schema') != 'zenith_execution_manifest_v1' or manifest.get('mission') != 'lab'
            or manifest.get('run_id') != root.name or not isinstance(scope, list) or not 0 < len(scope) <= 512
            or any(not isinstance(k, str) or not SAFE_ID.fullmatch(k) for k in scope)
            or len(set(scope)) != len(scope) or not isinstance(hashes, dict) or set(hashes) != set(scope)
            or any(not isinstance(v, str) or not SHA.fullmatch(v) for v in hashes.values())):
        emit('observability_unknown', source_ref=ref, details={'reason': 'manifest_binding'}, verification='none')
        return result
    result['status'] = 'observed'
    completed = set()
    for node in scope:
        artifact, source, problem = _read(root / 'artifacts' / (node + '.json'), root)
        if problem:
            emit('node_artifact_absent' if problem == 'missing' else 'observability_unknown', node, source,
                 {'reason': problem}, 'manifest_scope_and_presence' if problem == 'missing' else 'none')
            continue
        meta = artifact.get('metadata', {})
        if (artifact.get('id') != node or artifact.get('node_hash') != hashes[node] or not isinstance(meta, dict)
                or artifact.get('status') not in ('success', 'loaded', 'failure', 'pending', 'running', 'cancelled', 'not_started')
                or ('error' in meta and not isinstance(meta['error'], str))
                or ('validation_errors' in meta and (not isinstance(meta['validation_errors'], list)
                    or any(not isinstance(v, str) for v in meta['validation_errors'])))):
            emit('observability_unknown', node, source, {'reason': 'artifact_binding'}, 'none')
            continue
        status = artifact['status']
        emit('node_artifact_present', node, source, {'recorded_status': status}, 'manifest_node_hash_binding')
        if status in ('success', 'loaded'):
            completed.add(node)
        elif status == 'failure' and not str(meta.get('error', '')).startswith('Agent response pending:'):
            emit('node_failure_recorded', node, source, {'error': str(meta.get('error', ''))[:1200]}, 'manifest_node_hash_binding')
        if meta.get('validation_errors'):
            emit('output_validation_rejected', node, source, {'errors': meta['validation_errors']}, 'manifest_node_hash_binding')
    for path in _files(root / 'handoff/requests', root, emit):
        packet, source, problem = _read(path, root)
        try:
            verified = not problem and _packet(packet, path, manifest)
        except (TypeError, ValueError, OverflowError):
            verified = False
        if not verified:
            emit('observability_unknown', source_ref=source, details={'reason': problem or 'packet_binding'}, verification='none')
            continue
        node = packet['node_id']
        answer, answer_ref, problem = _read(root / 'handoff/responses' / path.name, root)
        if problem == 'missing':
            if node not in completed:
                emit('agent_response_pending', node, source, {'response_ref': answer_ref}, 'verified_packet_and_presence')
            continue
        if problem or not _response(answer, packet):
            emit('observability_unknown', node, answer_ref, {'reason': problem or 'response_binding'}, 'none')
            continue
        validation, vref, problem = _read(root / 'handoff/validation' / path.name, root)
        if problem:
            emit('observability_unknown', node, vref, {'reason': 'validation_' + problem}, 'none')
            continue
        expected = {'schema': 'zenith_import_validation_v1', 'packet_id': packet['packet_id'],
                    'run_id': manifest['run_id'], 'node_id': node,
                    'response_sha256': hashlib.sha256(answer['response_text'].encode()).hexdigest()}
        errors = validation.get('engine_errors', [])
        if (any(validation.get(k) != v for k, v in expected.items()) or type(validation.get('engine_accepted')) is not bool
                or not isinstance(errors, list) or any(not isinstance(e, str) for e in errors)):
            emit('observability_unknown', node, vref, {'reason': 'validation_binding'}, 'none')
        elif not validation['engine_accepted']:
            emit('output_validation_rejected', node, vref, {'errors': validation.get('engine_errors', [])}, 'verified_request_response_validation_binding')
    for path in _files(root / 'artifacts/context_policy', root, emit):
        receipt, source, problem = _read(path, root)
        try:
            verified = not problem and _policy_receipt(receipt, path, manifest)
        except (KeyError, TypeError, ValueError, AttributeError, OverflowError):
            verified = False
        if not verified:
            emit('observability_unknown', source_ref=source, details={'reason': problem or 'context_receipt_binding'}, verification='none')
            continue
        for field, code in [('missing_dependency_ids', 'context_missing_recorded'),
                            ('omitted_dependency_ids', 'context_omitted_recorded'),
                            ('excerpt_dependency_ids', 'context_excerpt_recorded')]:
            if receipt[field]:
                emit(code, receipt['node_id'], source, {'dependency_ids': receipt[field]}, 'receipt_hash_manifest_policy_binding')
    return result
