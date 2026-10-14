# Plectis Zenith

Zenith tests whether investigations can accumulate useful executable knowledge. A model proposes experiments against a source, the host records what happens, and the model writes a program that predicts further observations. Retained knowledge consists of the program, its source binding, measured evidence and counterexamples. Unsupported quantities remain unresolved.

The working object is a program with its source binding, observations, tests and optional executable dependencies. Small experiments compare repair, fresh candidate search and learned composition. Historical graphs remain available; the [programme](program.md#relation-to-the-graph-ambition) separates useful program learning from graph superiority and improvement of the learning algorithm itself.

The latest campaign implements **structural revision and source-rule induction**. A model can change ordinary code, its interfaces and retained state using measured examples and execution feedback. Explicit local graph context is tested against unrestricted ordinary code and function contracts. [Method](docs/decomposition-study.md), [full results](docs/decomposition-20261014.md).

The complete pass made **122 calls for $0.178**. On six fresh synthetic source settings, DeepSeek V4.1 Flash with low reasoning and a plain coding prompt scored **144/144** on each of two later panels; contracts with low reasoning scored **120/144**, and contracts without reasoning **52/144**. All six winning first proposals already worked, so repeated revision earns no benefit here. The operation family is supplied and each query includes its whole history: this is acquired predictive computation, not compact-state discovery or recursive self-improvement.

An earlier native SQLite comparison and its follow-ons remain available with their original source settings, panels and budgets. They favor preserving evidence and executable alternatives. A new four-task structural test repairs information loss and rollback-sensitive state, but ordinary contracts outperform the explicit local-context condition. [Results, controls and limits](docs/status.md), [research programme](program.md).

- [Three-page paper](paper/zenith.pdf)
- [Method and experiment](docs/executable-investigations.md)
- [Measured results](docs/status.md)
- [Structural revision and rule-induction method](docs/decomposition-study.md)
- [Research programme](program.md)
- [Fifteen deep returns: learned decomposition and research direction](docs/deep-returns-20261014.md)
- [Eight next-round returns: synthesis, decisions and reproduction](docs/next-returns-20261014.md)
- [Ten frontier returns: synthesis and reproduction](docs/frontier-returns-20261013.md)

## Run

```sh
python -m pip install -e '.[test,research]'
python -m research.decomposition_study prepare work/rule-run \
  --dataset bindings --seed 20261015 --model deepseek/deepseek-v4.1-flash \
  --providers deepinfra/fp8 baidu/fp8 morph/fp8 --arms global \
  --reasoning-effort low --max-output-tokens 12288 --max-cost-usd 0.60
python -m research.decomposition_study run work/rule-run --env-file /path/to/local.env
python -m research.decomposition_study confirm work/rule-run
```

This reproduces the six-source design with new model outputs, not the original experiment. The recorded twelve-call version cost **$0.0274**; the $0.60 ceiling is only a maximum. For exact offline reproduction, use `python scripts/build_decomposition_report.py replay examples/decomposition/binding-deepseek-low-global-v1`. Original source archives preserve older execution rules.

Preparation freezes source, data, protocol and both later panels. Select recent capable inexpensive Chinese-developed models from current metadata and actual delivery; this campaign favored DeepSeek with low reasoning. Independent trials use at most three concurrent calls across the host and one per pinned endpoint. Each trajectory stays ordered. There are no automatic retries or expensive fallbacks; credentials and transport records remain local. [Historical native-source campaign commands](docs/executable-investigations.md) remain available.

## Source map and validation

| Owner | Role |
|---|---|
| [Restricted execution](zenith/investigation_program.py) | Run proposed code with logged table acquisition and resource limits |
| [Native source world](research/observation_world.py) | SQLite observations and a separate evaluator |
| [Structural revision](research/decomposition_study.py) | Matched whole-program, local-context and ordinary-contract repairs with frozen later cases |
| [Mechanism tasks](research/decomposition_tasks.py) | Information-losing interfaces, native SQLite allocation and a correct-code control |
| [Rule induction](research/state_discovery_tasks.py) | Synthetic source rules, identifying observations and longer unseen sequences |
| [Structural evidence replay](scripts/build_decomposition_report.py) | Exact returned code, billing and portable archived-source replay |
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
python scripts/build_decomposition_report.py replay examples/decomposition/binding-deepseek-low-global-v1
tectonic paper/zenith.tex
```

The [financial investigator](docs/investigator.md), [full financial graph](docs/full-graph-case.md), [basket pilot](docs/baskets.md) and [System A fixture](docs/demo.md) remain runnable with their original evidence boundaries. The [read-only API and site](site/README.md) expose allowlisted documents and receipts; private execution remains explicit and local. [Research notice](RESEARCH_NOTICE.md).
