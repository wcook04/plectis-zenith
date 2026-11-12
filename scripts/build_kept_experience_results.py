#!/usr/bin/env python3
"""Summarise the kept-experience held-out run and project it into the paper.

Reads score files from a study directory, writes the committed evidence summary
docs/studies/kept-experience/results.json, and regenerates the manuscript block
between '% BEGIN kept_experience_results' and '% END kept_experience_results'.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from research.kept_experience.analyse import bootstrap_diff, load, sign_test  # noqa: E402

ARMS = [("cold", "None"), ("advice", "Generic advice"), ("kept", "Practice record"),
        ("lessons_v1", "Playbook v1"), ("lessons_v2", "Playbook v2"),
        ("imagine", "Imagined faults"), ("imagine_kept", "Imagined faults + record")]
RANDOM = ("random_plus", "Five random EvalPlus inputs")


def summarise(study: Path, split: str, population: str) -> dict:
    base = load(study, "cold", split, population)
    rows = []
    for arm, label in [*ARMS, RANDOM]:
        scores = load(study, arm, split, population)
        if scores is None:
            continue
        mean = sum(scores.values()) / len(scores)
        row = {"arm": arm, "label": label, "problems": len(scores), "mean": round(mean, 4)}
        if arm != "cold" and base is not None:
            diff, lo, hi = bootstrap_diff(scores, base)
            wins, losses, p = sign_test(scores, base)
            row.update(diff_vs_none=round(diff, 4), ci95=[round(lo, 4), round(hi, 4)],
                       wins=wins, losses=losses, ties=len(scores) - wins - losses, sign_p=round(p, 4))
        if arm != RANDOM[0]:
            row["validity"] = {k: v for k, v in validity(study, arm, split, population).items()
                               if k != "fully_valid_tasks"}
            if arm != "cold":
                row["all_inputs_valid_subset"] = restricted(study, arm, split, population)
        rows.append(row)
    return {"split": split, "population": population, "rows": rows}


def validity(study: Path, arm: str, split: str, population: str) -> dict:
    """Share of chosen inputs that satisfied the input contract, and fully valid problems."""
    path = study / "scores" / f"{arm}__{split}__{population}.json"
    rows = json.loads(path.read_text())["rows"]
    valid = sum(r["n_valid"] for r in rows)
    asked = sum(5 for r in rows)
    by_task: dict[str, bool] = {}
    for r in rows:
        by_task[r["task_id"]] = by_task.get(r["task_id"], True) and r["n_valid"] == 5
    return {"valid_inputs": valid, "requested_inputs": asked, "fully_valid_tasks": sorted(t for t, ok in by_task.items() if ok)}


def restricted(study: Path, arm: str, split: str, population: str) -> dict:
    """Exploratory: paired change against none on problems where both had every input valid."""
    a, b = load(study, arm, split, population), load(study, "cold", split, population)
    keep = set(validity(study, arm, split, population)["fully_valid_tasks"]) & \
        set(validity(study, "cold", split, population)["fully_valid_tasks"])
    a = {t: v for t, v in a.items() if t in keep}
    b = {t: v for t, v in b.items() if t in keep}
    diff, lo, hi = bootstrap_diff(a, b)
    wins, losses, p = sign_test(a, b)
    return {"problems": len(keep), "diff_vs_none": round(diff, 4), "ci95": [round(lo, 4), round(hi, 4)],
            "wins": wins, "losses": losses, "sign_p": round(p, 4)}


def interval(study: Path, arm: str, split: str, population: str) -> tuple[float, float]:
    """95% bootstrap interval of an arm's mean over problems."""
    import random
    scores = load(study, arm, split, population)
    values = list(scores.values())
    rng = random.Random(11)
    means = sorted(sum(rng.choice(values) for _ in values) / len(values) for _ in range(20000))
    return means[500], means[19500]


def tex_block(study: Path, primary: dict, secondary: dict | None) -> str:
    pct = lambda x: f"{100 * x:.1f}"
    lines = [r"\begin{center}\small", r"\begin{tabular}{lrrr}", r"\toprule",
             r"Shown to the tester & Exposed (\%) & Change vs none & Better / worse problems\\", r"\midrule"]
    for row in primary["rows"]:
        if row["arm"] == "cold":
            lines.append(f"{row['label']} & {pct(row['mean'])} & -- & --\\\\")
        else:
            lo, hi = row["ci95"]
            signed = lambda v: ("+" if v >= 0 else "$-$") + pct(abs(v))
            lines.append(f"{row['label']} & {pct(row['mean'])} & {signed(row['diff_vs_none'])} "
                         f"[{signed(lo)}, {signed(hi)}] & {row['wins']} / {row['losses']}\\\\")
    lines += [r"\bottomrule", r"\end{tabular}", r"\end{center}"]
    # dot plot in plain TikZ: paired change in percentage points against "none", one row per arm
    rows = [row for row in primary["rows"] if row["arm"] != "cold"]
    lo_all = min(row["ci95"][0] for row in rows)
    hi_all = max(row["ci95"][1] for row in rows)
    x0 = 10 * ((100 * lo_all) // 10)
    x1 = 10 * (-((-100 * hi_all) // 10))
    width = 9.0
    xs = lambda v: (100 * v - x0) / (x1 - x0) * width
    plot = [r"% figure: kept-experience-results | Change in the share of hidden model-written faults exposed, against a tester shown nothing, on 58 held-out problems.",
            r"\begin{center}",
            r"\begin{tikzpicture}[font=\footnotesize, y=-6.2mm]"]
    for tick in range(int(x0), int(x1) + 1, 10):
        plot.append(rf"\draw[black!15] ({xs(tick / 100):.3f},-0.6) -- ({xs(tick / 100):.3f},{len(rows) - 0.4:.1f});")
        label = f"+{tick}" if tick > 0 else ("$-$" + str(-tick) if tick < 0 else "0")
        plot.append(rf"\node[below, font=\scriptsize] at ({xs(tick / 100):.3f},{len(rows) - 0.4:.1f}) {{{label}}};")
    plot.append(rf"\draw[black!60] ({xs(0):.3f},-0.6) -- ({xs(0):.3f},{len(rows) - 0.4:.1f});")
    plot.append(rf"\node[font=\scriptsize] at ({width / 2:.2f},{len(rows) + 0.45:.1f}) {{change against a tester shown nothing (percentage points), paired over problems}};")
    for i, row in enumerate(rows):
        lo, hi = row["ci95"]
        dashed = ", densely dashed" if row["arm"] == RANDOM[0] else ""
        fill = "white" if row["arm"] == RANDOM[0] else "black"
        plot.append(rf"\node[anchor=east] at (-0.15,{i}) {{{row['label']}}};")
        plot.append(rf"\draw[thick{dashed}] ({xs(lo):.3f},{i}) -- ({xs(hi):.3f},{i});")
        plot.append(rf"\fill[draw=black, fill={fill}] ({xs(row['diff_vs_none']):.3f},{i}) circle (1.4pt);")
    plot.append(r"\end{tikzpicture}")
    n = primary["rows"][0]["problems"]
    caption = (r"{\footnotesize Paired change against a tester shown nothing, " + f"{n} held-out problems" +
               r". Dots are mean differences; bars are 95\% bootstrap intervals over problems. "
               r"The open dot is five random EvalPlus inputs, which uses no model.}")
    plot += ["", caption, r"\end{center}"]
    return "\n".join(["% BEGIN kept_experience_results", *lines, "", *plot, "% END kept_experience_results"])


EXPERIMENT2 = [("cold_nr", "None, reasoning off"), ("kept_nr", "Practice record, reasoning off"),
               ("lessons_v1_nr", "Playbook v1, reasoning off"), ("lessons_v2_nr", "Playbook v2, reasoning off")]


def experiment2(study: Path) -> dict:
    base = load(study, "cold_nr", "heldout", "natural")
    rows = []
    for arm, label in [*EXPERIMENT2, ("cold", "None, high reasoning (experiment 1)")]:
        scores = load(study, arm, "heldout", "natural")
        row = {"arm": arm, "label": label, "mean": round(sum(scores.values()) / len(scores), 4)}
        if arm != "cold_nr":
            diff, lo, hi = bootstrap_diff(scores, base)
            wins, losses, p = sign_test(scores, base)
            row.update(diff_vs_none_reasoning_off=round(diff, 4), ci95=[round(lo, 4), round(hi, 4)],
                       wins=wins, losses=losses, sign_p=round(p, 4))
        rows.append(row)
    return {"rows": rows}


def without_timeouts(study: Path) -> dict | None:
    """Exploratory: exposures excluding faults whose only observed difference was a timeout."""
    files = {arm: study / f"scores_no_timeout_{arm}.json" for arm, _ in ARMS}
    if not all(f.exists() for f in files.values()):
        return None
    scores = {arm: json.loads(f.read_text()) for arm, f in files.items()}
    rows = []
    for arm, label in ARMS:
        row = {"arm": arm, "label": label, "mean": round(sum(scores[arm].values()) / len(scores[arm]), 4)}
        if arm != "cold":
            diff, lo, hi = bootstrap_diff(scores[arm], scores["cold"])
            wins, losses, p = sign_test(scores[arm], scores["cold"])
            row.update(diff_vs_none=round(diff, 4), ci95=[round(lo, 4), round(hi, 4)], wins=wins, losses=losses,
                       sign_p=round(p, 4))
        rows.append(row)
    return {"rows": rows}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("study", type=Path)
    ap.add_argument("--split", default="heldout")
    args = ap.parse_args()
    primary = summarise(args.study, args.split, "natural")
    secondary = summarise(args.study, args.split, "mutant")
    out = ROOT / "docs/studies/kept-experience/results.json"
    summary = {"primary": primary, "secondary_mutants": secondary,
               "experiment2_reasoning_off": experiment2(args.study),
               "exploratory_without_timeout_exposures": without_timeouts(args.study)}
    out.write_text(json.dumps(summary, indent=2) + "\n")
    manuscript = ROOT / "paper/zenith.tex"
    tex = manuscript.read_text()
    block = tex_block(args.study, primary, secondary)
    pattern = re.compile(r"% BEGIN kept_experience_results.*?% END kept_experience_results", re.S)
    if pattern.search(tex):
        manuscript.write_text(pattern.sub(lambda _: block, tex))
    print(json.dumps(primary, indent=1))


if __name__ == "__main__":
    main()
