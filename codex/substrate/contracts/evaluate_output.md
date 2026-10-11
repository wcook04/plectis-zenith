# Evaluate Output Contract v1.1

## Purpose
Audit evaluate nodes compare prediction vs reality. Their output must be structured
enough for the survival classifier to extract realized drivers.

## Required Sections
For each prediction vector evaluated, output one block:

LANE: <lane_name>
VECTOR: <the original prediction, quoted>
OPERATOR: >> | --> | >| | x--x | << >> | === | ... (which operator the prediction used)
PREDICTION: <what was predicted, one line>
PREDICTION_CONF: HIGH | MEDIUM | LOW (from the prediction's confidence tag)
BAND_TYPE: STANDARD | WIDENED (was the band widened due to C:LOW / CONF_FLOOR?)
REALITY: <what actually happened, one line>
VERDICT: HIT | MISS | PARTIAL | EXPIRED | DROPPED | N/A (N/A only for === predictions where trigger didn't fire)
TRIGGER_FIRED: YES | NO | N/A (did the prediction's INVALIDATED_IF condition occur?)
DRIVER: <the key realized driver that determined the outcome, one line>

## Verdict Rules
- HIT: Reality falls within the predicted {T+1} band AND direction was correct
- PARTIAL: Direction correct but magnitude outside band, OR reality at band edge
- MISS: Direction wrong OR reality far outside band
- Special: If BAND_TYPE=WIDENED and reality falls in the widened portion only (not the standard band), verdict is PARTIAL not HIT. Widened bands earn partial credit, not full credit.

## Operator-Aware Verdict Adjustments
- **`...` (Latency) predictions**: If the predictor stated "setup building / no expression yet," a 24h MISS on price is EXPECTED. Grade the SETUP VALIDITY instead: did the conditions the predictor identified actually exist? If yes and direction was eventually correct, verdict is PARTIAL (not MISS). If the setup itself was wrong, verdict is MISS.
- **`<< >>` (Bifurcation) predictions**: Two sub-predictions in one vector. Evaluate BOTH legs. If one leg hits and the other misses, verdict is PARTIAL regardless of individual magnitudes.
- **`===` (Short-Circuit) predictions**: These are conditional (IF trigger fires THEN violent move). If the trigger did NOT fire: verdict is N/A (not MISS). If the trigger fired: grade normally against the predicted magnitude.
- **`>|` (Dampening) predictions**: The predictor claimed a force was being absorbed. If reality shows a BREAKOUT (the absorption failed), verdict is MISS with DRIVER noting "dampening mechanism failed."
- **Dynamic-universe lanes (Polymarket/StockGrid)**:
  - `EXPIRED`: Entity naturally resolved/aged out before comparable T+1 measurement.
  - `DROPPED`: Entity dropped out of the measurable leaderboard/universe at T+1.
  - `EXPIRED`/`DROPPED` are state outcomes, not directional misses.

## Constraints
- Every prediction vector from the upstream predictor must be evaluated
- DRIVER field is mandatory for MISS and PARTIAL verdicts
- DRIVER should be specific enough to trace back to feed data
- If TRIGGER_FIRED=YES and VERDICT=MISS, note: "Stated invalidation condition realized"
- If PREDICTION_CONF=LOW and VERDICT=MISS, note: "Low-confidence prediction — miss expected"
