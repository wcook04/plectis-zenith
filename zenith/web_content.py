"""Read models for a teaching website, backed by the manuscript and native graph."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from . import runtime
from .paper_reading import diagram_source, paper_reading

API = "/api/v1"
# Reviewed source/PDF and TikZ/SVG pairs. Update after compiling and visual inspection.
PAPER_EDITION = {"source_sha256": "b15077b01d5345ea75f6d7c6ba528030554dd5d05192f96be28e5b4d5ad0b788", "pdf_sha256": "2d87ccc5007d4b023f537f25950ce04c34aaeae5ef5d288e017fe5c7e9e27d52", "figure_source_sha256": "c905bebf5be49a93d0c3ee4e8f0a4865a4bbc5cd9a1e7c47c68a7f7227adc2fe", "figure_sha256": "e63032ffa13264806412e13626fd8d00d1d60a2bbe6d28584b00e435fada5e92"}
DOCUMENTS = {
    "introduction": "README.md",
    "paper": "paper/zenith.tex",
    "architecture": "docs/architecture.md",
    "historical-architecture": "docs/history/architecture.md",
    "graphs": "docs/history/graphs.md",
    "results": "docs/status.md",
    "experiment": "docs/history/baskets.md",
    "synthetic-fixture": "docs/history/demo.md",
    "data": "docs/history/data.md",
    "diagnosis": "docs/history/failure-diagnosis.md",
    "reasoning-ontology": "docs/history/reasoning-ontology.md",
    "investigator": "docs/history/investigator.md",
    "executable-investigations": "docs/history/executable-investigations.md",
    "observation-learning": "docs/history/executable-investigations.md",
    "decomposition-study": "docs/history/decomposition-study.md",
    "decomposition-results": "docs/history/decomposition-20261014.md",
    "conformance-study": "docs/studies/native/conformance-study.md",
    "continuation-memory": "docs/history/continuation-memory.md",
    "advance-synthesis": "docs/history/advance-returns-20261014.md",
    "progress-synthesis": "docs/history/progress-returns-20261014.md",
    "progress-results": "docs/studies/native/progress-campaign-20261014.md",
    "continuation-learner": "examples/continuation-memory/witness-preserving-v1/README.md",
    "client-investigation-protocol": "docs/client-investigation-protocol-20261014.md",
    "client-investigation": "docs/studies/client/client-investigation-20261014.md",
    "client-investigation-protocol-v2": "docs/client-investigation-protocol-v2-20261015.md",
    "client-investigation-v2": "docs/studies/client/client-investigation-v2-20261015.md",
    "client-investigation-v2-low": "docs/studies/client/client-investigation-v2-low-20261015.md",
    "research-programme": "program.md",
    "model-repair": "docs/history/model-repair-20261013.md",
    "worked-case": "docs/history/full-graph-case.md",
    "research-direction": "program.md",
    "walkthrough": "docs/history/zenith-walkthrough-script.md",
    "notice": "RESEARCH_NOTICE.md",
}
EVIDENCE = {
    "progress-campaign": "docs/studies/native/progress-campaign-20261014.json",
    "client-investigation": "examples/conformance/client-reuse-v1/report.json",
    "client-investigation-v2": "examples/conformance/client-reuse-v2/report.json",
    "client-investigation-v2-low": "examples/conformance/client-reuse-v2-low/report.json",
    "advance-campaign": "docs/history/advance-campaign-20261014.json",
    "decomposition-result": "docs/history/decomposition-20261014.json",
    "observation-learning-result": "docs/history/observation-learning-20261013.json",
    "observation-screens": "docs/history/observation-screens-20261013.json",
    "investigation-learning-result": "docs/history/investigation-learning-20261013.json",
    "investigator-result": "docs/history/investigator-evidence.json",
    "model-repair-result": "docs/history/model-repair-20261013.json",
    "sources": "examples/demo/provenance.json",
    "replacements": "examples/demo/replacements.json",
    "demo-result": "examples/demo/result.json",
    "basket-result": "examples/baskets/result.json",
    "basket-trace": "examples/baskets/trace.json",
    "basket-repair": "examples/baskets/repair.json",
    "basket-protocol": "examples/baskets/protocol.json",
    "full-graph-result": "examples/full-graph/result.json",
    "full-graph-trace": "examples/full-graph/trace.json",
    "reasoning-schemas": "examples/full-graph/reasoning-schemas.json",
    "experiment-reasoning-schemas": "examples/full-graph/experiment-reasoning-schemas.json",
    "full-graph-protocol": "examples/full-graph/protocol.json",
    "full-graph-history": "examples/full-graph/development-history.json",
    "full-graph-followups": "examples/full-graph/followups.json",
    "full-graph-manifest": "examples/full-graph/manifest.json",
}
FIGURES = ("replay", "lab", "oracle", "evolve", "lab-detail", "oracle-detail", "evolve-detail", "basket-detail", "basket-serial-detail", "investigator-detail")
CHAPTERS = (
    ("idea", "The idea", "introduction", None, None, "authored_mechanism"),
    ("lab", "Choose inputs to test the software", "conformance-study", None, None, "authored_mechanism"),
    ("oracle", "Compare repaired programs with reference software", "conformance-study", None, None, "authored_mechanism"),
    ("evolve", "Remember earlier actions to predict later answers", "continuation-learner", None, None, "authored_mechanism"),
    ("results", "Current experiments and their limits", "progress-results", None, None, "measured_execution"),
    ("next", "What still needs testing", "research-programme", None, None, "research_proposal"),
)
CHAPTER_EVIDENCE = {
    "idea": (), "lab": (), "oracle": ("progress-campaign",), "evolve": ("progress-campaign",),
    "results": ("progress-campaign",), "next": (),
}
PAPER_SECTIONS = {"idea": "idea", "lab": "lab", "oracle": "oracle",
                  "evolve": "evolve", "results": "results", "next": "research"}


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def safe_read(root: Path, relative: str, limit: int = 8 * 1024 * 1024) -> bytes:
    """Only callers' allowlisted paths; never follow symlinks, even in parents."""
    parts = Path(relative).parts
    if not parts or Path(relative).is_absolute() or any(p in (".", "..") for p in parts):
        raise FileNotFoundError("Unknown resource")
    current = root
    for part in parts:
        current = current / part
        if current.is_symlink():
            raise FileNotFoundError("Unknown resource")
    if not current.is_file():
        raise FileNotFoundError("Unknown resource")
    with current.open("rb") as stream:
        data = stream.read(limit + 1)
    if len(data) > limit:
        raise ValueError("Resource exceeds the read limit")
    return data


REFERENCE_PATH = "paper/references.json"
CITE = re.compile(r"\\cite(?:\[([^\]]*)\])?\{([^}]+)\}")
BIBLIOGRAPHY = re.compile(r"\\begin\{thebibliography\}\{\d+\}.*?\\end\{thebibliography\}", re.S)


def reviewed_references(root: Path) -> tuple[list[dict], bytes]:
    """Read portable source-edition records, not the private annex source bodies."""
    raw = safe_read(root, REFERENCE_PATH)
    data = json.loads(raw)
    if data.get("schema") != "zenith_reviewed_references_v1":
        raise ValueError("Unknown reviewed-reference schema")
    records = data.get("sources", [])
    keys = [record["id"] for record in records]
    if not keys or len(set(keys)) != len(keys):
        raise ValueError("Reviewed references need unique bibliography keys")
    for record in records:
        for field in ("id", "title", "author_label", "venue", "year_label", "url", "application"):
            if not isinstance(record.get(field), str) or not record[field].strip():
                raise ValueError(f"Reference {record['id']} lacks {field}")
        source = record["reviewed_source"]
        if not re.fullmatch(r"[0-9a-f]{64}", source.get("sha256", "")) or not source.get("edition"):
            raise ValueError(f"Reference {record['id']} lacks an exact reviewed edition")
        if not record["url"].startswith("https://") or record.get("verification_state") != "source_verified":
            raise ValueError(f"Reference {record['id']} lacks source verification")
        locators = record.get("source_locators", [])
        ids = [locator["id"] for locator in locators]
        if not ids or len(set(ids)) != len(ids) or not record.get("artifact_links"):
            raise ValueError(f"Reference {record['id']} lacks unique locators or manuscript bindings")
        if any(not locator.get(field) for locator in locators for field in ("locator", "supports", "boundary")):
            raise ValueError(f"Reference {record['id']} has incomplete source support")
    return records, raw


def reference_bibliography(records: list[dict]) -> str:
    """One bibliography projection from the reviewed metadata."""
    def tex(value: str) -> str:
        return re.sub(r"([&#%_{}])", r"\\\1", value)

    lines = [f"\\begin{{thebibliography}}{{{len(records)}}}\\footnotesize",
             r"\setlength{\itemsep}{0pt}\setlength{\parskip}{0pt}"]
    for record in records:
        lines.append(r"\bibitem{" + record["id"] + "} " + tex(record["author_label"].rstrip(".")) + ". "
                     + r"\href{" + record["url"] + "}{" + tex(record["title"]) + "}. "
                     + tex(record["venue"]) + ", " + tex(record["year_label"]) + ".")
    return "\n".join([*lines, r"\end{thebibliography}"])


def paper_citations(root: Path, tex: str) -> tuple[list[dict], bytes]:
    """Bind every citation to a reviewed edition and unchanged supporting passage.

    This checks custody and review coverage; hashes do not certify source claims.
    The supported TeX surface is the manuscript's inline bibliography and \\cite.
    """
    records, raw = reviewed_references(root)
    bibliographies = list(BIBLIOGRAPHY.finditer(tex))
    if len(bibliographies) != 1 or bibliographies[0][0] != reference_bibliography(records):
        raise ValueError("Bibliography differs from reviewed metadata; run scripts/build_paper_references.py")
    prose = tex[:bibliographies[0].start()]
    # Ignore commented citations while retaining original line coordinates.
    visible = re.sub(r"(?<!\\)%[^\n]*", lambda match: " " * len(match[0]), prose)
    all_uses = list(CITE.finditer(visible))
    known = {record["id"] for record in records}
    for use in all_uses:
        if set(key.strip() for key in use[2].split(",")) - known:
            raise ValueError(f"Unknown bibliography key: {use[2]}")
    bodies = {match[1]: match[2].strip() for match in re.finditer(
        r"\\bibitem\{([^}]+)\}(.*?)(?=\\bibitem|\\end\{thebibliography\})", tex, re.S)}
    citations = []
    for record in records:
        key = record["id"]
        uses = [use for use in all_uses if key in [value.strip() for value in use[2].split(",")]]
        if not uses:
            raise ValueError(f"Unused reviewed reference: {key}")
        ranges = []
        locator_ids = {locator["id"] for locator in record["source_locators"]}
        for binding in record["artifact_links"]:
            excerpt = binding.get("expected_text", "")
            if (binding.get("path") != "paper/zenith.tex" or not excerpt
                    or prose.count(excerpt) != 1 or digest(excerpt.encode()) != binding.get("excerpt_sha256")):
                raise ValueError(f"Stale manuscript binding for {key}")
            support = binding.get("source_locator_ids", [])
            if not support or set(support) - locator_ids:
                raise ValueError(f"Unknown source support for {key}")
            first = prose.index(excerpt)
            ranges.append((first, first + len(excerpt)))
        used = []
        for use in uses:
            line = visible[:use.start()].count("\n") + 1
            if not any(first <= use.start() and use.end() <= last for first, last in ranges):
                raise ValueError(f"Unreviewed citation use for {key} at line {line}")
            used.append({"line": line, "locator": use[1] or None})
        citations.append({"id": key, "latex": bodies[key], "urls": [record["url"]],
                          "used_at": used, "review": record})
    return citations, raw


class PublicContent:
    def __init__(self, root: Path):
        self.root = Path(root).resolve()
        self.nodes = runtime.load_graph(self.root)
        self.sources = {}
        for path in sorted((self.root / "codex/substrate/nodes").glob("*/*.json")):
            raw = safe_read(self.root, path.relative_to(self.root).as_posix())
            source = json.loads(raw)
            if source.get("id") in self.nodes:
                self.sources[source["id"]] = (path.relative_to(self.root).as_posix(), raw, source)
        if set(self.sources) != set(self.nodes):
            raise ValueError("Native nodes lack source bindings")
        self.plans = {name: runtime.plan(self.root, name) for name in ("lab", "oracle", "refinement", "basket", "basket_serial", "basket_evolve")}

    def source(self, path: str, data: bytes) -> dict:
        return {"path": path, "sha256": digest(data),
                "url": f"https://github.com/wcook04/plectis-zenith/blob/main/{path}"}

    def document(self, identifier: str) -> dict:
        if identifier not in DOCUMENTS:
            raise FileNotFoundError("Unknown document")
        path = DOCUMENTS[identifier]
        raw = safe_read(self.root, path)
        content = raw.decode("utf-8")
        headings = [{"level": len(m[1]), "title": m[2], "line": content[:m.start()].count("\n") + 1}
                    for m in re.finditer(r"^(#{1,6}) (.+)$", content, re.M)]
        return {"id": identifier, "format": "latex" if path.endswith(".tex") else "markdown",
                "content": content, "headings": headings, "source": self.source(path, raw),
                "base_url": self.source(path, raw)["url"].rsplit("/", 1)[0] + "/"}

    def paper(self) -> dict:
        source = self.document("paper")
        tex = source["content"]
        title = re.search(r"\\Large\\bfseries\s+([^}\n]+)", tex)
        citations, references_raw = paper_citations(self.root, tex)
        pdf = safe_read(self.root, "paper/zenith.pdf")
        figure = safe_read(self.root, "paper/repair-loop.svg")
        if (digest(figure) != PAPER_EDITION.get("figure_sha256") or
                digest(diagram_source(tex).encode()) != PAPER_EDITION.get("figure_source_sha256")):
            raise ValueError("The paper diagram differs from the reviewed source/SVG pair")
        current_pdf = (source["source"]["sha256"] == PAPER_EDITION["source_sha256"]
                       and digest(pdf) == PAPER_EDITION["pdf_sha256"])
        anchors = list(re.finditer(r"\\hypertarget\{([a-z-]+)\}\{\}", tex))
        sections = []
        for index, anchor in enumerate(anchors):
            end = anchors[index + 1].start() if index + 1 < len(anchors) else len(tex)
            start_line = tex[:anchor.start()].count("\n") + 1
            end_line = tex[:end].count("\n")
            sections.append({"id": anchor[1], "start_line": start_line, "end_line": end_line,
                             "source": source["source"],
                             "source_url": source["source"]["url"] + f"#L{start_line}",
                             "pdf_url": "/assets/paper.pdf#nameddest=" + anchor[1],
                             "citation_ids": [c["id"] for c in citations
                                              if any(start_line <= u["line"] <= end_line for u in c["used_at"])]})
        return {"title": title[1] if title else "Zenith", "source": source["source"],
                "source_url": f"{API}/documents/paper", "pdf_url": "/assets/paper.pdf",
                "pdf_sha256": digest(pdf), "citations": citations, "sections": sections,
                "references_source": self.source(REFERENCE_PATH, references_raw),
                "reading": paper_reading(tex, [record["id"] for record in citations]),
                "figure_source": self.source("paper/repair-loop.svg", figure),
                "pdf_current": current_pdf,
                "pdf_edition": "reviewed_current_source" if current_pdf else "retained_previous_edition",
                "pdf_note": ("The PDF and manuscript match the pair compiled and visually reviewed on 15 October 2026."
                             if current_pdf else "The PDF or manuscript differs from the reviewed pair; use the current source."),
                "notice_url": f"{API}/documents/notice"}

    def node(self, identifier: str, task_profile: str = "generic") -> dict:
        if identifier not in self.nodes:
            raise FileNotFoundError("Unknown node")
        if task_profile=="financial":
            group=self.nodes[identifier].group
            if group not in {"lab","oracle","refinement","feeds"}:raise ValueError("Node has no financial profile")
            mission="lab" if group=="feeds" else group
            return next(n for n in self.graph("financial_"+mission)["nodes"] if n["id"]==identifier)
        if task_profile!="generic":raise ValueError("Unknown task profile")
        node = self.nodes[identifier]
        path, raw, authored = self.sources[identifier]
        consumers = sorted(n.id for n in self.nodes.values() if identifier in n.dependencies)
        demo = self.evidence("sources")["data"]
        provenance = next((lane for snapshot in demo["snapshots"] if snapshot["id"] == "earlier"
                           for lane in snapshot["lanes"] if lane["node_id"] == identifier), None)
        dossier = None
        perspective = node.lane.lower()
        if not node.group.startswith("basket") and perspective in {"measurements", "subsystems", "environment", "events", "interventions", "derived"}:
            dossier_path = f"codex/substrate/dossiers/{perspective}.json"
            dossier_raw = safe_read(self.root, dossier_path)
            dossier = {"data": json.loads(dossier_raw), "source": self.source(dossier_path, dossier_raw)}
        return {"id": node.id, "type": node.type.value, "group": node.group, "lane": node.lane,
                "purpose": node.teleology, "mechanism": node.mechanism, "expectation": node.expectation,
                "boundary": authored.get("boundary", ""), "instruction": node.instruction,
                "instruction_kind": "current_authored_definition_not_run_override",
                "dependencies": list(node.dependencies), "consumers": consumers,
                "demo_provenance": provenance, "dossier": dossier,
                "output_schema": node.output_schema, "source": self.source(path, raw),
                "explanation_url": f"{API}/documents/experiment" if node.group.startswith("basket") else f"{API}/documents/graphs"}

    def graph(self, mission: str = "all", focus: str | None = None) -> dict:
        if mission.startswith("financial_"):
            underlying=mission.removeprefix("financial_")
            if underlying not in {"lab","oracle","refinement"}: raise ValueError("unknown financial mission")
            answer=self.graph(underlying,focus)
            financial=runtime.load_graph(self.root,task_profile="financial")
            from .financial_reasoning import schema_for
            for row in answer["nodes"]:
                node=financial[row["id"]]
                from system.lib.hashing import hash_node
                row["effective_node_hash"]=hash_node(node)
                row["task_profile"]="financial"
                row["instruction"]=node.instruction
                row["output_schema"]=node.output_schema
                row["dossier"]=None;row["demo_provenance"]=None
                row["explanation_url"]=f"{API}/documents/reasoning-ontology"
                row["detail_url"]=f"{API}/nodes/{node.id}?task_profile=financial"
                row["profile_source"]=self.source("zenith/market_graph.py",safe_read(self.root,"zenith/market_graph.py"))
                row["instruction_kind"]="effective_financial_definition_not_run_override"
                if node.type.value=="reasoning":
                    from .financial_reasoning import stage_for
                    row["purpose"]="Financial reasoning stage: "+stage_for(node.id)
                    row["expectation"]="Validated reasoning record with the attached stage-specific JSON Schema."
                if node.type.value=="reasoning": row["reasoning_schema"]=schema_for(node.id,persisted=True)
            selected={n["id"] for n in answer["nodes"]}
            edges=[{"id":f"{dep}->{nid}","source":dep,"target":nid,"kind":"declared_dependency"}
                   for nid in sorted(selected) for dep in financial[nid].dependencies if dep in selected]
            for row in answer["nodes"]:
                row["dependencies"]=list(financial[row["id"]].dependencies)
                row["consumers"]=sorted(n for n in selected if row["id"] in financial[n].dependencies)
            def reachable(reverse):
                seen=set();todo=[focus] if focus else []
                while todo:
                    current=todo.pop()
                    for edge in edges:
                        before,after=(edge["target"],edge["source"]) if reverse else (edge["source"],edge["target"])
                        if before==current and after not in seen:seen.add(after);todo.append(after)
                return sorted(seen)
            from system.core.governance import compute_waves
            answer.update(edges=edges,edge_count=len(edges),waves=compute_waves({n:financial[n] for n in selected}),
                          focus={"id":focus,"ancestors":reachable(True),"descendants":reachable(False)})
            answer.update(mission=mission,task_profile="financial",profile_source="zenith/market_graph.py")
            return answer
        if mission == "evolve":
            mission = "refinement"
        if mission == "all":
            from system.core.governance import compute_waves
            ids, waves = set(self.nodes), compute_waves(self.nodes)
        elif mission in self.plans:
            plan = self.plans[mission]
            ids = {n["id"] for n in plan["nodes"]}
            waves = plan["waves"]
        else:
            raise ValueError("Mission must be all, lab, oracle or refinement")
        if focus and focus not in ids:
            raise ValueError("Focus node does not belong to the selected graph")
        edges = [{"id": f"{dep}->{identifier}", "source": dep, "target": identifier,
                  "kind": "declared_dependency"} for identifier in sorted(ids)
                 for dep in self.nodes[identifier].dependencies if dep in ids]
        def traverse(reverse: bool) -> list[str]:
            seen, todo = set(), [focus] if focus else []
            while todo:
                item = todo.pop()
                for edge in edges:
                    before, after = (edge["target"], edge["source"]) if reverse else (edge["source"], edge["target"])
                    if before == item and after not in seen:
                        seen.add(after); todo.append(after)
            return sorted(seen)
        return {"schema": "zenith_web_graph_v1", "mission": mission,
                "nodes": [self.node(identifier) for identifier in sorted(ids)], "edges": edges,
                "waves": waves, "node_count": len(ids), "edge_count": len(edges),
                "focus": {"id": focus, "ancestors": traverse(True), "descendants": traverse(False)},
                "semantics": "Edges are authored prerequisites. Saved-run states and runtime feed hydration are separate evidence.",
                "definition_loaded_at_startup": True}

    def evidence(self, identifier: str) -> dict:
        if identifier not in EVIDENCE:
            raise FileNotFoundError("Unknown evidence")
        path = EVIDENCE[identifier]
        raw = safe_read(self.root, path)
        return {"id": identifier, "source": self.source(path, raw), "data": json.loads(raw)}

    def site(self, local_runs: bool) -> dict:
        chapters = []
        current_available = (self.root / EVIDENCE["progress-campaign"]).is_file()
        paper = self.paper()
        sections = {section["id"]: section for section in paper["sections"]}
        for identifier, title, document, figure, mission, kind in CHAPTERS:
            if identifier == "results":
                # Analysis completion does not certify construction, protected
                # outcomes or learning success for every constituent study.
                kind = "measured_execution" if current_available else "research_proposal"
            available = (self.root / DOCUMENTS[document]).is_file()
            chapters.append({"id": identifier, "title": title, "evidence_kind": kind,
                             "document_url": f"{API}/documents/{document}" if available else None,
                             "available": available, "figure_url": f"/assets/graphs/{figure}.svg" if figure else None,
                             "graph_url": f"{API}/graph?mission={mission}" if mission else None,
                             "paper_section": sections.get(PAPER_SECTIONS[identifier]),
                             "evidence_urls": [f"{API}/evidence/{name}" for name in CHAPTER_EVIDENCE[identifier] if (self.root/EVIDENCE[name]).is_file()]})
        return {"schema": "zenith_teaching_site_v1", "api_version": "1",
                "title": paper["title"], "paper_url": f"{API}/paper", "chapters": chapters,
                "notice": "Experimental research prototype.", "notice_url": f"{API}/documents/notice",
                "documents": {k: f"{API}/documents/{k}" for k, v in DOCUMENTS.items() if (self.root / v).is_file()},
                "figures": {k: f"/assets/graphs/{k}.svg" for k in FIGURES},
                "evidence": {k: f"{API}/evidence/{k}" for k,v in EVIDENCE.items() if (self.root / v).is_file()},
                "active_evidence_id": "progress-campaign",
                "data_mode": "source_bound_acquisition_research",
                "data_note": "The software-repair experiment, database-tester pilot and separate memory learner answer different questions; their scores are reported separately. Earlier experiments and program versions remain available with their original results and limits.",
                "local_runs_enabled": local_runs,
                "run_index_url": f"{API}/runs" if local_runs else None,
                "capabilities": {"read_graph": True, "read_paper": True, "read_local_runs": local_runs,
                                 "execute_model": False, "mutate_graph": False},
                "rendering": "No coordinates or components are prescribed. Use native waves, lanes and directed edges; preserve source and evidence labels."}
