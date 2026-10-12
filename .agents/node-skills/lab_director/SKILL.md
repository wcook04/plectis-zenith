---
name: lab-director
description: Apply the typed lab_director operation to its declared context.
---
# lab_director

- Input ports: `lab_decide`, `lab_miner_v2_stock`, `lab_miner_v2_etf`, `lab_miner_v2_macro`, `lab_miner_v2_news`, `lab_miner_v2_poly`, `lab_miner_v2_calc`, `lab_miner_v2_stockgrid`, `lab_cross_corr_v2`.
- Output contract: `isomorphic_cp2`. Mission: `lab`.
- Implementation: `codex/substrate/nodes/lab/director.json`; shared contracts compile at dispatch.
- Parameters: frozen skill rule, incoming-edge weights, context budget.
- Version: `7f6046d562009d2c2600e654b0a9283d4e55300d54aa80a1dd8e0e132dc63418`.
- Inspect: `python -m zenith inspect lab_director`.

Generated projection; edit the source or a frozen experimental variant, then rebuild. These fields declare a contract; they do not prove the model follows it.
