"""Read models for a teaching website, backed by the manuscript and native graph."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from . import runtime

API = "/api/v1"
DOCUMENTS = {
    "introduction": "README.md",
    "paper": "paper/zenith.tex",
    "architecture": "docs/architecture.md",
    "graphs": "docs/graphs.md",
    "results": "docs/status.md",
    "experiment": "docs/baskets.md",
    "synthetic-fixture": "docs/demo.md",
    "data": "docs/data.md",
    "diagnosis": "docs/failure-diagnosis.md",
    "reasoning-ontology": "docs/reasoning-ontology.md",
    "investigator": "docs/investigator.md",
    "executable-investigations": "docs/executable-investigations.md",
    "observation-learning": "docs/executable-investigations.md",
    "decomposition-study": "docs/decomposition-study.md",
    "decomposition-results": "docs/decomposition-20261014.md",
    "research-programme": "program.md",
    "model-repair": "docs/model-repair-20261013.md",
    "worked-case": "docs/full-graph-case.md",
    "research-direction": "docs/research-direction.md",
    "walkthrough": "docs/zenith-walkthrough-script.md",
    "notice": "RESEARCH_NOTICE.md",
}
EVIDENCE = {
    "decomposition-result": "docs/decomposition-20261014.json",
    "observation-learning-result": "docs/observation-learning-20261013.json",
    "observation-screens": "docs/observation-screens-20261013.json",
    "investigation-learning-result": "docs/investigation-learning-20261013.json",
    "investigator-result": "docs/investigator-evidence.json",
    "model-repair-result": "docs/model-repair-20261013.json",
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
    ("lab", "Observe a native source", "observation-learning", None, None, "authored_mechanism"),
    ("oracle", "Measure success and failure", "observation-learning", None, None, "authored_mechanism"),
    ("evolve", "Revise the computation", "observation-learning", None, None, "authored_mechanism"),
    ("results", "Study and measured results", "results", None, None, "measured_experiment"),
    ("next", "What still needs testing", "research-direction", None, None, "research_proposal"),
)
CHAPTER_EVIDENCE = {
    "idea": (), "lab": (), "oracle": ("observation-learning-result",), "evolve": ("observation-learning-result",),
    "results": ("observation-learning-result", "decomposition-result"), "next": (),
}
PAPER_SECTIONS = {"idea": "idea", "lab": "lab", "oracle": "oracle",
                  "evolve": "trace", "results": "results", "next": "research"}


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
        citations = []
        for match in re.finditer(r"\\bibitem\{([^}]+)\}(.*?)(?=\\bibitem|\\end\{thebibliography\})", tex, re.S):
            key, body = match[1], match[2].strip()
            used = []
            for cite in re.finditer(r"\\cite\{([^}]+)\}", tex):
                if key in [v.strip() for v in cite[1].split(",")]:
                    used.append({"line": tex[:cite.start()].count("\n") + 1})
            citations.append({"id": key, "latex": body,
                              "urls": re.findall(r"\\(?:url|href)\{([^}]+)\}", body), "used_at": used})
        pdf = safe_read(self.root, "paper/zenith.pdf")
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
        observation = (self.evidence("observation-learning-result")["data"]
                       if (self.root / EVIDENCE["observation-learning-result"]).is_file() else None)
        paper = self.paper()
        sections = {section["id"]: section for section in paper["sections"]}
        for identifier, title, document, figure, mission, kind in CHAPTERS:
            if identifier == "results":
                complete = (observation is not None and observation.get("complete") is True
                            and observation.get("status") == "complete" and observation.get("aggregate") is not None)
                kind = "measured_experiment" if complete else "measured_execution" if observation is not None else "research_proposal"
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
                "active_evidence_id": "observation-learning-result",
                "data_mode": "native_observation_research",
                "data_note": "Constructed action sequences produce actual native SQLite observations. Frozen compositions test source-specific programs under a bounded identification family. Operational latency studies, financial studies and System A remain historical profiles.",
                "local_runs_enabled": local_runs,
                "run_index_url": f"{API}/runs" if local_runs else None,
                "capabilities": {"read_graph": True, "read_paper": True, "read_local_runs": local_runs,
                                 "execute_model": False, "mutate_graph": False},
                "rendering": "No coordinates or components are prescribed. Use native waves, lanes and directed edges; preserve source and evidence labels."}
