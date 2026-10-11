# Backend contract for Claude's frontend

The operator rejected dropdown menus and assigned the frontend to Claude.
Build it separately against the implemented graph API; layout remains your
decision. Start the
backend from an installed source checkout:

```sh
python -m zenith serve --host 127.0.0.1 --port 8765 \
  --allow-origin http://localhost:5173
```

Use the actual frontend origin; `--allow-origin` is repeatable and accepts exact
HTTP(S) origins without paths or credentials. The API sends no CORS allow-origin
header by default. This repository supplies no frontend framework or design.

All routes below are relative to `http://127.0.0.1:8765`:

| GET route | Contract |
| --- | --- |
| `/api/v1/health` | Service readiness, graph counts and source hash; readiness is not execution status. |
| `/api/v1/graph` | Complete `zenith_public_graph_v1`: nodes, directed edges, native mission scopes, groups, waves, counts, provenance and claim boundary. |
| `/api/v1/missions` | Mission index; use returned identifiers and availability labels. |
| `/api/v1/missions/{id}` | Selected mission, its nodes and only edges whose endpoints are in that scope. |
| `/api/v1/nodes/{id}?mission=lab` | Node metadata and immediate incoming/outgoing node ids within the selected mission. Omit `mission` for whole-graph neighbors. |
| `/api/v1/openapi.json` | OpenAPI 3.1 route and exact response schemas. |

Read [zenith/api.py](../zenith/api.py) for the implemented transport and
[zenith/public_graph.py](../zenith/public_graph.py) for the positive source
allowlist. The API builds its snapshot once at startup. Restart after source
changes. The generated file `data/graph/public-graph.json` uses the same builder;
`python scripts/build_demo_data.py --check` verifies it.

Edges run from dependency to consumer. Mission scopes include the native
sibling closure and upstream dependencies; returned mission waves give their
execution order. Keep canonical node ids available for CLI inspection. Present
source provenance, availability and claim boundaries with the graph. Declared
edges describe structure; injected context and cross-run handoffs have separate
authority. The refinement nodes do not mean a candidate was evaluated or accepted.

GET routes support HEAD and `If-None-Match` with ETags; a matching ETag returns
304 without a body. Error responses use `zenith_api_error_v1` with
`error.code` and `error.message`. Invalid queries return 400, unknown identifiers
return 404, and mutation methods return 405. Only one nonempty `mission` query
is accepted on a node view. Allowed origins can read the ETag header; CORS does
not enable write methods or credentialed requests.

The HTTP service exposes no runs, prompts, provider responses, filesystem
browser or execution endpoint. Existing execution remains in the native CLI:
`python -m zenith plan lab`, `python -m zenith inspect lab_director`, and the
explicit `prepare`, `import-response`, `resume` and `run` commands. Follow
[the runtime architecture](architecture.md), [provider setup](providers.md)
and each command's help for inputs. A graph view must keep service readiness,
pending agent work, completed execution and measured forecast results distinct.
