---
name: lab-miner-v2-stockgrid
description: Apply the typed lab_miner_v2_stockgrid operation to its declared context.
---
# lab_miner_v2_stockgrid

- Input ports: `lab_decide`, `global_stockgrid_feed`.
- Output contract: `text`. Mission: `lab`.
- Implementation: `codex/substrate/nodes/lab/miner_v2_stockgrid.json`; shared contracts compile at dispatch.
- Parameters: frozen skill rule, incoming-edge weights, context budget.
- Version: `2df8d291f662286d1af4c6311563ba67a131e2434a5939993b6eda8435762ddb`.
- Inspect: `python -m zenith inspect lab_miner_v2_stockgrid`.

Generated projection; edit the source or a frozen experimental variant, then rebuild. These fields declare a contract; they do not prove the model follows it.
