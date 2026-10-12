---
name: oracle-explain
description: Apply the typed oracle_explain operation to its declared context.
---
# oracle_explain

- Input ports: `oracle_attribution_map`.
- Output contract: `json`. Mission: `oracle`.
- Implementation: `codex/substrate/nodes/oracle/oracle_explain.json`; shared contracts compile at dispatch.
- Parameters: frozen skill rule, incoming-edge weights, context budget.
- Version: `ad7e7072b231d190ca7533add24ba4c14df2152ac090a8c3a7126488d2325d8f`.
- Inspect: `python -m zenith inspect oracle_explain`.

Generated projection; edit the source or a frozen experimental variant, then rebuild. These fields declare a contract; they do not prove the model follows it.
