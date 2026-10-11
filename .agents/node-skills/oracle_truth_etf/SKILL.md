---
name: oracle-truth-etf
description: Apply the typed oracle_truth_etf operation to its declared context.
---
# oracle_truth_etf

- Input ports: `oracle_subject_index`, `oracle_truth_diff_equity`, `oracle_subject_etf_feed`, `global_etf_feed`.
- Output contract: `json`. Mission: `oracle`.
- Implementation: `codex/substrate/nodes/oracle/oracle_truth_etf.json`; shared contracts compile at dispatch.
- Parameters: frozen skill rule, incoming-edge weights, context budget.
- Version: `c9fd46eba7bce272e25cf1d10e253763d685a2596e38cbae2c3b9240317eabce`.
- Inspect: `python -m zenith inspect oracle_truth_etf`.

Generated projection; edit the source or a frozen experimental variant, then rebuild. These fields declare a contract; they do not prove the model follows it.
