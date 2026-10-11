# Scorecard Contract v1.1

## Taxonomy (exactly five grades, always in this order)
SKILL / LUCK / ERROR / BLIND_SPOT / HALLUCINATION

- SKILL: Prediction correct AND reasoning chain valid AND confidence appropriate
- LUCK: Prediction correct BUT reasoning chain flawed or coincidental
- ERROR: Prediction incorrect, reasoning had identifiable flaw in logic
- BLIND_SPOT: Prediction incorrect, built on evidence flagged C:LOW or CONF_FLOOR=LOW that was not adequately widened/hedged. The system had information about data unreliability but failed to propagate it.
- HALLUCINATION: Prediction based on fabricated or nonexistent data

## Output Format
```json
{
  "verdict": "<SKILL|LUCK|ERROR|BLIND_SPOT|HALLUCINATION>",
  "prediction": "<what was predicted, one line>",
  "operator": ">> | --> | >| | x--x | << >> | === | ... (which operator the prediction used)",
  "prediction_conf": "HIGH | MEDIUM | LOW (confidence at prediction time)",
  "band_type": "STANDARD | WIDENED",
  "reality": "<what actually happened, one line>",
  "reasoning": "<why this grade, 2-3 sentences max>",
  "key_driver": "<the single most important causal factor, one line>",
  "conf_chain": "<did confidence propagate correctly from miner to predictor? YES/NO + note>"
}
```

## Grading Guidelines
- SKILL requires: HIT + valid reasoning + PREDICTION_CONF appropriate to evidence quality
- SKILL on WIDENED band: only if the widening was correct given C:LOW inputs (the system was honest about uncertainty)
- LUCK: HIT but reasoning chain cites wrong mechanism or coincidental correlation
- ERROR: MISS where the logic was wrong (e.g., predicted continuation when a regime break was signaled)
- BLIND_SPOT: MISS where upstream C:LOW / CONF_FLOOR=LOW evidence existed but was not reflected in band width or confidence tag. Check: did the miner flag C:LOW? Did Decide V2 flag CONF_FLOOR=LOW? Did the predictor widen? If the chain broke, grade BLIND_SPOT.
- HALLUCINATION: prediction cites data that does not exist in any feed or miner output
- Dynamic-universe state outcomes (`EXPIRED` / `DROPPED`) are excluded from SKILL/LUCK/ERROR/BLIND_SPOT/HALLUCINATION denominator math.

## Operator-Specific Grading
- **`...` Latency predictions**: If the setup was valid but the 24h window was too short for expression, grade SKILL (setup correct) or LUCK (setup coincidental), NOT ERROR. Only grade ERROR if the setup itself was wrong (the force didn't exist).
- **`===` Short-Circuit predictions**: If the trigger didn't fire, grade N/A (not ERROR). The predictor correctly identified a risk that didn't materialize — that's risk identification, not a miss.
- **`<< >>` Bifurcation predictions**: Both legs must be graded. If one leg is SKILL and the other is ERROR, net grade is ERROR (the bifurcation thesis was partially wrong). If both legs are directionally correct but one magnitude is off, SKILL.
- **`>>` Amplification predictions that undershoot**: If direction was right but the amplification didn't materialize (move was proportional, not disproportionate), grade LUCK — the direction was right but the stated mechanism (leverage/crowding/cascade) was wrong.
