---
name: surv-micro-v2-calc
description: Apply the typed surv_micro_v2_calc operation to its declared context.
---
# surv_micro_v2_calc

- Input ports: `global_calculator_feed`, `surv_micro_v1_calc`, `surv_macro_v1_context_search`.
- Output contract: `text`. Mission: `surveillance`.
- Implementation: `codex/substrate/nodes/surveillance/micro_v2_calc.json`; shared contracts compile at dispatch.
- Parameters: frozen skill rule, incoming-edge weights, context budget.
- Version: `5075e6a00bca3c9c7f80fdf89104ecaeef5e7aeaefe4c91b9e03c386ccfa5d6e`.
- Inspect: `python -m zenith inspect surv_micro_v2_calc`.

Generated projection; edit the source or a frozen experimental variant, then rebuild. These fields declare a contract; they do not prove the model follows it.
