"""Synthetic source-clock, price-basis and native-controller regressions."""
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import hashlib

import pytest

from benchmarks import traderharness_daily as adapter
from zenith import daily, runtime
from system.lib.run_compare import combined_prices


def cached_pin(content):
    return {'bytes': len(content), 'sha256': hashlib.sha256(content).hexdigest()}


def test_cached_acquisition_keeps_independent_files_and_avoids_read_bytes(tmp_path, monkeypatch):
    original, target = tmp_path/'original', tmp_path/'target'
    original.write_bytes(b'pinned source')
    def no_full_read(*args, **kwargs):
        raise AssertionError('Cached acquisition must stream or clone')
    monkeypatch.setattr(Path, 'read_bytes', no_full_read)
    adapter.acquire_cached_file(original, target, cached_pin(b'pinned source'))
    assert target.stat().st_ino != original.stat().st_ino
    assert target.stat().st_nlink == original.stat().st_nlink == 1
    assert not target.is_symlink()
    target.write_bytes(b'independent change')
    assert original.open('rb').read() == b'pinned source'
    assert not list(tmp_path.glob('.acquire-*'))


def test_bad_cached_source_is_not_published(tmp_path):
    original, target = tmp_path/'original', tmp_path/'target'
    original.write_bytes(b'bad source')
    with pytest.raises(ValueError, match='Cached.*size/hash'):
        adapter.acquire_cached_file(original, target, cached_pin(b'pinned source'))
    assert not target.exists()
    assert not list(tmp_path.glob('.acquire-*'))


def test_cached_acquisition_preserves_existing_destination(tmp_path):
    original, target = tmp_path/'original', tmp_path/'target'
    original.write_bytes(b'pinned source')
    target.write_bytes(b'existing destination')
    with pytest.raises(FileExistsError):
        adapter.acquire_cached_file(original, target, cached_pin(b'pinned source'))
    assert target.read_bytes() == b'existing destination'
    assert not list(tmp_path.glob('.acquire-*'))


def test_cached_copy_fallback_and_corruption_detection(tmp_path, monkeypatch):
    original, target = tmp_path/'original', tmp_path/'target'
    original.write_bytes(b'pinned source')
    monkeypatch.setattr(adapter.sys, 'platform', 'linux')
    adapter.acquire_cached_file(original, target, cached_pin(b'pinned source'))
    assert target.read_bytes() == b'pinned source'
    target.unlink()
    monkeypatch.setattr(adapter.shutil, 'copyfile', lambda source, dest: Path(dest).write_bytes(b'corrupt'))
    with pytest.raises(ValueError, match='Copied.*size/hash'):
        adapter.acquire_cached_file(original, target, cached_pin(b'pinned source'))
    assert not target.exists()
    assert not list(tmp_path.glob('.acquire-*'))


def test_failed_native_clone_falls_back_from_its_partial_copy(tmp_path, monkeypatch):
    original, target = tmp_path/'original', tmp_path/'target'
    original.write_bytes(b'pinned source')
    monkeypatch.setattr(adapter.sys, 'platform', 'darwin')
    def failed_clone(argv, **kwargs):
        Path(argv[-1]).write_bytes(b'partial copy')
        raise adapter.subprocess.CalledProcessError(1, argv)
    monkeypatch.setattr(adapter.subprocess, 'run', failed_clone)
    adapter.acquire_cached_file(original, target, cached_pin(b'pinned source'))
    assert target.read_bytes() == b'pinned source'
    assert original.stat().st_ino != target.stat().st_ino
    assert target.stat().st_nlink == 1
    assert not list(tmp_path.glob('.acquire-*'))


@pytest.fixture
def source_index():
    calendar = adapter.calendar_for('2023-03-01', '2023-05-31')
    sessions = [s.date().isoformat() for s in calendar.sessions_in_range('2023-03-01', '2023-05-10')]
    bars = [{'date': day, 'stock_code': '600438', 'open': 100., 'high': 101.,
             'low': 99., 'close': 100., 'volume': 1000.} for day in sessions]
    def announcement(day, title):
        return {'stock_code': '600438', 'announcement_time': datetime.fromisoformat(day),
                'title': title, 'pdf_url': 'https://example.invalid/'+title+'.pdf'}
    def news(stamp, title, identity):
        dt = datetime.fromisoformat(stamp)
        return {'id': identity, 'ctime': int(dt.timestamp()), 'display_time': dt.astimezone(adapter.source.SHANGHAI).replace(tzinfo=None),
                'title': title, 'content_source': 'derived_headline'}
    tables = {'daily': bars, 'index_300': deepcopy(bars), 'announcements': [
        announcement('2023-04-26', 'ADMITTED_TITLE'), announcement('2023-04-27', 'NEXT_DAY_TITLE')],
        'news_cls': [news('2023-04-27T06:59:45+00:00', '{{C600438}} admitted headline', 1),
                     news('2023-04-27T07:00:45+00:00', '{{C600438}} FUTURE_NEWS', 2)],
        'dividends': [{'stock_code': '600438', 'ann_date': '2023-04-20', 'record_date': '2023-04-25',
                       'ex_date': '2023-04-26', 'bonus_shares': 1., 'transfer_shares': 0., 'cash_dividend': 10., 'progress': '实施'},
                      {'stock_code': '600438', 'ann_date': '2023-04-20', 'record_date': '2023-05-05',
                       'ex_date': '2023-05-08', 'bonus_shares': 2., 'transfer_shares': 0., 'cash_dividend': 20., 'progress': '实施'}]}
    return adapter.index_tables(tables, ['600438'])


def test_cutoff_and_actions_do_not_change_raw_quote_target(source_index):
    value = adapter.daily_inputs(source_index, '2023-04-27')
    assert value['observation_at_utc'] == '2023-04-27T07:00:00+00:00'
    assert value['issue_at_utc'] == '2023-04-27T07:01:00+00:00'
    assert value['stock']['rows'] == [['600438', 100.]]
    assert value['stock']['wealth_history']['600438']['bars'][-1]['Close'] == 1.11
    assert len(value['stock']['historical_corporate_actions']['600438']) == 1
    text = json.dumps(value['news'])
    assert 'ADMITTED_TITLE' in text and 'admitted headline' in text
    assert 'NEXT_DAY_TITLE' not in text and 'FUTURE_NEWS' not in text
    assert all(row['available_at'] <= value['observation_at_utc'] for row in value['news']['items'])
    assert value['news']['items'][0]['pdf_url'].endswith('ADMITTED_TITLE.pdf')
    assert len(value['stock']['price_history']['600438']) == 21
    assert 'fundamentals' not in value['stock']


def test_future_prices_cannot_change_the_forward_inputs(source_index):
    before = adapter.daily_inputs(source_index, '2023-04-27')
    source_index['prices']['600438']['2023-04-28']['close'] = 10_000.
    source_index['market']['2023-04-28']['close'] = 50_000.
    assert adapter.daily_inputs(source_index, '2023-04-27') == before


def test_missing_historical_session_is_not_forward_filled(source_index):
    del source_index['prices']['600438']['2023-04-25']
    with pytest.raises(ValueError, match='consecutive price history'):
        adapter.daily_inputs(source_index, '2023-04-27')


def test_numeric_and_leading_zero_issuers_keep_their_identity(tmp_path):
    adapter.write_json(tmp_path/'artifacts/global_stock_feed.json', {
        'data': {'columns': ['Ticker', 'Price'], 'rows': [['000858', '123.45'], ['600438', '35.2']]}})
    result = combined_prices(tmp_path)
    assert set(result) == {'000858', '600438'}
    assert result['000858'] == {'Ticker': '000858', 'Price': 123.45}


@pytest.mark.parametrize('before,after', [('2023-09-28', '2023-10-09'), ('2024-02-08', '2024-02-19')])
def test_xshg_holiday_next_session(before, after):
    cal = adapter.calendar_for(before, after)
    assert cal.next_session(before).date().isoformat() == after
    assert cal.session_close(after).isoformat() == after+'T07:00:00+00:00'


@pytest.fixture
def native_source(tmp_path, source_index, monkeypatch):
    manifest = {'schema': 'traderharness_daily_source_v1', 'manifest_sha256': 'synthetic'}
    path = tmp_path/'source'
    adapter.write_json(path/'source-manifest.json', manifest)
    monkeypatch.setattr(adapter, 'verify', lambda directory: manifest)
    monkeypatch.setattr(adapter, 'indexed', lambda *args: source_index)
    monkeypatch.setattr(adapter.source, 'SYMBOLS', ['600438'])
    return path


def test_snapshot_is_immutable_and_missing_lanes_stay_missing(tmp_path, native_source):
    output = tmp_path/'snapshot'
    packet = adapter.snapshot(native_source, '2023-04-27', output)
    assert adapter.snapshot(native_source, '2023-04-27', output) == packet
    artifact = output/'artifacts/global_stock_feed.json'
    assert daily.read(artifact)['metadata']['currency'] == 'CNY'
    assert daily.read(output/'artifacts/global_macro_feed.json')['data']['availability'] == 'unavailable'
    artifact.write_text('{}')
    with pytest.raises(ValueError, match='snapshot drift'):
        adapter.snapshot(native_source, '2023-04-27', output)


def test_daily_full_native_graph_uses_observation_horizon_and_later_availability(tmp_path, native_source):
    root = tmp_path/'checkout'
    shutil.copytree(runtime.DEFAULT_ROOT/'codex', root/'codex')
    daily.write_json(root/'master_config.json', {'paths': {'runs_dir': 'state/runs'}, 'execution': {'max_workers': 8}})
    programme = tmp_path/'programme'
    daily.initialize(root, programme, native_source, '2023-04-27', '2023-04-27')
    manifest = daily.load(root, programme)
    assert manifest['snapshots'][1]['anchor'] == '2023-04-28T07:01:00+00:00'
    assert manifest['snapshots'][1]['observation_at'] == '2023-04-28T07:00:00+00:00'
    result = daily.advance(root, programme)
    assert (result['stage'], result['status'], result['scope_count']) == ('lab', 'awaiting_agent', 28)
    spec = daily.read(runtime.runs_root(root)/result['run_id']/'zenith_run.json')
    assert runtime.stamp(spec['horizon']).isoformat() == '2023-04-28T07:00:00+00:00'
    assert runtime.stamp(spec['time_anchor']).isoformat() == '2023-04-27T07:01:00+00:00'
    assert spec['truth_run'] is None
    assert spec['feed_source'].endswith('2023-04-27')


def test_profit_state_survives_news_window_without_a_new_matching_release():
    def row(identity,stamp,text,entities=None):
        return {'id':identity,'available_at':stamp,'published_date':stamp[:10],'entities':['601919'] if entities is None else entities,'content':text,'kind':'news'}
    old=row('prior','2023-04-10T10:22:10+00:00','{{C601919}}：预计一季度归母净利润69.33亿元 同比减少约74.91%')
    future=row('future','2023-04-28T09:15:53+00:00','{{C601919}}：一季度净利润71.27亿元 同比下降74.2%')
    unrelated=row('other','2023-04-27T07:00:00+00:00','客户2022年一季度净利润99亿元',['601919','999999'])
    cutoff='2023-04-28T07:00:00+00:00'
    legacy,_=adapter.select_daily_text([old,unrelated,future],cutoff,'601919')
    assert 'prior' not in {r['id'] for r in legacy}
    memory,audit=adapter.select_daily_text([future,unrelated,old],cutoff,'601919',profit_memory=True)
    assert audit['profit_state_items_added']==1
    state=[r for r in memory if r['scope']=='issuer_profit_state']
    assert state==[{**old,'scope':'issuer_profit_state'}]
    assert 'future' not in {r['id'] for r in memory}
    # Once the actual result is available it supersedes guidance as latest state;
    # prior-comparison retrieval independently keeps the guidance when appropriate.
    _,later=adapter.select_daily_text([old,unrelated,future],'2023-05-04T07:00:00+00:00','601919',profit_memory=True)
    assert later['profit_state_records'][0]['id']=='future'


def test_profit_state_is_bounded_and_does_not_rewrite_legacy_profile():
    before=adapter.manifest_body()
    after=adapter.manifest_body(True)
    assert 'selection_profile' not in before
    assert after['selection_profile']=='issuer_profit_state_v1'
    assert before['policy']==adapter.POLICY
    assert before['files']==after['files']
    assert adapter.canonical_hash(before)!=adapter.canonical_hash(after)
    rows=[{'id':str(i),'available_at':f'2023-04-{i:02d}T07:00:00+00:00','published_date':f'2023-04-{i:02d}',
           'entities':['601919'],'content':f'{2019+i}年一季度净利润{i}亿元','kind':'news'} for i in range(1,5)]
    selected,audit=adapter.select_daily_text(rows,'2023-04-28T07:00:00+00:00','601919',profit_memory=True)
    assert len(audit['profit_state_records'])==2
    assert [r['id'] for r in selected]==['4','3']
