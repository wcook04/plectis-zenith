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
   State concrete, time-bounded, observable conditions that would break the thesis.
   Each invalidation must include: (a) the specific observable (price level, spread, flow reversal, etc.), (b) the time window within which it must occur, and (c) the asset or instrument on which it is observable.
   Vague hedges ("unless conditions change", "if sentiment shifts") are not valid invalidation conditions.
6. **Dominance Scope** (v1.1 addition)
   Explicitly state: (a) what the thesis does NOT claim (negative scope), and (b) which lanes or asset classes are outside the thesis's transmission path. This prevents thesis creep where the dominant force is silently extended to explain everything.

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
