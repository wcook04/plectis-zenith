# Contributing

Start with the [README](README.md), [programme](program.md), [architecture](docs/architecture.md) and [agent instructions](AGENTS.md). Zenith is unfinished. Contributions should help test a research claim, improve a reproduction or make the implementation easier to understand.

## Set up and check

Work from a source checkout on Linux, macOS or a suitable WSL environment with Python 3.11 or newer. The graph runtime and restricted workers use POSIX facilities. An editable install preserves access to repository task definitions, papers and evidence:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[test,research]'
make demo
make replay
make test-current
make validate
```

`make demo` runs the small learner example; `make replay` checks the published client run without new inference. The demonstration itself uses only the Python standard library. `make test-current` checks the current studies and shared execution. Run `make test` after runtime changes to include the historical experiments; their archived replay tests take substantially longer. Override the interpreter with `make PYTHON=/path/to/python …` when needed.

CI uses Python 3.12 and [requirements-test.lock](requirements-test.lock). That exact lock requires Python 3.12 or newer; Python 3.11 users should use the editable-install resolver above.

For frontend changes, use Node.js 22.12 or newer and follow the [frontend guide](site/README.md):

```sh
npm ci --prefix site
npm test --prefix site
npm run build --prefix site
```

Inspect the rendered page on desktop and mobile. Reuse the site's existing components, assets and typography. Keep the website, README and paper's current claims consistent, and label historical material by its actual scope.

## Change source without changing evidence

Preserve public module paths and command interfaces used by archived studies. Put new source beside its actual owner in the [source map](docs/architecture.md#repository-roles); do not create another framework for an existing responsibility.

Published attempts, responses and frozen runtime archives are immutable evidence. After editing maintained source, run `python scripts/check_extraction.py --refresh` and inspect the resulting current-source hash changes. Do not refresh archived programs to make a replay pass. Run `make validate`, stage only intended paths, then run `make validate-index` to check the staged layout and entry-document links.

## Add an experiment

Start with a question and a competent ordinary baseline. Freeze source, tasks, evaluator, selection rule and model route before later evaluation. Keep failed attempts, acquisition cost, invalid outputs and duplicate queries in the record. Use the existing provider budgets and restricted executor; a new paid campaign needs an explicit budget and run command.

Separate the native, client and learner populations. A repair, successful compilation, reused answer, learned representation and independently transferable procedure are different claims. Preserve fixed-test, ordinary-code and repair-only controls; do not select a winner after inspecting later outcomes.

Publish through the study's allowlisted exporter and replay the resulting bundle from a fresh checkout. Cite external methods and data. Keep credentials, private snapshots and transport records out of Git; [SECURITY.md](SECURITY.md) explains the execution boundary.
