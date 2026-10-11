---
name: lab-miner-v2-calc
description: Apply the typed lab_miner_v2_calc operation to its declared context.
---
# lab_miner_v2_calc

- Input ports: `lab_decide`, `global_calculator_feed`.
- Output contract: `text`. Mission: `lab`.
- Implementation: `codex/substrate/nodes/lab/miner_v2_calc.json`; shared contracts compile at dispatch.
- Parameters: frozen skill rule, incoming-edge weights, context budget.
- Version: `6f525a6e7c7cf11558d8bb26be17ab7edaa715ac988873e2aff3f7b40263de37`.
- Inspect: `python -m zenith inspect lab_miner_v2_calc`.

Generated projection; edit the source or a frozen experimental variant, then rebuild. These fields declare a contract; they do not prove the model follows it.
