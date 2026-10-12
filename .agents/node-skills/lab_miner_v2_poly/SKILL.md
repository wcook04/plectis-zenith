---
name: lab-miner-v2-poly
description: Apply the typed lab_miner_v2_poly operation to its declared context.
---
# lab_miner_v2_poly

- Input ports: `lab_decide`, `global_polymarket_feed`.
- Output contract: `text`. Mission: `lab`.
- Implementation: `codex/substrate/nodes/lab/miner_v2_poly.json`; shared contracts compile at dispatch.
- Parameters: frozen skill rule, incoming-edge weights, context budget.
- Version: `bd21cba38e75939f3a2c92f60058bd5af1554829fa6435cab2aebd987df27ad4`.
- Inspect: `python -m zenith inspect lab_miner_v2_poly`.

Generated projection; edit the source or a frozen experimental variant, then rebuild. These fields declare a contract; they do not prove the model follows it.
