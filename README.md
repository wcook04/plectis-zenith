# Plectis Zenith

**Public research draft.** The examples run, but we have not yet shown that an AI can learn a way to test software that outperforms ordinary reusable tests.

[Read the research website →](https://wcook04.github.io/plectis-zenith/)

[Results](docs/status.md) · [Paper source](paper/zenith.tex) · [Run locally](#try-it-without-an-account) · [Credits](#credits-and-license)

[![Zenith’s research website](https://raw.githubusercontent.com/wcook04/plectis-zenith/main/docs/images/zenith-research.png)](https://wcook04.github.io/plectis-zenith/)

**Agents can navigate the website too.** [llms.txt](https://wcook04.github.io/plectis-zenith/llms.txt) lists where to start. The [research and graph map](https://wcook04.github.io/plectis-zenith/agent-map.md) links to documents, saved results and diagrams. The [machine route index](https://wcook04.github.io/plectis-zenith/agent-index.json) gives software a URL for each record, so it can read the site without JavaScript or an account. Graph records name each program step and its inputs. File checksums identify the source version; they do not prove a result correct.

```sh
curl -fsSL https://wcook04.github.io/plectis-zenith/llms.txt
curl -fsSL https://wcook04.github.io/plectis-zenith/agent-index.json
```

**Can an AI learn better ways to find faults in software?** Zenith asks a language model to propose a test. It runs the proposed inputs through a program being repaired and through reference software, then sends any disagreement back to the model. After the model changes the code, Zenith tries additional inputs to see whether the change helped. The longer-term question is whether experience with one program helps the model test another program more effectively or cheaply.

Zenith saves the code, test inputs, actual answers and errors from each attempt. A diagram can show which step reads another step’s output, but a larger diagram or a persuasive explanation is not evidence of better results. The experiments compare AI-chosen tests with tests chosen in advance and with simply asking the model to repair the code without running new tests.

## What works today

A DeepSeek V4.1 Flash experiment used examples from database import programs to write a tester for programs that transfer money between accounts. The saved tester found **3 of 4 deliberately written faults, without further requests to the AI while testing those later programs**. Ordinary reusable code matched it; tests chosen in advance found **4 of 4**. The generated tester repeated the same input when it did not find a fault. It could be reused, but did not learn to choose better follow-up tests.

That experiment used **46 requests to the AI for $0.007117764**, with the provider’s reasoning-effort setting set to low. Two earlier versions remain published: one wrote testers that stopped without trying anything; the next wrote one invalid program and another tester that stopped. The three versions together used 133 requests for $0.019295552. All the tested programs use SQLite, a database library already examined during development. The model knew how to call the later programs before it wrote the testers. [Results, full costs and instructions to repeat the tests](docs/client-investigation-v2-low-20261015.md).

A separate experiment asks the model to repair programs that imitate database, cache and text-decoding operations. Asking for a repair without new tests improves **259/576 → 365/576** correct answers on later inputs. New investigation does not beat that result: tests chosen in advance score 364, an AI-written program that chooses tests scores 354, and AI-chosen tests with responses supplied between attempts score 343. The comparison used **130 requests for $0.12982944**. Its twelve starting examples cover three tasks written for this study, not twelve independent applications. [Complete comparisons and costs](docs/progress-campaign-20261014.md).

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

The first demonstration runs reference software ten times to learn how a queue behaves when it reaches its size limit. We repaired the learner to remember both the earlier actions that exposed a prediction error and the later question that revealed it. The repaired version learns a model whose memory is represented by five numbers, using exact fractions and agrees with the queue on the tested sequences of lengths 0–32. A simple counter solves this particular task more compactly; the learned model is not the best known solution.

The second demonstration builds a model for each of eight software settings. Testing additional inputs still finds incorrect predictions for UTF-8 text decoding and SQLite. The learner ran the reference software 11,395 times to collect answers; a comparison using generic one-action questions needed 11,379. **The repair can be reproduced, but has not shown a cost advantage over that simpler comparison.** [Exact results, file checksums and instructions to repeat the tests](examples/continuation-memory/witness-preserving-v1/README.md).

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

Open [localhost:4175](http://localhost:4175). The default mode shows published results and hides private saved executions. The [frontend guide](site/README.md) explains how to work on the website. The separate [diagram example with invented data](docs/demo.md#synthetic-offline-first-run) demonstrates the earlier Lab and Oracle program steps without calling an AI.

## What is being tested

The repair comparison asks whether running new tests helps more than simply asking the AI for another repair. Each method starts with the same program. Invalid proposed programs and tests that did not help remain in the results:

| Method | Additional evidence before repair |
|---|---|
| Repair only | The task description and examples |
| Tests chosen in advance | Up to eight previously chosen inputs run on the reference software |
| AI-written test chooser | A Python program written by the model can attempt up to eight tests |
| Tests proposed together | One AI response proposes up to eight tests |
| Tests proposed in stages | Up to two groups of tests; the AI sees the first group’s answers before choosing the second |
| Same first tests, answers hidden | The first AI response is the same, but the second request does not include the answers |

Zenith runs the reference software and the program being repaired separately. A repair may change the whole program, but it must retain every previously correct answer on the examples already tried. Zenith saves the chosen version before testing additional inputs. Passing the tested examples cannot guarantee correctness on every possible input. The [v5 experiment procedure](docs/progress-protocol-v5-20261014.md), [original comparison](docs/progress-protocol-20261014.md) and [method](docs/conformance-study.md) give the exact rules.

A separate [tester-reuse experiment](docs/client-investigation-protocol-v2-20261015.md) moves from database imports to account transfers. After examining the earlier programs, the model writes a tester that must stay unchanged when it examines the later programs. We compare it with ordinary reusable code, a fresh AI investigation with or without the earlier results, and tests chosen in advance. The model knows how to call the later programs before it writes either reusable tester. All the programs were written for this study using SQLite, so the result does not establish success on an independent project.

- [Current results and limits](docs/status.md)
- [Current three-page paper source](paper/zenith.tex) · [previous PDF edition](paper/zenith.pdf)
- [Research programme and relation to the graph](program.md)
- [Nineteen PROGRESS returns: synthesis, custody and reproduction](docs/progress-returns-20261014.md)
- [Live research website](https://wcook04.github.io/plectis-zenith/) · [Frontend development](site/README.md)

## Source map

| Owner | Role |
|---|---|
| [Conformance study](research/conformance_study.py) | Compare testing methods, repair programs, save them unchanged and try later inputs |
| [Direct investigation](research/direct_investigation.py) | Send test inputs to software and control which answers the AI sees |
| [Native tasks](research/native_conformance_tasks.py) | Define database, cache and text operations, expected answers and test inputs |
| [Client investigation study](research/client_investigation_study.py) | Learn reusable testers, save them unchanged and compare them on later database programs |
| [Client tasks](research/client_investigation_tasks.py) | Define expected behavior when database operations succeed, fail or continue after a failure |
| [Continuation learner](research/continuation_learning.py) | Learn predictions while retaining action sequences that exposed earlier errors |
| [Offline learner demonstration](scripts/demo_continuation_learning.py) | Reproduce a small prediction error and test eight settings of the reference software |
| [Campaign analysis](scripts/analyze_progress_campaign.py) | Compare methods on the same starting programs, identify repeated programs and total costs |
| [Conformance publication](scripts/build_conformance_report.py) | Publish approved result files and rerun programs from their archived source |
| [Client publication](scripts/build_client_investigation_report.py) | Publish saved AI replies, rerun their programs and total the costs of learning and use |
| [Funding continuation](scripts/continue_conformance_budget.py) | Raise an explicitly authorized spending limit while reusing completed replies |
| [Website snapshot](scripts/export_site_snapshot.py) | Export public data and documents as static files for people and agents |
| [Restricted execution](zenith/investigation_program.py) | Explicit Python syntax, process, time and memory limits |
| [Source custody](zenith/source_snapshot.py) | Record which source files produced an experiment |
| [Budgeted provider](zenith/budgeted.py) and [model policy](zenith/provider_policy.py) | Select allowed AI services, cap spending and limit simultaneous requests |
| [Architecture](docs/architecture.md) | Locate the source for each component and earlier program version |

For a new paid experiment, use the [explicit run commands](docs/conformance-study.md#reproduce-or-run), verify current model prices and set a hard ceiling. Model selection favors recent, capable, inexpensive Chinese-developed models. There is no automatic retry or expensive fallback. A ceiling is not an expected invoice; exact replay requires no API calls.

```sh
python -m pytest tests
python -m zenith validate
python scripts/check_structure.py
python scripts/check_extraction.py
```

For an agent-assisted review, use the [website's agent map](https://wcook04.github.io/plectis-zenith/agent-map.md), or clone this repository and ask the agent to read `AGENTS.md`, this README, `program.md` and the selected experiment's protocol. The website explains the research. Saved result files and archived source let you inspect the actual inputs, outputs, errors and costs and repeat the software tests. [Contributing](CONTRIBUTING.md) · [Research boundary](RESEARCH_NOTICE.md).

The [static site exporter](scripts/export_site_snapshot.py) owns the generated `llms.txt`, `agent-map.md`, `agent-index.json` and direct JSON files in `site/dist/`; [the frontend guide](site/README.md#static-publication) documents the build. The map reuses the public API from [zenith/web_content.py](zenith/web_content.py), with [publication regressions](tests/test_site_snapshot.py) and [layout validation](scripts/check_structure.py). Generated navigation adds no browser script, fetch or preload to human reading.

Earlier [memory studies](docs/continuation-memory.md), [native observation studies](docs/executable-investigations.md), [structural studies](docs/decomposition-20261014.md), [financial investigator](docs/investigator.md), [full graph](docs/full-graph-case.md), [basket pilot](docs/baskets.md) and [System A fixture](docs/demo.md) retain their original artifacts. Their results are not pooled with the current comparison.

## Credits and license

Created by Will Cook with AI coding agents. Zenith adapts the `ai_workflow` research system and the explicitly attributed research-return components in [NOTICE](NOTICE). The [extraction manifest](docs/extraction-manifest.json) records source custody and maintained adaptations. Software is licensed under [Apache 2.0](LICENSE).

The website uses React, React Flow and React Markdown; its graph viewer and inspectors adapt the earlier research UI. [Reuse details](site/README.md#what-came-from-the-original-zenith-ui) and the [SIL Open Font Licenses](site/public/fonts/) are retained. Software licensing does not grant rights to separately acquired datasets or provider responses.
