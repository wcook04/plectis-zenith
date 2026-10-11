---
name: surv-micro-v2-stock
description: Apply the typed surv_micro_v2_stock operation to its declared context.
---
# surv_micro_v2_stock

- Input ports: `global_stock_feed`, `surv_micro_v1_stock`, `surv_macro_v1_context_search`.
- Output contract: `text`. Mission: `surveillance`.
- Implementation: `codex/substrate/nodes/surveillance/micro_v2_stock.json`; shared contracts compile at dispatch.
- Parameters: frozen skill rule, incoming-edge weights, context budget.
- Version: `26b27b3d86083cfadf993ca7b81bf2fcfcd0c40aeda9472518eba43563a3428c`.
- Inspect: `python -m zenith inspect surv_micro_v2_stock`.

Generated projection; edit the source or a frozen experimental variant, then rebuild. These fields declare a contract; they do not prove the model follows it.
