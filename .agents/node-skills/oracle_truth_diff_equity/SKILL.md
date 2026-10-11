---
name: oracle-truth-diff-equity
description: Apply the typed oracle_truth_diff_equity operation to its declared context.
---
# oracle_truth_diff_equity

- Input ports: `oracle_subject_stock_feed`, `oracle_subject_etf_feed`, `global_stock_feed`, `global_etf_feed`, `oracle_subject_lab_director`.
- Output contract: `schema_prediction_reconciliation`. Mission: `oracle`.
- Implementation: `codex/substrate/nodes/oracle/oracle_truth_diff_equity.json`; shared contracts compile at dispatch.
- Parameters: frozen skill rule, incoming-edge weights, context budget.
- Version: `5c50bb8a90e699eeee1972c8ea27d0effa5dd5924b5b3a7eacbe952954eff884`.
- Inspect: `python -m zenith inspect oracle_truth_diff_equity`.

Generated projection; edit the source or a frozen experimental variant, then rebuild. These fields declare a contract; they do not prove the model follows it.
