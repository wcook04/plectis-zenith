# A shared daily panel for the original Zenith loop

The selected panel is the MSFT, HON and JNJ JSON data from
[InvestorBench](https://github.com/felis33/INVESTOR-BENCH/tree/87e0f7bc83baf7d89fbdc1a51f92458f8d4ee11a),
the financial-agent benchmark described by
[Li et al. (ACL 2025)](https://aclanthology.org/2025.acl-long.126/).
Zenith reuses the source data through its own native feed adapter. It does not
run the upstream trading agent or claim to reproduce its reported performance.

The pinned files have prices for all **291 XNYS sessions from 12 March 2020
through 6 May 2021**, with no missing shared sessions. Their 4,990 news summaries
provide a longer development stream than the small FNSPID AA article slice.
The machine-readable [admission receipt](investorbench-admission.json) binds
source hashes, coverage, exclusions and limitations.

| Symbol | Daily prices | News summaries | Dates with no news | Excluded filings |
|---|---:|---:|---:|---:|
| MSFT | 291 | 3,636 | 10 | 5 |
| HON | 291 | 444 | 79 | 5 |
| JNJ | 291 | 910 | 26 | 5 |

All three have news on 196 common dates. These are upstream summaries, not
independently verified full articles. Counts do not measure information quality
or independent events, and a symbol bucket does not prove issuer relevance.

## Acquire and use

```sh
python -m benchmarks.investorbench acquire
python -m benchmarks.investorbench audit
python -m zenith daily init --work-dir work/daily-demo \
  --dataset work/datasets/investorbench \
  --start 2020-07-01 --end 2020-07-31 \
  --policy examples/daily/sparse-policy.json
python -m zenith daily next --work-dir work/daily-demo
```

Only three pinned JSON files are downloaded, about 4.52 MB. Their exact hashes
are checked before reading. No upstream Python or pickle is executed. A snapshot
preserves twenty prior observed scalar prices and the preceding seven calendar
days of summaries, excluding the current date's summaries. STOCK and NEWS feed
the existing graph; ETF, MACRO, POLYMARKET, CALCULATOR and STOCKGRID explicitly
remain unavailable. The full Lab and Oracle are retained.

Each source record contains `prices`, `news`, `10k` and `10q`. The price is a
scalar, so the adapter does not invent OHLCV. News has a date bucket but no
original URL, publication time or capture clock. The adapter assumes availability
at midnight in New York on the next calendar day and records that assumption.
That delay reduces same-day timing ambiguity; it cannot prove historical
point-in-time validity or remove model familiarity with these events.

All filing summaries are excluded because their date keys do not establish
release or acceptance times. Price adjustment vintages and historical summary
revisions remain unknown. The source is therefore appropriate for reconstructing
and debugging the learning loop, with these limits carried into experiments.
It is not a clean prospective investment backtest.

The source repository is MIT licensed, copyright 2024 Haohang Li, Yupeng Cao
and Yangyang Yu. That code license does not independently establish rights to
republish every publisher-derived dataset item. Zenith distributes pins and
the adapter; downloaded text and its derived snapshots stay in ignored local
storage. See [NOTICE](../NOTICE).
