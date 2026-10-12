---
name: lab-miner-v2-calc
description: Apply the typed lab_miner_v2_calc operation to its declared context.
---
# lab_miner_v2_calc

- Input ports: `lab_decide`, `global_calculator_feed`.
- Output contract: `text`. Mission: `lab`.
- Implementation: `codex/substrate/nodes/lab/miner_v2_calc.json`; shared contracts compile at dispatch.
- Parameters: frozen skill rule, incoming-edge weights, context budget.
- Version: `6d1367a8fa92c467a73c8575faad51f81bcf2b5e7c86edd72f814da434434f1e`.
- Inspect: `python -m zenith inspect lab_miner_v2_calc`.

Generated projection; edit the source or a frozen experimental variant, then rebuild. These fields declare a contract; they do not prove the model follows it.
