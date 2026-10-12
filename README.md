# Plectis Zenith

Zenith learns which parts of a large observation history to investigate before making a forecast. Its first real-data experiment predicts six research baskets from the shared histories of 147 instruments, the baskets themselves and market indices. Every basket can use the whole universe.

A numerical model supplies initial forecasts. Six readers identify patterns and questions; a planner chooses up to six numerical investigations. A final model selects a supported candidate or keeps the baseline for each basket. The backend freezes all predictions before scoring later outcomes. One instruction revision is proposed from development results and tested on later dates.

The experiment compares this graph with a numerical forecaster, fixed investigations and a single controller that sees all first-pass data and has the same query tools. The graph has to earn its extra computation. Historical association is not evidence of physical causality.

- [Current measurements and decision](docs/status.md)
- [Three-page research paper](paper/zenith.pdf)
- [Executable protocol and reproduction](docs/baskets.md)
- [Data source, licence and limitations](docs/data.md)
- [Research programme](program.md)

The price panel is real historical NEPSE data published under a dataset-specific MIT-form licence. The baskets are constructed indices, not traded ETFs. This is a retrospective research prototype; stale marks, unavailable historical release timestamps and possible model pretraining contamination limit what its results can establish.

```sh
python -m pip install -e '.[test,research]'
python -m zenith validate
python -m zenith basket fetch --output work/data/nepse-source
python -m zenith basket ingest --source work/data/nepse-source \
  --output work/data/nepse-panel --through 2025-12-31
python -m zenith basket prepare --data work/data/nepse-panel \
  --study work/basket-study --model inclusionai/ling-3.0-flash
python -m zenith basket run --study work/basket-study --env-file /path/to/local.env
python -m zenith basket report --study work/basket-study
```

The model run has a shared $2 / 260-call cap. Only the `run` step makes inference calls. Credentials and raw run artifacts stay local. Numerical preparation requires NumPy and pandas; the existing engine owns model execution, saved node artifacts, budgets and policies.

The [read-only API](site/README.md) serves the paper, graph definitions and approved evidence. Start it with `python -m zenith serve --port 4175`. Frontend design is outside this change. The older [System A demonstration](docs/demo.md) remains a synthetic protocol fixture, separate from this financial experiment.

```sh
python -m pytest tests
python scripts/build_graphs.py
python scripts/check_extraction.py
tectonic paper/zenith.tex
```
