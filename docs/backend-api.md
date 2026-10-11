# Graph API

Zenith's HTTP adapter exposes the native authored graph to an independently
built frontend. It has no frontend assets and no execution endpoints. The
existing CLI owns graph runs, agent packets, response validation, feedback and
candidate evaluation.

## Start

From the installed source checkout:

```sh
python -m zenith serve --host 127.0.0.1 --port 8765
curl http://127.0.0.1:8765/api/v1/health
curl http://127.0.0.1:8765/api/v1/graph
```

Use `python -m zenith --root /path/to/checkout serve` from another directory.
The default bind is loopback. Stop with Ctrl-C. Port `0` chooses an available
port and reports it in the JSON startup receipt.

For a separately served local frontend, explicitly allow its origin:

```sh
python -m zenith serve --allow-origin http://localhost:5173
```

Repeat `--allow-origin` for another exact origin. A path, wildcard or credential
is not an origin. An unlisted origin receives no cross-origin read permission.
No cookies, authentication credentials or provider keys belong in frontend
requests. The service uses Python's standard HTTP server for local development;
public hosting, TLS and deployment are separate integration work.

## Routes

All routes return UTF-8 JSON. The live OpenAPI 3.1 document defines exact object
fields and response schemas; tests validate real responses against it.

| GET route | Contract |
| --- | --- |
| `/api/v1/health` | Service readiness, API version and source counts. Readiness does not mean a graph run completed. |
| `/api/v1/graph` | Entire reviewed `zenith_public_graph_v1` projection: nodes, edges, mission scopes, waves and source identity. |
| `/api/v1/missions` | Native mission rows, provenance and context boundary. |
| `/api/v1/missions/lab` | Exact Lab closure: mission row, node rows, edges, counts and provenance. Other IDs come from the mission index. |
| `/api/v1/nodes/lab_director` | One node, immediate incoming/outgoing IDs across the authored graph and context notes. |
| `/api/v1/nodes/lab_director?mission=lab` | The same neighborhood restricted to both endpoints in the Lab closure. |
| `/api/v1/openapi.json` | Machine-readable API contract. |

Only node views accept a query parameter: one nonempty `mission`. Unknown IDs
or a node outside the requested mission return JSON `404`; invalid queries
return JSON `400`. No route accepts a filesystem path, arbitrary root, command,
model or provider. There is no static-file fallback at `/`.

Every GET supports HEAD and an ETag. Send `If-None-Match` to receive `304` when
the representation is unchanged. OPTIONS supports cross-origin GET/HEAD
preflight for allowed origins. POST, PUT, PATCH and DELETE return JSON `405`.

Errors have one shape, with no submitted path or private exception details:

```json
{
  "schema": "zenith_api_error_v1",
  "error": {
    "code": "unknown_node",
    "message": "The requested node does not exist."
  }
}
```

## Source and semantics

`zenith.public_graph.build()` uses the actual loader, scope policy and dependency
wave function. `zenith.api` uses that projection directly. It builds one snapshot
at startup; restart after editing source. The HTTP handler never opens run
directories, constructs the engine or invokes a provider.

The checked-in projection at `data/graph/public-graph.json` is independently
usable by a frontend that needs no server. Regenerate or check it through its
owner rather than editing JSON:

```sh
python scripts/build_demo_data.py
python scripts/build_demo_data.py --check
```

An unreviewed node ID, group, lane, type or output schema fails export and server
startup. The allowlist intentionally omits instructions, configuration, dossiers,
run artifacts and real forecast values. The full CLI `inspect` output is a
private authoring interface and must not be substituted for this projection.

Counts refer to execution closures, including shared inputs. Lab has 28 nodes
in 11 waves; Oracle has 31 in seven. A node's `wave` is its rank in the whole
authored graph; use the selected mission's `waves` array for that mission's
ordering. Surveillance is an authored scope marked
`authored_requires_execution_configuration`, not an advertised executable CLI
mission.

Edges mean declared dependencies. They do not include every injected runtime
input and do not prove causal attribution. Refinement's three retained nodes
also receive Oracle feedback and prior Lab artifacts; their node views say so.
The newer reflection/cohort learning route is separate. Lab-to-Oracle handoffs
reuse dated artifacts across runs rather than inventing cross-mission edges.

## Execution boundary

The original backend remains the execution authority:

- `python -m zenith prepare`, `status`, `import-response` and `resume` manage
  durable agent handoffs through the native engine.
- `python -m zenith run` is an explicit provider-backed alternative with the
  existing model, provenance and spending rules.
- [Forecast feedback](forecast-feedback.md) handles exact dated observations.
- [Experiments](experiments.md) freezes studies and validates one-parameter
  reflection candidates on matched support before any reviewed promotion.

This adapter does not turn those operations into browser actions. A future
execution interface needs its own deliberate contract; a frontend can already
inspect all graph structure without being coupled to a provider account.

See [the frontend handoff](frontend-handoff.md), [disclosure contract](demo-disclosure.md)
and [reproduction guide](reproducing.md) for integration and verification.
