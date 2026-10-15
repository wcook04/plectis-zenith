# Plectis Zenith

**Work in progress.** A research testbed for model-proposed experiments, measured code repair and reusable tests.

Zenith asks whether solving one problem can leave behind a better way to investigate the next. A language model proposes tests or code; the host runs them against reference software, records what happened, and checks whether a repair helped. The intended memory is a program, its measured evidence, and questions that expose its limits.

The current prototype can repair programs and reuse generated testers. **It has not yet shown that its learned investigation methods outperform ordinary reusable code or fixed tests.** Model weights stay fixed; learning here means changing the retained code, tests or state representation.

**[Explore the research website →](https://wcook04.github.io/plectis-zenith/)**

[Current paper](paper/zenith.tex) · [Results and limits](docs/status.md) · [Try it locally](#try-it-without-an-account) · [Architecture](docs/architecture.md)

## What works today

The paper reports three separate experiments. The continuation learner is an authored algorithm; it does not power the model-generated testers.

| Experiment | Observed result | What the comparison tells us |
|---|---|---|
| [Reusable SQLite testers](docs/studies/client/client-investigation-v2-low-20261015.md) | Generated code found **3 of 4 authored faults**, with no model calls on the later clients. | Ordinary reusable code tied it; fixed tests found **4 of 4**. Both generated testers repeat a constant query and ignore feedback. |
| [Native program repair](docs/studies/native/progress-campaign-20261014.md) | A repair call alone improved later answers from **259/576 to 365/576**. | None of the extra investigation methods beat repair alone. The twelve parent episodes cover only three authored contracts. |
| [Continuation learner repair](examples/continuation-memory/witness-preserving-v1/README.md) | Keeping the history that witnessed a missing distinction lets all **8 native configurations** finish fitting. | Generic questions cost slightly less: **11,379 vs 11,395** source calls. Later UTF-8 and SQLite checks still find errors. |

The working client run used DeepSeek V4.1 Flash: **46 calls, $0.00712** reported inference cost, including acquisition and compilation. The separate native diagnostic used Ling3.1Flash: **130 calls, $0.12983**. These are recorded run costs, not current price quotes. Qualification and earlier attempts remain in their linked reports.

These are constructed, inspected workloads. They establish working mechanisms and reproducible limits; they do not establish independent transfer, a general learning advantage or recursive self-improvement.

[![The Zenith research website: question, method, findings and frontier](https://raw.githubusercontent.com/wcook04/plectis-zenith/main/docs/images/zenith-research.png)](https://wcook04.github.io/plectis-zenith/)

*The [website](https://wcook04.github.io/plectis-zenith/) is the short reading route. The [paper guide](paper/README.md) distinguishes the current source from the previous PDF edition.*

Agents can read the site without JavaScript or an account: [llms.txt](https://wcook04.github.io/plectis-zenith/llms.txt) gives the starting points, the [research and graph map](https://wcook04.github.io/plectis-zenith/agent-map.md) explains the records, and the [machine route index](https://wcook04.github.io/plectis-zenith/agent-index.json) lists their URLs. Graph records name program steps and inputs; source checksums identify versions, not scientific validity.

<a id="what-is-being-tested"></a>

## How it works

1. **Propose a question.** The model sees the task, candidate program, examples and measurements available to its condition.
2. **Measure the answer.** The host executes the candidate and reference software separately. Their disagreement supplies evidence; a model's explanation does not certify the cause.
3. **Repair and check.** A replacement must preserve every previously correct measured case. Selection freezes before later evaluation.
4. **Test reuse separately.** The client study compiles a tester from earlier investigations, freezes it, and compares it with ordinary code, fresh investigation and fixed tests on later clients.

Lab, Oracle and Evolve name the execution, review and revision roles. A graph can organize their dependencies; the current studies use ordinary programs and tests. The [programme](program.md) explains the graph ambition, the separate learner and their still-unbuilt connections.

## What remains open

The next useful result would be a procedure that learns to choose **new, informative tests** on changed software, finds more faults or uses less work than competent ordinary testing, and repays its acquisition cost. That needs independently sourced clients with genuine room to improve, a frozen selection rule, and comparisons that include failed attempts and all stages of work. Reusing a successful probe is a starting point, not that result.

## Try it without an account

Use Python 3.11 or newer from a source checkout on Linux, macOS or a suitable WSL environment. The runtime uses POSIX facilities. The examples below make no model calls.

```sh
git clone https://github.com/wcook04/plectis-zenith.git
cd plectis-zenith
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[test,research]'
```

**Replay the published client result:**

```sh
python scripts/build_client_investigation_report.py replay-behavior examples/conformance/client-reuse-v2-low
```

A successful run reports `behavioral_match`: the archived prompts, replies, queries, outcomes, work counters and costs agree. It reports the archived and local SQLite versions; changed behavior still fails. The [strict replay](docs/studies/client/client-investigation-v2-low-20261015.md#evidence-and-replay) also requires the original runtime identity. Replay checks recorded work; it does not ask a model to solve the tasks again.

**Run the separate learner example:**

```sh
python scripts/demo_continuation_learning.py
```

Expect ten source calls, five rational-linear coordinates and correct outputs for queue lengths 0–32. This small example uses only the Python standard library. A single nonlinear counter solves it more simply. Add `--native` to reproduce the eight-configuration diagnostic and its residual errors.

For the website, install Node.js 22.12 or newer, then run:

```sh
npm ci --prefix site
npm run build --prefix site
python -m zenith serve --port 4175 --frontend-dir site/dist
```

Open [localhost:4175](http://localhost:4175). The public-mode server exposes published evidence, with no model-execution endpoint or private saved runs. [Frontend guide](site/README.md).

## Source map

| Area | Start here |
|---|---|
| Current experiments | [Native repair](research/conformance_study.py), [client test reuse](research/client_investigation_study.py), [continuation learner](research/continuation_learning.py) |
| Shared execution | [Restricted Python](zenith/investigation_program.py), [provider budgets](zenith/budgeted.py), [model policy](zenith/provider_policy.py), [source snapshots](zenith/source_snapshot.py) |
| Evidence and replay | [Published bundles](examples/conformance), [learner example](examples/continuation-memory/witness-preserving-v1), [report/replay commands](scripts) |
| Reading surfaces | [Paper](paper/README.md), [current status](docs/status.md), [website source](site/README.md) |
| Retained graph and earlier studies | [Historical architecture and source owners](docs/history/architecture.md) |

The [architecture guide](docs/architecture.md) maps dependencies, command owners and evidence boundaries. Runtime and study entry points remain stable; it also documents the retired unused tools and the documentation migration.

## Development

```sh
make validate       # source layout, custody and retained graph contracts
make test-current   # current experiments and shared execution regressions
make test           # complete suite, including historical studies
```

`make demo` and `make replay` run the two offline examples above. See [CONTRIBUTING.md](CONTRIBUTING.md) for frontend checks and how to publish a new experiment. Useful contributions include stronger ordinary baselines, independently sourced client tasks, clearer failure reproductions and cheaper experiments with the same controls.

New inference runs require an explicit command, your own credentials and a declared budget. Model selection favors recent, capable, inexpensive Chinese-developed models with verified endpoint prices; there is no automatic expensive fallback. [Run protocol](docs/studies/native/conformance-study.md#reproduce-or-run) · [Security and execution limits](SECURITY.md).

## Credits and license

Created by Will Cook with AI coding agents. Zenith adapts the `ai_workflow` research system and attributed research-return components; [NOTICE](NOTICE) records their provenance. [Apache 2.0](LICENSE) covers the software. Dataset and provider-response rights are separate. The website's [reuse notes](site/README.md#what-came-from-the-original-zenith-ui) credit its components and fonts.
