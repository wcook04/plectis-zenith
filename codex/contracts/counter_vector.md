# Counter-Vector Contract v1.2

## Format
Min 3 counter-vectors per critic output.

{Draft: <thesis_claim>} >> [L: <evidence>] x--x {Reality: <contradiction>}
* <one_sentence_explanation>
SEVERITY: STRUCTURAL | CONSTRAINING | DATA_QUALITY

## Severity Classification (MANDATORY — one tag per counter-vector)
- `STRUCTURAL`: Falsifies the core MECHANISM of the hypothesis — the operator itself is wrong. The thesis says `>>` (amplification) but evidence shows `>|` (dampening). The thesis says `-->` (transmission) but evidence shows `x--x` (break). If true, hypothesis should be killed (x--x).
- `CONSTRAINING`: Narrows or weakens the hypothesis but the mechanism still holds. The direction is right but the magnitude, scope, or timing is wrong. Hypothesis survives in reduced form.
- `DATA_QUALITY`: Evidence supporting the hypothesis is unreliable (C:LOW, coverage gap, stale data). The mechanism MIGHT be correct but you cannot verify it from this lane. Hypothesis may be true but cannot be trusted.

## Hypothesis Targeting (MANDATORY when falsifying a hypothesis)
Draft field MUST include [H:slug] when targeting a specific hypothesis:
{Draft: [H:fed_rate_chain] implies 3 cuts by Q3} >> [L: Core PCE 2.8%] x--x {Reality: Dot plot shows 1 cut}
* Inflation stickiness contradicts the aggressive rate path.
SEVERITY: STRUCTURAL

## Data Integrity Check (MANDATORY)
Before writing counter-vectors, scan all miner tuples for C:LOW tags.
If ANY tuple cited by the Draft Thesis carries C:LOW, you MUST emit a dedicated
counter-vector of the form:
{Draft: [H:slug] cites <ticker> <metric>} >> [L: C:LOW / data coverage gap] x--x {Reality: Confidence insufficient to support claim}
* Data quality flag present in source feed; claim cannot be verified from this lane.
SEVERITY: DATA_QUALITY

If the hypothesis already carries CONF:LOW from Orient/V1, state:
"NOTE: Hypothesis already tagged CONF:LOW at origin — this reinforces the flag."

## Hard Constraints
- `x--x` operator is MANDATORY (the collision marker)
- Explanation line starts with `*`
- SEVERITY line follows explanation
- Do NOT invent hypothesis slugs that don't exist in Decide V1
- C:LOW data integrity counter-vectors count toward the minimum 3 requirement
- At least 1 counter-vector MUST be DATA_QUALITY type if any miner evidence is C:LOW
