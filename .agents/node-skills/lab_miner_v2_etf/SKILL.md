---
name: lab-miner-v2-etf
description: Apply the typed lab_miner_v2_etf operation to its declared context.
---
# lab_miner_v2_etf

- Input ports: `lab_decide`, `global_etf_feed`.
- Output contract: `text`. Mission: `lab`.
- Implementation: `codex/substrate/nodes/lab/miner_v2_etf.json`; shared contracts compile at dispatch.
- Parameters: frozen skill rule, incoming-edge weights, context budget.
- Version: `2cbcbd5b2a3b26e56070768ae47a0eeafccf079ee2f89a3c708c72ea25edb94d`.
- Inspect: `python -m zenith inspect lab_miner_v2_etf`.

Generated projection; edit the source or a frozen experimental variant, then rebuild. These fields declare a contract; they do not prove the model follows it.
