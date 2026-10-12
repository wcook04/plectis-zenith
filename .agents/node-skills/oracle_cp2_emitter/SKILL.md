---
name: oracle-cp2-emitter
description: Apply the typed oracle_cp2_emitter operation to its declared context.
---
# oracle_cp2_emitter

- Input ports: `oracle_subject_index`, `oracle_truth_map`, `oracle_attribution_map`, `oracle_explain`.
- Output contract: `isomorphic_cp2`. Mission: `oracle`.
- Implementation: `codex/substrate/nodes/oracle/oracle_cp2_emitter.json`; shared contracts compile at dispatch.
- Parameters: frozen skill rule, incoming-edge weights, context budget.
- Version: `1d287e11ef59f80a9454d431e8de86019a05fcebe363232162b86db07d315db9`.
- Inspect: `python -m zenith inspect oracle_cp2_emitter`.

Generated projection; edit the source or a frozen experimental variant, then rebuild. These fields declare a contract; they do not prove the model follows it.
