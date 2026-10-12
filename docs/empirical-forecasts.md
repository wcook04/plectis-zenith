# Testing a prediction without inventing its cause

The full Lab now supports an explicit `forecast_basis: EMPIRICAL` alongside
legacy `CAUSAL` forecasts and evidence-bound abstention. A causal explanation
and a predictive rule are different research objects: an unknown cause does
not prevent testing a rule, and a correct prediction does not identify a cause.

This addresses an observed constraint in the July 23–24 InvestorBench pilot.
The supplied Microsoft earnings item announced results without containing
them. Lab correctly declined to invent an earnings surprise. That limitation
should not prohibit a separately declared price-history experiment. The
completed causal attempt remains unchanged and scored as a no-call.

The first empirical operator is a deliberately simple **price-only control
inside the full 28-node graph**, which still receives and reviews STOCK and
NEWS. It is not evidence that news adds value, a replacement graph, or an
implementation of AlphaGo. Richer operators require their own declared input
mapping and later evaluation; this control provides a concrete starting point.

For each chosen stock, take the last `lookback_returns + 1` observed daily
prices ending at the issue close. Compute each simple return, average them,
multiply by `scale`, and clip to `±max_abs_return`. The next-session target is
`last_price × (1 + clipped_return)`. All return parameters are fractions.

CP1 declares and freezes:

```json
{
  "forecast_basis": "EMPIRICAL",
  "dominant_evidence_track": "EMPIRICAL",
  "empirical_rule": {
    "method": "trailing_mean_return_v1",
    "lookback_returns": 5,
    "scale": 0.25,
    "max_abs_return": 0.02,
    "target_ids": ["MSFT", "HON", "JNJ"],
    "evidence_refs": ["[1]", "[2]", "[3]"],
    "selection_basis": "Illustrative unvalidated control; not a fitted model.",
    "calibration_status": "UNVALIDATED"
  }
}
```

The ordinary evidence dictionary, cited thesis and rationale remain required.
The thesis describes the predictive hypothesis and its limits. Parameters
allow 1–19 trailing returns, a nonzero scale from −1 to 1, and a positive cap
at most 0.1. Negative scale represents a declared reversal hypothesis. Bounds
are implementation limits, not estimates of reasonable market risk.

The engine checks source stock IDs, consecutive XNYS sessions, positive finite
prices, the issue close and next-session close, the complete declared target
set, and independently recomputed target prices. The Director cannot change
CP1's basis or rule. Oracle must preserve an empirical subject's rule instead
of fitting a hindsight-optimal coefficient. It can diagnose input errors and
record predictive loss; a proposed different rule belongs to a later experiment.

No zero-return prediction is replaced with a tiny UP/DOWN forecast. The existing
CP2 direction interface still requires a nonzero target; abstention remains
available. The existing feedback evaluator separately compares eligible
forecasts with unchanged-price persistence. Selective forecasting and a FLAT
CP2 mode are not implemented by this change.

A later success is evidence about that frozen prediction only. Learning claims
require later matched incumbent/candidate outputs, complete target coverage,
all retained failures and a selection protocol separate from final assessment.
A parameter chosen after inspecting this pilot's outcomes is development,
not an untouched test. This implementation changes the experiment interface;
it does not certify a calibrated or profitable strategy.

## The completed two-day sequence

The primary agent completed the July 24 and July 27, 2020 issues using the native
importer: each Lab completed 28/28 nodes with 21 reasoning responses, and each
Oracle completed 31/31 with 11 accepted responses. One Oracle response initially
used prose in an enum field; it was rejected, retained and corrected. No paid
provider calls or prior-run response replays were used for these two issues.

The first rule used five returns, scale 0.25, cap 0.02 and all three equities.
After its July 27 outcomes, Evolve proposed changing only scale to 0.125. The
reviewed addon was present in the next Lab's actual `lab_decide` prompt, and
that Lab's frozen targets used it before the agent opened July 28 outcomes.

| Issue → outcome | Native rule | Native MAE | Unchanged scale 0.25 | Persistence |
|---|---|---:|---:|---:|
| July 24 → July 27 | Scale 0.25 | 0.98649 | 0.98649 | 0.93047 |
| July 27 → July 28 | Scale 0.125 | 0.62531 | 0.59575 | 0.65488 |

MAE is the mean across MSFT, HON and JNJ of
`100 × abs(predicted_price − actual_price) / issue_price`, in percentage points
of return. The unchanged and persistence columns are deterministic arithmetic
controls on identical inputs, not separately executed native model arms.
The first issue had one correct direction; the second had two. These are two
dates with correlated assets, not six independent trials.

The actual stored change was tested, and it **did not beat the unchanged rule**
on the next issue. The second Evolve review made no further change from this
tiny contradictory sample. Its `no_change` keeps the experimental policy
lineage; it does not select the candidate as a winner. No generation-retention
command was run. Both versions remain available for a later declared comparison.

The [machine-readable receipt](empirical-pilot-receipt.json) binds forecasts,
actual outcomes, all native artifact hashes, reviews, policies, rejected-response
files and the successor prompt. Rebuild it while the recorded runtime and source
identity remain available with:

```sh
python scripts/export_empirical_pilot.py \
  --work-dir work/investorbench-empirical-20261012 \
  --output docs/empirical-pilot-receipt.json
```

The receipt publishes our numerical findings and reviews, not full upstream
news or private transcripts. Reacquiring the pinned source is independent of
reproducing the primary agent's reasoning. This case establishes that the
experience-to-procedure connection executes; a useful contribution from news,
complex reasoning or sustained learning still requires evidence.
