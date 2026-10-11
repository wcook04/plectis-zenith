---
name: surv-micro-v2-news
description: Apply the typed surv_micro_v2_news operation to its declared context.
---
# surv_micro_v2_news

- Input ports: `global_news_feed`, `surv_micro_v1_news`, `surv_macro_v1_context_search`.
- Output contract: `text`. Mission: `surveillance`.
- Implementation: `codex/substrate/nodes/surveillance/micro_v2_news.json`; shared contracts compile at dispatch.
- Parameters: frozen skill rule, incoming-edge weights, context budget.
- Version: `38fcf3ba9689e6edb3dc14cad410ce02545dd10257e90b4468a6a76bfa0ff560`.
- Inspect: `python -m zenith inspect surv_micro_v2_news`.

Generated projection; edit the source or a frozen experimental variant, then rebuild. These fields declare a contract; they do not prove the model follows it.
