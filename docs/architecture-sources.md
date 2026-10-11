# Sources shaping the learning system

## Existing Zenith ideas

The internal `generalized_problem_solving_testbed` owner identifies DAG structure, node instructions, context injection, information acquisition and skill allocation as the optimisation object. Family-09 raw seed expresses that explicitly in the 19 April source cluster, and later describes tracing downstream needs upstream to find where a change belongs. `reasoning_node_contracts` already supplies input, injection, output, oracle, topology, learning and side-effect contracts. This extraction consumes those ideas; it does not claim to originate them.

The executable graph remains the measured baseline. Later graph and policy variants identify exactly what changed. Feedback should suggest alternative explanations and experiments, not automatically attribute a downstream error to every ancestor.

## External methods

[GEPA](https://github.com/gepa-ai/gepa/tree/462e437a09be67d2acb59564cc0ea59132f5777c) provides the closest reflective-search interface: candidate components, batch execution, per-case scores and trajectories, then a small reflective dataset for the component being revised. Its adapter expects higher scores to be better, so an error metric would need an explicit sign or normalisation convention. It supplies an optimiser, not market truth. Zenith retains its own admission, delayed-truth, failure and holdout rules. Source inspected: `src/gepa/core/adapter.py`; not installed or connected to autonomous model spending.

[Optuna](https://github.com/optuna/optuna/tree/13a3ff1c78314b6a1117dcee9dbbe54ab66788f9) separates proposing parameter values from reporting completed trial values through `Study.ask` and `Study.tell`. That separation suits delayed price horizons: a pending forecast cannot masquerade as a completed trial. Numeric context weights and budgets belong in a declared search space; node additions and rewiring need typed structural validation as well. Source inspected: `optuna/study/study.py`; reference only, with no optimiser dependency installed.

[Karpathy autoresearch](https://github.com/karpathy/autoresearch/tree/228791fb499afffb54b46200aca536f79142f117) supplies the small operational pattern: fixed evaluator, bounded experiment, narrowly editable candidate and a log including unsuccessful attempts. Zenith adds temporal admission, grouped market windows, explicit budgets and a sealed final assessment. Its original GPU training program is not this market engine.

Pinned references and license hashes are in `architecture-sources.json`. The imported point-in-time and backtest skills have separate exact-copy license manifests under `third_party/`; their examples do not replace native contracts.

## Assimilated graph-learning methods

The following primary repositories were cloned and their relevant implementations
read. Versioned AFlow, ADAS, TextGrad and GEPA paper sources were read through
their methods and experimental limitations; exact versions are in the manifest.
No upstream program was executed or added as a runtime
dependency. The integration is the native [reflection consumer](../research/reflection.py),
not a claim to reproduce any paper's results.

| Source | What the method does | Zenith decision |
| --- | --- | --- |
| [TextGrad](https://www.nature.com/articles/s41586-025-08661-4), [pinned code](https://github.com/zou-group/textgrad/tree/75e912e210864b61999781778cdf756d4468120f) | Attaches language feedback to variables and their context; traverses predecessors and uses textual updates. Read `variable.py`, LLM backward operations and optimizer prompts. | Retain context-bearing criticism as a candidate explanation. The packet/compiler does not implement backward traversal or numerical differentiation. |
| [GEPA](https://arxiv.org/abs/2507.19457), [pinned adapter](https://github.com/gepa-ai/gepa/blob/462e437a09be67d2acb59564cc0ea59132f5777c/src/gepa/core/adapter.py) | Reflects on scored execution trajectories, proposes component changes and retains complementary candidates. | Keep measured outcomes and case traces together. The current agent proposes the change; the existing evaluator decides its measured value. No GEPA optimizer is installed. |
| [AFlow](https://arxiv.org/abs/2410.10762v4), [pinned code](https://github.com/FoundationAgents/AFlow/tree/3f457218fc716093fe53f6df8a5d5e6379d66346) | Searches code-represented workflows using parent selection, execution feedback and repeated evaluations. The inspected implementation proposes one modification relative to a selected parent. | Keep one parent-relative change and its evidence. Defer tree search until a useful population of native candidates exists; retain temporal splits rather than importing its benchmark partition procedure. |
| [ADAS](https://arxiv.org/abs/2408.08435v2), [pinned code](https://github.com/ShengranHu/ADAS/tree/2702bee8fefda42255efc5be9f60e3bd3db96ae4) | A separate meta agent reads an archive, generates agent programs, reflects and debugs them, then evaluates designs. | Separate proposer from executor and retain proposal lineage. Use admitted JSON policies instead of arbitrary replacement code. Keep rejected/failed measured trials in the native ledger. |

The resulting loop is small: **complete development feedback → one proposal →
native policy validation → new matched graph runs → existing evaluator**.
Source hashes, graph identity, chronology and explicit membership are checked
at the boundary. They establish what was compared, not whether a textual
explanation is causal or a result generalizes. A new study does not reset
cumulative selection bias. Comparative claims require actual controlled runs
against the cited methods; source assimilation alone supplies no such result.
