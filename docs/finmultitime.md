# AAPL three-channel historical input adapter

This adapter prepares real historical prices, publisher text and SEC financial
facts from the authors' [FinMultiTime release](https://huggingface.co/datasets/Wenyan0110/Multimodal-Dataset-Image_Text_Table_TimeSeries-for-Financial-Time-Series-Forecasting/tree/72d4e97b9acb92651949b8efb22c55676ff633ff).
It pins revision `72d4e97b9acb92651949b8efb22c55676ff633ff` and protocol
`finmultitime_aapl_three_channel_v1`. The original four-modal forecasting corpus
and [paper](https://arxiv.org/abs/2506.05019) remain distinct from this new
three-channel preparation slice. No original score or split reproduction is claimed.

```sh
.venv/bin/python -m benchmarks.finmultitime import --output work/datasets/finmultitime
.venv/bin/python -m benchmarks.finmultitime snapshot \
  --dataset work/datasets/finmultitime --issue-date 2025-03-28 \
  --output work/finmultitime-aapl-snapshot-v1
.venv/bin/python -m unittest discover -s tests -p test_finmultitime.py -v
```

Archive transport and extraction use the standard library. Actual XNYS sessions
use the project's declared `exchange_calendars` dependency. No upstream code,
pickle, model, browser or API credential is used. The source card declares MIT,
but the adapter grants no public redistribution rights over publisher articles
or platform prices. Original data and derived text-bearing packets stay in
ignored `work/`; the tracked import receipt contains hashes and coverage only.

## Bounded import and identity

Exactly five fixed AAPL members are read from three pinned archives: daily
prices, article JSONL, balance-sheet facts, equity facts and cash-flow facts.
HTTP ranges must return status 206 and the exact `Content-Range`; a full-server
response is rejected before reading its body. The total transport budget is
32 MiB; any read is bounded to 16 MiB. No arbitrary archive extraction occurs.
Duplicate, encrypted, unsupported, oversized or CRC-corrupt selected members
are rejected. Uncompressed total data is bounded to 96 MiB.

The completed import read 15,726,208 bytes including ZIP metadata, and retained
94,721,080 uncompressed bytes. Each member's SHA256 is also anchored in the
adapter's audited fixed-source hash map. The frozen manifest records canonical
source URLs, revision, member names, CRCs, sizes, file hashes, policy and import
implementation hash. Import replay verifies it without re-fetching data.
An incomplete prior import is retained and requires a new empty custody folder.

## Availability and selection

Prices become usable at their actual XNYS session close. The snapshot must have
the **exact issue-session bar** to classify current price as available. Twenty
historical rows can be retained when the issue bar is missing, but the channel
is `partial_stale`, its data-gap receipt names the missing issue bar, and the
native current Price field is null. Dates are not silently backfilled. Source
OHLCV adjustment and historical vintage remain unverified.

Article dates have no time or timezone. The adapter explicitly assumes the US
publisher calendar date and activates the item only at the following XNYS
session open. Weekend and holiday handling uses the exchange calendar. Within
seven calendar days, it selects the latest five unique date/URL/text-hash records
without consulting outcomes, sentiment or popularity. Text is capped at 800
characters; full-text hashes, omission counts, original date and availability
uncertainty are retained. The AAPL file assignment is not a proven relevance
classification. Text is evidence, never executable instructions.

Each whitelisted financial fact must have a valid SEC accession and its own
`filed` date. It activates at the following XNYS session open. Later restatements
cannot replace older eligible filings before their own availability. Period end
must not exceed filing day. The selected period, duration, value, unit, accession,
form, fiscal context, source member and original outer wrapper date remain in
the packet. The wrapper date does not make an older individual fact unavailable;
an old period end does not make a future-filed revision available.

Missing or malformed evidence is counted or marked unavailable, never converted
into a fabricated neutral article, zero financial value or current API response.
These conservative rules do not prove exact publication, acceptance, acquisition,
edit or price-vintage history. Modern language models may have learned these
historical outcomes; no contamination-free evaluation is claimed.

## Frozen outputs and actual coverage

`issue-packet.json` contains three subject-only channels (`prices`, `text`,
`fundamentals`), their selection receipts, source hashes, policy, cutoff and
snapshot identity. It contains no future truth. `feed-envelopes.json` and
`artifacts/global_stock_feed.json` / `artifacts/global_news_feed.json` preserve
native STOCK table and NEWS item shapes. Fundamentals are explicitly located
under STOCK data, not a new native feed node. Metadata identifies FinMultiTime
and its uncertainty; it does not relabel the source as Yahoo or invent native
engine node-success/hash receipts. `runtime_context.json` marks adapter-only
partial input. ETF, MACRO, POLYMARKET, STOCKGRID and CALCULATOR are unavailable.

Existing output replay is allowed only when the computed issue packet is
identical and every frozen artifact passes its recorded checksum. A changed
issue, implementation, source, policy or tampered artifact is rejected; use a
new output directory for a new protocol case.

The [tracked text-free result](finmultitime-import-result.json) records three
coverage cases prepared before any model call or outcome evaluation:

| Issue date | Current price | Article text | Eligible facts |
|---|---|---|---|
| 2025-03-28 | Available; 20 bars including exact issue bar | Five admitted articles | 13 facts |
| 2015-08-03 | Available; 20 bars | Unavailable; source news begins in 2022 | 13 facts |
| 2025-04-21 | Stale; last source bar is 2025-03-28, current Price null | Five admitted articles | 13 facts |

Eleven tests cover holiday activation, pre-close price withholding, same-day
filing/news exclusion, restatement timing, source/manifest drift, ZIP CRC and
size/range bounds, exact issue-bar coverage, canonical partial native envelopes,
frozen output replay and changed-case refusal. This is verified input preparation,
not a completed seven-lane Lab run, model comparison or profitability result.
