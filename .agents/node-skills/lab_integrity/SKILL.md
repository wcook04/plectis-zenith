---
name: lab-integrity
description: Apply the typed lab_integrity operation to its declared context.
---
# lab_integrity

- Input ports: `lab_seed_state`, `lab_miner_stock`, `lab_miner_etf`, `lab_miner_macro`, `lab_miner_news`, `lab_miner_poly`, `lab_miner_calc`, `lab_miner_stockgrid`, `lab_cross_corr_v1`, `lab_orient`, `lab_decide`, `lab_miner_v2_stock`, `lab_miner_v2_etf`, `lab_miner_v2_macro`, `lab_miner_v2_news`, `lab_miner_v2_poly`, `lab_miner_v2_calc`, `lab_miner_v2_stockgrid`, `lab_cross_corr_v2`, `lab_director`.
- Output contract: `text`. Mission: `lab`.
- Implementation: `codex/substrate/nodes/lab/integrity.json`; shared contracts compile at dispatch.
- Parameters: frozen skill rule, incoming-edge weights, context budget.
- Version: `294db29c416a8858fc3d13759e5555fe73986ab60f87273326e9b58c9ada92cd`.
- Inspect: `python -m zenith inspect lab_integrity`.

Generated projection; edit the source or a frozen experimental variant, then rebuild. These fields declare a contract; they do not prove the model follows it.
