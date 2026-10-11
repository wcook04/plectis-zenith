---
id: "temporal_contract"
kind: "flow"
summary: "Flow doctrine for the T-n subject / T truth split, paired Oracle runs, replay limits, and golden-id grounding."
focus_paths:
  - codex/CODEX.md
  - codex/doctrine/missions/lab.md
  - codex/doctrine/missions/oracle.md
  - codex/doctrine/flows/contracts_and_grading.md
  - system/core/engine.py
  - system/lib/run_compare.py
  - tools/oracle/subject_index.py
  - codex/substrate/nodes/oracle/oracle_truth_map.json
  - codex/substrate/nodes/oracle/oracle_cp2_emitter.json
doc_links:
  - codex/doctrine/missions/lab.md
  - codex/doctrine/missions/oracle.md
  - codex/doctrine/flows/contracts_and_grading.md
  - codex/doctrine/components/observation_report.md
  - codex/doctrine/operations/oracle_proof_runbook.md
last_verified_at: "2026-03-07"
---
<!-- DOCTRINE_STRUCTURED_BLOCK -->
## Purpose
Flow doctrine for the T-n subject / T truth split, paired Oracle runs, replay limits, and golden-id grounding.

## Scope
- This doctrine file is `codex/doctrine/flows/temporal_contract.md`. [focus:codex/CODEX.md]
- Source of truth includes the authored temporal model in `codex/CODEX.md`, `codex/doctrine/missions/lab.md`, `codex/doctrine/missions/oracle.md`, and `codex/doctrine/flows/contracts_and_grading.md`. [focus:codex/CODEX.md] [focus:codex/doctrine/missions/lab.md] [focus:codex/doctrine/missions/oracle.md] [focus:codex/doctrine/flows/contracts_and_grading.md]
- Source of truth includes runtime enforcement in `system/core/engine.py`, `system/lib/run_compare.py`, and `tools/oracle/subject_index.py`. [focus:system/core/engine.py] [focus:system/lib/run_compare.py] [focus:tools/oracle/subject_index.py]
- Source of truth includes the Oracle truth and emission boundaries in `codex/substrate/nodes/oracle/oracle_truth_map.json` and `codex/substrate/nodes/oracle/oracle_cp2_emitter.json`. [focus:codex/substrate/nodes/oracle/oracle_truth_map.json] [focus:codex/substrate/nodes/oracle/oracle_cp2_emitter.json]

## Claims
- Lab is a `T-n` system: it may reason from the snapshot baseline but not from realized `T`. [focus:codex/doctrine/missions/lab.md] [focus:codex/CODEX.md]
- Oracle is a paired-run system: it requires both subject-side lineage at `T-n` and truth-side realized evidence at `T`. [focus:codex/doctrine/missions/oracle.md] [focus:system/core/engine.py]
- Feed replay is provenance only; it does not grant realized-truth authority to Lab or collapse subject/truth separation. [focus:codex/CODEX.md] [focus:codex/doctrine/flows/contracts_and_grading.md] [focus:system/lib/run_compare.py]
- Golden-id grounding remains subject-side: Oracle may learn from truth-side facts, but final CP2 grounding must stay within the subject-run ledger set. [focus:codex/substrate/nodes/oracle/oracle_cp2_emitter.json] [focus:tools/oracle/subject_index.py]

## Interfaces
- Focus paths:
  - `codex/CODEX.md`
  - `codex/doctrine/missions/lab.md`
  - `codex/doctrine/missions/oracle.md`
  - `codex/doctrine/flows/contracts_and_grading.md`
  - `system/core/engine.py`
  - `system/lib/run_compare.py`
  - `tools/oracle/subject_index.py`
  - `codex/substrate/nodes/oracle/oracle_truth_map.json`
  - `codex/substrate/nodes/oracle/oracle_cp2_emitter.json`
- Related docs:
  - `codex/doctrine/missions/lab.md`
  - `codex/doctrine/missions/oracle.md`
  - `codex/doctrine/flows/contracts_and_grading.md`
  - `codex/doctrine/components/observation_report.md`
  - `codex/doctrine/operations/oracle_proof_runbook.md`
<!-- END_DOCTRINE_STRUCTURED_BLOCK -->
# Temporal Contract

The system is only coherent if the time boundary stays explicit.

## Canonical Split

| Surface | Time authority | What it may do | What it may not do |
|---|---|---|---|
| Feeds | `T-n` snapshot | define the baseline state | declare realized outcomes |
| Lab | `T-n` only | produce CP1 and forward CP2 | use realized `T` facts |
| Oracle | `T-n` lineage + realized `T` | grade, reconstruct, critique | emit truth-grounded CP2 evidence |

## Subject Run vs Truth Run

- The **subject run** is the original Lab run whose CP1/CP2 lineage is being judged.
- The **truth run** is the later run that contains realized feed evidence for the same horizon.
- Oracle is invalid if either side is missing.
- Oracle anchoring starts from the subject run, not the truth run, even when truth-side feeds are hydrated downstream.

## Feed Replay Rule

Feed replay is allowed as a provenance mechanism only.

- A replay source can explain where the `T-n` snapshot came from.
- A replay source is not a substitute for a realized truth run.
- If the supposed truth side is actually just a replay source, grading and comparison are invalid.

## Golden-ID Law

Oracle has asymmetric authority:

- `oracle_truth_map` may use realized truth-side facts freely.
- `oracle_attribution_map` may explain what the subject run missed.
- `oracle_cp2_emitter` may use those findings to shape hindsight judgement.
- Final `evidence_dictionary` grounding in the emitted CP2 must still come only from subject-run eligible ledger ids.

Truth can inform. Truth cannot ground.

## Paired-Run Validation

Before treating two runs as a valid Oracle pair, confirm:

1. subject run is the original Lab call at `T-n`
2. truth run is later than the subject horizon boundary
3. truth run is not merely a feed replay source
4. subject-side lineage and target universe are still resolvable
5. Oracle sink artifacts can be emitted without violating golden-id constraints

## Failure Modes

- Missing truth run: Oracle should not start.
- Reversed ordering: comparison is meaningless.
- Replay mistaken for truth: grading is epistemically invalid.
- Truth-only evidence in final Oracle CP2: hard boundary violation.
- Subject ledger ids not found in the original lineage: golden-id violation.

## Operational Consequence

When in doubt:

1. verify temporal ordering with kernel run commands
2. verify lineage and replay status
3. verify the grounding set before trusting the final Oracle CP2

If those checks fail, stop before analysis proceeds further.
