---
name: oracle-truth-macro
description: Apply the typed oracle_truth_macro operation to its declared context.
---
# oracle_truth_macro

- Input ports: `oracle_subject_index`, `oracle_truth_diff_macro`, `oracle_subject_macro_feed`, `global_macro_feed`.
- Output contract: `json`. Mission: `oracle`.
- Implementation: `codex/substrate/nodes/oracle/oracle_truth_macro.json`; shared contracts compile at dispatch.
- Parameters: frozen skill rule, incoming-edge weights, context budget.
- Version: `bc0bdbf762c7abd6bf85faacefd3e9d68051dfe6ba99b4e5743c55417170f456`.
- Inspect: `python -m zenith inspect oracle_truth_macro`.

Generated projection; edit the source or a frozen experimental variant, then rebuild. These fields declare a contract; they do not prove the model follows it.
