---
name: oracle-truth-map
description: Apply the typed oracle_truth_map operation to its declared context.
---
# oracle_truth_map

- Input ports: `oracle_subject_index`, `oracle_truth_diff_equity`, `oracle_truth_diff_macro`, `oracle_truth_stock`, `oracle_truth_etf`, `oracle_truth_macro`, `oracle_truth_news`, `oracle_truth_poly`, `oracle_truth_calc`, `oracle_truth_stockgrid`.
- Output contract: `schema_realized_hindsight_brief`. Mission: `oracle`.
- Implementation: `codex/substrate/nodes/oracle/oracle_truth_map.json`; shared contracts compile at dispatch.
- Parameters: frozen skill rule, incoming-edge weights, context budget.
- Version: `deaf04fa58430aa4c34ee8cf30e751b672a4764d25358b1ccd15000719ec53ea`.
- Inspect: `python -m zenith inspect oracle_truth_map`.

Generated projection; edit the source or a frozen experimental variant, then rebuild. These fields declare a contract; they do not prove the model follows it.
