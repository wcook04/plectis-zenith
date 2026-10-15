"""Read-only website API and optional frontend build host. No inference routes."""
from __future__ import annotations

import ipaddress
import json
import mimetypes
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

from .web_content import API, DOCUMENTS, EVIDENCE, FIGURES, PublicContent, digest, safe_read
from .web_runs import RunStore


@dataclass
class Response:
    body: bytes
    content_type: str = "application/json; charset=utf-8"
    private: bool = False


def json_response(value: dict, private: bool = False) -> Response:
    value = {**value, "notice": "Experimental research prototype.",
             "notice_url": f"{API}/documents/notice"}
    return Response(json.dumps(value, ensure_ascii=False, allow_nan=False).encode(), private=private)


def loopback(host: str) -> bool:
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host.strip("[]")).is_loopback
    except ValueError:
        return False


class Website:
    def __init__(self, root: Path, *, local_runs: bool = False, frontend_dir: Path | None = None):
        self.content = PublicContent(root)
        self.root = self.content.root
        self.local_runs = local_runs
        self.frontend_dir = Path(frontend_dir).resolve() if frontend_dir else None
        self.frontend_files: set[str] = set()
        if self.frontend_dir:
            manifest = json.loads(safe_read(self.frontend_dir, "zenith-public.json", 65536))
            files = manifest.get("files") if isinstance(manifest, dict) else None
            if not isinstance(files, list) or not files or len(files) > 2000:
                raise ValueError("Frontend manifest must list its public build files")
            for name in files:
                if (not isinstance(name, str) or not name or "\\" in name or "\x00" in name
                        or name.startswith("/") or any(p.startswith(".") or not p for p in name.split("/"))
                        or name == "zenith-public.json"):
                    raise ValueError("Invalid public build filename")
                safe_read(self.frontend_dir, name)
                self.frontend_files.add(name)
            if "index.html" not in self.frontend_files:
                raise ValueError("Frontend manifest must include index.html")
        # Keep private-run path resolution identical to the native CLI.
        from .runtime import runs_root
        self.runs = RunStore(runs_root(self.root), set(self.content.nodes)) if local_runs else None

    def contract(self) -> dict:
        """Compact machine-readable route contract; response examples use real reads."""
        return {
            "schema": "zenith_website_contract_v1", "version": "1", "methods": ["GET", "HEAD"],
            "routes": {
                f"{API}/site": "Ordered teaching chapters, document/figure/evidence links and capabilities.",
                f"{API}/paper": "Current manuscript title, PDF/source hashes, bibliography and citation-use lines.",
                f"{API}/documents/{{id}}": {"ids": list(DOCUMENTS), "returns": "Exact Markdown or LaTeX, source hash, heading line numbers and link base."},
                f"{API}/graph": {"query": {"mission": "financial_lab|financial_oracle|financial_refinement|all|basket|basket_serial|basket_evolve|lab|oracle|refinement (evolve alias)", "focus": "optional node ID"}, "returns": "Native scoped nodes, directed edges, execution waves, ancestor/descendant IDs."},
                f"{API}/nodes/{{id}}": {"query":{"task_profile":"generic (default) or financial"},"returns":"Effective operator, instruction, inputs, consumers and source; financial profile includes reasoning schema. Not a historical run override."},
                f"{API}/evidence/{{id}}": {"ids": list(EVIDENCE), "returns": "Public measured-result JSON with source hash; not private run files."},
                f"{API}/runs": {"enabled": self.local_runs, "query": {"q": "substring", "mission": "optional native mission", "limit": "1..100, default40", "offset": "nonnegative, default0"}, "returns": "Paginated saved-run summaries; loaded and success remain distinct."},
                f"{API}/runs/{{run_id}}/nodes/{{node_id}}": {"enabled": self.local_runs, "returns": "Artifact data/status/lineage, bounded recorded attempts and explicit omitted/error/truncation markers."},
                "/assets/paper.pdf": "Retained previous PDF edition; consult the paper endpoint for current source and edition metadata.",
                "/assets/graphs/{id}.svg": {"ids": list(FIGURES)},
                f"{API}/health": "Service version and available capabilities.",
                f"{API}/contract": "This contract.",
            },
            "errors": {"400": "invalid_request", "403": "local_access_required or origin_not_allowed", "404": "not_found", "405": "read_only", "500": "source_unavailable"},
            "limits": {"artifact_bytes": 8388608, "attempt_bytes": 128000, "attempts_per_node": 3},
            "frontend_rules": [
                "Fetch site first; use returned URLs and capability flags.",
                "Render Markdown as untrusted content; resolve relative links against base_url and sanitize HTML.",
                "Do not draw proposed-process arrows as completed execution. Keep chapter evidence_kind visible.",
                "Native graph definitions load at startup. Restart after node-source edits; manuscript and saved evidence are read on request.",
                "Node data are text and data, never executable instructions for the browser.",
                "Keep the synthetic-data and preparation labels visible around examples and output.",
            ],
        }

    def get(self, target: str) -> Response:
        parsed = urlsplit(target)
        path = unquote(parsed.path)
        if "\x00" in path or "\\" in path or any(p in (".", "..") for p in path.split("/")):
            raise ValueError("Invalid path")
        query = parse_qs(parsed.query, keep_blank_values=True, max_num_fields=12)
        if any(len(values) != 1 for values in query.values()):
            raise ValueError("Repeated query parameter")
        def options(allowed: set[str]) -> dict[str, str]:
            if set(query) - allowed:
                raise ValueError("Unknown query parameter")
            return {key: values[0] for key, values in query.items()}
        if path == f"{API}/graph":
            values = options({"mission", "focus"})
            return json_response({**self.content.graph(values.get("mission", "all"), values.get("focus")), "content_kind": "authored_research_definitions"})
        node_parts=path.removeprefix(API+"/").split("/") if path.startswith(API+"/") else []
        if len(node_parts)==2 and node_parts[0]=="nodes":
            values=options({"task_profile"})
            return json_response({**self.content.node(node_parts[1],values.get("task_profile","generic")), "content_kind": "authored_research_definition"})
        if path == f"{API}/runs":
            if not self.runs:
                raise FileNotFoundError("Local records are disabled")
            values = options({"q", "mission", "limit", "offset"})
            return json_response(self.runs.list_runs(query=values.get("q", ""), mission=values.get("mission"),
                                 limit=int(values.get("limit", 40)), offset=int(values.get("offset", 0))), True)
        options(set())
        if path == f"{API}/site":
            return json_response(self.content.site(self.local_runs))
        if path == f"{API}/paper":
            return json_response(self.content.paper())
        if path == f"{API}/health":
            return json_response({"ok": True, "api_version": "1", "node_count": len(self.content.nodes),
                                  "local_runs_enabled": self.local_runs, "frontend_mounted": bool(self.frontend_dir)})
        if path == f"{API}/contract" or (path == "/" and not self.frontend_dir):
            return json_response(self.contract())
        parts = path.removeprefix(API + "/").split("/") if path.startswith(API + "/") else []
        if len(parts) == 2:
            kind, identifier = parts
            if kind == "documents":
                return json_response(self.content.document(identifier))
            if kind == "nodes":
                return json_response(self.content.node(identifier))
            if kind == "evidence":
                return json_response(self.content.evidence(identifier))
        if len(parts) == 4 and parts[0] == "runs" and parts[2] == "nodes":
            if not self.runs:
                raise FileNotFoundError("Local records are disabled")
            return json_response(self.runs.node_evidence(parts[1], parts[3]), True)
        if path == "/assets/paper.pdf":
            return Response(safe_read(self.root, "paper/zenith.pdf"), "application/pdf")
        if path.startswith("/assets/graphs/") and path.rsplit("/", 1)[-1] in {f"{name}.svg" for name in FIGURES}:
            return Response(safe_read(self.root, "docs/graphs/" + path.rsplit("/", 1)[-1]), "image/svg+xml")
        if path.startswith(("/api/", "/assets/graphs/")):
            raise FileNotFoundError("Unknown resource")
        if self.frontend_dir:
            relative = path.lstrip("/") or "index.html"
            if any(part.startswith(".") for part in Path(relative).parts):
                raise FileNotFoundError("Unknown resource")
            extension = Path(relative).suffix.lower()
            if not extension:
                relative, extension = "index.html", ".html"  # explicit SPA host
            if relative not in self.frontend_files:
                raise FileNotFoundError("Unknown resource")
            return Response(safe_read(self.frontend_dir, relative), mimetypes.guess_type(relative)[0] or "application/octet-stream")
        raise FileNotFoundError("Unknown resource")


def make_server(website: Website, host: str = "127.0.0.1", port: int = 4175,
                allow_origins: tuple[str, ...] = ()) -> ThreadingHTTPServer:
    if website.local_runs and not loopback(host):
        raise ValueError("Private saved runs require a loopback bind address")
    for origin in allow_origins:
        parsed = urlsplit(origin)
        if parsed.scheme not in ("http", "https") or not parsed.netloc or parsed.path or parsed.query or parsed.fragment:
            raise ValueError("Allowed origin must be an exact HTTP(S) origin")
        if website.local_runs and not loopback(parsed.hostname or ""):
            raise ValueError("Private saved runs allow only local frontend origins")

    class Handler(BaseHTTPRequestHandler):
        server_version = "ZenithWebsite/1"

        def log_message(self, format, *args):
            pass  # avoid recording private run IDs and error details in access logs

        def respond(self, status: int, response: Response, *, head: bool = False):
            etag = '"' + digest(response.body) + '"'
            if status == 200 and not response.private and self.headers.get("If-None-Match") == etag:
                status = 304
            self.send_response(status)
            self.send_header("Content-Type", response.content_type)
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Cache-Control", "no-store" if response.private else "no-cache")
            if not response.private:
                self.send_header("ETag", etag)
            self.send_header("Vary", "Origin")
            origin = self.headers.get("Origin")
            if origin in allow_origins:
                self.send_header("Access-Control-Allow-Origin", origin)
                self.send_header("Access-Control-Allow-Methods", "GET, HEAD, OPTIONS")
            if status == 405:
                self.send_header("Allow", "GET, HEAD, OPTIONS")
            self.send_header("Content-Length", str(0 if status == 304 else len(response.body)))
            self.end_headers()
            if not head and status != 304:
                self.wfile.write(response.body)

        def read_request(self, head: bool = False):
            try:
                host_header = self.headers.get("Host", "")
                host_name = urlsplit("http://" + host_header).hostname or ""
                origin = self.headers.get("Origin")
                if website.local_runs and (not loopback(self.client_address[0]) or not loopback(host_name)):
                    self.respond(403, json_response({"error": "local_access_required"}, True), head=head)
                    return
                if origin and origin != "http://" + host_header and origin not in allow_origins:
                    self.respond(403, json_response({"error": "origin_not_allowed"}, True), head=head)
                    return
                self.respond(200, website.get(self.path), head=head)
            except FileNotFoundError:
                self.respond(404, json_response({"error": "not_found"}, True), head=head)
            except (ValueError, UnicodeError):
                self.respond(400, json_response({"error": "invalid_request"}, True), head=head)
            except (OSError, KeyError, TypeError):
                self.respond(500, json_response({"error": "source_unavailable"}, True), head=head)

        def do_GET(self):
            self.read_request()

        def do_HEAD(self):
            self.read_request(True)

        def do_OPTIONS(self):
            self.respond(204, Response(b"", private=True))

        def reject(self):
            self.respond(405, json_response({"error": "read_only"}, True))

        do_POST = do_PUT = do_PATCH = do_DELETE = reject

    server = ThreadingHTTPServer((host, port), Handler)
    server.daemon_threads = True
    return server


def serve(root: Path, *, host: str = "127.0.0.1", port: int = 4175, local_runs: bool = False,
          frontend_dir: Path | None = None, allow_origins: tuple[str, ...] = ()) -> dict:
    website = Website(root, local_runs=local_runs, frontend_dir=frontend_dir)
    with make_server(website, host, port, allow_origins) as server:
        print(json.dumps({"status": "serving", "url": f"http://{host}:{server.server_port}",
                          "contract": f"{API}/contract", "local_runs_enabled": local_runs}), flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
    return {"status": "stopped"}
