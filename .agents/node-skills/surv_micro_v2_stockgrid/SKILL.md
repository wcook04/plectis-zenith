---
name: surv-micro-v2-stockgrid
description: Apply the typed surv_micro_v2_stockgrid operation to its declared context.
---
# surv_micro_v2_stockgrid

- Input ports: `global_stockgrid_feed`, `surv_micro_v1_stockgrid`, `surv_macro_v1_context_search`.
- Output contract: `text`. Mission: `surveillance`.
- Implementation: `codex/substrate/nodes/surveillance/micro_v2_stockgrid.json`; shared contracts compile at dispatch.
- Parameters: frozen skill rule, incoming-edge weights, context budget.
- Version: `707f7ff0f5a6359ba4fb2369292e4aa855796b42736bff85ce3f6b96ee7be1e0`.
- Inspect: `python -m zenith inspect surv_micro_v2_stockgrid`.

Generated projection; edit the source or a frozen experimental variant, then rebuild. These fields declare a contract; they do not prove the model follows it.
