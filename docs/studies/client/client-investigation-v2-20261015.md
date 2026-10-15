# Client investigation v2: clarified prompt, failed retained delivery

The v2 prompt explicitly permits a new legal experiment before any target result exists. In this complete engineering follow-up, the retained procedure was invalid Python and the ordinary reusable tester again stopped without a target query. Fresh investigation with development history and cold investigation each found three of the four faulty clients. The fixed tester found all four.

The population had already been exposed in [v1](client-investigation-20261014.md). V2 tests delivery of a clarified instruction on those same authored SQLite clients; its results do not establish an independent efficacy estimate, a prompt's causal effect, a learning advantage or transfer. Development histories and model replies also differ between runs. V1 remains a separate frozen record.

## What was delivered

The procedure response encoded its entire Python body on one line, with assignments and compound `if` statements separated by spaces. The unchanged validator rejected it with `SyntaxError: invalid syntax (<unknown>, line 1)`. All five procedure target slots therefore retain `not_run: invalid frozen artifact`. The raw response remains published; the host did not insert line breaks or repair the source.

The ordinary tester was valid Python. Its only action returned `query: null`, asserting that no legal transfer query could be constructed from the batch development grammar. The preparation request had supplied the transfer contract and full transfer grammar. This is a recorded delivery failure; its note is not evidence that the interface lacked that information. The program ran unchanged five times and stopped each time.

| Arm | Faulty clients detected | Target query slots | Valid native probes | Target model calls | Target model cost |
|---|---:|---:|---:|---:|---:|
| Retained procedure | 0 / 4; invalid artifact | 0 | 0 | 0 | $0 |
| Ordinary code reuse | 0 / 4; immediate stop | 0 | 0 | 0 | $0 |
| Same-history fresh | 3 / 4 | 15 | 15 | 15 | $0.003468402 |
| Cold investigation | 3 / 4 | 16 | 16 | 16 | $0.001699941 |
| Fixed tester | 4 / 4 | 7 | 7 | 0 | $0 |

| Target | Protected client panel | Procedure | Ordinary reuse | Same-history | Cold | Fixed |
|---|---:|---|---|---|---|---|
| `transfer-b8` | 58 / 80 correct | Invalid artifact | Stop | Witness | Witness | Witness |
| `transfer-f3` | 72 / 80 correct | Invalid artifact | Stop | No witness in 6 probes | No witness in 6 probes | Witness |
| `transfer-m6` | 80 / 80 correct | Invalid artifact | Stop | No witness | No witness | No witness |
| `transfer-q1` | 36 / 80 correct | Invalid artifact | Stop | Witness | Witness | Witness |
| `transfer-v4` | 40 / 80 correct | Invalid artifact | Stop | Witness | Witness | Witness |

Detection requires a host-measured reference/client state difference on a legal query. The finite panel characterizes the client, not investigator prediction accuracy. Keeping the client that passes all 80 panel cases does not make no-witness runs a model-specificity measure or certify unrestricted client correctness. Query rows are correlated within each target.

There was one invalid artifact delivery and no invalid or duplicate study queries. Direct model deliveries were valid. The ordinary tester's five executions took about 0.546 seconds; native development and target queries took about 0.022 seconds. These observed timings are not calibrated performance estimates. The complete study records 20 executed target-arm runs and five skipped procedure runs, then opens the protected panel after the whole study freezes.

## Full lifecycle and evidence

This condition pinned `deepseek/deepseek-v4.1-flash`, `morph/fp8`, reasoning `none`, and a 12,288-token output limit before inference. All 45 attempts settled with known reported cost, totaling **$0.006991092**, below the 92-call and $2 ceilings. Billing retains 178,492 prompt tokens, 6,581 completion tokens and zero reported reasoning tokens.

| Phase | Model calls | Reported model cost |
|---|---:|---:|
| Shared development investigation | 12 | $0.000972987 |
| Invalid procedure compilation | 1 | $0.000710898 |
| Ordinary tester preparation | 1 | $0.000138864 |
| All target investigation | 31 | $0.005168343 |
| Total | 45 | $0.006991092 |

The zero target-call costs of the retained arms include their failed deliveries; their preparation costs remain charged above. The evidence records 50 study probes, ten shared public examples and 400 protected validation probes. Reference and client execute separately: lifecycle totals are 460 reference calls, 460 client calls, 8,194 reference SQL statements and 7,134 client SQL statements. Observed model network time was about 49.849 seconds. Native execution has work counters and query/policy times, without a cash price. Human authoring and provider-metadata lookup time or charges were not separately metered.

The [machine report](../../../examples/conformance/client-reuse-v2/report.json) is an identical copy of [report.json](../../../examples/conformance/client-reuse-v2/report.json) in the verified [v2 evidence bundle](../../../examples/conformance/client-reuse-v2/manifest.json). The bundle preserves original prompts, raw outputs, prepared population, frozen state, protected panel, source archive and hash-matched [v2 protocol](../../client-investigation-protocol-v2-20261015.md). Scientific files are copied byte for byte. Billing is an allowlisted projection that excludes credentials and private transport records. There were no retries or manual repairs.

Exact archived replay was verified under Python 3.13.7 and SQLite 3.53.4 with zero network access:

```sh
python scripts/build_client_investigation_report.py replay examples/conformance/client-reuse-v2
```

The replay reproduces all 45 recorded model attempts, 50 study probes, invalid-source rejection, stops and 400 protected client-panel cases. A different SQLite version can fail the exact identity check. The separately named behavioral check preserves archive, prompt and response custody, compares all query/outcome/error/work/cost fields, and excludes only SQLite version identity plus the original replay clock exclusions:

```sh
python scripts/build_client_investigation_report.py replay-behavior examples/conformance/client-reuse-v2
```

Its receipt reports `behavioral_match`, both SQLite identities and whether the environment changed. It cannot report exact runtime replay. Any later reasoning-setting condition requires its own freeze, accounting and result; it does not replace these failed outputs.
