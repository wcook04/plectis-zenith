---
name: delta-analyzer
description: Apply the typed delta_analyzer operation to its declared context.
---
# delta_analyzer

- Input ports: none.
- Output contract: `text`. Mission: `refinement`.
- Implementation: `codex/substrate/nodes/refinement/delta_analyzer.json`; shared contracts compile at dispatch.
- Parameters: frozen skill rule, incoming-edge weights, context budget.
- Version: `344167382c4e2651de2442c4071972e3a0ebae328ed1f8590f7d438137cfc6f6`.
- Inspect: `python -m zenith inspect delta_analyzer`.

Generated projection; edit the source or a frozen experimental variant, then rebuild. These fields declare a contract; they do not prove the model follows it.
