# Zenith

> **This is not financial advice.** Zenith is an experimental research prototype.
> See the [research notice](RESEARCH_NOTICE.md).

Zenith studies whether recorded failures in a graph of reasoning steps can guide
useful revisions. Lab produces experimental forecasts from earlier snapshots;
Oracle compares them with later observations; Evolve proposes a change for
another comparison. Start with the fully synthetic offline example below.

**Lab → Oracle → Evolve → compare again.** The model weights stay fixed.
We change the instructions, context or connections in the reasoning graph.

[Read the paper](paper/zenith.pdf) · [See the diagrams](docs/graphs.md) ·
[Website backend](docs/website-backend.md) · [Walkthrough](docs/zenith-walkthrough-script.md)

![Earlier inputs through Lab, Oracle, Evolve and a later comparison](docs/graphs/replay.svg)

## The mixed-data research demonstration

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

### First run: the offline teaching example

Start here. This path is entirely synthetic, needs no inputs or credentials, and
makes no network or model calls:

```sh
python -m zenith demo --output state/demo/offline-example
```

It authors its own feed snapshots, runs the **real native Lab graph** through the
original engine, validation and handoff contracts, shows one deliberately invalid
response being rejected and then corrected, and writes the actual completion
counts and evidence paths to `summary.json`. **This is not financial advice.**
It is a synthetic contract demonstration; it is not evidence of improved
forecasting. It refuses a nonempty output directory and keeps every generated
file under `--output`.

### Later: real inputs and providers (optional)

Prepare mixed inputs from your own authorised saved snapshots:

```sh
python -m zenith prepare-demo --earlier-source /path/to/earlier \
  --later-source /path/to/later --output state/demo/my-pair
```

This command copies the three retained real feeds exactly, constructs the two
labelled replacements and runs the existing calculator. It makes no network or
model calls. [The demo guide](docs/demo.md) shows how to pass these inputs through
Lab and Oracle. Public exports contain provenance and invented examples only.
[Data boundaries](docs/data.md) explain the distinction. Real inputs and provider
execution need explicit configuration and are never part of the offline example.
Explicit provider execution sends the assembled prompt and supplied data to
that provider. Use data you are entitled to send; do not supply personal
financial information.

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

## Repository map

The runtime, research code and authored graph retain their existing paths. Start
with the CLI in `zenith/`; [architecture](docs/architecture.md) traces a snapshot
through its owners.

| Purpose | Files |
|---|---|
| Node instructions and dependencies | `codex/substrate/nodes/` |
| Execute Lab and Oracle | `zenith/`, `system/core/` |
| Score forecasts and selections | `feedback/` |
| Compare versions and diagnose failures | `research/` |
| Inspect the mixed demonstration | `examples/demo/`, `docs/demo.md` |
| Paper and diagrams | `paper/`, `docs/graphs.md` |
| Feed acquisition, refinement and shared execution | `tools/`, `system/` |
| Input adapters and reviewed graph variants | `benchmarks/`, `variants/` |
| Web frontend and its interaction tests | `site/` |
| Offline regression tests | `tests/` |
| Graph projections and source checks | `scripts/` |
| Agent guidance and CI | `AGENTS.md`, `.agents/`, `.github/` |

Run `python -m pytest tests` for the offline checks and `make validate` for graph,
extraction and layout checks. The layout checker reads Git's tracked and visible
new files, including staged changes, while skipping ignored build trees. It
rejects misplaced Python tests, programs in narrative directories and new root
areas without an assigned role. Add a role to the map and checker when an actual
new boundary is needed. Keep the prototype small.
