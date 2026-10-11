---
name: oracle-attribution-map
description: Apply the typed oracle_attribution_map operation to its declared context.
---
# oracle_attribution_map

- Input ports: `oracle_subject_index`, `oracle_truth_map`, `oracle_truth_diff_equity`.
- Output contract: `schema_cp2_critique`. Mission: `oracle`.
- Implementation: `codex/substrate/nodes/oracle/oracle_attribution_map.json`; shared contracts compile at dispatch.
- Parameters: frozen skill rule, incoming-edge weights, context budget.
- Version: `30a478e35382f67704d238eb139bfdf44e31ad86b7499160748b1b3b101365d6`.
- Inspect: `python -m zenith inspect oracle_attribution_map`.

Generated projection; edit the source or a frozen experimental variant, then rebuild. These fields declare a contract; they do not prove the model follows it.
