"""Pinned TraderHarness observations for the original native daily graph.

This adapter never calls the five-session study builder or reads its labels.
Prices are raw CNY closes. Rebased historical wealth is separate evidence.
"""
from __future__ import annotations

import argparse
from bisect import bisect_right
from datetime import date, datetime, timedelta
from functools import lru_cache
import hashlib
import importlib.metadata
import json
from pathlib import Path

import exchange_calendars as xcals
import requests

from . import traderharness as source
from .fnspid import LANES, canonical_hash, sha, write_json

ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = 'https://github.com/HephaestLab/TraderHarness'
REVISION = '3e18369da5a2060f9c65b27c2a63f99edd93e167'
DATASET = 'https://huggingface.co/datasets/ANTICH/traderharness-ashare-5y'
DATA_REVISION = '3bf5151ab3e94851bb09dd8ade815563c44b15a6'
BASIS = 'traderharness_raw_cny_close_vintage_unverified'
POLICY = {
    'universe': 'Ten names fixed by 2021 turnover; not selected by later outcomes.',
    'calendar': 'XSHG session proxy for this Shanghai/Shenzhen panel; not an issuer exchange identifier.',
    'prices': 'Raw CNY close, observed at session close; packet availability reconstructed as close plus one minute. Historical revision vintage is unverified.',
    'news': 'Entity-templated derived headlines only, not full CLS articles. Entity tags are candidate associations, not verified issuer relevance.',
    'announcements': 'Titles and source PDF links only; PDFs not fetched. Midnight/date-only records become eligible at the next exchange-session open.',
    'text_clock': 'Text capped at observed close, before reconstructed packet availability. News uses source epoch seconds; timed announcements assume Asia/Shanghai. Publication metadata does not certify historical text vintage.',
    'selection': 'Per issuer: latest four issuer items and two common headlines from seven days, plus at most two earlier same-period profit comparisons from 187 days; 600 characters per item.',
    'actions': 'Only already ex-dated, announcement-eligible implemented actions. Per-ten-share terms. Final archive status is not a historical revision certificate; pending future terms excluded.',
    'wealth': 'Twenty historical wealth bars rebased to the preceding close, gross cash receivable without reinvestment. Context only, never the Price target or an executable return.',
    'fundamentals': 'Excluded: financial-fact revision history and definition/attribution unresolved.',
    'missing_lanes': 'No ETF, FX, macro, crypto or commodity observations. CSI300 index context remains in STOCK.',
    'rights': 'Research-use source; upstream rights retained. No downloaded data or source text in public Git.',
}


def calendar_for(start, end):
    return xcals.get_calendar('XSHG', start=start, end=end)


def pinned_files():
    pinned = json.loads((ROOT/'docs/data-selection-intraday.json').read_text())['candidates'][0]['files']
    return {f'harness_{Path(r["path"]).name}': {k: r[k] for k in ('bytes', 'sha256')}
            for r in pinned if Path(r['path']).stem in source.TABLES}


def policy_for(profit_memory=False):
    policy = dict(POLICY)
    if profit_memory:
        policy['profit_state_memory'] = 'At most two latest distinct issuer profit-period claims within 187 days, even without a recent matching headline; single issuer candidate token required. Original timestamps retained; not authenticated fundamentals or consensus.'
    return policy


def manifest_body(profit_memory=False):
    value = {'schema': 'traderharness_daily_source_v1', 'repository': REPOSITORY, 'revision': REVISION,
            'dataset': DATASET, 'data_revision': DATA_REVISION, 'files': pinned_files(),
            'symbols': source.SYMBOLS, 'policy': policy_for(profit_memory)}
    if profit_memory:
        value['selection_profile'] = 'issuer_profit_state_v1'
    return value


def verify(directory):
    directory = Path(directory)
    manifest = json.loads((directory/'source-manifest.json').read_text())
    if manifest.get('selection_profile') not in (None, 'issuer_profit_state_v1'):
        raise ValueError('Unknown daily selection profile')
    expected = manifest_body(manifest.get('selection_profile') == 'issuer_profit_state_v1')
    for name, pin in expected['files'].items():
        path = directory/name
        if path.stat().st_size != pin['bytes'] or sha(path) != pin['sha256']:
            raise ValueError('Pinned TraderHarness source bytes differ: '+name)
    if manifest != {**expected, 'manifest_sha256': canonical_hash(expected)}:
        raise ValueError('TraderHarness daily source manifest changed')
    return manifest


def acquire(directory, cached_source=None, *, profit_memory=False):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    body = manifest_body(profit_memory)
    for name, pin in body['files'].items():
        target = directory/name
        if target.exists():
            if target.stat().st_size != pin['bytes'] or sha(target) != pin['sha256']:
                raise ValueError('Existing source differs; preserve it and use another directory')
            continue
        if cached_source:
            content = (Path(cached_source)/name).read_bytes()
        else:
            url = f'{DATASET}/resolve/{DATA_REVISION}/{name.removeprefix("harness_")}'
            response = requests.get(url, timeout=120)
            response.raise_for_status()
            content = response.content
        if len(content) != pin['bytes'] or hashlib.sha256(content).hexdigest() != pin['sha256']:
            raise ValueError('Downloaded TraderHarness source failed size/hash check')
        target.write_bytes(content)
    manifest = {**body, 'manifest_sha256': canonical_hash(body)}
    path = directory/'source-manifest.json'
    if path.exists() and json.loads(path.read_text()) != manifest:
        raise ValueError('Existing source manifest differs')
    write_json(path, manifest)
    return verify(directory)


def index_tables(tables, symbols):
    """Index observations, without constructing any forward targets or returns."""
    calendar = calendar_for('2021-01-01', '2026-02-01')
    sessions = [s.date().isoformat() for s in calendar.sessions]
    prices, market = {s: {} for s in symbols}, {}
    for kind in ('daily', 'index_300'):
        for row in tables[kind]:
            if kind == 'daily' and row['stock_code'] not in prices:
                continue
            dest = prices[row['stock_code']] if kind == 'daily' else market
            day = source.day(row['date'])
            if day in dest:
                raise ValueError('Duplicate source price date')
            dest[day] = row
    records, audit = source.text_index(tables, sessions, calendar, symbols)
    links = {}
    for raw in tables['announcements']:
        if raw['stock_code'] in symbols and raw.get('title'):
            identity = {'stock_code': raw['stock_code'], 'title': raw['title'].strip(),
                        'announcement_time': str(raw['announcement_time']), 'pdf_url': raw['pdf_url']}
            links['announcement_'+source.sha(identity)[:20]] = raw['pdf_url']
    for record in records:
        if record['kind'] == 'filing':
            record['pdf_url'] = links[record['id']]
    return {'calendar': calendar, 'sessions': sessions, 'prices': prices, 'market': market,
            'actions': source.normalize_actions(tables['dividends'], symbols), 'records': records,
            'record_times': [r['available_at'] for r in records], 'clock_audit': audit}


@lru_cache(maxsize=1)
def indexed(directory, source_identity):
    # The caller verifies all original bytes before entering this cache.
    tables, _ = source.read_sources(Path(directory))
    return index_tables(tables, source.SYMBOLS)


def select_daily_text(records, cutoff, symbol, *, profit_memory=False):
    chosen, audit = source.select_text(records, cutoff, symbol)
    if not profit_memory:
        return chosen, audit
    lower = source.iso(datetime.fromisoformat(cutoff)-timedelta(days=187))
    periods, states = set(), []
    # Explicit ordering makes the bounded memory independent of input row order.
    for row in sorted(records, key=lambda r: (r['available_at'], r['id']), reverse=True):
        if row['entities'] != [symbol] or not lower < row['available_at'] <= cutoff:
            continue
        key = source.profit_period(row['content'], row.get('published_date', row['available_at'][:10]))
        if key is None:
            continue
        period = (key['year'], key['period'])
        if period in periods:
            continue
        periods.add(period)
        states.append((row, key))
        if len(states) == 2:
            break
    seen = {r['id'] for r in chosen}
    additions = [{**row, 'scope': 'issuer_profit_state', 'content': row['content'][:600]}
                 for row, _ in states if row['id'] not in seen]
    chosen += additions
    audit = {**audit, 'profit_state_items_added': len(additions),
             'profit_state_records': [{'id': row['id'], 'period_key': key,
                 'available_at': row['available_at'],
                 'basis': 'Latest eligible dated claim for this source issuer token/period; entity and accounting meaning unverified.'}
                 for row, key in states],
             'retained_characters': sum(len(r['content']) for r in chosen)}
    return chosen, audit


def daily_inputs(index, issue_date, *, profit_memory=False):
    date.fromisoformat(issue_date)
    calendar, sessions = index['calendar'], index['sessions']
    if not calendar.is_session(issue_date):
        raise ValueError('Issue date is not an XSHG session')
    offset = sessions.index(issue_date)
    if offset < 20:
        raise ValueError('Twenty sessions plus preceding close required')
    dates = sessions[offset-20:offset+1]
    observed = calendar.session_close(issue_date).to_pydatetime()
    cutoff = source.iso(observed)
    lower = source.iso(datetime.fromisoformat(cutoff)-timedelta(days=187))
    records = index['records'][bisect_right(index['record_times'], lower):bisect_right(index['record_times'], cutoff)]
    rows, histories, wealth, actions, evidence, observations, items, selection = [], {}, {}, {}, [], {}, {}, {}
    for symbol, series in sorted(index['prices'].items()):
        if not all(source.valid_bar(series.get(d)) for d in dates):
            raise ValueError('Missing or invalid consecutive price history: '+symbol)
        rows.append([symbol, series[issue_date]['close']])
        histories[symbol] = [{'session_date': d, **{k: series[d][k] for k in ('open', 'high', 'low', 'close', 'volume')}} for d in dates]
        eligible = []
        for action in index['actions'][symbol]:
            pos = bisect_right(sessions, action['ann_date'])
            if (action['ex_date'] <= issue_date and pos < len(sessions)
                    and source.iso(calendar.session_open(sessions[pos]).to_pydatetime()) <= cutoff):
                eligible.append(action)
        actions[symbol] = [a for a in eligible if dates[0] < a['ex_date'] <= issue_date]
        bars, preceding = source.history_view(dates, series, eligible)
        wealth[symbol] = {'basis': 'gross_receivable_wealth_rebased_to_one', 'preceding_close': preceding,
                         'bars': [{'session_date': d, **bar} for d, bar in zip(dates[1:], bars)]}
        evidence.append({'ledger_id': 'S_'+canonical_hash([symbol, histories[symbol], actions[symbol]])[:8].upper(),
                         'subject': symbol, 'signal_summary': f'Raw CNY close {series[issue_date]["close"]} on {issue_date}; 21 observed sessions. Wealth context is separately rebased.',
                         'source_ref': f'global_stock_feed.data.price_history.{symbol}'})
        observations[symbol] = {'session_date': issue_date, 'price_basis': BASIS, 'currency': 'CNY',
                                'provider': 'TraderHarness', 'observation_at_utc': source.iso(observed)}
        selected, selection[symbol] = select_daily_text(records, cutoff, symbol, profit_memory=profit_memory)
        for record in selected:
            key = record['id']
            if key not in items:
                items[key] = {**record, 'ledger_id': 'N_'+canonical_hash([key, record['source_sha256']])[:8].upper(),
                              'source_ref': key, 'text': record['content'], 'selected_for': []}
            items[key]['selected_for'].append(symbol)
    if not all(source.valid_bar(index['market'].get(d)) for d in dates):
        raise ValueError('Missing or invalid consecutive CSI300 history')
    market = [{'session_date': d, **{k: index['market'][d][k] for k in ('open', 'high', 'low', 'close', 'volume')}} for d in dates]
    news = sorted(items.values(), key=lambda r: (r['available_at'], r['id']))
    news_evidence = [{'ledger_id': r['ledger_id'], 'subject': ','.join(r['entities']) or 'MARKET',
                      'signal_summary': r['text'], 'source_ref': r['source_ref']} for r in news]
    if len({r['ledger_id'] for r in evidence+news_evidence}) != len(evidence+news_evidence):
        raise ValueError('Evidence ID collision')
    return {'issue_at_utc': source.iso(observed+timedelta(minutes=1)), 'observation_at_utc': cutoff,
            'stock': {'availability': 'available', 'columns': ['Ticker', 'Price'], 'rows': rows,
                      'price_basis': BASIS, 'price_history': histories, 'wealth_history': wealth,
                      'historical_corporate_actions': actions, 'csi300_history': market,
                      'evidence_dictionary': evidence, 'source_limitations': policy_for(profit_memory)},
            'news': {'availability': 'available' if news else 'unavailable', 'items': news,
                     'evidence_dictionary': news_evidence, 'selection_audit': selection, 'source_limitations': policy_for(profit_memory)},
            'price_observations': observations}


def snapshot(directory, issue_date, output):
    directory, output = Path(directory).resolve(), Path(output)
    manifest = verify(directory)
    profit_memory = manifest.get('selection_profile') == 'issuer_profit_state_v1'
    values = daily_inputs(indexed(str(directory), manifest['manifest_sha256']), issue_date, profit_memory=profit_memory)
    cutoff = values['issue_at_utc']
    packet = {'schema': 'traderharness_daily_snapshot_v1', 'issue_date': issue_date,
              'issue_at_utc': cutoff, 'observation_at_utc': values['observation_at_utc'],
              'source_manifest_sha256': manifest['manifest_sha256'],
              'implementation_sha256': sha(Path(__file__)), 'selector_sha256': sha(Path(source.__file__)),
              'calendar_id': 'XSHG', 'calendar_version': importlib.metadata.version('exchange_calendars'),
              'policy': policy_for(profit_memory), 'symbols': source.SYMBOLS, 'news_count': len(values['news']['items']),
              'native_execution_claimed': False}
    packet['snapshot_sha256'] = canonical_hash(packet)
    artifacts = {'issue-packet.json': packet,
                 'runtime_context.json': {'as_of': cutoff, 'time_anchor': cutoff, 'adapter_only': True}}
    for lane, node in LANES.items():
        data = {'availability': 'unavailable', 'items': [], 'rows': [], 'reason': 'No admitted historical observations for this lane'}
        metadata = {'status': 'partial', 'tool': 'traderharness_recorded_feed', 'as_of': cutoff,
                    'time_anchor': cutoff, 'timestamp': cutoff, 'run_id': output.name,
                    'source_manifest_sha256': manifest['manifest_sha256'], 'context_class': 'subject_side_evidence'}
        if lane == 'STOCK':
            data = values['stock']
            metadata.update(status='success', currency='CNY', price_basis=BASIS, timezone='Asia/Shanghai',
                            diagnostics={'price_observations': values['price_observations']})
        elif lane == 'NEWS':
            data = values['news']
        artifacts[f'artifacts/{node}.json'] = {'metadata': metadata, 'data': data}
    if output.exists() and any(output.iterdir()):
        old = json.loads((output/'artifact-manifest.json').read_text())
        if old['snapshot_sha256'] != packet['snapshot_sha256'] or set(old['files']) != set(artifacts):
            raise ValueError('Existing snapshot differs')
        for name, value in artifacts.items():
            if sha(output/name) != old['files'][name] or json.loads((output/name).read_text()) != value:
                raise ValueError('Frozen snapshot drift')
        return packet
    for name, value in artifacts.items():
        write_json(output/name, value)
    write_json(output/'artifact-manifest.json', {'schema': 'traderharness_daily_artifact_manifest_v1',
               'snapshot_sha256': packet['snapshot_sha256'], 'files': {name: sha(output/name) for name in artifacts}})
    return packet


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['acquire', 'snapshot'])
    parser.add_argument('--dataset', type=Path, default=ROOT/'work/datasets/traderharness-daily')
    parser.add_argument('--cached-source', type=Path)
    parser.add_argument('--profit-state-memory', action='store_true', help='Acquire a distinct source profile retaining earlier issuer profit claims')
    parser.add_argument('--issue-date')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.command == 'acquire':
        result = acquire(args.dataset, args.cached_source, profit_memory=args.profit_state_memory)
    else:
        if args.profit_state_memory:
            parser.error('Selection is frozen at acquire; snapshot reads the dataset manifest profile')
        if not args.issue_date or not args.output:
            parser.error('snapshot requires --issue-date and --output')
        result = snapshot(args.dataset, args.issue_date, args.output)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
