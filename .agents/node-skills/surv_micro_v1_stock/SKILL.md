---
name: surv-micro-v1-stock
description: Apply the typed surv_micro_v1_stock operation to its declared context.
---
# surv_micro_v1_stock

- Input ports: `global_stock_feed`.
- Output contract: `text`. Mission: `surveillance`.
- Implementation: `codex/substrate/nodes/surveillance/micro_v1_stock.json`; shared contracts compile at dispatch.
- Parameters: frozen skill rule, incoming-edge weights, context budget.
- Version: `4deb17e3f65cb998d35159c7bc5e5ee817f7a627e335121b6b828ebb7c516a72`.
- Inspect: `python -m zenith inspect surv_micro_v1_stock`.

Generated projection; edit the source or a frozen experimental variant, then rebuild. These fields declare a contract; they do not prove the model follows it.
