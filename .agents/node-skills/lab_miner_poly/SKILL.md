---
name: lab-miner-poly
description: Apply the typed lab_miner_poly operation to its declared context.
---
# lab_miner_poly

- Input ports: `global_polymarket_feed`, `lab_seed_state`.
- Output contract: `text`. Mission: `lab`.
- Implementation: `codex/substrate/nodes/lab/miner_poly.json`; shared contracts compile at dispatch.
- Parameters: frozen skill rule, incoming-edge weights, context budget.
- Version: `a2dee388aff652da74fa5d08bca3356e9470db07fea0d68098c86e92820a2b71`.
- Inspect: `python -m zenith inspect lab_miner_poly`.

Generated projection; edit the source or a frozen experimental variant, then rebuild. These fields declare a contract; they do not prove the model follows it.
