# Forecast measurements and proposed skill feedback

`python -m feedback` connects accepted Lab CP2 price forecasts to dated truth
and rolling research summaries. It reads the existing graph/artifact interfaces;
it neither collects data nor supplies hindsight to Lab. Run it in the repository's
installed Python environment. There are no API calls in this lane.

## Try the full offline path

```sh
python -m feedback demo --store work/forecast-feedback-demo
```

Use a fresh store path. The command creates **synthetic** grammar/provenance
fixtures: twenty distinct issue times over several weeks, including correct
and incorrect forecasts. It demonstrates pending-to-mature transitions,
idempotent scoring, price/direction metrics, and proposed feedback with the
full denominator. None of these fixtures is a market observation, real model
run, accuracy result or evidence of a useful strategy.

The tests cover real contract validation and negative boundaries:

```sh
python -m unittest discover -s tests -p 'test_feedback*.py' -v
```

## Register an actual accepted Lab forecast

Prepare and complete Lab through `python -m zenith`; do not create or edit
its accepted CP2 artifact by hand. Registration consumes
`artifacts/lab_director.json` through
`system.lib.schema_validator.validate_cp2`, including subject ticker universe,
grounding and declared runtime timestamps. It separately compares every
snapshot price with the subject-run equity baseline. Oracle hindsight CP2
is not an admissible forward forecast.

A feedback policy declares the measurement conventions in advance:

```json
{
  "schema": "zenith_forecast_feedback_policy_v1",
  "policy_id": "quoted-price-error-v1",
  "price_basis": "daily_close_auto_adjust_false",
  "currency": "USD",
  "observation_precision": "session_close",
  "calendar_id": "XNYS",
  "calendar_version": "4.13.2",
  "relative_error_threshold": 0.05
}
```

The calendar version must match the installed `exchange_calendars` package;
the example does not bypass that check. For observations with exact
timezone-aware timestamps, use `observation_precision: "timestamp"` and omit
the calendar fields. Basis and currency must be established in the subject
and truth artifact; declaring them in the policy alone does not establish
their availability. The provider's `auto_adjust=false` setting does not prove
that corporate-action history has been independently checked.

```sh
python -m feedback register --store work/forecast-feedback --subject-run state/runs/LAB_RUN --policy feedback-policy.json --horizon-id next_us_close
python -m feedback score --store work/forecast-feedback --truth state/runs/TRUTH_RUN --as-of 2026-10-12T21:00:00+00:00
python -m feedback summary --store work/forecast-feedback --as-of 2026-10-12T21:00:00+00:00 --window-days 30
python -m feedback propose --store work/forecast-feedback --as-of 2026-10-12T21:00:00+00:00 --window-days 90 --minimum-issue-times 20
```

Replace these illustrative run paths/times with observed local evidence. The
CLI also accepts one historical price-artifact file for `--truth`, using the
existing resolver's row or symbol/date mapping format. Python API owners are
`feedback.engine.register`, `score`, `summary` and `propose`.

Registration preserves the source artifact hash and prediction JSON pointer,
actual/requested model receipt, feedback policy hash, runtime reasoning policy,
and frozen effective ancestor node hashes/edges. Actual model identity can be
unavailable; it is never replaced with a router alias. Named skill loading is
not inferred: where present, the actual frozen `skill_addon` hash and context
policy receipt identify instruction participation. Captured replays remain
distinct from live model executions. Missing frozen ancestry or model identity
prevents feedback eligibility.

Registration after a forecast's horizon is labelled `historical_import`. Local
source hashes preserve what was admitted; admission does not prove the forecast
was published contemporaneously or prevent an operator from fabricating a
source. Synthetic fixtures are segregated from other records.

## Exact horizons and observation dates

Each forecast retains its exact `snapshot_time` and `target_time_iso`, plus
declared `horizon_id` and elapsed seconds. Duration IDs such as `24h`, `48h`
and `7d` must match those timestamps. `next_us_close` must match the native
XNYS calendar resolver. For several horizons, run separate locked CP2 runs
at the same issue time with different target times; their results stay in
separate horizon groups. A second label for the same run/target/horizon is
not a new forecast.

Truth must match the exact declared target. Timestamp mode requires an exact
aware timestamp, including intraday time. Session-close mode requires an
explicit bar date mapped to the native calendar's close, including holidays
and early closes. Neither mode rolls to a convenient adjacent observation.

The reader reuses Oracle's table parser and the historical resolver's price
formats. It also retains the provider's explicit
`metadata.diagnostics.price_observations` bar/session-date metadata. Envelope
`as_of` or fetch time is never a substitute for a bar observation date. A
subject observation may predate the issue, but cannot be later; its original
observation time and age at issue remain visible. The direction comparison is
against that recorded snapshot quote, not an independently observed spot price
at issue.

Before maturity the state is `pending`. Missing exact observations, dates,
basis/currency, failed artifacts or duplicates produce `data_gap`, with no
model-error class. Scored truth is immutable: a later revised input cannot
silently replace it. Repeated identical registration/scoring is idempotent.
Each score request is retained independently of the forecast's locked result.

## What the measurements mean

For declared target price P, realized price R and snapshot S, the scorer reports
absolute error `abs(P-R)`, relative error `abs(P-R)/R`, signed error `P-R`, and
the direction relative to S. A realized tie is `FLAT`; an UP/DOWN forecast
does not receive a directional hit for a tie. The no-change price baseline is
S, with errors `abs(S-R)` and `abs(S-R)/R`. Snapshot and realized prices must
be finite and positive. Finite predicted targets, including nonpositive
outliers admitted by the original CP2 contract, stay in the corpus rather
than being selected away.
These are forecast errors, not investment returns.

Rolling summaries select issue times in `[as_of-window, as_of]`, retaining
pending/unscored/data-gap counts separately. They group by horizon, feedback
policy, reasoning policy, actual model, execution kind and scoring implementation
hash, separating historical imports from prospective registrations. They retain
the no-change baseline and all resolved successes/failures. Related assets,
overlapping forecast horizons and successive sliding windows are dependent;
the summary does not call its row count independent trials or attach a
significance claim.

## Review-only propagation

The default batch gate is at least **20 distinct resolved issue times** across
at least three fixed, nonoverlapping seven-day UTC issue buckets. It can be
raised with `--minimum-issue-times`. Repeated horizons/assets/runs at one issue
time do not inflate that count. A candidate class additionally needs failures
on at least three distinct issue times, issue runs and nonoverlapping buckets;
`--minimum-failure-issues` can raise that requirement. These counts are
operational routing gates, not statistically validated thresholds.

Candidate classes are measured direction misses, target-price errors worse
than no-change, and relative error beyond the policy's declared threshold.
Proposals include total failures/resolved, forecast and issue support fractions,
status counts, the full resolved evidence including successes, exact
forecast/truth hashes and observation times, and participating ancestor/skill
lineage. This is a discrete review signal; it is neither causal blame assigned
to an ancestor nor a mathematical gradient.

Proposals persist under the store's `proposals/` and in `feedback.sqlite3`.
Every proposal has `live_mutation_permission=false`. Review the underlying
cases, form one falsifiable instruction/context change, then test on new
heldout or prospective shadow evidence with an uncertainty assessment before
any promotion. A price-error hypothesis needs price-error evaluation; a
probability-mapping Brier improvement alone cannot establish it. The feedback
command never edits skills, live dossiers or the graph.

Stores are local research state. They contain asset-level forecasts, prices
and evidence lineage and are not part of the Observatory aggregate export
allowlist. Keep them outside `web/` and review disclosure separately.
