---
name: global-news-feed
description: Apply the typed global_news_feed operation to its declared context.
---
# global_news_feed

- Input ports: none.
- Output contract: `text`. Mission: `feeds`.
- Implementation: `codex/substrate/nodes/feeds/global_news_feed.json`; shared contracts compile at dispatch.
- Parameters: frozen skill rule, incoming-edge weights, context budget.
- Version: `380b9c44926456eaa203251f5ec9bd39cff4c8ecad1d1f4021821019fa97c4bf`.
- Inspect: `python -m zenith inspect global_news_feed`.

Generated projection; edit the source or a frozen experimental variant, then rebuild. These fields declare a contract; they do not prove the model follows it.
