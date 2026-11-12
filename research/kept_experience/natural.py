"""Natural faults: model-written HumanEval solutions that pass the original tests.

EvalPlus released sampled solutions from several code models. A sample is a
*natural subtle fault* when it matches the reference on every original
HumanEval input but differs on at least one EvalPlus input. Samples are
deduplicated by source, then grouped by behaviour: two faulty solutions with the
same set of failing augmented inputs count as one fault class.
"""

from __future__ import annotations

import ast
import builtins
import contextlib
import hashlib
import io
import json
import time
import os
import sys
import tempfile
from pathlib import Path

from research.kept_experience import population as P
from research.kept_experience import sandbox as S

MAX_TIMEOUTS = 3


def _guard() -> None:
    """Best-effort guard for executing third-party sampled code in a forked worker."""
    import shutil
    import subprocess
    if getattr(os, "unlink", None) is None:
        return
    os.chdir(tempfile.mkdtemp(prefix="zenith-kept-"))
    for name in ("system", "kill", "remove", "unlink", "rmdir", "removedirs", "rename",
                 "renames", "truncate", "putenv", "fork", "forkpty", "killpg", "chmod",
                 "chown", "setuid", "execv", "execve", "spawnv"):
        if hasattr(os, name):
            setattr(os, name, None)
    shutil.rmtree = None  # type: ignore[assignment]
    shutil.move = None  # type: ignore[assignment]
    subprocess.Popen = None  # type: ignore[assignment,misc]
    builtins.exit = None  # type: ignore[assignment]
    builtins.quit = None  # type: ignore[assignment]


def normalise(source: str) -> str | None:
    try:
        return ast.unparse(ast.parse(source))
    except Exception:  # noqa: BLE001
        return None


def collect(sample_root: Path, problems: list[dict]) -> dict[str, list[dict]]:
    """Unique parseable samples per task, with their source models."""
    by_task: dict[str, dict[str, dict]] = {p["task_id"]: {} for p in problems}
    for model_dir in sorted(sample_root.iterdir()):
        if not model_dir.is_dir():
            continue
        model = model_dir.name
        for task_dir in sorted(model_dir.iterdir()):
            task_id = task_dir.name.replace("_", "/")
            if task_id not in by_task:
                continue
            for f in sorted(task_dir.glob("*.py")):
                text = normalise(f.read_text(errors="replace"))
                if text is None:
                    continue
                row = by_task[task_id].setdefault(text, {"source": text, "models": []})
                if model not in row["models"]:
                    row["models"].append(model)
    return {t: list(rows.values()) for t, rows in by_task.items()}


def _profile(job: tuple) -> dict:
    problem, candidates, kind = job
    _guard()
    sys.setrecursionlimit(10_000)
    entry, atol = problem["entry_point"], problem.get("atol") or 0
    ref = P._load(P.reference_source(problem), entry)
    base, plus = [], []
    for name, bucket in (("base_input", base), ("plus_input", plus)):
        for args in problem[name]:
            outcome = P.call(ref, args, timeout=2.0)
            if outcome[0] != "timeout":
                bucket.append((args, outcome))
    rows = []
    sink = io.StringIO()
    for cand in candidates:
        with contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
            try:
                fn = P._load(cand["source"], entry)
            except BaseException:  # noqa: BLE001
                continue
            if any(P.outcomes_differ(o, P.call(fn, a), atol) for a, o in base):
                continue
            failing, timeouts = [], 0
            for i, (a, o) in enumerate(plus):
                got = P.call(fn, a)
                if got == ("timeout",):
                    timeouts += 1
                if P.outcomes_differ(o, got, atol):
                    failing.append(i)
                if timeouts >= MAX_TIMEOUTS:
                    failing.append("timeout-stop")
                    break
        sink.seek(0)
        sink.truncate()
        if failing:
            sig = hashlib.sha256(json.dumps(failing).encode()).hexdigest()[:16]
            rows.append({"source": cand["source"], "kind": kind,
                         "models": cand.get("models", []),
                         "operator": cand.get("operator"),
                         "failing_plus": failing, "n_failing_plus": len(failing),
                         "signature": sig})
    return {"task_id": problem["task_id"], "plus_inputs": len(plus), "faults": rows}


BATCH = 40


def build(dataset: Path, sample_root: Path, out: Path, processes: int = S.DEFAULT_PROCESSES) -> dict:
    problems = P.load_problems(dataset)
    natural = collect(sample_root, problems)
    jobs = []
    for p in problems:
        for kind, cands in (("natural", natural[p["task_id"]]), ("mutant", P.mutants(p))):
            for i in range(0, len(cands), BATCH):
                jobs.append((p, cands[i:i + BATCH], kind))
    out.mkdir(parents=True, exist_ok=True)
    log = (out / "progress.log").open("w")

    def progress(done: int, total: int) -> None:
        if done % 50 == 0 or done == total:
            log.write(f"{time.strftime('%H:%M:%S')} {done}/{total}\n")
            log.flush()

    raw = S.run_jobs(_profile, jobs, processes, progress=progress)
    results, lost = [], []
    for job, r in zip(jobs, raw):
        if r["ok"]:
            results.append(r["value"])
        else:
            lost.append({"task_id": job[0]["task_id"], "kind": job[2],
                         "candidates": len(job[1]), "error": r["error"]})
    faults: dict[str, list[dict]] = {}
    for r in results:
        bucket = faults.setdefault(r["task_id"], [])
        seen = {(f["kind"], f["signature"]) for f in bucket}
        for f in r["faults"]:
            key = (f["kind"], f["signature"])
            if key in seen:
                # keep provenance of every model that produced this behaviour
                for g in bucket:
                    if (g["kind"], g["signature"]) == key:
                        g["models"] = sorted(set(g["models"]) | set(f["models"]))
                        g["duplicates"] = g.get("duplicates", 1) + 1
                continue
            seen.add(key)
            bucket.append({**f, "fault_id": f"{r['task_id']}#{f['kind'][0]}{len(bucket)}"})
    (out / "faults.json").write_text(json.dumps(faults, indent=1))
    summary = {
        "dataset_sha256": hashlib.sha256(dataset.read_bytes()).hexdigest(),
        "sample_models": sorted(d.name for d in sample_root.iterdir() if d.is_dir()),
        "unique_natural_samples": sum(len(v) for v in natural.values()),
        "natural_fault_classes": sum(1 for v in faults.values() for f in v if f["kind"] == "natural"),
        "mutant_fault_classes": sum(1 for v in faults.values() for f in v if f["kind"] == "mutant"),
        "problems_with_natural": sum(1 for v in faults.values() if any(f["kind"] == "natural" for f in v)),
        "problems_with_mutant": sum(1 for v in faults.values() if any(f["kind"] == "mutant" for f in v)),
        "lost_batches": lost,
    }
    (out / "faults_summary.json").write_text(json.dumps(summary, indent=2))
    return summary


if __name__ == "__main__":
    print(json.dumps(build(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])), indent=2))
