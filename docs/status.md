# Current prototype

> **This is not financial advice.** This is experimental research. Historical
> examples and model outputs are not investment recommendations and must not be
> used to make financial decisions. See the [research notice](../RESEARCH_NOTICE.md).

The example uses the original saved STOCK, ETF, MACRO, STOCKGRID, POLYMARKET
and NEWS feeds, plus the derived CALCULATOR. The original Lab has 28 nodes
and Oracle has 31, sharing feed nodes within the 55-node substrate.

## What ran

Four full Lab attempts used snapshots from June 26, July 13, July 20 and
July 21, 2026. Each used the same graph, policy, DeepSeek V4.1 Flash through
DeepInfra, full feed data, and a 4,096-token response limit. All completed the
inventory and seven miners. All stopped at truncated cross-correlation JSON.

One instruction limited the size of the cross-correlation report. Tested on
the two later episodes with their original upstream outputs held fixed, it
produced schema-valid output in **2/2 cases**, versus **0/2** for the original
instruction. The responses used 1,308 and 1,172 output tokens. Both exceeded
the requested four-subject limit (nine and eleven); that limit is not part of
the native schema. This is a local execution repair, with partial instruction
compliance. It is not evidence of better predictions.

[The worked experiment](original-feed-windows.md) and its
[public result receipt](original-feed-window-result.json) record the fixed
inputs, candidate, native validation, costs and limits.

## What happened next

A separate conditional native Lab fork reused the eight successful, unchanged
July 20 ancestor outputs and all seven original feed artifacts. It applied
the same frozen change and made three new calls:

**Cross-correlation passed → Orient passed → Decide hit the output limit.**

The saved response ended inside JSON at 4,096 tokens. No completed CP1, CP2
or forecast was produced. The [conditional result](../examples/replay/conditional-result.json)
records the source hashes and exact reuse. This branch is not a fresh
independent execution of the candidate graph.

The four original attempts, two component tests and conditional continuation
used **41 real model calls**, reported **USD 0.4538263632** and reserved
**USD 2.7113265** under the existing research allocation. Failed attempts are
retained. The next execution experiment must declare any further change
separately; these results do not promote a new graph version.

## What the data establishes

The July 20 stock payload has 457 entries; 456 stocks have numeric prices in
both the July 20 and July 21 close snapshots. Collection finished after the
nominal 20:00 UTC label, so the July 20 replay uses 20:01:39 UTC availability.
The original timestamps and payloads remain unchanged.

The historical stock tool computes the last retained Close value but does not
save its provider bar index in each row. Artifact creation time therefore
cannot establish the underlying price-bar time. Comparisons describe changes
between stored prices; they are not certified trading backtests. Publication
vintages are also incomplete, and a current model may know later information.

[Source hashes](../examples/replay/sources.json) and
[three original rows](../examples/replay/observations.json) identify the sample.
Complete private inputs, prompts, outputs and provider receipts remain in the
local replay bundle. Prior studies remain in Git history and the private
Type B archive.
