---
name: oracle-truth-stock
description: Apply the typed oracle_truth_stock operation to its declared context.
---
# oracle_truth_stock

- Input ports: `oracle_subject_index`, `oracle_truth_diff_equity`, `oracle_subject_stock_feed`, `global_stock_feed`.
- Output contract: `json`. Mission: `oracle`.
- Implementation: `codex/substrate/nodes/oracle/oracle_truth_stock.json`; shared contracts compile at dispatch.
- Parameters: frozen skill rule, incoming-edge weights, context budget.
- Version: `5c928525f83def290e5d9b65e76c9081e51dad499a149816a1c81945eb4e1dc2`.
- Inspect: `python -m zenith inspect oracle_truth_stock`.

Generated projection; edit the source or a frozen experimental variant, then rebuild. These fields declare a contract; they do not prove the model follows it.
