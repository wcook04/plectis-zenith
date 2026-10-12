---
name: lab-cross-corr-v2
description: Apply the typed lab_cross_corr_v2 operation to its declared context.
---
# lab_cross_corr_v2

- Input ports: `lab_miner_v2_stock`, `lab_miner_v2_etf`, `lab_miner_v2_macro`, `lab_miner_v2_news`, `lab_miner_v2_poly`, `lab_miner_v2_calc`, `lab_miner_v2_stockgrid`.
- Output contract: `json`. Mission: `lab`.
- Implementation: `codex/substrate/nodes/lab/cross_corr_v2.json`; shared contracts compile at dispatch.
- Parameters: frozen skill rule, incoming-edge weights, context budget.
- Version: `0875eea6df846ea36c12658a09cf84a2744da51be1540a753a09504d3bbf2f7e`.
- Inspect: `python -m zenith inspect lab_cross_corr_v2`.

Generated projection; edit the source or a frozen experimental variant, then rebuild. These fields declare a contract; they do not prove the model follows it.
