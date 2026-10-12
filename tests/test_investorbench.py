"""Synthetic source clocks, missing lanes and observed-price compatibility."""
import json
from pathlib import Path
import pytest
from benchmarks import investorbench as ib
from feedback.engine import dated_rows
from zenith import runtime


@pytest.fixture
def source(tmp_path, monkeypatch):
    source = tmp_path/'source'
    source.mkdir()
    files = {}
    for symbol in ('msft', 'hon', 'jnj'):
        rows = {'2020-07-01': {'prices': 100, 'news': ['Older summary'], '10k': ['unclocked filing'], '10q': []},
                '2020-07-02': {'prices': 102, 'news': ['Current day must wait'], '10k': [], '10q': []}}
        path = source/(symbol+'.json')
        path.write_text(json.dumps(rows))
        files[path.name] = ib.sha(path)
    monkeypatch.setattr(ib, 'FILES', files)
    ib.acquire(tmp_path/'admitted', source)
    return tmp_path/'admitted'


def test_date_only_news_lag_and_unclocked_filings_exclusion(source, tmp_path):
    output = tmp_path/'feeds'
    packet = ib.snapshot(source, '2020-07-02', output)
    assert packet['news_count'] == 3
    news = json.loads((output/'artifacts/global_news_feed.json').read_text())['data']
    assert {n['text'] for n in news['items']} == {'Older summary'}
    assert all(n['source_date'] == '2020-07-01' for n in news['items'])
    assert 'unclocked filing' not in json.dumps(news)
    prices = dated_rows(output/'artifacts/global_stock_feed.json')
    assert {r['target_id'] for r in prices} == {'MSFT', 'HON', 'JNJ'}
    assert {r['price'] for r in prices} == {102}
    runtime.forward_preflight(runtime.DEFAULT_ROOT, output, runtime.stamp(packet['issue_at_utc']))
    for lane, node in ib.LANES.items():
        if lane not in {'STOCK', 'NEWS'}:
            assert json.loads((output/'artifacts'/f'{node}.json').read_text())['data']['availability'] == 'unavailable'


def test_exact_prices_and_source_drift(source, tmp_path):
    with pytest.raises(ValueError, match='Exact issue-day'):
        ib.snapshot(source, '2020-07-06', tmp_path/'bad')
    (source/'msft.json').write_text('{}')
    with pytest.raises(ValueError, match='source bytes'):
        ib.audit(source)


def test_audit_and_immutable_output(source, tmp_path):
    report = ib.audit(source)
    assert report['common_price_dates'] == 2
    assert report['symbols']['MSFT']['excluded_filing_summaries'] == 1
    output = tmp_path/'feeds'
    before = ib.snapshot(source, '2020-07-02', output)
    assert ib.snapshot(source, '2020-07-02', output) == before
    (output/'artifacts/global_news_feed.json').write_text('{}')
    with pytest.raises(ValueError, match='drift'):
        ib.snapshot(source, '2020-07-02', output)
