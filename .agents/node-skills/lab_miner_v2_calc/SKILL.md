---
name: lab-miner-v2-calc
description: Apply the typed lab_miner_v2_calc operation to its declared context.
---
# lab_miner_v2_calc

- Input ports: `lab_decide`, `global_calculator_feed`.
- Output contract: `text`. Mission: `lab`.
- Implementation: `codex/substrate/nodes/lab/miner_v2_calc.json`; shared contracts compile at dispatch.
- Parameters: frozen skill rule, incoming-edge weights, context budget.
- Version: `7366da798320105885c92ef897346d38d5978c72b9a3dad3b2f6d12d68e1d612`.
- Inspect: `python -m zenith inspect lab_miner_v2_calc`.

Generated projection; edit the source or a frozen experimental variant, then rebuild. These fields declare a contract; they do not prove the model follows it.
