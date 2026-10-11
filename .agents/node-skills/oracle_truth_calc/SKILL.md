---
name: oracle-truth-calc
description: Apply the typed oracle_truth_calc operation to its declared context.
---
# oracle_truth_calc

- Input ports: `oracle_subject_index`, `oracle_subject_calc_feed`, `global_calculator_feed`.
- Output contract: `json`. Mission: `oracle`.
- Implementation: `codex/substrate/nodes/oracle/oracle_truth_calc.json`; shared contracts compile at dispatch.
- Parameters: frozen skill rule, incoming-edge weights, context budget.
- Version: `2db906d5dbd6646f851844776b7a49ac0fec30475378055fb934e714d8dc1235`.
- Inspect: `python -m zenith inspect oracle_truth_calc`.

Generated projection; edit the source or a frozen experimental variant, then rebuild. These fields declare a contract; they do not prove the model follows it.
