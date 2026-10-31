# Architecture

Zenith is an unfinished research testbed with three separate studies, shared execution support, and published evidence. The [paper](../paper/zenith.tex) describes their results; [program.md](../program.md) describes the broader goal. The graph-based financial and forecasting profiles have their own [historical architecture](history/architecture.md).

## Current source owners

| Study | Orchestration and source tasks | What changes |
|---|---|---|
| Native investigation and repair | [conformance_study.py](../research/conformance_study.py), [direct_investigation.py](../research/direct_investigation.py), [native_conformance_tasks.py](../research/native_conformance_tasks.py) | Questions produce measurements that can expose a discrepancy; a model proposes a whole-program repair. |
| Client test reuse | [client_investigation_study.py](../research/client_investigation_study.py), [client_investigation_tasks.py](../research/client_investigation_tasks.py) | Earlier investigations produce frozen testers, compared with ordinary reuse and fresh investigation on later clients. |
| Continuation learning | [continuation_learning.py](../research/continuation_learning.py), [demo_continuation_learning.py](../scripts/demo_continuation_learning.py) | An authored rational-linear learner expands an observation table through counterexample refinement, retaining access histories with their distinguishing continuations. |

These mechanisms are not one integrated learner. In particular, the continuation learner is not called by the client-test or native-repair campaigns. Language-model weights remain fixed.

The continuation repair restores the paired rank-growth invariant in the [weighted-automata source](https://www.cs.ox.ac.uk/people/james.worrell/MA-learning.pdf), Proposition 1, pp. 2–3. Its measured finite challenges do not provide the global equivalence oracle assumed there. [Predictive state representations](https://proceedings.neurips.cc/paper/2001/file/1e4d36177d71bbb3558e43af9577d70e-Paper.pdf) supply conceptual context for future-test coordinates in stochastic systems, with a known model and normalized updates; they are not a runtime dependency or the implemented learner.

## Execution and evidence boundaries

1. **Prepare.** A study freezes its source, task definitions, model route, reasoning setting and budget. Public task information and later evaluation inputs remain distinct.
2. **Propose.** A model returns a program or a bounded query. Notes about its purpose or limitations are untrusted proposals.
3. **Measure.** The host executes the reference and candidate independently. Invalid deliveries, duplicate queries, errors and cost remain in the record.
4. **Select.** Native repair uses only that arm's available development evidence and preserves each previously correct measured case. A nonregressing replacement may be accepted on an equal score; both scores remain recorded. Later evaluation cannot enter a repair prompt.
5. **Freeze and evaluate.** Selected programs or reusable testers freeze before later execution. Each comparison keeps its own population and budget.
6. **Publish and replay.** Exporters publish allowlisted records and source archives. Offline replay executes preserved programs and checks the recorded behavior without new inference.

The preservation rule is finite; it does not prove a repaired program correct on unseen inputs. The [native method](studies/native/conformance-study.md), [v5 protocol](progress-protocol-v5-20261014.md) and [client v2 protocol](client-investigation-protocol-v2-20261015.md) own the exact experimental contracts.

## Shared implementation

| Owner | Boundary |
|---|---|
| [investigation_program.py](../zenith/investigation_program.py) | Explicit Python syntax, process, time and memory limits for generated code. This is a research executor, not a general sandbox service. |
| [budgeted.py](../zenith/budgeted.py), [provider_policy.py](../zenith/provider_policy.py) | Explicit paid requests, route eligibility, atomic cost reservations and bounded concurrency. No automatic expensive fallback. |
| [source_snapshot.py](../zenith/source_snapshot.py) | Implementation hashes and frozen runtime archives, without importing an experiment or the market/graph runtime. |
| [decomposition_study.py](../research/decomposition_study.py) | Retained execution/schema/scoring helpers also used by current native and client studies. Its historical experiment is not credited as part of their results. |
| [web.py](../zenith/web.py), [web_content.py](../zenith/web_content.py), [site/](../site/README.md) | Read-only projection of manuscript, public evidence and retained graphs. Public mode excludes private runs and has no inference or editing endpoint. |
| [references.json](../paper/references.json), [build_paper_references.py](../scripts/build_paper_references.py) | Reviewed source editions and claim support, with a generated inline bibliography and checks binding citations to exact manuscript passages. [test_paper_references.py](../tests/test_paper_references.py) checks this boundary. These files add no experiment runtime. |
| [paper_reading.py](../zenith/paper_reading.py), [build_paper_reading.py](../scripts/build_paper_reading.py) | Restricted TeX-to-Markdown paper projection and a builder rendering the existing TikZ figure into `paper/repair-loop.svg`. Unsupported content is rejected; `tests/test_paper_reading.py` checks projection and stale-output boundaries. |

Direct investigation uses the conformance runner's invocation helper. Some retained module names therefore remain in the active import path. Renaming these files alone would not simplify execution and would disturb published import and replay interfaces.

Unused private-system operation registries and the speculative reasoning-packet/plan framework have been removed. The retired `build_reasoning_contract_packet`, `build_reasoning_execution_plan` and `verify_reasoning_execution_plan` commands have no replacement: they were not used by the graph or research runners. Actual graph-contract validation remains available through `python -m tools.meta.factory.validate_reasoning_contracts --check`. Its runtime schema and vocabulary are preserved.

The loader and engine read Markdown contract bodies from `codex/contracts/`. Seven unused Markdown copies under `codex/substrate/contracts/` have been retired; their original extraction records and replacement paths remain in `docs/extraction-manifest.json::retired_files`. JSON contracts and refinement nodes still have callers in both trees, as the [historical source map](history/architecture.md#retained-source-owners) explains. Frozen experimental evidence remains unchanged.

The website exporter, [`export_site_snapshot.py`](../scripts/export_site_snapshot.py), also publishes `llms.txt`, `agent-map.md` and `agent-index.json`. These derive from the same document, evidence and graph owners as the browser interface; they do not create a separate research catalogue. Each mission/profile has readable static records.

## Repository roles

| Directory | Role |
|---|---|
| `research/` | Current experiments and retained research runners; begin with the three studies above. |
| `zenith/` | Shared provider/execution/custody support, website backend and retained graph CLI. |
| `scripts/` | Explicit developer commands: demonstrations, reports, offline replay, validation and website export. |
| `examples/` | Published evidence, original attempts, generated programs, hashes and frozen source archives. |
| `tests/` | Current and historical regression tests; `tests/upstream/` preserves extracted engine checks. |
| `docs/`, `paper/` | Methods, results, architecture, manuscript and generated reading assets. Narrative does not own executable implementation. |
| `site/` | React reading website and its own build, tests, fonts and components, with unchanged copies of the website list, styles and film stills shared by Will Cook's websites ([family links](../site/README.md#links-to-will-cooks-other-websites)). |
| `system/` | Graph loading/execution and shared provider transport used by current studies. |
| `tools/`, `feedback/`, `variants/`, `codex/` | Graph tools, refinement and data contracts; see [resource consumers](#resource-consumers) and the [historical source map](history/architecture.md#retained-source-owners). |

The root keeps package/build configuration, contributor guidance and stable research entry points. The [layout gate](../scripts/check_structure.py) checks allowed top-level areas, required anchors, misplaced executable/test/cache files and local file destinations in its named entry documents. Import behaviour, archive membership and publication consistency have separate tests. It reads working files by default; `--index` checks the staged version before a commit.

### Resource consumers

Some similarly named resources serve different commands. Choose the path from the consumer that reads it:

| Source path | Consumer and editing responsibility |
|---|---|
| `codex/contracts/` | [Graph loader](../system/core/loader.py) contract expansion, [engine](../system/core/engine.py) contract bundles (including `schema_cp1.json` and `schema_cp2.json`) and web-search policy, and [schema validator](../system/lib/schema_validator.py) settings. Edit live Markdown contract bodies here. |
| `codex/substrate/contracts/*.json` | Schema references in the [graph node definitions](../codex/substrate/nodes/) and the [Evolve handoff](../tools/refinement/run_evolve.py). Use each consumer's declared schema path; similarly named schemas in `codex/contracts/` are not interchangeable. |
| `codex/substrate/nodes/` | Preferred node tree for [graph loading](../system/core/loader.py) and source bindings in the [website](../zenith/web_content.py). The loader falls back to `codex/nodes/` only when the substrate node directory is absent. |
| `codex/nodes/refinement/delta_analyzer.json` and `codex/nodes/refinement/dossier_updater.json` | [run_evolve.py](../tools/refinement/run_evolve.py) reads these files directly when building its prompts, independently of the graph loader's choice. They differ from the substrate definitions and remain live inputs. |
| `master_config.json` | [Runtime](../zenith/runtime.py) run-directory resolution and [engine](../system/core/engine.py) execution/bridge configuration. Keep it at the checkout root used by those consumers. |

Seven unused Markdown mirrors and the duplicate validator configuration under `codex/substrate/contracts/` have been retired; their canonical owners remain under `codex/contracts/` and their original extraction records remain in `retired_files`. CP1/CP2 schema metadata now names the same configuration file that the loader and validator read. The JSON schemas and directly read refinement nodes have the distinct consumers listed above.

### Package, snapshot and publication boundaries

[pyproject.toml](../pyproject.toml) installs six package families: `zenith`, `research`, `system`, `tools`, `feedback` and `variants`. Developer commands in `scripts/` and resources under `codex/`, `docs/`, `paper/` and `examples/` retain their source-checkout paths. Make, CI and the documented replay commands call those paths directly.

[source_snapshot.py](../zenith/source_snapshot.py) preserves its established member policy: implementation Python under `zenith`, `system/core`, `system/lib`, `tools` and `variants`, plus research Python, Codex JSON and `master_config.json` in runtime archives. This is a recorded experiment boundary, not an inventory of every installed package. [Snapshot tests](../tests/test_source_snapshot.py) protect its members, bytes and compatibility imports. Published `examples/` bundles keep their original archived code even when maintained source changes.

Public document and evidence IDs are mapped to source paths by [web_content.py](../zenith/web_content.py); [export_site_snapshot.py](../scripts/export_site_snapshot.py) projects those same owners. A future move must trace imports, relative resource lookups, snapshot membership, Make/CI commands, replay inputs and public source links together. The present layout preserves those interfaces.


## Documentation and evidence

Current findings stay in [status.md](status.md). Maintained native methods, results and funding records live in `docs/studies/native/`; client interpretations live in `docs/studies/client/`. Earlier methods, dated return syntheses and the older status chronology live in `docs/history/`. The paper stays under `paper/`, and graph/image assets keep their existing locations. No new document index replaces the study owners.

`paper/references.json` belongs to the existing manuscript role. It records reviewed editions of the seven cited sources, source-file hashes and locators, the supported claims and their limits, and exact supporting manuscript passages with hashes. `scripts/build_paper_references.py` projects that metadata into the inline bibliography and checks that every citation remains inside a reviewed passage; `--check` reads the working files and `--index` reads staged files. A changed claim requires source re-review before its binding changes. A matching hash identifies the reviewed passage; it does not certify the paper's scientific claim.

The seven sources have different roles: ILF learns a testing policy; CoverUp supplies an authored coverage/error-feedback driver; Voyager retains an executable skill library; STOP optimizes a code-improvement scaffold; Hyperagents edits task and meta-agent code. The two state-learning sources above describe predictive state and weighted-automata methods. Exact version links and source support live in the [paper guide](../paper/README.md#reviewed-sources-and-their-use) and source records. No upstream runtime is imported by citing them. Bounded development-only tester refinement and the frozen-improver comparison remain proposals in [program.md](../program.md), with no new result or unused runtime layer.

The website's artifact-currency labels have a separate owner: `zenith/web_content.py::PAPER_EDITION` pairs the reviewed manuscript SHA-256 with the reviewed PDF SHA-256, and separately pairs the TikZ diagram-source hash with the SVG hash. Inspect every PDF page and the SVG before updating the affected pair together. Citation support and output currency are separate checks; neither hash establishes scientific validity.

The paper's web edition also reads `paper/zenith.tex` through `zenith/web_content.py` and the restricted `zenith/paper_reading.py` converter. The `/api/v1/paper` response exposes `reading` content derived from the manuscript's exact paragraphs, table and citations, which the existing frontend reading components render. The diagram stays with its manuscript owner: `paper/repair-loop.svg` is generated from the existing TikZ figure and served at `/assets/repair-loop.svg`; the caption is projected from TeX. `scripts/export_site_snapshot.py` publishes the same response and SVG for static hosting. These projections share the manuscript as their content owner.

This consolidation moves the former flat `docs/` reports to those owners and updates maintained links. Existing `/api/v1/documents/*` and `/api/v1/evidence/*` IDs remain stable; their source metadata names the new paths. The three client evidence IDs now read each immutable bundle’s `report.json` directly, rather than duplicate JSON files in `docs/`. Old GitHub `main/docs/<moved-name>` links migrate to these paths; historical commit links remain unchanged.

Four frozen protocol files remain at their original `docs/` paths: the v1/v2 client protocols and v4/v5 Progress protocols. Their bytes and logical identities are part of recorded experiments. Published bundles, archived source, prompts and responses under `examples/` remain unchanged. The research-direction route uses `program.md`; the small feed-coverage note is included in the historical data guide.

## Commands and publication

Use the source checkout with an editable install on Linux, macOS or a suitable WSL environment. Graph execution, providers and restricted workers rely on POSIX facilities. The package metadata installs Python modules; it does not turn the manuscript, task resources, scripts or archived experiments into a standalone wheel application.

| Command | Owner and result |
|---|---|
| `make demo` | Small continuation learner reproduction; no provider or network. |
| `make replay` | Behavioral replay of the latest published client condition; no inference. |
| `make test-current` | Current study, shared execution and publication regressions. |
| `make test` | Complete retained suite, including historical studies. |
| `make validate` | Reviewed citations, layout/routes, exported custody hashes and retained native graph validation. |
| `python scripts/build_paper_references.py --check` | Checks the generated bibliography, reviewed source editions and manuscript support bindings; `--index` checks staged copies. |
| `python scripts/build_paper_reading.py` | Renders the manuscript's TikZ figure through Tectonic and Poppler's `pdftocairo` to `paper/repair-loop.svg`; inspect before binding reviewed hashes. |
| `python -m zenith serve …` | Existing read-only website server; build the frontend first. |

[build_client_investigation_report.py](../scripts/build_client_investigation_report.py) and [build_conformance_report.py](../scripts/build_conformance_report.py) own the public study exports and archived-runtime replay. [build_progress_report.py](../scripts/build_progress_report.py) derives the current campaign summary; [analyze_progress_campaign.py](../scripts/analyze_progress_campaign.py) reconstructs paired comparisons. [continue_conformance_budget.py](../scripts/continue_conformance_budget.py) preserves settled responses during an explicitly authorized funding-only continuation.

[export_site_snapshot.py](../scripts/export_site_snapshot.py) exports the existing public API for the same frontend. GitHub Pages is a reading surface, not a remote experiment service. [Website backend](website-backend.md) and [frontend guide](../site/README.md) document its routes.

## Retiring a source path

Trace consumers before retiring a file: imports, node declarations, command entry points, publication routes and source manifests can all depend on its path. Matching bytes alone do not establish that two files serve the same role. For example, the retired `codex/substrate/contracts/epicentre_thesis.md` matched its canonical Markdown body but had a different original source checksum. Its complete original extraction row is retained with its replacement path; the canonical file's provenance has not been substituted for it.

The seven retired Markdown copies are `atomic_tuple.md`, `counter_vector.md`, `epicentre_thesis.md`, `exemplar_state.md`, `prediction_vector.md`, `scorecard.md` and `web_search_disabled.md`. Each resolves to its same-named owner under `codex/contracts/`. Their removal leaves all 75 loaded node definitions and the runtime-archive member policy unchanged. The historical daily controller also fingerprints all `codex/` Markdown and JSON: an existing frozen daily programme must continue in its original checkout. Do not rewrite that programme's recorded fingerprint to accept a cleanup.

The retired validator settings path `codex/substrate/contracts/contract_config.json` resolves to `codex/contracts/contract_config.json`. Both files had identical exported bytes, but only the latter was read by the loader and schema validator. Maintained schema metadata uses that live owner; frozen archives retain the original paths and bytes. The layout gate requires the live configuration and rejects a new copy at the retired path.

Preserve frozen evidence byte for byte. After reviewing maintained-source changes, name every affected extraction member explicitly, for example:

```sh
python scripts/check_extraction.py --refresh research/continuation_learning.py tests/test_continuation_learning.py
python scripts/check_extraction.py
```

Refresh checks every recorded member before writing. An unselected changed or missing member aborts the update; paths under `examples/` cannot be refreshed. Original source paths, custody hashes and retirement records are preserved. New maintained files enter this inventory only when explicitly named. The checker neither discovers files nor decides which ones to remove. A retirement requires a reviewed manifest change retaining the original row and naming its replacement; inspect that diff and run validation. ZIP archives retain their separate bundle-level checks. Never regenerate historical runtime archives to make them match current code.

<a id="active-and-historical-architectures"></a>
<a id="physical-problem-setting"></a>

Earlier links to the physical forecasting design now lead to the [historical architecture](history/architecture.md#physical-problem-setting); those proposed applications remain unimplemented and untested.
