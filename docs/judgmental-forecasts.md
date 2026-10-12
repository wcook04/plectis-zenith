# Forecasting under uncertainty in the existing graph

The native Lab can now express a numerical belief without claiming to have
identified a market cause. `forecast_basis: JUDGMENTAL` freezes three return
quantiles at CP1: q10, q50 and q90. The Director carries them into the same CP2
and Oracle scores the original values. This extends the daily graph; it is not
a separate reasoner, neural-network weight update or evidence of a learned edge.

The point target is `snapshot_price * (1 + q50)`. q50 is a **median**, consistent
with the existing absolute-error objective, not an expected return. Exact zero
is valid: `FLAT` describes the median estimate, not certainty that the price will
be unchanged. The ordinary direction-hit diagnostic remains separate from the
quantile scores. An abstention still contains no predictions and loses coverage.

CP1 declares `forecast_quantiles` with exactly these fields:

```json
{
  "method": "evidence_conditioned_quantiles_v1",
  "calendar": "XSHG",
  "units": "simple_return_fraction",
  "calibration_status": "UNVALIDATED",
  "targets": [{
    "target_id": "000858", "q10": -0.03, "q50": 0, "q90": 0.03,
    "evidence_refs": ["[1]"],
    "reasoning": "Illustrative grammar only; values are not a market forecast."
  }]
}
```

The surrounding CP1 also requires `forecast_basis` and `dominant_evidence_track`
to be `JUDGMENTAL`, the usual evidence dictionary and a cited thesis. Each target
needs original STOCK evidence. Extra issuer news can inform the judgment, but its
citation is not evidence of causal identification or calibrated numerical effect.
Explain why a result is new or already known, whose cash flows it describes,
what expectations are missing, and how these limits affect the estimate. Retain
uncertainty about economic state separately from a numerical forecast.
`target_id` is the source issuer symbol (`000858` in the example), while
`ledger_id` is the cited evidence identity (`S_...`). Preserve both separately.

Validators check original evidence identities, opaque issuer codes, raw closing
quotes, exact median arithmetic, target coverage and the source exchange clock.
Issue time may be the observed close or the adapter's one-minute availability
stamp; the target must be the next actual XNYS/XSHG close, including holidays.
The entire object is locked through Director and Oracle. A later reviewer may
propose a new skill but cannot replace earlier beliefs with hindsight estimates.
Quantiles must be ordered finite fractions above -1 and at most 10; the upper
bound is only a numerical safety limit, not a finance assumption or fitted cap.

For realized simple return y and quantile q at probability p, the diagnostic is
`max(p*(y-q), (p-1)*(y-q))`. This is unscaled pinball loss; we average it at the
three fixed levels. It is a standard consistent quantile score, following
[Gneiting and Raftery (2007)](https://doi.org/10.1198/016214506000001437).
Three quantiles do not determine a full distribution. We additionally report
nominal 80% interval coverage and width; coverage alone does not reward sharpness
or establish calibration. Feedback and Oracle's reconciliation share this
calculation, so Evolve receives the same diagnostics. The cohort's existing
selection objective is unchanged; quantile diagnostics do not silently select a
new winner.

Compare the reasoning with predictions made from the same earlier price history,
and with unchanged-price persistence for the central estimate. Any subjective
adjustment needs later evaluation. Historical models can recognize these dates;
local source isolation is not evidence that the model never saw the outcomes.

## Completed development episode

The [verified receipt](judgmental-pilot-receipt.json) records all 28 Lab and 31
Oracle nodes on the April 28 → May 4, 2023 XSHG pair. Thirty-two primary-agent
responses were accepted; one rejected Oracle enum value was corrected and
retained. No previous-run responses were reused and no paid provider call was
made. All ten stocks received forecasts, with eight zero medians and small
negative medians for `002460` and `601012`. Inputs contained 21 closing prices
per stock and 22 text items. This is exposed historical development.

| Same-input forecast | Median MAE | Mean pinball loss | Interval coverage | Mean width |
| --- | ---: | ---: | ---: | ---: |
| Lab judgment | 1.1985 | 0.3954 | 10/10 | 5.8700 |
| Prior 20-return quantiles | 1.1592 | 0.3536 | 8/10 | 4.2198 |
| Unchanged price | 1.2685 | — | — | — |

Loss and width are in percentage points of simple return. Lower losses are
better. The historical reference uses the median and inclusive linearly
interpolated q10/q90 of the twenty observed returns; it was frozen before
later truth inspection. Both controls are arithmetic comparisons, not native
matched graph arms. Ten stocks on one date cannot establish calibration.

The result motivates restraint: Lab beat persistence but lost to the price-only
reference on both losses. The reviewed Evolve candidate requires an explicit
historical reference and the exact evidence-based change to each quantile.
Missing feeds alone do not justify wider tails. The later diagnostic below
tested that candidate; it did not pass generation retention.

Oracle also exposed an omitted earlier COSCO profit-guidance claim. The
[separate retrieval profile](traderharness-daily.md#retaining-earlier-issuer-state)
recovers it under the original issue cutoff. It changes source selection and
must be controlled separately from the prompt change in later experiments.

Re-export from the original completed local programme with:

```sh
python scripts/export_judgmental_pilot.py \
  --work-dir work/judgmental-native-20261012 \
  --output docs/judgmental-pilot-receipt.json
```

The exporter checks completed native state, original forecast locks, dated
truth, the pre-truth freeze and independently reconstructed price controls.
It exports numeric results and provenance hashes, not raw licensed headlines
or private reasoning transcripts. The receipt is reviewable from a cold clone;
full re-export requires the ignored original execution artifacts.

## The later instruction comparison

The [May 5 → May 8 receipt](judgmental-matchoff-receipt.json) records two complete
28-node Labs using the same ten-stock snapshot and profit-state retrieval
profile. Only the `lab_decide` instruction differed. The same primary agent
authored both versions, deliberately sharing ten current-day upstream responses
through Orient, then freezing both full forecasts before inspecting later truth.
This isolates the authored decision difference but is not an access-isolated,
independent model trial. No historical forecast response was replayed.

The original instruction produced zero medians with historical tail endpoints.
The revised instruction retained all historical quantiles, including ten
negative medians, with zero news adjustments. Eight stocks subsequently rose.

| Native forecast | Median MAE | Mean pinball | Coverage | Mean width |
| --- | ---: | ---: | ---: | ---: |
| Original instruction | 1.2413 | 0.4557 | 7/10 | 4.1743 |
| Revised instruction (= historical quantiles) | 1.5597 | 0.5087 | 7/10 | 4.1743 |

Loss and width use percentage points of return. The original median coincides
with unchanged-price prediction. The corresponding relative target-price
errors were 1.2232% and 1.5369%; that metric divides absolute return error by
one plus realized return and must not be called return MAE.

The formal comparison **failed admission**. A baseline target-ID correction
created 22 supplied responses against the frozen allowance of 21; the challenger
used 21. The rejection and original limit remain intact. The table is a
descriptive reconstruction of already-frozen forecasts, not an accepted cohort
result. The exporter checks original locks, dates, source histories and Oracle
scores. A source-only reader can inspect the numeric rows; full regeneration
requires the ignored original runs.

The challenger's 31-node Oracle completed with 11 accepted responses and
preserved every original quantile. The primary agent then reviewed the existing
fixed Evolve prompt and its source-bound artifacts, recommending **no change**.
This is a recorded lead-agent review, not an imported bridge run or daily
controller receipt. No policy or dossier was promoted and no paid call occurred.

The useful distinction is between **reporting a reference** and **choosing a
forecast**. This revision reported its assumptions more clearly but did not
improve the day's numbers. Neither this result nor the previous day establishes
the best default. A later comparison should keep reference-only cases, compare
zero and historical medians, and test whether evidence-conditioned adjustments
improve losses against a direct reasoner on the same inputs. Merely citing news
does not demonstrate that it contributed to a forecast.

```sh
python scripts/export_judgmental_matchoff.py \
  --work-dir work/quantile-matchoff-20261012 \
  --output docs/judgmental-matchoff-receipt.json
```
