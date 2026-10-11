# Learning a reasoning graph

## One predictor, one experiment, successive versions

The design direction is one trainable prediction graph `G`, evaluated on dated
episodes. Lab names its forward execution. Oracle names evaluation and diagnosis
of a frozen attempt. Evolve names a proposed transition from one graph version to
the next. These roles do not require three independently designed prediction
systems or three model-driven DAGs. The existing Oracle and refinement runners
remain implementations we can reuse selectively, not mandatory complexity for
every experiment.

At time A, freeze the evidence that was available, the target definition and
the graph's parameters. Execute the graph and retain its intermediate artifacts
and forecast. At time B, obtain the exact target observation, score the frozen
forecast and inspect the recorded trace. A proposed change produces a new
version for a new controlled run. It cannot change the inputs or prediction of
the old episode.

```text
recorded feeds at A
       │
       ▼
dated evidence admission and join
       │
       ▼
G_k: synthesis skill → forecasting skill → validate and freeze
                                             │
                                             ▼
target observation at B ───────────────────► score
                                             │
frozen intermediate artifacts ────────────► diagnose
                                             │
                                             ▼
                                    propose one change
                                             │
                                             ▼
                                    test G_(k+1)
```

This is the proposed compact shape, not a claim that the current Lab has two
model calls. Current Lab executes 28 nodes, including seven feed/calculation
nodes and two passes of reasoning. The two-skill candidate should reuse CP1
thesis/synthesis and CP2 forecasting contracts, with their deterministic
validators. Feed adapters keep their own dependency structure. In particular,
the existing `lab_seed_state` is a reasoning node; relabeling it as deterministic
data admission would be wrong.

The current variant contract retains every base node and its mandatory ancestry;
mission selection also includes siblings. Hiding branches, reducing an edge
weight or drawing five boxes does not reduce executed calls. Testing a genuinely
smaller graph requires an explicit replacement/ablation contract that preserves
the evidence cutoff, target support, CP2 interface, provenance and evaluator,
while permitting removal of internal reasoning branches. The existing graph is
the baseline until that experiment is implemented and assessed.

The optimization object is `(G, θ)`: a typed directed acyclic graph `G`, and per-node parameters `θ`. A node's parameters include a short skill rule, incoming-context weights, context budget and model choice. Its output contract and evidence cutoff constrain what the operation may do. Language-model calls do not supply the local derivatives that ordinary neural-network backpropagation requires. The current native context budget measures serialized source **characters**, not tokens.

## What the data and skills mean

Do not make every feed share the same raw payload. A price row, news article and
filing can share an evidence envelope while retaining different content types.
The envelope needs source identity and revision, observation/event time, first
availability, acquisition time, units/basis where applicable, missingness and
content hashes. Admission at A checks the clocks and retains exclusions. An
earlier event date does not make a later-published article available at A.

The target is a declared projection of later data: for example, a particular
asset's price at one exact horizon with a fixed currency and adjustment basis.
It is not an unspecified instruction to predict every field in every later
feed. Freeze that target before execution. The no-change baseline uses the
same subject quote and target convention as the graph.

Each skill has typed inputs, an output contract, parameters and a recorded
application to particular evidence. Reuse the existing Lean model
`Skill Parameters Input Output = Parameters → Input → Output → Prop`.
It supports nondeterministic model operations as well as deterministic checks.
Composition and refinement can establish conditional contract properties;
forward-safe context composition excludes declared future/truth inputs; rank
certificates establish acyclicity. Those are useful structural guarantees.
Safety applies to the records' declared availability and context classes; it
does not authenticate source clocks, prove completeness or enforce model obedience.
Empirical accuracy, useful output and causal fault attribution remain separate.
An empty relation is a refinement too, so refinement alone cannot mean
improvement. [The semantics](semantics.md) give the exact proved boundaries.

## Diagnose facts before assigning causes

One bad final prediction cannot uniquely identify the upstream cause. Keep an
observed outcome, a mechanically witnessed fact and a causal hypothesis as
separate fields. Preserve `unknown` when the evidence cannot choose among them.

| Evidence | Mechanical conclusion | What it does not establish |
| --- | --- | --- |
| Exact target observation is missing or has the wrong basis/time | Measurement is pending or has a data gap | That the prediction or reasoning was wrong |
| A required artifact is absent, failed or too late at A | A particular admission/execution condition failed | That acquiring another source would improve the forecast |
| A context-policy receipt marks an input absent, omitted or excerpted | The recorded node received missing or reduced source context under that policy | Whether the omitted content was necessary, or whether the model used retained content |
| Native response validation rejected a bound response | That response failed the declared acceptance contract | A general reasoning failure, or the cause of a later forecast miss |
| An accepted forecast differs from exact later truth | A measured error under the frozen scoring rule | Which ancestor caused it, or whether the outcome was predictable from A |
| A reproducible intermediate calculation violates a checked rule | A localized, witnessed contract/calculation defect | That fixing it improves forecasts on unseen episodes |
| A controlled replacement improves repeated matched runs | Evidence for that intervention on the measured support | Universal node blame, a mathematical gradient, or generalization beyond the assessment |

Separate four data questions: did the information exist by A; did the system
acquire it; did the graph route it; and did the node's prompt retain it? The
first two need source/acquisition evidence. The latter two use graph and context
receipts. A trace showing retained text cannot prove the model understood it.

Keep three records distinct: **acquired source → admitted snapshot → delivered
node context**. `zenith.context.compact_feeds` removes repeated metadata while
preserving feed data. The older `system.lib.feed_compression` can omit middle
price rows, and the reasoning policy can excerpt or omit an incoming edge.
Their selection receipts describe different operations. A historical source
acquired after A can support a qualified replay; it does not prove the system
possessed that information at A. Unknown source clocks remain unknown.

The implementation uses the existing cohort import receipt. Every import,
including a rejected or pre-CP2 attempt, receives a read-only diagnostic view
of the run's recorded artifacts and verified context-policy receipts. Unverified
evidence stays unknown. Diagnostics cannot admit a run or alter its acceptance
result. The receipt counts an **import attempt**: a run never submitted to the
cohort is not silently counted as an observed execution. Feedback itself admits
successful CP2 forecasts and remains the authority for subsequent measurement.

Complete comparisons retain per-issue losses, target coverage and paired
candidate-minus-baseline deltas; negative deltas favor the candidate. Each issue
has equal weight after averaging its declared targets. If any required support
is incomplete, score and delta maps are null and coverage remains visible.
These descriptive differences do not supply uncertainty estimates or causal
attribution. See [the receipt contract](experiments.md#compare-actual-graph-candidates).

Start diagnosis with those factual states. For a data-access hypothesis, restore
one recorded input or context allocation. For a reasoning hypothesis, change
one skill while keeping the input snapshot, model and evaluator fixed. Re-run
the affected computation and downstream forecast; retain failures and compare
paired per-issue losses, coverage and cost. Newly acquiring an additional feed
is a different input ablation protocol: the current cohort freezes one feed
snapshot per issue and must not silently substitute another one.

## Forward evaluation and loss

For an issue time `t`, freeze the evidence available by `t`, execute `G` with `θ`, and retain forecasts for each declared horizon. Resolve each forecast only when its exact target observation matures. Missing required prediction/measurement support or invalid output is a coverage/validity failure; it must not disappear to make average error look better. An absent auxiliary feed remains a recorded input condition; a forecast with valid price support can still be scored.

The input is a collection of feeds, not just a price series. A historical snapshot must identify each feed's source revision, observation time, first availability time, units and missing fields. Price bars, published text, filings and macro releases have different clocks. A financial period end is not the date its filing became available; a current fundamental value cached under an old date is not historical evidence. Preserve unknown availability rather than inventing a timestamp. Extra modalities earn admission through their provenance, not their count.

Begin an aggregation experiment with matched input ablations: the same issue times, assets, horizons and model, with a declared feed present versus absent. StockNet's original timestamped text supports a first prices-versus-prices-plus-text comparison. It does not supply the live system's other five feed lanes. Record clipping and missing text explicitly; a flat aggregation benchmark tests that input interface, while the native cohort adapter tests changes to the actual reasoning graph.

For price targets, the benchmark computes normalized-return errors. Its aggregation gives each issue date equal weight after averaging across the available stocks at that date. Horizon results remain separate. A future combined objective must freeze its horizon weights before candidate selection; an improvement at one horizon cannot conceal deterioration at another through a later change of weights.

The fixed no-change forecast is an essential reference. More elaborate reasoning earns its cost only through measured improvement on matched support. The current benchmark already shows why: a richer OHLCV ridge baseline does not consistently beat no change across horizons. There is no evidence yet that adding language-model nodes will do better.

## Immediate checks and delayed labels

Machine checking has two clocks. Graph cycles, invalid ports, malformed JSON, mismatched schemas, future-dated inputs, unknown model identity and changed frozen inputs can be rejected immediately. Historical target observations are already present in the separate evaluator, so historical prediction errors can be computed after each run. A live forecast has no realized-price error until its declared horizon matures. Before then it is pending; absent or mismatched observations are data gaps.

Use cheap deterministic checks before spending inference calls. Reject an invalid candidate before replay; retain the rejection in the trial ledger. Small exploratory batches can eliminate broken configurations, but they do not replace the preregistered full comparison or justify a generalized learned rule. A repeated reasoning failure suggests an experiment; a reproducible infrastructure defect can be repaired directly with a regression check.

## Backward diagnosis, then a controlled intervention

Accumulate outcomes from a fixed graph and model configuration. The current
measured error classes are direction miss, worse than no change and relative
price error. Keep recorded input/contract defects, such as omitted context or
inconsistent basis, separate from hypotheses such as unsupported reasoning or
overconfidence. Preserve successes and the full denominator. The feedback
implementation starts proposing work only after at least 20 distinct issue
times and repeated failures across three time buckets; this is an operational
gate, not a significance test. A single episode can be inspected immediately;
inspection does not waive that proposal gate.

A downstream error selects upstream traces to inspect. It does not assign causal blame to every ancestor. To test an explanation, change one bounded component and rerun the same subject-side snapshots. Examples are a shorter rule that requires a dated price source, more context allocated to the relevant evidence edge, a new unit-check node, or an additional connection supplying a missing intermediate result. The candidate's forecast must be generated again; changing a provenance label on an old forecast is not an experiment.

For numeric context parameters, coordinate search or finite differences can compare settings. Text rules and graph edits need discrete proposals and execution. Gradient descent is appropriate only for an explicitly differentiable numeric component. A future learned proposal model may use batch failure traces as training examples; the current implementation does not claim to train such a model.

## Acceptance

Freeze data, split membership, evaluator, model configuration, resource budget and candidate identity. Reserve the attempt before execution, retain failures, compare complete common support, and report validity/coverage alongside error. Model routing variation is a confounder: record actual returned models and do not attribute a model change to a skill change. A repeated run with another random response is another measured attempt.

Choose candidates using development evidence. Preserve the final assessment for the frozen selection, then retire that assessment from future tuning. A new rolling period can supply new evidence; repeatedly inspecting the same heldout period cannot. Overlapping horizons and multiple stocks on one date are correlated observations. The current descriptive scores do not provide uncertainty estimates or causal attribution.

Cost and simplicity matter, but their acceptance rules must also be set in advance: calls, tokens, elapsed time, node/edge count and rule length belong beside accuracy. Structural validity is checked separately from empirical usefulness. Lean proves conditional composition and rank-based acyclicity; it does not select the most accurate graph.

## Learn the update procedure without fitting the historical test

The candidate generator is part of what must be evaluated. Repeatedly selecting
the best graph on a development period can fit that period even when each
individual run is temporally valid. Renaming the study does not restore unseen
data. A nested chronological protocol should work as follows:

1. On an inner historical window, identify recurring failures and propose a
   fixed, bounded number of changes. Compare candidates on later inner
   validation windows using identical evidence, model and target support.
2. Freeze the entire selection procedure, selected candidate and resource
   budget before a later outer window. Record every tried candidate, inspected
   date and exposed outcome across studies, including unsuccessful proposals.
3. Ensure development labels have matured before the outer prediction window;
   exclude overlapping label intervals and apply a declared temporal gap.
   Group correlated observations by issue time, not individual stock rows.
4. Evaluate the selected graph and unchanged baseline on the outer window.
   Once inspected, that window belongs to future development history. Finish
   with a fresh prospective period that has not influenced selection.

The native cohort already checks development target times plus `embargo_days`
against the first heldout issue time, prevents a calendar week crossing splits,
freezes candidate budgets and consumes a final-assessment seal. Nested rolling
coordination and cross-study exposure accounting are **not yet implemented**.
They should extend those owners rather than introduce another evaluator.
The current boundary permits equality after the configured embargo. A future
rolling protocol must declare whether a label finalized exactly at the next
issue time is already available; timestamps alone do not resolve publication
or acquisition ordering. Strict interval exclusion is the conservative option.

Repeat an unchanged baseline to estimate model-response variation before
interpreting small improvements. Retain the new paired issue deltas so a later
uncertainty analysis can respect temporal dependence. Neither a count of 20
issues nor a positive mean difference establishes statistical confidence.
Deflated Sharpe measures address a trading-return statistic; they must not be
applied unchanged to this forecast-error objective. Reusable-holdout methods
also depend on assumptions that overlapping, serially dependent market labels
do not automatically satisfy. Historical contamination of model training data
remains a separate limit even after input timestamps are correct.

## What transfers from neural-network learning

The useful analogy is parameterized composition: typed node operations, a
forward execution, stored intermediate values, an external loss and an update
tested on separate data. Reuse the existing skill contracts and traces for
those parts. An intermediate validator supplies a local correctness signal;
its score must not quietly replace the final forecasting objective.

For now, optimize short skill rules and context allocations with bounded,
single-component proposals. Small changes make comparisons easier to interpret
and keep the candidate space constrained; they do not eliminate interactions
or overfitting. Freeze the simplicity rule in advance, such as preferring lower
call cost among candidates meeting a declared accuracy and coverage threshold.
If evidence suggests two changes only work together, predeclare a small
baseline/A/B/A+B comparison on the same support. That tests an interaction
without immediately adopting unrestricted joint search; one-field greedy
updates have no general optimality guarantee.

Textual criticism proposes a search direction. It is not a derivative. Numeric
finite differences or evolution strategies estimate sensitivity through actual
perturbed executions and need repeated measurements when responses are noisy.
Policy-gradient training additionally needs a trainable policy and suitable
probability/training access; ordinary hosted model calls do not provide that
interface. These are possible future update methods, not installed optimizers.

The [source comparison](architecture-sources.md) records which mechanisms
already exist elsewhere and what this implementation actually reuses. The
research question is whether verified temporal evidence and targeted graph
interventions improve later prediction at a fixed resource budget. Graph-shaped
reasoning, textual updates and scored candidate search themselves are prior art.

## The smallest executable learning step

Keep one executor, one evaluator and one proposal interface. The executor freezes
and runs the graph. The evaluator measures the resulting predictions. An agent
reads a complete development feedback packet and proposes a single change; it
does not supply its own score or overwrite the baseline.

`research/reflection.py` implements that interface. It binds the original
feedback proposal, development membership, source files, full resolved evidence,
successes and unresolved counts. A bounded selected-node trace view adds verified
prompt/response/output excerpts and explicit missing/truncated context without
changing the measurement denominator. The compiler checks the measured ancestor graph
and baseline policy, then changes one node's short skill rule, context budget, or
one incoming-edge weight through the existing policy validator. The output is an
ordinary native policy plus its exact before/after change and evidence hashes.
`research/reflection_cohort.py` can carry the verified parent model, provider and
graph identity into a native candidate row for the next study. There is no
additional executor, optimizer dependency or model call.

The agent supplies the proposed rule and its falsifiable hypothesis. The compiler
establishes that the proposal is a bounded, attributable intervention; it cannot
establish that the reasoning is good. A new preregistered cohort must execute the
candidate and baseline on matched inputs. New study names do not erase repeated
selection on the same history, and an examined final period is no longer unseen.

This takes context-bearing criticism from TextGrad, evaluated trajectory
reflection from GEPA, and parent-relative workflow changes from AFlow/ADAS.
Reverse textual feedback, search-tree scheduling and unrestricted code generation
remain unimplemented. They add value only if simpler native proposals are an
observed bottleneck. The [source decisions](architecture-sources.md) distinguish
what was read, adopted, deferred and actually executed.

## What is executable today

| Operation | Source owner |
|---|---|
| Execute or pause the real graph with frozen inputs | `zenith/runtime.py` and the original engine |
| Tune short rules and weighted context budgets | `system/lib/reasoning_policy.py` |
| Insert checks and rewire while retaining required ancestry | `variants/graph.py` |
| Admit price forecasts, resolve exact truth, aggregate failures | `feedback/engine.py` |
| Reserve bounded trials and seal a final probability-mapping assessment | `research/engine.py` |
| Compare completed native graph runs on frozen multi-feed snapshots | `research/cohort.py` |
| Observe submitted attempts and retain paired issue losses without causal blame | `research/diagnosis.py` and `research/cohort.py` |
| Bind development failures and compile one native policy intervention | `research/reflection.py` |
| Reproduce dated price-only baselines and export predictor/truth packets | `benchmarks/stocknet.py` |
| Check declared semantics and finite graph certificates | `formal/ZenithSemantics.lean` and `scripts/check_semantics.py` |

The full-graph comparison consumer is distinct from the probability-mapping adapter. Keep its actual supported states and evidence in `docs/status.md`; do not treat an intervention tag, proposed mutation, successful structural check or synthetic fixture as an observed forecasting improvement.

## Source lessons

Karpathy's [micrograd](https://github.com/karpathy/micrograd/tree/7bc720e951fe422b8f8814aa5aa1b64121d26b4c) makes forward values, graph dependencies, local derivatives and reverse accumulation explicit. Zenith can reuse the discipline of recorded intermediate state and dependency-aware diagnosis, while recognizing that its text operations lack those local derivatives.

[Autoresearch](https://github.com/karpathy/autoresearch/tree/228791fb499afffb54b46200aca536f79142f117) supplies the bounded candidate-change and fixed-evaluator pattern. [GEPA](https://github.com/gepa-ai/gepa/tree/462e437a09be67d2acb59564cc0ea59132f5777c) supplies a more directly relevant interface between candidate components, evaluated trajectories and reflective proposals. [Optuna](https://github.com/optuna/optuna/tree/13a3ff1c78314b6a1117dcee9dbbe54ab66788f9) informs delayed trial reservation/completion. These repositories were cloned and inspected as source material; none is silently launched as an autonomous optimizer or GPU training job.
