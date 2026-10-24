"""Kept-experience study: does retained testing experience help on new programs?

A tester sees only a function's public specification and may run K inputs.
Each input is executed on the reference solution and on every hidden faulty
solution of that problem; any observable difference exposes that fault. The
model never sees the hidden faults of the problem it is testing, nor their
outputs. Scoring is execution only.

Phases (each writes into one study directory):
  calls    model calls for an arm and split; raw replies cached by key
  score    zero-network execution of the cached replies
The protocol (splits, arms, prompts, model, budget) is frozen in
``protocol.json`` before any held-out call.
"""

from __future__ import annotations

import ast
import concurrent.futures as cf
import contextlib
import hashlib
import io
import json
import multiprocessing as mp
import os
import random
import re
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from research.kept_experience import natural as N
from research.kept_experience import population as P
from research.kept_experience import sandbox as S

MODEL = "deepseek/deepseek-v4.1-flash-1017"
PROVIDERS = ["morph/fp8"]
BUDGET_K = 5

# ------------------------------------------------------------------ prompts

SYSTEM = (
    "You are an expert software tester. You will be shown the public "
    "specification of a Python function: its signature, docstring and examples. "
    "Somebody has written an implementation that may contain a subtle bug. It "
    "already passes the docstring examples and the project's original test "
    "suite, so obvious cases will not expose it. You may run exactly {k} inputs. "
    "Each input is run on that implementation and on a correct reference; any "
    "difference in return value or raised exception exposes the bug. You will "
    "not see the implementation or the outputs. Choose the {k} inputs most "
    "likely to expose whatever mistake a programmer could plausibly have made.\n\n"
    "Every input must satisfy the stated preconditions; invalid inputs are "
    "discarded and still use up the budget.\n\n"
    "Finish your reply with exactly one fenced python block assigning "
    "INPUTS, a list of exactly {k} tuples of positional arguments, using only "
    "Python literals. A one-argument call is written as a one-element tuple, "
    "for example (\"abc\",).")

ADVICE = """General testing advice:
- Probe boundaries: empty inputs, a single element, zero, one, negative numbers, the smallest and largest legal values.
- Probe equality and ties: duplicates, equal adjacent values, values exactly at a threshold.
- Probe ordering: already sorted, reverse sorted, the interesting item first or last.
- Probe types the contract allows: floats as well as integers, upper and lower case, spaces and punctuation in strings.
- Probe size: longer inputs where a loop bound or index could be off by one.
- Combine conditions: inputs where two rules interact rather than one rule in isolation.
- Prefer inputs whose correct answer you can predict exactly from the specification."""

IMAGINE_SYSTEM = (
    "You are an expert software tester. You will be shown the public "
    "specification of a Python function. Somebody has written an "
    "implementation that may contain a subtle bug. It already passes the "
    "docstring examples and the project's original tests. You will choose "
    "{k} inputs; each is run on that implementation and a correct reference, "
    "and any difference exposes the bug.\n\n"
    "Work in three steps. First write your own correct implementation, named "
    "REFERENCE. Then imagine eight different plausible buggy implementations a "
    "competent programmer might write that would still pass the docstring "
    "examples; name them BUG_1 to BUG_8 and make each a complete function with "
    "the same signature. Then propose twenty candidate inputs that satisfy the "
    "preconditions. A program will run every candidate on REFERENCE and every "
    "BUG_i and choose the {k} candidates that expose the most different bugs.\n\n"
    "Finish with exactly one fenced python block that defines REFERENCE, "
    "BUG_1 ... BUG_8 and CANDIDATES, a list of twenty tuples of positional "
    "arguments written as Python literals. Imports must be inside functions.")


def spec_text(problem: dict) -> str:
    contract = "\n".join(line.split("#")[0].rstrip() for line in problem["contract"].splitlines()
                         if line.strip())
    return (f"Specification:\n```python\n{problem['prompt'].rstrip()}\n```\n\n"
            f"Preconditions on the arguments (checked before running):\n```python\n{contract}\n```")


def _strip_docstrings(source: str) -> str:
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Module)):
            body = node.body
            if body and isinstance(body[0], ast.Expr) and isinstance(getattr(body[0], "value", None), ast.Constant) \
                    and isinstance(body[0].value.value, str):
                node.body = body[1:] or [ast.Pass()]
    return ast.unparse(tree)


def experience_text(records: list[dict]) -> str:
    """Render practice records: what was tried, what was missed and what exposed it."""
    parts = ["Experience from earlier testing sessions on other functions. For each, you see "
             "the inputs that were tried, then each hidden bug that those inputs MISSED, with "
             "the buggy code and an input that exposes it.\n"]
    for r in records:
        parts.append(f"### {r['task_id']}: {r['summary']}")
        parts.append(f"Inputs tried: {r['tried']}")
        parts.append(f"Bugs exposed: {r['exposed']} of {r['total']}")
        for miss in r["missed"]:
            parts.append("Missed bug:\n```python\n" + miss["code"] + "\n```")
            parts.append(f"Exposing input: {miss['witness']}  reference -> {miss['expected']}  bug -> {miss['got']}")
        parts.append("")
    return "\n".join(parts)


NO_REASONING_SUFFIX = "_nr"


def base_arm(arm: str) -> str:
    """Experiment 2 arms reuse an experiment 1 prompt with reasoning switched off."""
    return arm[:-len(NO_REASONING_SUFFIX)] if arm.endswith(NO_REASONING_SUFFIX) else arm


def build_messages(arm: str, problem: dict, context: dict) -> list[dict]:
    arm = base_arm(arm)
    k = context.get("k", BUDGET_K)
    user = spec_text(problem)
    if arm in ("imagine", "imagine_kept"):
        system = IMAGINE_SYSTEM.format(k=k)
    else:
        system = SYSTEM.format(k=k)
    prefix = ""
    if arm == "advice":
        prefix = ADVICE + "\n\n"
    elif arm in ("kept", "imagine_kept"):
        prefix = context["experience"] + "\n\n"
    elif arm.startswith("lessons"):
        prefix = "Testing lessons distilled from earlier sessions:\n" + context["lessons"][arm] + "\n\n"
    return [{"role": "system", "content": system},
            {"role": "user", "content": prefix + user}]


LESSONS_PROMPT = (
    "Below is a log of testing sessions. In each, a tester saw only a function's "
    "specification and chose a few inputs; hidden buggy implementations that had "
    "already passed the original tests were then revealed, with the inputs that "
    "expose them. Study which bugs were missed and why the chosen inputs failed "
    "to reach them. Write a playbook of at most 400 words that will help a tester "
    "choose a handful of inputs for a NEW, different function, given only its "
    "specification. Generalise: do not mention the specific functions. Give "
    "concrete, checkable tactics, most valuable first. Output only the playbook.")

LESSONS_REVISE_PROMPT = (
    "Below is a testing playbook, followed by a log of new sessions in which a "
    "tester followed that playbook on unseen functions and still missed some bugs. "
    "Revise the playbook so that a tester following it would have caught more of "
    "the missed bugs, without losing what already works. At most 400 words, "
    "general tactics only, most valuable first. Output only the revised playbook.")


# ------------------------------------------------------------------ provider

class Ledger:
    def __init__(self, path: Path, cap_usd: float):
        self.path, self.cap, self.lock = path, cap_usd, threading.Lock()
        self.spent = 0.0
        if path.exists():
            for line in path.read_text().splitlines():
                self.spent += json.loads(line).get("cost", 0.0)

    def add(self, row: dict) -> None:
        with self.lock:
            self.spent += row.get("cost", 0.0)
            with self.path.open("a") as fh:
                fh.write(json.dumps(row) + "\n")

    def check(self) -> None:
        if self.spent >= self.cap:
            raise RuntimeError(f"study budget exhausted: ${self.spent:.4f} >= ${self.cap}")


def _api_key() -> str:
    key = os.environ.get("OPENROUTER_API_KEY")
    if key:
        return key
    env = Path(os.environ.get("ZENITH_ENV_FILE", Path.home() / "src/ai_workflow/.env"))
    for line in env.read_text().splitlines():
        if line.startswith("OPENROUTER_API_KEY="):
            return line.split("=", 1)[1].strip().strip('"')
    raise RuntimeError("OPENROUTER_API_KEY not available")


def chat(messages: list[dict], *, effort: str, max_tokens: int, ledger: Ledger,
         tag: str, attempts: int = 4) -> dict:
    ledger.check()
    reasoning = {"enabled": False} if effort == "off" else {"effort": effort}
    body = {"model": MODEL, "messages": messages, "max_tokens": max_tokens,
            "reasoning": reasoning, "usage": {"include": True},
            "provider": {"order": PROVIDERS, "allow_fallbacks": False}}
    data = json.dumps(body).encode()
    last = None
    for attempt in range(attempts):
        req = urllib.request.Request("https://openrouter.ai/api/v1/chat/completions", data=data,
                                     headers={"Authorization": f"Bearer {_api_key()}",
                                              "Content-Type": "application/json"})
        t0 = time.time()
        try:
            with urllib.request.urlopen(req, timeout=600) as resp:
                reply = json.loads(resp.read())
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            last = repr(exc)
            ledger.add({"tag": tag, "attempt": attempt, "error": last, "cost": 0.0})
            time.sleep(3 * (attempt + 1))
            continue
        usage = reply.get("usage") or {}
        cost = float(usage.get("cost") or 0.0)
        if "choices" not in reply:
            last = json.dumps(reply)[:500]
            ledger.add({"tag": tag, "attempt": attempt, "error": last, "cost": cost})
            time.sleep(3 * (attempt + 1))
            continue
        msg = reply["choices"][0]["message"]
        row = {"tag": tag, "attempt": attempt, "cost": cost, "provider": reply.get("provider"),
               "prompt_tokens": usage.get("prompt_tokens"),
               "completion_tokens": usage.get("completion_tokens"),
               "reasoning_tokens": (usage.get("completion_tokens_details") or {}).get("reasoning_tokens"),
               "finish_reason": reply["choices"][0].get("finish_reason"),
               "seconds": round(time.time() - t0, 2)}
        ledger.add(row)
        return {"content": msg.get("content") or "", "reasoning": msg.get("reasoning") or "",
                "meta": row}
    raise RuntimeError(f"provider failed for {tag}: {last}")


# ------------------------------------------------------------------ parsing

_BLOCK = re.compile(r"```(?:python|py)?\s*\n(.*?)```", re.S)


def last_block(text: str) -> str | None:
    blocks = _BLOCK.findall(text or "")
    return blocks[-1] if blocks else None


def parse_inputs(text: str, k: int) -> list[list]:
    block = last_block(text)
    if block is None:
        return []
    try:
        tree = ast.parse(block)
    except SyntaxError:
        return []
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(getattr(t, "id", None) == "INPUTS" for t in node.targets):
            try:
                value = ast.literal_eval(node.value)
            except Exception:  # noqa: BLE001
                return []
            out = []
            for item in list(value)[:k]:
                out.append(list(item) if isinstance(item, (tuple, list)) else [item])
            return out
    return []


DELIVERY_ATTEMPTS = 3


def delivered(arm: str, content: str) -> bool:
    """A reply is delivered when its final python block carries the requested name.

    An empty answer field (all output left in the reasoning channel) or a reply
    without the block is a delivery failure; the same request is sent again, up
    to DELIVERY_ATTEMPTS, identically for every arm. Undelivered attempts and
    their costs stay in the record.
    """
    block = last_block(content)
    if block is None:
        return False
    return ("CANDIDATES" in block) if arm.startswith("imagine") else ("INPUTS" in block)


# ------------------------------------------------------------------ execution

def _outcome_text(outcome: tuple) -> str:
    if outcome[0] == "ok":
        return repr(outcome[1])[:200]
    return f"<{' '.join(map(str, outcome))}>"


def _evaluate(job: dict) -> dict:
    """Execute chosen inputs on reference and hidden faults (forked worker)."""
    N._guard()
    sys.setrecursionlimit(10_000)
    problem, faults, inputs = job["problem"], job["faults"], job["inputs"]
    entry, atol = problem["entry_point"], problem.get("atol") or 0
    sink = io.StringIO()
    with contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
        validator = P._load(P.validator_source(problem), entry)
        ref = P._load(P.reference_source(problem), entry)
        valid = [a for a in inputs if P.valid_input(validator, a)]
        ref_out = [P.call(ref, a, timeout=2.0) for a in valid]
        killed = {}
        for f in faults:
            try:
                fn = P._load(f["source"], entry)
            except BaseException:  # noqa: BLE001
                continue
            for i, a in enumerate(valid):
                if ref_out[i] == ("timeout",):
                    continue
                if P.outcomes_differ(ref_out[i], P.call(fn, a), atol):
                    killed[f["fault_id"]] = i
                    break
    return {"task_id": problem["task_id"], "n_inputs": len(inputs), "n_valid": len(valid),
            "killed": killed, "n_faults": len(faults)}


ISOLATED_WALL_S = 20.0
SCORING_JOB_WALL_S = 120.0


def _reference_outcome(job: dict):
    """One input on the reference, in its own child (isolated fallback)."""
    N._guard()
    sys.setrecursionlimit(10_000)
    problem, args = job["problem"], job["args"]
    sink = io.StringIO()
    with contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
        validator = P._load(P.validator_source(problem), problem["entry_point"])
        if not P.valid_input(validator, args):
            return None
        return P.call(P._load(P.reference_source(problem), problem["entry_point"]), args, timeout=2.0)


def _fault_against(job: dict):
    """One fault on the reference-completed inputs, in its own child (isolated fallback)."""
    N._guard()
    sys.setrecursionlimit(10_000)
    problem, fault = job["problem"], job["fault"]
    sink = io.StringIO()
    with contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
        fn = P._load(fault["source"], problem["entry_point"])
        for i, (args, ref) in enumerate(job["cases"]):
            if P.outcomes_differ(ref, P.call(fn, args), problem.get("atol") or 0):
                return i
    return None


def evaluate_isolated(job: dict) -> dict:
    """Fallback when a whole evaluation job stalls inside uninterruptible native code.

    Each input runs on the reference in its own child; an input the reference
    cannot finish within ISOLATED_WALL_S is dropped (as a reference timeout is in
    the normal path). Each fault then runs in its own child; a fault whose child
    fails to finish, or dies, on inputs where the reference finished counts as
    exposed, matching the per-call rule that a timeout differs from a returned value.
    """
    problem, inputs = job["problem"], job["inputs"]
    refs = S.run_jobs(_reference_outcome, [{"problem": problem, "args": a} for a in inputs],
                      wall_s=ISOLATED_WALL_S)
    valid = [a for a, r in zip(inputs, refs) if r["ok"] and r["value"] is not None]
    cases = [(a, r["value"]) for a, r in zip(inputs, refs)
             if r["ok"] and r["value"] is not None and r["value"] != ("timeout",)]
    killed = {}
    results = S.run_jobs(_fault_against, [{"problem": problem, "fault": f, "cases": cases}
                                          for f in job["faults"]], wall_s=ISOLATED_WALL_S)
    for fault, r in zip(job["faults"], results):
        if not r["ok"]:
            if cases:
                killed[fault["fault_id"]] = "isolated:" + r["error"][:40]
        elif r["value"] is not None:
            killed[fault["fault_id"]] = r["value"]
    return {"task_id": problem["task_id"], "n_inputs": len(inputs), "n_valid": len(valid),
            "killed": killed, "n_faults": len(job["faults"]), "isolated": True}


def _imagine_select(job: dict) -> dict:
    """Choose K candidates by greedy cover of the model's own imagined bugs.

    Uses only model-written code and the public precondition checker; the true
    reference and the hidden faults are not consulted.
    """
    N._guard()
    sys.setrecursionlimit(10_000)
    problem, text, k = job["problem"], job["text"], job["k"]
    entry = problem["entry_point"]
    block = last_block(text) or ""
    info: dict[str, Any] = {"parsed": False}
    sink = io.StringIO()
    with contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
        try:
            ns: dict[str, Any] = {"__name__": "__imagined__"}
            prelude = problem["prompt"].split("def " + entry)[0]
            exec(compile(prelude + "\n" + block, "<imagined>", "exec"), ns)
            cands = [list(c) if isinstance(c, (tuple, list)) else [c] for c in ns["CANDIDATES"]]
            ref = ns["REFERENCE"]
            bugs = [ns[f"BUG_{i}"] for i in range(1, 9) if callable(ns.get(f"BUG_{i}"))]
        except BaseException as exc:  # noqa: BLE001
            info["error"] = type(exc).__name__
            return {"task_id": problem["task_id"], "inputs": [], "info": info}
        validator = P._load(P.validator_source(problem), entry)
        cands = [c for c in cands if P.valid_input(validator, c)]
        cover = []
        for c in cands:
            r = P.call(ref, c)
            cover.append({j for j, b in enumerate(bugs) if r != ("timeout",) and P.outcomes_differ(r, P.call(b, c), 1e-6)})
    chosen, covered = [], set()
    remaining = list(range(len(cands)))
    while remaining and len(chosen) < k:
        best = max(remaining, key=lambda i: (len(cover[i] - covered), -i))
        if not cover[best] - covered:
            break
        chosen.append(best)
        covered |= cover[best]
        remaining.remove(best)
    for i in remaining:  # fill unused slots in the model's own order
        if len(chosen) >= k:
            break
        chosen.append(i)
    info.update(parsed=True, n_candidates=len(cands), n_bugs=len(bugs), imagined_covered=len(covered))
    return {"task_id": problem["task_id"], "inputs": [cands[i] for i in sorted(chosen)], "info": info}


def pool_map(fn, jobs: list[dict], processes: int = S.DEFAULT_PROCESSES) -> list[dict]:
    """Bounded execution; a failed child yields {"error": ...} in place of its value."""
    return [r["value"] if r["ok"] else {"error": r["error"]} for r in S.run_jobs(fn, jobs, processes)]


# ------------------------------------------------------------------ study

class Study:
    def __init__(self, root: Path):
        self.root = root
        self.protocol = json.loads((root / "protocol.json").read_text())
        self.problems = {p["task_id"]: p for p in P.load_problems(Path(self.protocol["dataset_path"]))}
        self.faults = json.loads(Path(self.protocol["faults_path"]).read_text())
        self.ledger = Ledger(root / "ledger.jsonl", self.protocol["budget_usd"])
        (root / "replies").mkdir(exist_ok=True)

    def split(self, name: str) -> list[str]:
        return self.protocol["splits"][name]

    def faults_for(self, task_id: str, population: str) -> list[dict]:
        return [f for f in self.faults.get(task_id, []) if f["kind"] == population]

    def reply_path(self, arm: str, task_id: str, rep: int) -> Path:
        return self.root / "replies" / arm / f"{task_id.replace('/', '_')}__r{rep}.json"

    def context(self) -> dict:
        ctx: dict[str, Any] = {"k": self.protocol["k"], "lessons": {}}
        exp = self.root / "experience.md"
        if exp.exists():
            ctx["experience"] = exp.read_text()
        for f in sorted(self.root.glob("lessons_*.md")):
            ctx["lessons"][f.stem] = f.read_text()
        return ctx

    def call_arm(self, arm: str, split: str, reps: int, workers: int = 8) -> None:
        ctx = self.context()
        effort = "off" if arm.endswith(NO_REASONING_SUFFIX) else self.protocol["effort"]
        max_tokens = self.protocol["max_tokens"]["imagine" if arm.startswith("imagine") else "test"]
        todo = []
        for task_id in self.split(split):
            for rep in range(reps):
                path = self.reply_path(arm, task_id, rep)
                if not path.exists():
                    todo.append((task_id, rep, path))

        def one(item):
            task_id, rep, path = item
            messages = build_messages(arm, self.problems[task_id], ctx)
            failed = []
            for attempt in range(DELIVERY_ATTEMPTS):
                reply = chat(messages, effort=effort, max_tokens=max_tokens, ledger=self.ledger,
                             tag=f"{arm}|{task_id}|r{rep}|d{attempt}")
                if delivered(arm, reply["content"]):
                    break
                failed.append({"content": reply["content"], "reasoning_chars": len(reply["reasoning"]),
                               "meta": reply["meta"]})
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({"arm": arm, "task_id": task_id, "rep": rep,
                                        "messages_sha256": hashlib.sha256(json.dumps(messages).encode()).hexdigest(),
                                        "undelivered_attempts": failed, **reply}, indent=1))
            return task_id

        with cf.ThreadPoolExecutor(workers) as ex:
            for fut in cf.as_completed([ex.submit(one, t) for t in todo]):
                fut.result()
        print(f"{arm}/{split}: {len(todo)} calls, ledger ${self.ledger.spent:.4f}", flush=True)

    def chosen_inputs(self, arm: str, split: str, reps: int) -> dict[tuple, list]:
        k = self.protocol["k"]
        out = {}
        if arm.startswith("imagine"):
            jobs = []
            for task_id in self.split(split):
                for rep in range(reps):
                    text = json.loads(self.reply_path(arm, task_id, rep).read_text())["content"]
                    jobs.append({"problem": self.problems[task_id], "text": text, "k": k, "rep": rep})
            for job, res in zip(jobs, pool_map(_imagine_select, jobs)):
                out[(job["problem"]["task_id"], job["rep"])] = res.get("inputs", [])
            return out
        for task_id in self.split(split):
            for rep in range(reps):
                text = json.loads(self.reply_path(arm, task_id, rep).read_text())["content"]
                out[(task_id, rep)] = parse_inputs(text, k)
        return out

    def score_arm(self, arm: str, split: str, reps: int, population: str) -> dict:
        chosen = self.chosen_inputs(arm, split, reps)
        jobs = [{"problem": self.problems[t], "faults": self.faults_for(t, population),
                 "inputs": inputs, "rep": rep} for (t, rep), inputs in chosen.items()]
        jobs = [j for j in jobs if j["faults"]]
        rows = [r["value"] if r["ok"] else {"error": r["error"]}
                for r in S.run_jobs(_evaluate, jobs, wall_s=SCORING_JOB_WALL_S)]
        for idx, (j, r) in enumerate(zip(jobs, rows)):
            if "error" in r:
                rows[idx] = r = evaluate_isolated(j)
            r["rep"] = j["rep"]
            r["inputs"] = j["inputs"]
        return {"arm": arm, "split": split, "population": population, "rows": rows}

    def score_random(self, split: str, population: str, draws: int = 200, seed: int = 0) -> dict:
        """Expected kill rate of K inputs drawn uniformly from EvalPlus's augmented set."""
        k = self.protocol["k"]
        rows = []
        for t in self.split(split):
            faults = self.faults_for(t, population)
            if not faults:
                continue
            nplus = len(self.problems[t]["plus_input"])
            rng = random.Random(f"{seed}|{t}")
            total = 0.0
            for _ in range(draws):
                pick = set(rng.sample(range(nplus), min(k, nplus)))
                total += sum(1 for f in faults
                             if pick & {i for i in f["failing_plus"] if isinstance(i, int)})
            rows.append({"task_id": t, "n_faults": len(faults), "expected_killed": total / draws})
        return {"arm": "random_plus", "split": split, "population": population, "rows": rows}


def summarise(result: dict) -> dict:
    by_task: dict[str, list[float]] = {}
    for r in result["rows"]:
        killed = r.get("expected_killed", len(r.get("killed", {})))
        by_task.setdefault(r["task_id"], []).append(killed / r["n_faults"])
    per_task = {t: sum(v) / len(v) for t, v in by_task.items()}
    mean = sum(per_task.values()) / max(1, len(per_task))
    return {"arm": result["arm"], "population": result["population"], "problems": len(per_task),
            "mean_fraction_exposed": round(mean, 4), "per_task": per_task}
