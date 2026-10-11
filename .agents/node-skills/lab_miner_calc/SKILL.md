---
name: lab-miner-calc
description: Apply the typed lab_miner_calc operation to its declared context.
---
# lab_miner_calc

- Input ports: `global_calculator_feed`, `lab_seed_state`.
- Output contract: `text`. Mission: `lab`.
- Implementation: `codex/substrate/nodes/lab/miner_calc.json`; shared contracts compile at dispatch.
- Parameters: frozen skill rule, incoming-edge weights, context budget.
- Version: `55136052e877dc3704f05efbaaf3f2d9166d98c19ab9d69f34158516fb77ea45`.
- Inspect: `python -m zenith inspect lab_miner_calc`.

Generated projection; edit the source or a frozen experimental variant, then rebuild. These fields declare a contract; they do not prove the model follows it.
