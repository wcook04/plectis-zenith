# Zenith research manuscript

[zenith.tex](zenith.tex) and [zenith.pdf](zenith.pdf) describe **Zenith: Learning a
Financial Reasoning Pipeline from Daily Experience**. This is the standalone
Zenith paper, separate from the Plectis system paper and private strategy.

The argument follows the original daily Lab → Oracle → Evolve loop: available
feeds, the full native forward graph, frozen forecasts, later diagnosis, reviewed
procedure changes and later evaluation. Supporting A-share calibration and issuer
guidance remain evidence and examples, not the selected replacement programme.

Citations appear at the use of external mechanisms, datasets and financial facts.
The supplied Huang, Wang/Yeung and Yu papers retain their distinct target and
method boundaries. Neither source assimilation nor completed manual development episodes
establishes novelty, forecasting advantage, transferable learning or profitability.
The daily review importer validates structure and quotations, not semantic truth.

Build from this directory with `tectonic --keep-logs --reruns 2 zenith.tex`.
Source and bibliography are Apache-2.0; `paper-house-style.sty` retains its
CC-BY-4.0 attribution. The standalone checkout includes the bibliography and style.

## Current measured and compiled evidence

- [Constructed learning example](../docs/learning-design.md#a-small-closed-system-we-can-run) and [receipt](../docs/learning-microcosm-receipt.json): twelve deterministic operator combinations, whole-universe selection loss, separated training/validation/assessment and a noise control. Joint search succeeds where strictly improving single-edit search stops at zero. The correct rule is deliberately in the bank; this is no LLM or financial improvement claim. Autoresearch and selective prediction are cited at their uses in the manuscript.
- [Richer native daily source](../docs/traderharness-daily.md) and [receipt](../docs/traderharness-native-receipt.json): ten stocks, 696 complete trailing-price windows and 695 next-close pairs. One full Lab/Oracle episode completed with 32 accepted responses, an explicit no-call and a reviewed issuer/listing-check candidate. Later benefit is untested. The paper cites the separate HKEX issuer verification where used; it was not added to the frozen native inputs.
- [Empirical sequence](../docs/empirical-forecasts.md) and [receipt](../docs/empirical-pilot-receipt.json): two complete Lab/Oracle pairs, one reviewed scale change used by the next Lab, and a later loss against unchanged-rule arithmetic. Sixty-four accepted primary-agent responses and one retained correction; no new paid calls. This demonstrates an actual transition without a learning advantage or measured news contribution.
- [Herculean audit](../docs/herculean-audit.md): two dated news counterexamples verified against original issuer releases. The paper cites the database and releases where the finding is used. News remains quarantined; no global contamination rate is inferred.

- [Native abstention](../docs/abstention.md) and [receipt](../docs/abstention-receipt.json): a completed 28/31-node Lab/Oracle contract replay, unresolved causal diagnosis and reviewed no-change. Twenty-nine reused responses are disclosed. No forecasting score or learned advantage exists for this no-call.

- [InvestorBench admission](../docs/investorbench-admission.json): pinned three-equity source, 291 complete shared sessions, 4,990 summaries, date-lag assumptions and excluded filings. This is data coverage, not a new forecast result.
- [Generation comparisons](../docs/generations.md): reviewed candidates through the existing native cohort and explicit retention with an enforced evidence cutoff. No completed generation comparison is reported. The paper cites AlphaGo Zero for the design analogy where introduced.

- [Daily replay](../docs/daily-replay.md) and [receipt](../docs/daily-replay-receipt.json): pinned FNSPID raw AA sources, rejected paid trial, complete primary-agent Lab/Oracle, exact outcome comparison and one reviewed next-day policy candidate. The manuscript cites the dataset where used. No learned performance gain is established.

- [Development diagnosis](../docs/ashare-development-diagnosis.json): original
  forecasts, date-equal energy/alignment, chronological calibration, common and
  relative errors, source binding and fit boundaries. Calibration design used
  earlier aggregate development results; there is no untouched-test claim.
- [Guidance sources](../docs/guidance-development-sources.json) and
  [compiler receipt](../docs/guidance-development.json): six original releases,
  four events, 13 comparisons, clocks, hashes, rights and price-basis limitation.
  Selected transcriptions are not full autonomous report extraction. Model
  requests exclude the oracle and do not ask for returns.
- [Base batch](../docs/ashare-base-plan.json): an unexecuted 21-call direct/graph candidate,
  exact frozen cohort and conservative USD0.5860815 quote. The later operator
  instruction dedicates remaining programme funds to research; Type B may
  recommend replacing this candidate.
  [Active protocol](../docs/ashare-study.md) owns commands and the spending boundary.

The latest [quantile comparison](../docs/judgmental-forecasts.md) includes a
[verified later diagnostic](../docs/judgmental-matchoff-receipt.json). Both
instructions completed the native Lab on May 5 inputs; the revised instruction
retained historical quantiles and had worse May 8 median and pinball losses.
Its baseline correction exceeded the frozen response allowance, so the formal
cohort remained incomplete. The paper reports this admission failure beside
the descriptive numbers. A completed Oracle and recorded lead-agent Evolve
review produced no promotion. The [earlier episode](../docs/judgmental-pilot-receipt.json)
and separate [retrieval repair](../docs/profit-state-retrieval-audit.json) remain
source-bound evidence. No learned forecasting advantage has been established.

## Historical supporting evidence

The old 2015 study compared a manually frozen price-only rule with a model
baseline. It demonstrated pipeline feasibility; it did not learn the rule from
feedback. Its historical assessment was sealed as `native-deepinfra-final-v1`.
Those dates had already been examined. This pilot no longer drives the abstract
or main argument. These exports remain unchanged and do not support claims
about the new financial reasoning system:

- `study-evidence.json`: complete native development/final reports and shared
  accounting. Reproduce with `export_study_evidence.py` using the original study
  at `work/native-deepinfra-study` and its exact original budget ledger.
- `calibration-evidence.json`: four excluded July compatibility pilots, six
  attempts, distinct from the shared ledger total. Raw outputs were not rewritten
  to pass newer instructions.
- `export-validation.json`: export rejection checks and source attribution.
- [repair-controls.json](../docs/repair-controls.json): synthetic deterministic
  routing/control experiments; no model or market result.

Keep future exports separate. Exporting projects completed authoritative receipts;
it never executes, selects or seals a study. Unknown costs and reservations
remain distinct from reported costs. The historical export retains its original 106 attempts, 105 responses and one unknown charge. Subsequent daily-development calls remain in the same immutable ledger and are reported separately in the daily replay receipt. New authorization histories do not erase it.
Detailed historical reproduction remains in [reproducing.md](../docs/reproducing.md)
and [experiments.md](../docs/experiments.md).

| Supporting mechanism | Owner |
| --- | --- |
| Native execution and planning | `zenith/runtime.py`, `system/core/engine.py` |
| Skill/context policy | `system/lib/reasoning_policy.py` |
| Forecast admission and matured truth | `feedback/engine.py` |
| Matched comparison and final seals | `research/cohort.py` |
| Diagnosis and proposal compilation | `research/diagnosis.py`, `research/reflection.py`, `research/reflection_cohort.py` |
| Conditional formal model | `formal/ZenithSemantics.lean`, `scripts/check_semantics.py` |
| Development comparison and scaling | `research/ashare_study.py`, `research/ashare_protocol.py`, `research/ashare_text.py` |
| Fuller-source compiler | `benchmarks/guidance_events.py` |

The formal model assumes constituent contracts; it does not certify LLM
compliance or financial correctness. These are supporting mechanisms.
Authoring followed the parent's route-human-authoring, humanizer and
mathematical-reasoning skills. The square-loss identity is elementary algebra,
not a new mathematical result.
