---
name: surv-micro-v1-calc
description: Apply the typed surv_micro_v1_calc operation to its declared context.
---
# surv_micro_v1_calc

- Input ports: `global_calculator_feed`.
- Output contract: `text`. Mission: `surveillance`.
- Implementation: `codex/substrate/nodes/surveillance/micro_v1_calc.json`; shared contracts compile at dispatch.
- Parameters: frozen skill rule, incoming-edge weights, context budget.
- Version: `14390deaff1b43e3e3816895d68b57ba3d38ef4b7214b13b5c9f401859eb1018`.
- Inspect: `python -m zenith inspect surv_micro_v1_calc`.

Generated projection; edit the source or a frozen experimental variant, then rebuild. These fields declare a contract; they do not prove the model follows it.
