# Zenith research programme

**Research direction, 13 October 2026.** Learn which distinctions a reasoning
programme must preserve, investigate and act on, using failures to propose and
test local repairs. Forecast every research basket from the shared history of
all baskets and constituents. First-run predictive gain is not the condition
for demonstrating this loop. The [reasoning ontology](docs/reasoning-ontology.md)
owns the current full-graph contracts; [status](docs/status.md) owns measured
results. The earlier reduced basket experiment and System A fixture remain
separate evidence.

## Question and task

Can a directed second pass find useful evidence that the first summaries omitted, and can measured comparisons teach it when to perform those investigations?

Use price and volume histories. Define baskets and their membership rules explicitly; do not present them as traded ETFs. Every target can use the entire permitted universe. Feed partitions are an implementation choice, not a requirement that each sector have its own isolated forecaster or that there be exactly six economic sectors.

Begin with point forecasts of five-trading-session basket returns. For initial-value weights held through that interval, the realised basket return is the weighted sum of constituent returns under the declared price or total-return convention. Membership and weights must be knowable at the cutoff. Derived basket series share lineage with their constituents and do not count as independent evidence.

A modest pilot can use six to eight baskets with tens of constituents each. One year may be a query lookback, but is not the complete training and evaluation sample. Use enough earlier history for model fitting, revision selection and separate evaluation. Sample-size adequacy must follow observed variation across forecast dates, not the number of correlated constituents.

## Prediction and investigation

1. An immutable numerical store holds dated observations, availability clocks, corporate-action conventions, basket definitions and provenance. A deterministic inventory describes coverage and query handles. The whole panel must not be transcribed into the Seed prompt.
2. A common inexpensive numerical procedure forecasts every basket. Include a zero-return reference and a regularised all-universe model fitted only on eligible earlier observations.
3. First-pass readers report bounded observations and unresolved questions. Cross-source synthesis can identify a subgroup, lag or alternative explanation worth checking elsewhere.
4. The feed packet saves the provisional forecast vector; CP1 saves empirical hypotheses and the investigation plan. It is immutable as a record. Its conclusions may be rejected before CP2.
5. Directed readers request cutoff-valid windows and calculations from a small operation catalogue. Initial candidates are constituent breadth/concentration, a lagged relationship, and stability across earlier windows. Each query records its inputs, parameters, result, evidence hash and resource use. Numerical code computes statistics, fits coefficients and produces forecast values; the LLM chooses and interprets investigations.
6. CP2 freezes final forecasts for the same complete target universe, plus the changes from CP1 and their support. An uninvestigated basket keeps its baseline forecast. An unsuccessful investigation can legitimately leave it unchanged.

The apparent relevance of an investigation is not sufficient to adopt a correction. Feature selection, lag search, numerical fitting and validation all occur inside the permitted training history. Correlated proposals need one declared combination rule. Repeatedly searching the same validation period is model selection and cannot be reported as untouched evaluation.

No step must invent a single economic cause. Distinguish an empirical predictive association, a basket accounting identity and an edge between computations. Price histories alone do not establish a causal mechanism.

## What Oracle measures and Evolve learns

Zenith is a passive research forecaster. The same realised outcome can score several computational alternatives committed before that outcome was opened. Testing a change to the forecasting programme does not require identifying the cause of a market movement.

The primary score covers every declared basket, with target weights and any scaling fixed using earlier information. Under squared loss, the realised gain of a candidate is the incumbent's full-universe loss minus the candidate's full-universe loss. A positive result on one date is not evidence of general improvement.

Keep three comparisons separate:

- **CP1 versus CP2:** the realised contribution of the entire second pass, including its extra computation. This does not isolate the value of question conditioning.
- **Directed versus undirected second pass:** both can revisit the same store under the same total budget, but only one receives the cross-source investigation question. This is the first architectural test.
- **Fixed versus revised investigation policy:** freeze one reusable revision after development, then compare it with the incumbent on further identical cutoff packets. This tests learning.

A hindsight repair of an old intermediate message is development evidence. It may nominate a reusable instruction change but cannot validate that change on the same case. When replaying a local change, retain identical upstream records and unaffected branches; rerun affected descendants. Its value is conditional on the surrounding programme and may interact with other changes.

Start with two versioned investigation procedures and a no-change choice. Only after useful differences recur should a controller learn to select procedures from cutoff-visible context. Include unchanged-versus-unchanged runs when model sampling variation matters. A neural controller and smooth numerical prompt settings are unnecessary for the first result.

## Comparisons and acceptance

The graph must compete with an all-universe numerical forecaster and a single adaptive LLM controller using the same store, numerical tools and budget. Give the latter the opportunity to discover its own summaries. Supplying the right summary for free, or denying it retrieval, would not test the complete procedures fairly.

Count model input/output, retrieval, numerical computation, retries and latency; report development and revision-search expense separately. Keep baskets from one forecast date together. Use chronological development, selection and untouched test blocks; exclude training labels that extend across split boundaries. A forecast may use legitimate past history across a boundary, but not future labels. Treat overlapping horizons and nearby origins as dependent.

Historical replay with a pretrained model cannot rule out memorisation merely by masking dates or names. Record that limitation and reserve prospective forecasts as a later check. A synthetic panel using the same interface can test cutoffs and controlled cross-feed relevance; it cannot establish financial forecasting performance.

Retain a revision only under a predeclared full-universe comparison, with uncertainty, failures, regressions and costs visible. If a numerical or single-controller baseline matches the graph more cheaply, the current graph has not earned its complexity. A serial programme can execute the same DAG; exclusive computational capability is not the claim.

## Implementation and research boundary

The current `financial` task profile runs the full native Lab, Oracle and Evolve
missions. Every reasoning stage uses a common validated record, with typed
claims, distinctions, uncertainties and a stage-specific result. Input references
must resolve. Six lane views share one numerical history; they are not six
isolated basket predictors. The two-pass Lab freezes an empirical investigation
at CP1 and final numerical choices at CP2.

Oracle receives the actual intermediate Lab records and later measured errors.
It produces located failure hypotheses, which remain hypotheses. Evolve stages
one instruction change, the expected effect and its evidence. Local replay
freezes unaffected artifacts and reruns descendants. An empty-instruction control
and later matched comparisons separate development effects from prospective
behavior as far as this small experiment permits. No model weights or neural
controller are trained.

The original generic contracts remain available as a separate profile. The
18-node `basket` mission and its earlier comparisons are a diagnostic pilot;
running it through the same engine did not exercise full Oracle decomposition.
Do not describe engine reuse as proof that a particular research graph ran.
Website design remains outside the task.
