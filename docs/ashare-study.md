# Developing a capable financial reasoner

The current objective is to establish a useful base reasoner, then test whether
experience improves its recurring financial procedures beyond numerical
calibration. Retrieval, prompts, topology, models, event families and horizons
are development choices. The controls of a frozen comparison apply to that
comparison; they are not permanent limits on Zenith.

**The operator has now dedicated the remaining authorized budget to the research
programme and requested a source-rich Type B review before selecting what to do
next.** No inference is currently running. The [reviewable candidate batch](ashare-base-plan.json)
contains 21 calls, not the earlier 572-call learning study. No new LLM outputs,
learned-reasoning improvement, final assessment or trading result exist.

## The measured diagnosis

The [current measurement](ashare-development-diagnosis.json) reproduces the
original controls on 33 dates and 330 asset forecasts after eight initial fit
issues. Every transformation and ridge fit uses earlier matured training data.

| Forecast | Original MSE | Chronologically scaled MSE |
| --- | ---: | ---: |
| Zero market-relative return | 0.0010951783 | 0.0010951783 |
| Numerical, metadata and issuer ridge | 0.0014184998 | 0.0010872885 |
| Same inputs plus character text | 0.0014834418 | 0.0010865439 |

The identity `MSE(q)-MSE(0)=E[q²]-2E[yq]` uses equal date weights.
Numerical forecast energy is 0.0004857933 and alignment is 0.0000812359.
Text energy is 0.0005650676 and alignment is 0.0000884020. Both have positive
sample alignment and excessive scale. All-date optimal scalars, 0.1672 and
0.1564, are retrospective diagnostics only.

Chronological scaling fits one nonnegative coefficient capped at one. It uses
only complete earlier date groups whose labels have strictly matured before
the query; four mature dates are required, with a four-date zero prior.
Warm-up predictions remain zero corrections in the complete score. Applying
the same rule to the raw incremental text correction on top of the scaled
numerical baseline gives MSE 0.0010865306. This tiny difference does not establish
an incremental text advantage.

The approximately 0.7–0.8% improvement below zero is development evidence.
Calibration was designed after the original aggregate errors had been seen;
its settings were not retuned after this new measurement. This does not test
LLM reasoning or an untouched holdout. The original
[unscaled receipt](ashare-development-controls.json) remains unchanged.

## The concrete base comparison

Frozen cohort: `work/ashare-base-development-20261012/`. Its binding, exact source
hashes, library versions, packets and selected dates are retained. Model choice:
`deepseek/deepseek-v4.1-flash` at the exact `deepinfra/fp8` endpoint.

- Excluded compatibility date: 2023-03-08, three calls.
- Development dates: 2023-03-01, 2023-04-27, 2023-07-20, 2023-08-03,
  2023-08-31 and 2023-12-22, three calls each.
- Direct arm: one capable prompt reasoning over original evidence.
- Graph arm: a supported-change interpretation, then a forecast using both
  that interpretation and original evidence.
- Shared information: issuer identity, prices, numerical state, weak anchor,
  dated evidence, decision clock, target and native forecast validator.
- Comparison limits: one versus two calls per date, not equal token budgets.
  Provider receipts retain actual usage, identity and cost.

Inputs guided the explicit date selection; previously exposed development
outcomes do not become unseen by selecting a smaller batch. The pilot verifies
actual validators before the comparison can issue calls. Any invalid response
ends the batch after that date; invalid dependencies skip the graph call.
Provider failures stop execution. No silent retry or automatic candidate learning
occurs. Replays reparse original response caches. Development closes after a
selection or final seal.

The interpretation separates FACT, CHANGE, CHANNEL, PRICED and UNKNOWN. Its
additional economic-change signal is a bounded score, not a return or claimed
market surprise. Raw unknowns remain null. An explicit numerical comparator
maps unknowns to zero correction and learns one coefficient capped at 0.05 using
the same mature-date rule. Direct and graph forecasts receive ordinary scaling
as well. Six dates leave only two after the four-date calibration warm-up;
matched raw and zero scores accompany that restricted comparison. All six dates
remain in the full score. This is a behavior-first diagnostic, not a superiority
or learning result.

Inspect outputs against the source: right issuer, accounting period, latest
comparable claim, contradictory evidence, unknown expectations, and effect
remaining after entry. JSON/reference validation is not an entailment verdict.
If either arm fails these recurring tasks, change the base and retain the
failed version before attempting the larger learning loop.

## Fuller-source replacement already compiled

The [source manifest](guidance-development-sources.json) binds six original
issuer releases, SEC clock cross-checks, table images and price support.
The [compiler receipt](guidance-development.json) contains four Adobe/Salesforce
updates and 13 exact range comparisons. These cases are selected for source
feasibility, not as a representative or held-out opportunity stream.

Adobe target sections come from the original PDFs. Salesforce packets contain
visually reviewed selected annual-column transcriptions; they do not include
all guidance measures, reconciliation tables or whole-report prose. Current-site
navigation and later editorial additions are excluded. The task therefore tests
financial comparison on reviewed extracts, not autonomous report extraction.

The cases distinguish mixed revisions, unchanged revenue with higher margins,
and per-metric previous publications. Adobe's March release omits annual revenue
and segment-revenue targets; their June comparison uses December rather than
inventing a March reaffirmation. Endpoint and width changes accompany midpoint
direction, so an unchanged midpoint cannot hide a revised range. The exact
oracle is outside every model request. The representation task does not ask for
returns or receive outcome labels.

Four typed packets and held requests are under
`work/guidance-development-final-20261012/`. Acceptance plus five minutes defines
a reconstructed decision clock; entry is the next regular open and exit the
fifth regular close. Current mirrors are not authenticated historical snapshots.
The source manifest distinguishes SEC clock evidence from historical byte identity.
Twenty completed price sessions and five future sessions exist for each issuer
and SPY. Adjustment vintage and distribution treatment remain unresolved, so
this lane scores no returns. A modern model may remember these events.

## Evidence and accounting retained from the A-share work

The pinned [TraderHarness code](https://github.com/HephaestLab/TraderHarness/tree/3e18369da5a2060f9c65b27c2a63f99edd93e167)
and [dataset](https://huggingface.co/datasets/ANTICH/traderharness-ashare-5y/tree/3bf5151ab3e94851bb09dd8ade815563c44b15a6)
supply short titles, not article bodies. Fixed retrieval keeps four issuer-tagged
items and two common headlines within seven days, plus up to two earlier
numerical profit claims with matching issuer/fiscal-period candidates within
180 days. Only five older items were added to training. Tags, matches and
inferred periods are candidate evidence, not verified issuer/accounting identity.
News epoch clocks match Shanghai display times. Midnight announcements have day
precision and become available at the following open; timed announcements use
the declared Shanghai-clock assumption. These rules do not certify text vintage.

All 136 admitted windows have complete stock/benchmark bars: 41 training,
47 validation and 48 assessment dates. Of 1,360 asset windows, 452 have no
issuer-tagged item. No final-assessment errors have been evaluated in this reset.
The 2021 anchor is a weak price reference, not a competitive fitted language model.

Labels are next-open to fifth-close gross stock wealth minus CSI 300 price return.
Pre-event share quantity determines cash entitlement; extra shares and cash enter
terminal wealth. Buying at the ex-date open receives no old-holder entitlement.
Past input normalization uses only actions occurring and announced by the issue.
The [label checks](ashare-label-checks.json) retain independent entitlement tests.
This mixed-basis target excludes costs, taxes, lots and execution constraints.
It is not a feasible hedged portfolio return. Any trading stage must define
holdings, cash, overlapping positions, executable benchmark, action treatment,
entry/exit delays and costs. A decision using the realized open cannot fill at
that same open without an independently justified execution mechanism.

## Learning after the base earns it

The existing learning profiles remain implementation options, not the next run.
Their earlier [first profile](ashare-first-run.json) allows 572 calls and the
[full profile](ashare-admission.json) 1,259; both are historical source bindings
and must not be executed against changed code. Never rewrite their frozen inputs.

A useful learned procedure might retrieve each metric's latest publication,
check period agreement, preserve an opposing segment, or decline unsupported
surprise. Compare a fixed reasoner and learned reasoner under identical numerical
adaptation, with retrieval memory as a further control. Outcome-only versus
outcome-plus-later-reporting teachers test privileged feedback if that becomes a
central claim. Lessons must use later forward-observable triggers. Larger coherent
revisions are allowed during development; separate ablations are needed for
component-level attribution. Existing native reflection provides proposal
machinery; the inspected upstream GEPA adapter interface offers a route for
reflective search, but a local GEPA integration is not established by these
changes. Keep all attempts and exposure; do not invent another optimizer.

Memory currently ranks eligible training experiences by 0.8 forward-text cosine
plus 0.2 numerical-state proximity, with three-case/24,000-byte caps. Ranking
uses no outcomes or review text. This is related to
[FinMem](https://arxiv.org/abs/2311.13743v2) and numerical/narrative analogs in
[Wang and Yeung](https://doi.org/10.3389/frai.2026.1722121), not a reproduction.
[Cawley and Talbot](https://www.jmlr.org/papers/v11/cawley10a.html) motivate keeping
selection exposure explicit. The manuscript cites the supplied papers at use.

## Reproduction and spending boundary

From the standalone repository, with the declared study dependencies installed:

```sh
python -m research.ashare_study compile --dataset work/datasets/data-selection/root \
  --study work/ashare-base-development-20261012 --profile first_learning \
  --base-date 2023-03-01 --base-date 2023-04-27 --base-date 2023-07-20 \
  --base-date 2023-08-03 --base-date 2023-08-31 --base-date 2023-12-22
python -m research.ashare_study offline-controls \
  --study work/ashare-base-development-20261012 --output docs/ashare-development-diagnosis.json
python -m research.ashare_study base-plan --study work/ashare-base-development-20261012 \
  --input-usd-per-million 0.30 --output-usd-per-million 1.20
python -m benchmarks.guidance_events --dataset work/datasets/guidance-reset-20261012 \
  --manifest docs/guidance-development-sources.json \
  --output work/guidance-development-final-20261012 --receipt docs/guidance-development.json
```

Use fresh output directories for recompilation. Both compilers refuse overwrite.
The public base-plan receipt additionally binds the frozen hash, public pricing
observation and existing ledger snapshots. Its conservative reservation is
**USD 0.5860815**, using ordinary model-catalog input/output rates, a byte-based
input token upper bound, framing/interpretation allowances, and 4,096 output
tokens per call. Endpoint/cache discounts are not assumed; this is not an
expected bill. Recheck live pricing before any release.

The earlier proposal was **USD 1 total, at most 21 calls**, only
`base-pilot` and `base-comparison`. The existing USD 4 ledger has immutable
1,024-output-token limits and cannot be silently amended or reset. All previous
ledgers, unknown costs and reservations remain preserved. No replacement ledger
has been initialized, account inspected or paid call made. The local
`authorization-held.json` explicitly has `research_hold_released: false` and
cannot execute. The later operator instruction now authorizes use of remaining programme funds;
it supersedes the earlier request for another release. Local unused capacity
under the USD 4 reservation cap is USD 3.9896875, not a verified live account
balance. Before choosing and executing this or a replacement batch, verify
funded headroom, bind its exact frozen hash/provider/scope and preserve the
remaining programme ceiling without changing old limits or resetting history.
The four fuller-source representation requests are outside this candidate batch.
