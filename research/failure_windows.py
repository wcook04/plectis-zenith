"""Source-bound Oracle hypotheses across overlapping windows; never promotion.

The public taxonomy remains owned by schema_cp2_critique.json. This module adds the
orthogonal evidence-availability axis and an optional, reviewed node location.
Recorded bytes establish provenance, not causal correctness of an annotation.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from research.diagnosis import _digest, _packet, _read, observe_run
from system.lib.schema_validator import validate_cp2_critique

ROOT = Path(__file__).resolve().parents[1]
STATES = {'unknown', 'in_node_context', 'in_universe_not_context',
          'outside_universe_pre_cutoff', 'post_cutoff'}


def _time(value):
    if not isinstance(value, str):
        raise ValueError('Timestamp must be an ISO string')
    result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if result.tzinfo is None:
        raise ValueError('Explicit timezone required')
    return result.astimezone(timezone.utc)


def _load(path, root):
    value, ref, error = _read(path, root)
    if error:
        raise ValueError(f'{path}: {error}')
    return value, ref


def _artifact(run, manifest, name):
    value, ref = _load(run / 'artifacts' / (name + '.json'), run)
    metadata = value.get('metadata', {})
    if not isinstance(metadata, dict):
        raise ValueError(f'{name}: invalid artifact metadata')
    owner = metadata.get('artifact_alias_of', name)
    if (value.get('id') != name or owner not in manifest['node_hashes']
            or value.get('node_hash') != manifest['node_hashes'][owner]
            or value.get('status') not in {'success', 'loaded'}
            or 'data' not in value):
        raise ValueError(f'{name}: artifact does not bind to a successful declared node')
    return value['data'], ref


def _manifest(run, mission):
    value, ref = _load(run / 'zenith_run.json', run)
    if (value.get('schema') != 'zenith_execution_manifest_v1'
            or value.get('mission') != mission or value.get('run_id') != run.name
            or not isinstance(value.get('node_hashes'), dict) or not value['node_hashes']):
        raise ValueError(f'Invalid {mission} manifest')
    return value, ref


def observe_pair(oracle_run):
    """Read the original quartet and manifests; leave absent evidence unresolved."""
    oracle = Path(oracle_run).resolve()
    om, oref = _manifest(oracle, 'oracle')
    subject = Path(om['subject_run']).resolve()
    sm, sref = _manifest(subject, 'lab')
    start, end = _time(sm['time_anchor']), _time(sm['horizon'])
    if not start < end or start != _time(om['time_anchor']) or end != _time(om['horizon']):
        raise ValueError('Oracle and Lab must share the frozen issue time and horizon')
    # Rerun attempts and alternate Oracle narratives about one forecast are one
    # episode, not independent evidence. Different graphs remain separate strata.
    graph = _digest({k: sm.get(k) for k in ('node_hashes', 'reasoning_policy',
                    'context_profile', 'provider', 'model', 'implementation_hashes')})
    inputs = sorted(_digest(v) for v in sm.get('source_hashes', {}).values())
    episode = {'episode_id': _digest([graph, inputs, start.isoformat(), end.isoformat()]),
               'subject_run': str(subject), 'oracle_run': str(oracle), 'graph_id': graph,
               'start': start.isoformat(), 'end': end.isoformat(),
               'manifest_refs': [sref, oref], 'cases': [], 'status': 'unresolved',
               'runtime_observations': observe_run(subject), 'problems': []}
    try:
        # Check the subject bytes that Oracle actually froze, not today's graph.
        frozen = om.get('source_hashes', {}).get(str(subject))
        if not isinstance(frozen, dict) or not frozen:
            raise ValueError('Oracle has no frozen subject source hashes')
        for name, expected in frozen.items():
            _, ref = _load(subject / name, subject)
            if ref['sha256'] != expected:
                raise ValueError(f'Frozen subject changed: {name}')
        reconciliation, rref = _artifact(oracle, om, 'prediction_reconciliation')
        if not isinstance(reconciliation, dict) or not isinstance(reconciliation.get('feed_health'), dict):
            raise ValueError('Reconciliation or feed health is not an object')
        if reconciliation.get('subject_run_id') != subject.name:
            raise ValueError('Reconciliation belongs to a different subject')
        episode['reconciliation_ref'] = rref
        episode['feed_health'] = reconciliation.get('feed_health', {}).get('status', 'UNKNOWN')
        if episode['feed_health'] == 'ABSTAINED':
            episode['status'] = 'abstained'
            return episode
        if episode['feed_health'] != 'READY':
            episode['status'] = 'data_gap'
            return episode
        critique, cref = _artifact(oracle, om, 'cp2_critique')
        validation = validate_cp2_critique(critique)
        if not validation.ok:
            raise ValueError('Invalid native critique: ' + '; '.join(validation.errors))
        index, iref = _artifact(oracle, om, 'oracle_subject_index')
        if not isinstance(index, dict):
            raise ValueError('Subject index is not an object')
        if index.get('subject_run_id') != subject.name:
            raise ValueError('Subject index belongs to a different subject')
        eligible = set(index.get('eligible_ledger_ids', []))
        # Native critiques may use either ledger IDs or CP2 display references.
        eligible.update(row['ref_id'] for row in index.get('evidence_dictionary', [])
                        if isinstance(row, dict) and row.get('ledger_id') in eligible
                        and isinstance(row.get('ref_id'), str))
        taxonomy, _ = _load(ROOT / 'codex/substrate/contracts/schema_cp2_critique.json', ROOT)
        classes = taxonomy['critique_item']['error_class']['enum']
        items = critique.get('critique_items')
        if not isinstance(items, list):
            raise ValueError('Missing critique items')
        if not items:
            review = critique.get('no_findings_review', {})
            if (critique.get('finding_status') != 'NO_FINDINGS'
                    or not review.get('review_summary') or not review.get('realized_refs')
                    or not review.get('subject_grounding_refs')
                    or not set(review['subject_grounding_refs']) <= eligible):
                raise ValueError('Empty critique is not an evidence-bound NO_FINDINGS review')
            episode['status'] = 'reviewed_no_findings'
            episode['no_findings_review'] = review
        else:
            for number, item in enumerate(items):
                if (not isinstance(item, dict) or item.get('error_class') not in classes
                        or not item.get('what_was_wrong') or not item.get('realized_refs')
                        or not isinstance(item.get('subject_grounding_refs'), list)
                        or not set(item['subject_grounding_refs']) <= eligible):
                    raise ValueError(f'Critique item {number} has invalid class or grounding')
                episode['cases'].append({'case_id': _digest([episode['episode_id'], cref['sha256'], number]),
                    'error_class': item['error_class'], 'scope': item.get('scope'),
                    'target_or_claim': item.get('target_or_claim'), 'oracle_hypothesis': item['what_was_wrong'],
                    'subject_grounding_refs': item['subject_grounding_refs'], 'realized_refs': item['realized_refs'],
                    'critique_ref': dict(cref, pointer=f'/data/critique_items/{number}'),
                    'subject_index_ref': iref, 'evidence_state': 'unknown', 'node_id': None,
                    'mechanism': None, 'attribution_status': 'unlocalized_hypothesis'})
            episode['status'] = 'hypotheses_recorded'
    except (ValueError, KeyError, TypeError) as exc:
        episode['cases'] = []
        episode['problems'].append(str(exc))
    return episode


def _pointer(value, pointer):
    if not isinstance(pointer, str) or not pointer.startswith('/'):
        raise ValueError('Use an explicit RFC6901 pointer')
    for part in pointer[1:].split('/'):
        part = part.replace('~1', '/').replace('~0', '~')
        if isinstance(value, list):
            if not part.isdecimal() or str(int(part)) != part:
                raise ValueError('Invalid array index')
            value = value[int(part)]
        else:
            value = value[part]
    return value


def annotate(episode, case, annotation):
    """Verify observations and node bindings; keep semantic judgments as hypotheses."""
    required = {'case_id', 'node_id', 'evidence_state', 'mechanism', 'rationale', 'reviewer', 'citations'}
    if set(annotation) != required or annotation['evidence_state'] not in STATES:
        raise ValueError('Invalid annotation fields or evidence state')
    for key in ('mechanism', 'rationale', 'reviewer'):
        if not isinstance(annotation[key], str) or not annotation[key].strip():
            raise ValueError(f'Annotation requires {key}')
    root = Path(episode['subject_run'])
    manifest, _ = _manifest(root, 'lab')
    node = annotation['node_id']
    if node not in manifest['node_hashes'] or not annotation['citations']:
        raise ValueError('Annotation requires a recorded node and citations')
    roles = set()
    for citation in annotation['citations']:
        if not isinstance(citation, dict):
            raise ValueError('Citation must be an object')
        role = citation.get('role')
        path = Path(citation['path']).resolve()
        if role not in {'subject', 'node_input', 'node_output', 'external'}:
            raise ValueError('Unknown citation role')
        value, ref = _load(path, path.parent if role == 'external' else root)
        if citation.get('sha256') != ref['sha256']:
            raise ValueError('Citation source bytes changed')
        observationd = _pointer(value, citation['pointer'])
        if _digest(observationd) != _digest(citation['value']):
            raise ValueError('Citation observation does not match source')
        if role == 'node_input':
            if path.parent != root / 'handoff/requests' or not _packet(value, path, manifest) or value['node_id'] != node:
                raise ValueError('Input is not a prompt-bound request for this node')
            if citation['pointer'] != '/prompt':
                raise ValueError('Cite the complete input prompt for an availability review')
        elif role in {'subject', 'node_output'}:
            if path.parent != root / 'artifacts':
                raise ValueError('Subject evidence must be a recorded subject artifact')
            _artifact(root, manifest, path.stem)
            if citation['pointer'] != '/data' and not citation['pointer'].startswith('/data/'):
                raise ValueError('Cite artifact data, not metadata')
            if role == 'node_output' and path.stem != node:
                raise ValueError('Output is not from the named node')
        else:
            available = _time(citation['available_at'])
            if annotation['evidence_state'] == 'outside_universe_pre_cutoff' and available > _time(episode['start']):
                raise ValueError('Later information cannot be pre-cutoff external evidence')
            if annotation['evidence_state'] == 'post_cutoff' and available <= _time(episode['start']):
                raise ValueError('Post-cutoff information requires a later availability time')
        roles.add(role)
    needed = {'node_input', 'node_output'}
    state = annotation['evidence_state']
    if state in {'in_node_context', 'in_universe_not_context'}:
        needed.add('subject')
    if state in {'outside_universe_pre_cutoff', 'post_cutoff'}:
        needed.add('external')
    if not needed <= roles:
        raise ValueError(f'Availability review needs citation roles: {sorted(needed)}')
    case.update({k: annotation[k] for k in ('node_id', 'evidence_state', 'mechanism', 'rationale', 'reviewer', 'citations')})
    case['attribution_status'] = 'source_bound_reviewed_hypothesis'


def _groups(episodes):
    groups = defaultdict(list)
    for episode in episodes:
        for case in episode['cases']:
            key = (case['error_class'], case['scope'], case['node_id'], case['evidence_state'], case['mechanism'])
            groups[key].append((episode, case))
    result = []
    for key, members in groups.items():
        unique = {e['episode_id']: e for e, _ in members}
        # Maximum disjoint intervals, not a statistical independence claim.
        selected, previous_end = [], None
        for e in sorted(unique.values(), key=lambda x: (x['end'], x['start'])):
            if previous_end is None or _time(e['start']) >= previous_end:
                selected.append(e['episode_id'])
                previous_end = _time(e['end'])
        result.append(dict(zip(('error_class', 'scope', 'node_id', 'evidence_state', 'mechanism'), key),
            case_count=len(members), episode_count=len(unique), nonoverlapping_episode_count=len(selected),
            nonoverlapping_episode_ids=selected, case_ids=[c['case_id'] for _, c in members]))
    return sorted(result, key=lambda r: (-r['nonoverlapping_episode_count'], -r['episode_count'],
                                       _digest(r['case_ids'])))


def diagnose(oracle_runs, widths=(1, 2, 5), stride=1, annotations=()):
    """Windows are consecutive forecast origins within each recorded graph.

    Forecast horizons stay exactly as issued. Width never relabels a one-day
    forecast as a five-day forecast. Overlap is descriptive, not extra samples.
    """
    if (not widths or any(type(w) is not int or w < 1 for w in widths)
            or type(stride) is not int or stride < 1):
        raise ValueError('Widths and stride must be positive integers')
    if not oracle_runs:
        raise ValueError('At least one explicit Oracle run required')
    episodes = [observe_pair(p) for p in oracle_runs]
    if len({e['episode_id'] for e in episodes}) != len(episodes):
        raise ValueError('Duplicate forecast episode; select one Oracle review per subject/horizon')
    cases = {c['case_id']: (e, c) for e in episodes for c in e['cases']}
    seen = set()
    for annotation in annotations:
        key = annotation['case_id']
        if key not in cases or key in seen:
            raise ValueError('Unknown or duplicate annotation case_id')
        seen.add(key)
        annotate(*cases[key], annotation)
    strata = defaultdict(list)
    for episode in episodes:
        strata[episode['graph_id']].append(episode)
    reports = []
    for graph, rows in sorted(strata.items()):
        rows.sort(key=lambda e: (e['start'], e['end'], e['episode_id']))
        windows = []
        for width in sorted(set(widths)):
            for start in range(0, len(rows) - width + 1, stride):
                selected = rows[start:start+width]
                windows.append({'width': width, 'offset': start,
                    'episode_ids': [e['episode_id'] for e in selected],
                    'unresolved_episode_count': sum(e['status'] in {'unresolved', 'data_gap'} for e in selected),
                    'failure_groups': _groups(selected)})
        ranking = _groups(rows)
        candidates = [r for r in ranking if r['node_id'] and r['mechanism']
                      and r['evidence_state'] in {'in_node_context', 'in_universe_not_context'}
                      and r['nonoverlapping_episode_count'] >= 2]
        statuses = {status: sum(e['status'] == status for e in rows) for status in
                    ('hypotheses_recorded', 'reviewed_no_findings', 'abstained', 'data_gap', 'unresolved')}
        reports.append({'graph_id': graph, 'episode_count': len(rows), 'episode_status_counts': statuses,
            'windows': windows,
            'unsupported_widths': [w for w in sorted(set(widths)) if w > len(rows)],
            'aggregate': ranking, 'next_intervention_hypothesis': candidates[0] if candidates else None})
    return {'schema': 'zenith_failure_windows_v1', 'episodes': episodes, 'strata': reports,
            'promotion_authorized': False,
            'boundary': 'Oracle classes and reviewed locations are hypotheses. Quotes verify recorded bytes, '
            'not semantic attribution, historical availability or causality. Missing information stays unknown. '
            'Nonoverlapping horizons are not necessarily statistically independent. Windows reuse cases. '
            'A repeated localized hypothesis proposes an intervention; only a separate later matched '
            'comparison can support retaining it. No universal improvement claim follows from this report.'}
