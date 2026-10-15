# Client investigation v1: direct investigation works; compiled reuse stops

The completed authored SQLite pilot found no advantage from either retained tester. Both compiled programs were valid, ran unchanged on all five later clients and immediately returned `query: null`. They issued no target probes and detected none of the four faulty clients. Fresh investigation with the same development history found all four faults; the predeclared fixed tester also found all four. Cold investigation found three.

This establishes working direct investigation and a failed compilation into reusable investigation code in this run. It supplies no positive learning or transfer result. The later clients are authored variations within the same SQLite family, with the transfer contract and grammar supplied before compilation.

## Paired target results

Five batch-import clients supplied development history. Five account-transfer clients were then investigated separately by each arm, with six query slots per client and no retries or manual repair. All retained code froze before target investigation. The protected panel opened only after all 25 target runs had frozen.

| Arm | Faulty clients detected | Target query slots | Valid native probes | Target model calls | Target model cost |
|---|---:|---:|---:|---:|---:|
| Retained procedure | 0 / 4 | 0 | 0 | 0 | $0 |
| Ordinary code reuse | 0 / 4 | 0 | 0 | 0 | $0 |
| Same-history fresh | 4 / 4 | 13 | 12 | 13 | $0.002559662 |
| Cold investigation | 3 / 4 | 17 | 17 | 17 | $0.001540814 |
| Fixed tester | 4 / 4 | 7 | 7 | 0 | $0 |

| Target | Protected client panel | Procedure | Ordinary reuse | Same-history | Cold | Fixed |
|---|---:|---|---|---|---|---|
| `transfer-b8` | 58 / 80 correct | Stop | Stop | Witness | Witness | Witness |
| `transfer-f3` | 72 / 80 correct | Stop | Stop | Witness | No witness in 6 probes | Witness |
| `transfer-m6` | 80 / 80 correct | Stop | Stop | No witness | No witness | No witness |
| `transfer-q1` | 36 / 80 correct | Stop | Stop | Witness | Witness | Witness |
| `transfer-v4` | 40 / 80 correct | Stop | Stop | Witness | Witness | Witness |

A witness is a legal query for which native reference and client states differ. Notes and diagnoses are not scored. The panel measures the client's behavior on 80 finite cases; it does not measure investigator prediction accuracy. The client that passes all 80 cases remains in the population, but no-witness runs do not establish model specificity or certify unrestricted correctness. Query rows within a target are correlated measurements.

Both retained programs explain their stop by referring to the absence of measured transfer outcomes. Their outputs are consistent with reading the instruction “Use only that measured evidence” as prohibiting a new question before a target has been measured. The run does not isolate that wording as the cause. The original prompts and raw replies remain intact. Any clarification belongs to a separately versioned experiment.

There were no invalid artifact deliveries, model-delivery errors or duplicate queries. Same-history fresh submitted one invalid transfer query on `transfer-m6`; it consumed a slot and produced no native measurement. Each retained program executed five times and stopped five times. Their observed execution totals were 0.522 and 0.498 seconds. Native query execution across development and all target arms took about 0.022 seconds. These are observed timings, not a calibrated performance benchmark.

## Full lifecycle and custody

The run pinned `deepseek/deepseek-v4.1-flash` to `morph/fp8` with reasoning `none`, based on official model and endpoint metadata recorded before inference. The protocol allowed at most 92 calls and $2; the complete run used 42 settled calls and reported **$0.005186696**. All 158,488 prompt tokens and 4,941 completion tokens remain in the billing projection; reported reasoning tokens were zero.

| Phase | Model calls | Reported model cost |
|---|---:|---:|
| Shared development investigation | 10 | $0.000782256 |
| Procedure compilation | 1 | $0.000194008 |
| Ordinary tester preparation | 1 | $0.000109956 |
| All target investigation | 30 | $0.004100476 |
| Total | 42 | $0.005186696 |

The zero target-call cost of the retained programs accompanies zero detection; preparation is included above. Shared development is charged once. The evidence records 46 study probes, ten shared public-example probes and 400 protected validation probes. Each probe invokes reference and client separately: the lifecycle total is 456 reference calls, 456 client calls, 8,213 reference SQL statements and 7,156 client SQL statements. Model network time totaled about 41.647 seconds. Native computation has work counters and observed query/policy time, without a cash price. Human authoring time and official metadata lookup time or charges were not separately metered.

The [machine report](client-investigation-20261014.json) is an identical copy of the verified bundle's [report.json](../examples/conformance/client-reuse-v1/report.json). The [bundle manifest](../examples/conformance/client-reuse-v1/manifest.json) binds the full prompts, original raw replies, prepared tasks, frozen state, protected panel, runtime source archive and hash-matched protocol source. Scientific files are copied byte for byte. The shared provider ledger is projected to allowlisted billing fields; credentials and private transport records are excluded. The [prospective v1 protocol](client-investigation-protocol-20261014.md) remains unchanged.

## Replay

Install the repository's declared test dependencies, then run from the repository root:

```sh
python scripts/build_client_investigation_report.py replay examples/conformance/client-reuse-v1
```

Exact replay was verified with Python 3.13.7 and SQLite 3.53.4: 42 model attempts, 46 study probes and all 400 protected client-panel cases reproduced without network access. Replay extracts the archived implementation and restores the hash-matched human protocol source. It does not substitute the current research implementation. SQLite version identity remains part of the exact comparison, so a different SQLite version can fail exact replay even when its measured behavior agrees.

An explicitly separate check permits that environment difference:

```sh
python scripts/build_client_investigation_report.py replay-behavior examples/conformance/client-reuse-v1
```

This verifies the same archive, file hashes, prompts and raw responses, reruns all recorded actions and protected cases, and compares queries, outcomes, errors, work counters and costs. It excludes only the `sqlite_version` identity field in addition to the exact replayer's existing clock exclusions. Its receipt reports `behavioral_match`, both SQLite identities and whether the environment changed. It never reports exact runtime replay. A changed outcome or SQL-work count still fails.
