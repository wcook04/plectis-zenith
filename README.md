# Plectis Zenith

Zenith learns how to reason about markets by repeating the same job on historical days:

**Daily feeds → Lab forecast → later observations → Oracle diagnosis → reviewed Evolve change → next day.**

The learning object is the reasoning pipeline: its instructions, incoming context,
node skills and, in broader experiments, its structure. The existing full Lab
and Oracle are the baseline. Evolve can be the lead agent or a worker following
a fixed prompt. It proposes a versioned change; later forecasts determine
whether that change helped. This is procedure learning, not LLM weight training.

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
python -m pip install -e '.[test]'
python -m zenith validate
python -m benchmarks.investorbench acquire
python -m zenith daily init --work-dir work/daily-demo \
  --dataset work/datasets/investorbench \
  --start 2020-07-01 --end 2020-07-31 \
  --policy examples/daily/sparse-policy.json
python -m zenith daily next --work-dir work/daily-demo
```

The pinned [InvestorBench panel](docs/investorbench.md) supplies **MSFT, HON and
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

One exposed historical episode completed **28/28 Lab and 31/31 Oracle nodes**
through primary-agent native imports. A separate cheap-model attempt failed and
is retained. The completed forecast had the correct direction, but its causal
reasoning remained inadequate. One following-day policy candidate was prepared;
there is no demonstrated learning gain. The [episode receipt](docs/daily-replay-receipt.json)
records the distinction. Some historical execution files remain local; their
hashes in a receipt do not make them publicly reproducible results.

The daily controller connects stage progression and reviewed policy transitions.
Its synthetic tests verify the plumbing, not forecasting ability. The next
research objective is repeated competent execution, followed by comparisons of
unchanged and revised pipelines on matched later evidence. Historical model
contamination, revised data and adaptive selection remain material limitations.

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
