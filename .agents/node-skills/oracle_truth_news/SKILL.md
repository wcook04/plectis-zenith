---
name: oracle-truth-news
description: Apply the typed oracle_truth_news operation to its declared context.
---
# oracle_truth_news

- Input ports: `oracle_subject_index`, `oracle_subject_news_feed`, `global_news_feed`.
- Output contract: `json`. Mission: `oracle`.
- Implementation: `codex/substrate/nodes/oracle/oracle_truth_news.json`; shared contracts compile at dispatch.
- Parameters: frozen skill rule, incoming-edge weights, context budget.
- Version: `3475eac55c2fa986d1b2cee425afb94baa4c4b64d21816b1fc326e487b3edf95`.
- Inspect: `python -m zenith inspect oracle_truth_news`.

Generated projection; edit the source or a frozen experimental variant, then rebuild. These fields declare a contract; they do not prove the model follows it.
