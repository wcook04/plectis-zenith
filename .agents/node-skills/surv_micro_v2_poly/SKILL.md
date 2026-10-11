---
name: surv-micro-v2-poly
description: Apply the typed surv_micro_v2_poly operation to its declared context.
---
# surv_micro_v2_poly

- Input ports: `global_polymarket_feed`, `surv_micro_v1_poly`, `surv_macro_v1_context_search`.
- Output contract: `text`. Mission: `surveillance`.
- Implementation: `codex/substrate/nodes/surveillance/micro_v2_poly.json`; shared contracts compile at dispatch.
- Parameters: frozen skill rule, incoming-edge weights, context budget.
- Version: `de40a258618e0e0173f65980c8be2681337cce7a23b3925c0b6dba1856d481a1`.
- Inspect: `python -m zenith inspect surv_micro_v2_poly`.

Generated projection; edit the source or a frozen experimental variant, then rebuild. These fields declare a contract; they do not prove the model follows it.
