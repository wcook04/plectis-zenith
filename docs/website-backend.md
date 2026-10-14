# Website backend

The Python backend supplies the real graph, the paper
and its citations, explanations, the preparation receipt, and optional local run
evidence. It has no model-execution or editing endpoints.

Keep the experimental boundary visible beside examples and model output.

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
hashes, citation IDs, URLs and the manuscript lines where citations are used. The current source compiles in the existing editor, while the retained PDF is a previous edition (`pdf_current=false`, `pdf_edition=retained_previous_edition`). Source and PDF are labelled separately; independent file hashes do not prove that they match.
`/api/v1/documents/paper` returns the exact LaTeX source. Browser-readable
explanations come from the existing Markdown, including the
[research direction](research-direction.md) and [spoken walkthrough](zenith-walkthrough-script.md).
A document response includes its hash, heading line numbers and `base_url` for
relative links. Sanitize rendered Markdown and treat model output as data.

Use the recorded experiment status. Successful JSON validation alone must not be displayed as predictive success. Use the current result
documents and receipts instead of hardcoding result counts into the frontend.

The active source is `/api/v1/documents/observation-learning`, an alias of
`docs/executable-investigations.md`. Its public receipt is
`/api/v1/evidence/observation-learning-result`, bound to
`docs/observation-learning-20261013.json`. Site metadata names this active
evidence ID even before a receipt is published. A missing receipt means results
pending, rather than a fallback to historical operational scores.

The receipt uses `zenith_observation_learning_evidence_v1`. Protected tables
require `complete=true`, `status=complete` and a measured aggregate. Failed and
partial snapshots publish status, calls, canaries, unresolved billing and source
hashes without completed outcome tables. Absence of a failure does not establish
that an external process is running. The site reads costs and comparison values
from the receipt. The older `investigation-learning-result` route remains
historical and retains its original schema.

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

Historical graph missions include `financial_lab`, `financial_oracle` and `financial_refinement`. Their graph responses include effective node hashes, instructions, dependencies and `reasoning_schema`. The generic `all`, `lab`, `oracle` and `refinement` graphs remain available; `evolve` aliases generic `refinement`. Earlier `basket`, `basket_serial` and `basket_evolve` graphs describe the reduced pilot. The active native observation study publishes source-bound programs and receipts and does not require those historical graphs to render its results.
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

## Current native observation edition

The initial comparison receipt remains immutable. `/api/v1/evidence/observation-screens`
serves `docs/observation-screens-20261013.json` for the later repair, candidate-pool,
composition and fixed-inventory selection tests, with separate protocols and cost
accounting. The results chapter links this receipt and the updated manuscript;
it does not overwrite the original comparison table with a different population.

`site.data_mode` is `native_observation_research`. Constructed action sequences
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
public examples. See [data boundaries](data.md) and [the demo](demo.md).

Financial graph node records include `detail_url` for profile-preserving inspection. The node route defaults to the generic fixture for compatibility; use the explicit financial parameter for the research graph. The completed experiment used reasoning schema v3; current contracts are v4 after correcting citation requirements and role separation. Public traces keep their original version.
