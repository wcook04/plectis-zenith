#!/usr/bin/env python3
"""Exploratory split: which exposures in a study were only timeouts.

Usage: python scripts/kept_experience_timeout_split.py STUDY_DIR HUMANEVALPLUS_JSONL FAULTS_JSON ARM [ARM ...]
Writes STUDY_DIR/scores_no_timeout_<arm>.json (per-problem share exposed by a
wrong value or exception, excluding faults whose exposing difference was a
timeout) and prints both means. The study's results builder reads these files.
"""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from research.kept_experience import population as P, natural as N, sandbox as S
STUDY, DATASET, FAULTS = (Path(a) for a in sys.argv[1:4])
probs = {p["task_id"]: p for p in P.load_problems(DATASET)}
faults = json.load(open(FAULTS))

def job(j):
    N._guard()
    p = probs[j["task_id"]]; e = p["entry_point"]
    val = P._load(P.validator_source(p), e)
    valid = [a for a in j["inputs"] if P.valid_input(val, a)]
    out = {}
    for fid, i in j["killed"].items():
        if not isinstance(i, int):
            out[fid] = "timeout"; continue
        f = [x for x in faults[j["task_id"]] if x["fault_id"] == fid][0]
        got = P.call(P._load(f["source"], e), valid[i])
        out[fid] = "timeout" if got == ("timeout",) else ("exception" if got[0] == "exc" else "wrong value")
    return out

for arm in sys.argv[4:]:
    rows = json.load(open(STUDY / f"scores/{arm}__heldout__natural.json"))["rows"]
    res = S.run_jobs(job, rows)
    per_task = {}
    for r, x in zip(rows, res):
        kinds = x["value"] if x["ok"] else {k: "timeout" for k in r["killed"]}
        nt = sum(1 for v in kinds.values() if v != "timeout")
        per_task.setdefault(r["task_id"], []).append((len(r["killed"]) / r["n_faults"], nt / r["n_faults"]))
    full = sum(sum(a for a, _ in v) / len(v) for v in per_task.values()) / len(per_task)
    notime = sum(sum(b for _, b in v) / len(v) for v in per_task.values()) / len(per_task)
    json.dump({t: sum(b for _, b in v) / len(v) for t, v in per_task.items()}, open(STUDY / f"scores_no_timeout_{arm}.json", "w"))
    print(arm, "all exposures", round(full, 4), "excluding timeout exposures", round(notime, 4))
