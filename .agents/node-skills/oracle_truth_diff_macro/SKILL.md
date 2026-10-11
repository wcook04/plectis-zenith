---
name: oracle-truth-diff-macro
description: Apply the typed oracle_truth_diff_macro operation to its declared context.
---
# oracle_truth_diff_macro

- Input ports: `oracle_subject_macro_feed`, `global_macro_feed`.
- Output contract: `text`. Mission: `oracle`.
- Implementation: `codex/substrate/nodes/oracle/oracle_truth_diff_macro.json`; shared contracts compile at dispatch.
- Parameters: frozen skill rule, incoming-edge weights, context budget.
- Version: `d2a1ac8e98a167d5319e7c992d1f0af9869fe3ab6bd90aa05d0cfe2bb6624845`.
- Inspect: `python -m zenith inspect oracle_truth_diff_macro`.

Generated projection; edit the source or a frozen experimental variant, then rebuild. These fields declare a contract; they do not prove the model follows it.
