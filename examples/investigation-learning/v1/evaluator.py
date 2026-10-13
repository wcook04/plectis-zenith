"""Synthetic operational investigations with an independent, latent-data oracle.

Inputs are measurements and source contracts, never labels or generator options.
The oracle evaluates latent intervals by elementary endpoint cells; it does not
execute or import a candidate's computation. Synthetic transfer is not field evidence.
"""
import math
import random

QUANTITIES = {
    'active': 'Measure time during which at least one child operation is active within a request. Simultaneous work occupies the same time, and idle gaps do not count.',
    'wall': 'Measure elapsed time from the first child operation starting to the last child operation ending within a request. Idle gaps count.',
    'work': 'Measure billed worker time per request. Every distinct child operation contributes its full duration, including simultaneous work on separate workers.'}
FIELDS = {'native': ['rid', 'sid', 'cohort', 't0', 't1'],
          'foreign': ['journey', 'emission', 'lane', 'opened', 'closed']}
TASK = '''Investigate the change in the requested per-request quantity. Compare after to before using the BEFORE request-population proportions over workload classes in BOTH periods. Give the ratio of the standardized after mean to the standardized before mean. A ratio strictly above 1.2 establishes latency_regression, strictly below 0.8 latency_improvement, otherwise latency_stable. Use a 1e-8 tolerance at those boundaries. These names also apply to billed work when that is the requested quantity.
Also retain independent findings: duplicate_delivery if an identical operation record appears more than once; workload_shift if the population class proportions differ. Multiple findings can coexist. Operation IDs are scoped within a period; identical repeats describe the same operation, not new work. Conflicting records for the same operation ID leave conflicting_event unresolved. The population table is authoritative and includes successful AND failed requests. A mismatch between observed distinct requests per class and population counts leaves incomplete_coverage unresolved; unknown time units leave unknown_clock_unit unresolved. In any unresolved case ratio must be null and no latency conclusion is permitted, but retain independently established duplicate_delivery and workload_shift. Empty unresolved means a numerical conclusion is required. Only these labels are allowed. Return exactly findings (list), unresolved (list), ratio (number or null).'''


def interval_quantity(intervals, kind):
    if kind == 'wall':
        return max(b for a, b in intervals) - min(a for a, b in intervals)
    if kind == 'work':
        return sum(b-a for a, b in intervals)
    endpoints = sorted({x for interval in intervals for x in interval})
    return sum(b-a for a, b in zip(endpoints, endpoints[1:])
               if any(left <= (a+b)/2 < right for left, right in intervals))


def make_case(seed, *, kind='active', overlap=False, gaps=False, duplicate=False,
              shift=False, units=False, missing=False, unknown=False, conflict=False,
              ratio=1.0, schema='native', heterogeneous=False):
    rng = random.Random(seed)
    before_counts = {'small': 2, 'large': 2}
    after_counts = {'small': 1, 'large': 3} if shift else dict(before_counts)
    populations = {'before': before_counts, 'after': after_counts}
    names = FIELDS[schema]
    rows, latent = [], {}
    factor = rng.uniform(6, 15)
    class_effect = rng.uniform(.8, 1.25) if heterogeneous else 1.
    for period in ['before', 'after']:
        latent[period] = {}
        for cohort, count in populations[period].items():
            for i in range(count):
                rid = f'{cohort}-{i}'
                # Same within-class latent distribution, independent variation between cases.
                length = factor * (1 if cohort == 'small' else 3)
                scale = ratio * (class_effect if cohort == 'large' else 1) if period == 'after' else 1
                # Change the overlap pattern after deployment, not only total duration.
                intervals = [(0, length), (length, 2*length), (2*length, 3*length)]
                if overlap and period == 'after':
                    intervals = [(0, 2*length), (.5*length, 2.5*length), (length, 3*length)]
                if gaps:
                    intervals = [(0, length), (2*length, 3*length), (4*length, 5*length)]
                    if overlap and period == 'after':
                        intervals = [(0, 2*length), (length, 3*length), (4*length, 5*length)]
                intervals = [(a*scale, b*scale) for a, b in intervals]
                latent[period][rid] = (cohort, intervals)
                if missing and period == 'after' and rid == 'small-0':
                    continue
                for j, (a, b) in enumerate(intervals):
                    multiplier = 1000 if units and period == 'after' else 1
                    values = [rid, f'{rid}-{j}', cohort, a*multiplier, b*multiplier]
                    rows.append({'period': period, **dict(zip(names, values))})
    if duplicate:
        rows += [dict(rows[-1]), dict(rows[-2])]
    if conflict:
        altered = dict(rows[-3]); altered[names[-1]] += 10
        rows.append(altered)
    rng.shuffle(rows)
    population = [{'period': p, 'class': c, 'count': n} for p, values in populations.items() for c, n in values.items()]
    context = {
        'id': f'case-{seed}', 'quantity_contract': QUANTITIES[kind],
        'source_documentation': f'Table spans: period is before or after; {names[0]} identifies a request, {names[1]} a child operation, {names[2]} the workload class, {names[3]} the interval start, {names[4]} its end. Table population: period, class, count (all requests). Clocks are consistent within each period.',
        'clock_units': {'before': 'milliseconds', 'after': 'unknown' if unknown else 'microseconds' if units else 'milliseconds'},
        'available_tables': ['spans', 'population'],
        'tables': {'spans': rows, 'population': population}}
    unresolved = sorted((['incomplete_coverage'] if missing else []) + (['unknown_clock_unit'] if unknown else []) + (['conflicting_event'] if conflict else []))
    findings = (['duplicate_delivery'] if duplicate else []) + (['workload_shift'] if shift else [])
    actual_ratio = None
    if not unresolved:
        means = {}
        for p, requests in latent.items():
            means[p] = sum(before_counts[c] / sum(before_counts.values()) *
                           sum(interval_quantity(intervals, kind) for cl, intervals in requests.values() if cl == c) /
                           populations[p][c] for c in before_counts)
        actual_ratio = means['after']/means['before']
        findings.append('latency_regression' if actual_ratio > 1.2+1e-8 else 'latency_improvement' if actual_ratio < .8-1e-8 else 'latency_stable')
    return context, {'findings': sorted(findings), 'unresolved': unresolved, 'ratio': actual_ratio}


FAMILIES = [
    {'kind': 'active'}, {'kind': 'active', 'overlap': True},
    {'kind': 'wall', 'gaps': True}, {'kind': 'work', 'overlap': True},
    {'kind': 'active', 'duplicate': True}, {'kind': 'active', 'units': True},
    {'kind': 'active', 'shift': True}, {'kind': 'active', 'missing': True},
    {'kind': 'wall', 'unknown': True}, {'kind': 'work', 'conflict': True},
    {'kind': 'active', 'overlap': True, 'duplicate': True, 'shift': True, 'units': True},
    {'kind': 'wall', 'overlap': True, 'gaps': True, 'duplicate': True, 'missing': True, 'shift': True},
    {'kind': 'work', 'overlap': True, 'duplicate': True, 'units': True, 'shift': True},
    {'kind': 'active', 'unknown': True, 'conflict': True, 'duplicate': True},
    {'kind': 'wall', 'missing': True, 'unknown': True, 'duplicate': True, 'conflict': True},
    {'kind': 'work', 'gaps': True, 'shift': True}]


def suite(seed, count=256, schema='native'):
    return [make_case(seed+i, **FAMILIES[i % len(FAMILIES)], ratio=[.65, 1., 1.4, 1.2][(i // len(FAMILIES)) % 4], schema=schema, heterogeneous=True)
            for i in range(count)]


def novel_suite(seed, count=256, schema='native'):
    """Previously unseen combinations of known semantic factors, half unresolved."""
    import itertools
    rng = random.Random(seed)
    flags = ['overlap', 'gaps', 'duplicate', 'shift', 'units', 'missing', 'unknown', 'conflict']
    known = {(f['kind'], *(bool(f.get(k)) for k in flags)) for f in FAMILIES}
    pools = {False: [], True: []}
    for kind in QUANTITIES:
        for bits in itertools.product([False, True], repeat=len(flags)):
            if (kind, *bits) not in known:
                pools[any(bits[-3:])].append({'kind': kind, **dict(zip(flags, bits))})
    for pool in pools.values():
        rng.shuffle(pool)
    return [make_case(seed+i, **pools[bool(i % 2)][(i//2) % len(pools[bool(i % 2)])],
                      ratio=rng.uniform(.55, 1.65), schema=schema, heterogeneous=True) for i in range(count)]


def rename_fields(case, mapping, documentation):
    """Mapping-only semantic adapter: cannot change the frozen computation or values."""
    if set(mapping) != set(FIELDS['native']) or set(mapping.values()) != set(FIELDS['foreign']):
        raise ValueError('adapter must be a bijection between documented field sets')
    reverse = {value: key for key, value in mapping.items()}
    return {**case, 'source_documentation': documentation,
            'tables': {**case['tables'], 'spans': [{reverse.get(k, k): v for k, v in row.items()} for row in case['tables']['spans']]}}


def grade(expected, actual):
    if not isinstance(actual, dict):
        return {'correct': False, 'claims_correct': False, 'ratio_correct': False}
    claims = sorted(actual.get('findings', [])) == expected['findings'] and sorted(actual.get('unresolved', [])) == expected['unresolved']
    ratio = actual.get('ratio')
    numeric = (ratio is None if expected['ratio'] is None else
               type(ratio) in (int, float) and math.isfinite(ratio) and math.isclose(ratio, expected['ratio'], rel_tol=.01, abs_tol=.005))
    return {'correct': claims and numeric, 'claims_correct': claims, 'ratio_correct': numeric}


def typed_reference(case):
    """Engineered code-only ceiling using exactly the observed tables and contracts."""
    names = FIELDS['foreign' if 'journey' in case['source_documentation'] else 'native']
    pop = {(r['period'], r['class']): r['count'] for r in case['tables']['population']}
    classes = {cl for period, cl in pop}
    proportions = {period: {cl: pop[period, cl] / sum(n for (p, c), n in pop.items() if p == period) for cl in classes}
                   for period in ['before', 'after']}
    findings, unresolved, unique = set(), set(), {}
    if proportions['before'] != proportions['after']:
        findings.add('workload_shift')
    for row in case['tables']['spans']:
        key = (row['period'], row[names[1]])
        if key in unique:
            if row == unique[key]:
                findings.add('duplicate_delivery')
            else:
                unresolved.add('conflicting_event')
        else:
            unique[key] = row
    requests = {}
    for row in unique.values():
        requests.setdefault((row['period'], row[names[0]], row[names[2]]), []).append((row[names[3]], row[names[4]]))
    for (period, cl), count in pop.items():
        if sum(p == period and c == cl for p, request, c in requests) != count:
            unresolved.add('incomplete_coverage')
    scales = {'milliseconds': 1., 'microseconds': .001}
    if any(unit not in scales for unit in case['clock_units'].values()):
        unresolved.add('unknown_clock_unit')
    ratio = None
    if not unresolved:
        contract = case['quantity_contract']
        values = {}
        for (p, rid, cl), spans in requests.items():
            if contract == QUANTITIES['wall']:
                value = max(b for a, b in spans) - min(a for a, b in spans)
            elif contract == QUANTITIES['work']:
                value = sum(b-a for a, b in spans)
            else:
                # Merge sorted intervals; independent of the endpoint-cell latent oracle.
                intervals = sorted(spans); start, end = intervals[0]; value = 0
                for a, b in intervals[1:]:
                    if a > end:
                        value += end-start; start, end = a, b
                    else:
                        end = max(end, b)
                value += end-start
            values.setdefault((p, cl), []).append(value*scales[case['clock_units'][p]])
        means = {p: sum(proportions['before'][cl] * sum(values[p, cl])/len(values[p, cl]) for cl in classes) for p in ['before', 'after']}
        ratio = means['after']/means['before']
        findings.add('latency_regression' if ratio > 1.2+1e-8 else 'latency_improvement' if ratio < .8-1e-8 else 'latency_stable')
    return {'findings': sorted(findings), 'unresolved': sorted(unresolved), 'ratio': ratio}


INCUMBENT = '''def investigate(context, acquire):
    spans = acquire("spans")
    totals = {"before": {}, "after": {}}
    for row in spans:
        period = row["period"]
        rid = row["rid"]
        totals[period][rid] = totals[period].get(rid, 0) + row["t1"] - row["t0"]
    means = {}
    for period in totals:
        means[period] = sum(totals[period].values()) / len(totals[period])
    ratio = means["after"] / means["before"]
    finding = "latency_regression" if ratio > 1.2 + 1e-8 else "latency_improvement" if ratio < .8 - 1e-8 else "latency_stable"
    return {"findings": [finding], "unresolved": [], "ratio": ratio}
'''
