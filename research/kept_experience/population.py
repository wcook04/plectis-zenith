"""Subtle-fault population for the kept-experience study.

Each HumanEval+ problem supplies a specification (signature, docstring and
examples), a reference solution, the original HumanEval test inputs ("base")
and EvalPlus's augmented inputs ("plus"). We apply single-site mechanical
mutation operators to the reference function and execute every mutant against
both input sets. A mutant is *subtle* when the original human-written tests
cannot tell it from the reference but at least one augmented input can.

Neither the study author nor a model chooses these faults: the operators are
standard (arithmetic, relational, logical, constant and condition changes) and
the filter is a fixed execution rule.
"""

from __future__ import annotations

import ast
import copy
import hashlib
import json
import math
import signal
import sys
from pathlib import Path
from typing import Any

CALL_TIMEOUT_S = 1.0
MAX_MUTANTS_PER_PROBLEM = 400

_SWAP_BIN = {ast.Add: ast.Sub, ast.Sub: ast.Add, ast.Mult: ast.FloorDiv,
             ast.FloorDiv: ast.Mult, ast.Div: ast.Mult, ast.Mod: ast.FloorDiv,
             ast.Pow: ast.Mult}
_SWAP_CMP = {ast.Lt: ast.LtE, ast.LtE: ast.Lt, ast.Gt: ast.GtE, ast.GtE: ast.Gt,
             ast.Eq: ast.NotEq, ast.NotEq: ast.Eq, ast.In: ast.NotIn,
             ast.NotIn: ast.In, ast.Is: ast.IsNot, ast.IsNot: ast.Is}
_SWAP_BOOL = {ast.And: ast.Or, ast.Or: ast.And}


def load_problems(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _entry(tree: ast.Module, name: str) -> ast.FunctionDef:
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise ValueError(f"entry point {name} not found")


def _sites(fn: ast.FunctionDef) -> list[tuple[ast.AST, str]]:
    body = fn.body
    if body and isinstance(body[0], ast.Expr) and isinstance(getattr(body[0], "value", None), ast.Constant) \
            and isinstance(body[0].value.value, str):
        body = body[1:]
    sites: list[tuple[ast.AST, str]] = []
    for stmt in body:
        for node in ast.walk(stmt):
            if isinstance(node, ast.BinOp) and type(node.op) in _SWAP_BIN:
                sites.append((node, "binop"))
            elif isinstance(node, ast.AugAssign) and type(node.op) in _SWAP_BIN:
                sites.append((node, "augassign"))
            elif isinstance(node, ast.Compare):
                for i, op in enumerate(node.ops):
                    if type(op) in _SWAP_CMP:
                        sites.append((node, f"compare:{i}"))
            elif isinstance(node, ast.BoolOp) and type(node.op) in _SWAP_BOOL:
                sites.append((node, "boolop"))
            elif isinstance(node, ast.Constant) and type(node.value) is int:
                sites.append((node, "int+1"))
                sites.append((node, "int-1"))
            elif isinstance(node, ast.Constant) and type(node.value) is bool:
                sites.append((node, "bool"))
            elif isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
                sites.append((node, "drop_not"))
            elif isinstance(node, (ast.If, ast.While)):
                sites.append((node, "negate_test"))
            elif isinstance(node, ast.Break):
                sites.append((node, "break_continue"))
            elif isinstance(node, ast.Continue):
                sites.append((node, "continue_break"))
    return sites


class _Apply(ast.NodeTransformer):
    def __init__(self, target_index: int, kind: str):
        self.target_index, self.kind, self.seen = target_index, kind, -1

    def _hit(self, node: ast.AST) -> bool:
        return getattr(node, "_site", None) == self.target_index

    def generic_visit(self, node):  # type: ignore[override]
        node = super().generic_visit(node)
        if not self._hit(node):
            return node
        k = self.kind
        if k in ("binop", "augassign"):
            node.op = _SWAP_BIN[type(node.op)]()
        elif k.startswith("compare:"):
            i = int(k.split(":")[1])
            node.ops[i] = _SWAP_CMP[type(node.ops[i])]()
        elif k == "boolop":
            node.op = _SWAP_BOOL[type(node.op)]()
        elif k == "int+1":
            return ast.copy_location(ast.Constant(node.value + 1), node)
        elif k == "int-1":
            return ast.copy_location(ast.Constant(node.value - 1), node)
        elif k == "bool":
            return ast.copy_location(ast.Constant(not node.value), node)
        elif k == "drop_not":
            return node.operand
        elif k == "negate_test":
            node.test = ast.UnaryOp(ast.Not(), node.test)
        elif k == "break_continue":
            return ast.copy_location(ast.Continue(), node)
        elif k == "continue_break":
            return ast.copy_location(ast.Break(), node)
        return node


def mutants(problem: dict) -> list[dict]:
    """Every distinct single-site mutant of the reference entry function."""
    source = problem["prompt"] + problem["canonical_solution"]
    base_tree = ast.parse(source)
    reference = ast.unparse(base_tree)
    fn = _entry(base_tree, problem["entry_point"])
    sites = _sites(fn)
    out, seen = [], {reference}
    for index, (_, kind) in enumerate(sites):
        tree = ast.parse(source)
        fn2 = _entry(tree, problem["entry_point"])
        sites2 = _sites(fn2)
        sites2[index][0]._site = index  # type: ignore[attr-defined]
        tree = _Apply(index, kind).visit(tree)
        ast.fix_missing_locations(tree)
        try:
            text = ast.unparse(tree)
            compile(text, "<mutant>", "exec")
        except Exception:
            continue
        if text in seen:
            continue
        seen.add(text)
        line = getattr(sites[index][0], "lineno", None)
        out.append({"mutant_id": f"{problem['task_id']}#m{len(out)}",
                    "operator": kind.split(":")[0], "line": line,
                    "source": text,
                    "sha256": hashlib.sha256(text.encode()).hexdigest()})
        if len(out) >= MAX_MUTANTS_PER_PROBLEM:
            break
    return out


def reference_source(problem: dict) -> str:
    return ast.unparse(ast.parse(problem["prompt"] + problem["canonical_solution"]))


def validator_source(problem: dict) -> str:
    return problem["prompt"] + problem["contract"] + "    return True\n"


# ---------------------------------------------------------------- execution

class _Timeout(Exception):
    pass


def _alarm(_signum, _frame):
    raise _Timeout()


def _load(source: str, entry: str):
    namespace: dict[str, Any] = {"__name__": "__zenith_subject__"}
    exec(compile(source, "<subject>", "exec"), namespace)
    return namespace[entry]


def call(fn, args: list, timeout: float = CALL_TIMEOUT_S):
    """Return a comparable outcome: ("ok", value) | ("exc", type) | ("timeout",)."""
    signal.signal(signal.SIGALRM, _alarm)
    signal.setitimer(signal.ITIMER_REAL, timeout)
    try:
        value = fn(*copy.deepcopy(args))
        return ("ok", value)
    except _Timeout:
        return ("timeout",)
    except RecursionError:
        return ("exc", "RecursionError")
    except Exception as exc:  # noqa: BLE001 - outcomes are data here
        return ("exc", type(exc).__name__)
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)


def same(a: Any, b: Any, atol: float) -> bool:
    if isinstance(a, float) or isinstance(b, float):
        if isinstance(a, (int, float)) and isinstance(b, (int, float)) and not isinstance(a, bool) and not isinstance(b, bool):
            if math.isnan(a) and math.isnan(b):
                return True
            return math.isclose(a, b, rel_tol=0.0, abs_tol=atol or 1e-6)
        return False
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        return type(a) is type(b) and len(a) == len(b) and all(same(x, y, atol) for x, y in zip(a, b))
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(same(a[k], b[k], atol) for k in a)
    try:
        return bool(a == b) and type(a) is type(b)
    except Exception:  # noqa: BLE001
        return False


def outcomes_differ(ref: tuple, got: tuple, atol: float) -> bool:
    if ref[0] != got[0]:
        return True
    if ref[0] == "ok":
        return not same(ref[1], got[1], atol)
    return ref != got


def valid_input(validator, args: list) -> bool:
    outcome = call(validator, args, timeout=CALL_TIMEOUT_S)
    return outcome == ("ok", True)


def _classify(job: tuple) -> dict:
    problem, muts = job
    sys.setrecursionlimit(10_000)
    entry, atol = problem["entry_point"], problem.get("atol") or 0
    ref = _load(reference_source(problem), entry)
    base, plus = [], []
    for name, bucket in (("base_input", base), ("plus_input", plus)):
        for args in problem[name]:
            outcome = call(ref, args, timeout=2.0)
            if outcome[0] != "timeout":
                bucket.append((args, outcome))
    rows = []
    for m in muts:
        try:
            fn = _load(m["source"], entry)
        except Exception:  # noqa: BLE001
            continue
        killed_base = any(outcomes_differ(o, call(fn, a), atol) for a, o in base)
        plus_kill = None
        if not killed_base:
            for i, (a, o) in enumerate(plus):
                if outcomes_differ(o, call(fn, a), atol):
                    plus_kill = i
                    break
        rows.append({**{k: m[k] for k in ("mutant_id", "operator", "line", "sha256")},
                     "killed_by_base": killed_base,
                     "plus_witness_index": plus_kill})
    return {"task_id": problem["task_id"], "base_inputs": len(base),
            "plus_inputs": len(plus), "mutants": rows}


def build(dataset: Path, out: Path, processes: int = 8) -> dict:
    problems = load_problems(dataset)
    jobs = [(p, mutants(p)) for p in problems]
    sources = {m["mutant_id"]: m["source"] for _, ms in jobs for m in ms}
    from research.kept_experience import sandbox as S
    results = [r["value"] for r in S.run_jobs(_classify, jobs, min(processes, S.DEFAULT_PROCESSES)) if r["ok"]]
    subtle = [{**row, "source": sources[row["mutant_id"]]}
              for r in results for row in r["mutants"]
              if not row["killed_by_base"] and row["plus_witness_index"] is not None]
    summary = {
        "dataset_sha256": hashlib.sha256(dataset.read_bytes()).hexdigest(),
        "problems": len(problems),
        "mutants": sum(len(r["mutants"]) for r in results),
        "killed_by_base": sum(row["killed_by_base"] for r in results for row in r["mutants"]),
        "subtle": len(subtle),
        "problems_with_subtle": len({m["mutant_id"].split("#")[0] for m in subtle}),
    }
    out.mkdir(parents=True, exist_ok=True)
    (out / "classification.json").write_text(json.dumps(results, indent=1))
    (out / "subtle_mutants.json").write_text(json.dumps(subtle, indent=1))
    (out / "population_summary.json").write_text(json.dumps(summary, indent=2))
    return summary


if __name__ == "__main__":
    print(json.dumps(build(Path(sys.argv[1]), Path(sys.argv[2])), indent=2))
