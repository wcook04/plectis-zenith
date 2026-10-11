---
name: surv-macro-v2-structure
description: Apply the typed surv_macro_v2_structure operation to its declared context.
---
# surv_macro_v2_structure

- Input ports: `surv_macro_v1_context_search`, `surv_micro_v2_stock`, `surv_micro_v2_macro`, `surv_micro_v2_news`, `surv_micro_v2_poly`, `surv_micro_v2_calc`, `surv_micro_v2_stockgrid`.
- Output contract: `text`. Mission: `surveillance`.
- Implementation: `codex/substrate/nodes/surveillance/macro_v2_structure.json`; shared contracts compile at dispatch.
- Parameters: frozen skill rule, incoming-edge weights, context budget.
- Version: `cfd4bec5728b662c0a60fa9ea04b2a62ed508d90c13bb6fca5a401233c4eac75`.
- Inspect: `python -m zenith inspect surv_macro_v2_structure`.

Generated projection; edit the source or a frozen experimental variant, then rebuild. These fields declare a contract; they do not prove the model follows it.
