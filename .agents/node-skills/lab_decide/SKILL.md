---
name: lab-decide
description: Apply the typed lab_decide operation to its declared context.
---
# lab_decide

- Input ports: `lab_miner_stock`, `lab_miner_etf`, `lab_miner_macro`, `lab_miner_news`, `lab_miner_poly`, `lab_miner_calc`, `lab_miner_stockgrid`, `lab_cross_corr_v1`, `lab_orient`.
- Output contract: `isomorphic_cp1`. Mission: `lab`.
- Implementation: `codex/substrate/nodes/lab/decide.json`; shared contracts compile at dispatch.
- Parameters: frozen skill rule, incoming-edge weights, context budget.
- Version: `3063f319885c662bc77a916af2a84b4a2222eec02c08d90a78c319a6f976bd8e`.
- Inspect: `python -m zenith inspect lab_decide`.

Generated projection; edit the source or a frozen experimental variant, then rebuild. These fields declare a contract; they do not prove the model follows it.
