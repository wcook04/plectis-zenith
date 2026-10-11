"""
[PURPOSE]
- Teleology: Mark the Stock package as the market-intelligence entrypoint for the stock physics tool.
- Mechanism: Keep the package surface minimal and route readers to the concrete module that owns fetch and envelope behavior.

[INTERFACE]
- Exports: None from the package root; the executable surface lives in `tools/stock/stock.py`.
- Outputs: None.

[FLOW]
- Importers land on the package root.
- Readers escalate to the concrete module for fetch logic, metric computation, and the tool envelope.

[DEPENDENCIES]
- None.

[CONSTRAINTS]
- Non-goal: This package root does not re-export `run` or `StandardActor`; it is a routing stub only.
- When-needed: Open when a caller lands on the package root and needs the next concrete stock market-intelligence surface.
- Escalates-to: tools/stock/stock.py::run
- Navigation-group: market_intelligence
"""
