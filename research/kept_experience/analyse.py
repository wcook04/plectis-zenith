"""Paired analysis of kept-experience scores (problem is the unit)."""

from __future__ import annotations

import json
import math
import random
import sys
from pathlib import Path

from research.kept_experience.harness import summarise


def load(root: Path, arm: str, split: str, population: str) -> dict[str, float] | None:
    path = root / "scores" / f"{arm}__{split}__{population}.json"
    if not path.exists():
        return None
    return summarise(json.loads(path.read_text()))["per_task"]


def bootstrap_diff(a: dict, b: dict, draws: int = 20000, seed: int = 7) -> tuple[float, float, float]:
    tasks = sorted(set(a) & set(b))
    d = [a[t] - b[t] for t in tasks]
    rng = random.Random(seed)
    means = sorted(sum(rng.choice(d) for _ in d) / len(d) for _ in range(draws))
    return sum(d) / len(d), means[int(0.025 * draws)], means[int(0.975 * draws)]


def sign_test(a: dict, b: dict) -> tuple[int, int, float]:
    tasks = sorted(set(a) & set(b))
    wins = sum(1 for t in tasks if a[t] > b[t] + 1e-12)
    losses = sum(1 for t in tasks if b[t] > a[t] + 1e-12)
    n = wins + losses
    if n == 0:
        return wins, losses, 1.0
    tail = sum(math.comb(n, i) for i in range(0, min(wins, losses) + 1)) / 2 ** n
    return wins, losses, min(1.0, 2 * tail)


def table(root: Path, split: str, population: str, arms: list[str], baseline: str) -> list[dict]:
    base = load(root, baseline, split, population)
    rows = []
    for arm in arms:
        s = load(root, arm, split, population)
        if s is None:
            continue
        row = {"arm": arm, "problems": len(s), "mean": round(sum(s.values()) / len(s), 4)}
        if base is not None and arm != baseline:
            m, lo, hi = bootstrap_diff(s, base)
            w, l, p = sign_test(s, base)
            row.update(diff_vs_baseline=round(m, 4), ci95=[round(lo, 4), round(hi, 4)],
                       wins=w, losses=l, sign_p=round(p, 4))
        rows.append(row)
    return rows


if __name__ == "__main__":
    root, split, population, baseline = Path(sys.argv[1]), sys.argv[2], sys.argv[3], sys.argv[4]
    arms = sys.argv[5].split(",")
    for row in table(root, split, population, arms, baseline):
        print(json.dumps(row))
