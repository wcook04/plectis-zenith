---
id: "lab_mission"
kind: "mission"
summary: "Mission doctrine for Lab forward reasoning and CP1/CP2 contract-producing execution."
focus_paths:
  - codex/substrate/nodes/lab/seed_state.json
  - codex/substrate/nodes/lab/miner_calc.json
  - codex/substrate/nodes/lab/miner_etf.json
  - codex/substrate/nodes/lab/miner_macro.json
  - codex/substrate/nodes/lab/miner_news.json
  - codex/substrate/nodes/lab/miner_poly.json
  - codex/substrate/nodes/lab/miner_stock.json
  - codex/substrate/nodes/lab/miner_stockgrid.json
  - codex/substrate/nodes/lab/cross_corr_v1.json
  - codex/substrate/nodes/lab/orient.json
  - codex/substrate/nodes/lab/decide.json
  - codex/substrate/nodes/lab/miner_v2_calc.json
  - codex/substrate/nodes/lab/miner_v2_etf.json
  - codex/substrate/nodes/lab/miner_v2_macro.json
  - codex/substrate/nodes/lab/miner_v2_news.json
  - codex/substrate/nodes/lab/miner_v2_poly.json
  - codex/substrate/nodes/lab/miner_v2_stock.json
  - codex/substrate/nodes/lab/miner_v2_stockgrid.json
  - codex/substrate/nodes/lab/cross_corr_v2.json
  - codex/substrate/nodes/lab/director.json
  - codex/substrate/nodes/lab/integrity.json
  - codex/substrate/contracts/schema_cp1.json
  - codex/substrate/contracts/schema_cp2.json
doc_links:
  - codex/doctrine/flows/contracts_and_grading.md
  - codex/doctrine/flows/lab_courtroom_design.md
  - codex/doctrine/operations/codex_change_protocol.md
  - codex/doctrine/components/codex_nodes.md
last_verified_at: "2026-03-07"
---
<!-- DOCTRINE_STRUCTURED_BLOCK -->
## Purpose
Mission doctrine for Lab forward reasoning and CP1/CP2 contract-producing execution.

## Scope
- This doctrine file is `codex/doctrine/missions/lab.md`. [focus:codex/substrate/nodes/lab/orient.json]
- Source of truth includes the Phase 1 Lab spine from `lab_seed_state` through `lab_decide`. [focus:codex/substrate/nodes/lab/seed_state.json] [focus:codex/substrate/nodes/lab/cross_corr_v1.json] [focus:codex/substrate/nodes/lab/orient.json] [focus:codex/substrate/nodes/lab/decide.json]
- Source of truth includes the Phase 1 lane miners. [focus:codex/substrate/nodes/lab/miner_calc.json] [focus:codex/substrate/nodes/lab/miner_etf.json] [focus:codex/substrate/nodes/lab/miner_macro.json] [focus:codex/substrate/nodes/lab/miner_news.json] [focus:codex/substrate/nodes/lab/miner_poly.json] [focus:codex/substrate/nodes/lab/miner_stock.json] [focus:codex/substrate/nodes/lab/miner_stockgrid.json]
- Source of truth includes the Phase 2 lane miners plus the final sink and integrity checks. [focus:codex/substrate/nodes/lab/miner_v2_calc.json] [focus:codex/substrate/nodes/lab/miner_v2_etf.json] [focus:codex/substrate/nodes/lab/miner_v2_macro.json] [focus:codex/substrate/nodes/lab/miner_v2_news.json] [focus:codex/substrate/nodes/lab/miner_v2_poly.json] [focus:codex/substrate/nodes/lab/miner_v2_stock.json] [focus:codex/substrate/nodes/lab/miner_v2_stockgrid.json] [focus:codex/substrate/nodes/lab/cross_corr_v2.json] [focus:codex/substrate/nodes/lab/director.json] [focus:codex/substrate/nodes/lab/integrity.json]
- Source of truth includes the Lab checkpoint contracts. [focus:codex/substrate/contracts/schema_cp1.json] [focus:codex/substrate/contracts/schema_cp2.json]

## Claims
- Canonical claim paths include the full Phase 1 Lab reasoning chain. [focus:codex/substrate/nodes/lab/seed_state.json] [focus:codex/substrate/nodes/lab/cross_corr_v1.json] [focus:codex/substrate/nodes/lab/orient.json] [focus:codex/substrate/nodes/lab/decide.json]
- Canonical claim paths include the full Phase 1 and Phase 2 miner families. [focus:codex/substrate/nodes/lab/miner_calc.json] [focus:codex/substrate/nodes/lab/miner_etf.json] [focus:codex/substrate/nodes/lab/miner_macro.json] [focus:codex/substrate/nodes/lab/miner_news.json] [focus:codex/substrate/nodes/lab/miner_poly.json] [focus:codex/substrate/nodes/lab/miner_stock.json] [focus:codex/substrate/nodes/lab/miner_stockgrid.json] [focus:codex/substrate/nodes/lab/miner_v2_calc.json] [focus:codex/substrate/nodes/lab/miner_v2_etf.json] [focus:codex/substrate/nodes/lab/miner_v2_macro.json] [focus:codex/substrate/nodes/lab/miner_v2_news.json] [focus:codex/substrate/nodes/lab/miner_v2_poly.json] [focus:codex/substrate/nodes/lab/miner_v2_stock.json] [focus:codex/substrate/nodes/lab/miner_v2_stockgrid.json]
- Canonical claim paths include the final Phase 2 sinks and contracts. [focus:codex/substrate/nodes/lab/cross_corr_v2.json] [focus:codex/substrate/nodes/lab/director.json] [focus:codex/substrate/nodes/lab/integrity.json] [focus:codex/substrate/contracts/schema_cp1.json] [focus:codex/substrate/contracts/schema_cp2.json]

## Interfaces
- Focus paths:
  - `codex/substrate/nodes/lab/seed_state.json`
  - `codex/substrate/nodes/lab/miner_calc.json`
  - `codex/substrate/nodes/lab/miner_etf.json`
  - `codex/substrate/nodes/lab/miner_macro.json`
  - `codex/substrate/nodes/lab/miner_news.json`
  - `codex/substrate/nodes/lab/miner_poly.json`
  - `codex/substrate/nodes/lab/miner_stock.json`
  - `codex/substrate/nodes/lab/miner_stockgrid.json`
  - `codex/substrate/nodes/lab/cross_corr_v1.json`
  - `codex/substrate/nodes/lab/orient.json`
  - `codex/substrate/nodes/lab/decide.json`
  - `codex/substrate/nodes/lab/miner_v2_calc.json`
  - `codex/substrate/nodes/lab/miner_v2_etf.json`
  - `codex/substrate/nodes/lab/miner_v2_macro.json`
  - `codex/substrate/nodes/lab/miner_v2_news.json`
  - `codex/substrate/nodes/lab/miner_v2_poly.json`
  - `codex/substrate/nodes/lab/miner_v2_stock.json`
  - `codex/substrate/nodes/lab/miner_v2_stockgrid.json`
  - `codex/substrate/nodes/lab/cross_corr_v2.json`
  - `codex/substrate/nodes/lab/director.json`
  - `codex/substrate/nodes/lab/integrity.json`
  - `codex/substrate/contracts/schema_cp1.json`
  - `codex/substrate/contracts/schema_cp2.json`
- Related docs:
  - `codex/doctrine/flows/contracts_and_grading.md`
  - `codex/doctrine/flows/lab_courtroom_design.md`
  - `codex/doctrine/operations/codex_change_protocol.md`
  - `codex/doctrine/components/codex_nodes.md`
<!-- END_DOCTRINE_STRUCTURED_BLOCK -->
# Lab Mission Theory v3.1

> Convert T-n market state into falsifiable directional predictions by T.  
> Trust the tape before the story. Preserve contradiction before collapsing to consensus.

The Lab is a forward engine. It reads snapshot state at T-n, synthesizes one executable CP1 thesis, and emits machine-checkable CP2 predictions for T. That spine remains unchanged.

v3.1 is an ethos clarification of v3.0. It keeps the same node graph and contract framework, but it sharpens how the system should think:

1. Markets are mechanical ecosystems, not stories.
2. Edge lives in friction between lanes, not in forced agreement.
3. A single epicentre thesis is an execution contract, not a claim that reality has one cause.
4. Contradictions are signals to preserve and manage, not noise to erase.

---

## Mission Ethos

### 1) Mechanical First, Narrative Second
Price is moved by flows, positioning, liquidity, and hedging mechanics before narratives are written about those moves.

### 2) Contradiction Is Information
When lanes disagree, that disagreement is often the highest-value state. It frequently indicates pre-pricing, crowd complacency, or transfer of risk between cohorts.

### 3) CP1 Is a Commitment Layer
The system must output one dominant thesis for execution and auditability. That does not mean the model should pretend uncertainty does not exist.

### 4) Humility Over Storytelling
The output must be explicit about what could make the selected path wrong, and it must carry stress signals forward into CP2.

---

## Architecture — Two-Phase Spine (unchanged)

```text
Phase 1: Evidence Map -> CP1 (Epicentre)
Phase 2: CP1 -> Trajectory Map -> CP2 (Predictions)
Audit:   Entire pipeline -> Integrity Report
```

The structure is stable. What evolves is decision doctrine.

## Contract Boundary

- `lab_decide` emits CP1: the locked `T-n` epicentre checkpoint.
- `lab_director` emits CP2: forward predictions and trade rationale constrained by that CP1.
- Lab CP2 targets may be stocks or ETFs, but they must remain grounded in subject-matching equity evidence (`S_` or `E_`).
- Replaying a historical feed run does not give Lab realized-truth access. It only fixes the `T-n` snapshot provenance.
- Lab does not have access to realized `T` outcomes. If a CP2 statement depends on realized data, it belongs to Oracle, not Lab.

---

## Market Ontology (v3.1)

The system assumes:

1. Short-horizon moves are dominated by mechanics.
2. News is usually contextual and often lagging.
3. Prediction markets and price action are pre-pricing sensors.
4. Divergence across lanes is not a bug. It is a state to exploit.

---

## Epistemic Hierarchy (default)

When lanes disagree, this is the default resolution order. Overrides are allowed but must be defended in `lab_decide`.

| Tier | Lane(s) | Role |
|------|---------|------|
| 1 - Primary | Stockgrid, Calc | Leading mechanical state and regime structure |
| 2 - Confirmatory | ETF, Macro | Cross-asset flow and hard economic constraints |
| 3 - Probabilistic | Polymarket, Stock | Pre-pricing and realized tape confirmation |
| 4 - Contextual | News | Explanatory layer, usually lagging |

Default rule: Tier 1 outranks Tier 4 unless the override case is explicitly argued.

---

## Regime-Conditioned Emphasis (v3.1 clarification)

The hierarchy is a prior, not a constant.

Use calculator regime descriptors (`Energy`, `Directional_Concentration`) to adjust emphasis:

1. High energy + low concentration: mechanics dominate, narrative weight should be minimized.
2. Low energy + high concentration: narrative and macro can carry more explanatory weight.
3. Mixed regime: classify as `DIVERGENT` when evidence is split and preserve both paths.

This does not change required fields. It changes how confidence should be framed.

---

## Contradiction Engine Doctrine

The Lab should behave as a contradiction engine, not a consensus engine.

Operationally:

1. `lab_cross_corr_v1` must surface bifurcations, not smooth them.
2. `lab_orient` must build competing paths for each meaningful bifurcation.
3. `lab_decide` must choose one executable path while preserving explicit opposite-side invalidation.
4. `lab_cross_corr_v2` must surface `THESIS_STRESS` as a first-class output.
5. `lab_director` must not silently proceed through stress.

---

## Pre-Pricing Check (mandatory when News is causal)

Before `lab_decide` treats a news event as causal, run:

1. Polymarket test: Is probability already high enough to indicate pre-pricing?
2. Price-action test: Has the direct exposure already moved materially (for example >1 sigma)?
3. Flow-alignment test: Does Tier 1 flow agree with the narrative direction?

If the narrative fails 2 or more tests:

1. Downgrade narrative confidence.
2. Reflect that downgrade in CP1 framing.
3. Avoid presenting narrative as unchallenged dominant force.

---

## CP1 Confidence Track (required)

Every CP1 output must include:

1. `dominant_evidence_track`: `FLOW_LED` | `NARRATIVE_LED` | `DIVERGENT`
2. `pre_pricing_assessment`: required when news-sourced evidence is cited causally

Interpretation:

| Track | Meaning | Implication |
|------|---------|-------------|
| `FLOW_LED` | Primary grounding is Tier 1 mechanics | Invalidation should focus on flow reversal |
| `NARRATIVE_LED` | Narrative chosen despite weaker flow support | Must explicitly defend Tier 1 override |
| `DIVERGENT` | Material split between top evidence tracks | Competing path becomes primary invalidation branch |

---

## Phase 1 Responsibilities

| Step | Node | Role |
|------|------|------|
| 0 | `lab_seed_state` | Inject topology and baseline priors |
| 1 | 7x miners | Extract atomic tuples only |
| 2 | `lab_cross_corr_v1` | Structural map (swarms, bifurcations, orphans, asymmetries) |
| 3 | `lab_orient` | Build and rank competing causal paths |
| 4 | `lab_decide` | Lock one executable CP1 with explicit contradiction handling |

`lab_decide` must:

1. State tier provenance of the selected path.
2. Resolve all bifurcations explicitly.
3. Defend any Tier 4 over Tier 1 override.
4. Include falsifiable opposite-side invalidation conditions.

---

## Phase 2 Responsibilities

| Step | Node | Role |
|------|------|------|
| 5 | 7x v2 miners | Re-scan through CP1 lens |
| 6 | `lab_cross_corr_v2` | Build target map and surface `THESIS_STRESS` |
| 7 | `lab_director` | Produce constrained CP2 predictions |

`lab_director` is not a prisoner of CP1 narrative wording. It is bound to CP1 contract lineage, but must still respond to Phase 2 stress.

When `THESIS_STRESS` is material, director must:

1. Acknowledge it explicitly in `trade_rationale`, and
2. Either justify continuation or tighten invalidation conditions.

Silent omission is a hard failure.

---

## Contradiction Reconciliation Protocol

When bifurcation is Tier 1 vs Tier 4:

1. Default to Tier 1.
2. If overriding, provide explicit defense.
3. Treat the non-selected side as live invalidation logic, not dead context.

Reference failure: `RUN_2026-03-04` selected narrative crisis pricing while suppressing macro and stress disconfirmation. v3.1 doctrine exists to prevent this specific pattern.

---

## Integrity Hard-Fail Conditions (active doctrine)

| # | Condition |
|---|-----------|
| 1 | `epicentre_thesis` word count < 150 |
| 2 | No resolved `[N]` citations in thesis |
| 3 | No falsifiable invalidation condition |
| 4 | Director `epicentre_thesis` diverges from Decide |
| 5 | Compute-node output includes question marks or self-assessment |
| 6 | Cross-corr summaries include predictive causal claims |
| 7 | Phase 2 annotation collapse (Sentence 2 ~= Sentence 1) |
| 8 | Contradiction amnesia in Decide |
| 9 | Any CP2 prediction missing `target_price` |
| 10 | Direction-target price inconsistency |
| 11 | Engine `SNAPSHOT_PRICE_MISMATCH` |
| 12 | Director ignores material `THESIS_STRESS` |
| 13 | `NARRATIVE_LED` without explicit Tier 1 override defense |
| 14 | News-led causal thesis without pre-pricing assessment |
| 15 | Non-falsifiable prediction (no horizon-linked trigger, target too close to snapshot noise, or outcome framed too broadly) |
| 16 | Prediction introduces a causal driver absent from epicentre_thesis without explicit bridge in trade_rationale |
| 17 | Thesis cites only descriptive/retrospective evidence with no forward transmission or persistence mechanism cited |
| 18 | Core dominant-force claim is effectively uncited (citations decorate paragraph but do not support the central claim) |

---

## Thesis Verification Discipline (v3.1 addition)

Before `lab_decide` locks CP1, the evidence must satisfy minimum coverage thresholds:

1. **Lane diversity**: The epicentre thesis must be supported by evidence from at least 3 distinct lanes (of 7). A thesis grounded in only 1-2 lanes is under-supported.
2. **Causal chain completeness**: Every edge in the transmission path (force → mechanism → consequence) must be traceable to at least one miner tuple or cross-corr finding. Unsupported mechanism steps are speculation gaps.
3. **Falsification readiness**: The invalidation conditions must reference specific observables (prices, spreads, flows) that can be checked at T. Invalidation conditions that cannot be mechanically verified are insufficient.
4. **Alternative margin**: If the gap between the dominant thesis and the best alternative is narrow (both well-evidenced, similar consequence footprint), `lab_decide` should acknowledge the margin explicitly in the thesis and tighten invalidation conditions accordingly.

These are not hard-fail gates — they are calibration discipline. A thesis that scores poorly on these dimensions should carry lower confidence forward into CP2.

---

## Temporal Path Decomposition (v3.1 addition)

CP2 predictions are endpoint claims (directional at T), but prediction quality also depends on the expected path. Direction calls without path awareness frequently fail when the sign is right but the trading path invalidates the position.

When confidence allows, CP2 predictions should include:
- `path_profile`: one of TREND, GAP_AND_FADE, GAP_AND_GO, MEAN_REVERT, WHIPSAW, LATE_DRIFT
- `time_horizon_basis`: why the target is expected to be reached by T rather than only touched intraperiod

If the system has high conviction on close-state direction but low conviction on session path, confidence should be capped and invalidation conditions tightened.

This is advisory, not a hard contract field — but predictions that include path awareness will be scored higher by Oracle's critique.

---

## Draft-and-Verify Epistemic Architecture

The Lab uses a "Draft-and-Verify" pattern rather than pure blind extraction. This is the intended design:

1. **Seed State** (`lab_seed_state`): Compresses all raw feed data into a compact "current scene" report — not a thesis, just a factual overview of what the data shows.
2. **Hypothesis Generation** (`lab_orient`): Reads the seed state and produces a *Forward Draft* — an initial candidate thesis based on a quick read of the compressed regime. The draft is directional, not final.
3. **Directed Mining** (7x miners): Miners receive the draft and hunt for citations that confirm or invalidate it. They are no longer blind. They know what the hypothesis is and actively search for evidence to stress-test it.
4. **Thesis Lock** (`lab_decide`): Takes the miners' evidence and the draft. If evidence supports the draft, locks it as CP1. If evidence contradicts it, revises or replaces the draft with a better-supported thesis.

This mirrors the Oracle architecture in reverse: Oracle uses a "Hindsight Draft" (internet research spoiler) to direct its miners backward; Lab uses a "Forward Draft" (hypothesis from seed state) to direct its miners forward. The symmetry is deliberate — the same Draft-and-Verify loop, applied in opposite temporal directions.

**Why this matters:** Mining without a hypothesis produces unfocused extraction. The draft gives each miner a falsifiable target. If the evidence disproves the draft, that disproof is itself the signal.

---

## Oracle Feedback Loop

Doctrine is adaptive, not static. Oracle should score:

1. Track performance: `FLOW_LED` vs `NARRATIVE_LED` vs `DIVERGENT`
2. Pre-pricing accuracy: did pre-pricing flags improve hit rate?
3. Bifurcation resolution quality: which side won over realized horizon?

If evidence over multiple runs contradicts doctrine, update doctrine.

That doctrine update is still an explicit authoring step. There is no canonical automated `Evolve` mission yet.

---

## Platform Allocation (unchanged)

| Platform | Nodes | Rationale |
|----------|-------|-----------|
| ChatGPT | All miners (P1 + P2) | Extraction precision |
| Gemini | cross_corr, orient, decide, director, integrity | Synthesis and long-context reasoning |

---

## Living Document

This file is doctrine, not scripture. If a failure mode appears repeatedly, add a rule. If a rule creates more false positives than protection, remove or revise it.

Version history:

1. v1.0: Initial two-phase spine
2. v2.0: Contradiction protocol + causal language tiers
3. v2.1: Phase 2 miner anti-bottleneck + integrity additions
4. v3.0: Epistemic hierarchy + pre-pricing + CP1 track + thesis-stress authority
5. v3.1: Ethos clarification: contradiction-first operation, regime-conditioned emphasis, and CP1 as execution contract rather than ontological certainty
