# Zenith

> **This is not financial advice.** Zenith is an experimental research prototype.
> See the [research notice](RESEARCH_NOTICE.md).

Give a graph of reasoning nodes several feeds from an earlier time. Let it choose
assets and predict. Open the later snapshot, measure what happened, trace the
mistakes and propose one change. Test that change on later inputs.

**Lab → Oracle → Evolve → compare again.** The model weights stay fixed.
We change the instructions, context or connections in the reasoning graph.

[Read the paper](paper/zenith.pdf) · [See the diagrams](docs/graphs.md) ·
[Website backend](docs/website-backend.md) · [Walkthrough](docs/zenith-walkthrough-script.md)

![Earlier inputs through Lab, Oracle, Evolve and a later comparison](docs/graphs/replay.svg)

## The demonstration

This is a **mixed-data** prototype. Saved stock, ETF and prediction-market inputs
remain real. Only the macro and news lanes use explicitly invented examples.
CALC is recomputed from the resulting stock, ETF and macro inputs.
[Per-feed provenance](examples/demo/provenance.json) distinguishes each case.
Real payloads stay local while their publication permissions are reviewed;
withholding a payload does not turn the computation input into synthetic data.

The current graph has 25 nodes in Lab. It loads all six input artifacts and
prepares the first reasoning request. There are **no model calls or completed
forecasts for this configuration yet**. The [preparation receipt](examples/demo/result.json)
records that boundary. Earlier experiments used different inputs and are not
results for this version.

## Run it

Use Python 3.12 from a source checkout:

```sh
python3 -m venv .venv
. .venv/bin/activate
pip install -e '.[test]'
python -m zenith validate
python -m zenith plan lab
```

Prepare mixed inputs from your own authorised saved snapshots:

```sh
python -m zenith prepare-demo --earlier-source /path/to/earlier \
  --later-source /path/to/later --output state/demo/my-pair
```

This command copies the three retained real feeds exactly, constructs the two
labelled replacements and runs the existing calculator. It makes no network or
model calls. [The demo guide](docs/demo.md) shows how to pass these inputs through
Lab and Oracle. Public exports contain provenance and invented examples only.
[Data boundaries](docs/data.md) explain the distinction.

```sh
python -m zenith serve --port 4175
```

The read-only backend serves the graph, node instructions, paper and public
examples. Claude owns the frontend. Private saved-run inspection is an explicit
local option, not part of the public site.

## The research question

Can a recurring mistake identify a useful change to a reasoning node? A diagnosis
suggests an experiment. Only a matched comparison on later cases can show whether
the change helped. The [research direction](docs/research-direction.md) also
proposes a controller that chooses small prompt variations from available context;
that controller has not been trained or evaluated.

| Purpose | Files |
|---|---|
| Node instructions and dependencies | `codex/substrate/nodes/` |
| Execute Lab and Oracle | `zenith/`, `system/core/` |
| Score forecasts and selections | `feedback/` |
| Compare versions and diagnose failures | `research/` |
| Inspect the mixed demonstration | `examples/demo/`, `docs/demo.md` |
| Paper and diagrams | `paper/`, `docs/graphs.md` |

Run `python -m pytest tests` for the offline checks. Keep the prototype small.
