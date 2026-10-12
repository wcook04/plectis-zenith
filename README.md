# Plectis Zenith

Zenith is built to learn financial reasoning by repeating the same job on historical days:

**Daily feeds → Lab forecast → later observations → Oracle diagnosis → reviewed Evolve change → next day.**

The learning object is the reasoning pipeline: its instructions, incoming context,
node skills and, in broader experiments, its structure. The existing full Lab
and Oracle are the baseline. Evolve can be the lead agent or a worker following
a fixed prompt. It proposes a versioned change; later forecasts determine
whether that change helped. This is procedure learning, not LLM weight training.

To understand the learning step, run the small constructed example below.
It separates interpreting evidence, choosing companies and forecasting, and
shows why a sequence of individually improving edits can miss a useful
combination. This is a deterministic example with a known correct rule, not
LLM training or evidence of a financial advantage.

The real-data loop also runs. The latest [native comparison](docs/judgmental-forecasts.md)
produced ten forecasts under each instruction on identical May 5 inputs.
The revised instruction had worse later loss. A corrected baseline response
exceeded the frozen call allowance, so the [result](docs/judgmental-matchoff-receipt.json)
is descriptive and the formal comparison was not admitted. No policy was
promoted. The [paper](paper/zenith.pdf) distinguishes these financial attempts
from the constructed learning result.

## See what happens after a run

After installing the checkout as below, run:

```sh
python -m research synthetic-learning --output work/learning-example
python -m research synthetic-learning --output work/learning-no-signal --no-signal
```

The example scores the whole eight-company universe, including the six names
the graph did not select. Twelve candidate procedures are tested on earlier
synthetic dates; later dates accept one, and a final period measures it.
Every attempt and intermediate output is saved. In the known-signal world,
the selected combination beats the zero forecast; in the noise-only world,
it chooses zero. A greedy single-edit control gets stuck at zero even when
signal exists. No API key, download or paid call is needed.

[The worked explanation](docs/learning-design.md#a-small-closed-system-we-can-run)
connects this example to the actual Lab/Oracle/Evolve operations and distinguishes
a witnessed mistake, a suspected cause and a tested remedy.

## Run the daily loop

Use a Git source checkout on macOS or Linux with Python 3.11 or newer (Python 3.12 is
used for validation). The engine, 71 authored nodes, contracts, empty dossiers,
CLI, tests and paper are included. No private parent repository is required.
A wheel installation and Windows are not verified distribution formats.
Generation comparisons read the checkout's Git revision for provenance.

```sh
git clone https://github.com/wcook04/plectis-zenith.git
cd plectis-zenith
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[test,study]'
python -m zenith validate
python -m benchmarks.traderharness_daily acquire
python -m zenith daily init --work-dir work/daily-demo \
  --dataset work/datasets/traderharness-daily \
  --start 2023-04-27 --end 2023-04-27 \
  --policy examples/daily/sparse-policy.json
python -m zenith daily next --work-dir work/daily-demo
```

The [TraderHarness daily adapter](docs/traderharness-daily.md) supplies **ten
stocks, daily OHLCV, issuer headlines, announcement titles, historical corporate
actions and CSI300 context** to the same full Lab. Its five pinned tables total
175 MB. Raw CNY prices remain separate from rebased wealth history; financial
facts with unresolved revisions are excluded. Text stops at the close, packet
availability is reconstructed one minute later, and the target is the next
XSHG-session close. Five native feed lanes remain explicitly unavailable.
Source vintages are unverified.

The smaller pinned [InvestorBench panel](docs/investorbench.md) supplies **MSFT, HON and
JNJ prices on all 291 trading days from 12 March 2020 through 6 May 2021**, plus
4,990 news summaries. The adapter delays date-only summaries by one calendar day,
excludes unclocked filing summaries and retains five unavailable feed lanes.
Original publication/capture times and price adjustment vintages are unknown;
this is reconstructed historical development data. Downloads stay in ignored
local storage. The smaller [FNSPID AA replay](docs/daily-replay.md) retains full
timestamped articles for inspecting the original loop.

`daily next` prepares the full native Lab and stops at a real pending reasoning
packet. The agent reads that packet, writes its answer, and imports it:

```sh
python -m zenith import-response --packet PATH_FROM_PENDING_OUTPUT \
  --response answer.json --model DISCLOSED_AGENT_IDENTITY
python -m zenith daily next --work-dir work/daily-demo
```

Repeat for the native Lab and Oracle packets. Once both complete, `daily next`
emits an Evolve review packet containing fixed instructions, source bindings,
current policy and the response contract. The lead agent or reviewing worker
reads the original evidence and returns a candidate or a reasoned no-change:

```sh
python -m zenith daily review --work-dir work/daily-demo \
  --response reviewed-answer.json --reviewer DISCLOSED_REVIEWER_IDENTITY
python -m zenith daily next --work-dir work/daily-demo
```

The importer checks exact evidence quotations and the permitted skill change,
retains rejected attempts and freezes the next policy. It does not certify the
lesson's reasoning. The next day consumes that policy through the original
engine. Repeating the command does not purchase inference or create a chat.
[Agent instructions](AGENTS.md), [operating programme](program.md) and the
[daily guide](docs/daily-replay.md) explain the full workflow.

Lab can issue a cited [abstention](docs/abstention.md) when the available evidence
does not support a forward call. Oracle can leave a cause unresolved and report
no evidenced error; Evolve can make no change. These outcomes preserve honest
experience without counting no-calls as forecast wins.

## Compare and retain a generation

A reviewed change is a candidate. `daily matchoff` freezes that candidate and
its incumbent on identical later snapshots using the existing native cohort.
Both execute the full Lab. `daily retain` requires a complete comparison with
at least twenty issue dates and the improvement margin declared before execution.
If the challenger does not clear that margin, the incumbent is retained.
The next generation consumes a bound retention receipt and must start after
the selection evidence matured. [Commands and experiment design](docs/generations.md)
explain the complete cycle and its resource cost.

This carries the useful generation-and-comparison idea from
[AlphaGo Zero](https://deepmind.google/blog/alphago-zero-starting-from-scratch/)
into this research programme. Market outcomes come from external history;
the system cannot generate new market truth by playing itself. No generation
has yet demonstrated a financial learning advantage.

## What works, and what remains unproved

The latest [two-day development run](docs/empirical-forecasts.md#the-completed-two-day-sequence)
completed **two full Labs, two full Oracles, and a reviewed Evolve change that
was used by the next day's Lab**. After the first price-history rule lost to
unchanged-price persistence, Evolve halved its scale. On the next day the
changed rule beat persistence but lost to the unchanged rule. The candidate was
not promoted. The [source-bound receipt](docs/empirical-pilot-receipt.json)
includes actual predictions, errors, reviews and the successor prompt binding.
This is a price-only numerical control inside the full multi-feed graph;
the contribution of news and the graph's reasoning remains to be demonstrated.

One exposed historical episode completed **28/28 Lab and 31/31 Oracle nodes**
through primary-agent native imports. A separate cheap-model attempt failed and
is retained. The completed forecast had the correct direction, but its causal
reasoning remained inadequate. One following-day policy candidate was prepared;
there is no demonstrated learning gain. The [episode receipt](docs/daily-replay-receipt.json)
records the distinction. Some historical execution files remain local; their
hashes in a receipt do not make them publicly reproducible results.

A separate InvestorBench [contract replay](docs/abstention-receipt.json) completed
28/28 Lab and 31/31 Oracle nodes with an explicit no-call, unresolved cause and
reviewed no-change. It reused 29 earlier answers and is not an independent
forecasting result.

The daily controller connects stage progression and reviewed policy transitions.
Its synthetic tests verify the plumbing; the two-day run exercises an actual
reviewed transition without demonstrating improvement. The next research
objective is useful source-grounded prediction, followed by comparisons of
unchanged and revised pipelines on matched later evidence. Historical model
contamination, revised data and adaptive selection remain material limitations.
An inspected [richer GitHub dataset](docs/herculean-audit.md) had future-year
results in historical news rows; those summaries were not admitted.

The [paper](paper/zenith.pdf) ([source](paper/zenith.tex)) explains this system,
its actual evidence and the sources used. It makes no novelty, profitability or
learned-performance claim.

## Other interfaces and supporting research

- [Architecture](docs/architecture.md) and [learning design](docs/learning-design.md): native graph, temporal boundaries and permitted development changes.
- [Providers](docs/providers.md): explicit own-key model execution and immutable shared spending ledgers. Inspection and agent handoffs need no provider credentials.
- [Experiments](docs/experiments.md): controlled native cohorts, complete trial accounting and separately sealed final assessment.
- [API](docs/backend-api.md) and [frontend handoff](docs/frontend-handoff.md): read-only public graph metadata; no bundled website. Start with `python -m zenith serve`.
- [Status](docs/status.md): current work and dated history. Compact StockNet, A-share calibration and issuer-guidance studies are supporting evidence, not replacement products.
- [Data sources](docs/data-sources.md), [NOTICE](NOTICE) and [LICENSE](LICENSE): source provenance and rights. External datasets and imported material retain their own terms.

For validation, use `python -m pytest tests`. A pinned Python 3.12 environment is
provided in `requirements-test.lock`. GitHub CI also checks extraction hashes,
node skills, public graph metadata and the included historical scoring fixture.
Runtime state, credentials, downloaded articles and private operator material
are excluded from Git.
