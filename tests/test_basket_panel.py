"""Leakage, data integrity and all-target contracts; fixtures are synthetic."""
import csv
import json
import sqlite3
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

from zenith.market_data import COMMIT, ingest, sha256
from zenith.basket_panel import Panel, investigate
from zenith.providers import write_json


def synthetic_panel(folder):
    folder.mkdir()
    dates = pd.bdate_range('2020-01-01', periods=620).strftime('%Y-%m-%d').tolist()
    db = sqlite3.connect(folder/'panel.sqlite')
    db.execute('CREATE TABLE observations (feed TEXT,symbol TEXT,date TEXT,open REAL,high REAL,low REAL,close REAL,volume REAL)')
    rows=[]
    for t,d in enumerate(dates):
        for s in range(36):
            price=100*np.exp(.0002*t+.04*np.sin(t/17+s/5))
            if s==0 and t==550:continue
            rows.append(('stock',f'S{s:02}',d,price,price,price,price,100+s))
        rows.append(('index','NEPSE_index',d,100+t/10,100+t/10,100+t/10,100+t/10,None))
        if t>=540:rows.append(('stock','FUTURE_LISTING',d,100,100,100,100,100))
    db.executemany('INSERT INTO observations VALUES(?,?,?,?,?,?,?,?)',rows);db.commit();db.close()
    write_json(folder/'audit.json',{'commit':'synthetic-test-only','database_sha256':sha256(folder/'panel.sqlite')})
    return folder,dates


@pytest.fixture
def panel(tmp_path):
    folder,dates=synthetic_panel(tmp_path/'data')
    return Panel(folder,formation=dates[300]),dates


def test_future_listing_and_future_values_do_not_enter_snapshot(panel,tmp_path):
    p,dates=panel
    assert 'FUTURE_LISTING' not in p.symbols
    a=tmp_path/'a';p.snapshot(dates[550],a)
    arr=np.load(a/'history.npz',allow_pickle=False)
    assert max(arr['label_end_dates'])<=dates[550]
    original_x=arr['x'].copy();original_y=arr['y'].copy()
    # Changing only unseen outcomes must leave the prediction-side store unchanged.
    p.x[551:]*=10000;p.y[546:]=999
    b=tmp_path/'b';p.snapshot(dates[550],b)
    later=np.load(b/'history.npz',allow_pickle=False)
    np.testing.assert_array_equal(original_x,later['x'])
    np.testing.assert_array_equal(original_y,later['y'])
    assert sum(map(len,p.groups.values()))==36


def test_shared_query_and_tamper_boundary(panel,tmp_path):
    p,dates=panel;p.snapshot(dates[550],tmp_path/'snapshot')
    packet=json.loads((tmp_path/'snapshot/artifacts/basket_panel_feed.json').read_text())['data']
    query={'target':'B01','source':'B06','operation':'breadth','lag':5,'reason':'cross-basket test'}
    result=investigate(packet,[query])[0]
    assert result['query']==query and np.isfinite(result['prediction'])
    assert result['validation_last_label_date']<=dates[550]
    with pytest.raises(ValueError,match='invalid bounded'):investigate(packet,[dict(query,lag=-1)])
    with pytest.raises(ValueError,match='budget'):investigate(packet,[query]*7)
    with Path(packet['features']).open('ab') as stream:stream.write(b'changed')
    with pytest.raises(ValueError,match='hash'):investigate(packet,[query])


def test_stale_mark_is_reported_not_backfilled(panel,tmp_path):
    p,dates=panel;p.snapshot(dates[550],tmp_path/'snapshot')
    packet=json.loads((tmp_path/'snapshot/artifacts/basket_panel_feed.json').read_text())['data']
    row=next(r for r in packet['overview']['stock_observations'] if r['symbol']=='S00')
    assert row['quote_age']==1
    assert p.marked.loc[dates[550],'S00']==p.raw.loc[dates[549],'S00']


def test_import_duplicate_and_missing_volume(tmp_path):
    src=tmp_path/'source';(src/'ohlc_adjusted_stock').mkdir(parents=True);(src/'ohlc_index').mkdir()
    (src/'LICENSE').write_text('this dataset and associated documentation files')
    header='date,close,open,high,low,volume,symbol\n'
    row='2020-01-01,10,10,10,10,100,A\n'
    f=src/'ohlc_adjusted_stock/adj_2020-01-01.csv';f.write_text(header+row+row)
    (src/'ohlc_index/adj_2020-01-01.csv').write_text(header+'2020-01-01,10,10,10,10,,NEPSE_index\n')
    def git(args,**kwargs):return COMMIT+'\n' if 'rev-parse' in args else ''
    with patch('zenith.market_data.subprocess.check_output',side_effect=git):
        result=ingest(src,tmp_path/'import')
        assert result['identical_duplicates']==1
        assert result['rows']=={'stock':1,'index':1}
        assert result['missing_optional_values']['volume']==1
        f.write_text(header+row+row.replace(',10,10,10,10,',',11,10,10,10,'))
        with pytest.raises(ValueError,match='conflicting duplicate'):ingest(src,tmp_path/'conflict')
    assert not (tmp_path/'conflict/audit.json').exists()
