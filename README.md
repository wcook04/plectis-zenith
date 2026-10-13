# Plectis Zenith

Zenith tests whether an adaptive investigator can improve one reusable procedure by diagnosing and testing its own work. Lab chooses numerical investigations and commits forecasts. A combined Oracle/Evolve reviewer examines the recorded computation and later outcome, then proposes an exact procedure replacement or no change. Code reruns the whole Lab and returns the measured consequence to the next review.

The loop is implemented in the existing engine. **The first real episode completed, but its proposed repair did not improve forecasts.** The reviewer misread numerical evidence and repeated an unsupported diagnosis after unchanged replay. Engineering, valid execution and demonstrated learning are separate claims.

- [Three-page paper](paper/zenith.pdf)
- [Run the native investigator](docs/investigator.md)
- [Measured results](docs/status.md) and [source-bound evidence](docs/investigator-evidence.json)
- [Research programme](program.md)
- [Data, licence and limitations](docs/data.md)

## Run

Install the research dependencies and prepare the historical panel:

    python -m pip install -e '.[test,research]'
    python -m zenith validate
    python -m zenith basket fetch --output work/data/nepse-source
    python -m zenith basket ingest --source work/data/nepse-source \
      --output work/data/nepse-panel --through 2025-12-31

Prepare offline, then explicitly execute a bounded model episode:

    python -m zenith plan lab --task-profile financial_investigator_v1
    python -m research.investigator_study prepare \
      --data work/data/nepse-panel --study work/investigator-development
    python -m research.investigator_study run \
      --study work/investigator-development --env-file /path/to/local.env

The default maximum is $5 and 26 attempted calls. Invalid responses are terminal, with no automatic retry, forecast fallback or adoption. Credentials and raw runtime artifacts stay local. See the [method](docs/investigator.md) for contracts, controls and interpretation.

## Development and retained evidence

    python -m pytest tests
    python scripts/build_graphs.py
    python scripts/check_extraction.py
    tectonic paper/zenith.tex

The [historical full-graph case](docs/full-graph-case.md), [smaller basket pilot](docs/baskets.md) and [synthetic System A fixture](docs/demo.md) remain reproducible. They are not the active investigator specification. The real NEPSE panel and constructed research baskets do not establish trading performance or economic causality.

The [read-only API and site](site/README.md) serve allowlisted definitions, paper and historical public receipts. Private execution is explicit and local. The adaptive profile currently runs through the CLI; its exact artifacts are recorded locally.
