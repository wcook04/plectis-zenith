# Zenith research manuscript

[zenith.tex](zenith.tex) and [zenith.pdf](zenith.pdf) now describe **Learning to
Reason About Financial Change: Method and development evidence**. This is the
standalone Zenith manuscript, separate from the Plectis system paper and private
strategy document.

The argument begins with actual issuer guidance changes, separates financial
interpretation from numerical payoff, reports the measured overscaling diagnosis,
and presents the concrete source-rich development cases. The active daily loop now has a full native Lab/Oracle development execution and a reviewed, untested next-day skill candidate. The direct/graph and
learned-reasoning comparisons remain unexecuted. No LLM advantage, transferable
learning, explanation fidelity, novelty or profitability is claimed.

Citations appear beside borrowed mechanisms, methods, data, software and issuer
facts. [references.bib](references.bib) retains the larger reviewed inventory;
only sources used in this manuscript appear in its bibliography. Six primary
issuer releases support the actual financial examples. The supplied Huang,
Wang/Yeung and Yu papers are cited at use, with target and method differences
stated. The two Yu uploads are duplicate page content, not independent sources.
Parent annex provenance remains in
[finance-adaptive-sources.json](../docs/finance-adaptive-sources.json).

Build from this directory:

```sh
tectonic --keep-logs --reruns 2 zenith.tex
```

Tectonic runs the bibliography pass. Source and bibliography are Apache-2.0.
`paper-house-style.sty` retains Will Cook's CC-BY-4.0 header and is the exact shared
style copy with SHA256
`1b4630ead32bfb407a2f29f5953fbb8d4140a659f6500799282a4805ba54a883`.

## Current measured and compiled evidence

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
