---
name: lab-miner-etf
description: Apply the typed lab_miner_etf operation to its declared context.
---
# lab_miner_etf

- Input ports: `global_etf_feed`, `lab_seed_state`.
- Output contract: `text`. Mission: `lab`.
- Implementation: `codex/substrate/nodes/lab/miner_etf.json`; shared contracts compile at dispatch.
- Parameters: frozen skill rule, incoming-edge weights, context budget.
- Version: `1faf59ab0dde6155390dc3fc6dfa08a845638ba568d6ad7451606ff519ed1c6f`.
- Inspect: `python -m zenith inspect lab_miner_etf`.

Generated projection; edit the source or a frozen experimental variant, then rebuild. These fields declare a contract; they do not prove the model follows it.
