---
name: surv-final-report-author
description: Apply the typed surv_final_report_author operation to its declared context.
---
# surv_final_report_author

- Input ports: `surv_macro_v2_structure`, `surv_micro_v1_stock`, `surv_micro_v1_macro`, `surv_micro_v1_news`, `surv_micro_v1_poly`, `surv_micro_v1_calc`, `surv_micro_v2_stock`, `surv_micro_v2_macro`, `surv_micro_v2_news`, `surv_micro_v2_poly`, `surv_micro_v2_calc`, `surv_micro_v1_stockgrid`, `surv_micro_v2_stockgrid`.
- Output contract: `text`. Mission: `surveillance`.
- Implementation: `codex/substrate/nodes/surveillance/final_report_author.json`; shared contracts compile at dispatch.
- Parameters: frozen skill rule, incoming-edge weights, context budget.
- Version: `0e1a5a8763defb7f5f404331c0edb1d1ca01e2474d809ca0a126f97980811c9e`.
- Inspect: `python -m zenith inspect surv_final_report_author`.

Generated projection; edit the source or a frozen experimental variant, then rebuild. These fields declare a contract; they do not prove the model follows it.
