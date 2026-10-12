---
name: lab-director
description: Apply the typed lab_director operation to its declared context.
---
# lab_director

- Input ports: `lab_decide`, `lab_miner_v2_stock`, `lab_miner_v2_etf`, `lab_miner_v2_macro`, `lab_miner_v2_news`, `lab_miner_v2_poly`, `lab_miner_v2_calc`, `lab_miner_v2_stockgrid`, `lab_cross_corr_v2`.
- Output contract: `isomorphic_cp2`. Mission: `lab`.
- Implementation: `codex/substrate/nodes/lab/director.json`; shared contracts compile at dispatch.
- Parameters: frozen skill rule, incoming-edge weights, context budget.
- Version: `bb5fdbdfe5bb2beea98a8f3799498f09f3d894fb83a32f86677e72f0cf28848d`.
- Inspect: `python -m zenith inspect lab_director`.

Generated projection; edit the source or a frozen experimental variant, then rebuild. These fields declare a contract; they do not prove the model follows it.
