"""Pinned three-equity daily panel; date-only upstream summaries, not raw news.

No upstream code/pickle is executed. Filing summaries lack an established
availability clock and are excluded. Downloaded text stays in local custody.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
import math
from pathlib import Path
from zoneinfo import ZoneInfo
import requests

from .fnspid import LANES, calendar_for, canonical_hash, sha, write_json

ROOT = Path(__file__).resolve().parents[1]
REVISION = '87e0f7bc83baf7d89fbdc1a51f92458f8d4ee11a'
REPOSITORY = 'https://github.com/felis33/INVESTOR-BENCH'
FILES = {
    'msft.json': 'f3af207052f2580ce5d03079a1ba17c4314a715ad55b365dc45e954dd15c5509',
    'hon.json': 'ff90bea4e8ff35cb2752e24ad74d321eb94f06e72953acaaa48e02595e12850b',
    'jnj.json': 'ba557598af05ed9947a710cb328462e279d59be19b18907339805d503c45ca8c',
}
BASIS = 'investorbench_scalar_price_vintage_unverified'
POLICY = {'news': 'prior calendar dates only; seven-day window; complete upstream summaries',
          'availability': 'date bucket plus one local calendar day is a conservative reconstruction, not verified publication/capture time',
          'filings': 'exclude all 10k/10q summaries: no established release/acceptance clock',
          'prices': 'last twenty observed scalar prices; no invented OHLCV or adjustment-vintage claim',
          'rights': 'repository MIT; publisher dataset rights not independently established; no text redistribution'}


def verify(directory):
    directory = Path(directory)
    for name, expected in FILES.items():
        if sha(directory/name) != expected:
            raise ValueError('InvestorBench source bytes differ from pinned file: '+name)
    manifest = json.loads((directory/'source-manifest.json').read_text())
    expected = {'schema': 'investorbench_source_v1', 'repository': REPOSITORY,
                'revision': REVISION, 'files': FILES, 'policy': POLICY}
    if manifest != {**expected, 'manifest_sha256': canonical_hash(expected)}:
        raise ValueError('InvestorBench source manifest changed')
    return manifest


def acquire(directory, cached_source=None):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    for name, expected in FILES.items():
        target = directory/name
        if target.exists():
            if sha(target) != expected:
                raise ValueError('Existing source differs; preserve it and use another directory')
            continue
        if cached_source:
            content = (Path(cached_source)/name).read_bytes()
        else:
            url = f'https://raw.githubusercontent.com/felis33/INVESTOR-BENCH/{REVISION}/data/{name}'
            response = requests.get(url, timeout=60)
            response.raise_for_status()
            content = response.content
        if len(content) > 5_000_000 or hashlib.sha256(content).hexdigest() != expected:
            raise ValueError('Downloaded source failed size/hash check')
        target.write_bytes(content)
    manifest = {'schema': 'investorbench_source_v1', 'repository': REPOSITORY,
                'revision': REVISION, 'files': FILES, 'policy': POLICY}
    manifest['manifest_sha256'] = canonical_hash(manifest)
    p = directory/'source-manifest.json'
    if p.exists() and json.loads(p.read_text()) != manifest:
        raise ValueError('Existing source manifest differs')
    write_json(p, manifest)
    return verify(directory)


def records(directory):
    verify(directory)
    sources = {}
    for name in FILES:
        rows = json.loads((Path(directory)/name).read_text())
        for day, row in rows.items():
            date.fromisoformat(day)
            price = row.get('prices')
            if isinstance(price, bool) or not isinstance(price, (int, float)) or not math.isfinite(price) or price <= 0:
                raise ValueError('Finite positive scalar price required')
            if set(row) != {'prices', 'news', '10k', '10q'}:
                raise ValueError('Unknown source record shape')
            for key in ('news', '10k', '10q'):
                if not isinstance(row[key], list) or any(not isinstance(s, str) for s in row[key]):
                    raise ValueError('Expected narrative summary strings')
        sources[name[:-5].upper()] = rows
    return sources


def audit(directory):
    sources = records(directory)
    common = sorted(set.intersection(*(set(rows) for rows in sources.values())))
    calendar = calendar_for(common[0], common[-1])
    expected = {s.date().isoformat() for s in calendar.sessions_in_range(common[0], common[-1])}
    return {'schema': 'investorbench_coverage_v1', 'revision': REVISION,
            'common_price_dates': len(common), 'first': common[0], 'last': common[-1],
            'expected_xnys_sessions': len(expected),
            'missing_common_sessions': sorted(expected-set(common)),
            'non_session_dates': sorted(set(common)-expected),
            'source_bytes': sum((Path(directory)/name).stat().st_size for name in FILES),
            'all_symbols_have_news_dates': sum(all(sources[s][d]['news'] for s in sources) for d in common),
            'symbols': {s: {'price_rows': len(rows), 'news_summaries': sum(len(r['news']) for r in rows.values()),
                            'empty_news_dates': sum(not r['news'] for r in rows.values()),
                            'excluded_filing_summaries': sum(len(r['10k'])+len(r['10q']) for r in rows.values())}
                        for s, rows in sources.items()}, 'policy': POLICY,
            'performance_claimed': False}


def snapshot(directory, issue_date, output):
    directory, output = Path(directory), Path(output)
    source_manifest = verify(directory)
    sources = records(directory)
    issue = date.fromisoformat(issue_date)
    calendar = calendar_for((issue-timedelta(days=190)).isoformat(), (issue+timedelta(days=14)).isoformat())
    if not calendar.is_session(issue_date):
        raise ValueError('Issue date is not an XNYS session')
    cutoff = calendar.session_close(issue_date).to_pydatetime().isoformat()
    rows, histories, stock_evidence, news, observed = [], {}, [], [], {}
    for symbol, series in sources.items():
        if issue_date not in series:
            raise ValueError('Exact issue-day price missing: '+symbol)
        dates = sorted(d for d in series if d <= issue_date)[-20:]
        histories[symbol] = [{'session_date': d, 'price': series[d]['prices']} for d in dates]
        price = series[issue_date]['prices']
        rows.append([symbol, price])
        stock_evidence.append({'ledger_id': 'S_'+canonical_hash([symbol, histories[symbol]])[:8].upper(),
            'subject': symbol, 'signal_summary': f'Observed scalar price {price} on {issue_date}; adjustment vintage unverified.',
            'source_ref': f'global_stock_feed.data.price_history.{symbol}'})
        observed[symbol] = {'session_date': issue_date, 'price_basis': BASIS, 'currency': 'USD',
                            'provider': 'InvestorBench', 'source_hash': FILES[symbol.lower()+'.json']}
        for day in sorted(series):
            if not issue-timedelta(days=7) <= date.fromisoformat(day) < issue:
                continue
            for i, text in enumerate(series[day]['news']):
                if not text.strip():
                    continue
                news.append({'ledger_id': 'N_'+canonical_hash([symbol, day, i, text])[:8].upper(),
                             'symbol_bucket': symbol, 'source_date': day,
                             'available_at_utc': datetime.combine(date.fromisoformat(day)+timedelta(days=1), datetime.min.time(), ZoneInfo('America/New_York')).astimezone(timezone.utc).isoformat(),
                             'availability_basis': POLICY['availability'], 'text': text,
                             'source_ref': f'{symbol.lower()}.json/{day}/news/{i}',
                             'source_type': 'upstream_news_summary', 'issuer_relevance': 'unverified'})
    news_evidence = [{'ledger_id': n['ledger_id'], 'subject': n['symbol_bucket'],
                     'signal_summary': n['text'], 'source_ref': n['source_ref']} for n in news]
    if len({e['ledger_id'] for e in stock_evidence+news_evidence}) != len(stock_evidence+news_evidence):
        raise ValueError('Evidence ID collision')
    packet = {'schema': 'investorbench_daily_snapshot_v1', 'issue_date': issue_date, 'issue_at_utc': cutoff,
              'source_manifest_sha256': source_manifest['manifest_sha256'], 'implementation_sha256': sha(Path(__file__)),
              'policy': POLICY, 'symbols': sorted(sources), 'news_count': len(news), 'native_execution_claimed': False}
    packet['snapshot_sha256'] = canonical_hash(packet)
    artifacts = {'issue-packet.json': packet, 'runtime_context.json': {'as_of': cutoff, 'time_anchor': cutoff, 'adapter_only': True}}
    for lane, node in LANES.items():
        data = {'availability': 'unavailable', 'items': [], 'rows': [], 'reason': 'No admitted historical observations for this lane'}
        metadata = {'status': 'partial', 'tool': 'investorbench_recorded_feed', 'as_of': cutoff,
                    'time_anchor': cutoff, 'timestamp': cutoff, 'run_id': output.name,
                    'source_manifest_sha256': source_manifest['manifest_sha256'],
                    'context_class': 'subject_side_evidence'}
        if lane == 'STOCK':
            data = {'availability': 'available', 'columns': ['Ticker', 'Price'], 'rows': rows,
                    'price_history': histories, 'evidence_dictionary': stock_evidence, 'price_basis': BASIS}
            metadata.update(status='success', currency='USD', price_basis=BASIS,
                            diagnostics={'price_observations': observed})
        elif lane == 'NEWS':
            data = {'availability': 'available' if news else 'unavailable', 'items': news,
                    'evidence_dictionary': news_evidence, 'source_limitations': POLICY}
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
    write_json(output/'artifact-manifest.json', {'schema': 'investorbench_artifact_manifest_v1',
               'snapshot_sha256': packet['snapshot_sha256'], 'files': {name: sha(output/name) for name in artifacts}})
    return packet


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['acquire', 'audit', 'snapshot'])
    parser.add_argument('--dataset', type=Path, default=ROOT/'work/datasets/investorbench')
    parser.add_argument('--cached-source', type=Path)
    parser.add_argument('--issue-date')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.command == 'acquire':
        result = acquire(args.dataset, args.cached_source)
    elif args.command == 'audit':
        result = audit(args.dataset)
    else:
        if not args.issue_date or not args.output:
            parser.error('snapshot requires --issue-date and --output')
        result = snapshot(args.dataset, args.issue_date, args.output)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
