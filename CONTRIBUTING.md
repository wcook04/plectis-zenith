# Contributing

Start with the [README](README.md), [programme](program.md), [architecture](docs/architecture.md) and [agent instructions](AGENTS.md). Contributions should help test a research claim, improve a reproduction or make the implementation easier to understand. A useful first contribution is a small failure reproduction, a stronger ordinary baseline or a correction tied to its source.

<a id="set-up-and-check"></a>

## Start with an offline check

Use Python 3.11 or newer on Linux, macOS or a suitable WSL environment. Run these commands from the repository root, which contains `pyproject.toml`. The graph runtime and restricted workers use POSIX facilities.

```sh
python3 -m venv .venv
. .venv/bin/activate
python scripts/demo_continuation_learning.py
```

The small learner example uses only the Python standard library. Check its output against the [README's first-run explanation](README.md#try-it-without-an-account); `make demo` runs the same command. No account or package installation is needed for this example.

## Install and check the source checkout

An editable install keeps imports tied to the checkout and preserves access to its task definitions, papers, scripts and evidence. A wheel installation alone does not include those repository resources.

```sh
python -m pip install -e '.[test,research]'
make replay
```

`make replay` runs the published client comparison from its frozen source and saved model replies, with network access disabled in the replay process. Success is labelled `behavioral_match`: queries, native results, work counters and costs agree with the record. Both replay modes exclude timestamps, elapsed times and selected failure metadata; behavioural mode also excludes SQLite version identity. The [client report](docs/studies/client/client-investigation-v2-low-20261015.md#evidence-and-replay) gives the stricter `replay` command, which retains SQLite identity, and its original environment. Neither command makes new inference calls.

The following checks require the complete source checkout:

```sh
make test-current
make validate
```

`make test-current` checks the current studies and shared execution. Run `make test` after runtime changes to include historical experiments; their archived replay tests take substantially longer. Override the interpreter with `make PYTHON=/path/to/python …` when needed.

CI uses Python 3.12 and [requirements-test.lock](requirements-test.lock). To use those exact dependency versions, replace the editable-install command above with:

```sh
python -m pip install -r requirements-test.lock
python -m pip install -e .
```

The lock requires Python 3.12 or newer. Python 3.11 users should use the editable-install resolver above; record the versions actually installed when reporting a reproduction.

For frontend changes in a complete checkout, use Node.js 22.12 or newer and follow the [frontend guide](site/README.md):

```sh
npm ci --prefix site
npm test --prefix site
npm run build --prefix site
```

Inspect the rendered page on desktop and mobile. Reuse the site's existing components, assets and typography. Keep the website, README and paper's current claims consistent, and label historical material by its actual scope.

## Change source without changing evidence

Preserve public module paths and command interfaces used by archived studies. Put new source beside its actual owner in the [source map](docs/architecture.md#repository-roles); do not create another framework for an existing responsibility.

Published attempts, responses and frozen runtime archives are immutable evidence. After reviewing maintained-source changes, name their repository-relative paths explicitly, for example `python scripts/check_extraction.py --refresh research/continuation_learning.py tests/test_continuation_learning.py`, then inspect the manifest diff. Refresh preserves source attribution, refuses `examples/` paths and aborts without writing if any unselected recorded file has changed or disappeared. New maintained members must be named explicitly; the command does not discover or remove files. Retirements require a separate reviewed manifest change preserving the old row and replacement, as described in the [cleanup rules](docs/architecture.md#retiring-a-source-path). Do not refresh archived programs to make a replay pass. Run `make validate`, stage only intended paths, then run `make validate-index` to check the staged layout and entry-document links.

## Add an experiment

Start with a question and a competent ordinary baseline. Freeze source, tasks, evaluator, selection rule and model route before later evaluation. Keep failed attempts, acquisition cost, invalid outputs and duplicate queries in the record. Use the existing provider budgets and restricted executor; a new paid campaign needs an explicit budget and run command.

Separate the native, client and learner populations. A repair, successful compilation, reused answer, learned representation and independently transferable procedure are different claims. Preserve fixed-test, ordinary-code and repair-only controls; do not select a winner after inspecting later outcomes.

Publish through the study's allowlisted exporter and replay the resulting bundle from a fresh checkout. Cite external methods and data. Keep credentials, private snapshots and transport records out of Git; [SECURITY.md](SECURITY.md) explains the execution boundary.
