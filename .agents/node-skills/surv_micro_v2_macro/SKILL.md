---
name: surv-micro-v2-macro
description: Apply the typed surv_micro_v2_macro operation to its declared context.
---
# surv_micro_v2_macro

- Input ports: `global_macro_feed`, `surv_micro_v1_macro`, `surv_macro_v1_context_search`.
- Output contract: `text`. Mission: `surveillance`.
- Implementation: `codex/substrate/nodes/surveillance/micro_v2_macro.json`; shared contracts compile at dispatch.
- Parameters: frozen skill rule, incoming-edge weights, context budget.
- Version: `95ce05de7621d1fab4297b83122ed72ef4744d1a499bfff294945376fc10b410`.
- Inspect: `python -m zenith inspect surv_micro_v2_macro`.

Generated projection; edit the source or a frozen experimental variant, then rebuild. These fields declare a contract; they do not prove the model follows it.
