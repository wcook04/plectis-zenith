"""Offline client-workflow investigation fixtures backed by real SQLite.

These authored, exposed development tasks test client obligations rather than
SQLite emulation: each step must be atomic, preserve a caller-owned transaction,
and permit a later caller action after a failure. The hidden implementation
binding and held-out panel must live outside an investigator's tool process in
an actual study; ``public_task`` alone is an allowlist, not a security boundary.
No model, provider, generated-code executor, or network access is used here.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Any


class StepFailure(Exception):
    """A client operation cannot complete its external obligation."""


IMPORT_CONTRACT = ("An ordered batch insert is all-or-nothing on a real SQLite "
    "table with unique keys 1..9. A duplicate or key 10 makes that batch fail; "
    "later batches and the caller continuation still run. An existing caller "
    "transaction, its earlier writes, and its right to roll back remain intact. "
    "Observe each batch's success, rows and transaction state, then the "
    "continuation and caller rollback. No implementation source is supplied.")
TRANSFER_CONTRACT = ("Each account transfer is all-or-nothing on real SQLite "
    "balances: debit then credit, with no negative balance. Missing source, "
    "missing destination or insufficient funds makes only that transfer fail. "
    "Later transfers and a caller continuation still run. An existing caller "
    "transaction, its earlier writes, and its right to roll back remain intact. "
    "Observe each transfer's success, balances and transaction state, then "
    "the continuation and caller rollback. No implementation source is supplied.")

# The ordering and task identities are fixed before any probes. Correct and
# incorrect clients are retained, without filtering on public-example success.
_BINDINGS = {
    "batch-a7": ("batch", "partial"),
    "batch-k4": ("batch", "savepoint"),
    "batch-r9": ("batch", "whole_rollback"),
    "batch-u2": ("batch", "commit_success"),
    "batch-z5": ("batch", "swallow"),
    "transfer-b8": ("transfer", "whole_rollback"),
    "transfer-f3": ("transfer", "partial"),
    "transfer-m6": ("transfer", "savepoint"),
    "transfer-q1": ("transfer", "swallow"),
    "transfer-v4": ("transfer", "commit_success"),
}


def task_ids(family: str | None = None) -> tuple[str, ...]:
    if family not in (None, "batch", "transfer"):
        raise ValueError("unknown client family")
    return tuple(task for task, (kind, _) in _BINDINGS.items()
                 if family is None or kind == family)


def _integer(value: Any, low: int, high: int) -> bool:
    return type(value) is int and low <= value <= high


def validate_query(family: str, query: dict) -> None:
    """Check the public finite query grammar before either native execution."""
    if type(query) is not dict or set(query) != {"outer", "initial", "steps", "continuation"}:
        raise ValueError("query requires outer, initial, steps and continuation")
    if type(query["outer"]) is not bool or type(query["initial"]) is not list:
        raise ValueError("outer must be Boolean and initial must be a list")
    steps = query["steps"]
    if type(steps) is not list or not 1 <= len(steps) <= 3:
        raise ValueError("one to three operation steps required")
    if family == "batch":
        initial = query["initial"]
        if len(initial) > 4 or any(not _integer(x, 1, 9) for x in initial) or len(set(initial)) != len(initial):
            raise ValueError("initial batch keys must be unique integers 1..9")
        if any(type(step) is not list or not 1 <= len(step) <= 4 or
               any(not _integer(x, 1, 10) for x in step) for step in steps):
            raise ValueError("each batch must contain one to four integer keys 1..10")
        if not _integer(query["continuation"], 1, 10):
            raise ValueError("batch continuation must be an integer key 1..10")
    elif family == "transfer":
        initial = query["initial"]
        if not 2 <= len(initial) <= 4 or any(
                type(row) is not list or len(row) != 2 or
                not _integer(row[0], 1, 9) or not _integer(row[1], 0, 9)
                for row in initial):
            raise ValueError("initial accounts require 2..4 [id, balance] pairs")
        if len({row[0] for row in initial}) != len(initial):
            raise ValueError("initial account identifiers must be unique")
        if any(type(step) is not list or len(step) != 3 or
               not _integer(step[0], 1, 10) or not _integer(step[1], 1, 10) or
               not _integer(step[2], 1, 9) for step in steps):
            raise ValueError("transfer steps require [source, destination, amount]")
        tail = query["continuation"]
        if type(tail) is not list or len(tail) != 2 or not _integer(tail[0], 1, 10) or not _integer(tail[1], 1, 3):
            raise ValueError("transfer continuation requires [account, positive credit]")
    else:
        raise ValueError("unknown client family")


def _state(conn: sqlite3.Connection, family: str) -> list:
    if family == "batch":
        return [row[0] for row in conn.execute("SELECT k FROM items ORDER BY k")]
    return [[row[0], row[1]] for row in conn.execute("SELECT id, balance FROM accounts ORDER BY id")]


def _work(conn: sqlite3.Connection, family: str, step: list) -> None:
    if family == "batch":
        for key in step:
            conn.execute("INSERT INTO items(k) VALUES(?)", (key,))
    else:
        source, destination, amount = step
        debit = conn.execute(
            "UPDATE accounts SET balance=balance-? WHERE id=? AND balance>=?",
            (amount, source, amount))
        if debit.rowcount != 1:
            raise StepFailure("source missing or insufficient funds")
        credit = conn.execute("UPDATE accounts SET balance=balance+? WHERE id=?",
                              (amount, destination))
        if credit.rowcount != 1:
            raise StepFailure("destination missing")


def _attempt(conn: sqlite3.Connection, family: str, step: list, mode: str) -> bool:
    if mode in ("savepoint", "commit_success"):
        conn.execute("SAVEPOINT client_step")
        try:
            _work(conn, family, step)
        except (sqlite3.IntegrityError, StepFailure):
            conn.execute("ROLLBACK TO client_step")
            success = False
        else:
            success = True
        conn.execute("RELEASE client_step")
        if success and mode == "commit_success":
            conn.commit()  # Violates ownership when the caller opened a transaction.
        return success
    if mode == "whole_rollback":
        owns = not conn.in_transaction
        if owns:
            conn.execute("BEGIN")
        try:
            _work(conn, family, step)
        except (sqlite3.IntegrityError, StepFailure):
            conn.rollback()  # Incorrectly erases caller-owned earlier writes.
            return False
        if owns:
            conn.commit()
        return True
    if mode in ("partial", "swallow"):
        try:
            _work(conn, family, step)
        except (sqlite3.IntegrityError, StepFailure):
            return mode == "swallow"  # May also leave partial writes.
        return True
    raise ValueError("unknown internal client implementation")


def _execute(family: str, mode: str, query: dict) -> tuple[dict, int]:
    validate_query(family, query)
    conn = sqlite3.connect(":memory:", isolation_level=None)
    sql_count = 0

    def count(_statement: str) -> None:
        nonlocal sql_count
        sql_count += 1

    conn.set_trace_callback(count)
    try:
        if family == "batch":
            conn.execute("CREATE TABLE items(k INTEGER PRIMARY KEY CHECK(k BETWEEN 1 AND 9))")
        else:
            conn.execute("CREATE TABLE accounts(id INTEGER PRIMARY KEY, "
                         "balance INTEGER NOT NULL CHECK(balance >= 0))")
        if query["outer"]:
            conn.execute("BEGIN")
        for row in query["initial"]:
            if family == "batch":
                conn.execute("INSERT INTO items(k) VALUES(?)", (row,))
            else:
                conn.execute("INSERT INTO accounts(id,balance) VALUES(?,?)", row)
        outcomes = []
        for step in query["steps"]:
            ok = _attempt(conn, family, step, mode)
            outcomes.append({"ok": ok, "state": _state(conn, family),
                             "transaction_open": conn.in_transaction})
        try:
            if family == "batch":
                conn.execute("INSERT INTO items(k) VALUES(?)", (query["continuation"],))
            else:
                tail_id, amount = query["continuation"]
                changed = conn.execute("UPDATE accounts SET balance=balance+? WHERE id=?",
                                       (amount, tail_id))
                if changed.rowcount != 1:
                    raise StepFailure("caller continuation account missing")
        except (sqlite3.IntegrityError, StepFailure):
            tail_ok = False
        else:
            tail_ok = True
        before = _state(conn, family)
        open_before = conn.in_transaction
        if query["outer"]:
            conn.rollback()
        after = _state(conn, family)
        return ({"steps": outcomes, "continuation_ok": tail_ok,
                 "state_before_caller_rollback": before,
                 "transaction_open_before_caller_rollback": open_before,
                 "state_after_caller_rollback": after}, sql_count)
    finally:
        conn.close()


@dataclass
class Meter:
    reference_calls: int = 0
    client_calls: int = 0
    reference_sql: int = 0
    client_sql: int = 0


def _binding(task_id: str) -> tuple[str, str]:
    try:
        return _BINDINGS[task_id]
    except KeyError as exc:
        raise ValueError("unknown client task") from exc


class ProbeOracle:
    """Source-bound, charged native contrast; instantiate anew per study arm."""

    def __init__(self, task_id: str):
        family, mode = _binding(task_id)
        self.task_id, self.family, self._mode = task_id, family, mode
        self.meter = Meter()
        source = Path(__file__).read_bytes()
        self.source_sha256 = hashlib.sha256(source + mode.encode()).hexdigest()

    def ask(self, query: dict) -> dict:
        validate_query(self.family, query)
        expected, reference_sql = _execute(self.family, "savepoint", query)
        observed, client_sql = _execute(self.family, self._mode, query)
        self.meter.reference_calls += 1
        self.meter.client_calls += 1
        self.meter.reference_sql += reference_sql
        self.meter.client_sql += client_sql
        frozen = deepcopy(query)
        identity = hashlib.sha256(json.dumps(frozen, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        return {"task_id": self.task_id, "source_sha256": self.source_sha256,
                "sqlite_version": sqlite3.sqlite_version, "query": frozen,
                "query_sha256": identity, "reference": expected, "client": observed,
                "discrepancy": expected != observed,
                "cost": {"reference_calls": 1, "client_calls": 1,
                         "reference_sql": reference_sql, "client_sql": client_sql}}


def _public_example(family: str) -> dict:
    if family == "batch":
        return {"outer": False, "initial": [1], "steps": [[2]], "continuation": 3}
    return {"outer": False, "initial": [[1, 5], [2, 2]],
            "steps": [[1, 2, 1]], "continuation": [2, 1]}


def model_visible_receipt(full_receipt: dict) -> dict:
    """Project host evidence without implementation or SQL-cost fingerprints."""
    return {key: deepcopy(full_receipt[key]) for key in
            ("query", "reference", "client", "discrepancy")}


def _query_shape(family: str) -> dict:
    common = {"outer": "Boolean: true opens a caller-owned transaction before initial state; "
                        "the caller rolls it back after the continuation.",
              "steps": "1..3 ordered operations; every step is attempted, including after a failure."}
    if family == "batch":
        return {**common,
                "initial": "List of 0..4 DISTINCT integer keys in 1..9.",
                "steps_item": "List of 1..4 integer keys in 1..10; duplicates and key 10 are legal inputs and can fail natively.",
                "continuation": "One integer key in 1..10, inserted by the caller after every step."}
    return {**common,
            "initial": "List of 2..4 [id,balance] pairs: DISTINCT integer ids 1..9 and integer balances 0..9.",
            "steps_item": "[source_id,destination_id,amount]: integer ids 1..10 and integer amount 1..9. Missing ids and insufficient funds are legal cases.",
            "continuation": "[account_id,positive_credit]: integer id 1..10 and integer credit 1..3, applied by the caller after every step."}


def public_family_spec(family: str) -> dict:
    """Static prospective contract; no task binding, example, or native call."""
    if family not in ("batch", "transfer"):
        raise ValueError("unknown client family")
    return {"family": family,
            "contract": IMPORT_CONTRACT if family == "batch" else TRANSFER_CONTRACT,
            "query_shape": _query_shape(family), "probe_limit": 6}


def prepare_task(task_id: str) -> dict:
    """Acquire one example once; host retains audit cost, model gets only public.

    A real study must call this in the host process and account for the returned
    example receipt. Do not pass ``audit`` or this module to the investigator.
    """
    family, _ = _binding(task_id)
    full_example = ProbeOracle(task_id).ask(_public_example(family))
    visible = model_visible_receipt(full_example)
    public = {"id": task_id, **public_family_spec(family), "example": visible}
    return {"public": public, "audit": {"example_receipt": full_example}}


def public_task(task_id: str) -> dict:
    """Convenience public projection; host should use prepare_task for cost."""
    return prepare_task(task_id)["public"]


def heldout_queries(family: str) -> tuple[dict, ...]:
    """Private evaluation patterns; keep this owner outside the agent process."""
    if family == "batch":
        steps = ([4, 5], [4, 4], [10], [5, 6, 5], [7, 8])
        initial_states = ([4], [5, 7])
        return tuple({"outer": outer, "initial": list(initial),
                      "steps": [list(first), list(second)], "continuation": tail}
                     for outer in (False, True) for initial in initial_states
                     for first in steps for second in ([8], [9, 9])
                     for tail in (6, 9))
    if family == "transfer":
        steps = ([4, 5, 2], [4, 6, 2], [4, 5, 8], [6, 5, 1], [5, 4, 1])
        initial_states = ([[4, 5], [5, 1]], [[4, 3], [5, 4], [6, 0]])
        return tuple({"outer": outer, "initial": deepcopy(initial),
                      "steps": [list(first), list(second)], "continuation": [tail, 1]}
                     for outer in (False, True) for initial in initial_states
                     for first in steps for second in ([5, 4, 1], [4, 5, 1])
                     for tail in (4, 6))
    raise ValueError("unknown client family")


def score(task_id: str) -> dict:
    """Run only after freeze; this returns hidden labels and is not an agent tool."""
    family, _ = _binding(task_id)
    oracle = ProbeOracle(task_id)
    cases = heldout_queries(family)
    wrong = []
    for index, query in enumerate(cases):
        if oracle.ask(query)["discrepancy"]:
            wrong.append(index)
    return {"task_id": task_id, "correct": len(cases) - len(wrong),
            "total": len(cases), "failing_indices": wrong,
            "validation_cost": vars(oracle.meter).copy()}
