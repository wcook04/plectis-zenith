---
name: lab-miner-stock
description: Apply the typed lab_miner_stock operation to its declared context.
---
# lab_miner_stock

- Input ports: `global_stock_feed`, `lab_seed_state`.
- Output contract: `text`. Mission: `lab`.
- Implementation: `codex/substrate/nodes/lab/miner_stock.json`; shared contracts compile at dispatch.
- Parameters: frozen skill rule, incoming-edge weights, context budget.
- Version: `4c7b1e9069cf95740cf45f787e520e487c15ce11bc1d24569b0e531b325148e1`.
- Inspect: `python -m zenith inspect lab_miner_stock`.

Generated projection; edit the source or a frozen experimental variant, then rebuild. These fields declare a contract; they do not prove the model follows it.
