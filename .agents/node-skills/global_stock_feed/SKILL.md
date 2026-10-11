---
name: global-stock-feed
description: Apply the typed global_stock_feed operation to its declared context.
---
# global_stock_feed

- Input ports: none.
- Output contract: `text`. Mission: `feeds`.
- Implementation: `codex/substrate/nodes/feeds/global_stock_feed.json`; shared contracts compile at dispatch.
- Parameters: frozen skill rule, incoming-edge weights, context budget.
- Version: `48dc106236a4547eee917ca065578c36c436b329d88a829b1368527b4000379d`.
- Inspect: `python -m zenith inspect global_stock_feed`.

Generated projection; edit the source or a frozen experimental variant, then rebuild. These fields declare a contract; they do not prove the model follows it.
