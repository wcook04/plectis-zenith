"""Static publication reuses the public API and cannot expose local runs."""
import json
from pathlib import Path

import pytest

from scripts import export_site_snapshot as publisher


def test_snapshot_uses_exact_public_responses_and_excludes_runs(monkeypatch):
    calls = []
    class Response:
        private = False
        content_type = "application/json"
        def __init__(self, data):
            self.body = json.dumps(data).encode()
    class Website:
        def __init__(self, root, *, local_runs):
            assert local_runs is False
            self.content = type("Content", (), {"nodes": ["node"]})()
        def get(self, target):
            calls.append(target)
            if target.endswith("/site"):
                return Response({"active_evidence_id": "current", "documents": {},
                                 "evidence": {"current": "/api/v1/evidence/current"}})
            if "mission=financial" in target:
                return Response({"nodes": [{"detail_url": "/api/v1/nodes/node?task_profile=financial"}]})
            return Response({"target": target})
    monkeypatch.setattr(publisher, "Website", Website)
    data, assets = publisher.snapshot(Path("unused"))
    assert data["routes"]["/api/v1/evidence/current"] == {"target": "/api/v1/evidence/current"}
    assert "/api/v1/nodes/node?task_profile=financial" in data["routes"]
    assert not any("/runs" in path for path in calls)
    assert "assets/paper.pdf" in assets


def test_export_keeps_assets_and_downloadable_source_but_rejects_symlink(tmp_path, monkeypatch):
    (tmp_path / "index.html").write_text("existing frontend")
    (tmp_path / "zenith-public.json").write_text(json.dumps({"files": ["index.html"]}))
    data = {"schema": publisher.SCHEMA, "routes": {"/api/v1/paper": {"title": "draft"}}}
    monkeypatch.setattr(publisher, "snapshot", lambda root: (data, {"assets/paper.pdf": b"pdf"}))
    receipt = publisher.export(tmp_path, tmp_path)
    assert receipt["api_routes"] == 1 and not receipt["local_runs_enabled"]
    assert json.loads((tmp_path / "agent-index.json").read_text())["assets"] == {"/assets/paper.pdf": "assets/paper.pdf"}
    assert json.loads((tmp_path / "api/v1/paper.json").read_text()) == {"title": "draft"}
    assert (tmp_path / "index.html").read_text() == "existing frontend"
    (tmp_path / "public-api.json").unlink()
    (tmp_path / "public-api.json").symlink_to(tmp_path / "index.html")
    with pytest.raises((ValueError, FileNotFoundError)):
        publisher.export(tmp_path, tmp_path)


def test_agent_navigation_preserves_graph_profiles_sources_and_direct_fetches(tmp_path, monkeypatch):
    (tmp_path / "index.html").write_text("existing frontend")
    (tmp_path / "zenith-public.json").write_text(json.dumps({"files": ["index.html"]}))
    source = {"path": "codex/substrate/nodes/lab/node.json", "sha256": "frozen-source"}
    graph_route = "/api/v1/graph?mission=financial_lab"
    node_route = "/api/v1/nodes/node?task_profile=financial"
    graph = {"nodes": [{"id": "node", "dependencies": ["input"], "consumers": [],
                        "detail_url": node_route, "source": source}],
             "edges": [{"id": "input->node", "source": "input", "target": "node", "kind": "declared_dependency"}],
             "task_profile": "financial"}
    site = {"title": "Source-bound research", "active_evidence_id": "current",
            "documents": {"notice": "/api/v1/documents/notice"},
            "evidence": {"current": "/api/v1/evidence/current"},
            "chapters": [{"id": "idea", "title": "Idea", "evidence_kind": "authored_mechanism",
                          "document_url": "/api/v1/documents/notice"}]}
    routes = {"/api/v1/site": site, graph_route: graph, node_route: graph["nodes"][0],
              "/api/v1/documents/notice": {"content": "Research limits", "source": source},
              "/api/v1/evidence/current": {"source": source, "data": {"status": "incomplete"}}}
    monkeypatch.setattr(publisher, "snapshot", lambda root: ({"schema": publisher.SCHEMA, "routes": routes}, {}))
    receipt = publisher.export(tmp_path, tmp_path)
    index = json.loads((tmp_path / "agent-index.json").read_text())
    assert index["active_evidence_id"] == "current"
    for route, value in routes.items():
        path = index["routes"][route]
        assert "?" not in path
        assert json.loads((tmp_path / path).read_text()) == value
        assert path in receipt["files"]
    for name in ["llms.txt", "agent-map.md", "agent-index.json"]:
        assert name in receipt["files"]
    assert "financial_lab" in (tmp_path / "agent-map.md").read_text()
    assert "not proof of execution" in (tmp_path / "agent-map.md").read_text()
    assert (tmp_path / "index.html").read_text() == "existing frontend"


@pytest.mark.parametrize("route", ["/api/v1/../private", "/api/v1/graph?mission=../../private",
                                  "https://example.com/api/v1/site", "/api/v1/graph?mission="])
def test_static_route_rejects_unsafe_output_names(route):
    with pytest.raises(ValueError):
        publisher.static_route(route)
