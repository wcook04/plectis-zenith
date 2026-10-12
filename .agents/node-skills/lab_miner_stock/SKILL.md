---
name: lab-miner-stock
description: Apply the typed lab_miner_stock operation to its declared context.
---
# lab_miner_stock

- Input ports: `global_stock_feed`, `lab_seed_state`.
- Output contract: `text`. Mission: `lab`.
- Implementation: `codex/substrate/nodes/lab/miner_stock.json`; shared contracts compile at dispatch.
- Parameters: frozen skill rule, incoming-edge weights, context budget.
- Version: `24ef8d3ee15cae7a079948a1098e6837ef870eb5e42e0200a4dee08e2f3a8090`.
- Inspect: `python -m zenith inspect lab_miner_stock`.

Generated projection; edit the source or a frozen experimental variant, then rebuild. These fields declare a contract; they do not prove the model follows it.
