"""Bounded source fixtures for a learned-decomposition diagnostic.

The sensor and event sources are deliberately synthetic. Only the allocation
source runs native SQLite. These four constructed mechanisms are neither
production workloads nor a population from which to infer general transfer.
Private truth, reference programs and protected panels must never enter a
provider request; ``public_task`` is the model-facing allowlist.
"""
from __future__ import annotations

from copy import deepcopy
import json
import random
import sqlite3


MAX_ROWS = 32
MAX_ACTIONS = 32
MAX_EVENTS = 32
MAX_KEYS = 8
DEFAULT_SEED = 20261014

SENSOR_DESCRIPTION = """Synthetic diagnostic sensor source. A fresh query is exactly
{"rows": [integer, ...]}, with 0..32 readings, each -100..100. Each individual
reading is converted by one stable, source-private affine calibration s*x+b;
s is an integer 1..5 and b is an integer -15..15. The answer is the integer sum
of the calibrated individual readings, zero for an empty group. Individual
and grouped observed receipts are available; infer the calibration from them.
An allowed source probe uses exactly this same input schema and returns that
integer. There are no acquisition tables, ambient context fields or clocks.
Implement investigate(context, acquire), returning a JSON integer. The supplied
program is an experimental starting point, not a source specification.
"""

SQLITE_DESCRIPTION = """Native SQLite diagnostic source. Each query starts an empty
in-memory database with one table whose id column is INTEGER PRIMARY KEY
AUTOINCREMENT. Input is exactly {"actions": [action, ...]}, at most 32 actions.
An action is exactly {"op":"put", "id":n}, {"op":"delete", "id":n}, or
{"op":"begin"}, {"op":"commit"}, {"op":"rollback"}. IDs are integers
1..1000. Put inserts the explicit ID; it must be absent in the current
transactional view. Delete may name an absent ID. Transactions cannot nest;
commit/rollback require an open transaction. The sequence may end with an
open transaction. Operations and the final measurement use the same connection.
After the actions, insert one row without specifying an ID and return its
automatically allocated ID as an integer. The source has no other tables,
triggers, conflicts, connections or hidden modes. An allowed source probe uses
exactly this schema and returns this native measurement. There are no
acquisition tables. Implement investigate(context, acquire), returning a JSON
integer. The seed program is an experimental hypothesis.
"""

STREAM_DESCRIPTION = """Synthetic diagnostic keyed-event source. Input is exactly
{"events": [{"key":text,"time":integer,"value":integer}, ...], "keys":[text,...]}.
There are 0..32 events and 0..8 distinct requested keys. Keys are nonempty ASCII
letters, digits, '_' or '-', at most 20 characters. Times are integers
-1000..1000 and values -100..100. Arrival order is list order. The source uses
one fixed, private member of this disclosed two-rule family: either select the
last arriving event for each key, or select the event with greatest event
timestamp for each key (last arrival wins equal timestamps). Missing keys have
value null. Return [{"key":key,"value":selected-value-or-null}, ...] in the
requested-key order. No sum, sorting of requested keys or cross-key selection
is performed. Observed receipts distinguish the possible rules. An allowed
source probe uses exactly this input schema and returns that JSON list. There
are no acquisition tables, clocks or ambient context. Implement
investigate(context, acquire). The seed program is an experimental hypothesis.
"""


def _sensor_seed(scale: int) -> str:
    return f'''def sum_readings(rows):
    return sum(rows)

def calibrate(total):
    return {scale} * total

def investigate(context, acquire):
    return calibrate(sum_readings(context["rows"]))
'''


SQLITE_SEED = '''def visible_rows(actions):
    rows = []
    saved = []
    for action in actions:
        op = action["op"]
        if op == "put":
            rows.append(action["id"])
        elif op == "delete":
            if action["id"] in rows:
                rows.remove(action["id"])
        elif op == "begin":
            saved = list(rows)
        elif op == "rollback":
            rows = list(saved)
    return sorted(rows)

def next_id(rows):
    return max(rows + [0]) + 1

def investigate(context, acquire):
    return next_id(visible_rows(context["actions"]))
'''

STREAM_SEED = '''def project_values(events):
    return [event["value"] for event in events]

def select_latest(values, keys):
    value = values[-1] if values else None
    return [{"key": key, "value": value} for key in keys]

def investigate(context, acquire):
    return select_latest(project_values(context["events"]), context["keys"])
'''

SQLITE_REFERENCE = '''def allocation_state(actions):
    rows = []
    high = 0
    saved_rows = []
    saved_high = 0
    for action in actions:
        op = action["op"]
        if op == "put":
            rows.append(action["id"])
            high = max(high, action["id"])
        elif op == "delete":
            if action["id"] in rows:
                rows.remove(action["id"])
        elif op == "begin":
            saved_rows = list(rows)
            saved_high = high
        elif op == "rollback":
            rows = list(saved_rows)
            high = saved_high
    return {"rows": rows, "high": high}

def next_id(state):
    return max(state["rows"] + [state["high"], 0]) + 1

def investigate(context, acquire):
    return next_id(allocation_state(context["actions"]))
'''

STREAM_REFERENCE = '''def keyed_events(events):
    selected = {}
    for event in events:
        key = event["key"]
        if key not in selected or event["time"] >= selected[key]["time"]:
            selected[key] = event
    return selected

def select_latest(selected, keys):
    return [{"key": key, "value": selected[key]["value"] if key in selected else None} for key in keys]

def investigate(context, acquire):
    return select_latest(keyed_events(context["events"]), context["keys"])
'''


def _integer(value, lower: int, upper: int, label: str) -> int:
    if type(value) is not int or not lower <= value <= upper:
        raise ValueError(f"{label} must be an integer {lower}..{upper}")
    return value


def _object(value, fields: set[str], label: str) -> dict:
    if type(value) is not dict or set(value) != fields:
        raise ValueError(f"{label} must contain exactly {sorted(fields)}")
    return value


def _list(value, limit: int, label: str) -> list:
    if type(value) is not list or len(value) > limit:
        raise ValueError(f"{label} must be a list of at most {limit} entries")
    return value


def _key(value) -> str:
    if (type(value) is not str or not 1 <= len(value) <= 20
            or any(char not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-" for char in value)):
        raise ValueError("key must be 1..20 ASCII letters, digits, '_' or '-'")
    return value


def _actions(value) -> list[dict]:
    actions = _list(value, MAX_ACTIONS, "actions")
    visible: set[int] = set()
    saved = None
    for action in actions:
        if type(action) is not dict:
            raise ValueError("action must be an object")
        op = action.get("op")
        if op in ("put", "delete"):
            _object(action, {"op", "id"}, "action")
            item = _integer(action["id"], 1, 1000, "id")
            if op == "put":
                if item in visible:
                    raise ValueError("put requires an absent id")
                visible.add(item)
            else:
                visible.discard(item)
        elif op in ("begin", "commit", "rollback"):
            _object(action, {"op"}, "action")
            if op == "begin":
                if saved is not None:
                    raise ValueError("transactions cannot nest")
                saved = set(visible)
            else:
                if saved is None:
                    raise ValueError("transaction completion requires begin")
                if op == "rollback":
                    visible = saved
                saved = None
        else:
            raise ValueError("unsupported action")
    return actions


def oracle(task: dict, input: dict):
    """Measure one fresh bounded query. Only the host may call this function."""
    config = task["private"]
    kind = config["kind"]
    if kind == "sensor":
        _object(input, {"rows"}, "input")
        readings = _list(input["rows"], MAX_ROWS, "rows")
        for reading in readings:
            _integer(reading, -100, 100, "reading")
        return sum(config["scale"] * reading + config["offset"] for reading in readings)
    if kind == "sqlite":
        _object(input, {"actions"}, "input")
        actions = _actions(input["actions"])
        connection = sqlite3.connect(":memory:", isolation_level=None)
        try:
            connection.execute("CREATE TABLE items (id INTEGER PRIMARY KEY AUTOINCREMENT)")
            for action in actions:
                if action["op"] == "put":
                    connection.execute("INSERT INTO items(id) VALUES (?)", (action["id"],))
                elif action["op"] == "delete":
                    connection.execute("DELETE FROM items WHERE id = ?", (action["id"],))
                else:
                    connection.execute({"begin": "BEGIN", "commit": "COMMIT", "rollback": "ROLLBACK"}[action["op"]])
            return int(connection.execute("INSERT INTO items DEFAULT VALUES").lastrowid)
        finally:
            connection.close()
    if kind == "stream":
        _object(input, {"events", "keys"}, "input")
        events = _list(input["events"], MAX_EVENTS, "events")
        keys = _list(input["keys"], MAX_KEYS, "keys")
        for key in keys:
            _key(key)
        if len(set(keys)) != len(keys):
            raise ValueError("requested keys must be distinct")
        selected = {}
        for event in events:
            _object(event, {"key", "time", "value"}, "event")
            key = _key(event["key"])
            _integer(event["time"], -1000, 1000, "time")
            _integer(event["value"], -100, 100, "value")
            if (key not in selected or config["rule"] == "arrival"
                    or event["time"] >= selected[key]["time"]):
                selected[key] = event
        return [{"key": key, "value": selected[key]["value"] if key in selected else None} for key in keys]
    raise ValueError("unknown private source kind")


def public_task(task: dict) -> dict:
    """Copy only allowed training material, never protected cases or truth."""
    fields = ("id", "family", "description", "initial_source", "focus_function", "calibration", "development")
    return {field: deepcopy(task[field]) for field in fields}


def reference_source(task: dict) -> str:
    """Competent ordinary-code control, deliberately withheld from models."""
    return task["private"]["reference_source"]


def _put(item: int) -> dict:
    return {"op": "put", "id": item}


def _delete(item: int) -> dict:
    return {"op": "delete", "id": item}


def _tx(op: str) -> dict:
    return {"op": op}


def _sensor_calibration() -> list[dict]:
    return [{"rows": rows} for rows in ([], [0], [1], [-1], [3], [1, 2], [4, -1], [0, 0, 0])]


def _sqlite_calibration() -> list[dict]:
    sequences = [[], [_put(4)], [_put(4), _delete(4)], [_put(2), _put(7), _delete(7)],
                 [_tx("begin"), _put(9), _tx("rollback")],
                 [_put(3), _tx("begin"), _put(11), _tx("rollback")],
                 [_tx("begin"), _put(6), _tx("commit"), _delete(6)],
                 [_put(10), _delete(10), _put(2)]]
    return [{"actions": actions} for actions in sequences]


def _event(key: str, time: int, value: int) -> dict:
    return {"key": key, "time": time, "value": value}


def _stream_calibration() -> list[dict]:
    return [
        {"events": [], "keys": ["a"]},
        {"events": [_event("a", 1, 4)], "keys": ["a"]},
        {"events": [_event("a", 1, 4), _event("a", 9, 8)], "keys": ["a"]},
        {"events": [_event("a", 9, 4), _event("a", 1, 8)], "keys": ["a"]},
        {"events": [_event("a", 9, 4), _event("b", 1, 8)], "keys": ["a", "b"]},
        {"events": [_event("b", 9, 4), _event("a", 1, 8)], "keys": ["a", "b"]},
        {"events": [_event("a", 3, 4), _event("a", 3, -2)], "keys": ["a", "missing"]},
        {"events": [_event("a", 8, 0), _event("b", 7, 0), _event("a", 2, 9)], "keys": ["b", "a"]},
    ]


def _sensor_input(rng: random.Random, panel: int, index: int) -> dict:
    lengths = ((2, 3, 4, 6), (5, 7, 8, 10), (9, 11, 12, 16, 24, 32))[panel]
    count = lengths[index % len(lengths)]
    readings = [rng.randint(-20, 20) for unused in range(count)]
    # Repeated, zero and cancellation groups exercise different row structure.
    mode = index % 4
    if mode == 0:
        readings[0] = 0
    elif mode == 1:
        readings[-1] = readings[0]
    elif mode == 2:
        readings[1] = -readings[0]
    return {"rows": readings}


def _sqlite_input(rng: random.Random, panel: int, index: int) -> dict:
    low, middle, high, upper = (rng.randint(1, 30), rng.randint(50, 90),
                                rng.randint(100, 200), rng.randint(300, 500))
    p, d, b, c, r = _put, _delete, _tx("begin"), _tx("commit"), _tx("rollback")
    sequences = (
        ([p(high), d(high)], [p(low), p(high), d(high)], [b, p(high), r],
         [p(low), b, p(high), r, d(low)], [b, p(high), c, d(high)],
         [p(high), d(high), p(low)], [p(low), b, d(low), p(high), r],
         [p(low), b, d(low), p(high), c, d(high)]),
        ([p(low), p(high), d(high), p(middle), d(middle)],
         [p(low), b, p(high), d(high), r, p(middle)],
         [b, p(high), c, b, p(upper), r, d(high)],
         [p(low), b, d(low), p(high), c, d(high)],
         [p(low), p(high), b, d(high), r, d(high), p(middle)],
         [b, p(high), d(high), c, p(low)],
         [b, p(high), r, b, p(middle), c, d(middle)],
         [p(high), d(high), b, p(low), c, d(low)]),
        ([p(low), b, p(high), c, d(high), b, p(upper), r, p(middle)],
         [p(high), d(high), b, p(low), r, b, p(middle), c, d(middle)],
         [b, p(high), d(high), r, b, p(middle), c, d(middle), p(low)],
         [p(low), b, d(low), p(high), r, b, p(middle), c, d(middle)],
         [p(low), b, p(high), d(high), c, b, p(upper), r, d(low)],
         [b, p(high), c, b, d(high), p(upper), r, d(high), p(low)],
         [p(high), b, p(upper), c, d(upper), b, p(middle), r, d(high)],
         [p(low), b, p(high), r, b, p(upper), d(upper), c, d(low)]),
    )
    actions = deepcopy(sequences[panel][index % 8])
    # Later panels additionally query during an open transaction and include
    # harmless deletion of an absent row, rather than only varying constants.
    if panel and index % 3 == 0:
        actions += [b, p(upper + 1)]
    if panel and index % 3 == 1:
        actions.insert(0, d(999))
    return {"actions": actions}


def _stream_input(rng: random.Random, panel: int, index: int) -> dict:
    key_count = (2, 4, 6)[panel]
    keys = [f"k{panel}_{item}" for item in range(key_count)]
    events = []
    # Increasing key cardinality, cross-key interleavings, out-of-order and
    # equal-time updates, missing requested keys and reordered requests.
    for step in range((2, 3, 4)[panel]):
        order = list(keys)
        rng.shuffle(order)
        for key in order:
            time = rng.randint(-30, 30)
            if step == 1 and index % 3 == 0:
                time = next(event["time"] for event in events if event["key"] == key)
            events.append(_event(key, time, rng.randint(-20, 20)))
    rng.shuffle(keys)
    requested = keys + ([f"absent{panel}"] if index % 2 == 0 else [])
    if index % 5 == 0:
        requested = requested[:1]
    return {"events": events, "keys": requested}


def _canonical(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _task(task_id: str, kind: str, private: dict, source: str, focus: str, description: str) -> dict:
    return {"id": task_id, "family": kind, "description": description,
            "initial_source": source, "focus_function": focus, "private": private}


def build_dataset(seed: int = DEFAULT_SEED, panel_size: int = 24) -> dict:
    """Freeze eight observed examples and three disjoint fresh panels per task.

    Development contains fresh inputs only. Calibration remains a separately
    labelled training set; selection should replay both visible sets.
    Protected screen and confirmation answers are host-only.
    """
    if type(seed) is not int:
        raise ValueError("seed must be an integer")
    _integer(panel_size, 1, 256, "panel_size")
    rng = random.Random(seed)
    scale, offset = rng.choice((3, 4, 5)), rng.randint(3, 15)
    control_scale = rng.choice((2, 3, 4, 5))
    sensor_reference = f'''def calibrate_rows(rows):
    return [{scale} * reading + {offset} for reading in rows]

def sum_readings(rows):
    return sum(rows)

def investigate(context, acquire):
    return sum_readings(calibrate_rows(context["rows"]))
'''
    tasks = [
        _task("task-0", "synthetic_sensor", {"kind": "sensor", "scale": scale, "offset": offset,
              "reference_source": sensor_reference}, _sensor_seed(2), "calibrate", SENSOR_DESCRIPTION),
        _task("task-1", "native_sqlite", {"kind": "sqlite", "sqlite_version": sqlite3.sqlite_version,
              "reference_source": SQLITE_REFERENCE}, SQLITE_SEED, "next_id", SQLITE_DESCRIPTION),
        _task("task-2", "synthetic_keyed_stream", {"kind": "stream", "rule": "timestamp",
              "reference_source": STREAM_REFERENCE}, STREAM_SEED, "select_latest", STREAM_DESCRIPTION),
        _task("task-3", "synthetic_sensor", {"kind": "sensor", "scale": control_scale, "offset": 0,
              "reference_source": _sensor_seed(control_scale)}, _sensor_seed(control_scale), "calibrate", SENSOR_DESCRIPTION),
    ]
    for task in tasks:
        kind = task["private"]["kind"]
        calibration = {"sensor": _sensor_calibration, "sqlite": _sqlite_calibration,
                       "stream": _stream_calibration}[kind]()
        generator = {"sensor": _sensor_input, "sqlite": _sqlite_input, "stream": _stream_input}[kind]
        task["calibration"] = [{"input": deepcopy(query), "expected": oracle(task, query)} for query in calibration]
        seen = {_canonical(query) for query in calibration}
        for panel, name in enumerate(("development", "screen", "confirmation")):
            rows = []
            attempts = 0
            while len(rows) < panel_size:
                query = generator(rng, panel, attempts)
                attempts += 1
                key = _canonical(query)
                if key in seen:
                    continue
                seen.add(key)
                rows.append({"input": query, "expected": oracle(task, query)})
                if attempts > panel_size * 100:
                    raise RuntimeError("could not construct a distinct panel")
            task[name] = rows
    return {"schema": "zenith-decomposition-tasks-v1", "seed": seed, "panel_size": panel_size,
            "limitations": ["Three synthetic diagnostic sources and one native SQLite source; no production transfer claim.",
                            "Four authored mechanisms are not independent replications or a representative task population.",
                            "SQLite puts use explicit fresh positive IDs; conflicts, triggers and multiple connections are excluded.",
                            "Held-out structure is authored and bounded; lengths, key counts and action combinations are not new source mechanisms."],
            "tasks": tasks}
