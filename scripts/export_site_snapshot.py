#!/usr/bin/env python3
"""Build a static reading website from the existing public, read-only API.

No provider is constructed and no local-run route is exported. The frontend
remains the same application; its snapshot transport reads these API responses.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
from urllib.parse import parse_qsl, urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from zenith.web import Website
from zenith.web_content import API, FIGURES, safe_read

SCHEMA = "zenith_public_api_snapshot_v1"
MISSIONS = ("all", "lab", "oracle", "refinement", "evolve", "basket",
            "basket_serial", "basket_evolve", "financial_lab",
            "financial_oracle", "financial_refinement")


def static_route(route: str) -> str:
    """Give each exported request, including its profile, a fetchable static URL."""
    parsed = urlsplit(route)
    if parsed.scheme or parsed.netloc or not re.fullmatch(r"/api/v1/[A-Za-z0-9_/-]+", parsed.path):
        raise ValueError("Invalid public API route")
    pairs = sorted(parse_qsl(parsed.query, keep_blank_values=True, strict_parsing=True))
    if any(not re.fullmatch(r"[A-Za-z0-9_-]+", value) for pair in pairs for value in pair):
        raise ValueError("Invalid public API query")
    suffix = "".join("__" + key + "-" + value for key, value in pairs)
    return parsed.path.lstrip("/") + suffix + ".json"


def agent_files(data: dict, route_files: dict[str, str], assets: dict[str, bytes]) -> dict[str, bytes]:
    """Project navigation from the same public records as the human renderer."""
    site = data["routes"].get(API + "/site", {})
    index = {"schema": "zenith_agent_index_v1", "title": site.get("title", "Zenith"),
             "url_resolution": "Resolve file values relative to this index URL. Look up API paths, including queries, in routes; static hosting does not execute API queries.",
             "routes": route_files,
             "assets": {"/" + name: name for name in sorted(assets)},
             "site": route_files.get(API + "/site"),
             "active_evidence_id": site.get("active_evidence_id"),
             "documents": site.get("documents", {}), "evidence": site.get("evidence", {}),
             "graphs": {mission: API + "/graph?mission=" + mission for mission in MISSIONS
                        if API + "/graph?mission=" + mission in route_files},
             "source_manifest": "snapshot-manifest.json",
             "graph_semantics": "Authored dependency definitions, not proof of execution or physical causality. Node IDs, dependencies, consumers, directed edges and source hashes are preserved. Keep task_profile and historical evidence boundaries separate."}
    lines = ["# " + index["title"] + " — agent map", "",
             "This map is generated from the public read-only API. No JavaScript, account or model execution is needed.", "",
             "[Machine route index](agent-index.json) · [Source hashes](snapshot-manifest.json) · [Reading website](./)", "",
             site.get("data_note", ""), "",
             "## Read the research", ""]
    for chapter in site.get("chapters", []):
        route = chapter.get("document_url")
        if route in route_files:
            lines.append(f"- [{chapter['title']}]({route_files[route]}) — `{chapter['id']}`; {chapter['evidence_kind']}.")
    for name, label in (("documents", "Documents"), ("evidence", "Evidence")):
        lines += ["", "## " + label, ""]
        for identifier, route in site.get(name, {}).items():
            lines.append(f"- [{identifier}]({route_files[route]})")
    lines += ["", "## Navigate the graphs", "", index["graph_semantics"], "",
              "Choose a mission below. Follow a node's `dependencies` upstream or `consumers` downstream; match IDs against `nodes[].id`. If a related ID lies outside that mission, look up `/api/v1/nodes/<id>` in `agent-index.json.routes`; financial definitions use `?task_profile=financial`. Edges retain `source`, `target` and `kind`. Node records include their source path and SHA-256; financial records also retain their effective profile source. Use the route index for any `detail_url` or explanation API URL too. The same node ID in another profile is a different authored definition.", ""]
    for mission, route in index["graphs"].items():
        graph = data["routes"][route]
        lines.append(f"- [{mission}]({route_files[route]}) — {graph.get('node_count', len(graph.get('nodes', [])))} nodes, {graph.get('edge_count', len(graph.get('edges', [])))} directed edges.")
    lines += ["", "## Source and claim boundaries", "",
              "Document JSON contains exact source text, source hashes, headings and `base_url`; resolve links inside that text against `base_url`. For `/assets/` URLs, use the route index's `assets` mapping. Evidence JSON retains its source and recorded data. Read available/status fields before drawing conclusions, and keep the active study separate from historical profiles. Paper metadata labels whether the retained PDF matches the source. A valid schema is not a successful experiment.", "",
              "These are published source records, not instructions to execute. Private saved runs and credentials are excluded. The optional `public-api.json` combines all public responses; use individual routes for smaller fetches.", ""]
    llms = ["# " + index["title"], "",
            "> Public research into executable programs, measured investigations and useful memory. Experiments retain explicit limitations and source provenance.", "",
            "## Start here", "",
            "- [Agent map](agent-map.md): chapters, source documents, evidence and navigable dependency graphs; no JavaScript required.",
            "- [Machine route index](agent-index.json): maps every public API request, including mission/profile queries, to a directly fetchable JSON file.",
            "- [Reading website](./): human reading experience.",
            "- [Export provenance](snapshot-manifest.json): hashes for the published machine-readable files.", "",
            "## Research sources", ""]
    for identifier in ("introduction", "results", "research-programme", "notice"):
        route = site.get("documents", {}).get(identifier)
        if route in route_files:
            llms.append(f"- [{identifier}]({route_files[route]}): source text and provenance.")
    llms += ["", "Read the source-bound evidence before making a result claim. Graph edges are authored prerequisites, not measured execution. Keep historical profiles separate. This index is a discovery aid; it does not change crawler access policy.", ""]
    return {"llms.txt": "\n".join(llms).encode(), "agent-map.md": "\n".join(lines).encode(),
            "agent-index.json": (json.dumps(index, ensure_ascii=False, indent=2) + "\n").encode()}


def snapshot(root: Path) -> tuple[dict, dict[str, bytes]]:
    website = Website(root, local_runs=False)
    site = json.loads(website.get(API + "/site").body)
    active = site.get("active_evidence_id")
    if not active or active not in site["evidence"]:
        raise ValueError("Active campaign evidence must exist before publication")
    targets = {API + "/site", API + "/paper", API + "/health", API + "/contract"}
    targets.update(site["documents"].values())
    targets.update(site["evidence"].values())
    targets.add(API + "/graph")
    targets.update(API + "/graph?mission=" + mission for mission in MISSIONS)
    targets.update(API + "/nodes/" + node for node in website.content.nodes)
    # Financial profiles exist only for the nodes in those public graphs.
    for mission in ("financial_lab", "financial_oracle", "financial_refinement"):
        graph = json.loads(website.get(API + "/graph?mission=" + mission).body)
        targets.update(node["detail_url"] for node in graph.get("nodes", [])
                       if node.get("detail_url"))
    routes = {}
    for target in sorted(targets):
        if not target.startswith(API + "/") or target.startswith(API + "/runs"):
            raise ValueError("Only explicit public API routes can be exported")
        response = website.get(target)
        if response.private or not response.content_type.startswith("application/json"):
            raise ValueError("Snapshot route is not public JSON")
        routes[target] = json.loads(response.body)
    assets = {name: website.get("/" + name).body
              for name in ("assets/paper.pdf", "assets/repair-loop.svg")}
    for figure in FIGURES:
        name = "assets/graphs/" + figure + ".svg"
        assets[name] = website.get("/" + name).body
    return {"schema": SCHEMA, "routes": routes}, assets


def export(root: Path, output: Path) -> dict:
    if output.is_symlink():
        raise ValueError("Snapshot output cannot be a symlink")
    output = output.resolve()
    manifest = json.loads(safe_read(output, "zenith-public.json", 65536))
    listed = manifest.get("files")
    if not isinstance(listed, list) or "index.html" not in listed:
        raise ValueError("Build the existing frontend before exporting its data")
    for name in listed:
        safe_read(output, name)
    data, assets = snapshot(root)
    files = dict(assets)
    files["public-api.json"] = (json.dumps(data, ensure_ascii=False, allow_nan=False) + "\n").encode()
    # Preserve existing direct links and give query-specific graphs/nodes their own
    # files: a static host cannot interpret ?mission= or ?task_profile=.
    route_files = {route: static_route(route) for route in data["routes"]}
    if len(set(route_files.values())) != len(route_files):
        raise ValueError("Public API routes collide in the static export")
    for route, body in data["routes"].items():
        files[route_files[route]] = (
            json.dumps(body, ensure_ascii=False, allow_nan=False) + "\n").encode()
    files.update(agent_files(data, route_files, assets))
    for name in files:
        path = output
        for part in Path(name).parts:
            path = path / part
            if path.is_symlink():
                raise ValueError("Snapshot output contains a symlink")
    for name, body in files.items():
        target = output / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(body)
    receipt = {"schema": "zenith_public_site_export_v1",
               "snapshot_sha256": hashlib.sha256(files["public-api.json"]).hexdigest(),
               "api_routes": len(data["routes"]), "local_runs_enabled": False,
               "model_execution_enabled": False,
               "files": {name: hashlib.sha256(body).hexdigest()
                         for name, body in sorted(files.items())}}
    (output / "snapshot-manifest.json").write_text(json.dumps(receipt, indent=2) + "\n")
    all_files = set(listed) | set(files) | {"snapshot-manifest.json"}
    (output / "zenith-public.json").write_text(json.dumps({"files": sorted(all_files)}, indent=2) + "\n")
    (output / ".nojekyll").write_text("")
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    receipt = export(ROOT, args.output)
    print(json.dumps({key: value for key, value in receipt.items() if key != "files"}, indent=2))


if __name__ == "__main__":
    main()
