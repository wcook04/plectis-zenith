# Client investigation v2-low: working code reuse, fixed tests still win

Both retained programs were valid and ran unchanged against all five transfer clients. Each found three of the four faulty clients with five native probes and no target model calls. Same-history fresh and cold investigation also found three; the fixed tester found all four. This condition establishes working delivery and reuse of model-generated test code on the already exposed SQLite population. It does not establish a learned investigation advantage or transfer.

The two retained programs return the same query on every invocation. Each consumes ten duplicate-query slots after its first probes fail to find a witness on two clients. Their behavior supplies no acquired adaptive policy: neither program reads the target measurements to select a different question.

## Condition and paired results

This is a separate freeze after inspection of [v1's stops](client-investigation-20261014.md) and [v2's invalid procedure and stopping ordinary tester](client-investigation-v2-20261015.md). It retains the [v2 prompt](../../client-investigation-protocol-v2-20261015.md), five development clients, five target clients and evaluator. It requests `low` reasoning instead of `none` and raises the output-token limit from 12,288 to 16,384. Those changes, new model replies and new development history prevent a causal attribution to reasoning. The provider reports zero reasoning tokens despite the requested setting.

The run pins `deepseek/deepseek-v4.1-flash` to `morph/fp8`. Each arm has six query slots per target, one query per feedback decision. Invalid and duplicate queries consume slots; detection stops the run. The artifacts freeze before any target query. All 25 target runs complete before the protected panel opens. The previous failures remain unchanged records, without retries or manual output repair.

| Arm | Faulty clients detected | Target slots | Valid probes | Duplicate slots | Target model calls | Target model cost |
|---|---:|---:|---:|---:|---:|---:|
| Retained procedure | 3 / 4 | 15 | 5 | 10 | 0 | $0 |
| Ordinary code reuse | 3 / 4 | 15 | 5 | 10 | 0 | $0 |
| Same-history fresh | 3 / 4 | 19 | 15 | 4 | 19 | $0.004209498 |
| Cold investigation | 3 / 4 | 15 | 15 | 0 | 15 | $0.001581060 |
| Fixed tester | 4 / 4 | 7 | 7 | 0 | 0 | $0 |

| Target | Protected client panel | Procedure | Ordinary reuse | Same-history | Cold | Fixed |
|---|---:|---|---|---|---|---|
| `transfer-b8` | 58 / 80 correct | Witness | Witness | Witness | Witness | Witness |
| `transfer-f3` | 72 / 80 correct | No witness | No witness | No witness | No witness | Witness |
| `transfer-m6` | 80 / 80 correct | No witness | No witness | No witness | No witness | No witness |
| `transfer-q1` | 36 / 80 correct | Witness | Witness | Witness | Witness | Witness |
| `transfer-v4` | 40 / 80 correct | Witness | Witness | Witness | Witness | Witness |

A witness is a host-measured native reference/client state difference from a legal query. Model notes and diagnoses are not scored. The panel characterizes each client's finite behavior; no-witness runs do not establish investigator specificity or unrestricted client correctness. Query rows are correlated within a target.

The retained probe opens a caller transaction, transfers three units from account 1 to account 2, then attempts a missing-source transfer and an insufficient-funds transfer. Account 2 has eight units after the first transfer; requesting nine still fails. Both failure cases stop before a successful debit. They therefore miss the partial-debit fault in `transfer-f3`, which requires a missing destination after the source has been debited. The fixed tester's first query covers that case. Each retained program also proposes a continuation credit to an absent account, so that continuation fails in the measured reference. These details come from native traces and source, rather than the programs' scope claims.

There are no invalid artifact deliveries, malformed direct deliveries or nonduplicate invalid queries. Each retained program executes 15 times: one measured probe on each client, plus five rejected repeats on each of the two clients without a witness. Observed policy time totals 1.336 seconds for the procedure and 2.178 seconds for ordinary reuse. Native development and target queries total about 0.036 seconds. These are observed timings, not calibrated performance estimates.

## Acquisition and full lifecycle cost

All 46 provider attempts settle with known reported cost, totaling **$0.007117764**, within the 92-call and $2 ceilings. Billing retains 212,484 prompt tokens and 6,520 completion tokens. Official model/endpoint discovery evidence and the decision to run this condition after earlier failures remain in its frozen protocol. Metadata lookup time or charges and human authoring time were not separately metered.

| Phase | Model calls | Reported model cost |
|---|---:|---:|
| Shared development investigation | 10 | $0.000802116 |
| Procedure compilation | 1 | $0.000346182 |
| Ordinary tester preparation | 1 | $0.000178908 |
| Same-history target investigation | 19 | $0.004209498 |
| Cold target investigation | 15 | $0.001581060 |
| Total | 46 | $0.007117764 |

For one route using this acquired history, development plus procedure compilation costs $0.001148298 across 11 calls; development plus ordinary preparation costs $0.000981024 across 11 calls. Development plus same-history target investigation costs $0.005011614 across 29 calls. Cold investigation uses no development history and costs $0.001581060 across 15 calls. These alternative route totals repeat the shared acquisition cost for comparison and must not be added together. They describe this run on a known population. The fixed tester makes no model calls and detects the additional faulty client.

| Stage or arm | Native reference calls | Native client calls | Reference SQL | Client SQL |
|---|---:|---:|---:|---:|
| Shared development queries | 10 | 10 | 242 | 221 |
| Procedure target queries | 5 | 5 | 115 | 93 |
| Ordinary reuse target queries | 5 | 5 | 115 | 93 |
| Same-history target queries | 15 | 15 | 356 | 312 |
| Cold target queries | 15 | 15 | 321 | 273 |
| Fixed target queries | 7 | 7 | 155 | 135 |
| Shared public examples | 10 | 10 | 100 | 92 |
| Protected validation | 400 | 400 | 7,040 | 6,128 |
| Total | 467 | 467 | 8,444 | 7,347 |

The 57 development/target probes are distinct from the ten shared examples and 400 protected cases. Each probe invokes reference and client separately. Duplicate slots do not perform native calls. Observed provider network time totals about 81.074 seconds. Native execution is reported as work counters and observed query/policy time, without a cash price. These records prevent zero target model calls from erasing acquisition, compilation or failed work.

## Evidence and replay

The [machine report](../../../examples/conformance/client-reuse-v2-low/report.json) is identical to [report.json](../../../examples/conformance/client-reuse-v2-low/report.json) in the verified [evidence bundle](../../../examples/conformance/client-reuse-v2-low/manifest.json). The bundle preserves every original prompt and raw reply, both compiled programs, duplicate rejections, native measurements, prepared tasks, frozen state, protected panel, runtime source archive and hash-matched protocol source. Scientific files are copied byte for byte; billing is an allowlisted projection excluding credentials and private transport records.

Exact replay under Python 3.13.7 and SQLite 3.53.4 reproduces all 46 model attempts, 57 study probes and 400 protected cases with zero network calls:

```sh
python scripts/build_client_investigation_report.py replay examples/conformance/client-reuse-v2-low
```

For another SQLite version, use the explicitly separate behavioral check:

```sh
python scripts/build_client_investigation_report.py replay-behavior examples/conformance/client-reuse-v2-low
```

It retains exact archive, prompt and reply custody and compares every query, outcome, error, work counter and cost. It excludes only SQLite version identity in addition to the exact replayer's existing clock exclusions, reports both environments and labels success `behavioral_match`. Changed behavior or SQL work still fails. All three conditions remain available separately; their adaptive selection and shared authored population preclude pooling them as independent replications.
