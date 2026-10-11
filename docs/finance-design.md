# Finance grounding for the prediction graph

Zenith is a standalone forecasting experiment. One versioned graph consumes
dated evidence and emits a dated point forecast; a separate evaluator observes
the outcome. Learning proposes a new graph version and compares it with the
old version on frozen, matched episodes. This does not require an independent
Oracle or Evolve inference graph in every experiment.

The closest conceptual finance predecessor we reviewed is **QuantAgent:
Seeking Holy Grail in Trading by Self-Improving Large Language Model**
([Wang et al., 2024, v1](https://arxiv.org/abs/2402.03755v1)). Its writer/judge
inner loop refines financial signal code; an outer loop evaluates that code
on market data and retains outputs, scores and feedback in a knowledge base.
Zenith should borrow the separation of proposed explanations from external
measurement, and preserve unsuccessful attempts. QuantAgent generates alpha
factors, whereas the current Zenith contract produces dated prices. That
distinction does not establish novelty or superior performance.

The later price-analysis paper originally called QuantAgent, now QuantHarness,
is a different work. Paper versions, repository versions and the distinctions
between these systems are recorded in [the finance comparison](finance-related-work.json).

## The smallest useful implementation

```text
version G_k: dated evidence → synthesis → forecast → freeze
                                                   │
later observation ──────────────────────────────── score
                                                   │
recorded trace ─────────────────── observations and hypotheses
                                                   │
                             propose one change → test G_(k+1)
```

The stock adapter performs deterministic data preparation. CP1 summarizes the
available evidence; CP2 chooses target prices. The existing validators enforce
the output contract. Scoring and comparison remain deterministic. A model may
propose an explanation or change, but cannot supply its own accepted score.

Keep two units distinct:

| Unit | Frozen inputs | Output | What may change next |
| --- | --- | --- | --- |
| Prediction episode | Issue time, admitted evidence, target definition, graph, policy, model and provider | Intermediate artifacts and a validated forecast, or an explicit failure | Nothing inside that recorded episode |
| Candidate experiment | Parent version, declared change, dated support, evaluator, compute budget and selection rule | Complete paired losses and coverage, or an incomplete comparison | One reviewed successor version |

The first experiment changes only a forecasting skill: justify movement size
from supplied past returns and shrink weakly supported movements toward zero.
No agent debate, vector database, reinforcement-learning stack or topology
search is required to test this hypothesis. Add a node only when an identified
failure suggests a specific intervention and an ablation can test its value.

## What the finance literature changes

**Separate forecast loss from portfolio returns.** The current score is
absolute target-price error divided by realized positive price, averaged over
targets and then issue dates. It is a descriptive forecast loss. It does not
include position sizing, execution delay, spread, transaction costs, financing
or risk exposure, so Sharpe ratios and investment-performance claims do not
follow from it. Keep no-change and past-one-session momentum references on the
same support. [Evaluation details](finance-validation.md) state which controls
fit this task and which need a later trading experiment.

**State the statistical target before evaluation.** Different losses reward
different point predictions. Absolute relative-price loss is not a request
for the conditional mean price. Before a future prompt/profile revision is
frozen, specify both the target and scoring rule; never change historical scores
to flatter a candidate. This follows the distinction between forecast
directives and scoring functions in
[Gneiting, 2011](https://arxiv.org/abs/0912.0902v2). The current inherited CP2
prompt is not evidence that its output estimates the optimal statistical
functional for that loss.

**Maturity governs feedback availability.** A pending outcome remains pending;
its lesson becomes eligible only after the target observation is available.
Current TradingAgents code implements pending-decision settlement and dated
reflection. Its optional `as_of` guard checks dates (`resolved <= as_of`), not
authenticated intraday availability. Zenith already separates predictions from later truth; any future
cross-episode memory must apply the same availability check to lessons, not just
to raw feeds. Its precise paper/code relationship appears in the comparison
manifest. Do not treat replayed historical prices as proof of contemporaneous
access or absence of model-training contamination.

**An explanation is a candidate, not a diagnosis certificate.** A missing
artifact, excluded input, truncated context or rejected response can be
mechanically witnessed. A forecast miss alone cannot establish whether the
cause was inadequate data, an incorrect inference, irreducible uncertainty or
some combination. Keep the recorded observation separate from the hypothesis;
test a controlled replacement to gather evidence for the latter.

**Search history is part of the experiment.** The single-study ledger records
candidate and failed attempts. Repeatedly inventing new studies on the same
dates would still select on history. The intended next layer is a chronological
outer assessment with an exposure record shared across candidate studies,
followed by prospective forecasts. That layer is not yet implemented. The
current 20-date development and five-date later assessment are a small
integration study, not evidence of a durable market edge.

## Reuse and evidence boundaries

The executable owners are `variants/predictor.py`, `benchmarks/stocknet_native.py`,
`research/cohort.py`, `research/reflection.py`, `feedback/` and the native engine.
The finance review changes their design rationale; it does not add an upstream
framework dependency. [Adaptive finance sources](finance-adaptive-sources.json)
record the reviewed memory, belief-update and factor-search mechanisms. The
[paper](../paper/zenith.tex) cites primary publications and reports the actual
implementation and calibration results.

All portable design, code, source pins and citations live in this repository.
The private parent research archive may retain licensed acquisition copies;
it is neither a runtime dependency nor a required path for reproducing Zenith.
Fresh installation and offline checks follow [the reproduction guide](reproducing.md).
