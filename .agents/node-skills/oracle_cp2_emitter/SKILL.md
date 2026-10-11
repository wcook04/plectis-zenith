---
name: oracle-cp2-emitter
description: Apply the typed oracle_cp2_emitter operation to its declared context.
---
# oracle_cp2_emitter

- Input ports: `oracle_subject_index`, `oracle_truth_map`, `oracle_attribution_map`, `oracle_explain`.
- Output contract: `isomorphic_cp2`. Mission: `oracle`.
- Implementation: `codex/substrate/nodes/oracle/oracle_cp2_emitter.json`; shared contracts compile at dispatch.
- Parameters: frozen skill rule, incoming-edge weights, context budget.
- Version: `65ff36b06d54206c9ddccfcbc7efe1be086b1cc9e25762e4b7bc4a7c51db97cc`.
- Inspect: `python -m zenith inspect oracle_cp2_emitter`.

Generated projection; edit the source or a frozen experimental variant, then rebuild. These fields declare a contract; they do not prove the model follows it.
