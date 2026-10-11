#!/usr/bin/env python3
"""Check finite Zenith graph contracts and optionally instantiate the Lean model.

The input/output labels and pre/post references are declared contracts. This
checker certifies graph rank, declared input typing, and recorded evidence
boundaries; it never certifies natural-language model behavior.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
TOOLCHAIN = 'leanprover/lean4:v4.30.0'
RANK_SCHEMA = 'zenith_graph_rank_certificate_v1'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def validate_rank_certificate(certificate):
    fields = {'schema_version', 'node_ids', 'edges', 'ranks', 'condition'}
    if not isinstance(certificate, dict) or set(certificate) != fields or certificate['schema_version'] != RANK_SCHEMA:
        raise ValueError('rank certificate has wrong schema or fields')
    nodes = certificate['node_ids']
    if not isinstance(nodes, list) or any(not isinstance(n, str) or not n for n in nodes) or len(set(nodes)) != len(nodes):
        raise ValueError('node ids must be distinct nonempty strings')
    ranks = certificate['ranks']
    if not isinstance(ranks, dict) or set(ranks) != set(nodes) or any(type(v) is not int or v < 0 for v in ranks.values()):
        raise ValueError('rank certificate needs exactly one natural rank per node')
    if certificate['condition'] != 'rank(dependency)<rank(node)':
        raise ValueError('rank certificate has wrong ordering condition')
    if not isinstance(certificate['edges'], list):
        raise ValueError('rank edges must be a list')
    seen = set()
    for edge in certificate['edges']:
        if not isinstance(edge, dict) or set(edge) != {'dependency_id', 'node_id'}:
            raise ValueError('edge must name dependency_id and node_id')
        source, target = edge['dependency_id'], edge['node_id']
        if source not in ranks or target not in ranks:
            raise ValueError('edge endpoint is absent from rank certificate')
        if (source, target) in seen:
            raise ValueError('duplicate edge in rank certificate')
        seen.add((source, target))
        if ranks[source] >= ranks[target]:
            raise ValueError(f'edge violates strict rank: {source} -> {target}')
    return {'ok': True, 'node_count': len(nodes), 'edge_count': len(seen),
            'property': 'all edges strictly increase natural rank; no nonempty cycle'}


def generate(root: Path = ROOT):
    from system.core.governance import compute_waves
    from system.core.loader import PhysicalLoader
    loader = PhysicalLoader(root)
    graph = loader.load_all_nodes()
    ranks = {node: rank for rank, wave in enumerate(compute_waves(graph)) for node in wave}
    certificate = {'schema_version': RANK_SCHEMA, 'node_ids': sorted(graph),
        'edges': [{'dependency_id': dep, 'node_id': identifier} for identifier, node in sorted(graph.items()) for dep in node.dependencies],
        'ranks': ranks, 'condition': 'rank(dependency)<rank(node)'}
    validate_rank_certificate(certificate)
    skills, sources = [], {}
    for identifier, node in sorted(graph.items()):
        source = loader.manifest[identifier].relative_to(root).as_posix()
        sources[source] = sha((root / source).read_bytes())
        contract = node.meta.get('reasoning_contract', {})
        mode = contract.get('role_contract', {}).get('context_mode', '')
        forward = node.group == 'lab' or mode == 'forward_subject_only'
        incoming = {dep: 'truth_side_evidence' if graph[dep].group == 'oracle' else 'subject_side_evidence' for dep in node.dependencies}
        # Oracle outputs are conservatively truth side even when their CP2
        # grounding must use subject-side ids. The two authorities are distinct.
        skills.append({'node_id': identifier,
            'input_sorts': {dep: graph[dep].output_schema for dep in node.dependencies},
            'output_sort': node.output_schema,
            'parameters': {'timeout_seconds': node.execution.get('timeout'), 'retries': node.execution.get('retries'),
                'incoming_weights': {dep: 1.0 for dep in node.dependencies}, 'max_context_chars': None},
            'forward_only': forward, 'incoming_context_classes': incoming,
            'precondition_ref': 'subject_available_before_cutoff_and_no_truth_grounding' if forward else 'declared_mission_admission',
            'postcondition_ref': contract.get('output_contract', {}).get('schema_or_standard', node.output_schema),
            'skill_ref': f'.agents/node-skills/{identifier}/SKILL.md',
            'implementation_ref': source, 'instruction_sha256': sha(node.instruction.encode())})
    return {'schema_version': 'zenith_semantic_contract_v1', 'rank_certificate': certificate,
        'skills': skills, 'source_hashes': sources,
        'claim_boundary': 'declared contracts and finite structural certificate; no LLM behavioral or prediction guarantee'}


def validate_contract(spec, root: Path | None = None):
    if spec.get('schema_version') != 'zenith_semantic_contract_v1':
        raise ValueError('unsupported semantic contract schema')
    certificate = spec['rank_certificate']
    result = validate_rank_certificate(certificate)
    skills = spec['skills']
    skill_fields = {'node_id', 'input_sorts', 'output_sort', 'parameters', 'forward_only',
                    'incoming_context_classes', 'precondition_ref', 'postcondition_ref',
                    'skill_ref', 'implementation_ref', 'instruction_sha256'}
    if not isinstance(skills, list) or any(not isinstance(skill, dict) or set(skill) != skill_fields for skill in skills):
        raise ValueError('semantic skill must contain exactly the declared contract fields')
    for skill in skills:
        if type(skill['forward_only']) is not bool:
            raise ValueError('forward_only must be a boolean')
        if not isinstance(skill['output_sort'], str) or not skill['output_sort']:
            raise ValueError('output sort must be a nonempty declared schema label')
        if not isinstance(skill['input_sorts'], dict) or not isinstance(skill['incoming_context_classes'], dict):
            raise ValueError('input sorts and context classes must be port maps')
    by_id = {skill['node_id']: skill for skill in skills}
    if len(by_id) != len(skills) or set(by_id) != set(certificate['node_ids']):
        raise ValueError('semantic skills must cover certificate node ids exactly once')
    edges = {(e['dependency_id'], e['node_id']) for e in certificate['edges']}
    for identifier, skill in by_id.items():
        inputs = skill['input_sorts']
        expected = {source for source, target in edges if target == identifier}
        if set(inputs) != expected or set(skill['incoming_context_classes']) != expected:
            raise ValueError('skill input/context ports do not match graph edges')
        for source, sort in inputs.items():
            if sort != by_id[source]['output_sort']:
                raise ValueError('input sort differs from upstream output contract')
            klass = skill['incoming_context_classes'][source]
            if klass not in {'subject_side_evidence', 'truth_side_evidence'}:
                raise ValueError('unknown subject/truth evidence class')
            if skill['forward_only'] and klass == 'truth_side_evidence':
                raise ValueError('truth-side edge cannot enter a forward-only skill')
    if root is not None:
        for path, expected in spec['source_hashes'].items():
            if sha((root / path).read_bytes()) != expected:
                raise ValueError(f'canonical node source hash changed: {path}')
    return {**result, 'declared_port_typing': True, 'forward_context_boundary': True,
            'behavioral_semantics_verified': False}


def parse_time(value):
    if isinstance(value, bool):
        raise ValueError('boolean is not an evidence timestamp')
    if type(value) is int and value >= 0:
        return value
    if not isinstance(value, str):
        raise ValueError('timestamp must be natural ticks or a timezone-aware ISO string')
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('evidence timestamp requires a timezone')
    seconds = parsed.astimezone(timezone.utc).timestamp()
    if seconds < 0 or not seconds.is_integer():
        raise ValueError('evidence timestamps must be nonnegative whole seconds')
    return int(seconds)


def validate_evidence(records, *, cutoff, forward_only=True):
    cutoff = parse_time(cutoff)
    for record in records:
        if record.get('context_class') not in {'subject_side_evidence', 'truth_side_evidence'}:
            raise ValueError('unknown subject/truth evidence class')
        if parse_time(record['available_at']) > cutoff:
            raise ValueError('evidence was available after the frozen cutoff')
        if forward_only and record['context_class'] != 'subject_side_evidence':
            raise ValueError('truth-side evidence is forbidden in forward context')
    return {'ok': True, 'record_count': len(records), 'cutoff_ticks': cutoff}


def lean_instance(certificate):
    validate_rank_certificate(certificate)
    nodes = certificate['node_ids']
    positions = {node: index for index, node in enumerate(nodes)}
    ranks = ', '.join(str(certificate['ranks'][node]) for node in nodes)
    vertices = ', '.join(f"({index}, {certificate['ranks'][node]})" for index, node in enumerate(nodes))
    edges = ', '.join(f"(({positions[e['dependency_id']]}, {certificate['ranks'][e['dependency_id']]}), ({positions[e['node_id']]}, {certificate['ranks'][e['node_id']]}))" for e in certificate['edges'])
    return f'''
namespace Zenith.ObservedGraph
set_option maxRecDepth 10000
set_option maxHeartbeats 2000000
-- Each vertex is the exact (node_ids index, certified rank) pair. This keeps
-- rank projection computationally small without changing vertex identity.
abbrev Vertex := Nat × Nat
def ranks : Array Nat := #[{ranks}]
def vertices : List Vertex := [{vertices}]
def rank (node : Vertex) : Nat := node.2
def edges : List (Vertex × Vertex) := [{edges}]
theorem certificate_valid : rankChecks rank edges = true := by decide
theorem acyclic (node : Vertex) : ¬ Path (fun a b => (a, b) ∈ edges) node node :=
  ranked_graph_acyclic (rank_checks_sound certificate_valid) node
#print axioms certificate_valid
#print axioms acyclic
end Zenith.ObservedGraph
'''


def check_lean(certificate):
    source = (ROOT / 'formal/ZenithSemantics.lean').read_text()
    if shutil.which('elan') is None:
        raise ValueError('elan is unavailable; Python checks do not establish Lean acceptance')
    installed = subprocess.run(['elan', 'toolchain', 'list'], capture_output=True, text=True, check=True).stdout.splitlines()
    if TOOLCHAIN not in [line.split()[0] for line in installed]:
        raise ValueError(f'preinstalled {TOOLCHAIN} is required; this checker never installs tools')
    with tempfile.TemporaryDirectory(prefix='zenith-semantics-') as directory:
        path = Path(directory) / 'ObservedGraph.lean'
        path.write_text(source + lean_instance(certificate))
        run = subprocess.run(['elan', 'run', TOOLCHAIN, 'lean', '-j', '1', str(path)], cwd=ROOT,
            capture_output=True, text=True, timeout=120)
    if run.returncode or 'sorryAx' in run.stdout or 'depends on axioms:' in run.stdout:
        raise ValueError(f'Lean did not accept the axiom-free contract instance: {run.stdout}{run.stderr}')
    return {'lean_accepted': True, 'toolchain': TOOLCHAIN,
            'formal_source_sha256': sha(source.encode()), 'axiom_audit': run.stdout.strip()}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--spec', type=Path, help='check an existing semantic contract instead of regenerating')
    parser.add_argument('--rank-certificate', type=Path, help='check a topology variant rank certificate')
    parser.add_argument('--output', type=Path, help='save the generated contract and validation receipt')
    parser.add_argument('--evidence', type=Path, help='JSON list of available_at/context_class records')
    parser.add_argument('--cutoff', help='natural ticks or timezone-aware ISO timestamp')
    parser.add_argument('--hindsight', action='store_true', help='allow truth-side records in the evidence check')
    parser.add_argument('--lean', action='store_true', help='kernel-check finite graph and general theorem instance')
    args = parser.parse_args(argv)
    try:
        if args.rank_certificate:
            payload = json.loads(args.rank_certificate.read_text())
            certificate = payload.get('acyclic_certificate', payload)
            spec = None
            receipt = validate_rank_certificate(certificate)
        else:
            payload = json.loads(args.spec.read_text()) if args.spec else generate(args.root)
            spec = payload.get('contract', payload)
            certificate = spec['rank_certificate']
            receipt = validate_contract(spec, args.root)
        receipt['certificate_sha256'] = sha(json.dumps(certificate, sort_keys=True, separators=(',', ':')).encode())
        if args.evidence:
            if args.cutoff is None:
                raise ValueError('--evidence requires --cutoff')
            receipt['evidence'] = validate_evidence(json.loads(args.evidence.read_text()), cutoff=args.cutoff, forward_only=not args.hindsight)
        if args.lean:
            receipt.update(check_lean(certificate))
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps({'contract': spec, 'receipt': receipt}, indent=2, sort_keys=True) + '\n')
        print(json.dumps(receipt, indent=2))
        return 0
    except (ValueError, OSError, subprocess.SubprocessError) as exc:
        parser.exit(2, f'error: {exc}\n')


if __name__ == '__main__':
    raise SystemExit(main())
