---
name: lab-miner-v2-macro
description: Apply the typed lab_miner_v2_macro operation to its declared context.
---
# lab_miner_v2_macro

- Input ports: `lab_decide`, `global_macro_feed`.
- Output contract: `text`. Mission: `lab`.
- Implementation: `codex/substrate/nodes/lab/miner_v2_macro.json`; shared contracts compile at dispatch.
- Parameters: frozen skill rule, incoming-edge weights, context budget.
- Version: `e5e3ee38a9d03333915aee429cfaac0fb65396443ff9f7bf405f33ce798cd6b7`.
- Inspect: `python -m zenith inspect lab_miner_v2_macro`.

Generated projection; edit the source or a frozen experimental variant, then rebuild. These fields declare a contract; they do not prove the model follows it.
