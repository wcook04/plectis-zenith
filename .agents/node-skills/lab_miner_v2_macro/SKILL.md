---
name: lab-miner-v2-macro
description: Apply the typed lab_miner_v2_macro operation to its declared context.
---
# lab_miner_v2_macro

- Input ports: `lab_decide`, `global_macro_feed`.
- Output contract: `text`. Mission: `lab`.
- Implementation: `codex/substrate/nodes/lab/miner_v2_macro.json`; shared contracts compile at dispatch.
- Parameters: frozen skill rule, incoming-edge weights, context budget.
- Version: `b578250aaf9b50f550dc19f68ab7e06a297f39a46604719e1399406da3476f79`.
- Inspect: `python -m zenith inspect lab_miner_v2_macro`.

Generated projection; edit the source or a frozen experimental variant, then rebuild. These fields declare a contract; they do not prove the model follows it.
