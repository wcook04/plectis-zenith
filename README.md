# Plectis Zenith

Zenith tests whether a model can turn failed investigations into executable knowledge that keeps working. Lab runs a procedure over acquired observations. Oracle compares its answer with measured evidence. Evolve writes a replacement, which must improve a complete development replay without breaking previously correct cases. The frozen procedure then faces new cases and source schemas.

The active task investigates operational time series: did the requested latency or work quantity change, did measurement change, or are essential facts still missing? It retains simultaneous findings and unresolved checks. A language model supplies reusable code; deterministic execution supplies quantities. The financial forecasting experiments remain separately documented historical stress tests.

- [Three-page paper](paper/zenith.pdf)
- [Executable investigations: synthesis and method](docs/executable-investigations.md)
- [Measured results](docs/status.md)
- [Research programme](program.md)
- [Five-return reproduction receipt](docs/breakthrough-returns-20261013.json)

## Run

```sh
python -m pip install -e '.[test,research]'
python -m research.investigation_learning_study prepare --output work/learning-run --model deepseek/deepseek-v4.1-flash --provider-slug deepinfra/fp8
python -m research.investigation_learning_study run --output work/learning-run --env-file /path/to/local.env
```

Preparation freezes data, protocol and executable source without inference. Execution uses a current inexpensive Chinese-developed model on an explicit verified route. Calls are serialized, prices and total spend are bounded, and failed attempts remain recorded. The campaign ceiling is $1.50; the size follows the research question. Credentials and private request records stay local.

## Source map and validation

| Owner | Role |
|---|---|
| [Restricted execution](zenith/investigation_program.py) | Run proposed code with logged table acquisition and resource limits |
| [Operational cases](research/operational_cases.py) | Synthetic cases, independent evaluator and observed-data reference |
| [Learning campaign](research/investigation_learning_study.py) | Proposals, failed-candidate feedback, promotion, frozen transfer and controls |
| [Budgeted provider](zenith/budgeted.py) | Explicit model route, reasoning setting, immutable requests and cost ledger |
| [Model selection](zenith/provider_policy.py) | Current cheap models and host-wide serialization |

```sh
python -m pytest tests
python scripts/build_graphs.py
python scripts/check_extraction.py
python scripts/build_learning_report.py replay
tectonic paper/zenith.tex
```

The [financial investigator](docs/investigator.md), [full financial graph](docs/full-graph-case.md), [basket pilot](docs/baskets.md) and [System A fixture](docs/demo.md) remain runnable with their original evidence boundaries. The [read-only API and site](site/README.md) expose allowlisted documents and receipts; private execution remains explicit and local. [Research notice](RESEARCH_NOTICE.md).
