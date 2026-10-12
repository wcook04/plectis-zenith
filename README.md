# Zenith

> **This is not financial advice.** Zenith is an experimental research
> prototype. Historical examples and model outputs are not investment
> recommendations and must not be used to make financial decisions.
> [Read the research notice](RESEARCH_NOTICE.md).

Give a graph of reasoning nodes the saved market feeds at an earlier time.
Let it choose assets and predict. Open the later snapshot, measure what happened,
trace the mistakes and propose one change. Test that change on later inputs.

**Lab → Oracle → Evolve → compare again.** The model weights stay fixed.
We change the instructions, context or connections in the reasoning graph.

[Read the four-page paper](paper/zenith.pdf) · [See the diagrams](docs/graphs.md) ·
[Website backend](docs/website-backend.md) ·
[Spoken walkthrough script](docs/zenith-walkthrough-script.md) ·
[The research direction](docs/research-direction.md)

![Saved feeds through Lab, Oracle, Evolve and a later comparison](docs/graphs/replay.svg)

## The example

We found the original **20 and 21 July 2026** feed snapshots on disk. Each has
stocks, ETFs, macro, Stockgrid, prediction markets and news, plus a derived
calculator. The earlier stock table has 457 entries; 456 have prices in both
snapshots. These are the actual saved payloads.

[Three original price rows](examples/replay/observations.json) show what the
before/after data looks like. They are illustrations; the Lab receives the full
payloads. [Source hashes](examples/replay/sources.json) identify all fourteen
original artifacts. Full private inputs and provider records stay in the local
replay bundle.

Four real LLM attempts stopped at the same cross-correlation output limit.
One instruction change produced valid output on both later inputs. A conditional
continuation then reached Decide, which hit the same limit. No final forecast
yet. [The measured example](docs/original-feed-windows.md) and
[current result](docs/status.md) keep the successful local repair and the next
failure visible. This retrospective prototype establishes no financial advantage.

## The theoretical aim

A point-in-time packet can contain histories, not just one state. Future work
would use authorised proprietary snapshots to test forecasts of later states
or paths, with verified information cutoffs. A proposed shared neural
controller would use available regime signals to choose small semantic
variations in each reasoning node's prompt. Every node keeps the same job,
inputs and output contract. Numerical settings select exact text; they are
not direct gradients through the language model. This is a proposal, not a
trained capability or evidence of robustness to every regime. The
[research direction](docs/research-direction.md) explains the mechanism and
links the inspected neural-network and prompt-optimisation code.

## Run the original graph

Use a source checkout with Python 3.12:

```sh
python3 -m venv .venv
. .venv/bin/activate
pip install -e '.[test]'
python -m zenith validate
python -m zenith plan lab
```

A feed directory contains `artifacts/global_*_feed.json` and its original
`runtime_context.json`. Prepare a Lab from the earlier directory:

```sh
python -m zenith run lab --run-id example-lab \
  --feed-source /path/to/earlier-snapshot \
  --time-anchor 2026-07-20T20:01:39+00:00 \
  --horizon 2026-07-21T20:00:00+00:00 --context-profile compact_feeds
```

The default agent mode writes prompts. Import answers with
`python -m zenith import-response --packet <request.json> --response <answer.json> --model <author>`.
For explicit API execution, `run --help` lists the model, provider and shared
budget options. Credentials and paid calls are never implicit.

Once Lab completes, run Oracle against it and the later directory:

```sh
python -m zenith run oracle --run-id example-oracle \
  --subject-run example-lab --truth-run /path/to/later-snapshot \
  --context-profile compact_feeds
```

[The daily controller](docs/architecture.md) connects completed Lab/Oracle
pairs to reviewed Evolve changes and later comparisons.
[Failure diagnosis](docs/failure-diagnosis.md) explains how to trace repeated
errors without treating an explanation as proof.

## Where to look

| Purpose | Files |
|---|---|
| Original nodes and their instructions | `codex/substrate/nodes/` |
| Execute Lab and Oracle | `zenith/`, `system/core/` |
| Read feeds and apply reviewed changes | `tools/` |
| Score predictions and selections | `feedback/` |
| Compare versions and diagnose repeated failures | `research/` |
| Inspect this example | `examples/replay/`, `docs/status.md` |
| Read the argument and see the graphs | `paper/`, `docs/graphs.md` |

Run `python -m pytest tests` for the offline checks. Keep the prototype small.
