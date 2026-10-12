---
name: oracle-cp2-emitter
description: Apply the typed oracle_cp2_emitter operation to its declared context.
---
# oracle_cp2_emitter

- Input ports: `oracle_subject_index`, `oracle_truth_map`, `oracle_attribution_map`, `oracle_explain`.
- Output contract: `isomorphic_cp2`. Mission: `oracle`.
- Implementation: `codex/substrate/nodes/oracle/oracle_cp2_emitter.json`; shared contracts compile at dispatch.
- Parameters: frozen skill rule, incoming-edge weights, context budget.
- Version: `1dfece6ac4a17aae5abac420f6c38a94f4413a3297d17c30761d650e8fea217b`.
- Inspect: `python -m zenith inspect oracle_cp2_emitter`.

Generated projection; edit the source or a frozen experimental variant, then rebuild. These fields declare a contract; they do not prove the model follows it.
