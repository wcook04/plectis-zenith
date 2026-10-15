# Zenith teaching website

[Open the public research website](https://wcook04.github.io/plectis-zenith/).

**Experimental research prototype.** The active programme compares executable investigations on native SQLite, LRU caching and UTF-8 decoding, with a separate continuation-memory study.
Operational latency campaigns, financial experiments and the older System A fixture remain separately labelled historical profiles. See
the [research notice](../RESEARCH_NOTICE.md).

The current page has four sections: the research question, how the method works,
what the experiments found, and the frontier. The three findings remain separate:
reusable client tests, native program repair and the continuation learner. Primary
results and ordinary controls stay visible; qualification details, earlier attempts,
financial studies and old graph diagrams are optional reading.

This is a refinement of the existing `App.tsx`, `PaperAside`, result tables and
`source-doc` disclosures, using the existing React stack, STIX/Source Sans fonts,
tokens and styles. The paper source is the primary paper link. Its older PDF is
labelled in the archive, not presented beside current manuscript sections.
The API keeps its six chapter IDs; the current reading view combines them into
four sections and preserves `#lab` and `#evolve` as aliases. Theme, source links,
raw evidence, copy controls, historical graph views and offline replay remain.

Measured results and source material come from the API at runtime: chapters, paper sections and
citations from `/site` and `/paper`, graphs from `/graph`, node detail from
`/nodes/{id}`, measured results from `/evidence/*`, and saved runs from `/runs`
only when the backend enables them. Node counts, result numbers and requested
bounds are read from those responses. The frontend supplies the reading order
and concise explanations of the published studies.

## Develop

```sh
# from the repository root: the backend, with saved local runs for development
python -m zenith serve --port 4175 --local-runs \
  --allow-origin http://localhost:5173 --allow-origin http://127.0.0.1:5173

# in site/
npm install
npm run dev        # http://localhost:5173, proxies /api and /assets to :4175
```

Set `ZENITH_API` to proxy another backend, or `VITE_ZENITH_API` to call one
directly.

## Build and serve

```sh
npm run build      # typecheck, bundle to dist/, write dist/zenith-public.json
python -m zenith serve --frontend-dir site/dist   # public mode, from the repo root
```

The build writes `zenith-public.json` listing every emitted file, which is the
allow-list the backend serves. Bundles go under `static/`, so the backend's
reserved `/api`, `/assets/paper.pdf` and `/assets/graphs` routes keep their
meaning. Public mode has no run access; the site then shows definitions and the
public receipts only. Restart the serving process after rebuilding so it reads the new asset allowlist.

## Test

```sh
npm test           # layout, run-state, text-helper and interaction tests
```

The interaction tests open nodes, walk to an upstream input, close with Escape,
show a failed run's recorded error and excerpts, switch runs without leaving
the previous run's evidence on screen, keep reused evidence labelled as reused,
and check that backend Markdown cannot inject HTML or `javascript:` links.

## What came from the original Zenith UI

Adapted from `ai_workflow/system/server/ui/src` (the operator application),
rewritten against this API with no store or private endpoint:

- **GraphViewer** (`components/GraphViewer.tsx`): execution waves as columns
  and lanes as rows around the main path, lane order, collapsible containers for
  lane-parallel siblings, the four-tier emphasis grammar (selected, inputs,
  consumers, background), hiding skip links already implied by another path
  (`showAllDependencies`), fit and zoom controls. Here the containers sit on the
  main path so the overview reads as a line, long graphs wrap into the paper's
  two passes, and edges that skip a step route through channels instead of
  running behind cards.
- **NodeHUD**: the inspector's definition view, instruction disclosure, and
  dependency chips that navigate to the related node.
- **ArtifactViewer**: recorded output with a failure banner and copy control.
- **utils/status.ts**: state normalisation and container aggregation, changed so
  `loaded` (reused evidence) is never folded into `success`.

Typefaces (STIX Two Text and Source Sans 3, SIL OFL, licences in
`public/fonts/`) and the paper and night grounds come from the Plectis site.
Lane colours are a categorical palette checked for lightness, chroma and
colour-blind separation in both themes.

## Basket research API

The shared-universe backend adds `basket`, `basket_serial` and `basket_evolve` mission scopes to `/api/v1/graph`. `/api/v1/documents/experiment` describes the numerical protocol; `/api/v1/evidence/basket-result`, `basket-protocol` and `basket-trace` expose reviewed research evidence. `/api/v1/documents/synthetic-fixture` retains the earlier System A instructions.

The site metadata explicitly selects the Progress campaign; the Advance and basket receipts retain their own provenance. Public mode serves allowlisted evidence only; it does not expose the downloaded panel, local credentials or arbitrary run files. Model execution stays in the explicit CLI. No frontend redesign is required to use these endpoints.

`/api/v1/evidence/basket-repair` serves the successful new-date interface check separately from the original pilot result. Graph API records for basket nodes link to their own protocol and do not attach a legacy System A dossier.

## Active study and historical reasoning graph

The current chapters route to `/api/v1/documents/progress-synthesis`, `conformance-study` and `progress-results` and `continuation-learner`; `/api/v1/evidence/progress-campaign` serves the derived source-bound receipt when published. Its qualification and diagnostic studies keep their own actual attempts, known reported costs and evaluation panels. A forfeited protocol version remains visible without being pooled into a later diagnostic. `/api/v1/evidence/advance-campaign`, `/api/v1/documents/advance-synthesis`, `/api/v1/evidence/observation-learning-result` and other earlier routes remain historical references. Actual private provider records remain local CLI artifacts.

`/api/v1/evidence/client-investigation` serves `zenith_client_investigation_report_v1`
from `docs/client-investigation-20261014.json`; `/api/v1/documents/client-investigation-protocol`
serves its method, with the analysis at `/api/v1/documents/client-investigation`.
The results section renders this pilot independently of the native
campaign. It displays exact model cost, detected faults and valid target queries by
method, and withholds protected outcomes for an incomplete or unsupported receipt.
These are finite checks within an authored SQLite family; they do not establish
independent transfer or a false-accusation rate.

The client section displays the latest published version and keeps each earlier
version's receipt and analysis linked. The v1 routes retain their original
meaning. `/api/v1/evidence/client-investigation-v2` and `client-investigation-v2-low`
serve the separate v2 attempts, with matching document IDs for their analyses.
`/api/v1/documents/client-investigation-protocol-v2` serves the clarified protocol.
An invalid compiled artifact is labelled with skipped target runs rather than
reported as a measured zero. The table separates target queries and model calls;
the headline cost includes acquisition and compilation.

## Static publication

The deployed website is agent-readable without JavaScript: start with
[llms.txt](https://wcook04.github.io/plectis-zenith/llms.txt), then the
[research and graph map](https://wcook04.github.io/plectis-zenith/agent-map.md) or
[machine route index](https://wcook04.github.io/plectis-zenith/agent-index.json).
For example, `curl -fsSL https://wcook04.github.io/plectis-zenith/agent-index.json`
returns direct files for every exported API route. Node IDs, dependencies,
consumers, directed edges, task profiles and source hashes remain intact.
Follow the index's `routes` mapping for mission/profile queries; GitHub Pages
does not execute API query parameters. These files are fetched on demand and
add no JavaScript, network request or preload to the human application.

Build with `VITE_ZENITH_SNAPSHOT=1` and `VITE_ZENITH_API` set to the deployment
prefix, and pass the same prefix to Vite's `--base` option. The UI then reads
one `public-api.json` snapshot with schema `zenith_public_api_snapshot_v1` and
a `routes` map of exact public API paths to response bodies. Public read links
point to the corresponding `.json` files; assets use the deployment prefix.
Missing routes return a clear error without attempting a live backend.
The snapshot is exported from the read-only backend, preserving source hashes
and the public allowlist. See [website backend](../docs/website-backend.md).

From the repository root, generate the complete publication with:

```sh
VITE_ZENITH_SNAPSHOT=1 VITE_ZENITH_API=/plectis-zenith npm run build --prefix site -- --base=/plectis-zenith/
python scripts/export_site_snapshot.py site/dist
python -m pytest tests/test_site_snapshot.py tests/test_structure.py
python scripts/check_structure.py
```

The exporter owns the generated agent map and route index; edit its source,
not `site/dist`. `snapshot-manifest.json` hashes those outputs as well as the
direct graph, node, document and evidence files. A frontend-only development
build does not include these publication files; its live API still exposes
the same source records at `/api/v1/site`.

Use `financial_lab`, `financial_oracle` and `financial_refinement` as graph mission parameters. Responses expose effective dependencies, instructions and the persisted reasoning schema at each model node. `/api/v1/documents/reasoning-ontology` explains the contracts. `/api/v1/evidence/reasoning-schemas` exports them, and the `full-graph-result` and `full-graph-trace` evidence routes serve the completed experiment when present. The trace includes the frozen Lab graph and original-input bindings available to Oracle. This change concerns the backend and evidence; it does not redesign the frontend.
