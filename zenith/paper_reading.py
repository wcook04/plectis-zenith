"""Web projection of the current manuscript's deliberately small TeX surface.

This is not a general TeX renderer. Unsupported content fails publication rather
than being silently omitted. The PDF remains the typographic edition.

Figures: every TikZ figure sits in a ``center`` block preceded by a marker line
``% figure: <id> | <alt text>`` and followed by ``{\\footnotesize caption}``. The
builder renders each to ``paper/<id>.svg``; the site serves ``/assets/<id>.svg``.
Sections: numbered run-in headings ``\\textbf{N. Title}`` (N = 1, 2, ...), each
preceded by ``\\hypertarget{<section-id>}{}``.
"""
import re

CENTER = re.compile(r"\\begin\{center\}.*?\\end\{center\}", re.S)
TIKZ = re.compile(r"\\begin\{tikzpicture\}.*?\\end\{tikzpicture\}", re.S)
# Full description of the repair-loop figure; also its marker text in the manuscript.
DIAGRAM_DESCRIPTION = (
    "Native repair information flow. The model proposes a query; the host runs "
    "the parent and reference programs and compares their answers. Outputs and "
    "errors inform the model's proposed replacement code. Outcomes also inform "
    "further queries in adaptive conditions only; repair-only omits new queries. "
    "The host replays development cases and selects the parent or repair. "
    "Only the selected, frozen source passes into held-out evaluation. "
    "Held-out outcomes do not return to query proposals, repair or selection."
)
FIGURE_MARKER = re.compile(r"^%\s*figure:\s*([a-z0-9-]+)\s*\|\s*(.+?)\s*$\n\s*\\begin\{center\}", re.M)
HEADING = re.compile(r"\\hypertarget\{([a-z0-9-]+)\}\{\}\s*\\textbf\{(\d+)\. ([^}]+)\}")
MATH = {"$(P,E,Q)$": "(P, E, Q)", "$h$": "h", "$t$": "t",
        "$H_{h,t}=f(ht)$": "Hₕ,ₜ = f(ht)", "$f$": "f", "$K=5$": "K = 5", "$K$": "K", "$-$": "−"}


def figures(tex: str) -> list[dict]:
    """Ordered figure records: id, alt text and TikZ source."""
    markers = list(FIGURE_MARKER.finditer(tex))
    sources = list(TIKZ.finditer(tex))
    if len(markers) != len(sources):
        raise ValueError("Every manuscript TikZ figure needs one '% figure: id | alt' marker")
    out = []
    for marker, source in zip(markers, sources):
        if source.start() < marker.end():
            raise ValueError("Figure marker must precede its diagram")
        out.append({"id": marker[1], "alt": marker[2], "source": source[0]})
    if len({f["id"] for f in out}) != len(out):
        raise ValueError("Duplicate figure id")
    return out


def diagram_sources(tex: str) -> dict[str, str]:
    return {f["id"]: f["source"] for f in figures(tex)}


def inline(text: str, keys: list[str]) -> str:
    text = re.sub(r"\\href\{([^}]+)\}\{([^}]+)\}", r"[\2](\1)", text)
    def cite(match):
        locator = inline(match[1], keys) if match[1] else ""
        return ", ".join(f"[[{keys.index(key.strip()) + 1}{', ' + locator if locator else ''}]](#ref-{key.strip()})"
                         for key in match[2].split(","))
    text = re.sub(r"\\cite(?:\[([^\]]*)\])?\{([^}]+)\}", cite, text)
    text = re.sub(r"\\textbf\{([^}]+)\}", r"**\1**", text)
    text = re.sub(r"\\emph\{([^}]+)\}", r"*\1*", text)
    for math, plain in MATH.items():
        text = text.replace(math, plain)
    if re.search(r"(?<!\\)\$", text):
        raise ValueError("Unsupported manuscript math in web projection")
    for source, target in [(r"\%", "%"), (r"\$", "$"), (r"\&", "&"),
                           (r"\S", "§"), (r"\ ", " "), (r"\,", " "), ("~", " "),
                           (r"{,}", ","), ("---", "—"), ("--", "–")]:
        text = text.replace(source, target)
    if re.search(r"\\|[{}]", text):
        raise ValueError(f"Unsupported manuscript TeX in web projection: {text[:160]}")
    return re.sub(r"\s+", " ", text).strip()


def table_markdown(center: str, keys: list[str]) -> str:
    table = re.fullmatch(r"\\begin\{center\}\\small\s*\\begin\{tabular\}\{[lcr]+\}(.*?)\\end\{tabular\}\s*\\end\{center\}", center, re.S)
    if not table:
        raise ValueError("Unsupported manuscript table")
    body = re.sub(r"\\(?:toprule|midrule|bottomrule)", "", table[1])
    rows = [[inline(cell, keys) for cell in row.split("&")]
            for row in body.split(r"\\") if row.strip()]
    if not rows or any(len(row) != len(rows[0]) for row in rows):
        raise ValueError("Ragged manuscript table")
    rows.insert(1, ["---"] * len(rows[0]))
    return "\n".join("| " + " | ".join(row) + " |" for row in rows)


def paper_reading(tex: str, keys: list[str]) -> dict:
    """Preserve every paragraph, table cell, citation and figure caption in order."""
    records = iter(figures(tex))
    tex = re.sub(r"(?<!\\)%[^\n]*", "", tex)
    front, body = tex.split(r"\textbf{Abstract.}", 1)
    disclosure = re.findall(
        r"\\footnotetext\{(\\textbf\{Authorship and AI use\.\}[^{}]+)\}", front)
    if len(disclosure) != 1:
        raise ValueError("Expected one explicit first-page authorship and AI-use disclosure")
    body = body.split(r"\begin{thebibliography}", 1)[0]
    body = body.replace(r"\newpage", "")
    headings = list(HEADING.finditer(body))
    if not headings or [int(h[2]) for h in headings] != list(range(1, len(headings) + 1)):
        raise ValueError("Expected consecutively numbered manuscript sections, each with an anchor")
    body = re.sub(r"\\hypertarget\{[^}]+\}\{\}", "", body)
    headings = list(re.finditer(r"\\textbf\{(\d+)\. ([^}]+)\}", body))
    ids = [h[1] for h in HEADING.finditer(tex)]
    result = {"abstract": inline(body[:headings[0].start()], keys),
              "disclosure": inline(disclosure[0], keys), "sections": []}
    for index, heading in enumerate(headings):
        end = headings[index + 1].start() if index + 1 < len(headings) else len(body)
        part = body[heading.end():end]
        blocks = []
        def paragraphs(text):
            for paragraph in re.split(r"\n\s*\n", text.strip()):
                if not paragraph.strip():
                    continue
                listed = re.fullmatch(r"(.*?)\\begin\{itemize\}(.*?)\\end\{itemize\}\s*", paragraph, re.S)
                if listed:
                    items = [item for item in re.split(r"\\item\b", listed[2]) if item.strip()]
                    lead = inline(listed[1], keys) + "\n\n" if listed[1].strip() else ""
                    content = lead + "\n".join("- " + inline(item, keys) for item in items)
                else:
                    content = inline(paragraph, keys)
                blocks.append({"kind": "markdown", "content": content})
        last = 0
        for center in CENTER.finditer(part):
            paragraphs(part[last:center.start()])
            if TIKZ.search(center[0]):
                figure = re.fullmatch(
                    r"\\begin\{center\}\s*(\\begin\{tikzpicture\}.*?\\end\{tikzpicture\})"
                    r"\s*\{\\footnotesize\s+([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}\s*\\end\{center\}", center[0], re.S)
                if not figure:
                    raise ValueError("Unsupported manuscript figure content outside diagram/caption")
                record = next(records)
                blocks.append({"kind": "figure", "id": record["id"], "url": f"/assets/{record['id']}.svg",
                               "alt": record["alt"], "caption": inline(figure[2], keys)})
            else:
                blocks.append({"kind": "markdown", "content": table_markdown(center[0], keys)})
            last = center.end()
        paragraphs(part[last:])
        result["sections"].append({"id": ids[index], "title": inline(heading[2], keys), "blocks": blocks})
    return result
