# Public historical inputs for Zenith's feed aggregation

The best next richer input is a narrow **FinMultiTime prices + article text + SEC
facts** slice. It is now imported and timestamp-filtered locally. The original
StockNet text-plus-price task remains a useful smaller matched ablation; a
price-only StockNet baseline does not evaluate text aggregation. Neither slice
supplies every live Zenith feed or establishes prospective model accuracy.

The machine-readable [scout receipt](dataset-scout.json) pins the primary sources,
records software and source-data rights separately, and includes the specific
StockBench negative control. The actual text-free
[FinMultiTime import receipt](finmultitime-import-result.json) contains CRCs,
checksums and verified coverage. Findings are recorded on the existing market
WorkItem; its authority-visible note is `wie_20261011T145617Z_1c7da9f0`.

| Priority | Candidate | Actual complementary inputs | Practical use and boundary |
|---|---|---|---|
| 1 | [FinMultiTime official release](https://huggingface.co/datasets/Wenyan0110/Multimodal-Dataset-Image_Text_Table_TimeSeries-for-Financial-Time-Series-Forecasting/tree/72d4e97b9acb92651949b8efb22c55676ff633ff) | Prices, publisher articles, financial tables; charts are also supplied | Five AAPL archive members supply a real three-channel preparation slice. The release card says MIT; publisher/platform rights remain separate. Raw data stays in ignored local work. |
| 2 | [StockNet original corpus](https://github.com/yumoxu/stocknet-dataset/tree/330708b5ddc359961078bef469f43f48992fd6e4) | Original public tweets and Yahoo price histories | Small, dated text blobs support a matched price-versus-price-plus-text experiment. Repository MIT does not independently settle Twitter/Yahoo redistribution rights. Tweet creation time is observed, acquisition/edit availability is not. |
| 3 | [StockBench](https://github.com/ChenYXxxx/stockbench/tree/ce8b2b3483590646ad3b650ac8221f43f76fd091) | Price, news and fundamental prompt fields | Closest published evaluation design to this combination. Borrow the schema after auditing availability; the specific current-metric path below is unsuitable for historical inputs without repair. Apache-2.0 code and provider data rights are separate. |
| 4 | [FNSPID](https://github.com/Zdong104/FNSPID_Financial_News_Dataset/tree/4054842ec476953b30ee874d4b7e8eea786a21fa) | Real price histories and publisher financial news | Large real corpus, but the official data card and LICENSE retain CC BY-NC 4.0 while the later GitHub README announces broader use. Preserve that conflict; do not silently treat it as a permissive commercial grant. |
| 5 | [Original FinAgent](https://github.com/DVampire/FinAgent/tree/17248a0b8b729ee3e093e30bb7bea7f52181f363) | Provider prices/news/economic series/sentiment/guidance; derived charts | Useful channel interfaces and agent architecture. The inspected processor config is an acquisition range, not proof of a frozen train/test split or vintage macro data. MIT code does not cover all provider inputs. |

These are scoped observations of the pinned paths, not claims that every use of
each project is unsound. No upstream Python, setup script, pickle or model
checkpoint was executed. Shallow sparse clones retain the inspected source in
the private research work area; no wholesale framework is adopted.

## What the sources actually timestamp

The [StockNet paper](https://aclanthology.org/P18-1183/) combines tweets with prices,
uses chronological training/development/test periods, and removes minor movements
using asymmetric direction thresholds. Its published scores include text and
coverage filters. Our unfiltered regression, multiple horizons and matched-input
study are adaptations, not reproductions of those scores. In inspected original
files, preprocessed tweets contain `text`, `user_id_str`, `created_at`; raw prices
contain OHLCV and adjusted close. Exact tweet creation timestamps permit cutoff
tests; adjusted-price vintages and source ingestion times remain unverified.

FinMultiTime's actual AAPL news JSONL has `Date`, `Url`, `Article`; `Date` is a
calendar day without publication time. Its SEC tables retain each fact's
`end`, `val`, `accn`, `fy`, `fp`, `form`, `filed`, and sometimes `start`. A future
outer `filing_date` can wrap many older facts. Conversely, a historically old
period end can have a later restatement. The adapter filters **each fact's filed
day and accession**, keeps its duration/context, and never uses period end or
outer wrapper date as its release timestamp. Unknown intraday availability
becomes the following actual XNYS session open, with the assumption recorded.

FNSPID's inspected `data_processor/price_news_integrate.py` normalizes price and
news times to midnight before a same-day merge. That loses the distinction
between before-close and after-close news. Use original timestamps and a cutoff
join, not that merged daily table, for an intraday information-set claim. The
official large news files are approximately 5.73 GB and 23.23 GB; the price ZIP
is approximately 589.5 MB. They were not downloaded wholesale.

## Specific negative control: historical argument, current facts

At StockBench pin `ce8b2b3483590646ad3b650ac8221f43f76fd091`, the two inspected
`FinnhubClient.get_stock_indicators(symbol, date)` implementations accept `date`
but call current company profile/basic financial methods without passing it.
`stockbench/core/data_hub.py::get_stock_indicators` then caches indicators under
the requested historical date and trusts historical caches. The requested date
and cache filename cannot establish the facts' historical availability.

The scout JSON records this structural negative control from AST inspection,
including source hashes, functions and call arguments. It rejects **these current
metric fields** as historical evidence without a separate availability record.
No upstream function was executed and no entire-framework judgment is implied.

The original [FinMem pipeline](https://github.com/pipiku915/FinMem-LLM-StockTrading/blob/be814aa47970de9bf2fdd6a1d5a60ae5cf361b46/data-pipeline/README.md)
explicitly uses partly private Refinitiv/Reuters data, while its bundled sample
news is fake and does not represent real stock events. It is architecture/pipeline
prior art, not the selected public benchmark. FinGPT is a framework with varied
task datasets; no single verified frozen price/news/fundamentals/macro corpus was
adopted from it in this audit.

## Next compatible input

`benchmarks.finmultitime` imports only the pinned five AAPL leaves. The downloaded
payload was 15,726,208 bytes including central directories, rather than complete
multi-gigabyte archives. All five CRCs, declared sizes and SHA256s passed. The
verified 28 March 2025 issue supplies 20 prior/current price bars, five admitted
articles and 13 eligible financial facts. This is input preparation; no model was
called and no future outcome was scored.

See [the adapter protocol](finmultitime.md). Its issue packet exposes three named
data channels with per-record availability and file provenance. Canonical native
STOCK and NEWS envelopes preserve the table/item formats; fundamentals are an
explicit STOCK section, not an invented native feed node. Missing ETF, MACRO,
POLYMARKET, STOCKGRID and CALCULATOR lanes remain explicit. A full native Lab run
requires its own completeness decision and real additional inputs.
