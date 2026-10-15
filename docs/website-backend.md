# Website backend

The Python backend supplies the real graph, the paper
and its citations, explanations, the preparation receipt, and optional local run
evidence. It has no model-execution or editing endpoints.

Keep the experimental boundary visible beside examples and model output.

The public static website is also agent-navigable. Its generated
[`llms.txt`](https://wcook04.github.io/plectis-zenith/llms.txt) links to a
[`agent-map.md`](https://wcook04.github.io/plectis-zenith/agent-map.md) reading
and graph map and an
[`agent-index.json`](https://wcook04.github.io/plectis-zenith/agent-index.json)
route table. `scripts/export_site_snapshot.py` derives all three from this
same public API. Every exported request, including `?mission=` and
`?task_profile=`, has a static JSON file; resolve its filename relative to the
index URL. Source hashes, document `base_url`, graph node IDs, prerequisites,
consumers and profile distinctions remain unchanged. The static host does not
execute API queries. The combined `public-api.json` is optional for agents;
fetch individual responses to avoid downloading unrelated evidence. The live
backend continues to use its API routes as described below.

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

Fetch `/api/v1/site` first. Its six stable chapter IDs retain the idea, Lab,
Oracle, Evolve, results and future-research routes. The current frontend groups
them into research question, method, findings and frontier, preserving the
`#lab` and `#evolve` anchors. Each points to the owning document,
diagram and native mission graph, plus a `paper_section` with manuscript hash,
source lines, PDF named destination and citation IDs. `evidence_urls` bind the
relevant recorded evidence directly to the chapter; an empty list means no
measured result is attached to that chapter. `evidence_kind` separates a proposed process,
an authored mechanism, verified preparation and a research proposal.

`/api/v1/paper` reads the current title and bibliography, including PDF and LaTeX
hashes, citation IDs, URLs and the manuscript lines where citations are used. The current source compiles in the existing editor, while the retained PDF is a previous edition (`pdf_current=false`, `pdf_edition=retained_previous_edition`). Source and PDF are labelled separately; independent file hashes do not prove that they match.
`/api/v1/documents/paper` returns the exact LaTeX source. Browser-readable
explanations come from the existing Markdown, including the
[research direction](../program.md) and [spoken walkthrough](history/zenith-walkthrough-script.md).
A document response includes its hash, heading line numbers and `base_url` for
relative links. Sanitize rendered Markdown and treat model output as data.

Use the recorded experiment status. Successful JSON validation alone must not be displayed as predictive success. Use the current result
documents and receipts instead of hardcoding result counts into the frontend.

The current results explanation is `/api/v1/documents/progress-results`, bound
to `docs/studies/native/progress-campaign-20261014.md`. The learner explanation is
`/api/v1/documents/continuation-learner`, bound to the witness-preserving
demonstration README. The earlier assimilation remains available through
`/api/v1/documents/progress-synthesis`. Site metadata selects
`/api/v1/evidence/progress-campaign`, bound to
`docs/studies/native/progress-campaign-20261014.json` when that receipt is published. Its
schema is `zenith_progress_campaign_report_v1`. A missing receipt means current
results pending; the frontend does not substitute an older campaign. The
qualification and diagnostic stages retain separate parent populations,
actual model attempts, known reported costs, unknown-charge attempts and
confirmation panels. A forfeited protocol version remains visible as an
engineering failure, not a diagnostic result. The source-bound receipt supplies
all displayed scores and costs.

The separate `/api/v1/evidence/client-investigation` route reads
`examples/conformance/client-reuse-v1/report.json` with schema
`zenith_client_investigation_report_v1`. Its method is available at
`/api/v1/documents/client-investigation-protocol`. The frontend renders this
study's analysis from `/api/v1/documents/client-investigation`. It shows the
SQLite client pilot independently of the native campaign, including when the
native receipt is pending. `arm_metrics` supplies the failing-client detection
denominator and target query counts; model attempts and exact reported cost
include acquisition and compilation. Protected outcomes are withheld unless
the pilot and panel are complete. Missing, unavailable or unsupported evidence
never borrows outcomes from another study. These finite authored checks cannot
establish independent transfer or a false-accusation rate.

The v1 evidence and document IDs retain their meaning. The separate
`client-investigation-v2` and `client-investigation-v2-low` evidence and document
IDs expose the subsequent attempts, while `client-investigation-protocol-v2`
owns their clarified protocol. The UI displays the latest available version
and retains links and engineering outcomes for its predecessors. Invalid
artifacts show skipped target runs, without a measured detection score. Target
model calls remain separate from full lifecycle attempts and costs.

For a static deployment, the same frontend can read a snapshot with schema
`zenith_public_api_snapshot_v1`. Its `routes` map contains exact public API
paths and the JSON bodies produced by this backend. Set `VITE_ZENITH_SNAPSHOT=1`
and use `VITE_ZENITH_API` plus Vite's `--base` for the deployment prefix.
One snapshot request supplies the API client; absent routes return an explicit
404 error. Separate `.json` files preserve queryless API read links. This
mode has no local-run access and cannot execute models or write state.

`/api/v1/evidence/advance-campaign` and
`/api/v1/documents/advance-synthesis` retain the earlier campaign. The older
`observation-learning-result` and `investigation-learning-result` routes keep
their original schemas and historical evidence boundaries.

## API

All JSON routes are under `/api/v1`. `GET` and `HEAD` are supported; writes return
405. `/api/v1/contract` gives the machine-readable routes, parameters and errors.

| Route | Response |
|---|---|
| `/site` | Ordered chapters, document/figure/evidence links, notice and capabilities |
| `/paper` | Manuscript metadata, citations, citation uses and PDF/source hashes |
| `/documents/{id}` | Exact Markdown/LaTeX and its source binding |
| `/graph?mission=lab&focus=lab_cross_corr_v1` | Native nodes, edges, waves and ancestors/descendants |
| `/nodes/{id}?task_profile=financial` | Effective role, instruction, schema, inputs, consumers and profile source |
| `/evidence/{id}` | Public result/source JSON and its SHA-256 |
| `/runs?q=JUL20&mission=lab&limit=20&offset=0` | Optional local run index with total and pagination |
| `/runs/{run_id}/nodes/{node_id}` | Optional local artifact and recorded attempts |
| `/health` | Version and enabled capabilities |

Historical graph missions include `financial_lab`, `financial_oracle` and `financial_refinement`. Their graph responses include effective node hashes, instructions, dependencies and `reasoning_schema`. The generic `all`, `lab`, `oracle` and `refinement` graphs remain available; `evolve` aliases generic `refinement`. Earlier `basket`, `basket_serial` and `basket_evolve` graphs describe the reduced pilot. The current Progress result renders from its source-bound receipt and does not require those historical graphs.
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
const resultUrl = site.chapters.find(c => c.id === 'results').evidence_urls[0];
const receipt = await fetch(`${api}${resultUrl}`).then(r => r.json());
// Render status and costs even when protected scores are unavailable.
// Historical graphs remain at /api/v1/graph; use their explicit mission profile.
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

## Historical native observation edition

The initial comparison receipt remains immutable. `/api/v1/evidence/observation-screens`
serves `docs/history/observation-screens-20261013.json` for the later repair, candidate-pool,
composition and fixed-inventory selection tests, with separate protocols and cost
accounting. The historical receipt and manuscript retain their own population;
they do not overwrite the current Progress comparison.

In that historical edition, `site.data_mode` was `native_observation_research`. Constructed action sequences
produce actual native SQLite counter and committed-state observations. The
comparison remains conditional on the frozen software family. The source-bound
receipt separates primary policies, controls, errors and unsupported exact
answers; it does not certify arbitrary semantic discovery or production use.

## Retained synthetic edition

Use `site.data_mode`, `site.data_note` and each node's `demo_provenance`.
The optional `dossier` contains that lane's current role and evidence contract,
with its own source path and hash; the inspector exposes it beside the instruction.
Read current node and edge counts from the API rather than hardcoding them.
Five synthetic source perspectives describe an invented System A: measurements,
subsystems, environment, events and interventions. Derived summaries are
recomputed from supplied inputs. Quantities are abstract and have arbitrary
or dimensionless units; this is a demonstration of the protocol.

`evidence/sources` describes provenance and hashes. Follow the current site
manifest for complete synthetic observation payloads and the preparation
receipt. `evidence/demo-result` establishes preparation only: inputs loaded,
first request pending, zero model calls and no completed forecast.
Results have evidence kind `verified_preparation`.

Fetch current evidence URLs; do not restore historical result fixtures as
results for this configuration. Keep provenance visible when opening nodes.
Missing output means not run; never fill it with a fabricated response.
Recorded private runs are an explicit opt-in local capability, excluded from
public examples. See [data boundaries](history/data.md) and [the demo](history/demo.md).

Financial graph node records include `detail_url` for profile-preserving inspection. The node route defaults to the generic fixture for compatibility; use the explicit financial parameter for the research graph. The completed experiment used reasoning schema v3; current contracts are v4 after correcting citation requirements and role separation. Public traces keep their original version.
