[JUDGMENTAL QUANTILE FORECAST CONTRACT]
This explicit branch takes precedence over causal-only and price-formula-only requirements below. A predictive belief does not require an identified cause. Use forecast_basis="JUDGMENTAL", dominant_evidence_track="JUDGMENTAL", decision_status="FORECAST" with forecast_quantiles={method:"evidence_conditioned_quantiles_v1",calendar:"XSHG" or "XNYS",units:"simple_return_fraction",calibration_status:"UNVALIDATED",targets:[{target_id:<opaque stock ID>,q10:<number>,q50:<number>,q90:<number>,evidence_refs:[<original [N] refs>],reasoning:<evidence-to-estimate explanation and uncertainty>}]}. Exact fields are required. Every target needs original STOCK grounding. Preserve numeric/leading-zero identifiers. Quantiles are ordered 10th/50th/90th percentiles of next-session raw close return, not confidence in a causal story. q50 maps to target_price=snapshot_price*(1+q50). Units are fractions: .01 is 1 percent. A zero median is valid FLAT, not abstention or a guarantee of no movement. Values must be finite, greater than -1 and at most 10 (numeric safety limit, not estimated risk).
CP1 freezes the entire quantile object. Director and Oracle copy it exactly, with the same original citation mapping and all targets; no hindsight refit. Each prediction uses source currency/basis, source issue timestamp, next actual exchange close, and UP/DOWN/FLAT according to the sign of q50. Cross-correlation maps all locked targets; zero medians use direction_consensus N/A. Phase-two miners audit observations and reasoning without changing frozen estimates. Integrity checks evidence and uncertainty honestly, not unsupported causal certainty. Missing expectations are unknown; large profit growth is not automatically an earnings surprise, entity association is not ownership, and an already public result is not automatically new information. Cite every factual basis; explicitly distinguish subjective numerical judgments from observed quantities or trained calibration. Unknown signals may justify retaining a price-only reference, not omitting declared targets.
Oracle scores the ORIGINAL quantiles and median, retains numeric errors even with an unresolved cause, and proposes only future-tested lessons. Three quantiles are a partial forecast, not a complete probability distribution. Median absolute error and quantile pinball loss measure different aspects; coverage alone cannot establish calibration. Never claim learned advantage merely because this branch is accepted.

# Empirical branch

[EMPIRICAL FORECAST CONTRACT]
This explicit branch takes precedence over causal-only requirements below. Legacy forecasts have forecast_basis="CAUSAL". A FORECAST may instead set forecast_basis="EMPIRICAL" and dominant_evidence_track="EMPIRICAL" to test an outcome mapping without claiming an identified market cause. The first supported control is empirical_rule={method:"trailing_mean_return_v1",lookback_returns:<integer 1..19>,scale:<nonzero number -1..1>,max_abs_return:<positive fraction <=0.1>,target_ids:[<stock symbols>],evidence_refs:[<exact [N] refs grounding every target>],selection_basis:<why this rule was selected before truth>,calibration_status:"UNVALIDATED"}. All fields are required; no extra rule fields. For each target take the last lookback_returns+1 consecutive as-of scalar prices, calculate the arithmetic mean of their simple returns (p[i]/p[i-1]-1), multiply by scale, clip to +/-max_abs_return, and set target_price=last_price*(1+clipped_return). Horizon is the next XNYS close. The engine independently checks the calculation, history boundary, source IDs and exact target set. Zero return is not an epsilon directional forecast; abstain if the rule cannot produce supported nonzero targets. These parameters are an experimental control, not fitted skill or a claim of edge. The full Lab still reviews all available feeds; this control's numeric mapping uses prices only and cannot establish the value of news. Retain evidence citations and ordinary word counts. In EMPIRICAL, epicentre_thesis states the testable predictive hypothesis, its input limits, rule selection and falsification, rather than inventing a dominant cause. Missing causal identification alone does not force ABSTAIN. Use ABSTAIN if usable inputs or an explicit supported mapping are absent. Do not change the rule after seeing later outcomes. Ordinary CAUSAL forecasts retain their existing requirements.

The causal thesis contract below applies to CAUSAL forecasts. An empirical thesis must describe and test its declared rule instead.

# Epicentre Thesis Contract v1.0

## Purpose

Define a strict semantic contract for `epicentre_thesis` so CP outputs are not generic summaries.

The thesis must identify the **single dominant market force at `T-n`** that is expected to produce the
largest directional consequences by `T` (the prediction horizon).

---

## Core Definition

`epicentre_thesis` is the causal center-of-gravity statement for the run:

1. What force dominates now (`T-n`)
2. Why it dominates relative to competing forces
3. Which consequences it should transmit into `T`
4. What would falsify that causal story

If it does not satisfy all four, it is not a valid epicentre thesis.

---

## Required Semantic Components

Every `epicentre_thesis` must explicitly include:

1. **Dominant Force Statement**
   Name one force (not a list) as primary driver.
2. **Dominance Justification**
   Explain why this force outranks alternatives in current data.
3. **Transmission Path**
   Describe the mechanism from force -> affected lanes/assets.
4. **`T` Consequence Map**
   State expected directional consequences at horizon `T`.
5. **Invalidation Conditions**
   State concrete conditions that would break the thesis.

---

## Prohibitions

- No multi-thesis outputs presented as co-equal "main drivers."
- No hindsight phrasing in Lab CP outputs (must be from `T-n` perspective).
- No prediction list detached from causal chain.
- No evidence dumping without selecting a dominant force.

---

## Stage Responsibilities

### Cross-Correlation Stage (`lab_cross_corr_v1`)

- Must find structural swarms, bifurcations, orphans, and confidence asymmetries across Phase 1 miner outputs.
- Must not form hypotheses or interpret market meaning. Output is structural only.

### Orient Stage (`lab_orient`)

- Must surface candidate causal chains from cross-correlation structure.
- Must rank candidate epicentres by explanatory power and breadth.
- Must not finalize the thesis; only prepare candidate force structure.

### Decide Stage (`lab_decide`)

- Must synthesize one dominant epicentre from all Phase 1 evidence — not pick from Orient's list.
- The thesis emerges from total synthesis. It is the singular gravitational point, not the winner of a hypothesis tournament.
- Must lock CP1 output: `evidence_dictionary` + `epicentre_thesis` prose (≥150 words with [N] citations).

### CP2 Emitters (`lab_director`, `oracle_cp2_emitter`)

- Must ensure `predictions_t` are direct consequences of `epicentre_thesis`.
- Must ensure `trade_rationale` narrates consequence flow from the thesis, not isolated calls.

---

## Relationship to CP Contracts

- `schema_cp1.json` defines structural requirements and citation/word-count checks.
- `schema_cp2.json` extends CP1 with predictions and trade rationale.
- This contract defines the semantic meaning of `epicentre_thesis` used by both CP1 and CP2.

## Explicit abstention

The causal thesis requirements above govern `decision_status: FORECAST` (also
the legacy default). When no supported forward thesis exists, use the explicit
`ABSTAIN` branch in schema_cp1/schema_cp2. Keep cited observed evidence and a
150-word explanation of the unavailable support, unsupported claims and concrete
reconsideration condition. This is an evidence-backed no-call, not a causal thesis
made out of missingness. Director preserves it with empty predictions and a cited
no-trade rationale. Oracle separates intentional abstention from execution failure
and evaluates missed earlier opportunities without importing later facts as support.
Abstention supplies no zero-error observation and cannot win a fixed-support cohort.
