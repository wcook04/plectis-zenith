# Read-only graph API and future consumer disclosure

Zenith exposes reviewed authored graph metadata through a read-only HTTP API.
A separate frontend can consume that contract. The API does not execute
reasoning, collect feeds, resolve predictions or return private runtime
artifacts. Service readiness and structural validity do not establish useful
market predictions.

This document defines the metadata disclosure boundary and guidance for a future
consumer. The teaching case below is unimplemented frontend guidance, not a
bundled simulation. The actual product and release review remain governed by
[research-boundary.md](research-boundary.md).

## Graph projection

The canonical serializer is [`zenith/public_graph.py`](../zenith/public_graph.py).
Its reviewed source projection is
[`data/graph/public-graph.json`](../data/graph/public-graph.json).
The HTTP adapter at [`zenith/api.py`](../zenith/api.py) builds its in-memory
snapshot from that serializer; it does not require a frontend or read run data.
Restart the service after authored source changes to load a new snapshot.

The graph view uses a positive allowlist. It may contain canonical
node IDs, curated titles and short descriptions, node type, mission/group/lane,
dependency IDs, output-schema identifiers, edges, mission targets, wave order
and structural counts. Source and exporter hashes can identify the static
projection. They establish freshness, not completed reasoning or empirical
forecasting accuracy.

Do not return the CLI's full node-inspection response over HTTP: hydrated
instructions and configuration can contain injected contract or dossier
content. Do not export native free-form instructions or arbitrary schema fields
merely because they exist in authored JSON. Do not include assembled prompts, feed
values, model responses, private dossiers, provider/account configuration,
credentials, local file paths, runtime manifests or real instrument forecasts.
Build the projection without opening `work/`, `state/`, `.env` or provider
sessions. A link to a reviewed public source file is a separate editorial
choice, not permission to serialize the runtime graph object.

## Reviewed HTTP routes

| GET route | Disclosed content |
|---|---|
| `/api/v1/health` | Service readiness, API mode, structural counts and source hash. Readiness is not graph execution. |
| `/api/v1/graph` | Complete reviewed authored graph projection. |
| `/api/v1/missions` | Mission scopes, targets, waves and availability labels. |
| `/api/v1/missions/{mission_id}` | One mission's complete declared dependency closure. |
| `/api/v1/nodes/{node_id}` | Reviewed node metadata and immediate incoming/outgoing dependency IDs. Optional `mission` query restricts both ends of every edge to that mission. |
| `/api/v1/openapi.json` | Machine-readable response and route contract. |

GET routes also support HEAD and conditional ETags. The service supports OPTIONS
for explicitly configured consumer origins. Write methods are rejected. There
are no runtime, provider, arbitrary-file or mutation endpoints; native execution
remains in the CLI's explicit prepare/import/run flow.

Edges describe declared dependencies within the selected scope. They do not
represent all injected context or cross-run artifact handoffs. In particular,
the retained refinement nodes also use Oracle feedback and prior Lab artifacts;
their graph view does not establish automatic execution or acceptance of the
separate reflection/cohort evaluator. Preserve the API's context and availability
labels rather than inferring these capabilities from a connected diagram.

## A possible future teaching case

This case is a design example for a future frontend. The graph API does not
supply or execute these prices, forecasts, truth observations or comparisons.

Use an invented instrument such as `SYNTH_A`, with `synthetic_fixture: true` and
price basis `synthetic_point_quote`. Do not relabel an actual ticker's observed
price as invented data.

1. At an invented issue time, show the subject quote of 100 and evidence
   available before that cutoff. Give a second invented item an availability
   time after the cutoff and visibly withhold it. Distinguish observation time,
   first availability time and acquisition time.
2. Freeze the subject evidence and a target exactly 24 hours later. Show a
   handwritten baseline target of 104. Call it an illustrative forecast, or a
   captured synthetic response if it actually passes the native import path.
   It is not a live model prediction.
3. Before the target time, keep truth and error pending. At the exact target,
   reveal the invented quote of 101. The baseline absolute error is 3; the
   no-change target of 100 has error 1. These are arithmetic over invented data.
4. Explain Oracle's role: compare the frozen subject with later truth and
   inspect what the earlier evidence could support. Later evidence cannot
   enter the forward Lab snapshot. A diagram of this role is not an executed
   Oracle run unless native execution receipts exist.
5. Draft one review-only candidate rule, such as requiring an explicit
   no-change comparison. If showing a candidate target of 101, label it as
   another handwritten fixture. Its error of 0 is constructed for teaching;
   it does not show that the rule caused an improvement. Real candidate
   assessment reruns the graph on fixed matched support and retains failures.

One case explains the clocks and measurement. It does not satisfy the native
feedback gate for proposing a learned change. The existing feedback demo uses
20 distinct synthetic issue times; its minimum issue/time-bucket requirements
are operational gates, not statistical significance tests. Keep candidate
creation, development comparison, heldout assessment and promotion distinct.
Any future presentation must not claim automatic live mutation or trading.

## Existing examples and their limits

| Source | Possible consumer use | Required context |
|---|---|---|
| `feedback/demo.py` | Explain registration, pending truth, exact-time scoring and review proposals. | Synthetic contract fixtures; it writes grammar/provenance examples and does not execute model reasoning. Its fixture ticker names do not turn invented numbers into market observations. |
| `examples/experiments/graph_cohort.py` | Explain the complete-support cohort consumer. | It explicitly creates synthetic node artifacts and provider receipts. It does not execute the graph engine or a model; its hand-chosen candidate targets are not a tested graph intervention. |
| `examples/experiments/offline/` | Explain frozen probability trials and scoring. | Synthetic replay examples, not native Lab execution or market-performance evidence. |
| `docs/finmultitime-import-result.json` | Show pinned source identity, bounded transport and channel coverage. | Text-free input-preparation receipt. No model result or reproduction of the published four-modal protocol. |
| `docs/stocknet-multifeed-result.json` | Explain attempted historical input comparison, coverage and provenance. | Retain its actual completion state, missing/rejected calls, common support and limitations. It contains no original social text. It is not prospective evidence or a completed native Lab graph. |

Future consumers should show only execution states that the selected source
actually records. A pedagogical animation should use labels such as
"illustrated step", not an invented native success receipt.

## Data and source rights

The bundled UCI Dow Jones Index data is attributed in
[`data/historical/ATTRIBUTION.md`](../data/historical/ATTRIBUTION.md), with exact
source hashes in its manifest. The [official dataset page](https://archive.ics.uci.edu/dataset/312/dow+jones+index)
declares CC BY 4.0. Retain attribution and the
[licence link](https://creativecommons.org/licenses/by/4.0/), and identify
preprocessing changes when displaying or redistributing derived data. Keep this
historical benchmark separate from the synthetic teaching case.

FinMultiTime's local receipt explicitly withholds permission to redistribute
the acquired publisher articles and platform prices. StockNet source access and
repository licences do not establish a right to redistribute underlying social
text or vendor prices. Keep acquired datasets, news text, filing extracts and
text-bearing model packets in ignored local custody. Display audited metadata,
coverage counts and hashes instead. The graph API does not expose provider
materials.

The retained Arthera skills have an Apache-2.0 licence and pinned file hashes in
`third_party/skills/import_manifest.json`. Preserve their licence and attribution
when distributing those source folders. Architecture references that were only
inspected are citations; do not turn them into copied code or claim their
licence applies to Zenith's market inputs.

## Service and consumer boundary

The service binds to loopback by default and serves the explicit metadata
contract. Do not add blanket checkout-file serving or serialize private research
state for a consumer. Review any future frontend payloads, screenshots and
downloads separately: a synthetic label does not sanitize attached private
evidence.

Keep repository source licensing, third-party notices and dataset attribution
separate from claims about generated research. Starting a local API does not
imply public deployment or legal clearance.
