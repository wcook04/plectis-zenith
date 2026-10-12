#!/usr/bin/env python3
"""Render readable overviews and exact dependency drilldowns using stdlib SVG."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from xml.sax.saxutils import escape, quoteattr

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "graphs"
LANES = ("measurements", "subsystems", "environment", "events", "interventions", "derived")
WIDTH = 1440
CARD = 302
STEP = 66
RESEARCH_NOTICE = "Research prototype. Synthetic demonstration."


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
                 text(36, y + 54, "Repeated cards name the same artifact. Each declared edge appears once; no skip edges are omitted.", 14),
                 text(36, y + 80, RESEARCH_NOTICE, 14, color="#64748b")]
    height = y + 106
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



def path(d, arrow=True, dashed=False, endpoint=None):
    pieces = [f'<path d="{d}" class="{"dashed" if dashed else "flow"}"/>']
    if arrow:
        if endpoint is None:
            tokens = iter(re.findall(r"[MHV]|-?\d+", d))
            x = y = 0
            previous = None
            for command in tokens:
                previous = (x, y)
                if command == "M":
                    x, y = int(next(tokens)), int(next(tokens))
                elif command == "H":
                    x = int(next(tokens))
                elif command == "V":
                    y = int(next(tokens))
            if previous is None or previous == (x, y):
                raise ValueError(f"arrow needs a final segment: {d}")
            px, py = previous
            direction = "right" if x > px else "left" if x < px else "down" if y > py else "up"
        else:
            x, y, direction = endpoint
        if direction == "right":
            points = [(x - 8, y - 5), (x, y), (x - 8, y + 5)]
        elif direction == "left":
            points = [(x + 8, y - 5), (x, y), (x + 8, y + 5)]
        elif direction == "down":
            points = [(x - 5, y - 8), (x, y), (x + 5, y - 8)]
        elif direction == "up":
            points = [(x - 5, y + 8), (x, y), (x + 5, y + 8)]
        else:
            raise ValueError(f"invalid arrow direction: {direction}")
        coordinates = " ".join(f"{a},{b}" for a, b in points)
        pieces.append(f'<polygon points="{coordinates}" fill="{"#64748b" if dashed else "#527b6c"}"/>')
    return "".join(pieces)


def box(x, y, width, height, label, subtitle, accent=False, fill=None,
        label_size=17, sub_size=13):
    fill = fill or ("#e6f3ef" if accent else "#f5f7f9")
    return [f'<rect x="{x}" y="{y}" width="{width}" height="{height}" rx="7" '
            f'fill="{fill}" stroke="#80958f"/>',
            text(x + 12, y + 22 if height < 60 else y + 35, label, label_size, "600"),
            text(x + 12, y + 40 if height < 60 else y + 59, subtitle, sub_size)]


def overview(slug, title, description, nodes, hashes, scope, stages, notes, workflow=None):
    """A selected spine of real dependencies; every omitted edge is inventoried."""
    owners = {identifier: index for index, (_, _, ids) in enumerate(stages) for identifier in ids}
    if set(owners) != scope or sum(len(ids) for _, _, ids in stages) != len(scope):
        raise ValueError(f"overview groups do not partition {slug}")
    expected = {(dep, identifier) for identifier in scope for dep in nodes[identifier].get("dependencies", [])}
    represented = set()
    for index in range(len(stages) - 1):
        edges = {(a, b) for a, b in expected if owners[a] == index and owners[b] == index + 1}
        if not edges:
            raise ValueError(f"invented overview edge in {slug} at {index}")
        represented.update(edges)
    body = [text(32, 44, title, 29, "600"), text(32, 78, description, 17)]
    if slug == "lab":
        width, height = 1040, 720
        headings = [(36, "SAVED INPUTS"), (240, "FIRST PASS"), (445, "CP1"),
                    (645, "DIRECTED PASS"), (845, "CP2 + CHECK")]
        body += [text(x, 125, label, 13, "600", "#64748b") for x, label in headings]
        labels = ("Measurements", "Subsystems", "Environment", "Events", "Interventions", "DERIVED")
        for i, label in enumerate(labels):
            cy = 169 + i * 65
            body += [path(f"M 206 {cy + 24} H 240"),
                     path(f"M 408 {cy + 24} H 425", arrow=False),
                     path(f"M 625 {cy + 24} H 645"),
                     path(f"M 813 {cy + 24} H 825", arrow=False)]
        body += [path("M 425 193 V 518", arrow=False), path("M 425 388 H 445"),
                 path("M 605 388 H 625", arrow=False), path("M 625 193 V 518", arrow=False),
                 path("M 825 193 V 518", arrow=False), path("M 825 388 H 845"),
                 path("M 925 438 V 605")]
        for i, label in enumerate(labels):
            y = 169 + i * 65
            body += box(36, y, 170, 48, label, "source feed" if label != "DERIVED" else "derived tool")
            body += box(240, y, 168, 48, label, "read observations")
            body += box(645, y, 168, 48, label, "audit CP1 + feed")
        body += box(445, 338, 160, 100, "Cross → Orient", "Decide · CP1", True, label_size=16)
        body += [text(457, 416, "quantiles frozen", 12),
                 text(457, 430, "(quantile branch)", 11)]
        body += box(845, 338, 160, 100, "Cross → Director", "frozen CP2", True, label_size=16)
        body += box(845, 605, 160, 58, "Integrity", "checks both passes")
        body += [text(36, 693, "Seed state initializes pass 1. Source feeds also enter pass 2; exact direct and skip edges are in Lab detail.", 14)]
    elif slug == "oracle":
        width, height = 1040, 715
        for x, label in [(36, "ORIGINAL LAB SUBJECT"), (234, "LATER TRUTH FEED"),
                         (460, "SIX LANE REVIEWS"), (710, "SYNTHESIS")]:
            body.append(text(x, 125, label, 13, "600", "#64748b"))
        labels = ("Measurements", "Subsystems", "Environment", "Events", "Interventions", "DERIVED")
        for i, label in enumerate(labels):
            cy = 169 + i * 65
            body += [path(f"M 206 {cy + 24} H 210 Q 218 {cy + 24} 218 {cy + 16} "
                          f"V {cy - 1} Q 218 {cy - 9} 226 {cy - 9} H 544 "
                          f"Q 552 {cy - 9} 552 {cy - 1} V {cy}",
                          endpoint=(552, cy, "down")),
                     path(f"M 404 {cy + 32} H 460"),
                     path(f"M 645 {cy + 24} H 680", arrow=False)]
        body += [path("M 680 193 V 518", arrow=False), path("M 680 388 H 710"),
                 path("M 835 388 H 870"), path("M 790 442 V 506"),
                 path("M 835 556 H 862 Q 870 556 870 548 V 438", endpoint=(870, 438, "up"))]
        for i, label in enumerate(labels):
            y = 169 + i * 65
            body += box(36, y, 170, 48, label, "frozen subject")
            body += box(234, y, 170, 48, label, "later evidence")
            body += box(460, y, 185, 48, label, "truth review")
        body += box(710, 338, 125, 104, "Truth map", "reviews + diffs", True)
        body += box(870, 338, 135, 100, "Oracle CP2", "original targets", True)
        body += box(710, 506, 125, 50, "Attribution", "and Explain")
        body += [text(36, 677, "Subject index and numerical diffs also feed synthesis; CP2 keeps original target eligibility.", 14),
                 text(36, 699, "Source mirrors bind to the original Lab; later feeds bind to truth time. Exact edges are in Oracle detail.", 14)]
    else:
        width, height = 1040, 585
        body += [text(36, 128, "NATIVE DOSSIER DAG", 14, "600", "#64748b"),
                 text(36, 329, "DAILY REVIEW WORKFLOW · conceptual controller steps", 14, "600", "#64748b")]
        for x in (305, 655):
            body.append(path(f"M {x} 205 H {x + 35}"))
        body += box(36, 160, 269, 90, "Delta Analyzer", "paired Lab / Oracle runner inputs")
        body += box(340, 160, 315, 90, "Dossier Updater", "proposed instruction / context change")
        body += box(690, 160, 315, 90, "Version Committer", "explicit runner application", True)
        flow = [(36, "Paired feedback", "freeze source bindings"),
                (235, "Agent review", "candidate or no_change"),
                (434, "Development Lab", "try reviewed candidate"),
                (633, "Matched comparison", "same later inputs"),
                (832, "Retention review", "explicit decision")]
        for i, (x, label, sub) in enumerate(flow):
            if i < 4:
                body.append(path(f"M {x + 174} 405 H {flow[i + 1][0]} ", dashed=True))
            body += box(x, 355, 174, 100, label, sub, fill="#fffaf0", label_size=16, sub_size=13)
        body += [path("M 322 455 V 480", dashed=True),
                 text(414, 344, "candidate path", 12, color="#64748b")]
        body += box(235, 480, 245, 60, "No change", "keep current policy", fill="#fffaf0", label_size=16)
        body += [text(36, 565, "A diagnosis or reviewed candidate is not forecast gain; later matched evidence informs retention.", 14)]
    body.append(text(36, height + 6, RESEARCH_NOTICE, 14, color="#64748b"))
    height += 28
    if slug == "lab":
        represented = set()
        for lane in LANES:
            first, second = "lab_miner_" + lane, "lab_miner_v2_" + lane
            source = next(dep for dep in nodes[first]["dependencies"] if dep.startswith("global_"))
            represented.update({(source, first), (first, "lab_cross_corr_v1"),
                                ("lab_decide", second), (second, "lab_cross_corr_v2")})
        represented.add(("lab_director", "lab_integrity"))
    elif slug == "oracle":
        represented = set()
        for lane in LANES:
            reviewer = "oracle_truth_" + lane
            source = next(dep for dep in nodes[reviewer]["dependencies"] if dep.startswith("global_"))
            represented.update({("oracle_subject_" + lane + "_feed", reviewer),
                                (source, reviewer), (reviewer, "oracle_truth_map")})
        represented.update({("oracle_truth_map", "oracle_attribution_map"),
                            ("oracle_truth_map", "oracle_cp2_emitter"),
                            ("oracle_attribution_map", "oracle_cp2_emitter"),
                            ("oracle_explain", "oracle_cp2_emitter")})
    if not represented <= expected:
        raise ValueError(f"overview {slug} draws a nonexistent dependency")
    metadata = {"node_ids": sorted(scope), "edges": sorted(expected), "source_sha256": hashes,
                "groups": [ids for _, _, ids in stages], "represented_edges": sorted(represented),
                "detail_only_edges": sorted(expected - represented)}
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="{slug}-title {slug}-desc">'
           f'<title id="{slug}-title">{escape(title)}</title><desc id="{slug}-desc">{escape(description)} Grouped overview: skip and internal edges are in the exact detail diagram.</desc>'
           f'<metadata>{escape(json.dumps(metadata, sort_keys=True))}</metadata>'
           '<defs><marker id="arrow" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto"><path d="M0 0 L8 3 L0 6 Z" fill="#527b6c"/></marker></defs>'
           '<style>text{font-family:Arial,Helvetica,sans-serif}.flow{stroke:#527b6c;stroke-width:1.8;fill:none}.dashed{stroke:#64748b;stroke-width:1.7;stroke-dasharray:5 4;fill:none}</style>'
           f'<rect width="{width}" height="{height}" fill="white"/>' + "\n".join(body) + '</svg>\n')
    (OUT / f"{slug}.svg").write_text(svg)


def replay(hashes):
    """The intended saved-snapshot workflow, separate from native DAG edges."""
    width, height = 1040, 574
    boxes = [
        (36, 160, 270, "Earlier saved feeds", "Five sources + summaries", "#f5f7f9"),
        (36, 280, 270, "Full Lab", "Two passes → CP1 and CP2", "#f5f7f9"),
        (36, 400, 270, "Frozen Lab CP2", "Selections and forecasts", "#e6f3ef"),
        (385, 160, 270, "Later saved feeds", "Five sources + summaries", "#f5f7f9"),
        (385, 400, 270, "Oracle", "Measured errors + diagnosis", "#f5f7f9"),
        (734, 280, 270, "Evolve review", "Candidate or no_change", "#fffaf0"),
        (734, 400, 270, "Matched comparison", "Old/new on same further inputs", "#fffaf0"),
    ]
    body = [text(32, 44, "Saved-snapshot replay · intended workflow", 29, "600"),
            text(32, 76, "Synthetic System A: measurements, subsystems, context, events, interventions and derived summaries.", 17),
            text(32, 105, "Current synthetic example: inputs loaded; first reasoning request prepared; no forecast yet.", 15),
            text(36, 142, "EARLIER · ISSUE TIME", 13, "600", "#64748b"),
            text(385, 142, "LATER · TRUTH TIME", 13, "600", "#64748b"),
            text(734, 142, "CHANGE · FURTHER TEST", 13, "600", "#64748b")]
    paths = [
        ("M 171 240 V 280", None), ("M 171 360 V 400", None),
        ("M 306 440 H 385", None), ("M 520 240 V 400", None),
        ("M 655 440 H 676 Q 684 440 684 432 V 328 Q 684 320 692 320 H 734", (734, 320, "right")),
        ("M 869 360 V 400", None),
    ]
    body += [path(route, endpoint=end) for route, end in paths]
    for x, y, box_width, label, subtitle, fill in boxes:
        body += [f'<rect x="{x}" y="{y}" width="{box_width}" height="80" rx="8" fill="{fill}" stroke="#80958f"/>',
                 text(x + 16, y + 32, label, 19, "600"), text(x + 16, y + 59, subtitle, 14)]
    body.append(text(36, 518, "Oracle explains the frozen forecast against later truth; only a separate matched comparison can assess a reviewed change.", 14))
    body.append(text(36, 552, RESEARCH_NOTICE, 14, color="#64748b"))
    metadata = {"kind": "conceptual_workflow", "source_sha256": hashes,
                "recorded_limit": "first Lab run stopped at cross-correlation without a forecast"}
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
           f'viewBox="0 0 {width} {height}" role="img" aria-labelledby="replay-title replay-desc">'
           '<title id="replay-title">Saved-snapshot replay workflow</title>'
           '<desc id="replay-desc">An intended workflow from original earlier feeds through Lab and frozen CP2, then later feeds and Oracle diagnosis, Evolve review, and a later matched comparison. The current example stops at preparation of the first reasoning request.</desc>'
           f'<metadata>{escape(json.dumps(metadata, sort_keys=True))}</metadata>'
           '<defs><marker id="replay-arrow" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto"><path d="M0 0 L8 3 L0 6 Z" fill="#527b6c"/></marker></defs>'
           '<style>text{font-family:Arial,Helvetica,sans-serif}.flow{stroke:#527b6c;stroke-width:2;fill:none}</style>'
           f'<rect width="{width}" height="{height}" fill="white"/>' + "\n".join(body) + '</svg>\n')
    (OUT / "replay.svg").write_text(svg)


def main():
    nodes, hashes, groups = load_nodes()
    OUT.mkdir(parents=True, exist_ok=True)
    lab_order = ["global_derived_feed", "lab_seed_state"] + ["lab_miner_" + lane for lane in LANES]
    lab_order += ["lab_cross_corr_v1", "lab_orient", "lab_decide"]
    lab_order += ["lab_miner_v2_" + lane for lane in LANES]
    lab_order += ["lab_cross_corr_v2", "lab_director", "lab_integrity"]
    lab = render("lab-detail", "Lab · full native dependency atlas",
                 "All 25 Lab nodes and their exact prerequisite edges, from five source feeds and DERIVED through CP1, directed review, CP2 and Integrity.",
                 nodes, hashes, closure(nodes, groups["lab"]), lab_order,
                 ["Five feeds plus DERIVED → seed → six miners → Cross / Orient / Decide (CP1) → six directed miners → Cross / Director (CP2).",
                  "Integrity consumes both phases. Its 18 prerequisites span two continued panels; nothing is omitted.",
                  "Feed content is bound to the issue snapshot by runtime configuration, not by an extra JSON dependency edge."])
    oracle_order = ["global_derived_feed", "oracle_subject_index", "oracle_truth_diff_observations", "oracle_truth_diff_environment"]
    oracle_order += ["oracle_truth_" + lane for lane in LANES]
    oracle_order += ["oracle_truth_map", "oracle_attribution_map", "oracle_explain", "oracle_cp2_emitter"]
    oracle = render("oracle-detail", "Oracle · full native dependency atlas",
                    "All 28 Oracle nodes and exact prerequisite edges, combining original Lab subject artifacts with later truth evidence while preserving subject-only grounding.",
                    nodes, hashes, closure(nodes, groups["oracle"]), oracle_order,
                    ["Subject mirrors ← original Lab run. Global feed nodes ← later truth snapshot. These are runtime bindings, not graph edges.",
                     "Subject index / numerical diffs → six lane reviews → Truth map → Attribution / Explain → reconstructed Oracle CP2.",
                     "Oracle CP2 retains original subject eligibility; hindsight and explanation do not create admissible evidence or new targets."])
    evolve = render("evolve-detail", "Evolve · native DAG and reviewed daily workflow",
                    "The three-node native dossier refinement DAG is shown separately from the active daily agent review, candidate testing and explicit retention workflow.",
                    nodes, hashes, closure(nodes, groups["refinement"]),
                    ["delta_analyzer", "dossier_updater", "version_committer"],
                    ["Delta Analyzer receives the paired Lab CP2 and Oracle quartet through runner inputs, not a declared dependency edge.",
                     "Readiness gates block missing or unusable feedback. Exporting a handoff is not completed analysis or an applied patch."], evolve_review)
    feeds = groups["feeds"]
    overview("lab", "Lab · evidence to frozen predictions", "Five source feeds + derived DERIVED; two passes of model reasoning.", nodes, hashes,
             closure(nodes, groups["lab"]), [
        ("TOOLS · five feeds + DERIVED", "Measurements · Subsystems · environment · events · interventions", feeds),
        ("Seed state", "Set the starting context from the available evidence.", ["lab_seed_state"]),
        ("Six miners · first pass", "One reasoning operator per feed or derived lane.", ["lab_miner_" + lane for lane in LANES]),
        ("Cross → Orient → Decide · CP1", "Combine lane reports; freeze the first decision checkpoint.", ["lab_cross_corr_v1", "lab_orient", "lab_decide"]),
        ("Six directed miners · second pass", "Revisit each lane using CP1 and its source feed.", ["lab_miner_v2_" + lane for lane in LANES]),
        ("Cross → Director · CP2", "Combine directed reports; freeze selections and forecasts.", ["lab_cross_corr_v2", "lab_director"]),
        ("Integrity", "Check the seed and artifacts from both reasoning passes.", ["lab_integrity"]),
    ], ["Solid arrows: real dependencies between groups; internal and skip edges are in detail.",
        "Summaries derive from measurements, subsystems and context. Source feeds also enter both miner passes.",
        "Issue-time feed hydration is a runtime binding, not an extra native graph edge."])
    subjects = [i for i in groups["oracle"] if i.startswith("oracle_subject_") and i != "oracle_subject_index"]
    overview("oracle", "Oracle · frozen forecast meets later evidence", "Original Lab artifacts and later truth remain distinct runtime inputs.", nodes, hashes,
             closure(nodes, groups["oracle"]), [
        ("TOOLS · subject mirrors | later truth feeds + DERIVED", "Original Lab decisions and evidence | later outcome snapshot", subjects + feeds),
        ("TOOLS · subject index + numerical diffs", "Recover forecast targets; compare observations with later values.", ["oracle_subject_index", "oracle_truth_diff_observations", "oracle_truth_diff_environment"]),
        ("Six lane reviews", "Reason over the original subject and each lane’s later evidence.", ["oracle_truth_" + lane for lane in LANES]),
        ("Truth map", "Combine lane reviews and measured differences.", ["oracle_truth_map"]),
        ("Attribution → Explain", "Propose an account of what happened and why.", ["oracle_attribution_map", "oracle_explain"]),
        ("Oracle CP2", "Reconstruct the checkpoint under original subject eligibility.", ["oracle_cp2_emitter"]),
    ], ["Solid arrows: real dependencies between groups; direct source and skip edges are in detail.",
        "Subject mirrors bind to the original Lab; global feeds bind to the later truth snapshot.",
        "Explanation is a hypothesis. Hindsight does not create new admissible targets."])
    overview("evolve", "Evolve · propose, test, then review retention", "The native dossier DAG and the daily policy workflow are separate paths.", nodes, hashes,
             closure(nodes, groups["refinement"]), [
        ("Delta Analyzer", "Reason over supplied Lab / Oracle feedback.", ["delta_analyzer"]),
        ("Dossier Updater", "Propose changes to the reasoning dossier.", ["dossier_updater"]),
        ("TOOL · Version Committer", "Explicit runner application owns mutation.", ["version_committer"]),
    ], ["Solid arrows: the three-node native dossier DAG. Dashed arrows: daily workflow steps.",
        "Paired Lab CP2 and Oracle feedback enter through runner inputs, not native edges.",
        "A reviewed candidate is not an improvement; later matched evidence informs retention."], [
        ("Paired Lab + Oracle", "Freeze source bindings"),
        ("Agent review", "Candidate policy or no_change"),
        ("Development Lab", "Try the reviewed candidate"),
        ("Later matched comparison", "Same inputs, both versions"),
        ("Retention review", "Record an explicit decision"),
    ])
    replay(hashes)
    (ROOT / "docs/graphs.md").write_text(f"""# Actual graph diagrams

> **Experimental research prototype.** The example uses invented observations.
> See the [research notice](../RESEARCH_NOTICE.md).

The [saved-snapshot replay](graphs/replay.svg) shows the intended workflow.
The current example uses five invented perspectives on System A. A sixth feed
computes summaries from those observations; it is not independent evidence.
It has prepared the first reasoning request, with no forecast yet.
See [current status](status.md) and [per-feed provenance](../examples/demo/provenance.json).
SVG metadata hashes the node definitions used to draw the graphs.

![Replay workflow: earlier saved feeds and DERIVED through Lab and frozen CP2; later feeds through Oracle diagnosis, Evolve review and a later matched comparison](graphs/replay.svg)

Read the three columns from issue time to truth time to a further test. The
earlier saved feeds enter Lab; its CP2 forecast is frozen before the later feeds
can be read. Oracle compares that fixed subject with later truth. Evolve can
propose a reviewed candidate, which still needs a matched comparison on further
inputs.

The grouped views below open those stages into their native operators.

![Lab: five feeds and DERIVED through two reasoning passes, CP1, CP2 and Integrity](graphs/lab.svg)

Follow one row: the saved MEASUREMENTS table enters the measurements miner, which reports
observations with source references. Cross-correlation joins all six miner
reports; Orient weighs them; Decide freezes CP1, including numerical forecast
estimates with declared units and horizons. The directed measurements miner then checks that
thesis against CP1 and the earlier measurements feed. The second Cross and Director
assemble CP2; Integrity checks artifacts from both passes. The second pass
does not refit CP1's frozen estimates.

![Oracle: original Lab subjects and later evidence through truth reviews to Oracle CP2](graphs/oracle.svg)

Oracle reads the original Lab reasoning beside the later saved feeds. Code
computes numerical observation and context differences; the six lane reviews inspect
later evidence against the original subject. Truth map combines the reviews and
differences, then Attribution and Explain propose a diagnosis. Oracle CP2 keeps
the original subject targets and citation eligibility. A diagnosis is a
hypothesis about an outcome, not a new prediction or proof of improvement.

![Evolve: native dossier changes beside the separate reviewed daily policy workflow](graphs/evolve.svg)

The upper row is the native Delta Analyzer → Dossier Updater → Version Committer
dependency path. Paired Lab and Oracle records enter through runner inputs;
mutation requires explicit application. The lower dashed path is the daily
controller: a handoff, agent review, candidate or no-change decision, development
Lab, later matched comparison and explicit retention review. A candidate is not
promoted by being proposed.

The compact Lab and Oracle figures draw the lane inputs and the main merges.
They group CP1's internal Cross / Orient / Decide chain, CP2's Cross / Director
chain, and Oracle's Attribution / Explain chain. Direct feed reuse, subject-index
inputs and other skip edges are left to the exact views below. A shared bus
means that the named lane outputs enter a downstream consumer; it does not mean
that every box in one column connects to every box in another. Derived summaries use
the measurements, subsystem and context feeds.

| Exact dependency view | Native nodes | Declared edges |
|---|---:|---:|
| [Lab detail](graphs/lab-detail.svg) | {lab[0]} | {lab[1]} |
| [Oracle detail](graphs/oracle-detail.svg) | {oracle[0]} | {oracle[1]} |
| [Evolve detail](graphs/evolve-detail.svg) | {evolve[0]} | {evolve[1]} |

In each detail diagram, repeated cards name the same artifact and every declared
edge appears once. Integrity's 20 inputs occupy two continued panels.

Dependencies live under `codex/substrate/nodes/{{feeds,lab,oracle,refinement}}`.
Runtime hydration is separate: Lab binds global feeds to the issue snapshot;
Oracle binds subject mirrors to the original Lab and global feeds to later
truth. Those bindings do not add native dependency edges. Oracle CP2 preserves
original subject eligibility; explanations cannot admit new targets.

In that controller, `export_agent_handoff` exports pending analysis and
`compile_review` freezes a candidate or no-change decision. `daily matchoff`
compares old and new versions on the same later inputs; `daily retain` records
the reviewed retention decision.

Regenerate all seven figures without extra dependencies:

```sh
python3 scripts/build_graphs.py
```

The builder checks full node and edge coverage in the details and verifies that
overview groups partition the same nodes. Overview metadata records represented
and omitted edges. Native-graph SVGs embed node hashes and exact inventories;
the replay SVG identifies its conceptual workflow and node hashes.
""")


if __name__ == "__main__":
    main()
