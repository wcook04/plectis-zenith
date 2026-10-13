# Zenith teaching website

**Experimental research prototype.** The active financial experiment uses licensed historical observations.
The older System A fixture uses invented observations. See
the [research notice](../RESEARCH_NOTICE.md).

A React frontend for the read-only website API in
[docs/website-backend.md](../docs/website-backend.md). It walks through the
paper's argument and embeds the native mission graphs: select any node to read
its current instruction, the nodes it reads and feeds, its expected output and,
when a run is chosen, that run's recorded state, artifact, failure and
prompt/output excerpts.

Everything shown comes from the API at runtime: chapters, paper sections and
citations from `/site` and `/paper`, graphs from `/graph`, node detail from
`/nodes/{id}`, measured results from `/evidence/*`, and saved runs from `/runs`
only when the backend enables them. Node counts, result numbers and requested
bounds are read from those responses, never written into the source.

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
public receipts only.

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

The site metadata labels the active data as `historical_research`. Public mode serves allowlisted evidence only; it does not expose the downloaded panel, local credentials or arbitrary run files. Model execution stays in the explicit CLI. No frontend redesign is required to use these endpoints.

`/api/v1/evidence/basket-repair` serves the successful new-date interface check separately from the original pilot result. Graph API records for basket nodes link to their own protocol and do not attach a legacy System A dossier.

## Full reasoning-graph backend

The paper's current chapters point to the adaptive investigator method and curated episode evidence. `/api/v1/documents/investigator`, `/api/v1/evidence/investigator-result` and `/assets/graphs/investigator-detail.svg` expose those reviewed public artifacts. Actual private investigator runs remain local CLI artifacts. The full financial graph routes below remain historical comparators.

Use `financial_lab`, `financial_oracle` and `financial_refinement` as graph mission parameters. Responses expose effective dependencies, instructions and the persisted reasoning schema at each model node. `/api/v1/documents/reasoning-ontology` explains the contracts. `/api/v1/evidence/reasoning-schemas` exports them, and the `full-graph-result` and `full-graph-trace` evidence routes serve the completed experiment when present. The trace includes the frozen Lab graph and original-input bindings available to Oracle. This change concerns the backend and evidence; it does not redesign the frontend.
