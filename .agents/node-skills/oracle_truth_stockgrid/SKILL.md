---
name: oracle-truth-stockgrid
description: Apply the typed oracle_truth_stockgrid operation to its declared context.
---
# oracle_truth_stockgrid

- Input ports: `oracle_subject_index`, `oracle_subject_stockgrid_feed`, `global_stockgrid_feed`.
- Output contract: `json`. Mission: `oracle`.
- Implementation: `codex/substrate/nodes/oracle/oracle_truth_stockgrid.json`; shared contracts compile at dispatch.
- Parameters: frozen skill rule, incoming-edge weights, context budget.
- Version: `ccedd7754fbdb4269d391b408d6b78db8756800e78e466b3ebde3b6e5899e592`.
- Inspect: `python -m zenith inspect oracle_truth_stockgrid`.

Generated projection; edit the source or a frozen experimental variant, then rebuild. These fields declare a contract; they do not prove the model follows it.
