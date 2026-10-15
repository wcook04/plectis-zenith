# Architecture

Zenith is an unfinished research testbed with three separate studies, shared execution support, and published evidence. The [paper](../paper/zenith.tex) describes their results; [program.md](../program.md) describes the broader goal. The graph-based financial and forecasting profiles have their own [historical architecture](history/architecture.md).

## Current source owners

| Study | Orchestration and source tasks | What changes |
|---|---|---|
| Native investigation and repair | [conformance_study.py](../research/conformance_study.py), [direct_investigation.py](../research/direct_investigation.py), [native_conformance_tasks.py](../research/native_conformance_tasks.py) | Questions produce measurements that can expose a discrepancy; a model proposes a whole-program repair. |
| Client test reuse | [client_investigation_study.py](../research/client_investigation_study.py), [client_investigation_tasks.py](../research/client_investigation_tasks.py) | Earlier investigations produce frozen testers, compared with ordinary reuse and fresh investigation on later clients. |
| Continuation learning | [continuation_learning.py](../research/continuation_learning.py), [demo_continuation_learning.py](../scripts/demo_continuation_learning.py) | An authored rational-linear learner adds state coordinates while retaining the histories and continuations that justify them. |

These mechanisms are not one integrated learner. In particular, the continuation learner is not called by the client-test or native-repair campaigns. Model weights remain fixed.

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

Direct investigation uses the conformance runner's invocation helper. Some retained module names therefore remain in the active import path. Renaming these files alone would not simplify execution and would disturb published import and replay interfaces.

Unused private-system operation registries and the speculative reasoning-packet/plan framework have been removed. The retired `build_reasoning_contract_packet`, `build_reasoning_execution_plan` and `verify_reasoning_execution_plan` commands have no replacement: they were not used by the graph or research runners. Actual graph-contract validation remains available through `python -m tools.meta.factory.validate_reasoning_contracts --check`. Its runtime schema and vocabulary are preserved. Live Markdown contracts have one owner, `codex/contracts/`; archived copies remain in their original experiment bundles.

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
| `site/` | React reading website and its own build, tests, fonts and components. |
| `system/`, `tools/`, `feedback/`, `variants/`, `codex/` | Retained graph/runtime contracts and support; see the [historical source map](history/architecture.md#retained-source-owners). |

The root keeps package/build configuration, contributor guidance and stable research entry points. The [layout gate](../scripts/check_structure.py) checks these roles and links in the entry documents. It reads working files by default; `--index` checks the staged version before a commit.

## Documentation and evidence

Current findings stay in [status.md](status.md). Maintained native methods, results and funding records live in `docs/studies/native/`; client interpretations live in `docs/studies/client/`. Earlier methods, dated return syntheses and the older status chronology live in `docs/history/`. The paper stays under `paper/`, and graph/image assets keep their existing locations. No new document index replaces the study owners.

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
| `make validate` | Layout/routes, exported custody hashes and retained native graph validation. |
| `python -m zenith serve …` | Existing read-only website server; build the frontend first. |

[build_client_investigation_report.py](../scripts/build_client_investigation_report.py) and [build_conformance_report.py](../scripts/build_conformance_report.py) own the public study exports and archived-runtime replay. [build_progress_report.py](../scripts/build_progress_report.py) derives the current campaign summary; [analyze_progress_campaign.py](../scripts/analyze_progress_campaign.py) reconstructs paired comparisons. [continue_conformance_budget.py](../scripts/continue_conformance_budget.py) preserves settled responses during an explicitly authorized funding-only continuation.

[export_site_snapshot.py](../scripts/export_site_snapshot.py) exports the existing public API for the same frontend. GitHub Pages is a reading surface, not a remote experiment service. [Website backend](website-backend.md) and [frontend guide](../site/README.md) document its routes.

Preserve frozen evidence byte for byte. After reviewed changes to maintained source, refresh only current export hashes with `python scripts/check_extraction.py --refresh`, inspect that diff, then validate. Never regenerate historical runtime archives to make them match current code.

<a id="active-and-historical-architectures"></a>
<a id="physical-problem-setting"></a>

Earlier links to the physical forecasting design now lead to the [historical architecture](history/architecture.md#physical-problem-setting); those proposed applications remain unimplemented and untested.
