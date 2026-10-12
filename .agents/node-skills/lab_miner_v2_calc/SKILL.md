---
name: lab-miner-v2-calc
description: Apply the typed lab_miner_v2_calc operation to its declared context.
---
# lab_miner_v2_calc

- Input ports: `lab_decide`, `global_calculator_feed`.
- Output contract: `text`. Mission: `lab`.
- Implementation: `codex/substrate/nodes/lab/miner_v2_calc.json`; shared contracts compile at dispatch.
- Parameters: frozen skill rule, incoming-edge weights, context budget.
- Version: `e534f304d3f594a3ce738159b8e5b96817b062bc69ad9bf778446e23eda5843a`.
- Inspect: `python -m zenith inspect lab_miner_v2_calc`.

Generated projection; edit the source or a frozen experimental variant, then rebuild. These fields declare a contract; they do not prove the model follows it.
