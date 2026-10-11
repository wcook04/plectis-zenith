# Sources shaping the learning system

## Existing Zenith ideas

The internal `generalized_problem_solving_testbed` owner identifies DAG structure, node instructions, context injection, information acquisition and skill allocation as the optimisation object. Family-09 raw seed expresses that explicitly in the 19 April source cluster, and later describes tracing downstream needs upstream to find where a change belongs. `reasoning_node_contracts` already supplies input, injection, output, oracle, topology, learning and side-effect contracts. This extraction consumes those ideas; it does not claim to originate them.

The executable graph remains the measured baseline. Later graph and policy variants identify exactly what changed. Feedback should suggest alternative explanations and experiments, not automatically attribute a downstream error to every ancestor.

## External methods

[GEPA](https://github.com/gepa-ai/gepa/tree/462e437a09be67d2acb59564cc0ea59132f5777c) provides the closest reflective-search interface: candidate components, batch execution, per-case scores and trajectories, then a small reflective dataset for the component being revised. Its adapter expects higher scores to be better, so an error metric would need an explicit sign or normalisation convention. It supplies an optimiser, not market truth. Zenith retains its own admission, delayed-truth, failure and holdout rules. Source inspected: `src/gepa/core/adapter.py`; not installed or connected to autonomous model spending.

[Optuna](https://github.com/optuna/optuna/tree/13a3ff1c78314b6a1117dcee9dbbe54ab66788f9) separates proposing parameter values from reporting completed trial values through `Study.ask` and `Study.tell`. That separation suits delayed price horizons: a pending forecast cannot masquerade as a completed trial. Numeric context weights and budgets belong in a declared search space; node additions and rewiring need typed structural validation as well. Source inspected: `optuna/study/study.py`; reference only, with no optimiser dependency installed.

[Karpathy autoresearch](https://github.com/karpathy/autoresearch/tree/228791fb499afffb54b46200aca536f79142f117) supplies the small operational pattern: fixed evaluator, bounded experiment, narrowly editable candidate and a log including unsuccessful attempts. Zenith adds temporal admission, grouped market windows, explicit budgets and a sealed final assessment. Its original GPU training program is not this market engine.

Pinned references and license hashes are in `architecture-sources.json`. The imported point-in-time and backtest skills have separate exact-copy license manifests under `third_party/`; their examples do not replace native contracts.
