"""HTTP and publication boundaries for the website, without provider execution."""
import hashlib
import http.client
import json
import threading
from pathlib import Path

import pytest

from zenith.web import Website, make_server
from zenith.web_runs import RunStore

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def website():
    return Website(ROOT)


@pytest.fixture
def server(website):
    instance = make_server(website, port=0)
    worker = threading.Thread(target=instance.serve_forever, daemon=True)
    worker.start()
    yield instance
    instance.shutdown(); instance.server_close(); worker.join(timeout=2)


def request(server, path, method="GET", headers=None):
    connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)
    connection.request(method, path, headers=headers or {})
    response = connection.getresponse()
    result = response.status, dict(response.getheaders()), response.read()
    connection.close()
    return result


def test_native_scopes_sources_and_focus(website):
    for mission, count, edges in (("lab", 25, 86), ("oracle", 28, 53), ("evolve", 3, 2)):
        graph = json.loads(website.get(f"/api/v1/graph?mission={mission}").body)
        assert (graph["node_count"], graph["edge_count"]) == (count, edges)
        ids = {node["id"] for node in graph["nodes"]}
        assert {node for wave in graph["waves"] for node in wave} == ids
        assert all(edge["source"] in ids and edge["target"] in ids for edge in graph["edges"])
    graph = json.loads(website.get("/api/v1/graph?mission=lab&focus=lab_cross_corr_v1").body)
    assert "global_stock_feed" in graph["focus"]["ancestors"]
    assert "lab_integrity" in graph["focus"]["descendants"]
    node = json.loads(website.get("/api/v1/nodes/lab_cross_corr_v1").body)
    assert node["source"]["sha256"] == hashlib.sha256((ROOT / node["source"]["path"]).read_bytes()).hexdigest()
    assert node["instruction_kind"] == "current_authored_definition_not_run_override"


def test_teaching_material_uses_current_sources(website):
    site = json.loads(website.get("/api/v1/site").body)
    assert [chapter["id"] for chapter in site["chapters"]] == ["idea", "lab", "oracle", "evolve", "results", "next"]
    assert next(c for c in site["chapters"] if c["id"] == "results")["evidence_kind"] == "verified_preparation"
    for url in site["documents"].values():
        doc = json.loads(website.get(url).body)
        assert doc["content"] == (ROOT / doc["source"]["path"]).read_text()
    paper = json.loads(website.get(site["paper_url"]).body)
    assert paper["pdf_sha256"] == hashlib.sha256((ROOT / "paper/zenith.pdf").read_bytes()).hexdigest()
    assert {c["id"] for c in paper["citations"]} >= {"alphago", "autores", "scores"}
    assert all(c["used_at"] for c in paper["citations"])
    for chapter in site["chapters"]:
        section = chapter["paper_section"]
        assert section and section["source"]["sha256"] == paper["source"]["sha256"]
        assert section["end_line"] >= section["start_line"]
        assert section["pdf_url"].endswith("#nameddest=" + section["id"])
        assert all(website.get(url).body for url in chapter["evidence_urls"])
    results = next(c for c in site["chapters"] if c["id"] == "results")
    assert set(results["evidence_urls"]) == {"/api/v1/evidence/demo-result"}
    assert "demo" in results["paper_section"]["citation_ids"]
    for url in site["evidence"].values():
        evidence = json.loads(website.get(url).body)
        assert evidence["data"] == json.loads((ROOT / evidence["source"]["path"]).read_text())
    assert site["capabilities"]["execute_model"] is False


@pytest.mark.parametrize("path", ["/api/v1/graph", "/api/v1/nodes/lab_director",
                                  "/api/v1/evidence/replacements", "/api/v1/evidence/demo-result"])
def test_standalone_api_output_retains_research_notice(website, path):
    value = json.loads(website.get(path).body)
    assert value["notice"] == "This is not financial advice."
    notice = json.loads(website.get(value["notice_url"]).body)
    assert notice["content"] == (ROOT / "RESEARCH_NOTICE.md").read_text()
    if path in ("/api/v1/graph", "/api/v1/nodes/lab_director"):
        assert value["content_kind"].startswith("authored_research_definition")


def test_public_http_head_etag_and_private_exclusion(server):
    status, headers, pdf = request(server, "/assets/paper.pdf")
    assert status == 200 and pdf.startswith(b"%PDF")
    assert request(server, "/assets/paper.pdf", "HEAD")[2] == b""
    assert request(server, "/assets/paper.pdf", headers={"If-None-Match": headers["ETag"]})[0] == 304
    assert request(server, "/api/v1/runs")[0] == 404
    assert request(server, "/api/v1/runs/REAL_JUL20_LAB_20261012/nodes/lab_decide")[0] == 404
    assert request(server, "/api/v1/graph", "POST")[0] == 405


@pytest.mark.parametrize("path,status", [
    ("/api/v1/graph?mission=unknown", 400),
    ("/api/v1/graph?mission=lab&mission=oracle", 400),
    ("/api/v1/graph?path=.env", 400),
    ("/api/v1/graph?mission=lab&focus=oracle_truth_map", 400),
    ("/api/v1/documents/../../.env", 400),
    ("/api/v1/documents/%2e%2e%2f.env", 400),
    ("/state/runs/REAL_JUL20_LAB_20261012/run_summary.json", 404),
    ("/api/v1/documents/master_config", 404),
])
def test_invalid_routes_and_no_arbitrary_file_access(server, path, status):
    assert request(server, path)[0] == status


def test_local_run_boundary_and_failure_evidence(tmp_path):
    run = tmp_path / "runs" / "EXAMPLE.1"
    (run / "artifacts").mkdir(parents=True)
    (run / "run_summary.json").write_text(json.dumps({"node_outcomes": {"lab_cross_corr_v1": "failure"}}))
    (run / "zenith_run.json").write_text('{"mission":"lab"}')
    (run / "artifacts/lab_cross_corr_v1.json").write_text('{"status":"failure","metadata":{"error":"JSON_PARSE_ERROR","api_key":"do not expose"},"data":null}')
    local = Website(ROOT, local_runs=True)
    local.runs = RunStore(tmp_path / "runs", set(local.content.nodes))
    with pytest.raises(ValueError):
        make_server(local, host="0.0.0.0", port=0)
    with pytest.raises(ValueError):
        make_server(local, port=0, allow_origins=("https://example.com",))
    server = make_server(local, port=0, allow_origins=("http://localhost:5173",))
    worker = threading.Thread(target=server.serve_forever, daemon=True); worker.start()
    try:
        endpoint = "/api/v1/runs/EXAMPLE.1/nodes/lab_cross_corr_v1"
        status, headers, body = request(server, endpoint)
        assert status == 200 and headers["Cache-Control"] == "no-store" and "ETag" not in headers
        assert json.loads(body)["status"] == "failure" and b"do not expose" not in body
        assert request(server, endpoint, headers={"Host": "attacker.example"})[0] == 403
        assert request(server, endpoint, headers={"Origin": "https://attacker.example"})[0] == 403
        good = request(server, endpoint, headers={"Origin": "http://localhost:5173"})
        assert good[0] == 200 and good[1]["Access-Control-Allow-Origin"] == "http://localhost:5173"
    finally:
        server.shutdown(); server.server_close(); worker.join(timeout=2)


def test_future_frontend_build_can_mount_without_exposing_sources(tmp_path):
    (tmp_path / "index.html").write_text("<html>Frontend owner's build</html>")
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets/site.js").write_text("// public bundle")
    (tmp_path / "zenith-public.json").write_text(json.dumps({"files": ["index.html", "assets/site.js"]}))
    (tmp_path / "unrelated.json").write_text('{"private":"do not serve"}')
    (tmp_path / "unrelated.html").write_text("do not serve")
    (tmp_path / ".env").write_text("SECRET=no")
    (tmp_path / "secret.json").symlink_to(ROOT / "master_config.json")
    app = Website(ROOT, frontend_dir=tmp_path)
    assert b"Frontend owner" in app.get("/").body
    assert app.get("/assets/site.js").body == b"// public bundle"
    assert app.get("/learn/lab").body == app.get("/").body
    for path in ("/.env", "/secret.json", "/unrelated.json", "/unrelated.html", "/zenith-public.json", "/api/v1/unknown", "/assets/graphs/unknown.svg"):
        with pytest.raises(FileNotFoundError):
            app.get(path)
    (tmp_path / "assets/site.js").unlink()
    (tmp_path / "assets/site.js").symlink_to(ROOT / "master_config.json")
    with pytest.raises(FileNotFoundError):
        app.get("/assets/site.js")


@pytest.mark.parametrize("files", [["index.html", "../private.json"], ["index.html", ".env"], [], "index.html"])
def test_invalid_frontend_manifest_rejected(tmp_path, files):
    (tmp_path / "index.html").write_text("<html>Build</html>")
    (tmp_path / "zenith-public.json").write_text(json.dumps({"files": files}))
    with pytest.raises(ValueError):
        Website(ROOT, frontend_dir=tmp_path)
