---
name: lab-miner-v2-stockgrid
description: Apply the typed lab_miner_v2_stockgrid operation to its declared context.
---
# lab_miner_v2_stockgrid

- Input ports: `lab_decide`, `global_stockgrid_feed`.
- Output contract: `text`. Mission: `lab`.
- Implementation: `codex/substrate/nodes/lab/miner_v2_stockgrid.json`; shared contracts compile at dispatch.
- Parameters: frozen skill rule, incoming-edge weights, context budget.
- Version: `89bbd402545963b9dc2555a31b07720dd359f450db3f29c9fe4fb05d7a81d48c`.
- Inspect: `python -m zenith inspect lab_miner_v2_stockgrid`.

Generated projection; edit the source or a frozen experimental variant, then rebuild. These fields declare a contract; they do not prove the model follows it.
