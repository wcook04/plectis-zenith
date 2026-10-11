---
name: lab-cross-corr-v1
description: Apply the typed lab_cross_corr_v1 operation to its declared context.
---
# lab_cross_corr_v1

- Input ports: `lab_miner_stock`, `lab_miner_etf`, `lab_miner_macro`, `lab_miner_news`, `lab_miner_poly`, `lab_miner_calc`, `lab_miner_stockgrid`.
- Output contract: `json`. Mission: `lab`.
- Implementation: `codex/substrate/nodes/lab/cross_corr_v1.json`; shared contracts compile at dispatch.
- Parameters: frozen skill rule, incoming-edge weights, context budget.
- Version: `1d8c5e252e5faa2b26ca4ebcb8ecbc78a9bfa7737bfaa5fee58f9909205a2925`.
- Inspect: `python -m zenith inspect lab_cross_corr_v1`.

Generated projection; edit the source or a frozen experimental variant, then rebuild. These fields declare a contract; they do not prove the model follows it.
