# StockNet price-only baseline protocol

This protocol uses the 88-stock raw OHLCV universe released with Yumo Xu and Shay B. Cohen's 2018 [Stock Movement Prediction from Tweets and Historical Prices](https://aclanthology.org/P18-1183/). The dataset is pinned to [`330708b5`](https://github.com/yumoxu/stocknet-dataset/tree/330708b5ddc359961078bef469f43f48992fd6e4); its official code/config is pinned to [`e32147c0`](https://github.com/yumoxu/stocknet-code/tree/e32147c07c1e06033fcc8f76525a0c25e8babc16).

The official `src/config.yml` defines half-open train `[2014-01-01, 2015-08-01)`, development `[2015-08-01, 2015-10-01)` and test `[2015-10-01, 2016-01-01)` intervals. `src/DataPipe.py` confirms half-open inclusion. The importer checks these pinned objects before accepting prices.

This is a new price-only regression benchmark. The StockNet paper combines tweets and prices, predicts one-day direction, filters small movements and imposes text/coverage conditions. Our regression scores, longer horizons and unfiltered valid price rows are not reproductions of its published scores.

```sh
git clone --filter=blob:none --no-checkout https://github.com/yumoxu/stocknet-dataset.git work/stocknet-source
git clone --filter=blob:none --no-checkout https://github.com/yumoxu/stocknet-code.git work/stocknet-code-source
python -m benchmarks.stocknet import --dataset-repo work/stocknet-source --code-repo work/stocknet-code-source
python -m benchmarks.stocknet run --ridge
```

Import requests only 88 raw price CSV objects, StockTable, README/license text and the two protocol-source files. No tweets, pickle files, upstream Python code or upstream training scripts are executed. Raw CSVs and generated outputs stay under ignored `work/`; repository MIT licensing does not independently establish Yahoo data redistribution rights.

At each issue-row close, predictors use only that row and its observed past. Open, high, low, close and volume supply eight explicit backward-looking ridge features; adjusted close is excluded because retrospective adjustment can import unavailable information. Labels are future source Close prices and returns after 1, 5 or 20 observed rows for that stock. These are observed-row horizons, not promises that every source row is an exchange session. Historical price vintage/split adjustment and exact intraday availability are unverified; this is a bounded historical comparison, not proof of live point-in-time data quality.

Every label must mature strictly before its split end. The first `h` observed issue rows of each development/test stock split are embargoed for horizon `h`. Past rows preceding the training interval may supply feature warmup; they are never fitted as outside-interval labels. The holdout is frozen and does not select models, scaling or penalty. The optional ridge uses one prespecified penalty of 1 and standardization fitted on matured training labels only. Persistence predicts no change; momentum repeats the preceding equal-row-horizon return.

Primary normalized-return MAE/RMSE first average errors across available stocks on each issue date, then give dates equal weight. Stocks on one date are not counted as independent inferential trials. Nominal price errors are also reported, but share-price scales differ. Direction uses three signs (down, unchanged, up); a zero prediction is neutral rather than an implicit down vote. `nonzero_prediction_fraction` identifies the persistence model's abstention. No P&L or trading policy is computed.

The local output contains:

- `source-manifest.json` in the imported dataset: source-file hashes, rows, date ranges, fields, rejections, commits and rights boundary.
- `frozen-protocol.json` and `results.json`: all prespecified models/horizons, train/development/test exclusions, aggregate metrics and 20-issue-day windows. Trial count is 6 for the two baselines or 9 with ridge; split evaluations are reported separately.
- `predictor-rows.jsonl`: immutable sample ids, issued OHLCV and features, without target price/return/date.
- `truth-rows.jsonl`: matching ids and exact dated realized prices/returns, kept separately for delayed evaluation.
- `issue-packets.jsonl`: grouped subject-only native feed envelopes for future graph comparisons, with unavailable lanes named explicitly.
- `predictions.csv`: every dated model forecast and outcome for score reproduction; it is an evaluation export containing truth and must not become provider context.

The packets reuse `system.lib.feed_envelope`; feedback/research consumers can join predictor and truth rows by sample id and aggregate by the supplied issue windows. StockNet has no news/macro/prediction-market lanes, so these packets do not claim to supply a complete live seven-lane Lab run.

The local full-universe execution imported 108,589 valid source rows across 88 files. Three rows were rejected; each file's source manifest retains its rejected line, date and reason. The run evaluated nine prespecified model/horizon trials across all three splits: 27 split evaluations and 219 model-window evaluations, corresponding to 73 shared dated windows. Overlapping horizon labels and same-day stocks are not independent experimental replications.

The frozen test split produced the following equal-issue-date normalized-return RMSE values. Returns are fractions, so `0.016043` is approximately 1.60 percentage points of return error. Each model shares the same admissible rows for a given horizon.

| Observed-row horizon | Test forecasts per model | Issue dates | No change | Past momentum | Train-only OHLCV ridge |
|---|---:|---:|---:|---:|---:|
| 1 | 5,394 | 62 | 0.016043 | 0.022446 | 0.016031 |
| 5 | 4,698 | 54 | 0.033919 | 0.050424 | 0.033972 |
| 20 | 2,088 | 24 | 0.055354 | 0.085194 | 0.060525 |

These are descriptive scores from this one fixed historical dataset and protocol. Small score differences have no attached significance claim, and the table does not establish future forecasting value. Ridge is fitted only on training labels; no test score selects its penalty or parameters. Exact unrounded scores, all train/development/test windows, every forecast and their hashes are in local `work/stocknet-results/results.json` and `predictions.csv`.

The bounded price-plus-text study is a separate adapter in `benchmarks/stocknet_aggregation.py`. It freezes AAPL, MSFT and GOOG on the first 20 common development dates whose 1-, 5- and 20-observed-row labels all mature before 2015-10-01. No outcome is used to choose the dates, assets, model or text. It fits no historical labels, so it does not apply the horizon embargo of the fitted price-only protocol. The published StockNet test split remains untouched by this study.

Each issue timestamp is the actual XNYS calendar close. Public tweets are admitted only from the preceding 48 hours through that instant, using their original timezone-aware `created_at` values. The latest four unique texts per asset are retained, each at most 280 characters; timestamps, source file hashes, original full-text hashes, truncation counts and omissions remain explicit. Missing text is unavailable. Full pinned source objects stay in ignored local work. The NEWS envelope is explicitly a public social-text proxy, not a newswire feed. STOCK and that text proxy are available; ETF, MACRO, POLYMARKET and STOCKGRID are unavailable. These envelopes do not claim completed native Lab execution.

Two matched arms receive the same price snapshots and requested cases: price-only and price-plus-text. One model call batches three assets and three horizons per issue date, giving 40 maximum calls and 180 cases per arm. Prompts are frozen byte-for-byte before inference. Model, parameters, study and provider limits are frozen before the first call. Temperature is zero, output is capped, fallback and repair retries are disabled, and all calls share one budget ledger with a total cap of US$0.25. Strict JSON validation requires every case exactly once, finite bounded returns and only supplied tweet IDs. Invalid or interrupted responses remain missing and are never resent by this adapter.

Scores compare both model arms and no-change/momentum on their exact intersection of valid cases, with full requested and valid coverage reported separately. Metrics give equal weight to issue dates. Evidence citations establish that supplied text IDs reached the response; they do not establish causal usefulness. Modern models may remember these 2015 outcomes. This is a limited development input-aggregation study, not prospective evidence, a reproduction of StockNet paper scores, a significance test or a claim of an LLM advantage.

```sh
python -m benchmarks.stocknet_aggregation prepare \
  --dataset work/datasets/stocknet --dataset-repo /path/to/pinned/stocknet-dataset \
  --output work/stocknet-aggregation-v1
python -m benchmarks.stocknet_aggregation run \
  --study work/stocknet-aggregation-v1 --output work/stocknet-aggregation-results \
  --model mistralai/mistral-nemo --max-calls 40 --max-output-tokens 1024 \
  --max-cost-usd 0.25 --budget-dir work/stocknet-aggregation-budget \
  --env-file /path/to/private/runtime.env
```

The environment file is used only to load the credential at runtime; its location and contents are excluded from the study and result projections. Paid execution requires operator authorization. Frozen prompts, separate predictors and truth, native issue packets, response attempts and complete usage/cost receipts remain in ignored local work; a factual result projection can be retained without source text or credentials.

The authorized first paid batch on 11 October 2026 used `mistralai/mistral-nemo` with 1,024 maximum output tokens and one shared budget. The public catalogue estimate reserved at most US$0.020562984 for all 40 planned calls. Actual execution supplied three responses, all accepted by the strict schema. The fourth call returned HTTP 429; its actual cost and usage were unknown, so the provider halted the shared budget and made no further network requests. Failed and unattempted requests remain missing; none was retried or replaced.

The price-only arm has 18/180 valid cases and the text arm 9/180. Their common support is nine cases on **one issue date**, not the planned 20. `comparison_complete` is false. Four text-arm forecasts reference supplied tweet IDs. The three known-cost responses report 20,459 input tokens, 1,540 output tokens and US$0.000414462 total actual cost. All four attempted-call reservations, totaling US$0.002033574, remain retained; that reservation is an upper bound, not a reported bill for the unknown-cost failed attempt.

[The factual result projection](stocknet-multifeed-result.json) retains source pins, frozen prompt/input/evaluator/provider hashes, full coverage, matched scores and per-attempt metering without raw tweet text or private credential locations. The incomplete comparison is a provider-operation observation. Its one-day matched scores are descriptive only and cannot support model selection, graph promotion, statistical significance or an LLM advantage. The original frozen 20-date input cohort remains intact for an explicitly authorized later study with its own complete trial accounting; the failed attempt cannot be silently removed.
