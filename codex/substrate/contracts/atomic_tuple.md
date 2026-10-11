# Atomic Tuple Contract v1.5

## Format
One tuple per line. No headers, no blank lines between tuples. No preamble or postscript.

{Subject, Metric/Value, Trader Relevance Annotation}

Confidence-tagged form (use when data quality varies):

{Subject, Metric/Value, Trader Relevance Annotation, C:HIGH}

## Field Rules
- **Subject**: Entity identifier. Tickers for equities (NVDA, SPY). Short canonical names for macro (US_10Y, VIX). Topic slugs for news. Market slugs for polymarket.
- **Metric/Value**: Quantitative observation with direction (+/-), magnitude, unit.
- **Trader Relevance Annotation**: MANDATORY two sentences. Not a description of the data (redundant). Not a question (too prescriptive).
  - **Sentence 1 — Local Thesis**: What does this specific data point mean in isolation? State the semantic significance: what force, regime, or dynamic does this reading signal about the entity itself? This is not a restatement of the metric — it is an interpretation of what the entity is doing and why it matters structurally.
  - **Sentence 2 — Directional Inference**: Given sentence 1, what should happen next? State the expected trajectory and the specific condition that would confirm or negate it. Vague continuation language ("likely to continue", "may move higher") is prohibited — name a condition.
- **Confidence** (4th field):
  - `C:HIGH` — all source data fields populated; no coverage gaps
  - `C:LOW` — missing data flag present (e.g., wr=0); value may be unreliable
  - `C:DERIVED` — value computed/inferred from OTHER C:HIGH data; not directly observed

## Confidence Algebra (MANDATORY)
- C:DERIVED from C:LOW source data = **C:LOW** (not C:DERIVED)
- C:DERIVED from C:HIGH source data = C:DERIVED
- If source confidence is unknown, treat as C:LOW
- A tuple without a confidence tag is treated as **C:UNTAGGED** by downstream nodes (neither HIGH nor LOW — confidence unknown)

## Lane Provenance Rule
Each miner MUST only emit tuples derived from its own lane's raw feed input.
- Seed state may be used ONLY for coverage awareness (which IDs to inspect, where gaps exist)
- Do NOT copy numeric values, flows, z-scores, or anomaly magnitudes from seed state into tuples
- Do NOT re-emit data from another lane under a different confidence tag
- Violation: if a miner's tuple contains a metric that does not exist in its own global feed, it is invalid

## Quality Rules (MANDATORY)
- **Non-redundancy:** Sentence 1 MUST add meaning beyond the Metric/Value field. Sentence 2 MUST add meaning beyond Sentence 1.
- **Signal compression:** If many entities share the same pattern and implication, emit a cluster tuple instead of repeating near-identical ticker tuples.
- **Differentiation priority:** Emit individual entity tuples only when they materially differ (confidence, direction, magnitude, structure, or implication).
- **Adaptive coverage:** There is no fixed global tuple cap. Emit enough tuples to represent the lane's real signal structure while avoiding low-information repetition.
- **Specificity:** Sentence 2 must name a falsifiable condition (e.g., "if yield holds below 4.4% by close" or "if flow stays negative with wr>50 on next print").

## Hard Constraints (enforced by downstream parser)
- Line MUST start with `{` and end with `}`
- TWO or THREE commas separating THREE or FOUR fields
- NO commas allowed inside any field (use semicolons or slashes for internal lists)
- Field delimiter is COMMA. Do NOT use pipe (|) as a field separator.
- NO nested braces `{}`
- NO multi-line tuples
- Subject field MUST NOT be empty
- If Confidence field is present it MUST be exactly `C:HIGH`, `C:LOW`, or `C:DERIVED`

## Examples
{NVDA, +8.2% / Vol 3.1x avg, AI hardware spending is re-accelerating structurally — the breadth of enterprise adoption disclosed this cycle makes this more than earnings noise. If semis hold gains into tomorrow's open without a reversal in XLK flow; NVDA anchors the momentum leg and rotation out of defensives intensifies.}
{US_10Y, +12bp to 4.52%, The rate shock is a hawkish regime reassertion — the market had priced 2+ cuts and this print forces a full reprice of duration expectations. Growth and tech face multiple compression unless yields reverse below 4.45% by end of session.}
{NVDA, -$57011M flow / wr:0, Dark pool distribution at whale scale appeared but zero wr coverage means the reading cannot be verified as genuine positioning rather than a data artifact. If wr recovers above 50 on the next print with sustained negative flow; treat as confirmed institutional exit and expect sympathy pressure across the AI hardware cluster., C:LOW}
{VRT, -$4066M flow / wr:90, High-conviction institutional distribution in a consensus AI infrastructure long — this is a deliberate positioning shift not passive rebalancing given the coverage quality. Continued negative flow tomorrow with wr>70 confirms sector rotation out of power/cooling; watch for sympathy weakness in SMCI and DELL., C:HIGH}
{MEGA_CAP_FLOW_CLUSTER, 12 tickers / net flow -$273B / wr:0 dominant, Aggregate distribution signal across the mega-cap cohort is too large to dismiss but individual actor intent cannot be resolved given shared coverage gaps. Treat as a structural uncertainty vector — the signal survives only if wr recovers and the net flow direction holds., C:LOW}
