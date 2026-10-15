"""Exact, bounded single-output continuation learner with retained witnesses.

This is the maintained single-source adaptation of the witness-basis correction
in Zenith progress return 02 (Apache-2.0). The older learner in the immutable
continuation-memory source archive rebuilds its access basis after adding a
question and can thereby lose the history that made the question informative.
Here every refinement adds *both* the access history and continuation whose
measured residual is nonzero. It learns only within the rational-linear class;
passing finite challenges is not a universal correctness certificate.

Teachers are inspected, local callables. This module is not an executor for
untrusted generated code and does not use model providers or network access.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction
from typing import Callable, Sequence

Word = tuple[int, ...]
Vector = tuple[Fraction, ...]
Matrix = tuple[Vector, ...]


@dataclass
class Meter:
    source_calls: int = 0
    input_symbols: int = 0
    cache_hits: int = 0
    challenge_words: int = 0
    multiply_adds: int = 0


@dataclass
class Teacher:
    source: Callable[[Word], int]
    alphabet: tuple[int, ...]
    source_id: str
    max_length: int = 32
    meter: Meter = field(default_factory=Meter)
    cache: dict[Word, Fraction] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.source_id or not self.alphabet or len(set(self.alphabet)) != len(self.alphabet):
            raise ValueError("source identity and unique nonempty alphabet required")
        if any(type(x) is not int for x in self.alphabet) or self.max_length < 1:
            raise ValueError("integer alphabet and positive maximum length required")

    def ask(self, word: Word) -> Fraction:
        if len(word) > self.max_length or any(type(x) is not int or x not in self.alphabet for x in word):
            raise ValueError("query outside source binding")
        if word in self.cache:
            self.meter.cache_hits += 1
            return self.cache[word]
        value = self.source(word)
        if type(value) is not int:
            raise ValueError("source must return an exact integer")
        answer = Fraction(value)
        self.cache[word] = answer
        self.meter.source_calls += 1
        self.meter.input_symbols += len(word)
        return answer

    def row(self, prefix: Word, tests: Sequence[Word]) -> Vector:
        return tuple(self.ask(prefix + suffix) for suffix in tests)


def _dot(a: Sequence[Fraction], b: Sequence[Fraction], meter: Meter | None = None) -> Fraction:
    if len(a) != len(b):
        raise ValueError("dimension mismatch")
    total = Fraction(0)
    for x, y in zip(a, b):
        if x and y:
            total += x * y
            if meter is not None:
                meter.multiply_adds += 1
    return total


def _multiply(a: Matrix, b: Matrix, meter: Meter | None = None) -> Matrix:
    if not a or not b or len(a[0]) != len(b):
        raise ValueError("invalid matrix dimensions")
    columns = tuple(zip(*b))
    return tuple(tuple(_dot(row, col, meter) for col in columns) for row in a)


def _row_times(row: Vector, matrix: Matrix, meter: Meter | None = None) -> Vector:
    return _multiply((row,), matrix, meter)[0]


def _inverse(matrix: Matrix) -> Matrix:
    n = len(matrix)
    if not n or any(len(row) != n for row in matrix):
        raise ValueError("nonempty square matrix required")
    rows = [[*row, *(Fraction(int(i == j)) for j in range(n))] for i, row in enumerate(matrix)]
    for col in range(n):
        pivot = next((i for i in range(col, n) if rows[i][col]), None)
        if pivot is None:
            raise ValueError("singular witness matrix")
        rows[col], rows[pivot] = rows[pivot], rows[col]
        scale = rows[col][col]
        rows[col] = [x / scale for x in rows[col]]
        for i in range(n):
            if i != col and rows[i][col]:
                scale = rows[i][col]
                rows[i] = [x - scale * y for x, y in zip(rows[i], rows[col])]
    return tuple(tuple(row[n:]) for row in rows)


class _RowBasis:
    def __init__(self, width: int) -> None:
        self.width = width
        self.rows: dict[int, Vector] = {}

    def add(self, values: Vector) -> bool:
        if len(values) != self.width:
            raise ValueError("basis width mismatch")
        row = list(values)
        for pivot in sorted(self.rows):
            scale = row[pivot]
            if scale:
                row = [x - scale * y for x, y in zip(row, self.rows[pivot])]
        pivot = next((i for i, value in enumerate(row) if value), None)
        if pivot is None:
            return False
        scale = row[pivot]
        self.rows[pivot] = tuple(x / scale for x in row)
        return True

    @property
    def pivots(self) -> tuple[int, ...]:
        return tuple(sorted(self.rows))


@dataclass(frozen=True)
class Model:
    source_id: str
    alphabet: tuple[int, ...]
    max_length: int
    initial: Vector
    transitions: dict[int, Matrix]
    readout: Vector
    access: tuple[Word, ...]
    tests: tuple[Word, ...]

    @property
    def dimension(self) -> int:
        return len(self.initial)

    def predict(self, word: Word, meter: Meter | None = None) -> Fraction:
        if len(word) > self.max_length:
            raise ValueError("word exceeds binding")
        state = self.initial
        for symbol in word:
            if type(symbol) is not int or symbol not in self.transitions:
                raise ValueError("symbol outside binding")
            state = _row_times(state, self.transitions[symbol], meter)
        return _dot(state, self.readout, meter)


@dataclass(frozen=True)
class Refinement:
    history: Word
    continuation: Word
    residual: Fraction
    counterexample: Word


@dataclass(frozen=True)
class Fit:
    model: Model
    refinements: tuple[Refinement, ...]
    status: str = "passed_finite_development_challenges"


def _new_plan_cost(teacher: Teacher, access: list[Word], tests: list[Word]) -> tuple[int, int]:
    prefixes = set(access) | {p + (a,) for p in access for a in teacher.alphabet} | {()}
    words = {p + q for p in prefixes for q in tests} | set(access)
    missing = words - teacher.cache.keys()
    return len(missing), sum(map(len, missing))


def learn(
    teacher: Teacher,
    challenges: Sequence[Word],
    *,
    bank: Sequence[Word] = (),
    cost_gate: bool = False,
    max_dimension: int = 40,
    max_rounds: int = 20,
) -> Fit:
    """Fit one rational-linear source and preserve every nonzero rank witness.

    A bank is optional. The cost gate accepts an alternative only if its next
    fit needs fewer uncached source calls *and* its measured residual is nonzero.
    This one-step estimate is not a total-cost guarantee. Supplying generic
    singleton continuations gives an ordinary, experience-free bank control.
    """
    if max_dimension < 1 or max_rounds < 1:
        raise ValueError("positive caps required")
    if any(len(w) > teacher.max_length or any(type(x) is not int or x not in teacher.alphabet for x in w)
           for w in challenges):
        raise ValueError("challenge outside source binding")
    if any(len(q) > teacher.max_length or any(type(x) is not int or x not in teacher.alphabet for x in q)
           for q in bank):
        raise ValueError("bank outside source binding")
    bank = tuple(sorted(set(bank), key=lambda q: (len(q), q)))
    tests = [(), (teacher.alphabet[0],)]
    # A delayed nonzero series can vanish on both short tests. If a supplied
    # challenge exposes it, its suffixes provide a nonzero observation of the
    # empty history and let the initial access basis reach that behavior.
    if not any(teacher.ask(question) for question in tests):
        seed = next((word for word in sorted(set(challenges), key=lambda w: (len(w), w))
                     if teacher.ask(word)), None)
        if seed is not None:
            tests = list(dict.fromkeys((*tests, *(seed[i:] for i in range(len(seed))))))
    basis = _RowBasis(len(tests))
    access: list[Word] = []
    queue: list[Word] = [()]
    cursor = 0
    while cursor < len(queue):
        prefix = queue[cursor]
        cursor += 1
        if basis.add(teacher.row(prefix, tests)):
            access.append(prefix)
            queue.extend(prefix + (a,) for a in teacher.alphabet)
    if not access:
        raise RuntimeError("zero observed series")
    tests = [tests[i] for i in basis.pivots]
    refinements: list[Refinement] = []
    for _ in range(max_rounds):
        if len(access) > max_dimension:
            raise RuntimeError("dimension cap exhausted")
        h = tuple(teacher.row(prefix, tests) for prefix in access)
        inv = _inverse(h)  # the retained witness matrix must stay full rank
        transitions = {
            a: _multiply(inv, tuple(teacher.row(p + (a,), tests) for p in access), teacher.meter)
            for a in teacher.alphabet
        }
        outputs = tuple((teacher.ask(p),) for p in access)
        readout = tuple(row[0] for row in _multiply(inv, outputs, teacher.meter))
        model = Model(
            teacher.source_id, teacher.alphabet, teacher.max_length,
            teacher.row((), tests), transitions, readout, tuple(access), tuple(tests),
        )
        failure = None
        for word in challenges:
            teacher.meter.challenge_words += 1
            predicted, actual = model.predict(word, teacher.meter), teacher.ask(word)
            if predicted != actual:
                failure = word
                break
        if failure is None:
            return Fit(model, tuple(refinements))
        current = model.initial
        for i, symbol in enumerate(failure):
            current = _row_times(current, transitions[symbol], teacher.meter)
            observed = teacher.row(failure[: i + 1], tests)
            if current == observed:
                continue
            k = next(j for j, (x, y) in enumerate(zip(current, observed)) if x != y)
            prefix = failure[:i]
            generic = (symbol,) + tests[k]
            if prefix in access or generic in tests:
                raise RuntimeError("non-new refinement witness")
            coefficients = _row_times(teacher.row(prefix, tests), inv)
            chosen = generic
            if cost_gate:
                generic_cost = _new_plan_cost(teacher, access + [prefix], tests + [generic])
                candidates = []
                for question in bank:
                    if question == generic or question in tests:
                        continue
                    if max(map(len, access + [prefix])) + 1 + len(question) > teacher.max_length:
                        continue
                    cost = _new_plan_cost(teacher, access + [prefix], tests + [question])
                    if cost[0] < generic_cost[0]:
                        candidates.append((cost, question))
                for _, question in sorted(candidates)[:1]:
                    residual = teacher.ask(prefix + question) - _dot(
                        coefficients, tuple(teacher.ask(p + question) for p in access)
                    )
                    if residual:
                        chosen = question
            residual = teacher.ask(prefix + chosen) - _dot(
                coefficients, tuple(teacher.ask(p + chosen) for p in access)
            )
            if not residual:
                raise RuntimeError("refinement did not increase rank")
            refinements.append(Refinement(prefix, chosen, residual, failure))
            access.append(prefix)
            tests.append(chosen)
            break
        else:
            raise RuntimeError("readout mismatch without transition witness")
    raise RuntimeError("refinement cap exhausted")
