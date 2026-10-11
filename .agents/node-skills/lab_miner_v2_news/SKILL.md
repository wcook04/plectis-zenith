---
name: lab-miner-v2-news
description: Apply the typed lab_miner_v2_news operation to its declared context.
---
# lab_miner_v2_news

- Input ports: `lab_decide`, `global_news_feed`.
- Output contract: `text`. Mission: `lab`.
- Implementation: `codex/substrate/nodes/lab/miner_v2_news.json`; shared contracts compile at dispatch.
- Parameters: frozen skill rule, incoming-edge weights, context budget.
- Version: `81c71d5a5211bbc7ab97d916f21be6d7e69299f4c1513dffe879f8b4eae97f8f`.
- Inspect: `python -m zenith inspect lab_miner_v2_news`.

Generated projection; edit the source or a frozen experimental variant, then rebuild. These fields declare a contract; they do not prove the model follows it.
