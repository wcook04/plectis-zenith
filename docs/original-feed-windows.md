# An original-feed window experiment

> **This is not financial advice.** This is experimental research. Historical
> examples and model outputs are not investment recommendations and must not be
> used to make financial decisions. See the [research notice](../RESEARCH_NOTICE.md).

The intended loop is simple: run the same graph on several earlier snapshots,
trace repeated failures to a specific operation, change one thing, then compare
the original and changed versions on later snapshots. This page records a small
retrospective example of that loop. It is not a clean forecasting experiment.

**Result, 12 October 2026:** all four original-graph attempts stopped at the
first cross-feed synthesis with truncated JSON. One frozen instruction change
passed the native contract on both later inputs: **0/2 → 2/2**. Neither candidate
fully obeyed the requested subject-count limit. No forecast improvement is
established. The [machine-readable receipt](original-feed-window-result.json)
contains source, graph, prompt and response hashes alongside the measurements.

| Episode | Original node | Original output tokens | Changed node | Changed output tokens |
|---|---|---:|---|---:|
| D1 | Truncated; rejected | 4,096 | Not tested | — |
| D2 | Truncated; rejected | 4,096 | Not tested | — |
| L1 | Truncated; rejected | 4,096 | Valid native contract | 1,308 |
| L2 | Truncated; rejected | 4,096 | Valid native contract | 1,172 |

Each baseline completed the inventory and all seven first-pass miners before
failing at the same synthesis node. The 36 baseline calls and two candidate
calls reported **$0.4404** in total. This includes the July 20 baseline run that
predated the study. A subsequent full-graph continuation is accounted separately.

That [separate conditional continuation](../examples/replay/conditional-result.json)
reused the eight unchanged reasoning outputs and seven original feeds. With the
same frozen candidate, cross-feed synthesis and Orient succeeded; Decide then
truncated at 4,096 tokens. Its three new calls cost $0.0134. The repair advanced
execution to the next bottleneck, but still produced no CP1, CP2 or forecast.
This continuation does not add another paired later-window observation.

## What stayed fixed

The inputs are the original saved STOCK, ETF, MACRO, NEWS, POLYMARKET and
STOCKGRID feeds, plus their derived CALCULATOR feed. `compact_feeds` keeps every
data field and removes only acquisition/debug metadata from the prompt view.
The source files themselves remain unchanged and are identified by hashes.

The native Lab has 28 nodes, including seven feed nodes. All baseline attempts
use the same node and implementation hashes, supplemental policy, model
(`deepseek/deepseek-v4.1-flash`), provider (`deepinfra/fp8`) and 4,096-token
response limit. Selecting a Lab target still includes its mission siblings;
these are full native graph attempts, not a replacement graph.

The study assigned two earlier episodes to development and two later episodes
to comparison before the new runs. Issue times use the latest feed acquisition
timestamp, rather than pretending every feed arrived at its nominal snapshot
time. This conservative anchor does not certify the timing of every underlying
price bar or news item.

| Episode | Role | Original input | Issue time, UTC | Declared forecast endpoint, UTC |
|---|---|---|---|---|
| D1 | Development | June 26 first hourly capture | June 26, 14:31:59 | June 26, 15:30 |
| D2 | Development | July 13 close | July 13, 20:08:18 | July 14, 13:30 |
| L1 | Later comparison | July 20 close | July 20, 20:01:39 | July 21, 20:00 |
| L2 | Later comparison | July 21 open capture | July 21, 15:02:47 | July 21, 20:00 |

The later windows overlap. They are different input episodes, not independent
market replications. Sliding analysis windows of one, two and three episodes
produce nine views of these four episodes; they do not create nine experiments
or change the declared forecast horizons.

## What counts as a diagnosis

For a forecast miss, the [failure matrix](failure-diagnosis.md) asks whether the
relevant evidence existed, reached the responsible node, survived grouping and
selection, and supported the consequence drawn. Later research may explain an
event, but it cannot make that evidence available to the earlier graph.

An execution failure needs a separate label. A truncated JSON response is not
automatically an evidence failure or a bad financial inference just because it
occurred at a grouping node. Here, the evidence for `output_capacity` is the
provider's `finish_reason=length`, the exhausted output allowance, the saved
incomplete response and the native validator's rejection. The generic final
error also mentions the provider's prohibition on a second paid attempt; the
first attempt receipt establishes what happened before that retry was blocked.

## The bounded intervention

The test changes only the supplemental instruction at `lab_cross_corr_v1`.
It does not change source data, graph edges, model, output allowance or schema.
The later component comparison keeps the seven upstream miner outputs exactly
as they were in each baseline attempt. Candidate responses pass through the
native prompt assembler, provider accounting and schema validator.

The added instruction is:

> Output budget: keep all four required arrays; use at most 3 strongest records
> per array, at most 4 subjects per record, short IDs/names, and summaries of at
> most 24 words. Preserve required fields and uncertainty. Return complete JSON
> within the response limit.

Both later candidates returned three records in each of the four arrays. Their
longest summaries were 17 and 15 words. Their largest subject lists contained
9 and 11 entries, exceeding the requested limit of four. The existing schema
does not enforce that limit. We retain this partial adherence as a separate
result and do not revise the instruction after seeing it.

A successful component response establishes that this local repair can produce
valid output on the supplied inputs. It does not establish complete Lab
execution, useful downstream reasoning, improved forecasts or a better trading
policy. Those are separate measurements. The candidate remains a proposal
until an appropriate later comparison supports promotion.

## Reproduce or audit

Private original feeds, complete prompts, provider responses and budget ledgers
are retained locally under `work/original-feed-windows-20261012/` and the native
`state/runs/` directories. The source bundle is not shipped in this public repo.
An installation without those originals can inspect the code and public result
receipt, but cannot honestly reproduce the market-data experiment from unit
test fixtures.

```sh
python -m research.original_feed_windows --plan /path/to/evaluation-plan.json
```

The optional explicit paid component replay also requires `--candidate`,
`--subject-run`, `--run-id` and `--env-file`. It uses the plan's immutable shared
budget. It refuses to overwrite an attempt, verifies the original graph and
sources, permits only one node instruction change and records that it is a
component replay rather than a completed Lab run.

The original plan and any corrections are retained. In particular, the plan's
initial description of a prefix target was corrected after checking native
scope expansion: the actual manifests include the full 28-node Lab.

## Limits of the example

This is deliberately modest evidence. There are very few saved dates, different
horizon lengths, overlapping later windows and only one model sample per arm.
The analyst had already seen the July 20 execution failure and some later price
rows before the new study was frozen. Thus chronological separation does not
make these cases a blind holdout. The provider's model may also have historical
knowledge beyond the prompt boundary.

The original feeds have uncertain price-bar clocks, bare time-of-day news
fields and missing values. No contemporaneous forecasting performance, causal
effect size or universal improvement can be inferred here. Reducing output
size may discard useful associations even when it fixes serialization. Keep
that tradeoff visible when evaluating the eventual full graph.
