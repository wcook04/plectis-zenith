"""Exercise the actual engine with test responses, not model-performance claims."""
import json
import shutil
from pathlib import Path
from unittest.mock import patch

from zenith import runtime
from zenith.basket_panel import Panel
from zenith.providers import Provider, write_json
from test_basket_panel import synthetic_panel
from tools.baskets.numeric import run as numeric_run
import pytest


ROOT=Path(__file__).resolve().parents[1]


class FixtureProvider(Provider):
    def ask_ai(self,prompt,config=None,cancel=None):
        node=config['meta']['node_id']
        if 'reader' in node:return json.dumps({'observation':'Synthetic test response','cross_basket_question':'Test B06 for B01'})
        if node.endswith('_plan'):return json.dumps({'queries':[{'target':'B01','source':'B06','operation':'breadth','lag':5,'reason':'fixture'}]})
        if node.endswith('_director'):return json.dumps({'selections':{f'B{i:02}':'Q1' if i==1 else 'baseline' for i in range(1,7)}})
        raise AssertionError(node)


def test_native_forward_graph_and_final_forecasts(tmp_path):
    root=tmp_path/'root';root.mkdir();shutil.copytree(ROOT/'codex',root/'codex')
    write_json(root/'master_config.json',{'paths':{'runs_dir':'state/runs'},'execution':{'max_workers':4}})
    folder,dates=synthetic_panel(tmp_path/'data');p=Panel(folder,formation=dates[300])
    source=tmp_path/'snapshot';p.snapshot(dates[550],source)
    with patch.object(runtime,'provider_for',side_effect=lambda d,s:FixtureProvider(d)):
        result=runtime.start(root,mission='basket',run_id='FIXTURE_BASKET',feed_source=str(source),time_anchor=dates[550]+'T23:59:59+00:00',horizon=dates[555]+'T23:59:59+00:00')
    assert result['status']=='completed',result
    directory=runtime.runs_root(root)/'FIXTURE_BASKET'
    final=json.loads((directory/'artifacts/basket_final.json').read_text())['data']
    assert set(final['forecasts'])==set(p.groups)
    assert final['forecasts']['B01']!=final['provisional_forecasts']['B01']
    assert final['query_count']==1
    assert not (directory/'artifacts/lab_director.json').exists()
    # The final tool rejects selective scoring or a fabricated candidate ID.
    path=directory/'artifacts/basket_director.json';d=json.loads(path.read_text());del d['data']['selections']['B06'];write_json(path,d)
    with pytest.raises(ValueError,match='every basket'):numeric_run({'operation':'final'},directory)


def test_legacy_lab_scope_is_unchanged():
    assert runtime.plan(ROOT,'lab')['node_count']==25
    assert runtime.plan(ROOT,'basket')['node_count']==18
    assert runtime.plan(ROOT,'basket_serial')['node_count']==6
