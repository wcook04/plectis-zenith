# Learning what to notice in financial evidence

Zenith asks whether experience teaches a compact financial reasoning skill that
improves later forecasts beyond ordinary outcome feedback and retrieved memories.
The supplied evidence must support the distinctions we demand, and the comparison
must include capable inexpensive alternatives.

**Paid inference remains on hold.** The revised [admission receipt](ashare-admission.json)
and [first-run profile](ashare-first-run.json) describe compiled inputs and frozen
execution choices. The [cheap-control measurement](ashare-development-controls.json)
uses development data only. There is no new LLM, learned-skill or trading result.
The earlier US experiment and its immutable result exports remain separate.

## Evidence and the reasoning job

At each issue, one minute after an XSHG close, both reasoning nodes receive twenty
completed sessions, a preceding close, a numerical anchor fitted on 2021 data,
dated evidence and the exact forecast interval. Interpretation comes first; the
forecaster receives both the interpretation and original evidence. Only its short
skill, at most 1,200 characters, is initially mutable. Mixed dated prices/news,
related-stock examples and financial instruction tuning are established prior art
in [Yu et al.](https://arxiv.org/abs/2306.11025v1). Their return bins and fine-tuning
are different from this study's continuous target and short-skill update.

The interpreter distinguishes reported facts, comparison with an earlier claim,
explicit expectations, contrary evidence and the effect potentially remaining
after entry. An issuer estimate is not market consensus; positive growth alone
is not a surprise. Entry at next open excludes the first overnight price move.
The initial-response/drift distinction in
[Lopez-Lira and Tang](https://arxiv.org/abs/2304.07619v6) motivates this separation,
without establishing predictable remaining returns in this Chinese panel.

The revised interpreter also distinguishes the reported subject from the forecast
issuer, direct relevance from a hypothesized indirect channel, and supported
relationships from unknown ones. It requests short supporting spans and source
references. [Huang et al.](https://arxiv.org/abs/2604.19476v2) retrieve candidate
pairs and then classify relationships using disclosure evidence. That distinction
is useful here; their disclosure graph, competitor deletion and mean-reversion
weights are not imported. The validator checks references, shape and bounds, not
span entailment or the validity of economic reasoning.

Fixed retrieval retains up to four issuer-tagged items and two common headlines
from the previous seven calendar days, deduplicated by normalized content and
capped at 600 characters each. Up to two older numerical profit claims are added
when the candidate issuer token and fiscal-period key match a current claim,
strictly earlier and within 180 days. The latest distinct match wins. Year inference
is restricted to explicit intra-year periods and recorded; unsupported or ambiguous
periods abstain. Original text, clocks, references and matching basis remain intact.
A match is a candidate comparison, not verified entity or accounting equivalence.

Five recurring training omissions justified that patch: Moutai's Q1 and H1 updates,
Tongwei Q1, LONGi H1 and COSCO H1. The revised full panel adds only **11** older
items: five training, two validation, four assessment. Thirteen asset windows
have a candidate comparison, including two with an already-retained earlier item.
This narrow coverage is a limitation, not a rich-history claim.

The corpus contains headlines and announcement titles, not full article/report
bodies. Source tags can conflate related listed companies: inspected BYD Electronic
news carries BYD's A-share token. Similarity or a tag cannot establish an economic
relationship. Unverified financial-statement vintages remain excluded.

News epochs are UTC and independently match their Shanghai display timestamps.
Midnight announcements are treated as day precision and become eligible at the
following exchange open; timed announcements use the declared Shanghai-clock
assumption. These rules qualify publication metadata, not historical wording.
Issuer codes appear in every treatment; `asset_N` is a join key, not anonymization.

| Treatment | Information |
| --- | --- |
| Price | Issuer identity, history, numerical state and anchor |
| Metadata | Same prices plus admitted event times, types, counts and source IDs |
| Rich | Same selected records with their retained text |

Each treatment has its own interpretation. Named entities inside rich text still
provide additional cues; rich-minus-metadata does not isolate every identity effect.

## Dates and return accounting

The compiler verifies the pinned [TraderHarness software](https://github.com/HephaestLab/TraderHarness/tree/3e18369da5a2060f9c65b27c2a63f99edd93e167)
and [dataset](https://huggingface.co/datasets/ANTICH/traderharness-ashare-5y/tree/3bf5151ab3e94851bb09dd8ade815563c44b15a6)
provenance, then checks historical and outcome bars against XSHG sessions. Warmup
stays within the continuous February 2023 onward panel. Of 138 scheduled
nonoverlapping five-session windows, two cross phase boundaries and are purged.

| Phase | Admitted issue dates | Asset forecasts | First–last issue |
| --- | ---: | ---: | --- |
| Training | 41 | 410 | 2023-03-01–2023-12-22 |
| Validation | 47 | 470 | 2024-01-08–2024-12-20 |
| Assessment | 48 | 480 | 2025-01-06–2025-12-24 |

All 136 admitted windows have complete stock/benchmark bars. Of 1,360 asset
windows, 452 have no issuer-tagged item; every window has two common headlines.
`work/ashare-v2-full-bound-20261012/representative-inputs.json` retains ordinary,
issuer-information, thin-information and action-boundary examples chosen by
chronology/input properties, never forecast success. The original compiled study
at `work/ashare-offline-20261011/` remains an immutable reference to its old source.

The label is next-session open to fifth-session close stock gross wealth return
minus the matching CSI 300 price-index return. For holdings across an ex-date,
cash uses the pre-event share quantity; additional shares and unreinvested gross
cash enter the terminal wealth mark. Buying at the ex-date open receives no
prior-holder entitlement. Cash is a receivable and shares are valued without
claiming immediate liquidity. This mixed-basis difference is not an executable
hedged portfolio return. Taxes, costs, lots and trading constraints are excluded.

Historical OHLC is a gross wealth path rebased to one, using only actions occurring
and announced by its issue cutoff. Future distributions cannot rewrite past
inputs. Volume is normalized within-window after share multiplication; absolute
units change across source eras and are not features. Missing turnover is omitted,
not zero-filled. State includes CSI 300 past returns and volatility. Independent
Fraction tests cover entitlement boundaries and successive distributions; five
real checks are in [ashare-label-checks.json](ashare-label-checks.json). BYD's
[issuer announcement](https://static.cninfo.com.cn/finalpage/2025-07-22/1224237000.PDF)
confirms the inspected A-share event, not every archive record.

## Learning and strong comparators

Outcome and hindsight teachers receive identical complete forward traces,
interpretations, forecasts and per-asset residuals. Hindsight alone adds reporting
from the full completed outcome interval, including holidays. Its latest used
report and outcome jointly determine the earliest lesson availability. Everything
is bounded by the training cutoff. This follows the privileged-teacher pattern
of [Vapnik and Izmailov](https://jmlr.org/papers/v16/vapnik15b.html), without importing
their guarantees for prompt learning.

| Policy | Learning information | Mutable object |
| --- | --- | --- |
| Base | None | None |
| Outcome | Original traces and matured outcomes | One short skill |
| Hindsight | Same, plus later reporting | One short skill |
| Blinded, full profile only | Protected task and base skill | One feedback-free proposal |
| Memory | Same hindsight bank | Up to three eligible retrieved experiences |

Each review states a trigger, conditional lesson, uncertainty, disconfirmation
and references. Reasoning error, ignored alternative, new information, accounting
error and unresolved outcome remain distinct. Rejected reviews stay recorded.
One proposal per skill arm competes against unchanged on validation; unchanged
wins ties, and incomplete support cannot win. A blinded proposal's selector still
uses validation. Selected artifacts are frozen before assessment; one artifact
per arm does not establish reliability across independent learning runs.

Reflected experiences follow [FinMem](https://arxiv.org/abs/2311.13743v2), while
persistent investment guidance is related to [FinCon](https://arxiv.org/abs/2407.06567v3).
Numeric/narrative analog retrieval also appears in
[Wang and Yeung](https://doi.org/10.3389/frai.2026.1722121), whose targets are quarterly
network indicators. The local memory comparator is not a reproduction of these systems.

Retrieval fixes `0.8 * text_cosine + 0.2 * state_proximity`. Text is character
2–4-gram TF–IDF fitted only on eligible training packets (`min_df=1`, max 8,192
features). Common stories are deduplicated across assets; constant issuer
boilerplate is excluded from retrieval. State proximity is
`exp(-0.5 * mean(standardized_squared_distance))` over panel mean five-session
return and twenty-session volatility. Scales use the eligible training bank,
with unit scale for zero variance. Queries contain no lessons, later reporting
or outcomes. Ranking never rewards profit or small errors. Stable case-ID ties,
three-case and 24,000-byte caps remain. Its larger context than a skill precludes
an equal-token efficiency claim.

Cheap controls pair numeric/metadata/issuer ridge with an otherwise matched text
ridge. Text uses the exact retained evidence, character 2–4-grams, `min_df=2`,
max 8,192 features and TF–IDF. Numeric scaling, vocabulary, weights and regression
fit matured training data only. Issuer one-hot cues are shared; columns have fixed
names/order. Ridge penalty is one, solver sparse LSQR. Fitted transform/model
hashes and library versions are bound. [Ke, Kelly and Xiu](https://www.nber.org/papers/w26186)
motivate supervised target-trained text modeling; this simple comparator does not
reproduce their method. [Scikit-learn](https://www.jmlr.org/papers/v12/pedregosa11a.html)
provides TF–IDF and ridge.

The [development measurement](ashare-development-controls.json) expands fitting
chronologically after eight warmup issues and scores the remaining 33 dates
(330 assets). MSE: **zero 0.00109518**, **numeric/metadata/issuer 0.00141850**,
**with text 0.00148344**. Text is worse on this fixed diagnostic. Settings were
not tuned after seeing these scores. No validation, assessment or LLM score was
consumed. This result neither establishes text usefulness nor rules it out.

## Scores, failure behavior and behavioral checks

Primary loss averages squared return errors within each issue, then weights issues
equally. It decomposes exactly into panel-mean error and centered relative-stock
error. Pairwise ordering is reported separately. Other numerical controls are
zero, relative momentum, 2021 ridge, training ridge and training-fitted calibration.

Missing, invalid or abstained output makes the raw aggregate unavailable. A
separate frozen system policy substitutes zero market-relative return, retains
failures and reports fallback frequency. That score cannot select a skill.
For baseline `b`, realization `y` and revision `b+delta`, the exact correction
identity is `gain = 2*(y-b)*delta - delta**2`, with the same date weights. Moving
in the right direction can still overshoot. It diagnoses arithmetic contribution,
not causal reasoning. Paired losses use descriptive five-issue circular-block
intervals, not multiplicity-adjusted superiority tests.

Eleven [CheckList-inspired](https://aclanthology.org/2020.acl-main.442/) probes test
expectations, paraphrase, duplication, missing support, prior repricing, wrong
subject, unsupported relation, indirect input-cost transmission and issuer
estimates. They run both nodes and retain outputs for substantive review. Schema
acceptance is not semantic success. Synthetic stories have no counterfactual
historical labels. Future-news lexical overlap, used in Yu et al., is not adopted
as explanation fidelity. No real model probe has run under the hold.

## Execution profiles and reproduction

Owners: `benchmarks/traderharness.py`, `research/ashare_protocol.py`,
`research/ashare_text.py`, `research/ashare_study.py`. They reuse the existing
validators, serialization, exact response cache and shared-budget provider.
This adapter remains separate from the original 28-node Lab.

```sh
python -m pip install -e '.[study]'
python -m research.ashare_study compile --dataset work/datasets/data-selection/root --study work/ashare-study --profile first_learning
python -m research.ashare_study plan --study work/ashare-study --input-usd-per-million 0.30 --output-usd-per-million 1.20
python -m research.ashare_study report --study work/ashare-study --output work/admission-summary.json
python -m research.ashare_study offline-controls --study work/ashare-study --output work/development-controls.json
```

Compilation is offline and refuses overwrite. It separates packets from labels,
binds source/data/runtime versions, preserves exclusions and records the calendar.
Original text remains local under source terms; public receipts omit it.

The **full** profile permits 1,213 core calls, plus 22 probes and 24 additional
development information controls: **1,259 total**. The **first_learning** profile
retains all 41 training and 48 assessment dates, with 24 evenly spaced validation
positions including endpoints. Rich base, outcome, hindsight and memory require
**526 core calls + 22 probes + 24 development controls = 572 maximum calls**.
Six evenly spaced training dates receive price/metadata/rich capability comparisons;
the rich observations are reused in development. This profile drops blinded
proposals, assessment price/metadata contrasts, metadata transfer and unchanged
repeat claims. Choosing fewer validation dates preserves assessment coverage;
this is a declared budget tradeoff, not retrospective subsampling.

Stages: `capability`, complete `development` and `learn`, `select`, then `final`.
Capability records probes and information contrasts for inspection; it does not
automatically certify semantics. Selection and all teacher artifacts are rebuilt
from authenticated responses before assessment. Unchanged policies reuse cached
base draws; only the full-profile repeat gets another draw. A spent/interrupted
final seal cannot silently resample. No automatic retries are permitted.

The planner reports actual prepared prompt byte lengths, bounded intermediate
responses and maximum outputs. Compact Unicode prompts avoid unnecessary escapes;
canonical hash bytes stay unchanged. No expected bill is invented without actual
model usage. The October 11 catalogue quote was $0.30/M input and $1.20/M output;
refresh the exact provider quote before release. Schema-maximum cost bounds are
not expected charges: the first profile's quoted ceiling is $36.46, so fitting
under a 600-call cap does not establish affordability under the earlier $4 cap.
The adapter retains conservative reservations rather than assuming refunded
headroom from cheap responses. The existing immutable ledger alone determines remaining
money/calls, including earlier reservations; 572 calls is not authorization.

Every paid command requires explicit hold release bound to this frozen study,
an exact provider tag and the same shared budget ledger. No new allowance, ledger
or paid call was created. The three supplied papers have native annex records,
source-level limitations and explicit adoption/deferment/rejection decisions.
The two copies of arXiv:2306.11025v1 have identical decoded page content and no
distinguishable operator annotations. The [source manifest](finance-adaptive-sources.json)
and [paper](../paper/zenith.pdf) cite borrowed ideas where they are used.
