# Zenith teaching website

[Open the public research website](https://wcook04.github.io/plectis-zenith/).

**Experimental research prototype.** The front page is about the current study: whether a record of the bugs an AI tester missed on practice problems helps it expose hidden faults in new programs. The tester, DeepSeek V4.1 Flash, returns five inputs for each short Python function; a fault counts as exposed when an input makes a faulty solution behave differently from the reference solution. The page contains a worked example of how one problem is scored, a table of all eight conditions with 95% intervals, the change on each of the 58 held-out problems, the limits, and links to the saved replies and scores. See the [research notice](../RESEARCH_NOTICE.md).

## Front page: the current study

`src/Root.tsx` selects the page to render. By default it renders `src/components/Study.tsx`
(styles in `src/styles/study.css`). The page needs no request to the data server,
so it is complete on first paint. Every figure comes from
`src/content/keptExperience.json`, which
[`scripts/build_kept_experience_site_data.py`](../scripts/build_kept_experience_site_data.py)
writes from the study's saved files at a fixed revision of this repository. The
script reads those files from git objects, not from the working tree, and stops
if its recomputed per-problem figures disagree with the study's `results.json`.
From the repository root, the first command rewrites the file and the second
compares it with the study files without writing:

```sh
python scripts/build_kept_experience_site_data.py          # write
python scripts/build_kept_experience_site_data.py --check  # compare; needs the study revision fetched
```

`keptExperience.json` is generated: the next run of the script overwrites a hand
edit, and the comparison fails until then. `src/test/study.test.tsx` compares the
printed figures with the study report's table and recomputes the headline
means and counts from the per-problem scores.

## Earlier studies: the paper reading page

The reading page for the earlier studies is `src/App.tsx`, loaded only when it
is needed. It is rendered for `?studies=earlier`, for a `?node=` graph link, and
for any hash that is not one of the front page's own section anchors, so a link
made before November 2026 (such as `#paper`, `#results` or `#ref-1`) still
opens that page. A line of text above the paper begins "Earlier studies." and
links to the front page.

The reading page projects the three numbered sections of
[`paper/zenith.tex`](../paper/zenith.tex): programs and measured repair, test reuse
and continuation learning, and related work and next experiments. Its title,
abstract, paragraphs, table, citations and caption all come from that manuscript.
The diagram is rendered from the same TikZ source. The PDF is offered as current
only when its source and file checksums match the inspected edition.

The final section opens each earlier study's guide in place and links its saved measurements, with
older experiments in a separate disclosure. References include reviewed
editions, supporting passages and limits of applicability. The site uses its
existing React components, STIX/Source Sans typography, themes and source links.
On narrow screens, the diagram and table scroll horizontally at a readable size.

The reading view fetches `/api/v1/site` and `/api/v1/paper`; it does not maintain
a second narrative of the results. The API still provides historical graph,
node and experiment routes, and saved local runs when explicitly enabled.
A file hash identifies bytes; it does not establish a scientific claim.

## Links to Will Cook's other websites

The header begins with the family lockup: the Plectis plait, a short upright
rule, then Zenith's mark (the sun at its highest point on its arc) and name.
The plait opens the home page, <https://wcook04.github.io/>, which lists every
website and film; the mark and name open this site's front page. The footer
lists every website too, with Zenith marked as the one being read.

The first screen of the front page contains the stills of both Zenith videos,
each a link that opens YouTube in a new tab: the
[short video](https://www.youtube.com/watch?v=NQpTlQu_Wrw) (1:54), larger, and the
[full video](https://www.youtube.com/watch?v=wUxp2Wohmq0) (5:03), smaller. On the
earlier-studies page, a video slot beside the abstract (after it on narrow
screens) contains the still of the full video with its running time. That video
is about the kept-experience study, which is not in the paper, so the slot
contains the sentence "The paper on this page does not report this experiment."
and a link to that study's report. Neither page embeds a YouTube player or loads
any file from YouTube.

These parts follow the shared contract, `docs/family.md` in the
[wcook04.github.io repository](https://github.com/wcook04/wcook04.github.io),
and are copies, not edits: `src/content/family.json` is its `sites.json`,
`src/styles/family.css` is its `assets/family/family.css` (the site's colours
and typefaces are mapped onto the `--fam-*` names in `src/styles/tokens.css`),
`public/assets/family/plectis.svg` is its `assets/family/marks/plectis.svg`,
and `public/assets/films/` holds the two stills of each film this site shows
(the short video's stills are in `public/assets/films/next/`, the path given in `family.json`).
To update them, copy the files again, rebuild and run `npm test`; the tests
check the markup and that every released film the site lists has both stills.
The build copies `public/` into `dist/` and lists the stills in
`zenith-public.json`, so the Python server and GitHub Pages both publish them.
It also writes the home link and both video links into `index.html`'s noscript
note from `family.json`, for readers without JavaScript; that note also contains
the current study's question and a link to its report.

## Develop

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
npm test           # study page, layout, run-state, text-helper and interaction tests
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
from `examples/conformance/client-reuse-v1/report.json`; `/api/v1/documents/client-investigation-protocol`
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
