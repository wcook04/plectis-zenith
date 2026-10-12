# Website backend

Claude owns the frontend. This Python backend supplies the real graph, the paper
and its citations, explanations, the preparation receipt, and optional local run
evidence. It has no model-execution or editing endpoints.

**This is not financial advice.** Keep the [research notice](../RESEARCH_NOTICE.md)
visible in the website, especially beside financial examples and model output.

## Start

From the repo root, with the existing Python environment active:

```sh
python -m zenith serve --port 4175
```

Open `http://127.0.0.1:4175/api/v1/site`. The default serves public sources only.
To inspect saved runs on this computer while developing a separate frontend:

```sh
python -m zenith serve --port 4175 --local-runs \
  --allow-origin http://localhost:5173 \
  --allow-origin http://127.0.0.1:5173
```

Private run access requires a loopback bind and local frontend origins. It reads
the same configured run directory as the native CLI. There is no client-supplied
filesystem path or credential endpoint, and no paid calls occur.

For a finished frontend build, the same server can host it:

```sh
python -m zenith serve --frontend-dir /path/to/frontend/dist
```

The build directory must contain `zenith-public.json`, an explicit list of public
build outputs, for example:

```json
{"files": ["index.html", "assets/site.js", "assets/site.css"]}
```

Have the frontend build write this list from its emitted files. Only listed files
are served; unrelated JSON, HTML and source files remain inaccessible. The
manifest itself, hidden files and symlinked assets are excluded. Extensionless
SPA routes serve the listed `index.html`. API and paper/figure URLs keep their
meanings. With no frontend mounted, `/` returns the API
contract; there is no placeholder website. A public deployment should use the
default without `--local-runs`, behind its usual TLS reverse proxy.

## Build the reading experience from these sources

Fetch `/api/v1/site` first. Its ordered chapters cover the idea, Lab, Oracle,
Evolve, preparation status and future research. Each points to the owning document,
diagram and native mission graph, plus a `paper_section` with manuscript hash,
source lines, PDF named destination and citation IDs. `evidence_urls` bind the
relevant recorded evidence directly to the chapter; an empty list means no
measured result is attached to that chapter. `evidence_kind` separates a proposed process,
an authored mechanism, verified preparation and a research proposal.

`/api/v1/paper` reads the current title and bibliography, including PDF and LaTeX
hashes, citation IDs, URLs and the manuscript lines where citations are used.
`/api/v1/documents/paper` returns the exact LaTeX source. Browser-readable
explanations come from the existing Markdown, including the
[research direction](research-direction.md) and [spoken walkthrough](zenith-walkthrough-script.md).
A document response includes its hash, heading line numbers and `base_url` for
relative links. Sanitize rendered Markdown and treat model output as data.

The experiment has not produced a completed forecast. Successful local JSON
validation must not be displayed as predictive success. Use the current result
documents and receipts instead of hardcoding result counts into the frontend.

## API

All JSON routes are under `/api/v1`. `GET` and `HEAD` are supported; writes return
405. `/api/v1/contract` gives the machine-readable routes, parameters and errors.

| Route | Response |
|---|---|
| `/site` | Ordered chapters, document/figure/evidence links, notice and capabilities |
| `/paper` | Manuscript metadata, citations, citation uses and PDF/source hashes |
| `/documents/{id}` | Exact Markdown/LaTeX and its source binding |
| `/graph?mission=lab&focus=lab_cross_corr_v1` | Native nodes, edges, waves and ancestors/descendants |
| `/nodes/{id}` | Purpose, instruction, expected output, boundary, inputs, consumers and source |
| `/evidence/{id}` | Public result/source JSON and its SHA-256 |
| `/runs?q=JUL20&mission=lab&limit=20&offset=0` | Optional local run index with total and pagination |
| `/runs/{run_id}/nodes/{node_id}` | Optional local artifact and recorded attempts |
| `/health` | Version and enabled capabilities |

Missions are `all`, `lab`, `oracle` and `refinement`; `evolve` aliases `refinement`.
Site metadata lists document and evidence IDs. The PDF is `/assets/paper.pdf`;
figure URLs are `/assets/graphs/{id}.svg` and are listed by `/site`.

Graph definitions come from the native loader and engine scope policy. There
are no frontend coordinates. Use execution waves, lanes and directed edges to
choose a readable layout. Edges run prerequisite → consumer and do not assert
execution. `focus.ancestors` and `focus.descendants` support a focused view.
Node detail identifies the current authored instruction, not a historical
override. Recorded prompts belong to the separate run endpoint. Restart after
node-definition edits; documents and run records are read on request.

Saved-run responses distinguish `loaded` (reused evidence), `success`, `failure`
and `not_started`. Conditional runs carry their own lineage. `artifact_error`
distinguishes missing, malformed, unsafe and oversized records. An absent
artifact is never a successful output. The artifact limit is 8 MiB; up to three
attempt records are bounded at 128,000 bytes each. Prompt/output excerpts carry
truncation flags. Keep those flags and the distinction between run status and
artifact status visible. Local results use `Cache-Control: no-store`.

Public resources support ETags and conditional reads. Errors return JSON with
stable codes and no filesystem paths. Disabled local-run endpoints return 404.
Local mode rejects remote binds, unapproved origins and nonlocal Host headers.

## Minimal frontend connection

```js
const api = 'http://127.0.0.1:4175';
const site = await fetch(`${api}/api/v1/site`).then(r => r.json());
const graphUrl = site.chapters.find(c => c.id === 'lab').graph_url;
const graph = await fetch(`${api}${graphUrl}`).then(r => r.json());
// On node click:
const node = await fetch(`${api}/api/v1/nodes/${encodeURIComponent(selectedId)}`)
  .then(r => r.json());
// Offer the run selector only when site.local_runs_enabled is true.
```

The frontend owns presentation, navigation and interaction. The backend owns
source fidelity, graph scope, evidence access and result boundaries. There is
no dependency on the discarded ReactFlow viewer.

```sh
python -m pytest tests/test_web.py tests/test_web_runs.py
```

Checks cover native topology, manuscript links, result receipts, HTTP/ETags,
private/public separation, CORS/Host/method rejection, traversal, symlinks,
oversized and malformed evidence, and mounting a future frontend build.

## Current mixed-data edition

Use `site.data_mode`, `site.data_note` and each node's `demo_provenance`.
The graph has 50 nodes: Lab includes 25 nodes/86 edges, Oracle 28/53.
The five source lanes plus derived CALC are the current graph; do not hardcode
historical counts or lanes in the frontend.

`evidence/sources` now returns `zenith_mixed_demo_v1`: real saved stock, ETF and
prediction-market inputs, synthetic macro/news, recomputed CALC. Input retention
and public visibility are separate fields. The raw real inputs remain private.
`evidence/replacements` contains the complete invented macro/news examples.
`evidence/demo-result` records six loaded inputs, the pending Seed request and
zero model calls. Results have evidence kind `verified_preparation`.

The old `observations`, `window-result` and `conditional-result` routes return
404. Do not copy their old payloads into a frontend fixture. Fetch the current
site manifest and follow its evidence URLs. Keep labels visible when opening
nodes. A missing output means not run; never fill it with a fabricated response.
The current source instructions are available for every node. Recorded private
run inputs/outputs are a separate opt-in local capability and are not public
example data. See [data boundaries](data.md) and [the current demo](demo.md).
