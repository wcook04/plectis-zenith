#!/usr/bin/env python3
"""Render the manuscript's existing TikZ diagram as the website's SVG asset."""
import argparse
from html import escape
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from zenith.paper_reading import DIAGRAM_DESCRIPTION, diagram_source


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", choices=("tectonic", "pdflatex"), default="tectonic",
                        help="TeX compiler (default: tectonic; pdflatex uses an installed TeX Live)")
    args = parser.parse_args()
    diagram = diagram_source((ROOT / "paper/zenith.tex").read_text())
    # Match the manuscript's 11pt base so \footnotesize has the same size.
    source = (r"\documentclass[11pt,tikz,border=2pt]{standalone}" + "\n"
              + r"\usepackage[T1]{fontenc}\usepackage{lmodern}\usetikzlibrary{arrows.meta,positioning}" + "\n"
              + r"\begin{document}" + "\n" + diagram + "\n" + r"\end{document}")
    with tempfile.TemporaryDirectory(prefix="zenith-paper-figure-") as temporary:
        work = Path(temporary)
        (work / "repair-loop.tex").write_text(source)
        command = (["tectonic", "repair-loop.tex"] if args.engine == "tectonic" else
                   ["pdflatex", "-no-shell-escape", "-interaction=nonstopmode",
                    "-halt-on-error", "repair-loop.tex"])
        subprocess.run(command, cwd=work, check=True)
        subprocess.run(["pdftocairo", "-svg", "repair-loop.pdf", "repair-loop.svg"], cwd=work, check=True)
        svg = (work / "repair-loop.svg").read_text()
        start = svg.index("<svg ")
        end = svg.index(">", start)
        svg = (svg[:end] + ' role="img" aria-labelledby="diagram-title diagram-description"' + svg[end:])
        end = svg.index(">", start) + 1
        svg = (svg[:end] + '\n<title id="diagram-title">Native program repair</title>'
               + '\n<desc id="diagram-description">' + escape(DIAGRAM_DESCRIPTION) + '</desc>\n'
               + svg[end:])
        (ROOT / "paper/repair-loop.svg").write_text(svg)
    print("Rendered paper/repair-loop.svg from the manuscript TikZ diagram; inspect before binding its release hash.")


if __name__ == "__main__":
    main()
