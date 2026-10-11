---
name: lab-seed-state
description: Apply the typed lab_seed_state operation to its declared context.
---
# lab_seed_state

- Input ports: `global_stock_feed`, `global_etf_feed`, `global_macro_feed`, `global_news_feed`, `global_polymarket_feed`, `global_calculator_feed`, `global_stockgrid_feed`.
- Output contract: `text`. Mission: `lab`.
- Implementation: `codex/substrate/nodes/lab/seed_state.json`; shared contracts compile at dispatch.
- Parameters: frozen skill rule, incoming-edge weights, context budget.
- Version: `c9ce8f5918efc5ef5979478428a6def6fe9844af7899d118baf372ad3567b4c9`.
- Inspect: `python -m zenith inspect lab_seed_state`.

Generated projection; edit the source or a frozen experimental variant, then rebuild. These fields declare a contract; they do not prove the model follows it.
