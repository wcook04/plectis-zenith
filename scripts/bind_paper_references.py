#!/usr/bin/env python3
"""Rebind reviewed references to the paragraphs of paper/zenith.tex that cite them.

For each record, every manuscript paragraph containing a citation of its key
becomes one artifact link with the exact paragraph text and its hash. The
supporting source locators come from SUPPORT (key -> locator ids); a citation
without a declared support mapping fails. Records are reordered by first
citation. Run after reviewing the cited passages; hashes record custody, they do
not certify that a source supports the sentence.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
CITE = re.compile(r"\\cite(?:\[[^\]]*\])?\{([^}]+)\}")

# Which reviewed locators support this manuscript's citations of each source.
SUPPORT = {
    "psr": ["future-test-state", "known-model-construction"],
    "mutants": ["coupling", "correlation"],
    "evalplus": ["input-generation", "base-tests-miss"],
    "codet": ["test-generation", "dual-agreement"],
    "mutap": ["surviving-mutant-prompt"],
    "ach": ["fault-of-concern-mutants", "test-for-mutant"],
    "reflexion": ["verbal-reflection", "same-task-trials"],
    "expel": ["held-out-tasks", "insights-and-retrieval"],
    "cheatsheet": ["raw-history-hurts", "generic-instructions-help"],
    "ace": ["context-collapse", "playbook-results"],
}


def paragraphs(prose: str) -> list[str]:
    return [p for p in re.split(r"\n\s*\n", prose) if p.strip()]


def main() -> None:
    tex = (ROOT / "paper/zenith.tex").read_text()
    prose = tex.split(r"\begin{thebibliography}", 1)[0]
    visible = re.sub(r"(?<!\\)%[^\n]*", "", prose)
    data = json.loads((ROOT / "paper/references.json").read_text())
    records = {r["id"]: r for r in data["sources"]}
    order: list[str] = []
    for use in CITE.finditer(visible):
        for key in (k.strip() for k in use[1].split(",")):
            if key not in order:
                order.append(key)
    missing = [k for k in order if k not in records]
    if missing:
        raise SystemExit(f"No reviewed record for: {missing}")
    for key in order:
        record = records[key]
        locator_ids = {loc["id"] for loc in record["source_locators"]}
        support = SUPPORT.get(key) or [b for link in record.get("artifact_links", [])
                                       for b in link.get("source_locator_ids", [])]
        support = list(dict.fromkeys(support))
        if not support or set(support) - locator_ids:
            raise SystemExit(f"Undeclared or unknown support locators for {key}: {support}")
        links = []
        for para in paragraphs(prose):
            if any(key in [k.strip() for k in use[1].split(",")] for use in CITE.finditer(para)):
                text = para.strip("\n")
                if prose.count(text) != 1:
                    raise SystemExit(f"Paragraph citing {key} is not unique in the manuscript")
                links.append({"path": "paper/zenith.tex", "expected_text": text,
                              "excerpt_sha256": hashlib.sha256(text.encode()).hexdigest(),
                              "source_locator_ids": support})
        record["artifact_links"] = links
    unused = [k for k in records if k not in order]
    if unused:
        raise SystemExit(f"Reviewed records not cited by the manuscript: {unused}")
    data["sources"] = [records[k] for k in order]
    (ROOT / "paper/references.json").write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n")
    print(f"Bound {len(order)} sources: {', '.join(order)}")


if __name__ == "__main__":
    main()
