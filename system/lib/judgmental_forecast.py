"""Evidence-conditioned quantiles inside native CP1/CP2; no learned calibration.

q50 is the point forecast, coherent with absolute-error evaluation. Quantile
loss follows Gneiting & Raftery (2007), doi:10.1198/016214506000001437,
using the unscaled pinball convention. Three quantiles do not specify a full
predictive distribution. Source checks certify provenance, not the judgment.
"""
from datetime import datetime, timedelta
import json
import math
from pathlib import Path
import re

from system.lib.empirical_forecast import finite_number
from system.lib.citations import detect_malformed_citations, validate_citations

LEVELS = {'q10': .1, 'q50': .5, 'q90': .9}


def rule_errors(payload):
    rule = payload.get('forecast_quantiles')
    if payload.get('forecast_basis') != 'JUDGMENTAL':
        return ['INVALID_QUANTILES: only JUDGMENTAL may carry forecast_quantiles'] if rule is not None else []
    errors = []
    if payload.get('decision_status', 'FORECAST') != 'FORECAST' or payload.get('dominant_evidence_track') != 'JUDGMENTAL':
        errors.append('INVALID_QUANTILES: FORECAST and JUDGMENTAL evidence track required')
    if 'empirical_rule' in payload:
        errors.append('INVALID_QUANTILES: cannot also carry empirical_rule')
    fields = {'method', 'calendar', 'units', 'calibration_status', 'targets'}
    if not isinstance(rule, dict) or set(rule) != fields:
        return errors + ['INVALID_QUANTILES: exact forecast_quantiles fields required']
    if (rule['method'] != 'evidence_conditioned_quantiles_v1' or rule['calendar'] not in ('XNYS', 'XSHG')
            or rule['units'] != 'simple_return_fraction' or rule['calibration_status'] != 'UNVALIDATED'):
        errors.append('INVALID_QUANTILES: unsupported method, calendar, units or calibration claim')
    targets = rule['targets']
    if not isinstance(targets, list) or not targets:
        return errors + ['INVALID_QUANTILES: nonempty target list required']
    evidence = payload.get('evidence_dictionary', [])
    refs = {e.get('ref_id'): e for e in evidence if isinstance(e, dict) and isinstance(e.get('ref_id'), str)} if isinstance(evidence, list) else {}
    seen = set()
    for row in targets:
        if not isinstance(row, dict) or set(row) != {'target_id', *LEVELS, 'evidence_refs', 'reasoning'}:
            errors.append('INVALID_QUANTILES: exact target fields required')
            continue
        symbol = row['target_id']
        if not isinstance(symbol, str) or not re.fullmatch(r'[A-Z0-9][A-Z0-9.-]*', symbol) or symbol in seen:
            errors.append('INVALID_QUANTILES: unique opaque uppercase target IDs required')
        else:
            seen.add(symbol)
        values = [row[k] for k in LEVELS]
        if any(not finite_number(v) or not -1 < v <= 10 for v in values):
            errors.append('INVALID_QUANTILES: finite return fractions in (-1,10] required')
        elif values != sorted(values):
            errors.append('INVALID_QUANTILES: crossing quantiles')
        cited = row['evidence_refs']
        if not isinstance(cited, list) or not cited or any(not isinstance(r, str) or r not in refs for r in cited):
            errors.append('INVALID_QUANTILES: unresolved evidence refs')
        elif not any(refs[r].get('subject') == symbol and str(refs[r].get('ledger_id', '')).startswith('S_') for r in cited):
            errors.append('INVALID_QUANTILES: original stock grounding required for every target')
        if not isinstance(row['reasoning'], str) or not row['reasoning'].strip():
            errors.append('INVALID_QUANTILES: evidence-to-forecast reasoning required')
        else:
            if detect_malformed_citations(row['reasoning']):
                errors.append('INVALID_QUANTILES: malformed reasoning citation')
            errors.extend(validate_citations(row['reasoning'], evidence))
            if not isinstance(cited, list) or any(ref not in cited for ref in re.findall(r'\[[1-9]\d*\]', row['reasoning'])):
                errors.append('INVALID_QUANTILES: reasoning citations must be declared in target evidence_refs')
    return errors


def locked_evidence(payload):
    """Original citation identities used by the immutable quantile proposal."""
    if payload.get('forecast_basis') != 'JUDGMENTAL' or rule_errors(payload):
        return None
    refs = {ref for row in payload['forecast_quantiles']['targets'] for ref in row['evidence_refs']}
    return {e['ref_id']: {key: e.get(key) for key in ('ledger_id', 'subject', 'source_ref')}
            for e in payload['evidence_dictionary'] if e['ref_id'] in refs}


def target_errors(payload, subject_run_dir, issue_at, target_at):
    if payload.get('forecast_basis') != 'JUDGMENTAL' or rule_errors(payload):
        return []
    try:
        import exchange_calendars as xcals
        if subject_run_dir is None:
            raise ValueError('original source run required')
        root = Path(subject_run_dir)/'artifacts'
        artifact = json.loads((root/'global_stock_feed.json').read_text())
        stock, meta = artifact['data'], artifact.get('metadata', {})
        predictions = payload.get('predictions_t', [])
        if not isinstance(predictions, list) or not predictions or any(not isinstance(p, dict) for p in predictions):
            raise ValueError('nonempty prediction list required')
        issue = datetime.fromisoformat(issue_at or meta.get('as_of', ''))
        target = datetime.fromisoformat(target_at or predictions[0].get('target_time_iso', ''))
        if issue.utcoffset() is None or target.utcoffset() is None:
            raise ValueError('aware timestamps required')
        rule = payload['forecast_quantiles']
        cal = xcals.get_calendar(rule['calendar'], start=(issue.date()-timedelta(days=5)).isoformat(), end=(issue.date()+timedelta(days=20)).isoformat())
        day = issue.astimezone(cal.tz).date().isoformat()
        if not cal.is_session(day):
            raise ValueError('issue must be a source exchange session')
        close = cal.session_close(day).to_pydatetime()
        if not close <= issue <= close+timedelta(minutes=1):
            raise ValueError('issue must be source close or recorded one-minute availability')
        if cal.session_close(cal.next_session(day)).to_pydatetime() != target:
            raise ValueError('target must be next source exchange close')
        columns = stock['columns']
        quotes = {}
        for row in stock['rows']:
            symbol, price = row[columns.index('Ticker')], row[columns.index('Price')]
            if not isinstance(symbol, str) or symbol in quotes or not finite_number(price) or price <= 0:
                raise ValueError('ambiguous or invalid original stock quotes')
            quotes[symbol] = price
        # Bind every cited ledger ID to an original subject-side feed, never later Oracle text.
        originals = {}
        for path in root.glob('global_*_feed.json'):
            feed = json.loads(path.read_text()).get('data', {})
            if not isinstance(feed, dict):
                continue
            for e in feed.get('evidence_dictionary', []):
                if not isinstance(e, dict) or not isinstance(e.get('ledger_id'), str):
                    raise ValueError('invalid original evidence dictionary')
                if e['ledger_id'] in originals:
                    raise ValueError('ambiguous original evidence ID')
                originals[e['ledger_id']] = e
        by_ref = {e['ref_id']: e for e in payload['evidence_dictionary']}
        expected = {r['target_id']: r for r in rule['targets']}
        if len(predictions) != len(expected) or {p.get('target_id') for p in predictions} != set(expected):
            raise ValueError('predictions must cover exactly the CP1 target set')
        history = stock.get('price_history', {})
        for pred in predictions:
            symbol = pred['target_id']; row = expected[symbol]
            for ref in row['evidence_refs']:
                e = by_ref[ref]; original = originals.get(e['ledger_id'])
                if original is None or original.get('subject') != e.get('subject'):
                    raise ValueError('citation identity differs from original source')
                if 'source_ref' in e and e['source_ref'] != original.get('source_ref'):
                    raise ValueError('citation source_ref differs from original source')
            bars = history.get(symbol, []) if isinstance(history, dict) else history
            if not bars or bars[-1].get('session_date') != day or bars[-1].get('price', bars[-1].get('close')) != quotes[symbol]:
                raise ValueError('quote must equal observed source session closing bar')
            q50 = row['q50']; price = quotes[symbol]*(1+q50)
            for key, value in (('snapshot_price', quotes[symbol]), ('target_price', price)):
                if not finite_number(pred.get(key)) or not math.isclose(pred[key], value, rel_tol=1e-9, abs_tol=1e-7):
                    raise ValueError('median target arithmetic mismatch: '+symbol+'/'+key)
            direction = 'UP' if q50 > 0 else 'DOWN' if q50 < 0 else 'FLAT'
            if pred.get('direction') != direction:
                raise ValueError('direction must be sign of median estimate')
            if datetime.fromisoformat(pred.get('snapshot_time', '')) != issue or datetime.fromisoformat(pred.get('target_time_iso', '')) != target:
                raise ValueError('prediction clocks differ from source issue and next close')
        return []
    except (ValueError, KeyError, TypeError, IndexError, OSError, OverflowError, AttributeError) as exc:
        return ['INVALID_QUANTILE_TARGET: '+str(exc)]


def score_quantiles(row, realized_return):
    losses = {key: max(p*(realized_return-row[key]), (p-1)*(realized_return-row[key])) for key, p in LEVELS.items()}
    return {'realized_simple_return': realized_return, 'quantile_pinball_losses': losses,
            'mean_quantile_pinball_loss': math.fsum(losses.values())/len(losses),
            'interval_80_covered': row['q10'] <= realized_return <= row['q90'],
            'interval_80_width': row['q90']-row['q10'],
            'quantile_units': 'simple_return_fraction', 'calibration_status': 'UNVALIDATED'}


def verify_truth(payload, subject_run_dir, truth_run_dir):
    """Use the existing feedback observation parser before Oracle learns a loss."""
    import importlib.metadata
    from feedback.engine import dated_rows, observation_time, timestamp
    sources = [dated_rows(Path(root)/'artifacts/global_stock_feed.json')
               for root in (subject_run_dir, truth_run_dir)]
    for prediction in payload['predictions_t']:
        matches = [[r for r in rows if r['target_id'] == prediction['target_id']] for rows in sources]
        if any(len(rows) != 1 for rows in matches):
            raise ValueError('Judgmental truth requires one exact source and truth quote per target')
        subject, truth = [rows[0] for rows in matches]
        if any(not subject.get(k) or subject[k] != truth[k] for k in ('price_basis', 'currency')):
            raise ValueError('Judgmental truth price basis/currency mismatch')
        raw = truth['observed']
        precision = 'session_close' if isinstance(raw, str) and re.fullmatch(r'\d{4}-\d{2}-\d{2}', raw) else 'timestamp'
        policy = {'observation_precision': precision, 'calendar_id': payload['forecast_quantiles']['calendar'],
                  'calendar_version': importlib.metadata.version('exchange_calendars')}
        if observation_time(raw, policy) != timestamp(prediction['target_time_iso']):
            raise ValueError('Judgmental truth must be the exact forecast target close')
        if not finite_number(truth['price']) or truth['price'] <= 0:
            raise ValueError('Judgmental truth requires a positive finite quote')
