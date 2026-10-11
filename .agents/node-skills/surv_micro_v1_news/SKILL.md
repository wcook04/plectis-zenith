---
name: surv-micro-v1-news
description: Apply the typed surv_micro_v1_news operation to its declared context.
---
# surv_micro_v1_news

- Input ports: `global_news_feed`.
- Output contract: `text`. Mission: `surveillance`.
- Implementation: `codex/substrate/nodes/surveillance/micro_v1_news.json`; shared contracts compile at dispatch.
- Parameters: frozen skill rule, incoming-edge weights, context budget.
- Version: `0d6642d6e233cb23cb8ef0d1838bd1d2cdff1a39b3c7e36f596d0a522e0c268f`.
- Inspect: `python -m zenith inspect surv_micro_v1_news`.

Generated projection; edit the source or a frozen experimental variant, then rebuild. These fields declare a contract; they do not prove the model follows it.
