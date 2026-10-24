"""Process-per-job runner with memory and time bounds for generated code.

Mutants, sampled model solutions and model-imagined programs can allocate
without limit. A SIGALRM time limit does not stop that, and macOS ignores
RLIMIT_AS, so each job runs in its own forked child with:

* a watchdog thread on peak resident memory: a soft limit raises MemoryError
  in the main thread (the current call fails as data), a hard limit exits the
  child immediately;
* a wall-clock limit enforced by the parent;
* lowered priority.

A child that dies becomes an error row; it never hangs the run.
"""

from __future__ import annotations

import multiprocessing as mp
import os
import pickle
import resource
import signal
import sys
import threading
import time
from typing import Any, Callable

SOFT_RSS = 1_200_000_000
HARD_RSS = 2_500_000_000
DEFAULT_PROCESSES = 6
JOB_WALL_S = 900.0

# Bound before any job runs: guarded children disable os.kill and friends.
_KILL, _EXIT, _GETPID = os.kill, os._exit, os.getpid


def _peak_rss() -> int:
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return peak if sys.platform == "darwin" else peak * 1024


def _memory_error(_signum, _frame):
    raise MemoryError("zenith sandbox soft memory limit")


def _watch(soft: int, hard: int) -> None:
    # Limits are growth above the child's starting peak: a forked child can
    # begin with the parent's resident pages already counted.
    base = _peak_rss()
    soft, hard = base + soft, base + hard
    fired = False
    while True:
        peak = _peak_rss()
        if peak > hard:
            _EXIT(87)
        if peak > soft and not fired:
            fired = True
            _KILL(_GETPID(), signal.SIGUSR1)
        time.sleep(0.02)


def _child(fn: Callable, job: Any, conn, soft: int, hard: int) -> None:
    try:
        os.nice(10)
    except OSError:
        pass
    signal.signal(signal.SIGUSR1, _memory_error)
    threading.Thread(target=_watch, args=(soft, hard), daemon=True).start()
    try:
        result = {"ok": True, "value": fn(job)}
    except BaseException as exc:  # noqa: BLE001 - reported to parent as data
        result = {"ok": False, "error": f"{type(exc).__name__}: {exc}"[:300]}
    try:
        conn.send_bytes(pickle.dumps(result))
    finally:
        conn.close()
        _EXIT(0)


def run_jobs(fn: Callable, jobs: list, processes: int = DEFAULT_PROCESSES,
             wall_s: float = JOB_WALL_S, progress: Callable[[int, int], None] | None = None) -> list[dict]:
    """Run fn(job) for each job; return [{"ok", "value"|"error"}] in job order."""
    ctx = mp.get_context("fork")
    results: list[dict | None] = [None] * len(jobs)
    pending = list(range(len(jobs)))
    running: dict[int, tuple] = {}
    done = 0
    while pending or running:
        while pending and len(running) < processes:
            i = pending.pop(0)
            recv, send = ctx.Pipe(duplex=False)
            proc = ctx.Process(target=_child, args=(fn, jobs[i], send, SOFT_RSS, HARD_RSS), daemon=True)
            proc.start()
            send.close()
            running[i] = (proc, recv, time.time(), bytearray())
        for i, (proc, recv, start, _buf) in list(running.items()):
            finished = None
            if recv.poll(0):
                try:
                    finished = pickle.loads(recv.recv_bytes())
                except (EOFError, OSError):
                    finished = {"ok": False, "error": f"child exited {proc.exitcode}"}
            elif not proc.is_alive():
                finished = {"ok": False, "error": f"child exited {proc.exitcode}"
                            + (" (hard memory limit)" if proc.exitcode == 87 else "")}
            elif time.time() - start > wall_s:
                proc.kill()
                finished = {"ok": False, "error": "wall-clock limit"}
            if finished is not None:
                proc.join(timeout=5)
                if proc.is_alive():
                    proc.kill()
                recv.close()
                results[i] = finished
                del running[i]
                done += 1
                if progress:
                    progress(done, len(jobs))
        time.sleep(0.01)
    return [r if r is not None else {"ok": False, "error": "lost"} for r in results]
