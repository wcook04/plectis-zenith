#!/usr/bin/env python3
"""Render the manuscript's existing TikZ diagram as the website's SVG asset."""
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from zenith.paper_reading import diagram_source


def main():
    diagram = diagram_source((ROOT / "paper/zenith.tex").read_text())
    source = (r"\documentclass[tikz,border=2pt]{standalone}" + "\n"
              + r"\usepackage[T1]{fontenc}\usepackage{lmodern}\usetikzlibrary{arrows.meta,positioning}" + "\n"
              + r"\begin{document}" + "\n" + diagram + "\n" + r"\end{document}")
    with tempfile.TemporaryDirectory(prefix="zenith-paper-figure-") as temporary:
        work = Path(temporary)
        (work / "repair-loop.tex").write_text(source)
        subprocess.run(["tectonic", "repair-loop.tex"], cwd=work, check=True)
        subprocess.run(["pdftocairo", "-svg", "repair-loop.pdf", "repair-loop.svg"], cwd=work, check=True)
        (ROOT / "paper/repair-loop.svg").write_bytes((work / "repair-loop.svg").read_bytes())
    print("Rendered paper/repair-loop.svg from the manuscript TikZ diagram; inspect before binding its release hash.")


if __name__ == "__main__":
    main()
