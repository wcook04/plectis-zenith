"""Compile a reviewed reflection into a new-cohort candidate, without writes or calls."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import re
import sys

from feedback.engine import digest
from research import cohort, reflection
from research.engine import digest_bytes, read_json
from system.lib.hashing import hash_node
from zenith import runtime


def _study_file(study, relative):
    if not isinstance(relative, str) or not relative:
        raise ValueError('frozen cohort path must be a nonempty string')
    path = (study / relative).resolve()
    if not path.is_relative_to(study):
        raise ValueError('frozen cohort path escapes study')
    return path


@reflection._validated
def candidate_fragment(packet, compiled, *, study, policy_path, candidate_id,
                       source_commit, source_candidate_id='baseline'):
    """Return exact cohort fields and separate review provenance for a fresh study.

    ``policy_path`` is an intended output location; it need not exist yet. The
    payload is validated now, and an existing file must match. ``source_commit``
    is explicitly caller-declared provenance, not a verified Git revision.
    Frozen source hashes remain authority. Existing studies are never updated.
    """
    study = Path(study).resolve()
    reflection.validate_packet(packet)
    spec_path, state_path = study / 'cohort.json', study / 'cohort-state.json'
    spec, state = read_json(spec_path), read_json(state_path)
    if spec.get('schema') != cohort.SCHEMA or digest_bytes(spec_path.read_bytes()) != state.get('spec_hash'):
        raise ValueError('frozen cohort specification hash mismatch')
    if spec['authorities'] != cohort.authorities() or spec['python_version'] != sys.version:
        raise ValueError('frozen evaluator/runtime source or Python changed; new freeze required')
    if state.get('final') is not None:
        raise ValueError('heldout final seal consumed; reflection closed')
    for relative, expected in spec['frozen_hashes'].items():
        if digest_bytes(_study_file(study, relative).read_bytes()) != expected:
            raise ValueError('frozen cohort input or candidate changed')

    expected_scope = reflection.scope_from_study(study, packet['scope']['as_of'])
    if packet['scope'] != expected_scope:
        raise ValueError('reflection scope must reference this exact frozen cohort state')
    if not isinstance(candidate_id, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,119}', candidate_id):
        raise ValueError('new candidate_id must be a safe identifier')
    if any(row['candidate_id'] == candidate_id for row in spec['candidates']):
        raise ValueError('new candidate_id must differ from parent candidates')
    if not isinstance(source_commit, str) or not source_commit.strip():
        raise ValueError('explicit nonempty source_commit provenance required')
    source = next((row for row in spec['candidates'] if row['candidate_id'] == source_candidate_id), None)
    if source is None:
        raise ValueError('source candidate must be preregistered in parent cohort')
    proposal = packet['proposal']
    if (proposal.get('actual_model') != source['actual_model']
            or proposal.get('execution_kind') != source['execution_kind']):
        raise ValueError('measured model identity differs from source candidate')

    variant = source['graph_variant_payload']
    graph = runtime.load_graph(runtime.DEFAULT_ROOT, variant)
    if ({key: hash_node(node) for key, node in graph.items()} != source['node_hashes']
            or sorted(runtime.scope_for(graph, 'lab_director')) != source['scope']):
        raise ValueError('full frozen source graph or Lab scope differs')
    for field, payload in (('graph_variant', variant), ('reasoning_policy', source['reasoning_policy_payload'])):
        path = source[field]
        if (path is None) != (payload is None):
            raise ValueError('frozen candidate path and payload disagree')
        if path is not None and read_json(_study_file(study, path)) != payload:
            raise ValueError('frozen candidate payload differs from source file')

    candidate = compiled['candidate']
    change = candidate['change']
    regenerated = reflection.compile_candidate(
        packet, graph=graph, node_id=change['node_id'], parameter=change['parameter'],
        value=change['after'], hypothesis=candidate['hypothesis'], variant_id=candidate['variant_id'],
        edge_id=change['edge_id'], baseline_policy=source['reasoning_policy_payload'])
    if compiled != regenerated:
        raise ValueError('compiled reflection candidate or policy differs from verified change')
    if candidate_id != candidate['variant_id']:
        raise ValueError('candidate_id must match compiled policy variant_id')
    if not isinstance(policy_path, (str, Path)) or not str(policy_path).strip():
        raise ValueError('intended reasoning policy path required')
    policy_path = Path(policy_path).resolve()
    if policy_path.is_relative_to(study):
        raise ValueError('new policy output must be outside frozen parent study')
    if policy_path.exists() and read_json(policy_path) != compiled['reasoning_policy']:
        raise ValueError('existing reasoning policy file differs from compiled payload')

    row = {key: deepcopy(source[key]) for key in (
        'model', 'actual_model', 'provider', 'execution_kind', 'context_profile')}
    row.update(candidate_id=candidate_id, hypothesis=candidate['hypothesis'],
               change=json.dumps(change, sort_keys=True, separators=(',', ':'), allow_nan=False),
               source_commit=source_commit, prompt_sha256=packet['packet_sha256'],
               graph_variant=str(_study_file(study, source['graph_variant'])) if source['graph_variant'] else None,
               reasoning_policy=str(policy_path))
    review = {'schema': 'zenith_reflection_cohort_review_v1', 'state': 'review_only',
              'live_mutation_permission': False, 'new_study_required': True,
              'parent_cohort': str(spec_path), 'parent_spec_sha256': state['spec_hash'],
              'parent_state_sha256': digest_bytes(state_path.read_bytes()),
              'parent_authorities_sha256': digest(spec['authorities']),
              'source_candidate_id': source_candidate_id,
              'packet_sha256': packet['packet_sha256'], 'proposal_id': candidate['proposal_id'],
              'reflection_candidate_sha256': candidate['candidate_sha256'],
              'reasoning_policy_sha256': candidate['reasoning_policy_sha256'],
              'candidate_fragment_sha256': digest(row),
              'source_commit_provenance': 'caller-declared; not a verified Git revision',
              'policy_file_state': 'existing_verified' if policy_path.exists() else 'intended_not_written',
              'requires': 'Preregister this exact row and policy in a new bounded cohort. '
                          'Keep complete matched support and separate sealed holdout review. '
                          'This fragment makes no run, score, acceptance or improvement claim.'}
    return {'schema': 'zenith_reflection_cohort_fragment_v1', 'candidate': row, 'review': review}
