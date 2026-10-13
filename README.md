# Plectis Zenith

Zenith learns which distinctions a reasoning programme must preserve and investigate. Lab reads a shared financial universe, tests hypotheses and freezes forecasts. Oracle compares them with later outcomes and examines the full Lab graph and saved inputs to locate a possible failure. Evolve writes one instruction change; local replay and later cases test its consequences.

The immediate experiment is the complete error → diagnosis → repair → test loop. A wrong forecast is useful evidence. A plausible diagnosis still needs testing, and an ineffective repair remains a result. This does not establish that the graph outperforms a single adaptive model.

The financial profile uses 25 Lab, 28 Oracle and three Evolve nodes. Every reasoning node emits a typed record of claims, evidence references, distinctions, uncertainty and a stage-specific result. All six baskets can use the histories of all 147 eligible instruments, all baskets and 17 market indices.

- [Current execution evidence](docs/status.md)
- [A forecast failure, its diagnosis and attempted repairs](docs/full-graph-case.md)
- [Three-page research paper](paper/zenith.pdf)
- [Reasoning ontology and full-loop protocol](docs/reasoning-ontology.md)
- [Data source, licence and limitations](docs/data.md)
- [Research programme](program.md)

The price panel is real historical NEPSE data published under a dataset-specific MIT-form licence. The baskets are constructed indices, not traded ETFs. This is a retrospective research prototype; stale marks, unavailable historical release timestamps and possible model pretraining contamination limit what its results can establish.

```sh
python -m pip install -e '.[test,research]'
python -m zenith validate
python -m zenith basket fetch --output work/data/nepse-source
python -m zenith basket ingest --source work/data/nepse-source \
  --output work/data/nepse-panel --through 2025-12-31
python -m zenith plan lab --task-profile financial
python -m research.graph_failure_study prepare --data work/data/nepse-panel \
  --study work/full-graph-study
python -m research.graph_failure_study run --study work/full-graph-study \
  --env-file /path/to/local.env
```

Only `run` makes inference calls, through the explicit provider and frozen batch limits. Credentials and raw run artifacts stay local. Each node gets one attempt. Rejected output is preserved for input-contract diagnosis; valid forecasts are evaluated even when wrong. The native engine owns execution, intermediate artifacts, budgets and policies. The [earlier smaller basket pilot](docs/baskets.md) remains separately labelled.

The [read-only API](site/README.md) serves the paper, graph definitions and approved evidence. Start it with `python -m zenith serve --port 4175`. Frontend design is outside this change. The older [System A demonstration](docs/demo.md) remains a synthetic protocol fixture, separate from this financial experiment.

```sh
python -m pytest tests
python scripts/build_graphs.py
python scripts/check_extraction.py
tectonic paper/zenith.tex
```
