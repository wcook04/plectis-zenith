# Prediction Vector Contract v1.3

## Format
Each vector is one block. Blocks separated by blank line. Min 3 vectors per lane.

{T: <current_state>} >> [L: <logic_bridge>] >> {T+1: <projected_state>}

## Anchor Tokens (MUST be present, in order)
- `{T:` ... `}` — current observed state with specifics
- `[L:` ... `]` — causal logic bridge
- `{T+1:` ... `}` — projected state with directional range/band

## Operators (between anchors)

Each operator encodes HOW current state becomes future state. Pick the one that matches the transmission mechanism — do not default to `>>` for everything.

### `>>` Amplification
The output is DISPROPORTIONATE to the input. Small catalyst, violent reaction. This is leverage, crowding, reflexivity, or cascade dynamics. Use when {T+1} moves MORE than {T} would linearly suggest.
- Band implication: Wider bands justified. Overshoot is expected.
- Confidence implication: HIGH only if amplification mechanism is confirmed by multiple lanes.
- Audit reads this as: "predictor expects non-linear acceleration."
- Example: {T: NVDA +8% on earnings} >> [L: Short squeeze + gamma ramp] >> {T+1: NVDA +12-18%} — the move feeds on itself.
- WRONG usage: {T: Yield 4.4%} >> [L: Steady drift] >> {T+1: Yield 4.45%} — that's linear, use `-->`.

### `-->` Transmission
Standard cause-effect with normal friction. Energy passes through the system at roughly the rate the input implies. This is the DEFAULT when the mechanism is proportional and continuous. Linear extrapolation is appropriate.
- Band implication: Standard band widths. Reality should roughly match predicted magnitude.
- Confidence implication: Highest confidence operator — the world behaves normally.
- Audit reads this as: "predictor expects business as usual."
- Example: {T: DXY weakening} --> [L: Import prices rise with lag] --> {T+1: PPI ticks up 0.1%}

### `>|` Dampening / Absorption
A LARGE force produces a SMALL output. Something is absorbing the shock — passive flows, hedging, policy intervention, or structural support. The force EXISTS but is being contained. The opposite of `>>`.
- Band implication: Tighter bands than the input force would suggest. Compression.
- Confidence implication: MEDIUM — you're predicting that a containment mechanism holds, which can break.
- Audit reads this as: "predictor expects the obvious move to NOT happen (yet)."
- Example: {T: Mega-cap distribution -$50B} >| [L: Passive ETF bid absorbs] >| {T+1: SPY flat -0.3% to +0.2%}
- Key distinction from `x--x`: the mechanism is KNOWN and the relationship still exists but is muted. In `x--x` the relationship itself is broken.

### `x--x` Violation / Correlation Break
An established relationship BREAKS. The signal says "move right" but the asset moves left or doesn't move, and you cannot explain why through dampening. Historical playbook is unreliable. This is a regime change signal.
- Band implication: Wider bands — you're predicting abnormal behavior, which is inherently uncertain.
- Confidence implication: LOW unless you have strong evidence for WHY the break is happening.
- Audit reads this as: "predictor says historical correlations are offline" — grade carefully.
- Example: {T: Yields down 15bp} x--x [L: Duration-equity link severed by rotation] x--x {T+1: Tech flat despite lower rates}
- WRONG usage: as a generic "bearish" marker. `x--x` means the MECHANISM is broken, not just that the direction is down.

### `<< >>` Bifurcation
Energy SPLITS into opposing directions from a single catalyst. Winners and losers emerge simultaneously. This is rotation, not rally or crash. The catalyst is a PRISM, not a push.
- Band implication: State both legs. Each leg has its own band.
- Confidence implication: MEDIUM on the bifurcation; HIGH/LOW on individual legs as evidence warrants.
- Audit reads this as: "predictor expects a spread, not a level" — evaluate BOTH legs. If one leg hits and the other misses, verdict is PARTIAL.
- Example: {T: AI power demand surge} << >> [L: Grid vs. Fuel supply chain divergence] << >> {T+1: VRT +5-8% / LEU -8-15%}
- This operator produces TWO sub-predictions in one vector. Both must be evaluated.

### `===` Short-Circuit
Immediate, algorithmic, zero-latency reaction. Margin calls, liquidation cascades, circuit breakers, forced unwinds. No human decision-making in the loop. The trigger fires and the response is mechanical.
- Band implication: Wider bands — violent moves with no orderly price discovery.
- Confidence implication: LOW on whether trigger fires; HIGH on magnitude IF it fires. Often expressed as conditional.
- Audit reads this as: "predictor identifies a tripwire" — check whether the trigger fired, not just whether the level was hit.
- Example: {T: VIX at 18 with dealer gamma negative} === [L: Vol seller margin call cascade] === {T+1: VIX 22-28 / SPY gap down 2-3%}
- Best paired with INVALIDATED_IF: the trigger condition itself.

### `...` Latency / Delayed Effect
The force exists NOW but has not expressed in price yet. There is slack in the system — the effect takes days/weeks to materialize. Critical for short-horizon predictions where the setup is building but the payoff is beyond the window.
- Band implication: NARROW for 24h (the move hasn't started); state the SETUP not the PAYOFF.
- Confidence implication: MEDIUM on the setup existing; LOW on exact timing of expression.
- Audit reads this as: "predictor says the move is coming but NOT YET" — a near-horizon MISS is expected and should NOT be graded as ERROR if the setup was valid. Grade the setup validity, not the timing.
- Example: {T: M2 expansion accelerating} ... [L: 6-8 week lag to asset prices] ... {T+1: Setup building / no expression yet / monitor M2 velocity}
- This operator means: "I am flagging a force that will matter but cannot predict exactly when it arrives."

## Hypothesis Attribution
The [L:] field SHOULD cite [H:slug] references when logic derives from shared hypotheses.
If purely lane-local: state [L: lane-local extrapolation; no hypothesis]

## Sharpness Requirements (MANDATORY)
1. DIRECTIONAL COMMITMENT: Every vector MUST state a primary direction (UP/DOWN/FLAT). The band may be asymmetric around this direction but a direction must be committed to.
2. MAXIMUM BAND WIDTH: The total width of {T+1} range must not exceed:
   - For single stocks: 1.5x the ticker's Vol_20d (from miner data)
   - For indices (SPY/QQQ/IWM): 1.5% absolute
   - For macro (yields): 20bp absolute
   - For probabilities (Polymarket): 10pp absolute
3. POINT ESTIMATE: In addition to the band, state a single "center of gravity" number. This is the most likely outcome.
4. CONFIDENCE TAG: State HIGH/MEDIUM/LOW after the vector. If LOW, state why (e.g., "LOW: CONF_FLOOR=LOW on [H:slug]").

## Confidence-Adjusted Bands (MANDATORY)
Check Decide V2's CONF_FLOOR for each cited [H:slug].
If ANY cited hypothesis has CONF_FLOOR: LOW or CONF_FLOOR: MIXED:
- The {T+1:} band MUST be at least 2x the normal maximum width
- State this explicitly: "Band widened: [H:slug] CONF_FLOOR=LOW"
- Confidence tag MUST be LOW or MEDIUM (never HIGH on LOW-confidence evidence)
- If a critic flagged a STRUCTURAL counter-vector against the hypothesis, DO NOT predict continuation of that hypothesis

## Invalidation Trigger (MANDATORY)
After each vector block, state on one line:
INVALIDATED_IF: <specific condition that would make this prediction MISS>
Example: INVALIDATED_IF: SPY closes above 590 (breaks the "hollow core" thesis)

## Cross-Lane Assumptions
If a prediction depends on another lane's state holding, state:
ASSUMES: <lane> <condition>
Example: ASSUMES: MACRO yields remain below 4.55% (if yields spike, equity prediction breaks)

## Hard Constraints
- All three anchor tokens on ONE line (no multi-line vectors)
- No preamble/headers/narrative outside vector blocks
- T+1 must include quantitative range or probability band
- Vectors with bands exceeding the maximum width will be flagged as UNFALSIFIABLE by integrity
- INVALIDATED_IF line is mandatory (predictions without it are flagged by integrity)

## Operator-Specific Format Rules
- **`<< >>` Bifurcation**: T+1 must state BOTH legs with separate ranges. Example: `{T+1: VRT +5-8% / LEU -8-15% / bifurcation}`
- **`===` Short-Circuit**: T+1 must state the TRIGGER and the CONDITIONAL outcome. Example: `{T+1: IF VIX >22 THEN SPY -2% to -3% / center -2.5% / SHORT-CIRCUIT}`. INVALIDATED_IF should reference the trigger NOT firing.
- **`...` Latency**: T+1 must describe the SETUP state, not the eventual payoff. Example: `{T+1: Setup intact / conditions accumulating / no 24h price expression expected / monitor <trigger>}`. Band width rules are relaxed — state the setup quality, not a price target. Confidence tag should be LOW or MEDIUM (never HIGH on something that hasn't started expressing).
