"""Command line for the kept-experience study. See docs/studies/kept-experience/."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

from research.kept_experience import harness as H
from research.kept_experience import natural as N
from research.kept_experience import population as P

SPLIT_SALT = "zenith-kept-experience-2026-10-19"
MAX_MISSES_SHOWN = 3


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def init(root: Path, dataset: Path, faults: Path, budget: float, effort: str, k: int) -> dict:
    data = json.loads(faults.read_text())
    eligible = sorted(t for t, v in data.items() if any(f["kind"] == "natural" for f in v))
    order = sorted(eligible, key=lambda t: hashlib.sha256(f"{SPLIT_SALT}|{t}".encode()).hexdigest())
    n = len(order)
    a, b = n // 4, n // 2
    protocol = {
        "study": "zenith_kept_experience_v1",
        "question": "Does testing experience kept from earlier programs help a fixed model expose "
                    "hidden faults in new programs, under the same input budget?",
        "model": H.MODEL, "providers": H.PROVIDERS, "effort": effort, "k": k,
        "max_tokens": {"test": 32000, "imagine": 48000},
        "budget_usd": budget,
        "dataset_path": str(dataset), "dataset_sha256": _sha(dataset),
        "faults_path": str(faults), "faults_sha256": _sha(faults),
        "split_rule": f"sha256('{SPLIT_SALT}|'+task_id) order over problems with >=1 natural fault; "
                      "first quarter practice, second quarter development, second half held-out",
        "splits": {"practice": sorted(order[:a]), "dev": sorted(order[a:b]), "heldout": sorted(order[b:])},
        "prompts_sha256": {name: hashlib.sha256(getattr(H, name).encode()).hexdigest()
                           for name in ("SYSTEM", "ADVICE", "IMAGINE_SYSTEM", "LESSONS_PROMPT",
                                        "LESSONS_REVISE_PROMPT")},
        "primary_population": "natural",
        "primary_metric": "mean over held-out problems of the fraction of natural fault classes "
                          "exposed by the K chosen inputs, averaged over replicates",
    }
    root.mkdir(parents=True, exist_ok=True)
    (root / "protocol.json").write_text(json.dumps(protocol, indent=2))
    return {k2: (len(v) if k2 == "splits" else v) for k2, v in protocol.items() if k2 in ("splits",)} | \
        {"sizes": {s: len(v) for s, v in protocol["splits"].items()}}


def _witness_job(job: dict) -> dict:
    """Shortest exposing augmented input for each missed fault, with both outcomes."""
    N._guard()
    problem, faults = job["problem"], job["faults"]
    entry = problem["entry_point"]
    ref = P._load(P.reference_source(problem), entry)
    out = []
    for f in faults:
        idxs = [i for i in f["failing_plus"] if isinstance(i, int)]
        if not idxs:
            continue
        best = min(idxs, key=lambda i: len(repr(problem["plus_input"][i])))
        args = problem["plus_input"][best]
        try:
            fn = P._load(f["source"], entry)
        except BaseException:  # noqa: BLE001
            continue
        out.append({"fault_id": f["fault_id"], "witness": repr(tuple(args))[:300],
                    "expected": H._outcome_text(P.call(ref, args, timeout=2.0)),
                    "got": H._outcome_text(P.call(fn, args))})
    return {"task_id": problem["task_id"], "witnesses": out}


def experience(study: H.Study, arm: str, split: str, reps: int = 1) -> list[dict]:
    """Practice records: tried inputs, exposed count, and missed faults with witnesses."""
    scored = study.score_arm(arm, split, reps, "natural")
    jobs, rows = [], []
    for r in scored["rows"]:
        if r["rep"] != 0:
            continue
        faults = study.faults_for(r["task_id"], "natural")
        missed = [f for f in faults if f["fault_id"] not in r["killed"]]
        missed.sort(key=lambda f: (-f.get("duplicates", 1), len(f["source"])))
        jobs.append({"problem": study.problems[r["task_id"]], "faults": missed[:MAX_MISSES_SHOWN]})
        rows.append(r)
    wit = {job["problem"]["task_id"]: w.get("witnesses", [])
           for job, w in zip(jobs, H.pool_map(_witness_job, jobs))}
    records = []
    for r, job in zip(rows, jobs):
        p = study.problems[r["task_id"]]
        doc = p["prompt"].split('"""')[1] if '"""' in p["prompt"] else p["prompt"].split("'''")[1]
        summary = " ".join(doc.split())[:240]
        by_id = {f["fault_id"]: f for f in job["faults"]}
        missed = [{"code": H._strip_docstrings(by_id[w["fault_id"]]["source"])[:1500],
                   **{k: w[k] for k in ("witness", "expected", "got")}}
                  for w in wit.get(r["task_id"], [])]
        records.append({"task_id": r["task_id"], "summary": summary,
                        "tried": "; ".join(repr(tuple(a))[:160] for a in r["inputs"]),
                        "exposed": len(r["killed"]), "total": r["n_faults"], "missed": missed})
    return records


def distil(study: H.Study, prompt: str, body: str, name: str) -> str:
    reply = H.chat([{"role": "system", "content": prompt}, {"role": "user", "content": body}],
                   effort=study.protocol["effort"], max_tokens=32000, ledger=study.ledger, tag=name)
    text = reply["content"].strip()
    (study.root / f"{name}.md").write_text(text + "\n")
    (study.root / f"{name}.reply.json").write_text(json.dumps(reply, indent=1))
    return text


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    i = sub.add_parser("init")
    i.add_argument("root", type=Path)
    i.add_argument("--dataset", type=Path, required=True)
    i.add_argument("--faults", type=Path, required=True)
    i.add_argument("--budget", type=float, default=8.0)
    i.add_argument("--effort", default="high")
    i.add_argument("--k", type=int, default=H.BUDGET_K)
    c = sub.add_parser("call")
    c.add_argument("root", type=Path)
    c.add_argument("arm")
    c.add_argument("split")
    c.add_argument("--reps", type=int, default=1)
    c.add_argument("--workers", type=int, default=8)
    s = sub.add_parser("score")
    s.add_argument("root", type=Path)
    s.add_argument("arm")
    s.add_argument("split")
    s.add_argument("--reps", type=int, default=1)
    s.add_argument("--population", default="natural")
    e = sub.add_parser("experience")
    e.add_argument("root", type=Path)
    e.add_argument("--arm", default="cold")
    e.add_argument("--split", default="practice")
    e.add_argument("--out", default="experience")
    d = sub.add_parser("lessons")
    d.add_argument("root", type=Path)
    d.add_argument("--from-experience", default="experience")
    d.add_argument("--name", default="lessons_v1")
    v = sub.add_parser("revise")
    v.add_argument("root", type=Path)
    v.add_argument("--base", default="lessons_v1")
    v.add_argument("--log", required=True)
    v.add_argument("--name", default="lessons_v2")
    args = ap.parse_args(argv)

    if args.cmd == "init":
        print(json.dumps(init(args.root, args.dataset.resolve(), args.faults.resolve(),
                              args.budget, args.effort, args.k), indent=2))
        return 0
    study = H.Study(args.root)
    if args.cmd == "call":
        study.call_arm(args.arm, args.split, args.reps, args.workers)
    elif args.cmd == "score":
        if args.arm == "random_plus":
            res = study.score_random(args.split, args.population)
        else:
            res = study.score_arm(args.arm, args.split, args.reps, args.population)
        out = args.root / "scores" / f"{args.arm}__{args.split}__{args.population}.json"
        out.parent.mkdir(exist_ok=True)
        out.write_text(json.dumps(res, indent=1))
        summ = H.summarise(res)
        print(json.dumps({k: summ[k] for k in ("arm", "population", "problems", "mean_fraction_exposed")}))
    elif args.cmd == "experience":
        records = experience(study, args.arm, args.split)
        (args.root / f"{args.out}.json").write_text(json.dumps(records, indent=1))
        (args.root / f"{args.out}.md").write_text(H.experience_text(records))
        print(f"{len(records)} records, {sum(len(r['missed']) for r in records)} missed faults shown")
    elif args.cmd == "lessons":
        body = (args.root / f"{args.from_experience}.md").read_text()
        print(distil(study, H.LESSONS_PROMPT, body, args.name))
    elif args.cmd == "revise":
        base = (args.root / f"{args.base}.md").read_text()
        log = (args.root / f"{args.log}.md").read_text()
        print(distil(study, H.LESSONS_REVISE_PROMPT,
                     f"PLAYBOOK:\n{base}\n\nNEW SESSIONS:\n{log}", args.name))
    print(f"ledger total ${study.ledger.spent:.4f}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
