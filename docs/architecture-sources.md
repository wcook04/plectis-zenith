# Sources shaping the learning system

## Existing Zenith ideas

The internal `generalized_problem_solving_testbed` owner identifies DAG structure, node instructions, context injection, information acquisition and skill allocation as the optimisation object. Family-09 raw seed expresses that explicitly in the 19 April source cluster, and later describes tracing downstream needs upstream to find where a change belongs. `reasoning_node_contracts` already supplies input, injection, output, oracle, topology, learning and side-effect contracts. This extraction consumes those ideas; it does not claim to originate them.

The executable graph remains the measured baseline. Later graph and policy variants identify exactly what changed. Feedback should suggest alternative explanations and experiments, not automatically attribute a downstream error to every ancestor.

The earlier family-02 Lab notes add two constraints: learn recurring classes of
mistakes across dates, and do not give a historical predictor the explanations
Oracle discovered after seeing the outcome. The earlier prediction-chain notes
also require preserving the original age of evidence through successive runs.
These ideas now inform the separate acquisition, admission and context records
in [the learning design](learning-design.md). Raw operator material stays in its
existing private source; this repository carries the resulting design and
executable checks, not a second raw-seed archive.

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

## Neural learning and selection safeguards

The follow-up review inspected primary methods and selected implementation
paths. These are design transfers, not dependencies or reproduced results.

| Source | Transfer to Zenith | Boundary |
| --- | --- | --- |
| [Graph of Thoughts](https://ojs.aaai.org/index.php/AAAI/article/view/29720), [implementation](https://github.com/spcl/graph-of-thoughts) | Its graph of operations, retained reasoning state, aggregation and scoring are direct prior art for graph-shaped reasoning. | A reasoning DAG itself is not a novelty claim. |
| [Agent Lightning](https://arxiv.org/abs/2508.03680v1), [inspected current code](https://github.com/microsoft/agent-lightning/tree/69f5a40b36d9bff646b8e7a5532e8b78bd41eaf9) | Keep execution traces separate from the update method, with component inputs, outputs and external rewards. | The original method assigns the same final return to each action. The inspected later code computes a rollout advantage and broadcasts it to its transitions; this is an update signal, not causal fault identification. Neural policy training needs training access and resources absent from ordinary API inference. |
| [Trace / OptoPrime](https://arxiv.org/abs/2406.16218v2), [implementation](https://github.com/microsoft/Trace/tree/8190d032e43ffe18943a8cad9ea9ee99e43d6773) | Executed graph values, operator descriptions and feedback form a report for proposing heterogeneous parameter updates. Keep proposing separate from applying. | This is especially close prior art. Our bounded selected-node view is not its complete dynamic TraceGraph. Keep native admission and matched evaluation; defer full-graph prompts and arbitrary generated-code execution. |
| [MIPRO paper](https://arxiv.org/abs/2406.11695v2), [current DSPy MIPROv2 code](https://github.com/stanfordnlp/dspy/tree/f1260ff14610286cb295c7d3a5ee2cbfd0ba5cb9) | Separate grounded instruction proposals from selection among a fixed candidate bank; require full development comparison before selecting a candidate. | Current categorical TPE, demonstrations and minibatch scheduling are deferred. Successful final answers do not certify every intermediate trace as a valid demonstration. The paper and later implementation are distinct versions. |
| [Evolution Strategies](https://arxiv.org/abs/1703.03864v2), [official implementation](https://github.com/openai/evolution-strategies-starter/tree/951f19986921135739633fb23e55b2075f66c2e6) | Compare positive and negative perturbations on matched support when testing numeric context parameters. | The estimator concerns a smoothed numeric objective. It is neither differentiation through opaque model calls nor causal blame; discrete rules/topology need another proposal mechanism. Shared perturbation noise does not control provider randomness. No ES optimizer is integrated. |
| [Cawley and Talbot, model-selection overfitting](https://www.jmlr.org/papers/volume11/cawley10a/cawley10a.pdf), [nested-selection example](https://github.com/scikit-learn/scikit-learn/blob/102e5daf66759cf896beeee229d1bf7c80ab2ba4/examples/model_selection/plot_nested_cross_validation_iris.py) | Treat candidate proposal and selection as part of fitting, inside an outer assessment. | Replace the example's shuffled folds with chronological ones; nested rolling coordination remains planned. |
| [PurgedWalkForwardCV and purge](https://github.com/sam31415/timeseriescv/blob/cb04fb6ea7a0b2c15920ca253f882336fe336ba8/timeseriescv/cross_validation.py) | Track prediction and label-evaluation intervals and exclude label overlap. Reuse native cohort chronology and embargo checks. | Its preceding-label test is strict `<`; native cohort permits equality after its declared embargo. Equality needs an explicit availability/ordering convention. No splitter was imported. |
| [Deflated Sharpe Ratio](https://www.davidhbailey.com/dhbpapers/deflated-sharpe.pdf), [inspected reference implementation](https://github.com/rubenbriones/Probabilistic-Sharpe-Ratio/blob/7c65ea513df575a93a3a474b6e3c2a0a9e724607/src/sharpe_ratio_stats.py) | Preserve the full search history, including failed candidates and selection exposure across studies. | Its statistic and assumptions concern Sharpe ratios of returns. Applying it to current price-error scores would be invalid; cross-study exposure accounting remains planned. |
| [Adaptive holdout reuse / Thresholdout](https://arxiv.org/abs/1506.02629v2) | A revealed assessment is no longer untouched; record exposure and use fresh prospective periods. | Its restricted query interface, calibrated noise and budget are unimplemented, and its statistical assumptions do not automatically hold for correlated market labels. |

Agent Lightning's 2025 paper and the pinned 2026 implementation are separate
source versions. The paper's data, algorithm and experimental sections were
read; the code inspection covered `rollout_level_advantage.py` and
`per_rollout_loss.py`. Their correspondence is limited to the stated design
mechanisms. No model training, dependency installation or upstream script ran.

## Novelty is an open research question

Graph execution, modular skills, textual optimization and candidate search
already have substantial prior art. The candidate contribution here is an
inspectable combination: declared temporal evidence, typed skill composition,
diagnostic facts separated from causal hypotheses, and controlled graph
interventions evaluated against later observations. This review does **not**
establish that combination as new or superior.

To assess it, name one precise claim and compare equal-budget baselines:
unchanged native graph, a compact graph, a simple single-rule search, and a
selected prior-art optimizer adapted to the same evidence and evaluator.
Ablate the proposed diagnostic guidance and temporal guards separately. Report
forecast error, target coverage, failed attempts, calls and cost on untouched
assessment periods. Novelty remains unassessed until the closest prior art is
compared at that level; a literature search alone cannot certify it.
