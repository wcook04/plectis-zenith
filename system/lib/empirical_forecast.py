"""A declared empirical control inside the native graph, never a causal claim.

The first supported operator is deliberately narrow. It applies a frozen scale
and cap to the arithmetic mean of trailing simple returns. It does not select
parameters, learn weights, fetch data or establish predictive value.
"""
from datetime import date, datetime, timedelta
import json
import math
from pathlib import Path
import re


def finite_number(value):
    try:
        return type(value) in (int, float) and math.isfinite(value)
    except OverflowError:
        return False


def rule_errors(payload):
    basis = payload.get('forecast_basis', 'CAUSAL')
    if basis == 'JUDGMENTAL':
        return []  # Validated by the separate native quantile contract.
    if basis not in ('CAUSAL', 'EMPIRICAL'):
        return ['INVALID_FORECAST_BASIS: expected CAUSAL, EMPIRICAL or JUDGMENTAL']
    if basis != 'EMPIRICAL':
        if payload.get('dominant_evidence_track') == 'EMPIRICAL':
            return ['INVALID_EMPIRICAL_RULE: EMPIRICAL track requires explicit basis']
        return ['INVALID_EMPIRICAL_RULE: CAUSAL cannot carry empirical_rule'] if 'empirical_rule' in payload else []
    errors = []
    if payload.get('decision_status', 'FORECAST') != 'FORECAST':
        errors.append('INVALID_EMPIRICAL_RULE: empirical rule requires FORECAST')
    if payload.get('dominant_evidence_track') != 'EMPIRICAL':
        errors.append('INVALID_EMPIRICAL_RULE: empirical forecast requires EMPIRICAL evidence track')
    rule = payload.get('empirical_rule')
    required = {'method', 'lookback_returns', 'scale', 'max_abs_return', 'target_ids',
                'evidence_refs', 'selection_basis', 'calibration_status'}
    if not isinstance(rule, dict) or set(rule) != required:
        return errors + ['INVALID_EMPIRICAL_RULE: exact declared rule fields required']
    if rule['method'] != 'trailing_mean_return_v1':
        errors.append('INVALID_EMPIRICAL_RULE: unsupported method')
    if type(rule['lookback_returns']) is not int or not 1 <= rule['lookback_returns'] <= 19:
        errors.append('INVALID_EMPIRICAL_RULE: lookback_returns must be integer 1..19')
    for key in ('scale', 'max_abs_return'):
        v = rule[key]
        if not finite_number(v):
            errors.append('INVALID_EMPIRICAL_RULE: finite numeric ' + key + ' required')
        elif (key == 'scale' and not 0 < abs(v) <= 1) or (key == 'max_abs_return' and not 0 < v <= .1):
            errors.append('INVALID_EMPIRICAL_RULE: parameter outside declared bounds: ' + key)
    targets = rule['target_ids']
    if (not isinstance(targets, list) or not targets or
        any(not isinstance(t, str) or not re.fullmatch(r'[A-Z][A-Z0-9.-]*', t) for t in targets)):
        errors.append('INVALID_EMPIRICAL_RULE: nonempty uppercase targets required')
    elif len(set(targets)) != len(targets):
        errors.append('INVALID_EMPIRICAL_RULE: duplicate targets')
    refs = rule['evidence_refs']
    evidence = payload.get('evidence_dictionary', [])
    allowed = {e['ref_id']: e for e in evidence if isinstance(e, dict) and isinstance(e.get('ref_id'), str)} if isinstance(evidence, list) else {}
    if (not isinstance(refs, list) or not refs or
        any(not isinstance(r, str) or r not in allowed for r in refs)):
        errors.append('INVALID_EMPIRICAL_RULE: unresolved evidence_refs')
    elif isinstance(targets, list):
        for target in targets:
            if not any(allowed[r].get('subject') == target and str(allowed[r].get('ledger_id', '')).startswith('S_') for r in refs):
                errors.append('INVALID_EMPIRICAL_RULE: missing stock evidence for ' + str(target))
    if not isinstance(rule['selection_basis'], str) or not rule['selection_basis'].strip():
        errors.append('INVALID_EMPIRICAL_RULE: selection_basis required')
    if rule['calibration_status'] != 'UNVALIDATED':
        errors.append('INVALID_EMPIRICAL_RULE: this control does not certify calibrated or learned value')
    return errors


def calculate(rule, stock, issue_at, target_at):
    """Return independently recomputed targets from native as-of stock history."""
    import exchange_calendars as xcals
    issue, target = datetime.fromisoformat(issue_at), datetime.fromisoformat(target_at)
    if issue.utcoffset() is None or target.utcoffset() is None:
        raise ValueError('timezone-aware boundaries required')
    day = issue.date().isoformat()
    cal = xcals.get_calendar('XNYS', start=day, end=(issue.date()+timedelta(days=14)).isoformat())
    if not cal.is_session(day) or cal.session_close(day).to_pydatetime() != issue:
        raise ValueError('empirical control requires an XNYS issue close')
    if cal.session_close(cal.next_session(day)).to_pydatetime() != target:
        raise ValueError('empirical control requires the next XNYS close')
    if not isinstance(stock, dict):
        raise ValueError('stock data must be an object')
    history = stock.get('price_history')
    # InvestorBench has a symbol map; the original FNSPID AA slice has one list.
    if isinstance(history, list):
        columns, rows = stock.get('columns', []), stock.get('rows', [])
        if len(rows) != 1 or 'Ticker' not in columns:
            raise ValueError('single-history issuer is ambiguous')
        history = {rows[0][columns.index('Ticker')]: history}
    if not isinstance(history, dict):
        raise ValueError('observed price_history required')
    result = {}
    for symbol in rule['target_ids']:
        rows = history.get(symbol, [])
        n = rule['lookback_returns']
        if not isinstance(rows, list) or len(rows) < n+1 or any(not isinstance(r, dict) for r in rows):
            raise ValueError('insufficient history for ' + symbol)
        rows = rows[-n-1:]
        dates = [date.fromisoformat(r['session_date']) for r in rows]
        # An expanded calendar verifies consecutive history, including holidays.
        past = xcals.get_calendar('XNYS', start=dates[0].isoformat(), end=day)
        expected = [s.date() for s in past.sessions_in_range(dates[0].isoformat(), day)]
        if dates != expected or dates[-1] != issue.date():
            raise ValueError('history must be consecutive and end at the issue close')
        prices = [r.get('price', r.get('close')) for r in rows]
        if any(not finite_number(p) or p <= 0 for p in prices):
            raise ValueError('finite positive observed prices required')
        mean = math.fsum(b/a - 1 for a,b in zip(prices, prices[1:]))/n
        scaled = rule['scale']*mean
        predicted_return = max(-rule['max_abs_return'], min(rule['max_abs_return'], scaled))
        target_price = prices[-1]*(1+predicted_return)
        if not all(finite_number(v) for v in (mean, scaled, target_price)):
            raise ValueError('nonfinite derived arithmetic')
        result[symbol] = {'snapshot_price': prices[-1], 'mean_simple_return': mean,
                          'predicted_return': predicted_return,
                          'target_price': target_price}
    return result


def target_errors(payload, subject_run_dir, issue_at, target_at):
    if payload.get('forecast_basis', 'CAUSAL') != 'EMPIRICAL' or rule_errors(payload):
        return []
    try:
        if subject_run_dir is None:
            raise ValueError('source run required for empirical validation')
        artifact = json.loads((Path(subject_run_dir)/'artifacts/global_stock_feed.json').read_text())
        if not isinstance(artifact, dict) or not isinstance(artifact.get('data'), dict):
            raise ValueError('stock artifact and data must be objects')
        stock = artifact['data']
        predictions = payload.get('predictions_t', [])
        if not isinstance(predictions, list) or not predictions or any(not isinstance(p, dict) for p in predictions):
            raise ValueError('nonempty prediction objects required')
        metadata = artifact.get('metadata', {})
        if not isinstance(metadata, dict):
            raise ValueError('stock metadata must be an object')
        issue_at = issue_at or metadata.get('as_of')
        target_at = target_at or (predictions[0].get('target_time_iso') if predictions else None)
        if not issue_at or not target_at:
            raise ValueError('source issue and target times required')
        if any(datetime.fromisoformat(p.get('snapshot_time', '')) != datetime.fromisoformat(issue_at)
               or datetime.fromisoformat(p.get('target_time_iso', '')) != datetime.fromisoformat(target_at) for p in predictions):
            raise ValueError('prediction times must match the source issue and next close')
        source_evidence = stock.get('evidence_dictionary', [])
        if (not isinstance(source_evidence, list) or any(not isinstance(e, dict) or
                not isinstance(e.get('ledger_id'), str) for e in source_evidence)):
            raise ValueError('original stock evidence dictionary required')
        source_by_id = {e['ledger_id']: e for e in source_evidence}
        if len(source_by_id) != len(source_evidence):
            raise ValueError('ambiguous original stock evidence IDs')
        refs = set(payload['empirical_rule']['evidence_refs'])
        for entry in payload['evidence_dictionary']:
            if entry['ref_id'] in refs:
                original = source_by_id.get(entry['ledger_id'])
                if original is None or entry.get('subject') != original.get('subject'):
                    raise ValueError('empirical input citation issuer not bound to original stock feed')
                if 'source_ref' in entry and entry['source_ref'] != original.get('source_ref'):
                    raise ValueError('empirical input source_ref differs from original stock feed')
        expected = calculate(payload['empirical_rule'], stock, issue_at, target_at)
        if (not isinstance(predictions, list) or any(not isinstance(p, dict) for p in predictions)
            or len(predictions) != len(expected) or {p.get('target_id') for p in predictions} != set(expected)):
            raise ValueError('predictions must cover the exact locked rule target set')
        for prediction in predictions:
            row = expected[prediction['target_id']]
            for key in ('snapshot_price', 'target_price'):
                actual = prediction.get(key)
                if (not finite_number(actual)
                    or not math.isclose(actual, row[key], rel_tol=1e-9, abs_tol=1e-7)):
                    raise ValueError('target arithmetic mismatch: ' + prediction['target_id'] + '/' + key)
        return []
    except (ValueError, KeyError, TypeError, IndexError, OSError, OverflowError) as exc:
        return ['INVALID_EMPIRICAL_TARGET: ' + str(exc)]
