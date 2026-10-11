# Plectis Zenith

An agent-native research graph for making dated market predictions, measuring their errors, and testing changes to how the graph reasons.

Zenith extracts the existing Lab → Oracle → Evolve system into its own repository. Its 71 authored nodes, engine, typed contracts and provenance rules remain the execution authority. This checkout contains the backend, a read-only graph API and the contract for a separately built frontend.

The learning model is **one prediction graph, evaluated over dated episodes,
with changes between versions**. Lab executes the predictor, Oracle evaluates
its frozen attempts, and Evolve proposes a successor. Current Lab remains the
28-node baseline; the explicit three-node price-only replacement implements
the compact synthesis-and-forecast design. The [learning design](docs/learning-design.md)
defines both contracts. A measured compact-versus-full comparison remains open.

## Start here

Use Python 3.11 or newer from an editable checkout; the validation environment uses Python 3.12. A pinned test environment is recorded in `requirements-test.lock`:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[test]'
python -m zenith validate
python -m zenith plan lab
python -m zenith inspect lab_director
python -m pytest tests
```

No model or market-data credentials are needed for inspection, planning or the offline tests. For a pinned Python 3.12 setup, install `requirements-test.lock` before the editable package. `.[feeds]` adds optional acquisition dependencies. The runtime resolves contracts and assets from this checkout; a standalone wheel is not yet a verified distribution format.

## Frontend integration

Serve the native graph's reviewed metadata locally:

```sh
python -m zenith serve --allow-origin http://localhost:5173
curl http://127.0.0.1:8765/api/v1/graph
curl http://127.0.0.1:8765/api/v1/openapi.json
```

The API exposes graph, mission and node views, including real dependency edges
and wave order. It takes a source snapshot at startup and never invokes a model
or opens private run data. The optional origin flag lets an independently built
frontend read it. [API documentation](docs/backend-api.md) and the
[frontend handoff](docs/frontend-handoff.md) describe the exact contract.

The same projection is available in [public-graph.json](data/graph/public-graph.json).
Run `python scripts/build_demo_data.py --check` to verify its source freshness.
There is no bundled frontend or website deployment.

## Execute the actual graph

Prepare a Lab run from a recorded native feed directory and the time at which its evidence was available:

```sh
python -m zenith prepare lab \
  --run-id LAB_example \
  --feed-source /path/to/recorded/feed-run \
  --time-anchor 2026-10-12T13:30:00Z \
  --horizon next_us_close \
  --context-profile compact_feeds
python -m zenith status LAB_example
```

The engine executes tools and pauses when a reasoning response is needed. Its packet contains the assembled prompt and request hash. An agent can return a response through `import-response`; the original engine validates it before advancing. `run --provider openrouter_free` is an explicit alternative with zero-price eligibility checks and requested/actual model receipts. It never silently selects a paid fallback. NVIDIA hosted NIM is available with `--provider nvidia_nim --model YOUR_SELECTED_NVIDIA_MODEL` and the user’s own `NVIDIA_API_KEY`; its cost remains unknown when the service does not report it. See [provider and key setup](docs/providers.md), CLI help and [the runtime architecture](docs/architecture.md).

Explicit paid experiments use `openrouter_budgeted`, a concrete model and a shared batch budget directory. It reserves conservative costs before calls, limits calls and output tokens, and retains reported usage and cost. Failed or ambiguous calls are not retried; unknown cost halts the batch. The implementation permits an explicitly authorized ceiling of at most US$5 per shared budget; existing budgets remain immutable. This is a client-side spending guard, not a provider billing guarantee. Keys are supplied locally through environment variables or an explicitly selected private environment file.

The compact feed profile removes duplicated diagnostics from prompt context while retaining every feed data row and dated price provenance. It is recorded in the frozen run identity. It does not make large datasets fit every model automatically.

The [compact native backtest](docs/native-backtest.md) runs the existing STOCK,
CP1 and CP2 nodes as an explicit three-node replacement. It compares one frozen
forecasting-skill change with a fixed compact baseline on dated StockNet prices,
using the same native engine, validator and evaluator. Its [systems paper](paper/zenith.pdf)
([source](paper/zenith.tex))
documents the method, prior art and receipt-backed evidence as the implementation
develops. Neither artifact establishes forecasting advantage or method novelty.

The [A-share study](docs/ashare-study.md) compiles the collected TraderHarness
panel into 136 admitted five-session batches across ten stocks, with dated
headlines, separate wealth labels and actual LLM interpretation → forecast
nodes. It compares information use, outcome-trained skills, hindsight-trained
skills and reflected experiences. The [admission receipt](docs/ashare-admission.json)
records the actual support and call plan. Paid execution remains held; the
compiled study establishes no new forecast or learning result. The earlier
[US adapter](docs/trading-study.md) and its withdrawn Apple schedule remain
separate historical work.

## What can change, and how it earns acceptance

Each reasoning node has a [small skill card](.agents/node-skills/index.json), typed incoming context and an output contract. A frozen [reasoning policy](system/lib/reasoning_policy.py) can change its short skill rule, incoming-edge weights and context budget. [Graph variants](docs/graph-variants.md) can insert reasoning checks and rewire dependencies while preserving the base graph's required ancestry and temporal boundaries. The included variant adds an evidence check before CP1.

The [learning design](docs/learning-design.md) defines how graph structure, node parameters and accumulated errors fit together. The learning loop is explicit:

1. Freeze graph, skills, model identity, evidence and prediction time.
2. Produce validated forecasts at declared horizons.
3. Resolve matured forecasts against exact dated observations and compare errors with a no-change baseline.
4. Accumulate failures across issue times and time buckets; propose a skill, context or topology intervention with supporting evidence.
5. Evaluate the candidate with fixed data, complete trial accounting and a sealed final split. Promote it only after review.

[Forecast feedback](docs/forecast-feedback.md) defaults to at least 20 distinct issue times and three time buckets before producing a proposal. Ancestor participation identifies places to investigate; it is not proof that a node caused an error. [The experiment harness](docs/experiments.md) implements bounded autoresearch-style trials using the native replay evaluator. Its probability adapter adjusts frozen forecast cards; its cohort adapter imports and compares new native graph runs on identical frozen inputs and target support. `cohort-next` gives an agent the next concrete commands. Neither adapter automatically rewrites the live graph. See [program.md](program.md) for the agent operating procedure.

The [reflection commands](docs/experiments.md#from-measured-failures-to-one-native-candidate)
connect those pieces: freeze a complete development feedback packet, let an agent
propose one node parameter change, and compile it into a validated native policy
with an exact diff and evidence hashes. Test that policy in a new frozen cohort.
Every cohort import retains mechanical diagnostic observations, including
rejected attempts. Complete comparisons retain paired per-issue losses and
coverage; incomplete support cannot produce a favorable partial ranking.
The [source comparison](docs/architecture-sources.md) covers textual graph
optimization, neural learning and protection against selection overfitting.
Source assimilation does not establish forecasting advantage or method novelty.

Run the zero-inference [repair controls](docs/repair-controls.json) with:

```sh
python -m benchmarks.repair_controls --output work/repair-controls.json
```

They test measured selection of one context-edge restoration, unchanged and
irrelevant-edge controls, and cases that must stay unresolved. This uses the
native context-policy code with deterministic arithmetic; it is not a model
learning result. The [deep-pass synthesis](docs/learning-synthesis.json) records
the operator ideas, closest prior art and remaining falsifiable questions.

The [finance design](docs/finance-design.md) compares the closest financial
agent systems and keeps forecast error, investment returns, feedback maturity
and adaptive model selection distinct. It explains which mechanisms Zenith
reuses and which safeguards still need implementation.

## Historical comparisons and formal semantics

[Historical benchmarks](docs/historical-benchmarks.md) include pinned StockNet OHLCV baselines and a matched prices-versus-prices-plus-timestamped-text experiment over 1/5/20 observed-row horizons. Each issue snapshot joins its feeds before forecasting; target observations stay in a separate evaluator. The protocols do not reproduce StockNet's published paper scores. The older [UCI benchmark](benchmark/README.md) remains a small deterministic scoring fixture. Historical LLM evaluation can be contaminated by model training; prospective predictions form a separate evidence lane.

[FinMultiTime](docs/finmultitime.md) adds a richer historical input: prices, news articles and reported financial facts aligned at one cutoff. Its bounded importer fetches only five pinned Apple files, verifies their sizes, CRCs and hashes, and exports dated snapshots plus partial native feed artifacts. Missing news and stale prices stay explicit. [Dataset research](docs/dataset-scout.md) records the other candidates and the timestamp and licensing checks behind this choice.

The offline [macro-vintage adapter](benchmarks/macro_vintage.py) selects a
Philadelphia Fed RUC workbook version under an explicit reconstructed cutoff
policy. It preserves missing observations and never borrows another vintage's
value. [Source and validation records](docs/data-learning-sources.json) distinguish
that replay assumption from authenticated publication times. Original workbooks
are not bundled, and this adapter does not forecast releases.

```sh
python -m benchmarks.finmultitime import
python -m benchmarks.finmultitime snapshot \
  --issue-date 2025-03-28 --output work/finmultitime-example
```

[Lean semantics](docs/semantics.md) describe parameterized skills as relations, typed composition and refinement, evidence availability and graph rank conditions. The checker connects those finite conditions to the actual graph declarations. These proofs do not establish that a language model obeys its prompt or predicts markets successfully.

```sh
python scripts/build_node_skills.py --check
python scripts/check_extraction.py
python scripts/check_semantics.py --lean
```

Lean is pinned under `formal/`; the last command requires that toolchain. [Source pins and prior art](docs/architecture-sources.md), [imported skills and licenses](docs/skills.md), and the [extraction manifest](docs/extraction-manifest.json) record what was reused.

## Evidence and scope

[Current validation and remaining work](docs/status.md) distinguish synthetic execution checks, historical measurements and live collection. This is a local research repository. Credentials, collected provider data and runtime artifacts stay outside Git. The internal workstation collector continues to own market-open/close scheduling; this checkout does not silently install another daemon.

There is no public deployment or demonstrated forecasting advantage. Read the existing [research and release boundary](docs/research-boundary.md) before preparing a public product; data reuse rights and the actual product behavior require review separately from software licenses.

The source is licensed under [Apache-2.0](LICENSE), with separate imported-source
and dataset notices in [NOTICE](NOTICE). See [reproduction](docs/reproducing.md),
[contribution](CONTRIBUTING.md), [security reporting](SECURITY.md) and
[citation metadata](CITATION.cff). CI checks the native graph, projection,
semantics, offline suite and included historical fixture from a source install.
