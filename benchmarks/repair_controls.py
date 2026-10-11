"""Synthetic controls for selecting a context repair through the real policy owner.

This is a deterministic integration benchmark, not an LLM, market forecast,
native cohort, causal-discovery algorithm, or new graph executor. A fixed leaf
normalizes a quote for a split; only native incoming-context weights can change.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from decimal import Decimal, localcontext
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import random

from research.engine import event_time, write_json
from system.lib.reasoning_policy import apply_reasoning_policy, policy_sha256, validate_reasoning_policy
from system.lib.types import CodexNode, NodeType

NODE = CodexNode('normalize', NodeType.REASONING, dependencies=('quote', 'split', 'notes'))
GRAPH = {NODE.id: NODE, **{key: CodexNode(key, NodeType.TOOL) for key in NODE.dependencies}}
SCENARIOS = ('omitted_relevant', 'absent_source', 'future_source', 'conflicting_source',
             'irrelevant_omission', 'healthy', 'wrong_calculation')


def sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                    allow_nan=False).encode()).hexdigest()


def policy(weights):
    result = {'variant_id': 'control_' + sha(weights)[:12],
              'nodes': {NODE.id: {'incoming_weights': weights}}}
    result['policy_sha256'] = policy_sha256(result)
    return validate_reasoning_policy(result, GRAPH)


def admit(sources, as_of):
    """Explicit fixture admission; a source's event time alone is insufficient."""
    cutoff = event_time(as_of)
    return {key: deepcopy(row) for key, row in sources.items()
            if event_time(row['available_at']) <= cutoff}


def calculate(views, *, wrong_operator=False):
    """Use delivered values only; policy ids, repair labels and answers are absent."""
    try:
        quote, action = views['quote'], views['split']
        if quote['currency'] != 'USD' or len(action['ratios']) != 1:
            return None
        price, ratio = Decimal(quote['price']), Decimal(action['ratios'][0])
        if not price.is_finite() or not ratio.is_finite() or price <= 0 or ratio <= 0:
            return None
        with localcontext() as context:
            context.prec = 40
            return price * ratio if wrong_operator else price / ratio
    except (KeyError, TypeError, ValueError, ArithmeticError):
        return None


def execution_input(case):
    return {key: case[key] for key in ('sources', 'as_of')}


def execute(inputs, selected, *, wrong_operator=False):
    if set(inputs) != {'sources', 'as_of'}:
        raise ValueError('execution accepts sources and as_of only, never oracle labels')
    selected = validate_reasoning_policy(selected, GRAPH)
    admitted = admit(inputs['sources'], inputs['as_of'])
    before = sha(admitted)
    views, _, receipt = apply_reasoning_policy(NODE, admitted, selected)
    answer = calculate(views, wrong_operator=wrong_operator)
    if sha(admitted) != before:
        raise ValueError('context policy mutated canonical inputs')
    return answer, receipt


def summarize(cases, selected, *, wrong_operator=False):
    correct = answered = required = forbidden_answers = 0
    errors, receipts, retained_chars = [], [], []
    for case in cases:
        value, receipt = execute(execution_input(case), selected, wrong_operator=wrong_operator)
        receipts.append(receipt['receipt_sha256'])
        retained_chars.append(receipt['retained_source_chars'])
        # The independently represented oracle is never passed to execution.
        target = Fraction(case['oracle']) if case['oracle'] is not None else None
        required += target is not None
        answered += value is not None
        forbidden_answers += target is None and value is not None
        error = abs(Fraction(value) - target) if value is not None and target is not None else None
        correct += (target is None and value is None) or (error is not None and error <= Fraction(1, 10**25))
        if error is not None:
            errors.append(float(error))
    return {'cases': len(cases), 'contract_correct': correct, 'answered': answered,
            'required_numeric_answers': required, 'unsupported_numeric_answers': forbidden_answers,
            'numeric_mae_on_answered': sum(errors) / len(errors) if errors else None,
            'mean_retained_source_chars': sum(retained_chars) / len(retained_chars) if retained_chars else None,
            'receipt_set_sha256': sha(receipts)}


def select(training, baseline, *, wrong_operator=False):
    """Measured finite search: restore one witnessed omitted edge, or change nothing.

    The scorer sees matured training labels. Candidate generation sees only native
    receipts, not scenario names, hidden cases, oracle values or injected causes.
    A tie is not evidence for a repair; all attempted candidates remain recorded.
    """
    omitted = set()
    for case in training:
        _, receipt = execute(execution_input(case), baseline, wrong_operator=wrong_operator)
        omitted.update(receipt['omitted_dependency_ids'])
    candidates = [('unchanged', baseline)]
    for edge in sorted(omitted):
        weights = deepcopy(baseline['nodes'][NODE.id]['incoming_weights'])
        weights[edge] = 1
        candidates.append(('restore_' + edge, policy(weights)))
    trials = {name: summarize(training, candidate, wrong_operator=wrong_operator)
              for name, candidate in candidates}
    winner = 'unchanged'
    for name, _ in candidates[1:]:
        if trials[name]['contract_correct'] > trials[winner]['contract_correct']:
            winner = name
    selected = dict(candidates)[winner]
    return selected, {'selection': winner, 'trials': trials, 'policy_sha256': selected['policy_sha256'],
                      'training_sha256': sha(training), 'selection_rule': 'strict contract-correct improvement; unchanged wins ties',
                      'causal_verdict': 'not_established', 'live_mutation_permission': False}


def fixtures(scenario, *, seed, count, assessment=False):
    """Published reproducible fault controls; no scenario label enters the selector."""
    if scenario not in SCENARIOS:
        raise ValueError('unknown controlled scenario')
    rng = random.Random(seed)
    cases = []
    ratios = ('1.5', '3', '4', '10') if assessment else ('2', '5')
    for _ in range(count):
        cents = rng.randrange(10000, 500000) if assessment else rng.randrange(100, 9999)
        price, ratio = str(Decimal(cents) / 100), rng.choice(ratios)
        sources = {'quote': {'price': price, 'currency': 'USD', 'available_at': '2020-01-01T00:00:00Z'},
                   'split': {'ratios': [ratio], 'available_at': '2020-01-01T00:00:00Z'},
                   'notes': {'text': 'irrelevant ' + str(rng.randrange(10000)), 'available_at': '2020-01-01T00:00:00Z'}}
        # This oracle is rational arithmetic, independent of the Decimal leaf.
        oracle = str(Fraction(cents, 100) / Fraction(ratio))
        if scenario == 'absent_source':
            del sources['split']; oracle = None
        elif scenario == 'future_source':
            sources['split']['available_at'] = '2020-02-01T00:00:00Z'; oracle = None
        elif scenario == 'conflicting_source':
            sources['split']['ratios'].append(str(Decimal(ratio) + 1)); oracle = None
        # Change key order as a nuisance; content remains the authority.
        if assessment:
            sources = dict(reversed(list(sources.items())))
        cases.append({'as_of': '2020-01-02T00:00:00Z', 'sources': sources, 'oracle': oracle})
    return cases


def run():
    results = {}
    for scenario in SCENARIOS:
        # Both omissions are real native policy fields; their semantic relevance
        # is unknown to the candidate generator.
        baseline = policy({'split': 0 if scenario == 'omitted_relevant' else 1,
                           'notes': 1 if scenario == 'healthy' else 0})
        training = fixtures(scenario, seed=17, count=20)
        selected, selection = select(training, baseline, wrong_operator=scenario == 'wrong_calculation')
        # Materialize assessment only after selection; no adaptive repeat search.
        assessment = fixtures(scenario, seed=91, count=64, assessment=True)
        wrong = policy({**baseline['nodes'][NODE.id]['incoming_weights'], 'notes': 1})
        arms = {name: summarize(assessment, value, wrong_operator=scenario == 'wrong_calculation')
                for name, value in [('unchanged', baseline), ('selected', selected), ('irrelevant_edge_repair', wrong)]}
        results[scenario] = {'selection': selection, 'assessment_sha256': sha(assessment), 'arms': arms,
                             'source_status': 'synthetic controlled task, not financial forecast data'}
    source = Path(__file__)
    return {'schema': 'zenith_repair_controls_v1', 'implementation_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
            'native_policy_source_sha256': hashlib.sha256((source.parents[1] / 'system/lib/reasoning_policy.py').read_bytes()).hexdigest(),
            'training_cases_per_scenario': 20, 'assessment_cases_per_scenario': 64, 'scenarios': results,
            'model_calls': 0, 'model_learning_demonstrated': False, 'market_edge_demonstrated': False,
            'resource_boundary': 'Restoration increases delivered context; no fixed-cap reallocation or resource-efficiency claim. Retained source characters are reported for every arm.',
            'interpretation': 'Finite measured context-policy selection and negative controls; no LLM skill learning, statistical population claim, or causal discovery.',
            'abstention_metric': 'Unknown is contract-correct only when canonical admissible inputs cannot determine the answer. Coverage and numeric error are reported separately.',
            'exposure': 'Published fixed seeds and source permit reproduction; these are disjoint program-generated controls, not secret or pristine market holdouts.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('refuse to replace an existing control receipt')
    write_json(args.output, run())
    print(args.output)


if __name__ == '__main__':
    main()
