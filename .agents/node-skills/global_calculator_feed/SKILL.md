---
name: global-calculator-feed
description: Apply the typed global_calculator_feed operation to its declared context.
---
# global_calculator_feed

- Input ports: `global_stock_feed`, `global_macro_feed`, `global_etf_feed`.
- Output contract: `text`. Mission: `feeds`.
- Implementation: `codex/substrate/nodes/feeds/global_calculator_feed.json`; shared contracts compile at dispatch.
- Parameters: frozen skill rule, incoming-edge weights, context budget.
- Version: `a336f1e34beaf7d4ffc9b3255f1785c7c8c082871068cdb3811dd72c0cd08340`.
- Inspect: `python -m zenith inspect global_calculator_feed`.

Generated projection; edit the source or a frozen experimental variant, then rebuild. These fields declare a contract; they do not prove the model follows it.
