"""Three authored native wrapper diagnostics, with fresh protected panels.

Adapted from Zenith ADVANCE return 14, ``diagnostics.py`` (2026-10-14),
SHA256 dd6a1256438f83593c4078fe207d9e4953dd7668064b229ae6cc97f46648614a.
Its native SQLite/LRU/UTF8 adapters and public-example prefix policy supply
the starting implementation. SQLite uses the live decomposition_tasks owner.
These constructed contracts are not production workloads or novelty claims.
No buggy initial model is supplied. public_task is the provider allowlist.
"""
from __future__ import annotations

import codecs
from copy import deepcopy
from functools import lru_cache
import json
import platform
import random
import re
import sqlite3

from research import decomposition_tasks as sqlite_tasks


DEFAULT_SEED = 20261015
MAX_EVENTS = 32
MAX_CHUNK_BYTES = 64
MAX_TOTAL_BYTES = 256
PROBE_BUDGET = 8
FAMILIES = ("sqlite", "lru", "utf8")
SOURCE_IDS = {f"{kind}-{replicate}": kind
              for replicate in range(2) for kind in FAMILIES}
ADAPTATION = {
    "source": "ZENITH_ADVANCE_RETURN_14-the-next-decisive-campaign/diagnostics.py",
    "sha256": "dd6a1256438f83593c4078fe207d9e4953dd7668064b229ae6cc97f46648614a",
    "scope": "Native adapters and public-example proper-prefix tester; bounded local adaptation.",
}

SQLITE_CONTRACT = sqlite_tasks.SQLITE_DESCRIPTION.replace(
    "The seed program is an experimental hypothesis.",
    "No initial program is supplied; author a fresh behavioral model.")
LRU_CONTRACT = """Native functools.lru_cache diagnostic. A fresh query is exactly
{"capacity": integer, "events": [event, ...]}, with capacity 1..4 and at most
32 events. An event is exactly {"op":"call", "key":integer} with key 0..31,
or {"op":"reset"}. Booleans are not integers. A fresh capacity-sized cache
wraps a function returning its integer argument. Calls and resets operate in
list order. Reset calls cache_clear, clearing contents and hit/miss counters.
Return {"hits":integer,"misses":integer,"size":integer} from cache_info after
the events. Each query has an independent fresh cache. The source has no hidden
capacity or external data. Implement investigate(context, acquire), returning
that JSON object. No initial program is supplied. An allowed native probe uses
exactly the same query schema.
"""
UTF8_CONTRACT = """Native strict codecs UTF8 incremental-decoder diagnostic.
A fresh query is exactly {"events":[event,...]}, with at most 32 events.
An event is exactly {"op":"feed","bytes":[integer,...]}, {"op":"finish"},
or {"op":"reset"}. Each byte is an integer 0..255, excluding booleans; each
chunk has at most 64 bytes and the entire query at most 256 bytes. Empty chunks
are legal. Feed invokes decode(bytes, final=False); finish invokes decode with
empty bytes and final=True. Count Unicode code points in strings successfully
returned by these calls, not bytes or graphemes. A UnicodeDecodeError is a
measured result: status becomes "error", and the failing call contributes ZERO
characters, including any valid prefix in that same chunk. Successful finish
sets status "finished". Otherwise status is "open", including incomplete byte
prefixes. After either terminal status, only reset is legal. Reset creates a
fresh strict decoder and sets count=0,status="open". Reset may also occur while
open. Return {"count":integer,"status":"open"|"finished"|"error"}. Each query
starts fresh. Invalid/incomplete UTF8 bytes are allowed inputs; malformed query
shapes and events after a terminal result without reset are illegal queries.
Implement investigate(context, acquire). No initial program is supplied.
"""
CONTRACTS = {"sqlite": SQLITE_CONTRACT, "lru": LRU_CONTRACT, "utf8": UTF8_CONTRACT}

LRU_REFERENCE = '''def investigate(context, acquire):
    order = []
    hits = 0
    misses = 0
    for event in context["events"]:
        if event["op"] == "reset":
            order = []
            hits = 0
            misses = 0
        else:
            key = event["key"]
            if key in order:
                hits += 1
                order.remove(key)
            else:
                misses += 1
            order.append(key)
            if len(order) > context["capacity"]:
                order.pop(0)
    return {"hits": hits, "misses": misses, "size": len(order)}
'''


def _family(source_id):
    if type(source_id) is not str:
        raise ValueError("source_id must be a registered string")
    if source_id in FAMILIES:
        return source_id
    if source_id in SOURCE_IDS:
        return SOURCE_IDS[source_id]
    match = re.fullmatch(r"(sqlite|lru|utf8)-([0-9]+)", source_id)
    if match is None or int(match.group(2)) >= 32:
        raise ValueError("unknown native source_id")
    return match.group(1)


def _validate_shape(kind, query):
    """Typed public legality first; decode errors are not syntax violations."""
    if kind == "sqlite":
        sqlite_tasks._object(query, {"actions"}, "query")
        sqlite_tasks._actions(query["actions"])
        return
    fields = {"capacity", "events"} if kind == "lru" else {"events"}
    sqlite_tasks._object(query, fields, "query")
    if kind == "lru":
        sqlite_tasks._integer(query["capacity"], 1, 4, "capacity")
    events = sqlite_tasks._list(query["events"], MAX_EVENTS, "events")
    total_bytes, finished = 0, False
    for event in events:
        if type(event) is not dict or type(event.get("op")) is not str:
            raise ValueError("event must be an object with a string op")
        op = event["op"]
        if op == "reset":
            sqlite_tasks._object(event, {"op"}, "reset")
            finished = False
        elif kind == "lru" and op == "call":
            sqlite_tasks._object(event, {"op", "key"}, "call")
            sqlite_tasks._integer(event["key"], 0, 31, "key")
        elif kind == "utf8" and op in ("feed", "finish"):
            if finished:
                raise ValueError("terminal stream requires reset")
            if op == "finish":
                sqlite_tasks._object(event, {"op"}, "finish")
                finished = True
            else:
                sqlite_tasks._object(event, {"op", "bytes"}, "feed")
                values = sqlite_tasks._list(event["bytes"], MAX_CHUNK_BYTES, "bytes")
                for byte in values:
                    sqlite_tasks._integer(byte, 0, 255, "byte")
                total_bytes += len(values)
        else:
            raise ValueError("unsupported event")
    if total_bytes > MAX_TOTAL_BYTES:
        raise ValueError("query exceeds total byte budget")


def measure(source_id, query):
    """Run one fresh native query; illegal queries raise ValueError.

    UTF8 terminal status caused by a decoder exception is checked at runtime:
    it is an outcome until a subsequent non-reset event makes the query illegal.
    """
    kind = _family(source_id)
    _validate_shape(kind, query)
    if kind == "sqlite":
        return sqlite_tasks.oracle({"private": {"kind": "sqlite"}}, query)
    if kind == "lru":
        @lru_cache(maxsize=query["capacity"])
        def identity(key):
            return key

        for event in query["events"]:
            if event["op"] == "reset":
                identity.cache_clear()
            else:
                identity(event["key"])
        info = identity.cache_info()
        return {"hits": info.hits, "misses": info.misses, "size": info.currsize}
    decoder = codecs.getincrementaldecoder("utf-8")("strict")
    count, status = 0, "open"
    for event in query["events"]:
        if event["op"] == "reset":
            decoder.reset()
            count, status = 0, "open"
            continue
        if status != "open":
            raise ValueError("terminal stream requires reset")
        final = event["op"] == "finish"
        raw = b"" if final else bytes(event["bytes"])
        try:
            emitted = decoder.decode(raw, final=final)
        except UnicodeDecodeError:
            status = "error"
        else:
            count += len(emitted)
            if final:
                status = "finished"
    return {"count": count, "status": status}


def query_units(query):
    """Bounded source-specific work units, not comparable physical time.

    SQLite: actions plus CREATE/final INSERT. LRU: events plus cache_info.
    UTF8: events plus byte count plus initial decoder. Shape validation performs
    no native decoding; runtime terminal legality is checked by measure.
    """
    if type(query) is not dict:
        raise ValueError("query must be an object")
    kind = "sqlite" if "actions" in query else "lru" if "capacity" in query else "utf8"
    _validate_shape(kind, query)
    if kind == "sqlite":
        return len(query["actions"]) + 2
    units = len(query["events"]) + 1
    if kind == "utf8":
        units += sum(len(e["bytes"]) for e in query["events"] if e["op"] == "feed")
    return units


def public_task(task):
    return {key: deepcopy(task[key]) for key in ("id", "source_id", "contract", "examples")}


def _put(key):
    return {"op": "put", "id": key}


def _delete(key):
    return {"op": "delete", "id": key}


def _op(op):
    return {"op": op}


def _call(key):
    return {"op": "call", "key": key}


def _feed(values):
    return {"op": "feed", "bytes": list(values)}


def _public_inputs(kind):
    if kind == "sqlite":
        return [{"actions": a} for a in (
            [], [_put(4)], [_put(4), _delete(4)],
            [_op("begin"), _put(9), _op("rollback")],
            [_put(3), _op("begin"), _put(11), _op("rollback")],
            [_op("begin"), _put(6), _op("commit"), _delete(6)],
            [_put(2), _op("begin"), _put(7)],
            [_put(7), _delete(7), _put(1)])]
    if kind == "lru":
        return [{"capacity": c, "events": e} for c, e in (
            (1, []), (1, [_call(1), _call(1)]),
            (1, [_call(1), _call(2), _call(1)]),
            (2, [_call(1), _call(2), _call(1)]),
            (2, [_call(1), _call(2), _call(1), _call(3), _call(2)]),
            (3, [_call(2), _call(4), _call(2), _op("reset"), _call(2)]),
            (4, [_call(1), _call(2), _call(3), _call(4), _call(1)]),
            (2, [_call(31), _op("reset"), _op("reset")]))]
    return [{"events": e} for e in (
        [], [_feed([65]), _op("finish")], [_feed([194])],
        [_feed([194]), _feed([163]), _op("finish")],
        [_feed([240, 159, 152, 128]), _op("finish")],
        [_feed([128])], [_feed([65]), _feed([66, 255])],
        [_feed([226, 130]), _op("finish"), _op("reset"), _feed([97]), _op("finish")])]


def _boundaries(kind):
    if kind == "sqlite":
        return [{"actions": a} for a in (
            [_put(1), _delete(1)], [_op("begin"), _put(1000)],
            [_put(2), _op("begin"), _delete(2), _put(1000), _op("rollback")],
            [_op("begin"), _put(1000), _op("commit"), _delete(1000)],
            [_delete(1000)], [_put(1000)],
            [_put(1), _op("begin"), _delete(1), _op("rollback")],
            [_op("begin"), _op("rollback")])]
    if kind == "lru":
        return [{"capacity": c, "events": e} for c, e in (
            (1, [_call(31), _call(0), _call(31)]),
            (4, [_call(k) for k in (0, 1, 2, 3, 0, 4, 1)]),
            (2, [_call(0), _op("reset"), _call(0), _call(0)]),
            (3, [_call(k) for k in (0, 1, 2, 0, 3, 1)]),
            (4, []), (3, [_op("reset")]), (2, [_call(31)]),
            (1, [_op("reset"), _call(0)]))]
    return [{"events": e} for e in (
        [_feed([0]), _op("finish")], [_feed([240, 159, 152]), _op("finish")],
        [_feed([237, 160, 128])], [_feed([97]), _feed([98, 255])],
        [_feed([]), _op("finish")], [_feed([244, 143, 191, 191]), _op("finish")],
        [_feed([255]), _op("reset")], [_op("finish"), _op("reset"), _feed([194])])]


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def authored_fixed_queries(source_id, examples):
    """Eight authored probes, including known UTF-8 standard boundaries.

    Only public input shapes are read. No expected answers, protected panels,
    candidate predictions, source measurements or private references are read.
    """
    kind = _family(source_id)
    if kind == 'utf8':
        # RFC 3629 restricted lead/continuation edges. This stronger authored
        # rival was identified retrospectively on exposed studies; freeze it
        # before new inference and do not embed source answers.
        words = ((0xC0,), (0xC1,), (0xF5,), (0xFF,),
                 (0xE0, 0x9F), (0xED, 0xA0), (0xF0, 0x8F), (0xF4, 0x90))
        boundaries = [{'events': [_feed(word)]} for word in words]
        known = {_canonical(row['input']) for row in examples}
        fallback = []
        for row in examples:
            events = row['input']['events']
            for cut in range(len(events) - 1, -1, -1):
                fallback.append({'events': deepcopy(events[:cut])})
        result = []
        for query in boundaries + _boundaries(kind) + fallback:
            key = _canonical(query)
            if key in known:
                continue
            _validate_shape(kind, query)
            known.add(key); result.append(deepcopy(query))
            if len(result) == PROBE_BUDGET:
                return result
        raise ValueError('public examples leave too few authored fixed probes')
    boundaries = _boundaries(kind)
    field = "actions" if kind == "sqlite" else "events"
    prefixes = []
    for row in examples:
        query = row["input"]
        for cut in range(len(query[field]) - 1, -1, -1):
            prefix = deepcopy(query)
            prefix[field] = prefix[field][:cut]
            prefixes.append(prefix)
    known = {_canonical(row["input"]) for row in examples}
    result = []
    for query in boundaries[:4] + prefixes + boundaries[4:]:
        key = _canonical(query)
        if key in known:
            continue
        _validate_shape(kind, query)
        known.add(key)
        result.append(deepcopy(query))
        if len(result) == PROBE_BUDGET:
            return result
    raise ValueError("public examples leave too few authored fixed probes")


def _sqlite_input(rng, index):
    """Random histories selected solely under the disclosed legal grammar."""
    visible, saved, actions = set(), None, []
    for unused in range(rng.randint(3, 26)):
        choices = ["put", "put", "delete", "delete"]
        choices += ["begin"] if saved is None else ["commit", "rollback"]
        op = rng.choice(choices)
        if op == "put":
            key = rng.randint(1, 1000)
            while key in visible:
                key = rng.randint(1, 1000)
            actions.append(_put(key))
            visible.add(key)
        elif op == "delete":
            key = rng.choice(sorted(visible)) if visible and rng.random() < .6 else rng.randint(1, 1000)
            actions.append(_delete(key))
            visible.discard(key)
        elif op == "begin":
            saved = set(visible)
            actions.append(_op(op))
        else:
            actions.append(_op(op))
            if op == "rollback":
                visible = saved
            saved = None
    if index % 3 == 0 and saved is None:
        actions.append(_op("begin"))
    elif index % 3 == 1:
        if saved is None:
            actions.append(_op("begin"))
        actions.append(_op("rollback"))
    elif index % 3 == 2:
        actions.append(_delete(rng.randint(1, 1000)))
    return {"actions": actions}


def _lru_input(rng, index):
    capacity = index % 4 + 1
    key = rng.randint(0, 31)
    events = [_call(key), _call(key)]
    for unused in range(rng.randint(1, 24)):
        events.append(_op("reset") if rng.random() < .2 else _call(rng.randint(0, 31)))
    if index % 3 == 0:
        events += [_op("reset"), _call(key)]
    return {"capacity": capacity, "events": events}


def _chunks(rng, raw):
    cuts = sorted(rng.sample(range(1, len(raw)), rng.randint(0, min(4, len(raw) - 1))))
    points = [0] + cuts + [len(raw)]
    return [_feed(raw[left:right]) for left, right in zip(points, points[1:])]


def _utf8_input(rng, index):
    alphabet = ["A", "z", "\0", "¢", "€", "😀", "\u07ff", "\u0800", "\ud7ff", "\ue000", "\U0010ffff"]
    modes = (("finished",), ("open",), ("pending",), ("incomplete_error",),
             ("invalid",), ("invalid", "finished"),
             ("finished", "incomplete_error", "open"), ("finished", "finished"))[index % 8]
    events = []
    for frame, mode in enumerate(modes):
        if frame:
            events.append(_op("reset"))
        raw = "".join(rng.choice(alphabet) for unused in range(rng.randint(1, 5))).encode("utf-8")
        if mode in ("pending", "incomplete_error"):
            tail = rng.choice(["¢", "€", "😀", "\U0010ffff"]).encode("utf-8")
            raw += tail[:rng.randint(1, len(tail) - 1)]
        events.extend(_chunks(rng, raw))
        if mode in ("finished", "incomplete_error"):
            events.append(_op("finish"))
        elif mode == "invalid":
            bad = rng.choice([[128], [255], [192, 128], [237, 160, 128],
                              [244, 144, 128, 128], [224, 128, 128], [226, 40, 161]])
            # A valid prefix inside a failing call must not inflate the count.
            events.append(_feed([rng.randint(0, 127)] + bad))
    return {"events": events}


GENERATORS = {"sqlite": _sqlite_input, "lru": _lru_input, "utf8": _utf8_input}


def build_dataset(seed=DEFAULT_SEED, panel_size=48, parents_per_contract=2):
    """Freeze parent tasks before inference, without panel-based selection.

    Parent replicates per authored contract are not independent production
    problems. Each panel is freshly sampled and exact-input disjoint across
    both replicates of its contract, public examples and fixed tester probes.
    """
    if type(seed) is not int:
        raise ValueError("seed must be an integer")
    sqlite_tasks._integer(panel_size, 1, 256, "panel_size")
    sqlite_tasks._integer(parents_per_contract, 1, 32, "parents_per_contract")
    public = {kind: [{"input": q, "expected": measure(kind, q)}
                     for q in _public_inputs(kind)] for kind in FAMILIES}
    fixed = {kind: authored_fixed_queries(kind, public[kind]) for kind in FAMILIES}
    seen = {kind: {_canonical(row["input"]) for row in public[kind]}
            | {_canonical(q) for q in fixed[kind]} for kind in FAMILIES}
    tasks = []
    for replicate in range(parents_per_contract):
        for kind in FAMILIES:
            source_id = f"{kind}-{replicate}"
            task = {"id": f"native-{source_id}", "source_id": source_id,
                    "parent_replicate": replicate, "contract": CONTRACTS[kind],
                    "examples": deepcopy(public[kind]), "fixed_queries": deepcopy(fixed[kind])}
            for panel in ("screen", "confirmation"):
                rng = random.Random(f"{seed}:{kind}:{replicate}:{panel}")
                rows = []
                attempts = 0
                while len(rows) < panel_size:
                    attempts += 1
                    if attempts > panel_size * 1000:
                        raise RuntimeError("could not populate disjoint native panel")
                    query = GENERATORS[kind](rng, len(rows))
                    key = _canonical(query)
                    if key in seen[kind]:
                        continue
                    expected = measure(source_id, query)
                    seen[kind].add(key)
                    rows.append({"input": query, "expected": expected})
                task[panel] = rows
            task["reference_source"] = {"sqlite": sqlite_tasks.SQLITE_REFERENCE,
                                        "lru": LRU_REFERENCE, "utf8": None}[kind]
            tasks.append(task)
    return {"schema": "zenith_native_conformance_dataset_v1", "seed": seed,
            "panel_size": panel_size, "parents_per_contract": parents_per_contract,
            "probe_budget": PROBE_BUDGET,
            "max_query_units": {"sqlite": 34, "lru": 33, "utf8": 289},
            "source_versions": {"python": platform.python_version(), "sqlite": sqlite3.sqlite_version,
                                "lru": "stdlib functools.lru_cache", "utf8": "stdlib codecs strict utf-8"},
            "adaptation": deepcopy(ADAPTATION),
            "boundary": "Authored three-wrapper diagnostic population; fresh model parents, no initial buggy program, no production or novelty claim.",
            "tasks": tasks}
