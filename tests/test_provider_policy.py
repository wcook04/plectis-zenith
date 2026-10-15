"""Operator policy boundaries; no external inference or real credentials."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from decimal import Decimal
import multiprocessing
import threading
import os
import time
from pathlib import Path
from unittest.mock import Mock, patch
import pytest

from zenith.provider_policy import require_model, require_prices, recent_models, serialized_inference, inference_gate
from zenith.budgeted import OpenRouterBudgetedProvider, verified_model


@pytest.mark.parametrize("model",["openai/gpt-4.1","openai/gpt-4.1-mini","openai/gpt-5.5","anthropic/claude-opus-4.6","google/gemini-3-pro","openrouter/auto","synthetic/deepseek"])
def test_banned_before_metadata_or_inference(tmp_path,model):
    post=Mock();get=Mock()
    with pytest.raises(ValueError,match="policy"):
        OpenRouterBudgetedProvider(tmp_path/"run",model,".10",2,100,tmp_path/"budget",caller=post,catalogue_get=get)
    post.assert_not_called();get.assert_not_called()


@pytest.mark.parametrize("pricing",[
    {"prompt":".000004","completion":".000012"},
    {"prompt":".0000001","completion":".000009"},
    {"prompt":"NaN","completion":"0"},
    {"prompt":"0","completion":"0","request":".01"},
])
def test_chinese_name_does_not_excuse_expensive_or_unknown_price(pricing):
    with pytest.raises((ValueError,ArithmeticError)):
        require_prices(pricing)


def test_verified_model_consumes_policy():
    get=lambda *args:{"data":[{"id":"qwen/qwen-expensive","pricing":{"prompt":".000004","completion":".000012"}}]}
    with pytest.raises(ValueError,match="ceiling"):
        verified_model("qwen/qwen-expensive",http_get=get)


def test_pinned_tariff_above_catalogue_minimum_is_reserved_and_capped(tmp_path,monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY","fake-policy-test-only")
    model="deepseek/current"
    row={"id":model,"pricing":{"prompt":".0000001","completion":".0000002"},
        "context_length":100000,"architecture":{"input_modalities":["text"],"output_modalities":["text"]},
        "supported_parameters":["max_tokens","temperature"]}
    endpoint={"model_id":model,"tag":"host/fp8","provider_name":"Host","status":0,
        "context_length":100000,"max_completion_tokens":4096,"supported_parameters":["max_tokens","temperature"],
        "pricing":{"prompt":".0000003","completion":".0000006"}}
    def get(url,*args):return {"data":{"id":model,"endpoints":[endpoint]}} if url.endswith('/endpoints') else {"data":[row]}
    post=Mock(return_value={"model":model,"provider":"Host","usage":{"prompt_tokens":2,"completion_tokens":1,"cost":.0000012},
        "choices":[{"message":{"content":"valid"}}]})
    p=OpenRouterBudgetedProvider(tmp_path/'run',model,'.01',1,100,tmp_path/'budget',caller=post,catalogue_get=get,provider_slug='host/fp8')
    assert p.ask_ai('hello',{'meta':{'session_id':'run','node_id':'test'}})=='valid'
    routing=post.call_args.args[2]['provider']
    assert routing['only']==['host/fp8'] and routing['allow_fallbacks'] is False
    assert routing['max_price']['prompt']==.3
    assert routing['max_price']['completion']==.6


def test_newest_eligible_model_not_old_familiar_or_new_expensive():
    now=datetime.now(timezone.utc).timestamp()
    def row(name,age,price=".0000001"):
        return {"id":name,"created":now-age*86400,"pricing":{"prompt":price,"completion":price},
            "architecture":{"output_modalities":["text"]},"supported_parameters":["max_tokens","response_format","structured_outputs"]}
    rows=[row("deepseek/old",200),row("deepseek/current",10),row("qwen/new",2),
        row("z-ai/new-expensive",1,".000008"),row("openai/gpt-4.1",0),row("qwen/new:batch",1)]
    assert [r["id"] for r in recent_models(rows,now=now)]==["qwen/new","deepseek/current"]
    assert recent_models(rows,family="deepseek",now=now)[0]["id"]=="deepseek/current"


def test_singleflight_across_threads(tmp_path,monkeypatch):
    monkeypatch.setenv("HOME",str(tmp_path));active=0;peak=0
    @serialized_inference
    def job(i):
        nonlocal active,peak
        active+=1;peak=max(peak,active);time.sleep(.015);active-=1
        if i==2:raise ValueError("retained failure")
    with ThreadPoolExecutor(4) as pool:
        futures=[pool.submit(job,i) for i in range(4)]
        for i,f in enumerate(futures):
            if i==2:
                with pytest.raises(ValueError):f.result()
            else:f.result()
    assert peak==1


def _process_job(home,queue):
    os.environ["HOME"]=home
    @serialized_inference
    def job():
        start=time.monotonic();time.sleep(.04);queue.put((start,time.monotonic()))
    job()


def test_singleflight_across_processes(tmp_path):
    ctx=multiprocessing.get_context("spawn");queue=ctx.Queue()
    procs=[ctx.Process(target=_process_job,args=(str(tmp_path),queue)) for _ in range(3)]
    for p in procs:p.start()
    intervals=sorted(queue.get(timeout=15) for _ in procs)
    for p in procs:p.join(15);assert p.exitcode==0
    assert all(a[1]<=b[0] for a,b in zip(intervals,intervals[1:]))


def test_bounded_routes_overlap_with_three_global_slots(tmp_path, monkeypatch):
    monkeypatch.setattr('zenith.provider_policy._inference_root', lambda: tmp_path)
    mutex = threading.Lock()
    release = threading.Event()
    three_entered = threading.Event()
    active = peak = 0
    def job(index):
        nonlocal active, peak
        with inference_gate('bounded', f'route-{index}/fp8'):
            with mutex:
                active += 1
                peak = max(peak, active)
                if active == 3:
                    three_entered.set()
            assert release.wait(3)
            with mutex:
                active -= 1
    with ThreadPoolExecutor(6) as pool:
        futures = [pool.submit(job, i) for i in range(6)]
        try:
            assert three_entered.wait(3)
        finally:
            release.set()
        for future in futures:
            future.result(timeout=3)
    assert peak == 3


@pytest.mark.parametrize('first_mode', ['serial', 'bounded'])
def test_legacy_and_bounded_modes_exclude_each_other(tmp_path, monkeypatch, first_mode):
    monkeypatch.setattr('zenith.provider_policy._inference_root', lambda: tmp_path)
    first_entered = threading.Event()
    second_attempted = threading.Event()
    second_entered = threading.Event()
    release = threading.Event()
    def first():
        with inference_gate(first_mode, 'first/fp8'):
            first_entered.set()
            assert release.wait(3)
    def second():
        second_attempted.set()
        with inference_gate('bounded' if first_mode == 'serial' else 'serial', 'second/fp8'):
            second_entered.set()
    with ThreadPoolExecutor(2) as pool:
        a = pool.submit(first)
        assert first_entered.wait(3)
        b = pool.submit(second)
        assert second_attempted.wait(3)
        try:
            assert not second_entered.wait(.04)
        finally:
            release.set()
        a.result(timeout=3)
        b.result(timeout=3)
    assert second_entered.is_set()


def _bounded_process_job(root, route, queue, start):
    from zenith import provider_policy
    provider_policy._inference_root = lambda: Path(root)
    queue.put(('ready', route))
    assert start.wait(10)
    with provider_policy.inference_gate('bounded', route):
        begin = time.monotonic()
        time.sleep(.08)
        queue.put(('interval', route, begin, time.monotonic()))


def test_bounded_route_and_global_limits_cross_process(tmp_path):
    ctx = multiprocessing.get_context('spawn')
    queue, start = ctx.Queue(), ctx.Event()
    routes = ['one/fp8', 'two/fp8', 'three/fp8'] * 2
    processes = [ctx.Process(target=_bounded_process_job, args=(str(tmp_path), route, queue, start))
                 for route in routes]
    for process in processes:
        process.start()
    for _ in processes:
        assert queue.get(timeout=15)[0] == 'ready'
    start.set()
    intervals = [queue.get(timeout=15) for _ in processes]
    for process in processes:
        process.join(15)
        assert process.exitcode == 0
    for route in set(routes):
        pairs = sorted((row[2], row[3]) for row in intervals if row[1] == route)
        assert all(a[1] <= b[0] for a, b in zip(pairs, pairs[1:]))
    events = sorted([(row[2], 1) for row in intervals] + [(row[3], -1) for row in intervals])
    active = peak = 0
    for _, delta in events:
        active += delta
        peak = max(peak, active)
    assert 2 <= peak <= 3
