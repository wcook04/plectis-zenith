# Executable investigations and measured repair

The active test asks whether a model can write a useful experiment, observe a real discrepancy, and repair the program that produced it. Its simplest useful retained object is **a program together with the experiments that expose its limits**. The program's call graph helps inspection; it imposes no special execution architecture.

`research/conformance_study.py` implements the loop. `research/native_conformance_tasks.py` supplies three native diagnostic contracts: SQLite allocation across transactions, LRU cache counters, and incremental UTF8 decoding. These are authored wrappers around real library behavior, not production client workloads. Each contract receives two independently generated parent programs. Correct parents and invalid deliveries remain in the study. Nothing filters for attractive defects.

## What runs

1. Freeze the six tasks, public examples, two disjoint later panels, model settings, endpoint assignment and runtime source before inference.
2. Ask for a fresh whole program from the public contract and eight measured examples. This first proposal is the no-change control.
3. Compare three investigations of the same parent. **Ordinary** writes an unrestricted adaptive test program. **Witness** writes one with an optional compact account of the obligation, suspected assumption, evidence and proposed change. **Fixed** uses eight authored boundary/prefix tests without a policy-generation call.
4. Run each investigation with at most eight query slots. A generated policy sees the contract, complete parent code, public examples and its own accumulated receipts. The host measures the native source and executes the parent separately. The first verified discrepancy stops investigation. Duplicates and invalid requests consume slots; invalid requests cannot refute a parent.
5. Give each arm one whole-program repair call, including its actual measurements, failed execution and optional notes. A repair is selected only if it preserves every measured case the parent got right and does not worsen the aggregate development result. Rejected source is retained unchanged.
6. Freeze all selections, then evaluate the two later panels. Replay rebuilds every prompt, parses the original responses, re-executes the policies, native measurements, selection and later outcomes from the archived source.

The witness account is a proposal, not privileged introspection. It may suggest a missing input, wrong update, wrong readout, new question or deletion of the decomposition. The host does not certify those explanations or route changes through a special graph. Both generated policies receive the same complete context and may use any approach. This comparison therefore tests prompting and its executable consequences, not a graph engine.

Each generated-policy arm spends two calls after the parent; fixed testing spends one. All arms receive a repair call even when they discover no discrepancy, so repair gains alone do not identify the value of investigation. The current pilot has 36 calls at most. Query attempts, valid native probes, source-specific valid completed-probe work units, execution failures, model tokens and billed cost are retained separately. Work units are not interchangeable across the three libraries. An invalid query may execute a native prefix before rejection; valid-probe units exclude that partial work. Query attempts and slots remain recorded, and these counters do not justify claims about total physical source work. The exact-copy public evidence is exported by `scripts/build_conformance_report.py`; transport records and credentials stay local.

## Why these distinctions matter

The earlier SQLite failures retained the information they needed but ignored pending values at readout. Enlarging their state would have misdiagnosed the problem. A different, rows-only helper really did discard necessary history. An equal-input/different-obligation witness can rule out a particular local repair only when the captured input includes all available state and context. A node's claim that it needs more context does not establish this condition.

An improved program and an improved way of learning are different outcomes. The current live study tests newly generated experiments and repair; it does not yet revise and transfer an investigator across episodes. The continuation-memory experiment takes a separate step: retain test directions acquired during one workload, then measure whether they reduce the queries needed to acquire a later model beyond retaining the same raw answers. That controlled mechanism uses an authored algebraic learner and must also be compared with ordinary separate implementations and known-family fitting.

The next useful advance is a reusable investigation procedure whose value survives a changed client or mechanism. It must outperform a competent ordinary tester with the same earlier experience, after accounting for acquisition and execution cost. A smaller graph, a bypassed helper or direct native operation is an acceptable winning result.

## Commands

```sh
python -m research.conformance_study prepare work/native-pilot \
  --model inclusionai/ling-3.1-flash \
  --providers deepinfra/fp4 --workers 1 \
  --reasoning-effort none --max-output-tokens 12288 --max-cost-usd 0.60
python -m research.conformance_study run work/native-pilot --env-file /path/to/local.env
python -m research.conformance_study confirm work/native-pilot
python scripts/build_conformance_report.py export work/native-pilot examples/conformance/native-pilot
python scripts/build_conformance_report.py replay examples/conformance/native-pilot
```

The dollar figure is a ceiling, not a predicted charge. Current inexpensive Chinese model and endpoint metadata must be checked when launching a new campaign. Independent episodes use at most three host calls and one call per pinned endpoint; dependent calls remain ordered. Failed deliveries are recorded, never automatically retried. New model outputs constitute a new experiment, while archived replay uses no model calls.

The parent episode is the experimental unit. Two parents per contract and many query rows do not create six independent mechanisms or hundreds of independent replications. Both later panels test the same disclosed diagnostic population. These results can select the next experiment; they cannot establish general recursive self-improvement or a production advantage.

[Fifteen-return assimilation](advance-returns-20261014.md) records which mechanisms were adopted, reproduced or deferred. [Earlier structural campaign](decomposition-20261014.md) retains its original methods and evidence.

## Recorded campaign

The full frozen Ling3.1Flash comparison, `examples/conformance/ling-full-v3b`, completed all 36 calls for $0.03205644. The current metadata check selected this recently listed, eligible model and pinned DeepInfra's compatible endpoint at $0.30 input/$0.90 output per million tokens, with reasoning disabled. The protocol records the observation and prices; future runs must check again. Those prices apply to the chosen endpoint, not every host carrying the model.

| Arm | Screen / 288 | Confirmation / 288 | Valid probes | Semantic / execution defects |
|---|---:|---:|---:|---:|
| Unchanged parent | 218 | 216 | — | — |
| Ordinary generated policy | 218 | 216 | 3 | 1 / 0 |
| Diagnostic generated policy | 224 | 218 | 4 | 0 / 0 |
| Fixed tester | 241 | 239 | 29 | 1 / 2 |

The diagnostic arm improved a SQLite program without discovering a native counterexample. The ordinary arm found a UTF-8 semantic discrepancy but did not improve its aggregate later score. Fixed testing exposed two execution failures and a SQLite semantic failure, improving the aggregate while one UTF-8 repair regressed on later cases. Preserving measured successes does not guarantee later preservation. Ten of the eighteen repair proposals were byte-identical to their parents; selection permits a tie and does not by itself establish improvement. Three parents already scored perfectly on both panels, which limits repair headroom; we kept them rather than selecting only broken parents.

The first two attempts exposed concrete interface failures: a stopped DeepSeek run under its original restrictive executor and a three-call Ling qualification whose selector used a missing builtin. Narrow changes admitting `while` and pure `repr`, with existing resource limits, each started separately frozen experiments. The qualification's repair improved despite zero native probes; it cannot support an investigation claim. A later v3 attempt stopped on a disk write failure; its exact committed records and unknown final provider charge are recovered explicitly, without inventing a successful original freeze. The full fresh v3b instance ran on external storage. The [campaign receipt](advance-campaign-20261014.json) includes all five studies separately.

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
