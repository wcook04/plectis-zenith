#!/usr/bin/env python3
"""Curate completed campaign evidence; replay frozen programs without inference.

Copies the original execution harness from each source archive. Public bundles
contain synthetic inputs and model-authored programs, never credentials or raw
provider transport. Build reads immutable local campaigns; replay is offline.
"""
import argparse
from decimal import Decimal
import hashlib
import importlib.util
import json
import re
from pathlib import Path
import sys
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from zenith.providers import digest


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False)+'\n')


def summarize(result):
    if 'rows' not in result:
        return {k: result[k] for k in ('correct', 'total', 'error') if k in result}
    resolved = [r for r in result['rows'] if r['expected']['ratio'] is not None]
    unresolved = [r for r in result['rows'] if r['expected']['ratio'] is None]
    return {'correct': result['correct'], 'total': result['total'],
            'resolved_correct': sum(r['correct'] for r in resolved), 'resolved_total': len(resolved),
            'unresolved_correct': sum(r['correct'] for r in unresolved), 'unresolved_total': len(unresolved),
            'acquisitions': result.get('acquisitions')}


def build(studies):
    report = {'schema': 'zenith_learning_evidence_v1', 'campaigns': [],
              'scope': 'Synthetic operational cases. All versions and failed attempts retained. A larger score does not isolate model, interface, feedback or reasoning-mode effects between versions.'}
    total = Decimal(0)
    for study in studies:
        protocol = json.loads((study/'protocol.json').read_text())
        if hashlib.sha256(Path(protocol['source']['path']).read_bytes()).hexdigest() != protocol['source']['sha256']:
            raise ValueError('source archive custody mismatch')
        started = json.loads((study/'started.json').read_text())
        if started['protocol_sha256'] != digest(protocol):
            raise ValueError('started protocol custody mismatch')
        ledger = json.loads((study/'budget/budget.json').read_text())
        amount = Decimal(ledger['total_reported_cost_usd']); total += amount
        calls = []
        for entry in ledger['entries'].values():
            response = entry.get('provider_response', {})
            calls.append({k: entry.get(k) for k in ('call_id', 'node_id', 'status', 'actual_provider', 'requested_model', 'cost', 'prompt_sha256', 'response_sha256', 'reasoning_effort', 'reserved_cost_usd')})
            calls[-1].update(usage=response.get('usage'), finish_reason=(response.get('choices') or [{}])[0].get('finish_reason'))
        result_file = study/'results.json'
        campaign = {'id': study.name, 'protocol_sha256': digest(protocol),
                    'source_archive_sha256': protocol['source']['sha256'], 'model': protocol['model'],
                    'provider_slug': protocol['provider_slug'], 'reasoning_effort': protocol.get('reasoning_effort', 'none'),
                    'proposal_rounds': protocol['proposal_rounds'],
                    'max_output_tokens': protocol['max_output_tokens'],
                    'reported_cost_usd': str(amount), 'calls': calls,
                    'complete': result_file.exists(), 'private_source_run': str(study.resolve())}
        if not result_file.exists():
            failure = json.loads((study/'failure.json').read_text())
            safe_error = re.sub(r'https?://[^\s\"}]+', '[provider settings URL omitted]', failure['error'])
            campaign['failure'] = {'error': safe_error[:600],
                                   'full_error_sha256': digest(failure), 'automatic_retry': False}
            partial = study/'partial.json'
            if not partial.exists() or not json.loads(partial.read_text()).get('learners'):
                report['campaigns'].append(campaign)
                continue
            result_file = partial
        results = json.loads(result_file.read_text())
        if results['protocol_sha256'] != digest(protocol):
            raise ValueError('result protocol custody mismatch')
        data = json.loads((study/'datasets.json').read_text())
        if digest(data) != protocol['dataset_sha256']:
            raise ValueError('dataset custody mismatch')
        target = ROOT/'examples/investigation-learning'/study.name.rsplit('-', 1)[-1]
        target.mkdir(parents=True, exist_ok=True)
        with ZipFile(protocol['source']['path']) as archive:
            executor = archive.read('zenith/investigation_program.py')
            evaluator = archive.read('research/operational_cases.py')
        (target/'executor.py').write_bytes(executor)
        (target/'evaluator.py').write_bytes(evaluator)
        programs = []
        for i, learner in enumerate(results['learners']):
            frozen = json.loads((study/f'learner-{i}-frozen.json').read_text())
            if digest(frozen['program']) != frozen['sha256'] or learner['frozen_sha256'] != frozen['sha256']:
                raise ValueError('frozen program custody mismatch')
            if digest(frozen['program']['source']) != learner['dependency_sha256']:
                raise ValueError('frozen numerical source custody mismatch')
            programs.append({'final': frozen['program'], 'first': learner['rounds'][0]['proposal'],
                             'adapter': learner['adapter'], 'frozen_sha256': frozen['sha256'],
                             'expected_heldout': learner['heldout'], 'expected_first': learner['first_proposal_heldout'],
                             'expected_transfer': learner['transfer']})
        bundle = {'protocol': protocol, 'datasets': data, 'programs': programs,
                  'executor_sha256': hashlib.sha256(executor).hexdigest(),
                  'evaluator_sha256': hashlib.sha256(evaluator).hexdigest()}
        # Compact representation keeps the complete evidence smaller than a repeated trace.
        (target/'bundle.json').write_text(json.dumps(bundle, ensure_ascii=False, separators=(',', ':'))+'\n')
        campaign.update(bundle=str((target/'bundle.json').relative_to(ROOT)),
                        bundle_sha256=hashlib.sha256((target/'bundle.json').read_bytes()).hexdigest(),
                        executor_sha256=bundle['executor_sha256'],
                        evaluator_sha256=bundle['evaluator_sha256'],
                        typed_reference=results['typed_reference'], deletion=summarize(results['deletion']),
                        direct=summarize(results['direct']) if 'direct' in results else None,
                        prose=summarize(results['prose']) if 'prose' in results else None,
                        missing_control_arms=[arm for arm in ('direct', 'prose') if arm not in results], learners=[])
        for learner in results['learners']:
            campaign['learners'].append({'rounds': [{'old': r['old']['correct'], 'candidate': r['candidate']['correct'],
                'total': r['candidate']['total'], 'accepted': r['accepted'], 'regressions': r['regressions'],
                'execution_errors': sorted({row['error'] for row in r['candidate']['rows'] if row['error']})} for r in learner['rounds']],
                'heldout': summarize(learner['heldout']), 'first_proposal_heldout': summarize(learner['first_proposal_heldout']),
                'transfer': summarize(learner['transfer']), 'paired_controls': summarize(learner['controls']),
                'frozen_sha256': learner['frozen_sha256'], 'dependency_sha256': learner['dependency_sha256']})
        report['campaigns'].append(campaign)
    report['total_reported_cost_usd'] = str(total)
    report['total_calls'] = sum(len(c['calls']) for c in report['campaigns'])
    unpriced = [call for c in report['campaigns'] for call in c['calls'] if call['cost'] is None]
    report['unreported_cost_calls'] = len(unpriced)
    report['unreported_cost_reservations_usd'] = str(sum((Decimal(call['reserved_cost_usd']) for call in unpriced), Decimal(0)))
    write(ROOT/'docs/history/investigation-learning-20261013.json', report)
    return report


def replay():
    report = json.loads((ROOT/'docs/history/investigation-learning-20261013.json').read_text())
    checks = []
    for campaign in report['campaigns']:
        if 'bundle' not in campaign:
            continue
        path = ROOT/campaign['bundle']
        if hashlib.sha256(path.read_bytes()).hexdigest() != campaign['bundle_sha256']:
            raise ValueError('public bundle hash mismatch')
        bundle = json.loads(path.read_text())
        if digest(bundle['protocol']) != campaign['protocol_sha256']:
            raise ValueError('public protocol hash mismatch')
        executor_path = path.parent/'executor.py'
        if hashlib.sha256(executor_path.read_bytes()).hexdigest() != bundle['executor_sha256']:
            raise ValueError('frozen executor hash mismatch')
        spec = importlib.util.spec_from_file_location('frozen_investigation', executor_path)
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        evaluator_path = path.parent/'evaluator.py'
        if hashlib.sha256(evaluator_path.read_bytes()).hexdigest() != bundle['evaluator_sha256']:
            raise ValueError('frozen evaluator hash mismatch')
        spec = importlib.util.spec_from_file_location('frozen_evaluator', evaluator_path)
        evaluator = importlib.util.module_from_spec(spec); spec.loader.exec_module(evaluator)
        data = bundle['datasets']
        if digest(data) != bundle['protocol']['dataset_sha256']:
            raise ValueError('dataset hash mismatch')
        for i, program in enumerate(bundle['programs']):
            if digest(program['final']) != program['frozen_sha256']:
                raise ValueError('public frozen program hash mismatch')
            for kind in ('final', 'first'):
                try:
                    rows = module.execute(program[kind]['source'], [case for case, key in data['heldout']])
                except (ValueError, SyntaxError) as exc:
                    rows = [{'answer': None, 'trace': [], 'error': str(exc)} for pair in data['heldout']]
                expected = program['expected_heldout' if kind == 'final' else 'expected_first']
                if len(rows) != len(data['heldout']) or len(rows) != len(expected['rows']):
                    raise ValueError('heldout result cardinality mismatch')
                actual = sum(evaluator.grade(key, row['answer'])['correct'] for (case, key), row in zip(data['heldout'], rows))
                # Scores and acquisition/output/error records must reproduce, not just a headline.
                for observed, original in zip(rows, expected['rows']):
                    if any(observed[k] != original[k] for k in ('answer', 'trace', 'error')):
                        raise ValueError(f'{campaign["id"]} learner {i} {kind}: output/trace mismatch')
                if actual != expected['correct']:
                    raise ValueError('score mismatch')
                checks.append({'campaign': campaign['id'], 'learner': i, 'stage': kind, 'correct': actual, 'total': len(rows)})
            adapted = [(evaluator.rename_fields(case, program['adapter'], data['development'][0][0]['source_documentation']), key) for case, key in data['transfer']]
            rows = module.execute(program['final']['source'], [case for case, key in adapted])
            if len(rows) != len(adapted) or len(rows) != len(program['expected_transfer']['rows']):
                raise ValueError('transfer result cardinality mismatch')
            for observed, original in zip(rows, program['expected_transfer']['rows']):
                if any(observed[k] != original[k] for k in ('answer', 'trace', 'error')):
                    raise ValueError('transfer output/trace mismatch')
            actual = sum(evaluator.grade(key, row['answer'])['correct'] for (case, key), row in zip(adapted, rows))
            if actual != program['expected_transfer']['correct']:
                raise ValueError('transfer score mismatch')
    return {'ok': True, 'checks': checks, 'inference_calls': 0}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['build', 'replay'])
    parser.add_argument('--study', action='append', type=Path, default=[])
    args = parser.parse_args()
    result = build(args.study) if args.command == 'build' else replay()
    print(json.dumps(result if args.command == 'replay' else {k: result[k] for k in ('total_calls', 'total_reported_cost_usd')}, indent=2))
