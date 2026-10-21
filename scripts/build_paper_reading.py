#!/usr/bin/env python3
"""Render the paper figure or check the reviewed PDF and web reading edition."""
import argparse
from html import escape
from pathlib import Path
import re
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from zenith.paper_reading import DIAGRAM_DESCRIPTION, diagram_source


def check_publication():
    """Check the published bytes, including disclosure placement and page count."""
    from zenith.web_content import PublicContent
    paper = PublicContent(ROOT).paper()
    if not paper['pdf_current']:
        raise ValueError('The manuscript and PDF differ from the reviewed edition')
    text = subprocess.check_output(
        ['pdftotext', str(ROOT / 'paper/zenith.pdf'), '-'], text=True)
    pages = [page for page in text.split('\f') if page.strip()]
    if len(pages) != 3:
        raise ValueError(f'Expected the three-page paper; found {len(pages)} pages')
    def normalise(value):
        value = re.sub(r'-\s*\n\s*', '', value)
        return ' '.join(value.split())
    disclosure = paper['reading']['disclosure'].replace('**', '')
    if normalise(disclosure) not in normalise(pages[0]):
        raise ValueError('The web disclosure must also appear on PDF page one')
    print('Verified the reviewed three-page PDF and matching first-page/web AI-use disclosure.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true',
                        help='Check the reviewed PDF and disclosure without rebuilding the figure')
    parser.add_argument("--engine", choices=("tectonic", "pdflatex"), default="tectonic",
                        help="TeX compiler (default: tectonic; pdflatex uses an installed TeX Live)")
    args = parser.parse_args()
    if args.check:
        check_publication()
        return
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
