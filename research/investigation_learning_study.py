"""Precommitted program-learning campaign: proposals, measured repair, frozen reuse.

Uses Zenith's shared priced/serialized provider and source custody. Acquired
tables and exact code versions are recorded; no candidate is silently repaired.
"""
import argparse
import hashlib
import json
from pathlib import Path

from zenith.budgeted import OpenRouterBudgetedProvider
from zenith.investigation_program import execute, validate_source
from zenith.providers import digest, write_json
from zenith.provider_policy import latest_model
from zenith.source_snapshot import archive_runtime
from research.operational_cases import INCUMBENT, TASK, grade, make_case, suite, novel_suite, typed_reference, rename_fields, FIELDS

PROGRAM_SCHEMA = {'type': 'object', 'properties': {k: {'type': 'string'} for k in ['source', 'scope', 'lesson']},
                  'required': ['source', 'scope', 'lesson'], 'additionalProperties': False}
ANSWER_SCHEMA = {'type': 'object', 'properties': {
    'findings': {'type': 'array', 'items': {'type': 'string'}},
    'unresolved': {'type': 'array', 'items': {'type': 'string'}},
    'ratio': {'type': ['number', 'null']}}, 'required': ['findings', 'unresolved', 'ratio'], 'additionalProperties': False}
LANGUAGE = '''Write a reusable Python procedure investigate(context, acquire). context contains the case metadata and natural-language source and quantity contracts, but no tables. acquire("spans") and acquire("population") return the documented tables, at most eight acquisitions per case. Derive quantities from records, not case IDs. You may define helper functions. Only function definitions at module level, no imports, annotations, decorators, default arguments, names starting with underscore, exceptions, while loops, I/O, or global state. Python for loops, comprehensions, lambda, arithmetic except power, sets and dicts are allowed. Builtins: abs all any bool dict enumerate float int isinstance len list max min range reversed round set sorted str sum tuple zip. Methods: get items keys values append extend sort lower upper strip split setdefault add discard copy count index pop remove. Return the exact answer object. The goal is a computation that remains valid when measurements, combinations of faults, source contracts and workload mix change. Preserve independent findings when another conclusion is unresolved. No external libraries or hidden tools. The source is executed in a restricted resource-limited process. scope and lesson are short technical statements, not a chain-of-thought transcript.'''


def score_program(source, dataset):
    try:
        rows = execute(source, [case for case, key in dataset])
    except (ValueError, SyntaxError) as exc:
        rows = [{'answer': None, 'trace': [], 'error': str(exc)} for pair in dataset]
    for row, (case, key) in zip(rows, dataset):
        row.update(id=case['id'], expected=key, **grade(key, row['answer']))
    return {'correct': sum(row['correct'] for row in rows), 'total': len(rows),
            'claims_correct': sum(row['claims_correct'] for row in rows),
            'acquisitions': sum(len(row['trace']) for row in rows), 'rows': rows}


def feedback(dataset, result, include_residuals=False):
    evidence = []
    for (case, key), row in zip(dataset, result['rows']):
        actual = row['answer'] or {}
        wanted, got = key['ratio'], actual.get('ratio')
        residual = got - wanted if got is not None and wanted is not None else None
        evidence.append({'case': case, 'expected': key, 'actual': row['answer'],
                         'error': row['error'], 'correct': row['correct'],
                         'numerical_residual_actual_minus_expected': residual,
                         'missing_findings': sorted(set(key['findings']) - set(actual.get('findings', []))),
                         'extra_findings': sorted(set(actual.get('findings', [])) - set(key['findings'])),
                         'missing_unresolved': sorted(set(key['unresolved']) - set(actual.get('unresolved', []))),
                         'extra_unresolved': sorted(set(actual.get('unresolved', [])) - set(key['unresolved']))})
    if not include_residuals:
        evidence = [{k: e[k] for k in ('case', 'expected', 'actual', 'error', 'correct')} for e in evidence]
    return evidence


def prepare(output, model=None, provider_slug=None, seed_offset=600000, feedback_style="broad"):
    if feedback_style not in ("broad", "compact"):
        raise ValueError("feedback_style must be broad or compact")
    model = model or latest_model()
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    data = {'bootstrap': [make_case(seed_offset+71001, overlap=True, ratio=1.), make_case(seed_offset+71002, ratio=1.4)],
            'development': suite(seed_offset+72000, 64), 'heldout': novel_suite(seed_offset+81000, 256),
            'transfer': novel_suite(seed_offset+92000, 64, schema='foreign')}
    # Fixed paired cases are not fed to program learners or the prose compiler.
    data['control'] = [data['heldout'][(i * 7) % 256] for i in range(32)]
    write_json(output/'datasets.json', data)
    protocol = {'schema': 'zenith_executable_investigation_campaign_v7',
                'model': model, 'provider_slug': provider_slug,
                'max_cost_usd': '1.50', 'max_calls': 40, 'max_output_tokens': 8192,
                'reasoning_effort': 'none', 'seed_offset': seed_offset,
                'version_change': 'Configurable follow-on harness after the recorded V1-V6 campaigns. Broad feedback matches the V5 selection rule and is the default; compact feedback reproduces the V6 selection rule with output residuals. Model, source, settings and new seeds are frozen per run. This source version does not retroactively change any recorded campaign.',
                'learners': 3, 'proposal_rounds': 6, 'feedback_style': feedback_style,
                'failed_witnesses': 12 if feedback_style == 'broad' else 2,
                'correct_witnesses': 4 if feedback_style == 'broad' else 2,
                'residual_feedback': feedback_style == 'compact', 'dataset_sha256': digest(data),
                'source': archive_runtime(output), 'task': TASK, 'language': LANGUAGE,
                'promotion': 'Strict improvement in whole-development exact score with no regression on previously correct development cases. Local incumbent only, never production auto-adoption.',
                'primary': 'Frozen program exact answers on 256 fresh generated cases; before/after and deletion control. No holdout feedback to learners.',
                'secondary': '64 renamed-schema cases after one model-authored adapter; frozen core hash unchanged. 32 paired direct and algorithm-matched prose answers, using first learner only; no best-of-three selection.',
                'scope': 'Synthetic operator-authored task and generator. Heldout combinations exclude development combinations; half have unresolved evidence. Known semantic factors, not real operational data, autonomous concept invention, or evidence of general intelligence. Direct/prose controls lack code execution: this measures end-to-end compilation benefit, not isolated memory or graph advantage. Prose equivalence is intended, not guaranteed.',
                'feedback_selection': 'All 64 development cases score promotion. Broad prompts select up to 12 failed and 4 correct witnesses; compact selects 2 failed and 2 correct with output residuals. Full evaluation remains on disk. Stop proposing if development is perfect.',
                'calls': '3 learners x (6 proposals + 1 schema adapter) + 1 prose compilation + 8 direct batches + 8 prose batches = 38 maximum planned calls; no retries.',
                'selection': 'Recent inexpensive text/coding model, current official catalogue and explicit endpoint verification at every call; no paid fallback.'}
    write_json(output/'protocol.json', protocol)
    return protocol


def run(output, env_file):
    from system.lib.openrouter_free_runtime import load_env_file
    output = Path(output).resolve()
    if (output/'started.json').exists():
        raise ValueError('campaign already started; failed attempts are retained, never retried')
    protocol = json.loads((output/'protocol.json').read_text())
    data = json.loads((output/'datasets.json').read_text())
    if digest(data) != protocol['dataset_sha256']:
        raise ValueError('frozen datasets changed')
    archive = Path(protocol['source']['path'])
    if hashlib.sha256(archive.read_bytes()).hexdigest() != protocol['source']['sha256']:
        raise ValueError('source archive changed')
    # Verify the executable sources against the archive before spending.
    from zipfile import ZipFile
    root = Path(__file__).resolve().parents[1]
    with ZipFile(archive) as frozen:
        for name in frozen.namelist():
            if (root/name).read_bytes() != frozen.read(name):
                raise ValueError('runtime changed after preparation: ' + name)
    load_env_file(Path(env_file))
    write_json(output/'started.json', {'protocol_sha256': digest(protocol), 'dataset_sha256': digest(data)})
    provider = OpenRouterBudgetedProvider(output, protocol['model'], protocol['max_cost_usd'],
                protocol['max_calls'], protocol['max_output_tokens'], output/'budget', provider_slug=protocol['provider_slug'])

    def ask(name, prompt, schema, system):
        write_json(output/'prompts'/f'{name}.json', {'system': system, 'prompt': prompt, 'schema': schema})
        raw = provider.ask_ai(json.dumps(prompt, ensure_ascii=False),
            {'meta': {'session_id': output.name, 'node_id': name}, 'system_prompt': system,
             'reasoning_effort': protocol['reasoning_effort'],
             'response_format': {'type': 'json_schema', 'json_schema': {'name': 'investigation', 'strict': True, 'schema': schema}}})
        answer = json.loads(raw)
        from jsonschema import validate
        validate(answer, schema)
        write_json(output/'responses'/f'{name}.json', answer)
        print(json.dumps({'event': 'response', 'name': name}), flush=True)
        return answer

    reference = [grade(key, typed_reference(case))['correct'] for case, key in data['heldout']]
    if not all(reference):
        raise ValueError('independent observed-data reference disagrees with latent oracle')
    results = {'protocol_sha256': digest(protocol), 'learners': [],
               'typed_reference': {'correct': sum(reference), 'total': len(reference)},
               'deletion': score_program(INCUMBENT, data['heldout'])}
    try:
        for learner in range(protocol['learners']):
            current = {'source': INCUMBENT, 'scope': 'Naive summed operations; no learned library.', 'lesson': ''}
            rounds, witnesses = [], []
            for step in range(protocol['proposal_rounds']):
                examples = data['bootstrap'] if step == 0 else data['development']
                observed = score_program(current['source'], examples)
                if step > 0 and observed['correct'] == observed['total']:
                    break
                all_evidence = feedback(examples, observed, protocol['residual_feedback'])
                evidence = all_evidence if step == 0 else ([e for e in all_evidence if not e['correct']][:protocol['failed_witnesses']] + [e for e in all_evidence if e['correct']][:protocol['correct_witnesses']])
                witnesses = evidence if step else []
                prior = None
                if rounds:
                    rejected = rounds[-1]
                    prior = {'proposal': rejected['proposal'], 'accepted': rejected['accepted'],
                             'regressions': rejected['regressions'],
                             'candidate_failures': [e for e in feedback(data['development'], rejected['candidate'], protocol['residual_feedback']) if not e['correct']][:protocol['failed_witnesses']]}
                proposal = ask(f'learner-{learner}-round-{step}',
                    {'task': TASK, 'incumbent': current, 'measured_feedback': evidence,
                     'previous_candidate_execution': prior,
                     'feedback_selection': 'Selected diagnostic witnesses; the full development suite determines promotion.',
                     'whole_development_score': {'correct': observed['correct'], 'total': observed['total']},
                     'request': 'Replace the whole computation with a general, correctly scoped procedure. Address measured failures of both the incumbent and any previous rejected proposal, including compilation failures. Recheck the actual numerical outputs, units, and record multiplicity before concluding no change. Explain the learned distinction concisely in lesson. If the incumbent is already correct on the supplied evidence, preserve it; do not invent a defect.'},
                    PROGRAM_SCHEMA, LANGUAGE)
                old = score_program(current['source'], data['development'])
                candidate = score_program(proposal['source'], data['development'])
                regressions = sum(before['correct'] and not after['correct'] for before, after in zip(old['rows'], candidate['rows']))
                accepted = candidate['correct'] > old['correct'] and regressions == 0
                rounds.append({'proposal': proposal, 'old': old, 'candidate': candidate, 'accepted': accepted,
                               'parent_sha256': digest(current), 'regressions': regressions})
                if accepted:
                    current = proposal
                write_json(output/f'learner-{learner}-rounds.json', rounds)
            frozen = {'program': current, 'sha256': digest(current),
                      'counterexamples': witnesses, 'dependencies': [], 'rounds': rounds}
            write_json(output/f'learner-{learner}-frozen.json', frozen)
            heldout = score_program(current['source'], data['heldout'])
            first_proposal = score_program(rounds[0]['proposal']['source'], data['heldout'])
            controls = score_program(current['source'], data['control'])
            # Transfer permits a field-name adapter, not a rewritten solver.
            adapter_schema = {'type': 'object', 'properties': {name: {'type': 'string'} for name in FIELDS['native']}, 'required': FIELDS['native'], 'additionalProperties': False}
            adapter = ask(f'learner-{learner}-adapter',
                {
                 'old_documentation': data['development'][0][0]['source_documentation'],
                 'new_documentation': data['transfer'][0][0]['source_documentation'],
                 'request': 'Return a mapping from each old field name to the semantically corresponding new field name. This is only a schema adapter; the numerical program remains byte-identical.'},
                adapter_schema, 'Match documented source fields by their meanings. Return only the mapping.')
            try:
                adapted = [(rename_fields(case, adapter, data['development'][0][0]['source_documentation']), key) for case, key in data['transfer']]
                transfer = score_program(current['source'], adapted)
            except ValueError as exc:
                transfer = {'correct': 0, 'total': len(data['transfer']), 'error': str(exc)}
            record = {'frozen_sha256': frozen['sha256'], 'rounds': rounds,
                      'heldout': heldout, 'first_proposal_heldout': first_proposal, 'controls': controls, 'transfer': transfer,
                      'adapter': adapter, 'dependency_sha256': digest(current['source'])}
            results['learners'].append(record)
            write_json(output/'partial.json', results)
            print(json.dumps({'event': 'learner_complete', 'learner': learner, 'heldout': heldout['correct'], 'transfer': transfer['correct']}), flush=True)

        # Prose has the same learned algorithm, not a weakened generic reminder.
        primary = json.loads((output/'learner-0-frozen.json').read_text())
        prose = ask('prose-memory', {'task': TASK, 'program': primary['program'], 'counterexamples': primary['counterexamples'],
                    'request': 'Translate this exact computation and its scope into a precise reusable prose algorithm. Preserve each check and arithmetic operation; include no test-case answers or code.'},
                    {'type': 'object', 'properties': {'algorithm': {'type': 'string'}}, 'required': ['algorithm'], 'additionalProperties': False},
                    'Compile the supplied reusable algorithm into exact concise prose. Do not add unsupported claims.')
        for arm in ['direct', 'prose']:
            scores = []
            for batch in range(8):
                pairs = data['control'][batch*4:(batch+1)*4]
                schema = {'type': 'object', 'properties': {case['id']: ANSWER_SCHEMA for case, key in pairs},
                          'required': [case['id'] for case, key in pairs], 'additionalProperties': False}
                prompt = {'task': TASK, 'cases': [case for case, key in pairs]}
                if arm == 'prose':
                    prompt['reusable_algorithm'] = prose['algorithm']
                response = ask(f'{arm}-{batch}', prompt, schema,
                    'Compute the requested investigation from the supplied source contracts and raw records. Return one exact answer per case ID. No external tools are available. All tables are supplied; report unresolved conditions as specified.')
                scores.extend({'id': case['id'], 'answer': response[case['id']], 'expected': key, **grade(key, response[case['id']])} for case, key in pairs)
            results[arm] = {'correct': sum(r['correct'] for r in scores), 'total': len(scores), 'rows': scores}
            write_json(output/'partial.json', results)
        ledger = json.loads((output/'budget/budget.json').read_text())
        results['cost'] = {k: ledger[k] for k in ['total_reported_cost_usd', 'total_reserved_usd'] if k in ledger}
        results['calls'] = len(ledger['entries'])
        write_json(output/'results.json', results)
        print(json.dumps({'event': 'complete', 'calls': results['calls'], 'cost': results['cost']}), flush=True)
        return results
    except Exception as exc:
        write_json(output/'failure.json', {'error': f'{type(exc).__name__}: {exc}', 'automatic_retry': False})
        write_json(output/'partial.json', results)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['prepare', 'run'])
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--env-file', type=Path)
    parser.add_argument('--model')
    parser.add_argument('--provider-slug')
    parser.add_argument('--seed-offset', type=int, default=600000)
    parser.add_argument('--feedback-style', choices=['broad', 'compact'], default='broad')
    args = parser.parse_args()
    if args.command == 'prepare':
        print(json.dumps(prepare(args.output, args.model, args.provider_slug, args.seed_offset, args.feedback_style), indent=2))
    elif args.env_file is None:
        parser.error('run requires --env-file')
    else:
        run(args.output, args.env_file)


if __name__ == '__main__':
    main()
