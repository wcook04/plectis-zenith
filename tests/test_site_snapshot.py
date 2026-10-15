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
    assert json.loads((tmp_path / "api/v1/paper.json").read_text()) == {"title": "draft"}
    assert (tmp_path / "index.html").read_text() == "existing frontend"
    (tmp_path / "public-api.json").unlink()
    (tmp_path / "public-api.json").symlink_to(tmp_path / "index.html")
    with pytest.raises((ValueError, FileNotFoundError)):
        publisher.export(tmp_path, tmp_path)
