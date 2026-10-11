# Evidence and remaining work

This records implementation evidence, not a claim that the system predicts markets successfully. Local runtime artifacts live under ignored `work/` and `state/`; the repository retains code, protocols, fixtures and source manifests.

## Implemented

- A standalone read-only graph API exposes the reviewed native topology, mission closures and node neighborhoods through versioned JSON and OpenAPI. It serves no frontend, private run state or execution endpoints. The frontend contract is in [frontend-handoff.md](frontend-handoff.md).
- Source distribution includes Apache-2.0 licensing, retained-source and dataset notices, contribution/security/citation files, pinned offline CI and a clean-checkout reproduction guide. The positive-allowlist graph projection has its own backend owner and freshness check.
- The actual 71-node engine and contracts load independently of the internal kernel. Base Lab includes 28 nodes in 11 waves; Oracle includes 31 in seven waves.
- Agent packets, captured responses and provider adapters return through native validation, repair and resume. Frozen runs bind source, input, graph and policy hashes.
- Tiny generated node skill cards refer to canonical implementations. Frozen policies tune short rules, incoming context weights and budgets. A real graph variant inserts an evidence-check node and feeds its result into CP1.
- CP2 feedback admits validated forecasts, resolves exact dated truth and measures price errors. Default proposal gates require 20 issue times and recurring failures across three time buckets. Multiple assets or overlapping report windows do not become independent trials.
- The experiment harness retains failed attempts, freezes the evaluator and support, and spends a single final assessment. Its probability adapter maps frozen forecasts. A separate cohort adapter freezes candidate graphs and common inputs, imports actual native CP2 runs, measures them through feedback, and exposes the next commands for an agent.
- Cohort imports carry read-only mechanical observations of artifacts, handoffs, validation and bound context-policy receipts, including pre-CP2 failures. Unknown evidence stays unknown; diagnostics cannot change acceptance. Complete comparisons retain paired issue losses and target coverage, preserving equal issue weight and withholding all scores on incomplete support.
- Development reflection preserves the complete feedback batch and its denominators, adds bounded verified node traces, and compiles one short skill, context-budget or edge-weight change through the native policy validator. A verified parent cohort can supply a candidate row for a new study, retaining model, provider and graph identity. Reflection itself does not execute or accept the candidate.
- Lean models conditional skill composition/refinement, evidence availability and graph acyclicity. Python projects the actual graph; explicit Lean receipts distinguish compiled proofs from ordinary Python checks.
- StockNet historical import and price-only baselines are executable. Source pins, protocol, row exclusions, splits, predictor packets and truth packets remain separately attributable.
- The matched StockNet input study joins prices and timestamped social text on 20 fixed development issue dates. The two input arms share assets, horizons and model; every missing or invalid response remains in coverage accounting.
- A bounded FinMultiTime importer joins historical prices, news and per-filing financial facts. It exports partial native feed artifacts, checks exact issue-price availability, delays date-only news and filings until the next exchange session, and rejects changed source or snapshot bytes.
- Malformed FinMultiTime filing structures are counted as rejected evidence without discarding valid siblings. Feedback references retain resolvable absolute paths for external files and relative paths for files within the checkout; existing registered records are not rewritten.
- Explicit paid OpenRouter calls use one shared batch ledger with conservative pre-call reservations, fixed call/output limits, immutable run bindings and no retries or fallback. Unknown cost or an interrupted request halts the budget. Free-only and NVIDIA adapters remain separate.
- Repo-local skills include pinned, licensed point-in-time research and backtest-validation references. External projects informed the architecture; their presence is not evidence that their optimizers are integrated.

## Observed evidence

The private collector acquired all seven feed lanes on 11 October 2026. Stock and ETF feeds had partial symbol coverage; collection health and per-symbol availability remain separate. This Sunday run exercised infrastructure, not an open-market capture.

A native standalone Lab smoke consumed those actual recorded feeds, completed the seven tool nodes and paused for its first agent response. Compact prompt projection reduced the first prompt from 4,542,259 to 846,415 characters while preserving all feed data rows and dated price provenance. This does not establish that a selected model can accept or use that much context. It did not produce a live full-DAG forecast.

The final smoke in the renamed checkout also applied the explicit 16,000-character source-context policy. It consumed all seven feed artifacts, completed seven of 28 Lab nodes without a runtime failure, and paused for an agent with a 25,603-character prompt including contracts and metadata. This policy clips source context and records omissions; it is a tractable experimental setting, not an established improvement in evidence selection.

The StockNet run covers 88 stocks with no-change, past-momentum and a fixed train-only OHLCV ridge baseline over 1/5/20 observed-row horizons. The 27 split evaluations produce 219 model-window results across 73 shared dated windows. Test support is 5,394 / 4,698 / 2,088 forecasts across 62 / 54 / 24 issue dates respectively. See [historical benchmarks](historical-benchmarks.md) for metrics and interpretation. These are price-only baseline measurements, not StockNet paper reproduction or LLM results.

The pinned FinMultiTime import fetched five Apple source files with 15,726,208 bytes transferred using bounded HTTP ranges. The 28 March 2025 snapshot contains 20 price bars, five articles and 13 financial facts under the declared availability policy. A 2015 snapshot correctly reports missing news, and a 21 April 2025 snapshot reports stale prices with no current issue-price value. See the [text-free import result](finmultitime-import-result.json). This verifies a richer input interface; it does not reproduce FinMultiTime's published forecasting evaluation or establish exact historical data vintages.

The bounded experiment example evaluates an invented probability fixture. Baseline Brier 0.41 and shrink Brier 0.3284 demonstrate trial mechanics only. The feedback demo is likewise synthetic. Neither number is evidence of financial performance.

The canonical 71-node/205-edge finite graph passed Lean compilation with empty axiom audits for its checked declarations. The 72-node/206-edge variant passes Python structural validation, but its exact generated Lean instance timed out at the bounded 120-second limit and remains unverified. The general rank-implies-acyclicity theorem is proved; that does not substitute for acceptance of the concrete variant instance.

The public OpenRouter catalogue check found 16 eligible free entries without credentials. The explicitly authorized paid study requested `mistralai/mistral-nemo` under a shared US$0.25 client cap. Three valid responses reported US$0.000414462; the fourth call returned HTTP 429 with unknown cost/usage, so the ledger halted. All four reservations, totaling US$0.002033574, remain retained. No retry or fallback occurred. Only nine cases on one issue date have paired model output, so the 20-date comparison is incomplete and cannot select a candidate. The [factual result projection](stocknet-multifeed-result.json) preserves identities, hashes, metering and coverage without raw text or credentials.

No NVIDIA account call was made. A scan against locally configured secret values found no matches in candidate standalone files or existing Git history.

The 11 October source-assimilation pass read the full pinned AFlow, ADAS,
TextGrad and GEPA method/evaluation sources and their relevant implementations.
The resulting [design](learning-design.md) adopts component-specific criticism,
parent-relative changes and fixed external evaluation. The
[source manifest](architecture-sources.json) records exact paper versions, code
commits and licenses. It does not claim reproduction of their benchmark results.

The integrated suite passed all 370 tests on 11 October, using this checkout's
Python environment with inherited `PYTHONPATH` cleared. Native validation also
accepted all 71 nodes. Reflection tests cover source drift, development/heldout
membership, bounded trace integrity, one-parameter policies and consumption of
the candidate row by a fresh native cohort. These are software and synthetic
contract checks; no additional provider call or live learning result occurred.

The subsequent standalone backend pass passed **399 tests**: the original suite,
six public-projection checks and 23 API cases. The API tests validate real HTTP
responses against the OpenAPI contract, exact native mission scopes, private
field exclusion, conditional requests, origin permissions and write rejection.
Extraction, generated skills and the finite semantic checker also pass. These
checks did not rerun Lean compilation or produce a new forecast. The temporary
website implementation was removed at the operator's request.

The diagnosis and paired-comparison pass subsequently passed **423 tests** in
the standalone environment (199.98 seconds; ten existing dependency deprecation
warnings). Negative cases cover absent versus malformed records, escaped paths,
unbound handoff/validation evidence and inconsistent context receipts. Cohort
cases cover additive observer failures, pre-CP2 attempts and equal issue
weighting with unequal target counts. A new synthetic fixture initially lacked
its second target's required evidence grounding; the native validator rejected
it, and the fixture was corrected before this complete passing run.

The accompanying review adds Trace/OptoPrime, DSPy MIPRO, Agent Lightning,
evolution strategies and temporal/model-selection methods to the existing
source decisions. Papers and selected code were inspected, with implementation
pins and licensing evidence recorded where verified. No upstream optimizer,
training stack or provider execution was added. Nested rolling assessment and
lifetime history-exposure tracking are specified future work, not claimed
runtime protections.

## Remaining evidence obligations

| Work | Current boundary | Next evidence needed |
|---|---|---|
| Full graph learning | Native graph execution, frozen cohort comparison, verified development reflection and one-parameter candidate handoff are implemented; no autonomous optimizer or real model improvement is demonstrated | Execute a preregistered baseline/candidate cohort with actual provider receipts, complete matched support and the sealed final assessment |
| Forecasting advantage | Historical baselines exist; no model advantage is established | Prospective or carefully qualified historical predictions, matched support, uncertainty analysis and a genuinely untouched assessment |
| Automatic Evolve | Original reviewed runner retained; browser dispatch still separate | An agent/provider dispatch seam and batch-proposal consumer, with reviewed promotion kept explicit |
| General architecture search | Current variants add nodes and reroute edges while retaining base ancestry | A separately specified ablation contract before removing baseline branches or changing acceptance outputs |
| Selection across studies | Per-study chronology, embargo, candidate budget, complete support and final seal are enforced | Nested chronological selection manifests and lifetime history-exposure accounting; a renamed study must not present previously inspected dates as unseen |
| Method novelty | Primary graph, textual optimization, neural-learning and evaluation sources are compared and pinned where code was inspected | One precise new mechanism and equal-budget comparisons against the closest methods; current distinctions do not establish novelty |
| Context selection | Metadata compaction and explicit weighted excerpt budgets are available | Compare evidence-preserving context selection against the full snapshot on a frozen study |
| Provider operation | Real OpenRouter receipts and a rate-limit halt are recorded; the first matched comparison is incomplete | Capacity-aware planning for a new frozen batch; keep failed attempts and unknown cost, and do not bypass the halted ledger. NVIDIA operation remains mock/metadata-only |
| Candidate isolation | Candidate Python is trusted local code, not a security sandbox | External isolation if untrusted code or confidential heldout labels enter the experiment |
| Distribution | An isolated tracked-source checkout installed and passed the original 370-test suite on the same host; source/retained-skill/UCI notices are included | Independent-machine reproduction and destination-specific publication review; wheel portability is not verified |
| Frontend | Backend graph API and integration contract are ready; the requested website implementation was removed | Claude owns the separate frontend; no UI or public deployment is bundled |

The internal workstation collector owns daily market-open/close scheduling. It runs while the laptop is awake and logged in, with exchange holidays, early closes and daylight saving handled by the calendar. The standalone repository does not install a duplicate service. A future standalone scheduler must preserve the same timestamp and missed-capture rules.
