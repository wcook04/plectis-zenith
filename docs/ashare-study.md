# Learning what to notice in financial evidence

Zenith's next experiment asks whether a short financial reasoning skill learned
from completed cases improves later five-session forecasts. A second question
asks whether the supplied text helps at all. The two questions need separate
comparisons: a better forecast can come from additional information, better
interpretation, or a smaller systematic numerical bias.

The offline implementation is complete. **Paid inference remains on hold.**
The [generated admission receipt](ashare-admission.json) describes actual
compiled data, not an executed learning result. The earlier US experiment and
its result exports remain separate.

## What the model sees

Each issue occurs one minute after an XSHG session closes. The two reasoning
nodes receive twenty completed sessions plus the preceding close, an earlier
ridge anchor, dated evidence, and the exact future interval. The first node
interprets the evidence. The forecast node receives both that interpretation
and the original packet; an omitted fact is still available for inspection.
Only the forecast skill, at most 1,200 characters, is initially mutable.

The base instructions ask what was reported, what is new, which expectation is
actually supplied, how it could affect this company, what contradicts that
interpretation, and what effect could remain after entry. For example, 30%
profit growth means something different alongside 60% guidance than alongside
10% guidance. Without an expectation source, surprise is unknown. Because entry
is at the next open, the target excludes the first overnight price response.

Fixed selection retains up to four issuer-tagged items and two common headlines
from the preceding seven calendar days, deduplicated by normalized content and
capped at 600 characters each. Full articles and announcement PDFs are absent.
Source tags are candidate relevance links: they can conflate related listed
companies. One inspected title tags BYD Electronic news with BYD's A-share code.
The model must check the described subject rather than trust the tag alone.

News uses its retained epoch converted explicitly to UTC; the archived display
clock independently matches Shanghai time. Midnight announcements are treated
as day precision and become eligible at the following exchange open. Timed
announcements use the stated Shanghai-clock assumption. Unknown-vintage
financial facts remain excluded. These rules qualify publication metadata;
they do not establish that archived wording was unchanged historically.

Issuer codes are supplied in all treatments. `asset_N` is a stable join key,
not anonymization. The three information treatments are:

| Treatment | Available information |
| --- | --- |
| Price | Identical issuer identity, historical price state and numerical anchor |
| Metadata | Price input plus the admitted event times, types, count and source identifiers; text withheld |
| Rich | The same selected records with their actual titles/headlines |

Each treatment gets its own interpretation. All preserve identical labels and
issue dates. Named entities occurring within a story can still provide cues in
the rich arm, so rich-minus-metadata measures the contribution of the retained
text, not a pure experiment separating every semantic and identity mechanism.

## Dates and accounting

The compiler verifies the pinned originals and checks every historical and
future bar against the exchange calendar. It deliberately warms up entirely
within the verified February 2023 onward panel. It produces 138 nonoverlapping
scheduled windows, purges two at phase boundaries, and admits 136 complete
ten-stock batches:

| Phase | Issue dates | Asset forecasts | First–last issue |
| --- | ---: | ---: | --- |
| Training | 41 | 410 | 2023-03-01–2023-12-22 |
| Validation | 47 | 470 | 2024-01-08–2024-12-20 |
| Assessment | 48 | 480 | 2025-01-06–2025-12-24 |

Of the 1,360 asset windows, 452 have no issuer-tagged item. Every window has two
common headlines. The receipt counts what survives the actual selection and
records its source references. Ordinary, issuer-information, thin-information
and action-boundary example packets remain locally inspectable in
`work/ashare-offline-20261011/representative-inputs.json`. They are chosen by
chronology and input properties, never forecast success.

The target is stock gross wealth return minus the CSI 300 price-index return,
from the next-session open to the fifth-session close. For shares held across
an ex-date, cash uses the share quantity before that event's multiplication;
additional shares and unreinvested gross cash enter the terminal wealth mark.
Buying at the ex-date open receives neither prior-holder entitlement. Cash is
treated as a receivable; new shares are valued without claiming immediate
liquidity. Taxes, fees, lots, suspensions and executable portfolio returns are
outside this forecasting label. The stock and benchmark return bases differ.

Historical OHLC inputs are gross wealth marks for a holder at the preceding
close, rebased to one. Only actions occurring and announced by the issue enter
this calculation. A later distribution cannot rewrite an earlier packet.
Volume is normalized within the same window, allowing for share multiplication;
absolute units differ across source eras and are not treated as a feature.
Missing turnover amounts are not filled. The state also includes past CSI 300
returns and volatility so that market-relative reasoning has market context.
The numerical anchor is fitted on a fixed 2021 schedule, before study outcomes.

Independent fraction-arithmetic tests cover ex-date entry, ex-date exit,
successive distributions and unreinvested cash. BYD's
[issuer announcement](https://static.cninfo.com.cn/finalpage/2025-07-22/1224237000.PDF)
independently confirms the inspected 2025 A-share distribution. The tests do
not independently authenticate every record in the corporate-action archive.

## Learning contrasts

Training reviews see the same complete original packet, interpretation,
forecast and per-asset residuals. The hindsight treatment alone adds subsequent
reporting. That reporting spans the declared outcome interval, including long
holiday intervals; selection caps still apply. Its latest availability and the
outcome's availability jointly determine the earliest permissible lesson time.
All teaching evidence is bounded by the training-information cutoff.

| Policy | Development information | Mutable object |
| --- | --- | --- |
| Frozen base | None | None |
| Outcome skill | Original forward traces and matured outcomes | One proposed short skill |
| Hindsight skill | The same information plus subsequent reporting | One proposed short skill |
| Blinded skill | Protected task and original base skill | One proposal without feedback |
| Reflected memory | The same hindsight reviews and training outcomes | Up to three retrieved experiences |

Each review records an observable trigger, conditional lesson, uncertainty,
disconfirmation condition and source references. Reasoning error, ignored
alternative, newly arrived information, accounting error and unresolved outcome
are different diagnoses. Rejected reviews remain in the scheduled bank.

One proposal is allowed per skill arm. Validation chooses between that proposal
and unchanged; unchanged wins ties, and incomplete candidate support cannot win.
The blinded proposer receives no feedback, but its validation selector does.
Memory retrieves by distance in two forward-visible panel state variables,
with stable case-ID ties and a 24,000-byte serialized budget. Each retained
experience includes its review and asset-level predictions/outcomes. Selection
does not rank examples by profit or forecast error. The memory method is a
bounded local comparator inspired by FinMem, not a reproduction of that system.
Its context allowance is larger than a short skill's; actual cost/context must
be reported, and this comparison does not establish equal-token efficiency.

Assessment reports the selected skills, raw memory comparator, unchanged rich,
price and metadata models, an unchanged repeat, and the selected hindsight
skill on metadata-only input. Numerical controls are zero, relative momentum,
the earlier ridge, training-fitted ridge and training-fitted calibration.
An unchanged selection reuses baseline observations; only the repeat samples
the same policy again. The full selection is reconstructed from authentic
validation responses before assessment. A consumed/interrupted final seal
cannot silently launch another assessment.

## What the score can establish

The primary loss is squared return error, averaged over the fixed stocks and
then equally over issue dates. Missing, invalid or abstained forecasts make
the aggregate loss unavailable; they never improve it by disappearing.

Each date's MSE separates exactly into the error in the panel's mean forecast
and the error in centered, relative-stock forecasts. Pairwise ordering accuracy
is reported separately because relative magnitudes and rankings differ.
Training-fitted calibration tests whether apparent learning is mostly an
intercept/scale correction. Paired comparisons use issue-date losses with a
five-batch circular block bootstrap; the intervals are descriptive and
unadjusted for multiple comparisons, not a superiority decision rule.

Seven prepared semantic probes change expectations, paraphrase information,
repeat a fact, remove support and introduce an already observed price response.
The authorized `probes` action runs both nodes and records outputs for review.
Schema acceptance is not a semantic pass; probe text has no counterfactual
historical-return label. No model probe has run under the current hold.

## Reproduction and execution boundary

Owners are `benchmarks/traderharness.py`, `research/ashare_protocol.py` and
`research/ashare_study.py`. They reuse the existing two-node validators, native
research serialization and exact paid-response/cache ledger joins. This is an
explicit experimental adapter; it does not execute the original 28-node Lab.

Install the optional study dependencies and use a fresh output directory:

```sh
python -m pip install -e '.[study]'
python -m research.ashare_study compile --dataset work/datasets/data-selection/root --study work/ashare-study
python -m research.ashare_study plan --study work/ashare-study --input-usd-per-million 0.30 --output-usd-per-million 1.20
python -m research.ashare_study report --study work/ashare-study --output work/admission-summary.json
```

Compilation is offline. It writes immutable forward packets separately from
evaluator labels/review evidence, binds runtime/data hashes, retains every
scheduled exclusion and records the calendar version and session digest.
It does not load account credentials or change an old study or budget.

The full comparison has a **maximum of 1,213 core calls**, plus 14 optional
probe calls. Actual counts can be lower through unchanged-policy aliasing and
rejected proposals. `execution-plan.json` gives uncached token bounds and a
quote-based cost ceiling; it does not certify model compatibility or authorize
spending. The public model catalogue observed on 11 October 2026 quoted
DeepSeek V4.1 Flash at $0.30/M input and $1.20/M output tokens. Refresh the exact
provider quote before release. The previous 600-call allowance cannot cover
this complete plan; no new allowance or ledger has been created.

Paid `probes`, `development`, `learn`, `select` and `final` commands all require
an explicit hold-release authorization bound to the frozen study hash, an exact
provider tag and one unchanged shared budget ledger. Prior reservations remain
in force. Compatibility must be checked before spending on the cohort. If the
authorized resources cannot support this protocol, compile a separately
declared, time-spaced schedule and narrow the claim before any outcomes are
used; never silently stop early and report a favorable subset.

The source of the method matters. FinMem already uses future-in-training
outcomes to form memories; FinCon revises investment beliefs from completed
episodes. Learning Using Privileged Information supplies the teacher/student
information pattern, without guaranteeing this implementation. CheckList
motivates the controlled semantic probes. The [paper](../paper/zenith.pdf) and
[source manifest](finance-adaptive-sources.json) describe these relationships.
The open contribution is whether a compact lesson improves later use of
admitted evidence beyond outcome-only learning and reflected experiences.
