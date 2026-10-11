---
name: lab-director
description: Apply the typed lab_director operation to its declared context.
---
# lab_director

- Input ports: `lab_decide`, `lab_miner_v2_stock`, `lab_miner_v2_etf`, `lab_miner_v2_macro`, `lab_miner_v2_news`, `lab_miner_v2_poly`, `lab_miner_v2_calc`, `lab_miner_v2_stockgrid`, `lab_cross_corr_v2`.
- Output contract: `isomorphic_cp2`. Mission: `lab`.
- Implementation: `codex/substrate/nodes/lab/director.json`; shared contracts compile at dispatch.
- Parameters: frozen skill rule, incoming-edge weights, context budget.
- Version: `77c45561c759de3b80e24219163fb464d811b018f181c418b584f5190e853b23`.
- Inspect: `python -m zenith inspect lab_director`.

Generated projection; edit the source or a frozen experimental variant, then rebuild. These fields declare a contract; they do not prove the model follows it.
