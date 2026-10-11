---
name: lab-miner-v2-stockgrid
description: Apply the typed lab_miner_v2_stockgrid operation to its declared context.
---
# lab_miner_v2_stockgrid

- Input ports: `lab_decide`, `global_stockgrid_feed`.
- Output contract: `text`. Mission: `lab`.
- Implementation: `codex/substrate/nodes/lab/miner_v2_stockgrid.json`; shared contracts compile at dispatch.
- Parameters: frozen skill rule, incoming-edge weights, context budget.
- Version: `22a63b78c23093c3757946a6d90b78d05e15875e219244f5c9b11111b5199114`.
- Inspect: `python -m zenith inspect lab_miner_v2_stockgrid`.

Generated projection; edit the source or a frozen experimental variant, then rebuild. These fields declare a contract; they do not prove the model follows it.
