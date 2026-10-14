# Plectis Zenith

Zenith tests whether investigations can accumulate useful executable knowledge. A model proposes experiments against a source, the host records what happens, and the model writes a program that predicts further observations. Retained knowledge consists of the program, its source binding, measured evidence and counterexamples. Unsupported quantities remain unresolved.

The working object is a program with its source binding, observations, tests and optional executable dependencies. Small experiments compare repair, fresh candidate search and learned composition. Historical graphs remain available; the [programme](program.md#relation-to-the-graph-ambition) separates useful program learning from graph superiority and improvement of the learning algorithm itself.

The next research target is **learning the decomposition**: can a node use its caller, consumers and failures to discover a missing distinction, change an interface or design a better experiment? The fifteen latest returns motivate this direction; a reflective graph has not yet been implemented or validated. [Synthesis and proposed comparison](docs/deep-returns-20261014.md).

The active experiment uses real SQLite executions in controlled source configurations. Duplicate writes, insertion triggers, rollbacks and separate connections make the reported counter differ from committed state. The model receives action descriptions and measured examples, then authors its own computation. A fresh compiler and an execution-enabled archive receive the same evidence and total coding allowance.

The initial comparison made **126 calls for $0.1295**, but its final incremental code tied an unchanged early program. Small follow-on screens found a better direction: preserve evidence and executable alternatives, then test what to reuse. A mixed DeepSeek/Qwen pool scored **279/288** on separate confirmation sequences, versus **191/288** and **194/288** for four-proposal single-model pools. A later test with the larger historical archive reached **286/288** after two native observations per source, with **zero new model calls**. The panels and search budgets differ; these are useful bounded results, not recursive self-improvement. [Results, controls and limits](docs/status.md).

- [Three-page paper](paper/zenith.pdf)
- [Method and experiment](docs/executable-investigations.md)
- [Measured results](docs/status.md)
- [Research programme](program.md)
- [Fifteen deep returns: learned decomposition and research direction](docs/deep-returns-20261014.md)
- [Eight next-round returns: synthesis, decisions and reproduction](docs/next-returns-20261014.md)
- [Ten frontier returns: synthesis and reproduction](docs/frontier-returns-20261013.md)

## Run

```sh
python -m pip install -e '.[test,research]'
python -m research.observation_learning_study prepare work/observation-run --model deepseek/deepseek-v4.1-flash --provider deepinfra/fp8 --providers deepinfra/fp8 baidu/fp8 morph/fp8 --workers 3 --reasoning-effort none
python -m research.observation_learning_study run work/observation-run --env-file /path/to/local.env
python -m research.observation_learning_study replay work/observation-run
```

Preparation freezes the source, dataset and protocol before inference. The default design permits 126 calls across six configured sources. Its $2 ceiling is a hard maximum, not an expected invoice: receipts record actual token usage and charges separately from conservative reservations. Use current model and endpoint metadata, then an execution check, to select a recent capable inexpensive Chinese-developed model. Independent worlds run with a host-wide limit of three calls and one per pinned endpoint. Each learning trajectory stays ordered. A first-round engineering checkpoint stops unusable runs before further calls; there is no automatic retry or expensive fallback. Credentials and private transport records remain local.

## Source map and validation

| Owner | Role |
|---|---|
| [Restricted execution](zenith/investigation_program.py) | Run proposed code with logged table acquisition and resource limits |
| [Native source world](research/observation_world.py) | SQLite observations and a separate evaluator |
| [Observation learning](research/observation_learning_study.py) | Model-proposed probes, retained programs, equal-budget controls and frozen audit |
| [Counterexample repair screen](research/observation_repair_screen.py) | Matched repairs of selected failures, structural screening and separate confirmation |
| [Candidate-pool screen](research/observation_candidate_pool_screen.py) | Development-selected mixed and single-model pools with four proposals per source |
| [Probe and selection screen](research/observation_active_selection_screen.py) | Frozen candidates, two native probes and development-based selection, with the full historical archive as a reference |
| [Composition screen](research/observation_composition_screen.py) | Learned transition/readout components, a competent flat library and dependency ablation |
| [Evidence publication and replay](scripts/build_observation_report.py) | Publish reviewed records and reproduce them with their archived runtime |
| [Operational cases](research/operational_cases.py) | Synthetic cases, independent evaluator and observed-data reference |
| [Learning campaign](research/investigation_learning_study.py) | Proposals, failed-candidate feedback, promotion, frozen transfer and controls |
| [Budgeted provider](zenith/budgeted.py) | Explicit model route, reasoning setting, immutable requests and cost ledger |
| [Model selection](zenith/provider_policy.py) | Current cheap models and bounded host-wide admission |

```sh
python -m pytest tests
python scripts/build_graphs.py
python scripts/check_extraction.py
python scripts/build_learning_report.py replay
python scripts/build_observation_report.py replay
tectonic paper/zenith.tex
```

The [financial investigator](docs/investigator.md), [full financial graph](docs/full-graph-case.md), [basket pilot](docs/baskets.md) and [System A fixture](docs/demo.md) remain runnable with their original evidence boundaries. The [read-only API and site](site/README.md) expose allowlisted documents and receipts; private execution remains explicit and local. [Research notice](RESEARCH_NOTICE.md).
