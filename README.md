# Plectis Zenith

**Work in progress.** A research testbed for model-proposed experiments, measured code repair and reusable tests.

Zenith asks whether solving one problem can leave behind a better way to investigate the next. A language model proposes tests or code; the host runs them against reference software, records what happened, and checks whether a repair helped. The intended memory is a program, its measured evidence, and questions that expose its limits.

The current prototype can repair programs and reuse generated testers. **It has not yet shown that its learned investigation methods outperform ordinary reusable code or fixed tests.** Model weights stay fixed; learning here means changing the retained code, tests or state representation. The longer-term ambition is to improve the procedure that produces future improvements. That remains a research question.

**[Explore the research website →](https://wcook04.github.io/plectis-zenith/)**

[Three-page paper (PDF)](paper/zenith.pdf) · [Paper source](paper/zenith.tex) · [Results and limits](docs/status.md) · [Future directions](#what-we-want-to-find-out) · [Try it locally](#try-it-without-an-account)

## What works today

The paper reports separate studies and diagnostics. The continuation learner is an authored algorithm; it does not power the model-generated testers.

| Experiment | Observed result | What the comparison tells us |
|---|---|---|
| [Reusable SQLite testers](docs/studies/client/client-investigation-v2-low-20261015.md) | Generated code found **3 of 4 authored faults**, with no model calls on the later clients. | Ordinary reusable code tied it; fixed tests found **4 of 4**. Both generated testers repeat a constant query and ignore feedback. |
| [Native program repair](docs/studies/native/progress-campaign-20261014.md) | A repair call alone improved later answers from **259/576 to 365/576**. | None of the extra investigation methods beat repair alone. The twelve parent episodes cover only three authored contracts. |
| [Continuation learner repair](examples/continuation-memory/witness-preserving-v1/README.md) | Keeping the history that witnessed a missing distinction lets all **8 native configurations** finish fitting. | Generic questions cost slightly less: **11,379 vs 11,395** source calls. Later UTF-8 and SQLite checks still find errors. |
| [Earlier controlled question memory](docs/history/continuation-memory.md) | Retaining acquired questions reduced additional queries by **11.2–63.1%**, with the same cached answers in both conditions. | Total joint learning still cost **5,427–5,698** source calls versus **3,071** for separate ordinary modules. Blind question transfer later hurt five of six targets. |

The working client run used DeepSeek V4.1 Flash: **46 calls, $0.00712** reported inference cost, including acquisition and compilation. The separate native diagnostic used Ling3.1Flash: **130 calls, $0.12983**. These are recorded run costs, not current price quotes. Qualification and earlier attempts remain in their linked reports.

These are constructed, inspected workloads. They establish working mechanisms and reproducible limits; they do not establish independent transfer, a general learning advantage or recursive self-improvement.

[![The Zenith research website: question, method, findings and frontier](https://raw.githubusercontent.com/wcook04/plectis-zenith/main/docs/images/zenith-research.png)](https://wcook04.github.io/plectis-zenith/)

*The [website](https://wcook04.github.io/plectis-zenith/) is the short reading route. The [paper guide](paper/README.md) links the current PDF, source and reproductions.*

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

## What we want to find out

Can experience help a system discover **what needs to change**, then improve how it makes the next improvement? A wrong answer might come from discarding necessary history, ignoring information already retained, or never asking the question that would reveal the problem. Those need different interventions. Zenith's records contain examples of these distinctions; they do not show that it reliably diagnoses them on its own.

One possible connection is to retain the experiment that exposed a missing distinction, the histories and outcomes that justify it, the revised program, and a way to recognise when a similar investigation might help elsewhere. The separate continuation learner already represents state through answers to selected future questions. Connecting that mechanism to model-generated investigations, and making reuse selective and economical, remains future work.

This is also a possible route toward **recursive self-improvement**: an improved procedure helps produce subsequent improvements. A useful test would let an initial improver produce a successor, compare both on untouched copies of the same starting solvers and fresh problem families, then test whether reinvesting the successor helps produce a better next generation. Keep the evaluator independent of the edits and count acquisition, failed proposals, evaluation, execution and human intervention. Better final answers alone do not show that the improver got better. Any positive result would remain bounded by the tested tasks and budgets.

None of those broad ideas establishes novelty. [Predictive state representations](https://proceedings.neurips.cc/paper/2001/hash/1e4d36177d71bbb3558e43af9577d70e-Abstract.html) describe state through future observations; [weighted automata learning](https://www.cs.ox.ac.uk/people/james.worrell/MA-learning.pdf) supplies established learning machinery; [ILF](https://eth-sri.github.io/publications/he19ilf) learns testing policies for new programs. [STOP](https://arxiv.org/abs/2310.02304) and [Hyperagents](https://arxiv.org/abs/2603.19461) already study improving the improvement machinery. Our candidate contribution is the specific connection between measured distinctions, representation changes and better subsequent investigation. Its originality and value still need to be established against these neighbours and strong simple baselines.

### Why connect this with mathematics?

The [Plectis mathematical corpus](https://github.com/wcook04/plectis-erdos) contains papers, Lean proofs, partial results and open obligations. Its [argument-continuation exporter](https://github.com/wcook04/plectis-erdos/blob/main/scripts/export_argument_continuations.lean) looks for theorems that could supply a required hypothesis and records remaining obligations. That suggests concrete decisions to study: try to prove a prerequisite, seek a different route, or look for a counterexample. [Plectis Atlas](https://github.com/wcook04/plectis-atlas) offers a complementary reading route through OpenAI's mathematics release and attributed outside assessments. The mathematics and those assessments belong to their named authors.

These projects could supply problems, candidate arguments and evidence to inspect. They are **not yet connected to Zenith as a demonstrated learning system**. Finished proofs and paper collections do not supply complete records of alternative attempts or their costs. We would need records of what was known, which action was tried, its measured outcome, its cost and whether it helped the target, with solution material withheld from evaluation tasks.

Lean checks a supplied proof; it does not tell us whether an unproved statement is false or whether a proposed lemma is worth pursuing. A failed search is not a negative truth label. Correct auxiliary results count as progress only when their relevance is established. Cheap software experiments are the practical first test; mathematics is a possible harder transfer domain, not a settled pivot.

### Collaboration and guidance

I'm building Zenith with AI coding agents and learning the research methods as I go. This is an ambitious target, and I have limited experience in this area. The account here is my current understanding, open to correction. I'd welcome collaboration and guidance on the closest prior work, fair evaluations, useful real software tasks, or whether this mathematics connection makes sense. Small reproductions, stronger baselines and reasons a proposed approach will fail are useful contributions too. [Open an issue](https://github.com/wcook04/plectis-zenith/issues) or start with the [contribution guide](CONTRIBUTING.md).

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

## Related Plectis projects

- The [mathematical research corpus](https://github.com/wcook04/plectis-erdos), with papers, Lean proofs and open questions.
- [Plectis Atlas](https://github.com/wcook04/plectis-atlas), an independent reader for OpenAI's mathematics release and attributed external assessments.
- The earlier [Plectis toolkit](https://github.com/wcook04/plectis), with reusable Python components and worked examples.
- [One Checkout](https://github.com/wcook04/one-checkout), a tool for committing one reviewed patch from shared work.

Will Cook uses AI agents to pursue research and build software, then prepares the results with explanations, source and checks so other people can understand, inspect and continue the work. Explore the [research corpus](https://github.com/wcook04/plectis-erdos) and [Plectis website](https://wcook04.github.io/plectis/). Each repository has its own setup and evidence limits.
