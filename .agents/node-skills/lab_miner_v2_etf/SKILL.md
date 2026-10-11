---
name: lab-miner-v2-etf
description: Apply the typed lab_miner_v2_etf operation to its declared context.
---
# lab_miner_v2_etf

- Input ports: `lab_decide`, `global_etf_feed`.
- Output contract: `text`. Mission: `lab`.
- Implementation: `codex/substrate/nodes/lab/miner_v2_etf.json`; shared contracts compile at dispatch.
- Parameters: frozen skill rule, incoming-edge weights, context budget.
- Version: `b9d45dd60b0de0a88ee467501e749042d33f2e2dd0306ead0166ad83bdf3008a`.
- Inspect: `python -m zenith inspect lab_miner_v2_etf`.

Generated projection; edit the source or a frozen experimental variant, then rebuild. These fields declare a contract; they do not prove the model follows it.
