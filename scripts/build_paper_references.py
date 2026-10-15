#!/usr/bin/env python3
"""Project the reviewed bibliography and check exact manuscript support bindings."""
import argparse
from pathlib import Path
import sys
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from zenith.web_content import BIBLIOGRAPHY, paper_citations, reference_bibliography, reviewed_references


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Check without rewriting the bibliography")
    parser.add_argument("--index", action="store_true", help="Check the staged manuscript and records")
    args = parser.parse_args()
    if args.index:
        with tempfile.TemporaryDirectory(prefix="zenith-reference-index-") as temporary:
            root = Path(temporary)
            (root / "paper").mkdir()
            for name in ("paper/zenith.tex", "paper/references.json"):
                (root / name).write_bytes(subprocess.check_output(["git", "show", ":" + name], cwd=ROOT))
            citations, _ = paper_citations(root, (root / "paper/zenith.tex").read_text())
        print(f"Verified {len(citations)} staged source editions and manuscript bindings.")
        return
    manuscript = ROOT / "paper/zenith.tex"
    tex = manuscript.read_text()
    records, _ = reviewed_references(ROOT)
    if len(list(BIBLIOGRAPHY.finditer(tex))) != 1:
        parser.error("Manuscript must contain exactly one inline bibliography")
    if not args.check:
        tex = BIBLIOGRAPHY.sub(lambda _: reference_bibliography(records), tex)
    citations, _ = paper_citations(ROOT, tex)
    if not args.check and tex != manuscript.read_text():
        manuscript.write_text(tex)
    print(f"Verified {len(citations)} source editions and every manuscript citation binding.")


if __name__ == "__main__":
    main()
