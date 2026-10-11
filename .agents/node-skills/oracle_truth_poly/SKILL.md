---
name: oracle-truth-poly
description: Apply the typed oracle_truth_poly operation to its declared context.
---
# oracle_truth_poly

- Input ports: `oracle_subject_index`, `oracle_subject_poly_feed`, `global_polymarket_feed`.
- Output contract: `json`. Mission: `oracle`.
- Implementation: `codex/substrate/nodes/oracle/oracle_truth_poly.json`; shared contracts compile at dispatch.
- Parameters: frozen skill rule, incoming-edge weights, context budget.
- Version: `08da5ec13e10866a0d8cce0ba9c65f65747af0a890df9966f3dcb1e8eb723b54`.
- Inspect: `python -m zenith inspect oracle_truth_poly`.

Generated projection; edit the source or a frozen experimental variant, then rebuild. These fields declare a contract; they do not prove the model follows it.
