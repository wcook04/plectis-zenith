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
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from zenith.web import Website
from zenith.web_content import API, FIGURES, safe_read

SCHEMA = "zenith_public_api_snapshot_v1"
MISSIONS = ("all", "lab", "oracle", "refinement", "evolve", "basket",
            "basket_serial", "basket_evolve", "financial_lab",
            "financial_oracle", "financial_refinement")


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
    assets = {"assets/paper.pdf": website.get("/assets/paper.pdf").body}
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
    # Direct source/evidence links remain downloadable in a static deployment.
    for route, body in data["routes"].items():
        if "?" not in route:
            files[route.lstrip("/") + ".json"] = (
                json.dumps(body, ensure_ascii=False, allow_nan=False) + "\n").encode()
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
