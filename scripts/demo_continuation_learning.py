"""Run the maintained continuation learner against inspected native fixtures.

The eight-task workload and seeds are adapted from Zenith progress return 02
(Apache-2.0). This is an authored, deterministic diagnostic, not a sample of
independent applications. No provider, credential, or network access is used.

    python -B scripts/demo_continuation_learning.py
    python -B scripts/demo_continuation_learning.py --native
"""

from __future__ import annotations

import argparse
import codecs
from collections import deque
from functools import lru_cache
import itertools
import json
from pathlib import Path
import random
import sqlite3
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from research.continuation_learning import Teacher, learn  # noqa: E402

ALPHABET = tuple(range(-8, 9))
TASKS = ("deque-1", "deque-2", "deque-4", "lru-1", "lru-2", "utf8", "sqlite-rowid", "sqlite-auto")
BYTE_VALUES = (0, 65, 127, 128, 143, 159, 160, 191, 192, 193, 194, 223, 224, 237, 239, 240, 244)


def native_source(name):
    if name.startswith("deque-"):
        capacity = int(name.rsplit("-", 1)[1])
        return lambda word: sum(deque(word, maxlen=capacity))
    if name.startswith("lru-"):
        capacity = int(name.rsplit("-", 1)[1])

        def source(word):
            @lru_cache(maxsize=capacity)
            def identity(value):
                return value

            for value in word:
                identity(value % 3)
            return identity.cache_info().misses

        return source
    if name == "utf8":
        def source(word):
            decoder = codecs.getincrementaldecoder("utf-8")("strict")
            try:
                decoder.decode(bytes(BYTE_VALUES[value + 8] for value in word), final=False)
            except UnicodeDecodeError:
                return 0
            return 1 if decoder.getstate()[0] else 2

        return source
    if name in ("sqlite-rowid", "sqlite-auto"):
        def source(word):
            table = "CREATE TABLE t(id INTEGER PRIMARY KEY"
            table += " AUTOINCREMENT" if name == "sqlite-auto" else ""
            connection = sqlite3.connect(":memory:", isolation_level=None)
            try:
                connection.execute(table + ")")
                for value in word:
                    if value == -8:
                        if not connection.in_transaction:
                            connection.execute("BEGIN")
                    elif value == -7:
                        if connection.in_transaction:
                            connection.execute("COMMIT")
                    elif value == -6:
                        if connection.in_transaction:
                            connection.execute("ROLLBACK")
                    elif value == -5:
                        connection.execute("DELETE FROM t WHERE id=(SELECT MAX(id) FROM t)")
                    elif value == -4:
                        connection.execute("DELETE FROM t")
                    else:
                        connection.execute("INSERT OR REPLACE INTO t(id) VALUES(?)", (value % 3 + 1,))
                return connection.execute("INSERT INTO t DEFAULT VALUES").lastrowid
            finally:
                connection.close()

        return source
    raise ValueError("unknown native task")


def panels():
    development = [word for n in range(3) for word in itertools.product(ALPHABET, repeat=n)]
    randomizer = random.Random(1410202602)
    development += [tuple(randomizer.choice(ALPHABET) for _ in range(randomizer.randint(3, 12)))
                    for _ in range(192)]
    randomizer = random.Random(1410202699)
    longer = [tuple(randomizer.choice(ALPHABET) for _ in range(randomizer.randint(16, 32)))
              for _ in range(192)]
    short = list(itertools.product(ALPHABET, repeat=3))
    return development, longer, short


def minimal_witness():
    source = lambda word: sum(deque(word, maxlen=4))
    teacher = Teacher(source, (1,), "deque-maxlen-4")
    fit = learn(teacher, [(1,) * n for n in range(9)])
    checks = [(1,) * n for n in range(33)]
    assert all(fit.model.predict(word) == source(word) for word in checks)
    return {
        "task": "deque-maxlen-4-unary",
        "source_calls": teacher.meter.source_calls,
        "dimension_in_rational_linear_class": fit.model.dimension,
        "refinements": [
            {"history": list(r.history), "continuation": list(r.continuation),
             "residual": str(r.residual)} for r in fit.refinements
        ],
        "later_lengths_correct": len(checks),
        "ordinary_nonlinear_control": "one counter: min(count + 1, 4)",
        "boundary": fit.status,
    }


def native_panel():
    development, longer, short = panels()
    development_set = set(development)
    rows = []
    for name in TASKS:
        source = native_source(name)
        for condition in ("ordinary_witness", "generic_singletons"):
            teacher = Teacher(source, ALPHABET, name)
            fit = learn(
                teacher, development,
                bank=tuple((symbol,) for symbol in ALPHABET),
                cost_gate=condition == "generic_singletons",
            )
            row = {
                "task": name,
                "condition": condition,
                "status": fit.status,
                "dimension": fit.model.dimension,
                "acquisition_source_calls": teacher.meter.source_calls,
                "acquisition_input_symbols": teacher.meter.input_symbols,
                "refinements": len(fit.refinements),
            }
            for panel_name, panel in (("longer", longer), ("short", short)):
                correct = sum(fit.model.predict(word) == source(word) for word in panel)
                row[panel_name] = {"correct": correct, "total": len(panel)}
            rows.append(row)
    return {
        "source": "authored native wrappers and seeded panels adapted from progress return 02",
        "python": sys.version.split()[0],
        "sqlite": sqlite3.sqlite_version,
        "development_words": len(development),
        "longer_words": len(longer),
        "short_words": len(short),
        "short_not_in_development": sum(word not in development_set for word in short),
        "rows": rows,
        "boundary": "finite panels; one design, eight configurations, no independent confirmation",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--native", action="store_true", help="run all eight native configurations and panels")
    args = parser.parse_args()
    result = {"minimal_witness": minimal_witness()}
    if args.native:
        result["native_panel"] = native_panel()
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
