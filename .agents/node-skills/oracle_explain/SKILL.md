---
name: oracle-explain
description: Apply the typed oracle_explain operation to its declared context.
---
# oracle_explain

- Input ports: `oracle_attribution_map`.
- Output contract: `json`. Mission: `oracle`.
- Implementation: `codex/substrate/nodes/oracle/oracle_explain.json`; shared contracts compile at dispatch.
- Parameters: frozen skill rule, incoming-edge weights, context budget.
- Version: `0ec8c3a9be69cbe6c96bbf533ac8e8ac6eb5ce1b1efc0cbcc4caa254ec50222a`.
- Inspect: `python -m zenith inspect oracle_explain`.

Generated projection; edit the source or a frozen experimental variant, then rebuild. These fields declare a contract; they do not prove the model follows it.
