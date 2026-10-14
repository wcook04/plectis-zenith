# Plectis Zenith

Zenith studies whether experience can improve the next investigation. It retains executable programs, measured evidence and tests that expose the programs' limits. The goal is useful accumulated capability: solve later problems more accurately or with less acquisition work.

The active implementation writes experiments, measures native behavior, and repairs ordinary code while preserving every previously successful measured case. A parallel controlled study asks whether **learned questions help beyond retaining the same old answers**. The graph is an inspectable, revisable organization of computation; it can shrink or disappear when simpler code works better.

- [Current results and limits](docs/status.md)
- [Current paper source](paper/zenith.tex) · [previous PDF edition](paper/zenith.pdf)
- [Native investigation and repair method](docs/conformance-study.md)
- [Continuation-test memory experiment](docs/continuation-memory.md)
- [A model-acquired regression test and its provenance](examples/conformance/learned-regressions.json)
- [Research programme](program.md)
- [Fifteen ADVANCE returns: synthesis and reproduction](docs/advance-returns-20261014.md)

## One concrete distinction

A failed node may lack information, ignore information it already holds, or never have seen the relevant behavior. Those require different interventions. The earlier SQLite programs retained pending values but dropped them at readout; their original rows-only helper really did lose history. A useful investigation supplies a measured witness and lets the repair change the complete program. A node's explanation is a proposal to check.

The new native comparison gives fresh model-generated parents to an ordinary adaptive investigator, an investigator prompted to report obligations and suspected boundaries, and a competent fixed tester. All can deliver evidence to unrestricted repair. Later cases are hidden until selection freezes. This tests executable consequences of the ideas rather than the persuasiveness of a report.

## Run

```sh
python -m pip install -e '.[test,research]'
python -m research.conformance_study prepare work/native-pilot \
  --model inclusionai/ling-3.1-flash \
  --providers deepinfra/fp4 --workers 1 \
  --reasoning-effort none --max-output-tokens 12288 --max-cost-usd 0.60
python -m research.conformance_study run work/native-pilot --env-file /path/to/local.env
python -m research.conformance_study confirm work/native-pilot
```

This creates a new experiment. Its dollar ceiling is a maximum, not an expected bill. Check current model and endpoint metadata before a new run; prefer recent, capable, inexpensive Chinese-developed models. Independent trials use at most three concurrent calls across the host and one per pinned endpoint. Dependent calls remain ordered, with no automatic retry or expensive fallback. Exact archived replay uses no model calls.

## Source map

| Owner | Role |
|---|---|
| [Conformance study](research/conformance_study.py) | Fresh parents, executable investigations, measured repair and frozen later evaluation |
| [Native tasks](research/native_conformance_tasks.py) | SQLite, LRU and UTF8 contracts, measured examples, fixed tester and protected cases |
| [Campaign projection](scripts/build_advance_report.py) | Separate source-bound studies, all recorded costs and memory controls |
| [Conformance publication](scripts/build_conformance_report.py) | Exact scientific evidence, billed attempts and archived-source replay |
| [Restricted execution](zenith/investigation_program.py) | Proposed Python under syntax, process, time and memory limits |
| [Source custody](zenith/source_snapshot.py) | Standard-library snapshot owner shared by current and legacy runners |
| [Budgeted provider](zenith/budgeted.py) | Explicit model route, reasoning setting, immutable requests and cost ledger |
| [Model policy](zenith/provider_policy.py) | Cheap eligible models and bounded host-wide admission |
| [Structural revision](research/decomposition_study.py) | Earlier whole-program, local-context and function-signature comparisons |
| [Rule induction](research/state_discovery_tasks.py) | Earlier disclosed finite-family source rules and observations |
| [Historical observation loop](research/observation_learning_study.py) | Earlier SQLite experiments, retained programs and frozen audit |

```sh
python -m pytest tests
python -m zenith validate
python scripts/build_graphs.py
python scripts/check_extraction.py
python scripts/build_decomposition_report.py replay examples/decomposition/binding-deepseek-low-global-v1
```

The [site and read-only API](site/README.md) are the human reading interface for the manuscript, methods and reviewed receipts. For an agent-assisted source review, clone this repository and ask the agent to read `AGENTS.md`, this README, `program.md` and the specific experiment's protocol before editing or making claims.

Earlier [native observation studies](docs/executable-investigations.md), [structural and source-rule studies](docs/decomposition-20261014.md), [financial investigator](docs/investigator.md), [full graph](docs/full-graph-case.md), [basket pilot](docs/baskets.md) and [System A fixture](docs/demo.md) retain their original artifacts and evidence boundaries. The active programme does not require revisiting every historical route. [Research notice](RESEARCH_NOTICE.md).
