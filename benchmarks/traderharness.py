"""Point-in-time A-share packets and separately held gross wealth labels.

No inference, acquisition or trading. Archived publication metadata is not a
historical text-vintage certificate. Cash is a gross receivable on the ex-date;
bonus shares are marked then, not asserted to be immediately tradable.
"""
from __future__ import annotations

from bisect import bisect_right
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import hashlib
import math
from pathlib import Path
import re
from zoneinfo import ZoneInfo

import exchange_calendars as xcals

from benchmarks.trading_task import FEATURES as STOCK_FEATURES, state_features
from benchmarks.stocknet import fit_ridge, ridge_predict
from research.engine import canonical, read_json

ROOT = Path(__file__).resolve().parents[1]
SHANGHAI = ZoneInfo('Asia/Shanghai')
SYMBOLS = sorted(['600519', '601012', '002594', '002466', '600111',
                  '000858', '601919', '002460', '600031', '600438'])
SPLITS = {'training': ['2023-02-01', '2024-01-01'],
          'validation': ['2024-01-01', '2025-01-01'],
          'test': ['2025-01-01', '2026-01-01']}
TABLES = ('daily', 'announcements', 'news_cls', 'dividends', 'index_300')
FEATURES = STOCK_FEATURES + ['csi300_return_5', 'csi300_return_20', 'csi300_volatility_20']


def market_features(dates, benchmark):
    closes = [benchmark[d]['close'] for d in dates]
    changes = [b / a - 1 for a, b in zip(closes, closes[1:])]
    mean = math.fsum(changes) / len(changes)
    return [closes[-1] / closes[-6] - 1, closes[-1] / closes[0] - 1,
            math.sqrt(math.fsum((v - mean) ** 2 for v in changes) / len(changes))]


def sha(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def day(value):
    return str(value)[:10]


def iso(value):
    return value.astimezone(timezone.utc).isoformat()


def valid_bar(row):
    if row is None:
        return False
    fields = ['open', 'high', 'low', 'close', 'volume']
    return (all(isinstance(row.get(k), (int, float)) and math.isfinite(row[k]) for k in fields)
            and min(row[k] for k in fields[:4]) > 0 and row['volume'] > 0
            and row['low'] <= min(row['open'], row['close'])
            <= max(row['open'], row['close']) <= row['high'])


def action_terms(row):
    values = [Decimal(str(row[k])) for k in ('bonus_shares', 'transfer_shares', 'cash_dividend')]
    if any(not v.is_finite() or v < 0 for v in values):
        raise ValueError('invalid action amount')
    return Decimal(1) + (values[0] + values[1]) / 10, values[2] / 10


def normalize_actions(rows, symbols):
    result = defaultdict(list)
    seen = set()
    for raw in rows:
        if raw['stock_code'] not in symbols or not raw.get('ex_date'):
            continue
        if raw.get('progress') != '实施':
            continue
        row = {k: raw[k] for k in ('stock_code', 'bonus_shares', 'transfer_shares', 'cash_dividend')}
        row.update({k: day(raw[k]) for k in ('ann_date', 'record_date', 'ex_date')})
        if not row['ann_date'] <= row['record_date'] < row['ex_date']:
            raise ValueError('ambiguous action announcement/entitlement clocks')
        action_terms(row)
        key = (row['stock_code'], row['ex_date'])
        if key in seen:
            raise ValueError('duplicate corporate action: reconcile instead of double-crediting')
        seen.add(key)
        result[row['stock_code']].append(row)
    return {s: sorted(result[s], key=lambda a: a['ex_date']) for s in symbols}


def wealth_return(entry, exit_date, lookup, actions):
    """One share bought at entry open. Previous holders' rights are excluded."""
    shares, cash = Decimal(1), Decimal(0)
    applied = []
    for action in actions:
        if entry < action['ex_date'] <= exit_date:
            if action['record_date'] < entry:
                raise ValueError('entry misses record-date entitlement')
            factor, distribution = action_terms(action)
            cash += shares * distribution
            shares *= factor
            applied.append(action)
    opening = Decimal(str(lookup[entry]['open']))
    terminal = shares * Decimal(str(lookup[exit_date]['close'])) + cash
    return float(terminal / opening - 1), {
        'entry_open': float(opening), 'exit_close': lookup[exit_date]['close'],
        'terminal_shares': str(shares), 'cash_receivable': str(cash),
        'actions': applied, 'entitlement': 'entry <= record_date < ex_date <= exit; entry at ex open excluded'}


def history_view(dates, lookup, actions):
    """OHLC wealth marks for a holder at the preceding close, rebased to one.

    Uses only ex-dates and announcements inside the historical cutoff. Cash is
    not reinvested. Volume is divided by the contemporaneous share multiplier,
    then normalized within the window; no cross-era share/lot units are assumed.
    """
    before, last = dates[0], dates[-1]
    historical = {a['ex_date']: a for a in actions
                  if before < a['ex_date'] <= last and a['ann_date'] <= last}
    shares, cash = Decimal(1), Decimal(0)
    scale = Decimal(str(lookup[before]['close']))
    bars = []
    for stamp in dates[1:]:
        if stamp in historical:
            factor, distribution = action_terms(historical[stamp])
            cash += shares * distribution
            shares *= factor
        bar = {key.title(): float((shares * Decimal(str(lookup[stamp][key])) + cash) / scale)
               for key in ('open', 'high', 'low', 'close')}
        bar['Volume'] = lookup[stamp]['volume'] / float(shares)
        bars.append(bar)
    volume_mean = math.fsum(b['Volume'] for b in bars) / len(bars)
    for b in bars:
        b['Volume'] /= volume_mean
    return bars, 1.0


def read_sources(directory):
    """Read pinned originals, never trust an unbound derived panel."""
    import pyarrow.parquet as pq
    manifest = read_json(ROOT / 'docs/data-selection-intraday.json')['candidates'][0]
    expected = {Path(r['path']).stem: r['sha256'] for r in manifest['files']}
    hashes, tables = {}, {}
    for name in TABLES:
        path = directory / f'harness_{name}.parquet'
        hashes[name] = hashlib.sha256(path.read_bytes()).hexdigest()
        if hashes[name] != expected[name]:
            raise ValueError(f'pinned source hash differs: {name}')
        filters = [('stock_code', 'in', SYMBOLS)] if name in ('daily', 'announcements', 'dividends') else None
        tables[name] = pq.read_table(path, filters=filters).to_pylist()
    return tables, hashes


def text_index(tables, sessions, calendar, symbols):
    """Explicit source clocks; publication time never inferred from host timezone."""
    records, audit = [], Counter()
    for raw in tables['news_cls']:
        if raw.get('content_source') != 'derived_headline' or not raw.get('title'):
            audit['excluded_redacted_or_unverified_news'] += 1
            continue
        published = datetime.fromtimestamp(int(raw['ctime']), timezone.utc)
        local = published.astimezone(SHANGHAI).replace(tzinfo=None)
        if local != raw['display_time']:
            audit['news_epoch_display_mismatch'] += 1
        content = raw['title'].strip()
        entities = sorted(set(re.findall(r'\{\{C(\d{6})\}\}', content)))
        records.append({'id': 'news_' + str(raw['id']), 'kind': 'news',
                        'available_at': iso(published), 'published_date': local.date().isoformat(),
                        'availability_basis': 'observed_timestamp', 'precision': 'epoch_seconds',
                        'content': content, 'entities': entities, 'source_sha256': sha({
                            'id': int(raw['id']), 'ctime': int(raw['ctime']), 'content': content})})
        audit['admissible_news_records'] += 1
    for raw in tables['announcements']:
        if raw['stock_code'] not in symbols or not raw.get('title'):
            continue
        published = raw['announcement_time']
        date_only = published.time() == datetime.min.time()
        if date_only:
            index = bisect_right(sessions, day(published))
            if index == len(sessions):
                continue
            available = calendar.session_open(sessions[index]).to_pydatetime()
        else:
            available = published.replace(tzinfo=SHANGHAI)
        content = raw['title'].strip()
        identity = {'stock_code': raw['stock_code'], 'title': content,
                    'announcement_time': str(published), 'pdf_url': raw['pdf_url']}
        records.append({'id': 'announcement_' + sha(identity)[:20], 'kind': 'filing',
                        'available_at': iso(available), 'published_date': day(published),
                        'availability_basis': 'date_only_approximate' if date_only else 'observed_timestamp',
                        'precision': 'day' if date_only else 'local_seconds_assumed_shanghai',
                        'content': content, 'entities': [raw['stock_code']],
                        'source_sha256': sha(identity)})
        audit['day_precision_announcements' if date_only else 'timed_announcements'] += 1
    # Independent of source iteration order, prices, outcomes and assessment scores.
    records.sort(key=lambda r: (r['available_at'], r['id']))
    return records, dict(audit)


def profit_period(content, published_date):
    """Conservative retrieval key, not an authenticated accounting fact.

    Scope year to the profit clause. A later '2022 annual dividend' clause must
    not relabel a current-year Q1 profit. Annual or ambiguous periods abstain.
    """
    for clause in re.split(r'[。；;！!？?，,]', content):
        # A clause may append another year's annual-report/dividend statement.
        clause = re.split(r'\s+(?=20\d{2}年年报)', clause)[0]
        if not re.search(r'净利(?:润)?', clause) or not re.search(r'\d+(?:\.\d+)?\s*(?:%|％|亿|万)', clause):
            continue
        matches = list(re.finditer(r'(?:((?:20)\d{2})\s*年\s*)?(第一季度|一季度|Q1|上半年|半年度|H1|前三季度)', clause))
        if len(matches) != 1:
            continue
        match = matches[0]
        period = {'第一季度': 'Q1', '一季度': 'Q1', 'Q1': 'Q1',
                  '上半年': 'H1', '半年度': 'H1', 'H1': 'H1', '前三季度': 'Q1-Q3'}[match[2]]
        year = match[1] or published_date[:4]
        return {'family': 'profit', 'year': year, 'period': period,
                'year_basis': 'explicit_period_year' if match[1] else 'publication_year_for_intrayear_period'}
    return None


def prior_comparisons(records, chosen, cutoff, symbol):
    """At most two original prior claims; no semantic/surprise certification."""
    additions, pairs = [], []
    seen = {r['id'] for r in chosen}
    normalized = {re.sub(r'\s+', '', r['content']) for r in chosen}
    for current in chosen:
        if current['scope'] != 'issuer':
            continue
        key = profit_period(current['content'], current.get('published_date', current['available_at'][:10]))
        if key is None:
            continue
        lower = iso(datetime.fromisoformat(current['available_at']) - timedelta(days=180))
        candidates = []
        for r in records:
            if symbol not in r['entities'] or not lower < r['available_at'] < current['available_at'] <= cutoff:
                continue
            other = profit_period(r['content'], r.get('published_date', r['available_at'][:10]))
            if other and all(other[k] == key[k] for k in ('family', 'year', 'period')):
                if re.sub(r'\s+', '', r['content']) != re.sub(r'\s+', '', current['content']):
                    candidates.append(r)
        if not candidates:
            continue
        prior = max(candidates, key=lambda r: (r['available_at'], r['id']))
        if prior['id'] not in seen:
            if len(additions) == 2 or re.sub(r'\s+', '', prior['content']) in normalized:
                continue
            additions.append({**prior, 'scope': 'prior_comparison', 'content': prior['content'][:600]})
            seen.add(prior['id'])
            normalized.add(re.sub(r'\s+', '', prior['content']))
        pairs.append({'current_id': current['id'], 'prior_id': prior['id'], 'key': key,
                      'basis': 'same source issuer candidate token and profit-period key; identity/metric comparability unverified',
                      'prior_role': 'explicit_issuer_estimate' if re.search(r'预计|预告', prior['content']) else 'earlier_claim'})
    return additions, pairs


def select_text(records, cutoff, symbol, *, after=None):
    lower = iso(datetime.fromisoformat(cutoff) - timedelta(days=7))
    if after is not None:
        lower = after
    eligible = [r for r in records if lower < r['available_at'] <= cutoff]
    issuer = [r for r in eligible if symbol in r['entities']]
    common = [r for r in eligible if not r['entities'] and r['kind'] == 'news']
    chosen, seen = [], set()
    for lane, candidates, limit in [('issuer', issuer, 4), ('common', common, 2)]:
        count = 0
        for row in reversed(candidates):
            normalized = re.sub(r'\s+', '', row['content'])
            if normalized in seen:
                continue
            seen.add(normalized)
            chosen.append({**row, 'scope': lane, 'content': row['content'][:600]})
            count += 1
            if count == limit:
                break
    additions, pairs = prior_comparisons(records, chosen, cutoff, symbol) if after is None else ([], [])
    chosen += additions
    return chosen, {'issuer_available': len(issuer), 'common_available': len(common),
                    'issuer_retained': sum(r['scope'] == 'issuer' for r in chosen),
                    'common_retained': sum(r['scope'] == 'common' for r in chosen),
                    'prior_comparison_items': len(additions), 'comparison_pairs': pairs,
                    'retained_characters': sum(len(r['content']) for r in chosen)}


def build(tables, *, symbols=SYMBOLS, start='2023-02-01', end='2026-01-01', splits=SPLITS):
    calendar = xcals.get_calendar('XSHG', start='2021-01-01', end='2026-02-01')
    sessions = [d.date().isoformat() for d in calendar.sessions]
    prices = {s: {} for s in symbols}
    benchmark = {}
    for key, rows in [('daily', tables['daily']), ('index_300', tables['index_300'])]:
        for raw in rows:
            if key == 'daily' and raw['stock_code'] not in prices:
                continue
            dest = prices[raw['stock_code']] if key == 'daily' else benchmark
            stamp = day(raw['date'])
            if stamp in dest:
                raise ValueError('duplicate price date')
            dest[stamp] = raw
    actions = normalize_actions(tables['dividends'], symbols)
    records, clock_audit = text_index(tables, sessions, calendar, symbols)
    record_times = [r['available_at'] for r in records]

    def evidence(cutoff, symbol, after=None):
        lo = after if after is not None else iso(datetime.fromisoformat(cutoff) - timedelta(days=187))
        subset = records[bisect_right(record_times, lo):bisect_right(record_times, cutoff)]
        return select_text(subset, cutoff, symbol, after=after)

    schedule = []
    # Start only after 20 sessions within the verified continuous period, plus
    # one preceding close. No warm-up crosses the missing 2022 source months.
    continuous = [s for s in sessions if start <= s < end]
    for offset in range(20, len(continuous) - 5, 5):
        issue = continuous[offset]
        index = sessions.index(issue)
        entry, exit_date = sessions[index + 1], sessions[index + 5]
        phase = next((p for p, (a, b) in splits.items() if a <= issue < b), None)
        if phase is None:
            continue
        schedule.append({'issue_date': issue, 'entry_date': entry, 'exit_date': exit_date,
                         'phase': phase, 'purged': exit_date >= splits[phase][1]})
    rows, inventory, exclusions = [], [], []
    for window in schedule:
        issue, entry, exit_date, phase = (window[k] for k in ('issue_date', 'entry_date', 'exit_date', 'phase'))
        if window['purged']:
            exclusions.append({**window, 'reason': 'outcome_crosses_phase_boundary'})
            continue
        index = sessions.index(issue)
        historical_dates = sessions[index - 20:index + 1]
        future_dates = sessions[index + 1:index + 6]
        issue_at = iso(calendar.session_close(issue).to_pydatetime() + timedelta(minutes=1))
        exit_at = iso(calendar.session_close(exit_date).to_pydatetime())
        # Labels are available one minute after the close, never at the close.
        outcome_at = iso(datetime.fromisoformat(exit_at) + timedelta(minutes=1))
        reasons = []
        for symbol in symbols:
            if not all(valid_bar(prices[symbol].get(d)) for d in historical_dates + future_dates):
                reasons.append(symbol + ':missing_or_invalid_bar')
        if not all(valid_bar(benchmark.get(d)) for d in historical_dates + future_dates):
            reasons.append('benchmark:missing_or_invalid_bar')
        if reasons:
            exclusions.append({**window, 'reason': 'incomplete_common_support', 'details': reasons})
            continue
        benchmark_return = benchmark[exit_date]['close'] / benchmark[entry]['open'] - 1
        for symbol in symbols:
            history, previous = history_view(historical_dates, prices[symbol], actions[symbol])
            features = state_features(history, previous) + market_features(historical_dates, benchmark)
            gross, receipt = wealth_return(entry, exit_date, prices[symbol], actions[symbol])
            selected, counts = evidence(issue_at, symbol)
            # Teacher sees only the fixed outcome window, capped by training end.
            review, _ = evidence(outcome_at, symbol, after=issue_at) if phase == 'training' else ([], {})
            rows.append({'sample_id': issue + ':' + symbol, 'symbol': symbol, 'phase': phase,
                         'issue_date': issue, 'target_date': exit_date, 'issue_at': issue_at,
                         'entry_at': iso(calendar.session_open(entry).to_pydatetime()), 'exit_at': exit_at,
                         'outcome_available_at': outcome_at, 'features': features,
                         'history20': history, 'preceding_close': previous,
                         'evidence': selected, 'review_evidence': review,
                         'actual_return': gross - benchmark_return, 'stock_gross_return': gross,
                         'benchmark_return': benchmark_return, 'wealth_receipt': receipt,
                         'momentum': history[-1]['Close'] / history[-6]['Close'] - 1
                         - (benchmark[issue]['close'] / benchmark[sessions[index - 5]]['close'] - 1)})
            inventory.append({'issue_date': issue, 'symbol': symbol, 'phase': phase, **counts,
                              'has_action_in_history': any(historical_dates[0] < a['ex_date'] <= issue for a in actions[symbol]),
                              'action_in_outcome': bool(receipt['actions']),
                              'entry_at_ex_date': any(a['ex_date'] == entry for a in actions[symbol]),
                              'precision_counts': dict(Counter(r['precision'] for r in selected)),
                              'source_refs': [r['id'] for r in selected]})
    # Fixed ridge uses 2021 only; missing early warmups are retained as fit audit.
    fit_rows = []
    fit_excluded = 0
    fit_dates = [s for s in sessions if '2021-06-15' <= s < '2022-01-01']
    for issue in fit_dates[::5]:
        i = sessions.index(issue)
        target = sessions[i + 5]
        dates = sessions[i - 20:i + 6]
        if target >= '2022-01-01':
            continue
        for symbol in symbols:
            if not all(valid_bar(prices[symbol].get(d)) and valid_bar(benchmark.get(d)) for d in dates):
                fit_excluded += 1
                continue
            hist, prev = history_view(dates[:21], prices[symbol], actions[symbol])
            actual, _ = wealth_return(sessions[i + 1], target, prices[symbol], actions[symbol])
            fit_rows.append({'features': state_features(hist, prev) + market_features(dates[:21], benchmark), 'actual_return': actual
                             - (benchmark[target]['close'] / benchmark[sessions[i + 1]]['open'] - 1),
                             'issue_date': issue, 'target_date': target})
    anchor = fit_ridge(fit_rows)
    anchor['feature_names'] = FEATURES
    packets = {}
    for row in rows:
        stamp = row['issue_date']
        if stamp not in packets:
            packets[stamp] = {'schema': 'zenith_trading_packet_v2',
                             **{k: row[k] for k in ('issue_date', 'issue_at', 'entry_at', 'exit_at')}, 'assets': []}
        # Identity retained deliberately: Chinese issuer names and code-bearing
        # tags are evidence. asset_N is a join ID, not a claim of anonymization.
        aid = 'asset_' + str(symbols.index(row['symbol']) + 1)
        identity = {'ref_id': aid + ':identity', 'kind': 'filing',
                    'available_at': row['issue_at'], 'availability_basis': 'observed_timestamp',
                    'content': 'Fixed universe issuer code: ' + row['symbol'], 'source_sha256': sha(row['symbol'])}
        context = [identity] + [{'ref_id': aid + ':' + r['id'], 'kind': r['kind'],
                    **{k: r[k] for k in ('available_at', 'availability_basis', 'content', 'source_sha256')}}
                   for r in row['evidence']]
        packets[stamp]['assets'].append({'asset_id': aid, 'history20': row['history20'],
            'preceding_close': row['preceding_close'], 'features': dict(zip(FEATURES, row['features'], strict=True)),
            'anchor_mean_return': ridge_predict(row, anchor), 'info_status': 'available',
            'context_evidence': context,
            'evidence_refs': [aid + ':' + k for k in ('history', 'state', 'anchor')] + [r['ref_id'] for r in context]})
    for packet in packets.values():
        packet['packet_sha256'] = sha(packet)
    return {'rows': rows, 'packets': packets, 'anchor': anchor, 'inventory': inventory,
            'schedule': schedule, 'exclusions': exclusions, 'clock_audit': clock_audit,
            'fit_excluded_allowances': fit_excluded, 'symbols': symbols, 'splits': splits,
            'calendar': {'name': 'XSHG', 'exchange_calendars_version': xcals.__version__,
                         'session_list_sha256': sha(sessions)}}
