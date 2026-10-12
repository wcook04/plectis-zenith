# Hypothesis Slug Contract v2.0

## Purpose

Define how `[H:slug_name]` identifiers are created and used for **Orient path hypotheses** in the current Lab pipeline.

This contract is guidance for cross-node traceability. It is not a runtime schema validator.

## Syntax

`[H:slug_name]`

## Slug Rules

- 2-5 words, `snake_case`, lowercase, ASCII only
- 30 characters max for `slug_name`
- Semantically descriptive (the causal idea should be clear from the slug)
- Unique within a run

## Where Slugs Live In Lab (Current Architecture)

1. `lab_cross_corr_v1`:
   - Produces structural findings only (swarms, bifurcations, orphans)
   - Does **not** mint hypothesis slugs
2. `lab_orient`:
   - Mints slugs for candidate path hypotheses
   - Each hypothesis line must include both `[H:slug]` and `CONF:HIGH|LOW|MIXED`
3. `lab_decide` (CP1):
   - Consumes Orient hypotheses as candidate structure
   - May reference ideas from slugs, but CP1 schema does not require carrying slug ids forward
4. `lab_cross_corr_v2` + `lab_director` (CP2):
   - Operate on locked CP1 thesis and Phase 2 evidence
   - Do not create, merge, split, or adjudicate hypothesis slugs
5. `lab_integrity`:
   - Audits Orient output for `[H:slug]` presence and confidence-tag compliance

## Creation And Dedup Rules (`lab_orient`)

- One slug per semantic hypothesis, not per sentence
- Reworded duplicates must reuse the same slug
- Bifurcation hypotheses (winners vs losers from one force) should keep one shared slug unless mechanisms truly diverge
- If mechanisms diverge materially, create distinct slugs with explicit qualifiers (example: `liquidity_split_growth`, `liquidity_split_defensive`)

## Confidence Coupling

- Slugs are not confidence values themselves; confidence is carried by the paired `CONF:` tag
- `CONF:` is derived from supporting tuple confidence in the input cluster:
  - `CONF:HIGH`: all supporting tuples are `C:HIGH` or untagged
  - `CONF:LOW`: any required supporting tuple is `C:LOW`
  - `CONF:MIXED`: supporting tuple set contains both high- and low-confidence evidence

## Prohibitions

- Do not use obsolete lifecycle terms (`Decide V1/V2`, `Critics`, `Predictors`) in Lab node instructions
- Do not create slugs outside `lab_orient`
- Do not rename an existing slug mid-run once emitted
- Do not emit placeholder slugs (`hypothesis_1`, `test_slug`, etc.)

## Example

- `[H:rates_revalue_growth_duration]`
- `[H:ai_capex_supply_chain_bifurcation]`
- `[H:election_odds_policy_risk_spread]`
