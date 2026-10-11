---
name: surv-micro-v1-stockgrid
description: Apply the typed surv_micro_v1_stockgrid operation to its declared context.
---
# surv_micro_v1_stockgrid

- Input ports: `global_stockgrid_feed`.
- Output contract: `text`. Mission: `surveillance`.
- Implementation: `codex/substrate/nodes/surveillance/micro_v1_stockgrid.json`; shared contracts compile at dispatch.
- Parameters: frozen skill rule, incoming-edge weights, context budget.
- Version: `63719c325d53711c8c025eab05c528c351e3a5a77fc540e17233f7a254648219`.
- Inspect: `python -m zenith inspect surv_micro_v1_stockgrid`.

Generated projection; edit the source or a frozen experimental variant, then rebuild. These fields declare a contract; they do not prove the model follows it.
