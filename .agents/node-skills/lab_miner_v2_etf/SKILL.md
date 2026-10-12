---
name: lab-miner-v2-etf
description: Apply the typed lab_miner_v2_etf operation to its declared context.
---
# lab_miner_v2_etf

- Input ports: `lab_decide`, `global_etf_feed`.
- Output contract: `text`. Mission: `lab`.
- Implementation: `codex/substrate/nodes/lab/miner_v2_etf.json`; shared contracts compile at dispatch.
- Parameters: frozen skill rule, incoming-edge weights, context budget.
- Version: `7747fe830c4719c4f282b7be6b7ec01b6e1224af24d148ce0c40171b60bd0724`.
- Inspect: `python -m zenith inspect lab_miner_v2_etf`.

Generated projection; edit the source or a frozen experimental variant, then rebuild. These fields declare a contract; they do not prove the model follows it.
