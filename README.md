# Zenith

**Historical feeds → Lab predicts → Oracle measures → Evolve changes the graph → test on later days.**

Zenith learns a reasoning procedure. Each node takes evidence, applies an
instruction or skill, and passes its output onward. Lab chooses assets and
predicts their outcomes. Oracle compares the frozen predictions with reality.
An agent proposes a change; later matched runs determine whether it helped.
The language model's weights stay fixed.

Read the [three-page paper](paper/zenith.pdf) and the [actual graph diagrams](docs/graphs.md).

## Run

Use a source checkout with Python 3.12:

```sh
python3 -m venv .venv
. .venv/bin/activate
pip install -e '.[test]'
python -m zenith validate
python -m zenith plan lab
```

The existing FNSPID adapter is a small real-data entry into the original graph:

```sh
python -m benchmarks.fnspid acquire
python -m zenith daily init --work-dir work/daily \
  --dataset work/datasets/fnspid-aa --start 2024-01-16 --end 2024-01-17
python -m zenith daily next --work-dir work/daily
```

`daily next` prepares native agent packets. Answer each request, then import it:

```sh
python -m zenith import-response --packet <request.json> \
  --response <answer.json> --model <author>
python -m zenith daily next --work-dir work/daily
```

After Lab and Oracle finish, answer the Evolve packet and run
`daily review --work-dir work/daily --response <review.json> --reviewer <author>`.
The next day consumes that reviewed policy. `daily matchoff` compares the two
versions on later days; `daily retain` records a reviewed winner. Each command
has `--help`. Agent mode makes no provider calls itself.

## What is here

- `codex/`, `system/`, `tools/`: original feed contracts, reasoning nodes and engine.
- `zenith/`: native execution and the daily loop.
- `feedback/`: forecast and selection scoring.
- `research/`: matched later comparison and retention.
- `benchmarks/fnspid.py`: one pinned historical source adapter.
- `tests/`: offline checks for these paths.

The original input was six feeds—stocks, ETFs, macro, Stockgrid, prediction
markets and news—plus a calculator. The current adapter only supplies AA prices
and articles. [Restoring the other information](docs/feed-coverage.md) is the
next task. No tested version has established a forecasting advantage.

The accumulated studies, alternative benchmarks and long survey were removed
from the working repo at the author's request. They remain in Git history and
the private Type B research archive, together with the original notes and data
specimens. [Architecture](docs/architecture.md) · [Status](docs/status.md).
