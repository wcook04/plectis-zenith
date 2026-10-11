---
name: lab-miner-stockgrid
description: Apply the typed lab_miner_stockgrid operation to its declared context.
---
# lab_miner_stockgrid

- Input ports: `global_stockgrid_feed`, `lab_seed_state`.
- Output contract: `text`. Mission: `lab`.
- Implementation: `codex/substrate/nodes/lab/miner_stockgrid.json`; shared contracts compile at dispatch.
- Parameters: frozen skill rule, incoming-edge weights, context budget.
- Version: `f17ffcfa870ccb0064569c8a75f9e3247758c1ce4181602ed905478f93e9139c`.
- Inspect: `python -m zenith inspect lab_miner_stockgrid`.

Generated projection; edit the source or a frozen experimental variant, then rebuild. These fields declare a contract; they do not prove the model follows it.
