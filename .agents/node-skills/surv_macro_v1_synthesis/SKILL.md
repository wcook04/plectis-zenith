---
name: surv-macro-v1-synthesis
description: Apply the typed surv_macro_v1_synthesis operation to its declared context.
---
# surv_macro_v1_synthesis

- Input ports: `surv_micro_v1_stock`, `surv_micro_v1_macro`, `surv_micro_v1_news`, `surv_micro_v1_poly`, `surv_micro_v1_calc`, `surv_micro_v1_stockgrid`.
- Output contract: `text`. Mission: `surveillance`.
- Implementation: `codex/substrate/nodes/surveillance/macro_v1_synthesis.json`; shared contracts compile at dispatch.
- Parameters: frozen skill rule, incoming-edge weights, context budget.
- Version: `14cf37beab96e8c02a2e97a75f5a5573c23abc0da4859f732ba22b1243f25171`.
- Inspect: `python -m zenith inspect surv_macro_v1_synthesis`.

Generated projection; edit the source or a frozen experimental variant, then rebuild. These fields declare a contract; they do not prove the model follows it.
