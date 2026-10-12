---
name: lab-miner-v2-etf
description: Apply the typed lab_miner_v2_etf operation to its declared context.
---
# lab_miner_v2_etf

- Input ports: `lab_decide`, `global_etf_feed`.
- Output contract: `text`. Mission: `lab`.
- Implementation: `codex/substrate/nodes/lab/miner_v2_etf.json`; shared contracts compile at dispatch.
- Parameters: frozen skill rule, incoming-edge weights, context budget.
- Version: `c9b7b745a4471f3a3b9eb4ea87517a90a0c84a2e3c567190e1c6e32cc5af31ad`.
- Inspect: `python -m zenith inspect lab_miner_v2_etf`.

Generated projection; edit the source or a frozen experimental variant, then rebuild. These fields declare a contract; they do not prove the model follows it.
