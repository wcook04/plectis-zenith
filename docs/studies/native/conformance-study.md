# Executable investigations and measured repair

Zenith asks whether an experiment provides evidence that helps repair a program. The retained object is ordinary executable code, measured observations and queries that expose its limits. A useful explanation must lead to a checkable change or a better next question.

The current six-arm runner is `research/conformance_study.py`. Its native contracts cover SQLite allocation across transactions, LRU cache counters and incremental UTF-8 decoding. These are authored diagnostic wrappers around library behavior. They are not independently acquired production applications. The [prospective protocol](../../progress-protocol-20261014.md) specifies the new comparison; the [PROGRESS synthesis](../../history/progress-returns-20261014.md) records its source ideas and reproduction limits.

## What runs

1. Freeze the task data, public examples, two later panels, source archive, model route, analysis and budgets before inference.
2. Generate a parent program from the public contract and eight measured examples. Keep correct, incorrect and invalid programs in the denominator.
3. Give the same parent to six arms: **ordinary** compiles a Python selector; **fixed** uses predeclared boundary tests; **direct_batch** proposes up to eight queries in one JSON response; **direct_adaptive** can use measured outcomes to choose a second batch; **direct_masked** receives query identities without their outcomes; **repair_only** gets no new tests.
4. The direct host owns validation, deduplication, iteration and source access. Each investigator has eight proposal slots and stops at the first verified discrepancy. Invalid and duplicate proposals consume slots. A source error permitted by the contract is an observation; an investigator error is not a parent defect.
5. Every arm receives one whole-program repair call with its actual evidence. The selected repair must preserve every previously correct measured case and not worsen the aggregate development result. Rejected source and unchanged programs remain recorded.
6. Freeze every selection before opening later panels. Archived replay reconstructs prompts, raw output parsing, measurements, selection and later scores without model calls.

The adaptive and masked arms share one exact first provider response. Each separately reexecutes the native measurements and parent; both executions count in their arm. Only the second model call differs in access to outcomes. Early stopping can mean no second decision occurs. This must be reported, rather than treating all parent episodes as feedback interventions. Fixed testing and repair-only each save investigation calls and remain serious cost-aware rivals.

The qualification and diagnostic use separately seeded, nonoverlapping later panels. Their public contracts are shared; replicate-zero parent prompts repeat. New provider calls therefore do not guarantee unique source programs or independent mechanisms. Report repeated programs and family-level outcomes. Hundreds of query rows are not hundreds of experimental subjects.

The restricted Python executor has an explicit language and resource contract. A language-delivery failure belongs to the observed pipeline; it does not show that a model cannot solve the native task with ordinary unrestricted Python. The direct interface removes selector-code delivery as one possible failure, while whole-program repair still uses that executor.

## What the measurements mean

A model's note is a hypothesis, not privileged introspection. It can suggest missing information, an incorrect update or readout, a new test, or removal of a decomposition. The host certifies only what it measures. For example, an earlier SQLite program retained pending inserts but ignored them at readout. Enlarging its state would have misdiagnosed that failure. A different rows-only helper genuinely discarded history.

An improved program and an improved learning procedure require different evidence. This study compares investigations of fresh programs. It does not update an investigator across episodes. The separate [continuation learner](../../../examples/continuation-memory/witness-preserving-v1/README.md) preserves histories and questions that distinguish them within an authored rational-linear class. Neither implementation alone establishes transfer of an acquired investigation strategy.

Count provider attempts, valid distinct source queries, proposal slots, duplicates, execution failures, tokens and reported cost separately. Native work units are source-specific. A rejected query may execute a native prefix; completed-probe counters exclude that partial work and do not measure total physical work. Shared provider calls are billed once in campaign totals. Unknown charges remain unknown.

## Reproduce or run

The public bundles use each study's archived source, so later changes to the maintained runner cannot rewrite its results. The learner demonstration needs no account:

```sh
python scripts/demo_continuation_learning.py
python scripts/demo_continuation_learning.py --native
```

To create a new paid study, first verify current inexpensive Chinese-developed model and endpoint metadata, then use an explicit route and ceiling:

```sh
python -m research.conformance_study prepare work/native-pilot \
  --model inclusionai/ling-3.1-flash \
  --providers deepinfra/fp4 --workers 3 --parents-per-contract 1 \
  --reasoning-effort none --max-output-tokens 12288 --max-cost-usd 0.60
python -m research.conformance_study run work/native-pilot --env-file /path/to/local.env
python -m research.conformance_study confirm work/native-pilot
python scripts/build_conformance_report.py export work/native-pilot examples/conformance/native-pilot
python scripts/build_conformance_report.py replay examples/conformance/native-pilot
```

The ceiling is a maximum, not an expected charge. Independent work uses at most three host calls and one per pinned endpoint. Dependent calls remain ordered. There is no automatic retry or expensive fallback. A changed interface starts a separately frozen study.

## Historical three-arm campaign

The full frozen Ling3.1Flash comparison, `examples/conformance/ling-full-v3b`, completed all 36 calls for $0.03205644. The current metadata check selected this recently listed, eligible model and pinned DeepInfra's compatible endpoint at $0.30 input/$0.90 output per million tokens, with reasoning disabled. The protocol records the observation and prices; future runs must check again. Those prices apply to the chosen endpoint, not every host carrying the model.

| Arm | Screen / 288 | Confirmation / 288 | Valid probes | Semantic / execution defects |
|---|---:|---:|---:|---:|
| Unchanged parent | 218 | 216 | — | — |
| Ordinary generated policy | 218 | 216 | 3 | 1 / 0 |
| Diagnostic generated policy | 224 | 218 | 4 | 0 / 0 |
| Fixed tester | 241 | 239 | 29 | 1 / 2 |

The diagnostic arm improved a SQLite program without discovering a native counterexample. The ordinary arm found a UTF-8 semantic discrepancy but did not improve its aggregate later score. Fixed testing exposed two execution failures and a SQLite semantic failure, improving the aggregate while one UTF-8 repair regressed on later cases. Preserving measured successes does not guarantee later preservation. Ten of the eighteen repair proposals were byte-identical to their parents; selection permits a tie and does not by itself establish improvement. Three parents already scored perfectly on both panels, which limits repair headroom; we kept them rather than selecting only broken parents.

The first two attempts exposed concrete interface failures: a stopped DeepSeek run under its original restrictive executor and a three-call Ling qualification whose selector used a missing builtin. Narrow changes admitting `while` and pure `repr`, with existing resource limits, each started separately frozen experiments. The qualification's repair improved despite zero native probes; it cannot support an investigation claim. A later v3 attempt stopped on a disk write failure; its exact committed records and unknown final provider charge are recovered explicitly, without inventing a successful original freeze. The full fresh v3b instance ran on external storage. The [campaign receipt](../../history/advance-campaign-20261014.json) includes all five studies separately.

```sh
python scripts/build_conformance_report.py replay examples/conformance/deepseek-low-v1
python scripts/build_conformance_report.py replay examples/conformance/ling-qualification-v2
python scripts/build_conformance_report.py replay examples/conformance/ling-interrupted-v3
python scripts/build_conformance_report.py replay examples/conformance/ling-full-v3b
python scripts/build_advance_report.py
```

The maintained runner may evolve; these commands use each experiment's own archived dependencies. Reproduction needs no account or paid calls.

One concrete useful question illustrates the difference between an explanation and evidence. The ordinary UTF-8 investigator proposed feeding bytes `[224, 128]`. The native decoder rejected this overlong prefix; the parent kept it open. The investigator's accompanying explanation incorrectly called it a valid encoding of NUL. The host's measured discrepancy was real despite that explanation. The subsequent repair was byte-identical and did not fix it. The SQLite diagnostic repair, by contrast, corrected an already-visible rollback failure without discovering a new counterexample. Neither case warrants treating a node's account as privileged self-knowledge.

A separately frozen follow-up used DeepSeek V4.1 Flash with low reasoning, a 16,384-token output allowance and one fresh parent per contract. It made fifteen attempts for $0.045197154672 before the LRU policy exhausted its allowance without assistant content. The ordinary SQLite policy also delivered truncated JSON. Complete UTF-8 investigations found semantic discrepancies, but the full construction stopped and no protected panel was opened. All fourteen delivered responses, including an unconsumed SQLite policy, are retained in `examples/conformance/deepseek-reasoning-v3c`. This follow-up does not establish a causal reasoning-mode advantage: model, routes, allowance and parents differ. Its delivery failure also does not justify a claim that the proposed investigation mechanism cannot work.
