"""
[PURPOSE]
- Teleology: Mark `tools.news` as the package entry surface for the Telegram-backed news lane.
- Mechanism: Keep package-level routing minimal and point readers to the executable ingestion and auth surfaces.

[INTERFACE]
- Exports: None.
- Non-goal: This package marker does not perform Telegram auth or message fetches.

[FLOW]
- When-needed: Open when `tools.news` is the first located package hit and you need the concrete ingestion or auth module for market-intelligence news work.
- Escalates-to: tools/news/news.py::run; tools/news/auth_telegram.py::run_auth

[DEPENDENCIES]
- tools.news.news: canonical Telegram ingestion runtime.
- tools.news.auth_telegram: interactive session bootstrap helper.

[CONSTRAINTS]
- Guarantee: Importing this package marker has no side effects because it only supplies routing context.
- Navigation-group: market_intelligence
"""
