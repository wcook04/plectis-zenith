"""Read-only HTTP access to the reviewed native graph projection.

This adapter never opens runs, creates an engine, or invokes a provider. Native
execution remains available through the CLI's explicit prepare/import/run flow.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
from urllib.parse import parse_qs, unquote, urlsplit

from .public_graph import build, canonical


CONTEXT_BOUNDARY = (
    "Edges are declared node dependencies within the selected scope. Runtime-injected "
    "context and cross-run artifact handoffs are separate. Structure does not establish "
    "completed execution, causal attribution, or forecast accuracy."
)
REFINEMENT_CONTEXT = (
    "The retained refinement runner also uses injected Oracle feedback and prior Lab "
    "artifacts. The reflection/cohort evaluator is a separate route; these three nodes "
    "do not represent automatic execution or acceptance of that evaluator."
)
ID = re.compile(r"[a-z][a-z0-9_]*\Z")


class RequestError(Exception):
    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


@dataclass(frozen=True)
class Response:
    status: int
    body: bytes
    etag: str


def response(payload: dict, status: int = 200) -> Response:
    body = canonical(payload).encode("utf-8")
    return Response(status, body, '"' + hashlib.sha256(body).hexdigest() + '"')


def error_response(status: int, code: str, message: str) -> Response:
    return response({"schema": "zenith_api_error_v1", "error": {"code": code, "message": message}}, status)


def openapi() -> dict:
    """Machine-readable route and response contracts; no deployment URL is assumed."""
    ref = lambda name: {"$ref": f"#/components/schemas/{name}"}
    string = {"type": "string"}
    strings = {"type": "array", "items": string}
    waves = {"type": "array", "items": strings}

    def obj(properties, required=None):
        return {"type": "object", "properties": properties,
                "required": list(properties) if required is None else required,
                "additionalProperties": False}

    node = obj({
        "id": string, "label": string, "description": string,
        "type": {"enum": ["tool", "reasoning"]}, "group": string, "lane": string,
        "dependencies": strings, "output_schema": string, "output_shape": string,
        "wave": {"type": "integer", "minimum": 0},
    })
    edge = obj({"source": string, "target": string})
    counts = obj({"nodes": {"type": "integer"}, "edges": {"type": "integer"}})
    provenance = obj({"source": string, "source_sha256": string, "exporter_sha256": string,
                      "execution": {"const": "static_no_run_state"}})
    mission = obj({"id": string, "label": string, "target": string, "node_ids": strings,
                   "waves": waves, "availability": {"enum": ["native_plan_target", "authored_requires_execution_configuration"]}})
    nodes = {"type": "array", "items": ref("Node")}
    edges = {"type": "array", "items": ref("Edge")}
    missions = {"type": "array", "items": ref("Mission")}
    schemas = {
        "Node": node, "Edge": edge, "Mission": mission, "Counts": counts,
        "Provenance": provenance,
        "Graph": obj({"schema": {"const": "zenith_public_graph_v1"}, "nodes": nodes,
            "edges": edges, "missions": missions, "groups": {"type": "array", "items": obj({"id": string, "label": string, "description": string})},
            "waves": waves, "counts": ref("Counts"), "provenance": ref("Provenance"), "claim_boundary": string}),
        "MissionIndex": obj({"schema": {"const": "zenith_mission_index_v1"},
            "missions": missions, "provenance": ref("Provenance"), "context_boundary": string}),
        "MissionGraph": obj({"schema": {"const": "zenith_mission_graph_v1"},
            "mission": ref("Mission"), "nodes": nodes, "edges": edges,
            "counts": ref("Counts"), "provenance": ref("Provenance"), "context_boundary": string}),
        "NodeView": obj({"schema": {"const": "zenith_node_view_v1"}, "node": ref("Node"),
            "mission": {"type": ["string", "null"]}, "incoming": strings, "outgoing": strings,
            "context_boundary": string, "additional_context": {"type": ["string", "null"]},
            "provenance": ref("Provenance")}),
        "Health": obj({"schema": {"const": "zenith_api_health_v1"}, "status": {"const": "ready"},
            "api_version": {"const": "v1"}, "mode": {"const": "read_only_graph"},
            "counts": ref("Counts"), "source_sha256": string}),
        "Error": obj({"schema": {"const": "zenith_api_error_v1"}, "error": obj({"code": string, "message": string})}),
    }

    def operation(summary, schema, parameters=()):
        responses = {
            "200": {"description": "Reviewed source snapshot",
                    "content": {"application/json": {"schema": ref(schema)}}},
            "304": {"description": "The response ETag matches If-None-Match; no body"},
        }
        for status, description in [(400, "Invalid query"), (404, "Unknown route or identifier"), (405, "Read-only endpoint")]:
            responses[str(status)] = {"description": description,
                                      "content": {"application/json": {"schema": ref("Error")}}}
        return {"summary": summary, "parameters": list(parameters), "responses": responses}

    path_id = lambda name: {"name": name, "in": "path", "required": True, "schema": string}
    return {"openapi": "3.1.0", "info": {"title": "Zenith graph API", "version": "1.0.0",
        "description": "An immutable, allowlisted snapshot of authored graph structure. No run data, inference or mutation endpoints. Restart the service after source edits. GET routes also support HEAD and conditional ETags."},
        "paths": {
            "/api/v1/health": {"get": operation("Inspect service readiness, not graph execution", "Health")},
            "/api/v1/graph": {"get": operation("Read the complete authored graph", "Graph")},
            "/api/v1/missions": {"get": operation("List native mission scopes and waves", "MissionIndex")},
            "/api/v1/missions/{mission_id}": {"get": operation("Read a complete native mission closure", "MissionGraph", [path_id("mission_id")])},
            "/api/v1/nodes/{node_id}": {"get": operation("Inspect a node and its immediate declared dependencies", "NodeView", [path_id("node_id"),
                {"name": "mission", "in": "query", "required": False, "schema": string,
                 "description": "Restrict both ends of every edge to this native mission. Omit for the whole graph."}])},
            "/api/v1/openapi.json": {"get": {"summary": "Read this OpenAPI contract", "responses": {"200": {"description": "OpenAPI 3.1 document", "content": {"application/json": {"schema": {"type": "object"}}}}}}},
        }, "components": {"schemas": schemas}}


class GraphAPI:
    """A read-only, in-memory view built once from the public source allowlist."""

    def __init__(self, root: Path):
        self.graph = build(root)
        self.nodes = {node["id"]: node for node in self.graph["nodes"]}
        self.missions = {mission["id"]: mission for mission in self.graph["missions"]}
        self.provenance = self.graph["provenance"]
        self.static = {
            "/api/v1/graph": response(self.graph),
            "/api/v1/health": response({"schema": "zenith_api_health_v1", "status": "ready",
                "api_version": "v1", "mode": "read_only_graph", "counts": self.graph["counts"],
                "source_sha256": self.provenance["source_sha256"]}),
            "/api/v1/missions": response({"schema": "zenith_mission_index_v1",
                "missions": self.graph["missions"], "provenance": self.provenance,
                "context_boundary": CONTEXT_BOUNDARY}),
            "/api/v1/openapi.json": response(openapi()),
        }

    def get(self, target: str) -> Response:
        try:
            url = urlsplit(target)
            if url.scheme or url.netloc or url.fragment or len(target) > 4096:
                raise RequestError(400, "invalid_target", "Use a local API path.")
            path = unquote(url.path, errors="strict")
            query = parse_qs(url.query, keep_blank_values=True, max_num_fields=8)
            is_node = path.startswith("/api/v1/nodes/")
            if any(key != "mission" or not is_node or len(values) != 1 or not values[0]
                   for key, values in query.items()):
                raise RequestError(400, "invalid_query", "Only one nonempty mission query is accepted on node views.")
            if path in self.static:
                return self.static[path]
            if path.startswith("/api/v1/missions/"):
                mission = self._mission(path.removeprefix("/api/v1/missions/"))
                scope = set(mission["node_ids"])
                nodes = [node for node in self.graph["nodes"] if node["id"] in scope]
                edges = self._edges(scope)
                return response({"schema": "zenith_mission_graph_v1", "mission": mission,
                    "nodes": nodes, "edges": edges, "counts": {"nodes": len(nodes), "edges": len(edges)},
                    "provenance": self.provenance, "context_boundary": CONTEXT_BOUNDARY})
            if is_node:
                node_id = path.removeprefix("/api/v1/nodes/")
                if not ID.fullmatch(node_id) or node_id not in self.nodes:
                    raise RequestError(404, "unknown_node", "The requested node does not exist.")
                mission_id = query.get("mission", [None])[0]
                scope = set(self._mission(mission_id)["node_ids"]) if mission_id else set(self.nodes)
                if node_id not in scope:
                    raise RequestError(404, "node_outside_mission", "The node is outside the requested mission.")
                edges = self._edges(scope)
                node = self.nodes[node_id]
                return response({"schema": "zenith_node_view_v1", "node": node, "mission": mission_id,
                    "incoming": [edge["source"] for edge in edges if edge["target"] == node_id],
                    "outgoing": [edge["target"] for edge in edges if edge["source"] == node_id],
                    "context_boundary": CONTEXT_BOUNDARY,
                    "additional_context": REFINEMENT_CONTEXT if node["group"] == "refinement" else None,
                    "provenance": self.provenance})
            raise RequestError(404, "unknown_route", "The requested API route does not exist.")
        except RequestError as exc:
            return error_response(exc.status, exc.code, exc.message)
        except (ValueError, UnicodeError):
            return error_response(400, "invalid_target", "The request path or query is malformed.")

    def _mission(self, mission_id: str) -> dict:
        if not ID.fullmatch(mission_id) or mission_id not in self.missions:
            raise RequestError(404, "unknown_mission", "The requested mission does not exist.")
        return self.missions[mission_id]

    def _edges(self, scope: set[str]) -> list[dict]:
        return [edge for edge in self.graph["edges"] if edge["source"] in scope and edge["target"] in scope]


def validate_origins(origins) -> tuple[str, ...]:
    accepted = []
    for origin in origins:
        parsed = urlsplit(origin)
        if (parsed.scheme not in {"http", "https"} or not parsed.hostname
                or parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment):
            raise ValueError("CORS origins must be exact HTTP(S) origins without paths or credentials.")
        try:
            parsed.port
        except ValueError as exc:
            raise ValueError("CORS origin has an invalid port.") from exc
        accepted.append(origin)
    return tuple(dict.fromkeys(accepted))


def create_server(root: Path, host="127.0.0.1", port=8765, allow_origins=()) -> ThreadingHTTPServer:
    origins = validate_origins(allow_origins)
    api = GraphAPI(root)  # Fail startup on an unreviewed source interface; never serve raw loader data.

    class Handler(BaseHTTPRequestHandler):
        server_version = "ZenithGraph/1"
        sys_version = ""

        def log_message(self, *_args):
            pass  # Query strings may contain accidental private input; do not log them.

        def _headers(self, result, *, status=None, preflight=False):
            self.send_response(result.status if status is None else status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("ETag", result.etag)
            self.send_header("Vary", "Origin")
            origin = self.headers.get("Origin")
            if origin in origins:
                self.send_header("Access-Control-Allow-Origin", origin)
                self.send_header("Access-Control-Expose-Headers", "ETag")
                if preflight:
                    self.send_header("Access-Control-Allow-Methods", "GET, HEAD, OPTIONS")
                    self.send_header("Access-Control-Allow-Headers", "If-None-Match")
            if result.status == 405 or preflight:
                self.send_header("Allow", "GET, HEAD, OPTIONS")
            if status not in {204, 304}:
                self.send_header("Content-Length", str(len(result.body)))
            self.end_headers()

        def do_GET(self):
            result = api.get(self.path)
            tags = [tag.strip().removeprefix("W/") for tag in self.headers.get("If-None-Match", "").split(",")]
            unchanged = result.status == 200 and (result.etag in tags or "*" in tags)
            self._headers(result, status=304 if unchanged else None)
            if not unchanged and self.command != "HEAD":
                self.wfile.write(result.body)

        do_HEAD = do_GET

        def do_OPTIONS(self):
            result = api.get(self.path)
            self._headers(result, status=204 if result.status == 200 else None, preflight=True)
            if result.status != 200:
                self.wfile.write(result.body)

        def _reject_write(self):
            result = error_response(405, "read_only", "This API only exposes reviewed graph metadata. Use the native CLI for execution.")
            self._headers(result)
            self.wfile.write(result.body)

        do_POST = do_PUT = do_PATCH = do_DELETE = _reject_write

    server = ThreadingHTTPServer((host, port), Handler)
    server.daemon_threads = True
    return server


def serve(root: Path, host="127.0.0.1", port=8765, allow_origins=()) -> dict:
    with create_server(root, host, port, allow_origins) as server:
        address, selected_port = server.server_address[:2]
        print(json.dumps({"schema": "zenith_api_server_v1", "status": "listening",
            "host": address, "port": selected_port, "api": "/api/v1/graph",
            "mode": "read_only_graph"}), flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
    return {"schema": "zenith_api_server_v1", "status": "stopped"}
