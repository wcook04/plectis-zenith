# Historical days through the existing Lab, Oracle and Evolve

Zenith should learn from doing the job: see a day's evidence, make a dated
forecast, confront the later observations, diagnose the attempt, and carry a
reviewed improvement into a later day. `program.md` owns this direction.
The current work reconnects that loop to the existing full graph.

For a longer shared panel, use [InvestorBench](investorbench.md): three equities
and 291 complete daily price dates, with date-only summaries delayed by a day.
Pass `--dataset work/datasets/investorbench` to the same controller. This page
also preserves the original FNSPID episode and its sharper article clocks.
Use [generation comparisons](generations.md) to test reviewed changes against
the incumbent rather than treating next-day experimental adoption as success.

The first source is the **original AA slice of FNSPID**, pinned at
[`4054842`](https://github.com/Zdong104/FNSPID_Financial_News_Dataset/tree/4054842ec476953b30ee874d4b7e8eea786a21fa).
It provides a daily Alcoa price series and full market/company article bodies.
Its [original news CSV](https://github.com/Zdong104/FNSPID_Financial_News_Dataset/blob/4054842ec476953b30ee874d4b7e8eea786a21fa/data_processor/news_data_raw/aa.csv)
and [price CSV](https://github.com/Zdong104/FNSPID_Financial_News_Dataset/blob/4054842ec476953b30ee874d4b7e8eea786a21fa/data_processor/stock_price_data_raw/aa.csv)
are only 8.66 MB together. This is a practical starting slice, not the full
research universe. Filename assignment does not establish that every article
is specifically about Alcoa.

## Continue the programme with one native controller

After acquisition, freeze an inclusive range of forecast sessions:

```sh
python -m zenith daily init --work-dir work/daily-demo \
  --start 2024-01-16 --end 2024-01-17 \
  --policy examples/daily/sparse-policy.json
python -m zenith daily next --work-dir work/daily-demo
```

The controller creates snapshots through the session after `--end`, which supplies
truth for the final forecast. It freezes source bytes, graph/contracts/configuration,
implementation and baseline policy. It uses the complete existing missions and
returns native pending packets. Answer these through `zenith import-response`;
`daily next` checks their state and advances Lab → Oracle → Evolve → later Lab.
It never buys inference, starts a chat or invents responses. Use a fresh work directory
when code, source assets or the declared programme changes.

At Evolve, read `episodes/N/review-packet.json`, its fixed instructions and complete
bound originals. Return exactly its response contract: a diagnosis, uncertainty,
a later test, exact JSON evidence references and either a candidate skill change
or `no_change` with `change: null`. Evidence uses a named source and an RFC6901
JSON pointer, with the exact JSON value at that pointer. There is no requirement
to manufacture a lesson every day.

```sh
python -m zenith daily review --work-dir work/daily-demo \
  --response reviewed-answer.json --reviewer DISCLOSED_REVIEWER_IDENTITY
python -m zenith daily next --work-dir work/daily-demo
```

The reviewing agent explicitly accepts this development proposal by importing it.
The importer checks source identity, quotations and native policy validity; it
cannot verify the quality of the diagnosis. One skill addon of at most 512
characters replaces the selected Lab node's addon, preserving its other parameters
and every other node. Retain any earlier rule that is still needed in that text.
The successor is saved under `policies/after-N.json`; the next Lab freezes it in
its native manifest. Rejected responses remain under `episodes/N/attempts/`.
Accepted reviews include reviewer disclosure and identity hashes. No live dossier
or learning-ledger entry is automatically rewritten. Broader policy/topology
experiments remain available through the existing research interfaces.

This historical close-to-close sequence treats outcomes at the next close as
matured before the following forecast. A live implementation needs the actual
data-availability and review delay; it cannot promise execution at that same
closing price. Local source separation is not an operating-system sandbox: an
agent with unrestricted filesystem access must respect the forward packet.

## What a day contains

`benchmarks.fnspid` constructs immutable native feed directories. Each contains
the last 20 observed OHLCV bars, complete eligible article bodies from the last
seven calendar days, source hashes, original clocks and a selection receipt.
The issue anchor is the actual XNYS close; the next day's close belongs to a
separate snapshot. The Jan16,17,18 2024 snapshots contain 1,7,7 articles,
respectively; Jan18 has no fresh article. Repeated context is not new evidence.

All seven native feed artifact names are present. STOCK and NEWS contain the
actual source records. ETF, MACRO, POLYMARKET, CALCULATOR and STOCKGRID explicitly
say unavailable and contain no invented observations. Market news may discuss
macro conditions, but it does not become a structured macro series. The full
28-node Lab is retained, including its 21 reasoning calls. Successful hydration
means the engine read the envelope; it does not make a missing feed available.

Use original publication strings. The upstream
[preprocessor](https://github.com/Zdong104/FNSPID_Financial_News_Dataset/blob/4054842ec476953b30ee874d4b7e8eea786a21fa/data_processor/preprocess.py)
shifts timezone offsets in the wrong direction: Jan16 17:51EST must become
22:51UTC, after that day's close. It must not enter the Jan16 forecast. The
adapter does not execute upstream code. Literal `Text=0` is missing content,
not an article or neutral sentiment. Both full-month and abbreviated-month original clock formats are parsed; invalid or conflicting clocks are excluded and counted. Publisher timestamps still do not prove historical capture or
revision vintages, and historical material can be familiar to a modern model.

Use dataset `Close` consistently; do not mix it with `Adj Close`. Historical
corporate-action vintages are unverified. This initial trial establishes
execution mechanics, not uncontaminated forecasting skill or investment value.
Original article bodies remain in ignored local research custody.

The previously acquired FinMultiTime slice remains on disk. Inspected selected
article bodies did not match their URLs/dates, so those bodies are not admitted
to this replay. That does not invalidate its independently sourced price or
filing-fact tables. Local audit: `work/daily-feed-scout-20261012/daily-source-audit.json`.

## Run the native sequence

From this checkout, with its Python environment:

```sh
python -m benchmarks.fnspid acquire
python -m benchmarks.fnspid snapshot --issue-date 2024-01-16 --output work/replay/feeds/2024-01-16
python -m benchmarks.fnspid snapshot --issue-date 2024-01-17 --output work/replay/feeds/2024-01-17
python -m zenith prepare lab --run-id DAILY_LAB_20240116 \
  --feed-source work/replay/feeds/2024-01-16 \
  --time-anchor 2024-01-16T21:00:00Z --horizon 2024-01-17T21:00:00Z \
  --context-profile compact_feeds
```

`prepare` performs actual engine hydration and emits pending agent packets.
The lead agent or a worker answers them using `zenith import-response`; native
contracts validate responses and advance the graph. A paid `zenith run lab`
uses exactly the same graph and explicit model/provider/immutable budget
options described in [providers.md](providers.md). Never edit artifacts to
manufacture completion. Retain failed trials and unknown cost reservations.

After Lab completes, freeze its forecast and advance the evidence clock:

```sh
python -m zenith prepare oracle --run-id DAILY_ORACLE_20240117 \
  --subject-run state/runs/DAILY_LAB_20240116 \
  --truth-run work/replay/feeds/2024-01-17 \
  --time-anchor 2024-01-16T21:00:00Z --horizon 2024-01-17T21:00:00Z \
  --context-profile compact_feeds
```

Oracle retains the subject T0 anchor and the later T1 horizon; using T1 for both is rejected by the temporal contract. Complete its genuine pending packets through the same importer. Deterministic
reconciliation scores the frozen forecast against the later quote. Oracle
then separates what the forecast missed, what the earlier feeds could have
supported, and what arrived only afterward. An outcome does not by itself
identify its cause. Unsupported explanations must remain hypotheses.

## Evolve can be the lead agent or a worker

Once Oracle's quartet and the subject CP2 are ready:

```sh
python tools/refinement/run_evolve.py \
  --subject-run state/runs/DAILY_LAB_20240116 \
  --truth-run state/runs/DAILY_ORACLE_20240117 \
  --export-agent-packet work/replay/evolve-packet.json
```

The packet contains the existing runner's fixed delta-analysis instructions,
actual paired evidence and hashes binding the prompt, quartet, Lab CP2,
instructions, contract and dossiers. `--verify-agent-packet` checks the binding
before review. This is **pending work**, never a successful learning entry.
Running Evolve without a bridge now exports such a pending packet instead of
writing an AVAILABLE no-analysis placeholder.

The lead agent reads the packet and complete bound sources, identifies one
transferable change with exact evidence, or recommends no change. Review and
version the proposal before the next Lab; retain the previous version. A fixed
worker prompt can perform the same analysis. No separate scheduler or second
forecasting framework is necessary. The legacy export alone has no response importer. The daily controller above
wraps it with a narrower, explicit reviewed skill-policy transition; it does not
pretend to implement the legacy dossier-patch schema or certify semantic quality.

The point is to make this loop useful, then broaden daily coverage and test
whether accumulated changes help on later days. A forecast, critique or
plausible lesson is not evidence of improvement. The execution receipt in
[daily-replay-receipt.json](daily-replay-receipt.json) records what actually ran.
