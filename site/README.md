# Zenith teaching website

**This is not financial advice.** Zenith is an experimental research prototype.
Historical examples and model outputs are not investment recommendations. See
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

Use Node.js 22.12 or newer and complete the [Python setup](../README.md#run-it) first.

```sh
# from the repository root: the backend, with saved local runs for development
python -m zenith serve --port 4175 --local-runs \
  --allow-origin http://localhost:5173 --allow-origin http://127.0.0.1:5173

# in site/
npm ci
npm run dev        # http://localhost:5173, proxies /api and /assets to :4175
```

Set `ZENITH_API` to proxy another backend, or `VITE_ZENITH_API` to call one
directly.

## Build and serve

```sh
# from the repository root
cd site
npm ci
npm run build      # typecheck, bundle to dist/, write dist/zenith-public.json
cd ..
python -m zenith serve --port 4175 --frontend-dir site/dist
```

Open [localhost:4175](http://localhost:4175).

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

## README screenshot

[The root README image](../docs/images/zenith-lab.png) is a 1440 × 1000 browser
capture of this frontend served by the public-mode backend from source revision
`26f2d80`, with the button pointer-target correction in this branch. It shows the Lab definition graph with Saved feeds expanded, `lab_decide` selected, its
inspector open and the graph fitted to the remaining canvas. The implementation
is [GraphExplorer](src/components/graph/GraphExplorer.tsx) with
[Inspector](src/components/Inspector.tsx); the visual styling and fonts are unchanged.
No private saved run is enabled. This is an interface example, not execution
evidence.
