# Frozen weekly forecast benchmark

From repository root, using Python 3.9 or later:

```sh
python3 -m benchmark.run --output web/data/benchmark.json
python3 -m unittest discover -s tests -p test_benchmark.py -v
```

No package installation, API key, model endpoint or network request is needed.
The command writes the deterministic UI receipt and `predictions.csv` alongside
it, plus exact source-manifest and attribution projections. It also projects
this document to `web/docs/methodology.md`. Repeated builds from identical inputs
produce identical bytes. The receipt contains the source checksum, the prediction
CSV checksum, the benchmark implementation checksum and protocol version.

The source is the unchanged, CC BY 4.0 UCI Dow Jones Index dataset: 750 weekly
observations of 30 stocks during January–June 2011. See
[`ATTRIBUTION.md`](../data/historical/ATTRIBUTION.md) and
[`source_manifest.json`](../data/historical/source_manifest.json).

Each forecast asks whether the following observed week's close exceeds that
week's open. Current-week features are assumed available after the current
week's last close. This does not establish a precise historical publication
time. Future prices are read only to reconstruct labels; they never enter the
feature mapping received by a model. Future dividend metadata is also excluded.
Labels are independently compared with the following same-stock source row.

The frozen split trains on 330 Q1 observations and evaluates 360 Q2 observations
over 12 issue weeks. Thirty Q1 observations are purged because their next-week
horizon crosses into Q2. Thirty final Q2 observations are excluded because their
next-week prices cannot be verified within this dataset. All accepted training
labels resolve before the first holdout issue. Model fitting occurs once on the
training split. There is no tuning on the holdout.

The three baselines are neutral 50%, a smoothed training-label frequency, and a
fixed momentum rule (60% after a positive current week, otherwise 40%). Results
use Brier score, first grouped by week and then averaged over weeks. Assets
within a week are correlated; 360 rows are not 360 independent trials. No
confidence interval or significance claim is made from this short sample.

This is a reproducible historical evaluation demonstration. It does not
evaluate LLMs, simulate trading execution, establish corporate-action or vintage
correctness, or report portfolio profitability. Fresh prospective forecasts
belong to a separate evidence lane.
