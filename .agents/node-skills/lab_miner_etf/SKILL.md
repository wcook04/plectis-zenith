---
name: lab-miner-etf
description: Apply the typed lab_miner_etf operation to its declared context.
---
# lab_miner_etf

- Input ports: `global_etf_feed`, `lab_seed_state`.
- Output contract: `text`. Mission: `lab`.
- Implementation: `codex/substrate/nodes/lab/miner_etf.json`; shared contracts compile at dispatch.
- Parameters: frozen skill rule, incoming-edge weights, context budget.
- Version: `15f38070b081791dd21cffd1bb8c2ecd6db208e79e528b13ae2907a832feeb88`.
- Inspect: `python -m zenith inspect lab_miner_etf`.

Generated projection; edit the source or a frozen experimental variant, then rebuild. These fields declare a contract; they do not prove the model follows it.
