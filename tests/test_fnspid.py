"""Temporal rejection and native hydration tests, using synthetic source fixtures."""
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
from unittest.mock import patch

import pytest
from benchmarks import fnspid as fn


def test_original_after_close_and_dst_clocks():
    assert fn.publication_time("January 16, 2024 — 05:51 pm EST").isoformat() == "2024-01-16T22:51:00+00:00"
    assert fn.publication_time("July 16, 2024 — 05:51 pm EDT").hour == 21
    with pytest.raises(ValueError):
        fn.publication_time("January 16, 2024 — 05:51 pm EDT")
    with pytest.raises(ValueError):
        fn.publication_time("2024-01-16")


def test_news_future_missing_and_duplicate_are_not_evidence(tmp_path):
    p = tmp_path/'news.csv'
    rows = [
        ["January 16, 2024 — 03:51 pm EST", "a", "Before close", "1"],
        ["January 16, 2024 — 05:51 pm EST", "b", "After close future", "1"],
        ["January 16, 2024 — 03:00 pm EST", "c", "0", "1"],
        ["2024-01-16", "d", "No clock", "1"],
    ]
    with p.open('w') as f:
        writer = csv.writer(f); writer.writerow(['Date','Url','Text','Mark']); writer.writerows(rows+[rows[0]])
    news, counts = fn.select_news(p, datetime(2024,1,16,21,tzinfo=timezone.utc))
    assert [r['text'] for r in news] == ['Before close']
    assert counts['future'] == counts['missing_body'] == counts['unusable_clock'] == counts['duplicates'] == 1


def fixture_source(tmp_path):
    d = tmp_path/'source'; d.mkdir()
    (d/'aa-prices.csv').write_text('Date,Open,High,Low,Close,Adj Close,Volume\n2024-01-16,30,31,29,30,999,20\n2024-01-17,30,32,30,31,998,40\n')
    (d/'aa-news.csv').write_text('Date,Url,Text,Mark\n"January 16, 2024 — 03:00 pm EST",https://example.invalid/a,Historical evidence,1\n')
    files = {name: {'upstream': name, 'bytes': (d/name).stat().st_size, 'sha256': fn.sha(d/name)} for name in fn.FILES}
    manifest = {'schema':'fnspid_raw_source_v1','repository':fn.REPOSITORY,'revision':fn.REVISION,'files':files,'policy':fn.POLICY}
    fn.write_json(d/'source-manifest.json', {**manifest,'manifest_sha256':fn.canonical_hash(manifest)})
    return d, files


def test_native_snapshot_all_lanes_and_tamper_rejection(tmp_path):
    d, files = fixture_source(tmp_path)
    with patch.object(fn, 'FILES', files):
        output = tmp_path/'feeds'
        packet = fn.snapshot(d, '2024-01-16', output)
        assert len(packet['prices']) == 1 and packet['prices'][0]['close'] == 30
        assert len(list((output/'artifacts').glob('*.json'))) == 6
        for lane,node in fn.LANES.items():
            env = json.loads((output/'artifacts'/f'{node}.json').read_text())
            if lane not in {'NEWS','STOCK'}:
                assert env['data']['availability'] == 'unavailable' and env['data']['rows'] == []
        from feedback.engine import dated_rows
        observations = dated_rows(output/'artifacts/global_stock_feed.json')
        assert len(observations) == 1
        assert observations[0]['currency'] == 'USD'
        assert observations[0]['price_basis'] == 'dataset_close_vintage_unverified'
        from zenith.runtime import forward_preflight
        forward_preflight(fn.ROOT, output, datetime(2024,1,16,21,tzinfo=timezone.utc))
        assert fn.snapshot(d, '2024-01-16', output) == packet
        (output/'artifacts/global_stock_feed.json').write_text('{}')
        with pytest.raises(ValueError, match='drift'):
            fn.snapshot(d, '2024-01-16', output)
        (d/'aa-news.csv').write_text('tampered')
        with pytest.raises(ValueError, match='bytes'):
            fn.verify(d)


def test_missing_exact_bar_and_non_session_refuse(tmp_path):
    d, files = fixture_source(tmp_path)
    with patch.object(fn, 'FILES', files):
        with pytest.raises(ValueError, match='Exact issue-day'):
            fn.snapshot(d, '2024-01-18', tmp_path/'out')
        with pytest.raises(ValueError, match='not an XNYS'):
            fn.snapshot(d, '2024-01-15', tmp_path/'out')


def test_abbreviated_original_clock_and_evidence_ids(tmp_path):
    assert fn.publication_time('JAN 15, 2023 8:01AM EST').isoformat() == '2023-01-15T13:01:00+00:00'
    d, files = fixture_source(tmp_path)
    with patch.object(fn, 'FILES', files):
        output=tmp_path/'feeds'
        packet=fn.snapshot(d,'2024-01-16',output)
    assert all(fn.re.fullmatch(r'S_[0-9A-F]{8}',e['ledger_id']) for e in packet['stock_evidence'])
    assert packet['news'][0]['ledger_id'] == packet['news_evidence'][0]['ledger_id']
    data=json.loads((output/'artifacts/global_stock_feed.json').read_text())['data']
    assert data['rows'][0][5] is None  # one source bar cannot supply a five-session change
    assert data['rows'][0][6] is None  # no invented sixty-three-session change
