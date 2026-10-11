---
name: lab-miner-news
description: Apply the typed lab_miner_news operation to its declared context.
---
# lab_miner_news

- Input ports: `global_news_feed`, `lab_seed_state`.
- Output contract: `text`. Mission: `lab`.
- Implementation: `codex/substrate/nodes/lab/miner_news.json`; shared contracts compile at dispatch.
- Parameters: frozen skill rule, incoming-edge weights, context budget.
- Version: `4c6c21eb5be9ab23d2184358c34ae76e1909742adb32081bbfde3da88359c97f`.
- Inspect: `python -m zenith inspect lab_miner_news`.

Generated projection; edit the source or a frozen experimental variant, then rebuild. These fields declare a contract; they do not prove the model follows it.
