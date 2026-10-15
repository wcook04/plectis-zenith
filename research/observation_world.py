"""Native SQLite measurement experiments with learner/evaluator separation.

The disclosed family varies SQL conflict handling, insertion instrumentation and
counter selection. SQLite executes every observation; no synthetic answer rule
stands in for database behavior. Identification is conditional on this frozen
family, not a guarantee about arbitrary software or all SQLite features.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from functools import lru_cache
import hashlib
import itertools
import json
from pathlib import Path
import random
import sqlite3
import tempfile
from typing import Iterable

PROTOCOL_VERSION = "sqlite-observation-v2"
GOALS = ("channel", "committed_count", "committed_sum")
CHECKPOINT_PREFIXES = (3, 6, 9)
MAX_ACTIONS = 32
CONFLICTS = ("ignore", "replace", "upsert")
COUNTERS = ("main_direct", "main_total", "all_total")


def _canonical(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


@dataclass(frozen=True)
class WorldConfig:
    """Evaluator-only source configuration. Never include this in a prompt."""

    source_id: str
    conflict: str
    insert_trigger: bool
    counter: str

    def __post_init__(self):
        if not self.source_id or self.conflict not in CONFLICTS or self.counter not in COUNTERS:
            raise ValueError("invalid private world configuration")
        if type(self.insert_trigger) is not bool:
            raise ValueError("insert_trigger must be boolean")


def world(seed: int) -> WorldConfig:
    """Create a stable opaque identity and a private native configuration."""
    rng = random.Random(seed)
    source_id = "source-" + hashlib.sha256(f"{PROTOCOL_VERSION}:{seed}".encode()).hexdigest()[:20]
    return WorldConfig(source_id, rng.choice(CONFLICTS), bool(rng.randrange(2)), rng.choice(COUNTERS))


def task_spec() -> str:
    return """Predict a disposable SQLite source from its past measured experiments.
Each experiment starts with an empty items table (text primary key, nonnegative
integer value) and fresh main/other database connections. No state carries between
experiments. Actions are JSON dictionaries: put(key,value), update(key,value),
delete(key), begin, commit, rollback. Use the field op for the action name; an
optional connection is main (default) or other. Put submits an insertion with the
source's stable conflict handling; update changes an existing item's value;
delete removes an item. Values are integers 0..1000000 and keys are nonempty text
up to 40 characters. At most 32 actions are permitted. Transactions cannot nest.
While a transaction is open, writes and transaction actions use that connection;
the other connection can write after commit or rollback. A sequence may end with
an open transaction. A separate read connection measures committed state.

The source belongs to this disclosed, fixed 18-member family. Its put operation
uses exactly one of SQLite INSERT OR IGNORE, INSERT OR REPLACE, or INSERT with
ON CONFLICT(id) DO UPDATE of the value. Instrumentation is either absent or one
AFTER INSERT trigger that inserts exactly one row into an otherwise unread
auxiliary log; there are no other triggers. Its channel is exactly one of:
main connection changes() (last direct row-change count), main total_changes,
or main total_changes plus other total_changes. Each combination is possible.
The actual combination is private and stable for this source. Infer it from
measurements, using native SQLite semantics; do not assume a counter measures
net committed effects. Calibration history gives actions, emitted channel and
independently read committed item count/value sum.

A query supplies a fresh action sequence and one goal: channel (the source's
emitted number), committed_count (items visible to the separate committed-state
reader), or committed_sum (sum of their values, zero when empty). Query contexts
contain no outcome for the requested sequence. Return value as an integer and
unresolved=false when the calibration evidence supports that answer, otherwise
value=null and unresolved=true. A value is supported exactly when every member
of the disclosed family consistent with all calibration receipts predicts that
same value for this goal and sequence. Otherwise it is unresolved; an unsupported
lucky guess is not a supported answer. Author your own executable predictor;
no candidate programs, simulator or solver library are supplied.
"""


def _actions(actions: Iterable[dict]) -> list[dict]:
    rows = list(actions)
    if len(rows) > MAX_ACTIONS:
        raise ValueError("action budget exceeded")
    answer = []
    active = None
    for action in rows:
        if not isinstance(action, dict):
            raise ValueError("actions must be objects")
        op = action.get("op")
        connection = action.get("connection", "main")
        if op not in ("put", "update", "delete", "begin", "commit", "rollback") or connection not in ("main", "other"):
            raise ValueError("unsupported action or connection")
        fields = {"op", "connection"}
        if op in ("put", "update", "delete"):
            fields.add("key")
            key = action.get("key")
            if not isinstance(key, str) or not 1 <= len(key) <= 40:
                raise ValueError("invalid key")
        if op in ("put", "update"):
            fields.add("value")
            value = action.get("value")
            if type(value) is not int or not 0 <= value <= 1_000_000:
                raise ValueError("invalid value")
        if set(action) - fields or fields - {"connection"} - set(action):
            raise ValueError("unexpected or missing action fields")
        if active is not None and connection != active:
            raise ValueError("cross-connection write during an open transaction")
        if op == "begin":
            if active is not None:
                raise ValueError("nested transaction")
            active = connection
        elif op in ("commit", "rollback"):
            if active != connection:
                raise ValueError("transaction completion without matching begin")
            active = None
        # Preserve the caller's default spelling in the public receipt.
        answer.append(json.loads(_canonical(action)))
    return answer


def _run_native(config: WorldConfig, actions: list[dict]) -> tuple[int, int, int]:
    with tempfile.TemporaryDirectory(prefix="zenith-native-observation-") as directory:
        path = Path(directory) / "world.sqlite"
        main = sqlite3.connect(path, isolation_level=None, timeout=1)
        other = sqlite3.connect(path, isolation_level=None, timeout=1)
        reader = sqlite3.connect(path, isolation_level=None, timeout=1)
        try:
            main.executescript("CREATE TABLE items(id TEXT PRIMARY KEY, value INTEGER NOT NULL);"
                               "CREATE TABLE insertion_log(item_id TEXT NOT NULL);")
            if config.insert_trigger:
                main.executescript("CREATE TRIGGER inserted AFTER INSERT ON items BEGIN "
                                   "INSERT INTO insertion_log VALUES(NEW.id); END;")
            statements = {
                "ignore": "INSERT OR IGNORE INTO items VALUES(?,?)",
                "replace": "INSERT OR REPLACE INTO items VALUES(?,?)",
                "upsert": "INSERT INTO items VALUES(?,?) ON CONFLICT(id) DO UPDATE SET value=excluded.value",
            }
            connections = {"main": main, "other": other}
            for action in actions:
                con = connections[action.get("connection", "main")]
                op = action["op"]
                if op == "put":
                    con.execute(statements[config.conflict], (action["key"], action["value"]))
                elif op == "update":
                    con.execute("UPDATE items SET value=? WHERE id=?", (action["value"], action["key"]))
                elif op == "delete":
                    con.execute("DELETE FROM items WHERE id=?", (action["key"],))
                else:
                    con.execute(op.upper())
            if config.counter == "main_direct":
                channel = main.execute("SELECT changes()").fetchone()[0]
            elif config.counter == "main_total":
                channel = main.total_changes
            else:
                channel = main.total_changes + other.total_changes
            count, total = reader.execute("SELECT COUNT(*), COALESCE(SUM(value),0) FROM items").fetchone()
            return channel, count, total
        finally:
            reader.close()
            other.close()
            main.close()


def observe(config: WorldConfig, actions: Iterable[dict]) -> dict:
    """Execute one permitted probe; return no private flags or SQL statements."""
    actions = _actions(actions)
    values = _run_native(config, actions)
    receipt = {"source_id": config.source_id, "actions": actions,
               "observed": dict(zip(GOALS, values)),
               "authority": "native SQLite counter; committed state read through a separate connection",
               "sqlite_version": sqlite3.sqlite_version}
    receipt["receipt_sha256"] = hashlib.sha256(_canonical(receipt).encode()).hexdigest()
    return receipt


@lru_cache(maxsize=8192)
def _oracle(conflict: str, trigger: bool, counter: str, encoded_actions: str) -> tuple[int, int, int]:
    # Evaluator-only caching; the recorded learner probe still executes afresh.
    return _run_native(WorldConfig("evaluator", conflict, trigger, counter), json.loads(encoded_actions))


def _native_values(config: WorldConfig, actions: list[dict]) -> tuple[int, int, int]:
    return _oracle(config.conflict, config.insert_trigger, config.counter, _canonical(actions))


def compatible(config: WorldConfig, receipts: Iterable[dict]) -> list[WorldConfig]:
    """Private identification guard; hypotheses themselves never enter cases."""
    receipts = list(receipts)
    for receipt in receipts:
        if receipt.get("source_id") != config.source_id:
            raise ValueError("receipt belongs to another source")
        unsigned = {k: v for k, v in receipt.items() if k != "receipt_sha256"}
        if receipt.get("receipt_sha256") != hashlib.sha256(_canonical(unsigned).encode()).hexdigest():
            raise ValueError("receipt content changed")
        actions = _actions(receipt["actions"])
        if receipt["observed"] != dict(zip(GOALS, _native_values(config, actions))):
            raise ValueError("history does not match the actual native source")
    candidates = [WorldConfig(config.source_id, conflict, trigger, counter)
                  for conflict, trigger, counter in itertools.product(CONFLICTS, (False, True), COUNTERS)]
    return [candidate for candidate in candidates
            if all(dict(zip(GOALS, _native_values(candidate, _actions(receipt["actions"])))) == receipt["observed"]
                   for receipt in receipts)]


def expected(config: WorldConfig, receipts: Iterable[dict], actions: Iterable[dict], goal: str) -> dict:
    """Plain answer key, using exact native executions of compatible worlds."""
    if goal not in GOALS:
        raise ValueError("unknown goal")
    actions = _actions(actions)
    candidates = compatible(config, receipts)
    index = GOALS.index(goal)
    values = {_native_values(candidate, actions)[index] for candidate in candidates}
    if not values:
        raise ValueError("no compatible native world")
    return {"value": next(iter(values)) if len(values) == 1 else None,
            "unresolved": len(values) != 1}


def _put(key: str, value: int, connection: str = "main") -> dict:
    return {"op": "put", "key": key, "value": value, "connection": connection}


def discovery_sequences() -> list[list[dict]]:
    """Nine common probes; freeze prefixes 3/6/9 for the trajectory."""
    return [[], [_put("a", 2)], [_put("a", 2, "other")],
            [_put("a", 2), _put("a", 5)],
            [_put("a", 2), _put("b", 2)],
            [_put("a", 2), _put("b", 3), _put("c", 4)],
            [{"op": "begin"}, _put("a", 2), {"op": "rollback"}],
            [_put("a", 2), {"op": "update", "key": "a", "value": 2}],
            [_put("a", 2), _put("b", 4, "other")]]


def task_sequences(seed: int, partition: str = "eval") -> list[list[dict]]:
    """Predeclared structural partitions; row seeds are not semantic domains.

    Learn = fixed discovery actions. Challenge = five single new compositions.
    Eval = sixteen further compositions, never an exact discovery/challenge
    sequence. Values vary independently without determining the source policy.
    """
    if partition == "learn":
        return discovery_sequences()
    if partition not in ("challenge", "eval"):
        raise ValueError("unknown partition")
    rng = random.Random(seed)
    x, y, z = rng.sample(range(11, 100), 3)
    put, begin, commit, rollback = _put, {"op": "begin"}, {"op": "commit"}, {"op": "rollback"}
    update = {"op": "update", "key": "a", "value": y}
    noop = {"op": "update", "key": "a", "value": x}
    delete = {"op": "delete", "key": "a"}
    if partition == "challenge":
        return [[begin, put("a", x), put("a", y), commit],
                [put("a", x), begin, put("a", y), rollback],
                [put("a", x), put("a", y, "other")],
                [put("a", x), update, delete],
                [begin, put("a", x)]]
    return [[put("a", x), begin, put("a", y), rollback, put("b", z, "other")],
            [put("a", x, "other"), put("a", y, "other"), delete],
            [put("a", x), begin, noop, put("b", z), rollback, put("c", y)],
            [put("a", x), put("a", y), put("a", z), delete],
            [put("a", x), update, put("b", z, "other")],
            [put("a", x), begin, update, rollback, put("a", z, "other")],
            [begin, put("a", x), put("b", x)],
            [put("a", x), begin, delete, put("a", y), commit, put("c", z, "other")],
            [put("a", x, "other"), {"op": "begin", "connection": "other"},
             put("a", y, "other"), {"op": "rollback", "connection": "other"}, put("b", z)],
            [put("a", x), delete, put("a", y, "other")],
            [put("a", x), {"op": "update", "key": "absent", "value": y}, put("b", z, "other")],
            [put("a", x), begin, update, commit, begin, delete, rollback],
            [put("a", x), put("b", x), put("a", x), put("b", y, "other")],
            [put("a", x), begin, put("b", y), rollback, begin, put("c", z), commit],
            [put("a", x), put("a", y), put("b", z), {"op": "delete", "key": "absent"}],
            [put("a", x, "other"), put("b", y, "other"), begin, put("c", z), rollback]]


def cases(config: WorldConfig, receipts: Iterable[dict], sequences: Iterable[list[dict]],
          goals: Iterable[str] = GOALS) -> list[tuple[dict, dict]]:
    """Return config-free executor cases and separately retained answer keys."""
    receipts = json.loads(_canonical(list(receipts)))
    hypotheses = compatible(config, receipts)
    goals = tuple(goals)
    if any(goal not in GOALS for goal in goals):
        raise ValueError("unknown goal")
    result = []
    for sequence in sequences:
        actions = _actions(sequence)
        for goal in goals:
            identity = hashlib.sha256(_canonical([config.source_id, receipts, actions, goal]).encode()).hexdigest()
            case = {"id": identity, "source_id": config.source_id, "actions": actions,
                    "goal": goal, "documentation": task_spec(), "tables": {"history": receipts}}
            values = {_native_values(candidate, actions)[GOALS.index(goal)] for candidate in hypotheses}
            key = {"value": next(iter(values)) if len(values) == 1 else None, "unresolved": len(values) != 1}
            result.append((case, key))
    return result


def make_dataset(seed: int, n_worlds: int = 12) -> dict:
    """Generate a source-bound protocol with explicitly separate private custody.

    Native settings are balanced marginally in complete blocks of six sources.
    Configured sources are conditional replications, not new semantic domains.
    The parent must freeze all code and the dataset before model inference.
    """
    if type(n_worlds) is not int or n_worlds < 1:
        raise ValueError("positive number of worlds required")
    rng = random.Random(seed)
    conflicts, counters = list(CONFLICTS), list(COUNTERS)
    rng.shuffle(conflicts)
    rng.shuffle(counters)
    streams, configs = [], {}
    for index in range(n_worlds):
        source = world(seed * 10000 + index)
        config = WorldConfig(source.source_id, conflicts[index % 3], bool((index // 3) % 2),
                             counters[(index // 3 + index) % 3])
        configs[config.source_id] = asdict(config)
        receipts = [observe(config, actions) for actions in discovery_sequences()]
        streams.append({"source_id": config.source_id, "receipts": receipts,
                        "partitions": {name: task_sequences(seed * 10000 + index, name)
                                       for name in ("learn", "challenge", "eval")}})
    public = {"protocol_version": PROTOCOL_VERSION, "documentation": task_spec(),
              "checkpoint_prefixes": list(CHECKPOINT_PREFIXES), "streams": streams}
    return {"public": public, "private": {"configs": configs, "native_family_size": 18,
            "identification_scope": "exact predictions conditional on the frozen native family",
            "oracle": "actual SQLite execution; separate committed-state reader"}}
