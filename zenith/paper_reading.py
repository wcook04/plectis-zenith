"""Web projection of the current manuscript's deliberately small TeX surface.

This is not a general TeX renderer. Unsupported content fails publication rather
than being silently omitted. The PDF remains the typographic edition.
"""
import re

CENTER = re.compile(r"\\begin\{center\}.*?\\end\{center\}", re.S)
TIKZ = re.compile(r"\\begin\{tikzpicture\}.*?\\end\{tikzpicture\}", re.S)


def diagram_source(tex: str) -> str:
    figures = list(TIKZ.finditer(tex))
    if len(figures) != 1:
        raise ValueError("The current paper must contain one repair-loop diagram")
    return figures[0][0]


def inline(text: str, keys: list[str]) -> str:
    text = re.sub(r"\\href\{([^}]+)\}\{([^}]+)\}", r"[\2](\1)", text)
    def cite(match):
        locator = inline(match[1], keys) if match[1] else ""
        return ", ".join(f"[[{keys.index(key.strip()) + 1}{', ' + locator if locator else ''}]](#ref-{key.strip()})"
                         for key in match[2].split(","))
    text = re.sub(r"\\cite(?:\[([^\]]*)\])?\{([^}]+)\}", cite, text)
    text = re.sub(r"\\textbf\{([^}]+)\}", r"**\1**", text)
    for math, plain in {"$(P,E,Q)$": "(P, E, Q)", "$h$": "h", "$t$": "t",
                        "$H_{h,t}=f(ht)$": "Hₕ,ₜ = f(ht)", "$f$": "f"}.items():
        text = text.replace(math, plain)
    if re.search(r"(?<!\\)\$", text):
        raise ValueError("Unsupported manuscript math in web projection")
    for source, target in [(r"\%", "%"), (r"\$", "$"), (r"\&", "&"),
                           (r"\S", "§"), (r"\ ", " "), ("~", " "),
                           ("---", "—"), ("--", "–")]:
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
    tex = re.sub(r"(?<!\\)%[^\n]*", "", tex)
    body = tex.split(r"\textbf{Abstract.}", 1)[1].split(r"\begin{thebibliography}", 1)[0]
    body = re.sub(r"\\hypertarget\{[^}]+\}\{\}|\\newpage", "", body)
    headings = list(re.finditer(r"\\textbf\{([123])\. ([^}]+)\}", body))
    if [h[1] for h in headings] != ["1", "2", "3"]:
        raise ValueError("Expected the manuscript's three numbered sections")
    result = {"abstract": inline(body[:headings[0].start()], keys), "sections": []}
    for index, heading in enumerate(headings):
        part = body[heading.end():headings[index + 1].start() if index < 2 else len(body)]
        blocks = []
        def paragraphs(text):
            for paragraph in re.split(r"\n\s*\n", text.strip()):
                if paragraph.strip():
                    blocks.append({"kind": "markdown", "content": inline(paragraph, keys)})
        last = 0
        for center in CENTER.finditer(part):
            paragraphs(part[last:center.start()])
            if TIKZ.search(center[0]):
                figure = re.fullmatch(
                    r"\\begin\{center\}\s*(\\begin\{tikzpicture\}.*?\\end\{tikzpicture\})"
                    r"\s*\{\\footnotesize\s+([^{}]*)\}\s*\\end\{center\}", center[0], re.S)
                if not figure:
                    raise ValueError("Unsupported manuscript figure content outside diagram/caption")
                blocks.append({"kind": "figure", "url": "/assets/repair-loop.svg",
                               "alt": "Native repair: query execution, measured feedback, development selection and frozen held-out evaluation.",
                               "caption": inline(figure[2], keys)})
            else:
                blocks.append({"kind": "markdown", "content": table_markdown(center[0], keys)})
            last = center.end()
        paragraphs(part[last:])
        result["sections"].append({"id": ("idea", "results", "next")[index],
                                   "title": inline(heading[2], keys), "blocks": blocks})
    return result
