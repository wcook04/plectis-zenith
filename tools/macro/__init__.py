"""
[PURPOSE]
- Teleology: Mark `tools.macro` as the package entry surface for the repo's FRED-backed macro lane.
- Mechanism: Keep package-level routing lightweight and defer executable behavior to `tools/macro/macro.py`.

[INTERFACE]
- Exports: None.
- Non-goal: This package marker does not implement macro fetching or cache logic.

[FLOW]
- When-needed: Open when `tools.macro` is the first located package hit and you need the concrete module that owns the market-intelligence macro feed.
- Escalates-to: tools/macro/macro.py::run

[DEPENDENCIES]
- tools.macro.macro: canonical macro runtime and entrypoint.

[CONSTRAINTS]
- Guarantee: Importing this package marker has no side effects because it only supplies routing context.
- Navigation-group: market_intelligence
"""
