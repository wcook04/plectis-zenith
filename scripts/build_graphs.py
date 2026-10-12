#!/usr/bin/env python3
"""Render exact native dependency atlases; only Python's standard library."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from xml.sax.saxutils import escape, quoteattr

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "graphs"
LANES = ("stock", "etf", "macro", "news", "poly", "calc", "stockgrid")
WIDTH = 1440
CARD = 302
STEP = 66


def text(x, y, value, size=14, weight="normal", color="#334155"):
    return (f'<text x="{x}" y="{y}" font-size="{size}" '
            f'font-weight="{weight}" fill="{color}">{escape(value)}</text>')


def load_nodes():
    nodes, hashes, groups = {}, {}, {}
    for group in ("feeds", "lab", "oracle", "refinement"):
        groups[group] = []
        for path in sorted((ROOT / "codex/substrate/nodes" / group).glob("*.json")):
            raw = path.read_bytes()
            node = json.loads(raw)
            identifier = node["id"]
            if identifier in nodes:
                raise ValueError(f"duplicate node: {identifier}")
            nodes[identifier] = node
            hashes[str(path.relative_to(ROOT))] = hashlib.sha256(raw).hexdigest()
            groups[group].append(identifier)
    return nodes, hashes, groups


def closure(nodes, seeds):
    found = set()

    def visit(identifier):
        if identifier not in found:
            found.add(identifier)
            for dependency in nodes[identifier].get("dependencies", []):
                visit(dependency)

    for identifier in seeds:
        visit(identifier)
    return found


def card(nodes, identifier, x, y, height=56, output=False):
    kind = nodes[identifier]["type"].upper()
    emphasis = identifier in {"lab_decide", "lab_director", "oracle_cp2_emitter"}
    fill = "#e6f3ef" if emphasis else ("#eef2f6" if kind == "TOOL" else "#fffaf0")
    stroke = "#527b6c" if emphasis else "#a5afbd"
    pieces = [f'<g data-node={quoteattr(identifier)}>\n<title>{escape(identifier)}</title>',
              f'<rect x="{x}" y="{y}" width="{CARD}" height="{height}" rx="6" '
              f'fill="{fill}" stroke="{stroke}"/>']
    label_y = y + height / 2 + 3
    pieces += [text(x + 12, y + 18, kind, 10, color="#64748b"),
               text(x + 12, label_y + (7 if height == 56 else 0), identifier, 14, "600")]
    if output and height > 100:
        pieces.append(text(x + 12, label_y + 24, "Output artifact", 12, color="#64748b"))
    pieces.append("</g>")
    return "\n".join(pieces)


def panel(nodes, identifier, dependencies, x, y, part=""):
    """One artifact and its exact immediate prerequisites, with parallel edges."""
    body_height = max(56, len(dependencies) * STEP - 10)
    pieces = [text(x, y + 20, identifier + part, 16, "600"),
              text(x, y + 43, "PREREQUISITES", 10, color="#64748b"),
              text(x + 350, y + 43, "PRODUCED NODE", 10, color="#64748b")]
    body_y = y + 54
    for i, dependency in enumerate(dependencies):
        cy = body_y + i * STEP + 28
        pieces.append(f'<path data-from={quoteattr(dependency)} data-to={quoteattr(identifier)} '
                      f'd="M {x + CARD} {cy} H {x + 350}" class="dependency" '
                      'marker-end="url(#arrow)">'
                      f'<title>{escape(dependency)} → {escape(identifier)}</title></path>')
    # Paint boxes after arrows. Every destination port is distinct.
    for i, dependency in enumerate(dependencies):
        pieces.append(card(nodes, dependency, x, body_y + i * STEP))
    pieces.append(card(nodes, identifier, x + 350, body_y, body_height, True))
    if not dependencies:
        pieces.append(text(x + 12, body_y + 25, "No declared prerequisites", 13))
        pieces.append(text(x + 12, body_y + 47, "Runtime inputs may still be required.", 12))
    return pieces, body_height + 80


def render(slug, title, description, nodes, hashes, scope, order, notes, extra=None):
    expected = {(dep, identifier) for identifier in scope
                for dep in nodes[identifier].get("dependencies", [])}
    rows = []
    for identifier in order:
        deps = nodes[identifier].get("dependencies", [])
        chunks = [deps[i:i + 10] for i in range(0, len(deps), 10)] or [[]]
        for index, chunk in enumerate(chunks):
            suffix = f" · {index + 1}/{len(chunks)}" if len(chunks) > 1 else ""
            rows.append((identifier, chunk, suffix))
    drawn = {(dep, identifier) for identifier, deps, _ in rows for dep in deps}
    shown = {identifier for identifier, _, _ in rows} | {dep for dep, _ in drawn}
    if drawn != expected or shown != scope:
        raise ValueError(f"incomplete {slug}: missing nodes {scope - shown}, edges {expected - drawn}")
    contents = [text(36, 44, title, 30, "600"),
                text(36, 75, f"{len(scope)} native nodes · {len(expected)} declared dependencies · arrows point to the consumer", 16)]
    for i, note in enumerate(notes):
        contents.append(text(36, 107 + i * 23, note, 15))
    y = 140 + len(notes) * 23
    if extra:
        more, size = extra(y)
        contents.extend(more)
        y += size
    for i in range(0, len(rows), 2):
        heights = []
        for col, (identifier, deps, suffix) in enumerate(rows[i:i + 2]):
            pieces, height = panel(nodes, identifier, deps, 36 + col * 710, y, suffix)
            contents.extend(pieces)
            heights.append(height)
        y += max(heights) + 32
    contents += [f'<path d="M 36 {y} H 1404" stroke="#cbd5e1"/>',
                 text(36, y + 28, "TOOL: source or deterministic operation     REASONING: model operator     Green: frozen Lab/Oracle checkpoints", 14),
                 text(36, y + 54, "Repeated cards name the same artifact. Each declared edge appears once; no skip edges are omitted.", 14)]
    height = y + 82
    metadata = {"node_ids": sorted(scope), "edges": sorted(expected), "source_sha256": hashes}
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{height}" '
           f'viewBox="0 0 {WIDTH} {height}" role="img" aria-labelledby="{slug}-title {slug}-desc">\n'
           f'<title id="{slug}-title">{escape(title)}</title>\n'
           f'<desc id="{slug}-desc">{escape(description)}</desc>\n'
           f'<metadata>{escape(json.dumps(metadata, sort_keys=True))}</metadata>\n'
           '<defs><marker id="arrow" markerWidth="7" markerHeight="7" refX="6" refY="3.5" orient="auto">'
           '<path d="M 0 0 L 7 3.5 L 0 7 Z" fill="#64748b"/></marker></defs>\n'
           '<style>text{font-family:Arial,Helvetica,sans-serif}.dependency{fill:none;stroke:#64748b;stroke-width:1.4}'
           '.dependency:hover{stroke:#145b48;stroke-width:3}</style>\n'
           f'<rect width="{WIDTH}" height="{height}" fill="#ffffff"/>\n'
           + "\n".join(contents) + "\n</svg>\n")
    (OUT / f"{slug}.svg").write_text(svg)
    print(f"{slug}: {len(scope)} nodes, {len(expected)} edges, {WIDTH} × {height}")
    return len(scope), len(expected)


def evolve_review(y):
    """Daily workflow is explicitly separate from the authored native DAG."""
    pieces = [text(36, y + 22, "Active daily workflow · reviewed policy candidate, separate from the dossier DAG", 20, "600")]
    stages = [
        ("Paired frozen Lab + Oracle", "make_review_packet / source bindings"),
        ("Pending Evolve handoff", "export_agent_handoff; no inference"),
        ("Agent review → candidate / no_change", "compile_review; frozen policy addon"),
        ("Next development Lab", "daily next consumes the reviewed policy"),
        ("Matched later comparison", "daily matchoff; same inputs, both versions"),
        ("Reviewed retention decision", "daily retain; adoption is explicit"),
    ]
    for i in range(5):
        cy = y + 95 + i * 100
        pieces.append(f'<path d="M 356 {cy} V {cy + 50}" class="dependency" '
                      'stroke-dasharray="5 4" marker-end="url(#arrow)"/>')
    for i, (label, owner) in enumerate(stages):
        cy = y + 45 + i * 100
        pieces += [f'<rect x="36" y="{cy}" width="640" height="50" rx="6" fill="#f8fafc" stroke="#a5afbd"/>',
                   text(50, cy + 21, label, 16, "600"), text(50, cy + 40, owner, 13)]
    pieces += [text(750, y + 85, "Workflow boxes are not native node IDs.", 17, "600"),
               text(750, y + 120, "Review can keep the current policy unchanged.", 16),
               text(750, y + 153, "Candidate use on a development day is not promotion.", 16),
               text(750, y + 186, "An Oracle diagnosis is a hypothesis, not measured gain.", 16),
               text(750, y + 219, "Later matched comparison supports retention decisions.", 16),
               text(36, y + 635, "Native dossier DAG · declared dependencies below; live mutation requires explicit runner application", 20, "600")]
    return pieces, 670


def main():
    nodes, hashes, groups = load_nodes()
    OUT.mkdir(parents=True, exist_ok=True)
    lab_order = ["global_calculator_feed", "lab_seed_state"] + ["lab_miner_" + lane for lane in LANES]
    lab_order += ["lab_cross_corr_v1", "lab_orient", "lab_decide"]
    lab_order += ["lab_miner_v2_" + lane for lane in LANES]
    lab_order += ["lab_cross_corr_v2", "lab_director", "lab_integrity"]
    lab = render("lab", "Lab · full native dependency atlas",
                 "All 28 Lab nodes and their exact prerequisite edges, from six source feeds and CALC through CP1, directed review, CP2 and Integrity.",
                 nodes, hashes, closure(nodes, groups["lab"]), lab_order,
                 ["Six feeds plus CALC → seed → seven miners → Cross / Orient / Decide (CP1) → seven directed miners → Cross / Director (CP2).",
                  "Integrity consumes both phases. Its 20 prerequisites span two continued panels; nothing is omitted.",
                  "Feed content is bound to the issue snapshot by runtime configuration, not by an extra JSON dependency edge."])
    oracle_order = ["global_calculator_feed", "oracle_subject_index", "oracle_truth_diff_equity", "oracle_truth_diff_macro"]
    oracle_order += ["oracle_truth_" + lane for lane in LANES]
    oracle_order += ["oracle_truth_map", "oracle_attribution_map", "oracle_explain", "oracle_cp2_emitter"]
    oracle = render("oracle", "Oracle · full native dependency atlas",
                    "All 31 Oracle nodes and exact prerequisite edges, combining original Lab subject artifacts with later truth evidence while preserving subject-only grounding.",
                    nodes, hashes, closure(nodes, groups["oracle"]), oracle_order,
                    ["Subject mirrors ← original Lab run. Global feed nodes ← later truth snapshot. These are runtime bindings, not graph edges.",
                     "Subject index / numerical diffs → seven lane reviews → Truth map → Attribution / Explain → reconstructed Oracle CP2.",
                     "Oracle CP2 retains original subject eligibility; hindsight and explanation do not create admissible evidence or new targets."])
    evolve = render("evolve", "Evolve · native DAG and reviewed daily workflow",
                    "The three-node native dossier refinement DAG is shown separately from the active daily agent review, candidate testing and explicit retention workflow.",
                    nodes, hashes, closure(nodes, groups["refinement"]),
                    ["delta_analyzer", "dossier_updater", "version_committer"],
                    ["Delta Analyzer receives the paired Lab CP2 and Oracle quartet through runner inputs, not a declared dependency edge.",
                     "Readiness gates block missing or unusable feedback. Exporting a handoff is not completed analysis or an applied patch."], evolve_review)
    (ROOT / "docs/graphs.md").write_text(f"""# Actual graph diagrams

These SVGs are generated from the current native node JSON. Open the linked figure
and zoom to inspect the exact IDs. Each dependency panel shows a produced node and
all its immediate prerequisites. Repeated cards refer to the same artifact; each
declared edge appears once. Integrity's 20 inputs occupy two continued panels.

| View | Native nodes | Declared edges |
|---|---:|---:|
| [Full Lab](graphs/lab.svg) | {lab[0]} | {lab[1]} |
| [Full Oracle](graphs/oracle.svg) | {oracle[0]} | {oracle[1]} |
| [Evolve and daily review](graphs/evolve.svg) | {evolve[0]} | {evolve[1]} |

![Full native Lab dependency atlas](graphs/lab.svg)

![Full native Oracle dependency atlas](graphs/oracle.svg)

![Native Evolve and reviewed daily workflow](graphs/evolve.svg)

Solid arrows are exactly the `dependencies` fields under
`codex/substrate/nodes/{{feeds,lab,oracle,refinement}}`. They describe artifact
consumption, not every injected context item or execution-time source binding.
Lab binds feeds to its issue snapshot. Oracle binds `oracle_subject_*` tools to
the original Lab and `global_*` tools to later truth. Its subject-grounding rules
still govern reconstruction. See `zenith/daily.py::checked_run` and the engine's
tool hydration; the atlas does not invent dependencies for these bindings.

The Evolve figure separates the native dossier DAG from the daily controller's
reviewed policy path. Dashed arrows connect workflow steps, not native nodes.
`run_evolve.py::export_agent_handoff` exports pending analysis with source
bindings. `daily.py::compile_review` freezes a candidate or no-change decision.
The next development Lab may use that candidate; later `daily matchoff` and an
explicit `daily retain` decision govern retention. Neither an Oracle diagnosis
nor a candidate review establishes improvement. Native dossier mutation is a
separate explicit application path.

Regenerate without extra dependencies:

```sh
python3 scripts/build_graphs.py
```

The builder checks full node and edge coverage. Each SVG embeds the exact edge
inventory and SHA-256 hashes of the source node files in its metadata.
""")


if __name__ == "__main__":
    main()
