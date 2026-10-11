---
name: lab-miner-macro
description: Apply the typed lab_miner_macro operation to its declared context.
---
# lab_miner_macro

- Input ports: `global_macro_feed`, `lab_seed_state`.
- Output contract: `text`. Mission: `lab`.
- Implementation: `codex/substrate/nodes/lab/miner_macro.json`; shared contracts compile at dispatch.
- Parameters: frozen skill rule, incoming-edge weights, context budget.
- Version: `95838200edb346f0d6f1e300a6fbf6e400a7cc55a13d8d8e769a3fc55417e8cb`.
- Inspect: `python -m zenith inspect lab_miner_macro`.

Generated projection; edit the source or a frozen experimental variant, then rebuild. These fields declare a contract; they do not prove the model follows it.
