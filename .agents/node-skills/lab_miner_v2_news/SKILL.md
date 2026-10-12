---
name: lab-miner-v2-news
description: Apply the typed lab_miner_v2_news operation to its declared context.
---
# lab_miner_v2_news

- Input ports: `lab_decide`, `global_news_feed`.
- Output contract: `text`. Mission: `lab`.
- Implementation: `codex/substrate/nodes/lab/miner_v2_news.json`; shared contracts compile at dispatch.
- Parameters: frozen skill rule, incoming-edge weights, context budget.
- Version: `508b43226c089e5fc753de60af258107a64bc7809e7fc7b6caa691aad6f5d262`.
- Inspect: `python -m zenith inspect lab_miner_v2_news`.

Generated projection; edit the source or a frozen experimental variant, then rebuild. These fields declare a contract; they do not prove the model follows it.
