#!/usr/bin/env python3
"""Render every manuscript TikZ figure as an accessible website SVG (paper/<id>.svg).

The standalone preamble reuses the manuscript's own TikZ libraries and the
block between '% BEGIN figure styles' and '% END figure styles', so the PDF and
the web figures come from the same source. Each SVG carries a title and the
figure's description from its '% figure: id | description' marker.
"""
import argparse
from html import escape
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


def accessible(svg: str, figure_id: str, description: str) -> str:
    title = description.split(":", 1)[0].split(".", 1)[0].strip()
    start = svg.index("<svg ")
    end = svg.index(">", start)
    svg = svg[:end] + f' role="img" aria-labelledby="{figure_id}-title {figure_id}-description"' + svg[end:]
    end = svg.index(">", start) + 1
    return (svg[:end] + f'\n<title id="{figure_id}-title">{escape(title)}</title>'
            + f'\n<desc id="{figure_id}-description">{escape(description)}</desc>\n' + svg[end:])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", choices=("tectonic", "pdflatex"), default="tectonic",
                        help="TeX compiler (default: tectonic; pdflatex uses an installed TeX Live)")
    args = parser.parse_args()
    tex = (ROOT / "paper/zenith.tex").read_text()
    pre = preamble(tex)
    for figure in figures(tex):
        # Match the manuscript's 11pt base so \footnotesize has the same size.
        source = (r"\documentclass[11pt,tikz,border=2pt]{standalone}" + "\n" + pre + "\n"
                  + r"\begin{document}" + "\n" + figure["source"] + "\n" + r"\end{document}")
        with tempfile.TemporaryDirectory(prefix="zenith-paper-figure-") as temporary:
            work = Path(temporary)
            (work / "figure.tex").write_text(source)
            command = (["tectonic", "figure.tex"] if args.engine == "tectonic" else
                       ["pdflatex", "-no-shell-escape", "-interaction=nonstopmode",
                        "-halt-on-error", "figure.tex"])
            subprocess.run(command, cwd=work, check=True)
            subprocess.run(["pdftocairo", "-svg", "figure.pdf", "figure.svg"], cwd=work, check=True)
            svg = accessible((work / "figure.svg").read_text(), figure["id"], figure["alt"])
            (ROOT / f"paper/{figure['id']}.svg").write_text(svg)
        print(f"Rendered paper/{figure['id']}.svg; inspect before binding its release hash.")


if __name__ == "__main__":
    main()
