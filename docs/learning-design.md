# Learning a reasoning graph

The optimization object is `(G, θ)`: a typed directed acyclic graph `G`, and per-node parameters `θ`. A node's parameters include a short skill rule, incoming-context weights, context budget and model choice. Its output contract and evidence cutoff constrain what the operation may do. This is a trainable computational graph; language-model calls do not supply the derivatives that ordinary neural-network backpropagation requires.

## Forward evaluation and loss

For an issue time `t`, freeze the evidence available by `t`, execute `G` with `θ`, and retain forecasts for each declared horizon. Resolve each forecast only when its exact target observation matures. Missing evidence or invalid output is a coverage/validity failure; it must not disappear to make average error look better.

The input is a collection of feeds, not just a price series. A historical snapshot must identify each feed's source revision, observation time, first availability time, units and missing fields. Price bars, published text, filings and macro releases have different clocks. A financial period end is not the date its filing became available; a current fundamental value cached under an old date is not historical evidence. Preserve unknown availability rather than inventing a timestamp. Extra modalities earn admission through their provenance, not their count.

Begin an aggregation experiment with matched input ablations: the same issue times, assets, horizons and model, with a declared feed present versus absent. StockNet's original timestamped text supports a first prices-versus-prices-plus-text comparison. It does not supply the live system's other five feed lanes. Record clipping and missing text explicitly; a flat aggregation benchmark tests that input interface, while the native cohort adapter tests changes to the actual reasoning graph.

For price targets, the benchmark computes normalized-return errors. Its aggregation gives each issue date equal weight after averaging across the available stocks at that date. Horizon results remain separate. A future combined objective must freeze its horizon weights before candidate selection; an improvement at one horizon cannot conceal deterioration at another through a later change of weights.

The fixed no-change forecast is an essential reference. More elaborate reasoning earns its cost only through measured improvement on matched support. The current benchmark already shows why: a richer OHLCV ridge baseline does not consistently beat no change across horizons. There is no evidence yet that adding language-model nodes will do better.

## Immediate checks and delayed labels

Machine checking has two clocks. Graph cycles, invalid ports, malformed JSON, mismatched schemas, future-dated inputs, unknown model identity and changed frozen inputs can be rejected immediately. Historical target observations are already present in the separate evaluator, so historical prediction errors can be computed after each run. A live forecast has no realized-price error until its declared horizon matures. Before then it is pending; absent or mismatched observations are data gaps.

Use cheap deterministic checks before spending inference calls. Reject an invalid candidate before replay; retain the rejection in the trial ledger. Small exploratory batches can eliminate broken configurations, but they do not replace the preregistered full comparison or justify a generalized learned rule. A repeated reasoning failure suggests an experiment; a reproducible infrastructure defect can be repaired directly with a regression check.

## Backward diagnosis, then a controlled intervention

Accumulate failures from a fixed graph and model configuration. Group them by observed failure: stale evidence, missing context, unsupported conclusion, inconsistent units/basis, overconfidence, wrong direction, or large price error. Preserve successes and the full denominator. The feedback implementation starts proposing work only after at least 20 distinct issue times and repeated failures across three time buckets; this is an operational gate, not a significance test.

A downstream error selects upstream traces to inspect. It does not assign causal blame to every ancestor. To test an explanation, change one bounded component and rerun the same subject-side snapshots. Examples are a shorter rule that requires a dated price source, more context allocated to the relevant evidence edge, a new unit-check node, or an additional connection supplying a missing intermediate result. The candidate's forecast must be generated again; changing a provenance label on an old forecast is not an experiment.

For numeric context parameters, coordinate search or finite differences can compare settings. Text rules and graph edits need discrete proposals and execution. Gradient descent is appropriate only for an explicitly differentiable numeric component. A future learned proposal model may use batch failure traces as training examples; the current implementation does not claim to train such a model.

## Acceptance

Freeze data, split membership, evaluator, model configuration, resource budget and candidate identity. Reserve the attempt before execution, retain failures, compare complete common support, and report validity/coverage alongside error. Model routing variation is a confounder: record actual returned models and do not attribute a model change to a skill change. A repeated run with another random response is another measured attempt.

Choose candidates using development evidence. Preserve the final assessment for the frozen selection, then retire that assessment from future tuning. A new rolling period can supply new evidence; repeatedly inspecting the same heldout period cannot. Overlapping horizons and multiple stocks on one date are correlated observations. The current descriptive scores do not provide uncertainty estimates or causal attribution.

Cost and simplicity matter, but their acceptance rules must also be set in advance: calls, tokens, elapsed time, node/edge count and rule length belong beside accuracy. Structural validity is checked separately from empirical usefulness. Lean proves conditional composition and rank-based acyclicity; it does not select the most accurate graph.

## What is executable today

| Operation | Source owner |
|---|---|
| Execute or pause the real graph with frozen inputs | `zenith/runtime.py` and the original engine |
| Tune short rules and weighted context budgets | `system/lib/reasoning_policy.py` |
| Insert checks and rewire while retaining required ancestry | `variants/graph.py` |
| Admit price forecasts, resolve exact truth, aggregate failures | `feedback/engine.py` |
| Reserve bounded trials and seal a final probability-mapping assessment | `research/engine.py` |
| Compare completed native graph runs on frozen multi-feed snapshots | `research/cohort.py` |
| Reproduce dated price-only baselines and export predictor/truth packets | `benchmarks/stocknet.py` |
| Check declared semantics and finite graph certificates | `formal/ZenithSemantics.lean` and `scripts/check_semantics.py` |

The full-graph comparison consumer is distinct from the probability-mapping adapter. Keep its actual supported states and evidence in `docs/status.md`; do not treat an intervention tag, proposed mutation, successful structural check or synthetic fixture as an observed forecasting improvement.

## Source lessons

Karpathy's [micrograd](https://github.com/karpathy/micrograd/tree/7bc720e951fe422b8f8814aa5aa1b64121d26b4c) makes forward values, graph dependencies, local derivatives and reverse accumulation explicit. Zenith can reuse the discipline of recorded intermediate state and dependency-aware diagnosis, while recognizing that its text operations lack those local derivatives.

[Autoresearch](https://github.com/karpathy/autoresearch/tree/228791fb499afffb54b46200aca536f79142f117) supplies the bounded candidate-change and fixed-evaluator pattern. [GEPA](https://github.com/gepa-ai/gepa/tree/462e437a09be67d2acb59564cc0ea59132f5777c) supplies a more directly relevant interface between candidate components, evaluated trajectories and reflective proposals. [Optuna](https://github.com/optuna/optuna/tree/13a3ff1c78314b6a1117dcee9dbbe54ab66788f9) informs delayed trial reservation/completion. These repositories were cloned and inspected as source material; none is silently launched as an autonomous optimizer or GPU training job.
