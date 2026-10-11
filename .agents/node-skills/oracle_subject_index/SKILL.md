---
name: oracle-subject-index
description: Apply the typed oracle_subject_index operation to its declared context.
---
# oracle_subject_index

- Input ports: `oracle_subject_lab_decide`, `oracle_subject_lab_director`, `oracle_subject_lab_cross_corr_v2`, `oracle_subject_stock_feed`, `oracle_subject_etf_feed`.
- Output contract: `text`. Mission: `oracle`.
- Implementation: `codex/substrate/nodes/oracle/oracle_subject_index.json`; shared contracts compile at dispatch.
- Parameters: frozen skill rule, incoming-edge weights, context budget.
- Version: `828a6d50e9ff6461d701cbe31d037cc4904fc9be2d40cb862031508882079b30`.
- Inspect: `python -m zenith inspect oracle_subject_index`.

Generated projection; edit the source or a frozen experimental variant, then rebuild. These fields declare a contract; they do not prove the model follows it.
