# Zenith runtime boundary

Zenith is a standalone extraction of the existing market research system. The authored node JSON remains the graph authority. `PhysicalLoader` resolves node inheritance, contracts and dossier context; `compute_waves` validates and schedules dependencies; `GodModeEngine` executes tools and reasoning, validates responses and writes resumable artifacts.

## The research cycle

| Stage | Existing owner | Responsibility |
|---|---|---|
| Feeds | `codex/substrate/nodes/feeds` | Stock, ETF, macro, news, Polymarket, Stockgrid and Calculator envelopes |
| Lab | `codex/substrate/nodes/lab` | Two passes across seven lanes, cross-correlation, CP1 thesis, CP2 predictions and integrity audit |
| Oracle | `codex/substrate/nodes/oracle` | Bind separate subject/truth runs, deterministic differences, reconciliation, hindsight and critique |
| Evolve | `tools/refinement/run_evolve.py` | Propose changes from the Oracle quartet; reviewed, allowlisted dossier application |
| Surveillance | `codex/substrate/nodes/surveillance` | Retained authored monitoring family; requires separate execution configuration |

The current graph contains 71 nodes. Lab scope contains 28 nodes in 11 waves including its seven feeds; Oracle scope contains 31 nodes in seven waves. Selecting a target includes all siblings in its mission and upstream dependencies. `lab_integrity` therefore runs after `lab_director`; a target is not an ancestor-only subgraph request.

Actual Lab ordering is feed evidence → seed → seven first-pass miners → cross-correlation → orientation → CP1 → seven second-pass miners → cross-correlation → CP2 → integrity. Some historical doctrine sketches put orientation before miners. Runtime dependencies win over those sketches.

## Agent and model interfaces

Inspection and planning use loader/governance directly and never instantiate the engine. Execution uses the same engine for captured responses, external-agent handoffs and explicitly selected providers. Shared prompt assembly includes temporal substitution, dependency envelopes, policy text, audits and JSON guardrails. External responses must return through that engine's validation path; handoff files are not permission to synthesize successful artifacts.

A paused reasoning node exposes the assembled prompt and its hash. Import binds the response to that request; resume processes dependencies and schema validation. The run keeps the model identity and evidence needed to distinguish a model failure from missing data. Browser integration is optional legacy compatibility, not an inspection dependency.

## Scientific improvement

The `research` harness owns frozen experiment specifications and all-attempt trial accounting. The native replay evaluator retains event matching, admission, delayed truth, temporal split and Brier scoring contracts. Development results can nominate a candidate. A separate, single-use holdout assessment cannot silently become the next tuning set. `program.md` tells agents how to operate this loop.

Changes to graph structure, prompts, context compression, providers and dossiers require different declared hypotheses. Keep comparisons fair by fixing input snapshots, evaluator version and budget. A complete trial ledger is evidence of what was tried; a good development score alone is not evidence of generalization. The cohort adapter in `research/cohort.py` imports actual native CP2 runs under frozen graph/policy/input/model contracts, checks complete matched support through `feedback`, and exposes the next native commands for agents. It does not itself make inference calls or enforce a spend limit before provider calls.

## Extraction limits

The parent repository's kernel, Task Ledger, Station web server and private runtime state are outside this checkout. Config defaults are sanitized and dossiers start empty. Native file layout is retained because contract/policy loaders resolve source-relative assets. Use an editable checkout; a self-contained wheel is not a verified distribution format yet.

Synthetic fixtures prove execution and contract behavior. The small licensed UCI benchmark proves deterministic historical scoring. Neither establishes a successful live full-DAG market run. Historical LLM benchmarks additionally face training-data contamination; prospective frozen predictions are the stronger evidence lane.
