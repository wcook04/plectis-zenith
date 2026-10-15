# Plectis Zenith

**Public research draft.** The experiments and offline examples run; a general advantage from learned investigation remains an open question.

[Read the research website →](https://wcook04.github.io/plectis-zenith/)

[Results](docs/status.md) · [Paper source](paper/zenith.tex) · [Run locally](#try-it-without-an-account) · [Credits](#credits-and-license)

[![Zenith’s research website](https://raw.githubusercontent.com/wcook04/plectis-zenith/main/docs/images/zenith-research.png)](https://wcook04.github.io/plectis-zenith/)

**Agents can navigate the website too.** Start with [llms.txt](https://wcook04.github.io/plectis-zenith/llms.txt), follow the [research and graph map](https://wcook04.github.io/plectis-zenith/agent-map.md), or fetch the [machine route index](https://wcook04.github.io/plectis-zenith/agent-index.json). These static routes expose the same documents, measured evidence and dependency graphs, with stable node IDs and source hashes; they need no JavaScript or account. Graph definitions retain their historical scope and do not establish measured success.

```sh
curl -fsSL https://wcook04.github.io/plectis-zenith/llms.txt
curl -fsSL https://wcook04.github.io/plectis-zenith/agent-index.json
```

**Learn a program together with the questions that expose its limits.** Zenith lets a model propose experiments, measures their answers against native software, and uses the evidence to repair ordinary code. A later test checks whether the repair helped. The longer-term question is whether experience can make the next investigation cheaper or more effective.

The working implementation is deliberately small: programs, queries, measured receipts and a selection rule. A graph can organize these dependencies, but extra nodes and persuasive explanations are not success measures. Fixed tests and a repair call without new investigation are first-class competitors.

## What works today

A DeepSeek V4.1 Flash run acquired executable testers from batch-import investigations, then applied them to account-transfer clients. The retained tester found **3 of 4 authored faults with no target-stage model calls**. Ordinary reusable code matched it; a fixed tester found **4 of 4**. The acquired code repeated the same probe when it failed to find a discrepancy, so this is working test reuse, not an adaptive investigation advantage.

The complete low-reasoning run used **46 model calls for $0.007117764**. Two earlier engineering versions remain published: one produced stop-only testers; the next produced one invalid program and another stop. All three client runs together used 133 calls for $0.019295552. The clients belong to one already inspected SQLite family, and the later interface was supplied before compilation. [Results, full costs and replay](docs/client-investigation-v2-low-20261015.md).

A separate native repair comparison improves **259/576 → 365/576** later answers with a repair call alone. Extra investigation does not beat that control: fixed tests score 364, compiled investigation 354, and feedback-aware direct queries 343. The full comparison used **130 calls for $0.12982944**. Its twelve parent episodes cover three authored contracts, not independent applications. [Complete paired results and costs](docs/progress-campaign-20261014.md).

## Try it without an account

Use Python 3.11 or newer. From a fresh checkout:

```sh
git clone https://github.com/wcook04/plectis-zenith.git
cd plectis-zenith
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[test,research]'
python scripts/demo_continuation_learning.py
python scripts/demo_continuation_learning.py --native
```

The first command runs a small learning example in ten source calls. A bounded queue eventually stops growing. The learner must preserve both the history that exposed this and the future question that distinguishes it; retaining only the question had caused the earlier learner to fail. The repaired version fits five rational-linear coordinates and passes lengths 0–32. A simple nonlinear counter solves this particular task more compactly.

The native demonstration fits all eight inspected configurations, but finite later checks still find errors in UTF-8 and SQLite. Its 11,395 acquisition calls also exceed the generic singleton-question control's 11,379. **This is a reproducible learner repair, not a demonstrated memory advantage.** [Exact results, source hashes and replay](examples/continuation-memory/witness-preserving-v1/README.md).

Replay the published client result without an API key:

```sh
python scripts/build_client_investigation_report.py replay-behavior examples/conformance/client-reuse-v2-low
```

This checks the preserved prompts, replies, queries, outcomes and costs. It permits a different SQLite version only when behavior and work counters still match, and reports both environments. The [exact replay](docs/client-investigation-v2-low-20261015.md#evidence-and-replay) additionally checks the original SQLite identity.

To run the read-only website locally, install Node.js 22.12 or newer:

```sh
npm ci --prefix site
npm run build --prefix site
python -m zenith serve --port 4175 --frontend-dir site/dist
```

Open [localhost:4175](http://localhost:4175). Public mode serves published evidence and excludes private saved runs. The [frontend guide](site/README.md) covers development. The separately labelled [synthetic graph example](docs/demo.md#synthetic-offline-first-run) teaches the earlier Lab/Oracle contracts without model calls.

## What is being tested

The model comparison asks whether measured investigation adds anything beyond another repair call. It starts every arm from the same program and keeps invalid programs and unhelpful investigations in the result:

| Method | Additional evidence before repair |
|---|---|
| Repair only | Public contract and examples |
| Fixed tests | Up to eight predeclared native queries |
| Compiled investigator | A model-written Python selector with up to eight query slots |
| Direct batch | One model response proposing up to eight queries |
| Direct adaptive | Up to two query batches; the second sees measured outcomes |
| Outcome-masked control | Same first model response, with outcomes hidden from the second |

The host executes the source and parent separately. Repairs can change the complete program; selection must preserve every previously correct measured case. All selections freeze before later evaluation. That finite rule cannot guarantee correctness on unseen inputs. The [v5 protocol](docs/progress-protocol-v5-20261014.md), [original comparison](docs/progress-protocol-20261014.md) and [method](docs/conformance-study.md) specify what each comparison can establish.

A separate [client investigation pilot](docs/client-investigation-protocol-v2-20261015.md) moves from atomic batch imports to account transfers. A model investigates earlier clients, writes a reusable tester, then deploys it unchanged against later clients. We compare it with ordinary reusable code, fresh investigation with the same history, cold investigation, and fixed tests. Both retained testers know the later interface before compilation. This tests working reuse within an authored SQLite family; it does not establish transfer to an independent project.

- [Current results and limits](docs/status.md)
- [Current three-page paper source](paper/zenith.tex) · [previous PDF edition](paper/zenith.pdf)
- [Research programme and relation to the graph](program.md)
- [Nineteen PROGRESS returns: synthesis, custody and reproduction](docs/progress-returns-20261014.md)
- [Live research website](https://wcook04.github.io/plectis-zenith/) · [Frontend development](site/README.md)

## Source map

| Owner | Role |
|---|---|
| [Conformance study](research/conformance_study.py) | Paired investigations, measured repair and frozen later evaluation |
| [Direct investigation](research/direct_investigation.py) | Query delivery, native measurements and feedback masking |
| [Native tasks](research/native_conformance_tasks.py) | SQLite, LRU and UTF-8 contracts and query panels |
| [Client investigation study](research/client_investigation_study.py) | Acquire, freeze and compare reusable testers against later client workflows |
| [Client tasks](research/client_investigation_tasks.py) | Native SQLite failure, continuation and caller-transaction obligations |
| [Continuation learner](research/continuation_learning.py) | Exact arithmetic, witness-preserving refinement and finite challenges |
| [Offline learner demonstration](scripts/demo_continuation_learning.py) | Small reproducible failure and eight native configurations |
| [Campaign analysis](scripts/analyze_progress_campaign.py) | Parent-paired outcomes, repeated programs and cost accounting |
| [Conformance publication](scripts/build_conformance_report.py) | Allowlisted evidence and replay from each archived runtime |
| [Client publication](scripts/build_client_investigation_report.py) | Preserved model replies, native replay and lifecycle cost accounting |
| [Funding continuation](scripts/continue_conformance_budget.py) | Explicit reservation-cap amendment that reuses settled responses without retrying them |
| [Website snapshot](scripts/export_site_snapshot.py) | Publish the existing read-only interface from allowlisted API data |
| [Restricted execution](zenith/investigation_program.py) | Explicit Python syntax, process, time and memory limits |
| [Source custody](zenith/source_snapshot.py) | Archived runtime identity |
| [Budgeted provider](zenith/budgeted.py) and [model policy](zenith/provider_policy.py) | Pinned inexpensive routes, budgets and bounded concurrency |
| [Architecture](docs/architecture.md) | Current source ownership and retained historical profiles |

For a new paid experiment, use the [explicit run commands](docs/conformance-study.md#reproduce-or-run), verify current model prices and set a hard ceiling. Model selection favors recent, capable, inexpensive Chinese-developed models. There is no automatic retry or expensive fallback. A ceiling is not an expected invoice; exact replay requires no API calls.

```sh
python -m pytest tests
python -m zenith validate
python scripts/check_structure.py
python scripts/check_extraction.py
```

For an agent-assisted review, use the [website's agent map](https://wcook04.github.io/plectis-zenith/agent-map.md), or clone this repository and ask the agent to read `AGENTS.md`, this README, `program.md` and the selected experiment's protocol. The website explains the research; machine receipts and archived source support exact checks. [Contributing](CONTRIBUTING.md) · [Research boundary](RESEARCH_NOTICE.md).

The [static site exporter](scripts/export_site_snapshot.py) owns the generated `llms.txt`, `agent-map.md`, `agent-index.json` and direct JSON files in `site/dist/`; [the frontend guide](site/README.md#static-publication) documents the build. The map reuses the public API from [zenith/web_content.py](zenith/web_content.py), with [publication regressions](tests/test_site_snapshot.py) and [layout validation](scripts/check_structure.py). Generated navigation adds no browser script, fetch or preload to human reading.

Earlier [memory studies](docs/continuation-memory.md), [native observation studies](docs/executable-investigations.md), [structural studies](docs/decomposition-20261014.md), [financial investigator](docs/investigator.md), [full graph](docs/full-graph-case.md), [basket pilot](docs/baskets.md) and [System A fixture](docs/demo.md) retain their original artifacts. Their results are not pooled with the current comparison.

## Credits and license

Created by Will Cook with AI coding agents. Zenith adapts the `ai_workflow` research system and the explicitly attributed research-return components in [NOTICE](NOTICE). The [extraction manifest](docs/extraction-manifest.json) records source custody and maintained adaptations. Software is licensed under [Apache 2.0](LICENSE).

The website uses React, React Flow and React Markdown; its graph viewer and inspectors adapt the earlier research UI. [Reuse details](site/README.md#what-came-from-the-original-zenith-ui) and the [SIL Open Font Licenses](site/public/fonts/) are retained. Software licensing does not grant rights to separately acquired datasets or provider responses.
