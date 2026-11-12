#!/usr/bin/env python3
"""Re-score the kept-experience study from its evidence bundle, with no model calls.

Usage:
    python scripts/replay_kept_experience.py pack STUDY_DIR FAULTS_JSON   # maintainers: write the bundle
    python scripts/replay_kept_experience.py replay HUMANEVALPLUS_JSONL [--arms cold,kept]

`replay` rebuilds a temporary study directory from examples/kept-experience/
(stored replies, fault population, protocol), executes every chosen input on the
reference and the hidden faults exactly as the study did, and compares each
problem's score with the committed score files. HumanEvalPlus v0.1.10 must be
supplied (sha256 42526ec0e7d5f3ee0b06d6ced98f8c8bae3d76519151bfb3d36f79010645bd7f):
https://github.com/evalplus/humanevalplus_release/releases/download/v0.1.10/HumanEvalPlus.jsonl.gz
Executing sampled model code is sandboxed only by process limits; run it in a
disposable environment.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
BUNDLE = ROOT / "examples/kept-experience"
DATASET_SHA256 = "42526ec0e7d5f3ee0b06d6ced98f8c8bae3d76519151bfb3d36f79010645bd7f"
ARMS = ["cold", "advice", "kept", "lessons_v1", "lessons_v2", "imagine", "imagine_kept",
        "cold_nr", "kept_nr", "lessons_v1_nr", "lessons_v2_nr"]


def pack(study: Path, faults: Path) -> None:
    BUNDLE.mkdir(parents=True, exist_ok=True)
    rows = []
    for folder in ("replies", "replies_superseded"):
        for f in sorted((study / folder).glob("*/*.json")):
            row = json.loads(f.read_text())
            row["file"] = f"{folder}/{f.parent.name}/{f.name}"
            rows.append(row)
    text = "\n".join(json.dumps(r, ensure_ascii=False, sort_keys=True) for r in rows) + "\n"
    if "/Users/" in text:
        raise SystemExit("refusing to pack a local path")
    (BUNDLE / "replies.jsonl.gz").write_bytes(gzip.compress(text.encode(), 9, mtime=0))
    (BUNDLE / "faults.json.gz").write_bytes(gzip.compress(faults.read_bytes(), 9, mtime=0))
    shutil.copy(study / "ledger.jsonl", BUNDLE / "ledger.jsonl")
    scores = BUNDLE / "scores"
    scores.mkdir(exist_ok=True)
    for f in sorted((study / "scores").glob("*__heldout__*.json")):
        shutil.copy(f, scores / f.name)
    protocol = json.loads((study / "protocol.json").read_text())
    protocol["dataset_path"] = protocol["faults_path"] = "<supplied at replay>"
    (BUNDLE / "protocol.json").write_text(json.dumps(protocol, indent=2) + "\n")
    print(f"packed {len(rows)} replies into {BUNDLE.relative_to(ROOT)}")


def replay(dataset: Path, arms: list[str]) -> int:
    from research.kept_experience import harness as H
    from research.kept_experience.harness import summarise
    if hashlib.sha256(dataset.read_bytes()).hexdigest() != DATASET_SHA256:
        raise SystemExit("HumanEvalPlus file does not match the study's v0.1.10 edition")
    mismatches = 0
    with tempfile.TemporaryDirectory(prefix="kept-experience-replay-") as tmp:
        root = Path(tmp)
        faults = root / "faults.json"
        faults.write_bytes(gzip.decompress((BUNDLE / "faults.json.gz").read_bytes()))
        protocol = json.loads((BUNDLE / "protocol.json").read_text())
        protocol.update(dataset_path=str(dataset), faults_path=str(faults))
        (root / "protocol.json").write_text(json.dumps(protocol))
        for line in gzip.decompress((BUNDLE / "replies.jsonl.gz").read_bytes()).decode().splitlines():
            row = json.loads(line)
            target = root / row.pop("file")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(row))
        study = H.Study(root)
        for arm in arms:
            for population in ("natural", "mutant"):
                recorded = BUNDLE / "scores" / f"{arm}__heldout__{population}.json"
                if not recorded.exists():
                    continue
                fresh = summarise(study.score_arm(arm, "heldout", 2, population))
                kept = summarise(json.loads(recorded.read_text()))
                same = all(abs(fresh["per_task"][t] - kept["per_task"][t]) < 1e-9 for t in kept["per_task"])
                mismatches += not same
                print(f"{arm:14s} {population:7s} recorded {kept['mean_fraction_exposed']:.4f} "
                      f"replayed {fresh['mean_fraction_exposed']:.4f} {'match' if same else 'MISMATCH'}")
    return 1 if mismatches else 0


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("pack")
    p.add_argument("study", type=Path)
    p.add_argument("faults", type=Path)
    r = sub.add_parser("replay")
    r.add_argument("dataset", type=Path)
    r.add_argument("--arms", default=",".join(ARMS))
    args = ap.parse_args()
    if args.cmd == "pack":
        pack(args.study, args.faults)
    else:
        raise SystemExit(replay(args.dataset.resolve(), args.arms.split(",")))


if __name__ == "__main__":
    main()
