#!/usr/bin/env python3
"""Render every manuscript TikZ figure as a website SVG asset (paper/<id>.svg).

The standalone preamble reuses the manuscript's own TikZ libraries and the
block between '% BEGIN figure styles' and '% END figure styles', so the PDF and
the web figures come from the same source.
"""
from pathlib import Path
import re
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from zenith.paper_reading import figures


def preamble(tex: str) -> str:
    head = tex.split(r"\begin{document}", 1)[0]
    lines = [line for line in head.splitlines()
             if line.startswith((r"\usetikzlibrary", r"\usepgfplotslibrary", r"\pgfplotsset"))]
    styles = re.search(r"% BEGIN figure styles\n(.*?)% END figure styles", head, re.S)
    packages = r"\usepackage[T1]{fontenc}\usepackage{lmodern,amsmath}"
    if r"{pgfplots}" in head:
        packages += r"\usepackage{pgfplots}"
    return "\n".join([packages, *lines, styles[1] if styles else ""])


def main():
    tex = (ROOT / "paper/zenith.tex").read_text()
    pre = preamble(tex)
    for figure in figures(tex):
        source = (r"\documentclass[tikz,border=2pt]{standalone}" + "\n" + pre + "\n"
                  + r"\begin{document}" + "\n" + figure["source"] + "\n" + r"\end{document}")
        with tempfile.TemporaryDirectory(prefix="zenith-paper-figure-") as temporary:
            work = Path(temporary)
            (work / "figure.tex").write_text(source)
            subprocess.run(["tectonic", "figure.tex"], cwd=work, check=True)
            subprocess.run(["pdftocairo", "-svg", "figure.pdf", "figure.svg"], cwd=work, check=True)
            (ROOT / f"paper/{figure['id']}.svg").write_bytes((work / "figure.svg").read_bytes())
        print(f"Rendered paper/{figure['id']}.svg; inspect before binding its release hash.")


if __name__ == "__main__":
    main()
