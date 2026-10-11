---
name: lab-orient
description: Apply the typed lab_orient operation to its declared context.
---
# lab_orient

- Input ports: `lab_miner_stock`, `lab_miner_etf`, `lab_miner_macro`, `lab_miner_news`, `lab_miner_poly`, `lab_miner_calc`, `lab_miner_stockgrid`, `lab_cross_corr_v1`.
- Output contract: `text`. Mission: `lab`.
- Implementation: `codex/substrate/nodes/lab/orient.json`; shared contracts compile at dispatch.
- Parameters: frozen skill rule, incoming-edge weights, context budget.
- Version: `0f4ac900248878ed4c71f49260f223fb9f2fa8604d02a664aa758a78917ed19e`.
- Inspect: `python -m zenith inspect lab_orient`.

Generated projection; edit the source or a frozen experimental variant, then rebuild. These fields declare a contract; they do not prove the model follows it.
