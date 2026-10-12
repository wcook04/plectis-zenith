---
name: lab-miner-v2-stock
description: Apply the typed lab_miner_v2_stock operation to its declared context.
---
# lab_miner_v2_stock

- Input ports: `lab_decide`, `global_stock_feed`.
- Output contract: `text`. Mission: `lab`.
- Implementation: `codex/substrate/nodes/lab/miner_v2_stock.json`; shared contracts compile at dispatch.
- Parameters: frozen skill rule, incoming-edge weights, context budget.
- Version: `c66f41dd290af52d2189d247aa9a7577aa45c3ad64a2644b075d21d869b778f2`.
- Inspect: `python -m zenith inspect lab_miner_v2_stock`.

Generated projection; edit the source or a frozen experimental variant, then rebuild. These fields declare a contract; they do not prove the model follows it.
