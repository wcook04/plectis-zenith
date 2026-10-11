---
id: "contracts_and_grading"
kind: "flow"
summary: "Contract validation and post-run grading flow for CP1/CP2 and audit outcomes."
focus_paths:
  - codex/substrate/contracts/schema_cp1.json
  - codex/substrate/contracts/schema_cp2.json
  - system/core/engine.py
  - system/lib/observer_report.py
  - system/lib/run_compare.py
  - system/lib/schema_validator.py
  - system/lib/lab_contract_audit.py
doc_links:
  - codex/doctrine/missions/lab.md
  - codex/doctrine/missions/oracle.md
  - codex/doctrine/flows/temporal_contract.md
  - codex/doctrine/components/observation_report.md
  - codex/doctrine/operations/codex_change_protocol.md
last_verified_at: "2026-03-07"
---
<!-- DOCTRINE_STRUCTURED_BLOCK -->
## Purpose
Contract validation and post-run grading flow for CP1/CP2 and audit outcomes.

## Scope
- This doctrine file is `codex/doctrine/flows/contracts_and_grading.md`. [focus:codex/substrate/contracts/schema_cp1.json]
- Source of truth includes `codex/substrate/contracts/schema_cp1.json`. [focus:codex/substrate/contracts/schema_cp1.json]
- Source of truth includes `codex/substrate/contracts/schema_cp2.json`. [focus:codex/substrate/contracts/schema_cp2.json]
- Source of truth includes `system/core/engine.py`. [focus:system/core/engine.py]
- Source of truth includes `system/lib/observer_report.py`. [focus:system/lib/observer_report.py]
- Source of truth includes `system/lib/run_compare.py`. [focus:system/lib/run_compare.py]
- Source of truth includes `system/lib/schema_validator.py`. [focus:system/lib/schema_validator.py]
- Source of truth includes `system/lib/lab_contract_audit.py`. [focus:system/lib/lab_contract_audit.py]

## Claims
- Canonical claim path: `codex/substrate/contracts/schema_cp1.json`. [focus:codex/substrate/contracts/schema_cp1.json]
- Canonical claim path: `codex/substrate/contracts/schema_cp2.json`. [focus:codex/substrate/contracts/schema_cp2.json]
- Canonical claim path: `system/core/engine.py`. [focus:system/core/engine.py]
- Canonical claim path: `system/lib/observer_report.py`. [focus:system/lib/observer_report.py]
- Canonical claim path: `system/lib/run_compare.py`. [focus:system/lib/run_compare.py]
- Canonical claim path: `system/lib/schema_validator.py`. [focus:system/lib/schema_validator.py]
- Canonical claim path: `system/lib/lab_contract_audit.py`. [focus:system/lib/lab_contract_audit.py]

## Interfaces
- Focus paths:
  - `codex/substrate/contracts/schema_cp1.json`
  - `codex/substrate/contracts/schema_cp2.json`
  - `system/core/engine.py`
  - `system/lib/observer_report.py`
  - `system/lib/run_compare.py`
  - `system/lib/schema_validator.py`
  - `system/lib/lab_contract_audit.py`
- Related docs:
  - `codex/doctrine/missions/lab.md`
  - `codex/doctrine/missions/oracle.md`
  - `codex/doctrine/flows/temporal_contract.md`
  - `codex/doctrine/components/observation_report.md`
  - `codex/doctrine/operations/codex_change_protocol.md`
<!-- END_DOCTRINE_STRUCTURED_BLOCK -->
# Contracts And Grading

Contracts are the machine boundary between "plausible prose" and "acceptable system output."

They do three jobs:

1. enforce checkpoint structure at runtime
2. preserve comparability between Lab and Oracle outputs
3. provide deterministic input to post-run grading

## Contract Surface

Contracts live in `codex/substrate/contracts/`.

| Surface | Kind | Used by | Role |
|---|---|---|---|
| `atomic_tuple.md` | narrative contract | miners | defines tuple semantics per lane |
| `epicentre_thesis.md` | narrative contract | `lab_decide`, `lab_director`, `oracle_cp2_emitter` | defines what an epicentre thesis means |
| `schema_cp1.json` | machine schema | `lab_decide` | CP1 checkpoint at `T-n` |
| `schema_cp2.json` | machine schema | `lab_director`, `oracle_cp2_emitter` | CP2 checkpoint; Oracle uses CP2-core plus Oracle-only meta fields |
| `cross_corr_v1.json` / `cross_corr_v2.json` | machine schema | cross-corr nodes | structure-only correlation outputs |
| `schema_prediction_reconciliation.json` | machine schema | `oracle_truth_diff_equity` | deterministic per-target grading surface |
| `schema_realized_hindsight_brief.json` | machine schema | `oracle_truth_map` | realized-state contextualizer at `T` |
| `schema_cp2_critique.json` | machine schema | `oracle_attribution_map` | structured per-scope critique of Lab's CP2 |

## Current Checkpoint Definitions

### CP1

CP1 is not miner output.

CP1 is the locked `T-n` checkpoint emitted by `lab_decide`. It contains:

- `evidence_dictionary`
- `epicentre_thesis`
- `dominant_evidence_track`
- optional/conditional contradiction and pre-pricing fields defined by `schema_cp1.json`

This is the system's single committed dominant-force statement before forward predictions are made.

### CP2

CP2 is the directional consequence contract defined by `schema_cp2.json`.

It is emitted by two different nodes with different temporal authority:

- `lab_director`: forward CP2 from `T-n` toward `T`
- `oracle_cp2_emitter`: realized CP2 reconstruction after `T`

They share one schema so the system can compare forward structure with hindsight structure directly.

## Lab vs Oracle Boundary

| Layer | Time access | Contract output | Allowed authority |
|---|---|---|---|
| Lab | `T-n` snapshot only | CP1 then forward CP2 | prediction under uncertainty |
| Oracle | realized `T` plus `T-n` lineage | four Oracle artifacts plus CP2-compatible ideal reconstruction | hindsight grading, reconstruction, and critique without truth leakage |

Oracle's four primary outputs are:

1. `prediction_reconciliation` — deterministic per-target grading
2. `realized_hindsight_brief` — realized-state context at `T`
3. `ideal_cp2` — best hindsight CP2, CP2-core grounded in `T-n`, Oracle-meta recording `T` influence
4. `cp2_critique` — structured comparison of Lab CP2 vs ideal, scoped per field

Oracle sharing the CP2 schema does not make it another predictor. It uses CP2-compatible structure so "what was forecast" and "what should have been forecast" are directly comparable.

The grounding law applies throughout: only subject-side `T-n` ledger ids may ground the CP2-core claims in `ideal_cp2`. Truth-side refs are preserved in Oracle-meta fields and `cp2_critique` explanatory fields, but they are not admissible grounding.

Feed replay does not change that boundary. A replayed Lab run still has no realized-truth authority; it only records which `T-n` snapshot was reused.

There is no canonical automated `Evolve` contract. Oracle findings inform doctrine and dossier changes through explicit review, not autonomous schema mutation.

## Runtime Validation

Primary validator: `system/lib/schema_validator.py`

Key entrypoints:

- `validate_cp1(payload)` for `lab_decide`
- `validate_cp2(payload, subject_run_dir=...)` for `lab_director` and `oracle_cp2_emitter`
- `validate_cross_corr_v1(payload)`
- `validate_cross_corr_v2(payload)`

Validation is deterministic and filesystem-only. It checks structure, citations, ledger identity, equity grounding, and temporal coherence. Invalid checkpoint output is a hard runtime problem, not a style problem.

## What CP1 Enforces

`schema_cp1.json` and `epicentre_thesis.md` together enforce:

- one dominant force, not a basket of co-equal stories
- resolved `[N]` citations tied to `evidence_dictionary`
- minimum thesis length
- contradiction reconciliation when bifurcations are surfaced
- explicit evidence-track labeling (`FLOW_LED`, `NARRATIVE_LED`, `DIVERGENT`)

## What CP2 Enforces

`schema_cp2.json` extends CP1 and adds:

- `predictions_t`
- per-target `snapshot_price`, `target_price`, `direction`, and `invalidation`
- `trade_rationale`
- stock/ETF grounding per predicted target (`S_` or `E_`)
- temporal integrity between snapshot and target times

For Oracle outputs, these four fields remain the enforced CP2-core. Oracle may append an optional `oracle_meta` object, but `validate_cp2` continues to validate the CP2-core only. Oracle-meta never counts as admissible grounding and cannot compensate for missing or invalid core support.

Engine audit stamps deterministic times and audits `snapshot_price` against the subject-run stock+ETF baseline.

Oracle additionally applies the golden-ID guard so its emitted evidence cannot invent ledger IDs absent from the original Lab lineage.

Field-level critique boundaries live in `codex/substrate/dossiers/oracle_cp2_scope_dossier.json`. Provisional Oracle miss classes live in `codex/substrate/dossiers/oracle_error_taxonomy.json`.

## Miner And Cross-Corr Contracts

Miners do not emit CP1 or CP2.

They are governed by:

- `atomic_tuple.md` for tuple semantics
- cross-corr schemas for structural map outputs

This distinction matters. If miner semantics change, update tuple doctrine. If checkpoint semantics change, update CP1 or CP2 doctrine.

## Post-Run Grading

`system/lib/lab_contract_audit.py` computes the Lab run grade.

High-level checks include:

- completion rate
- CP1 validity
- CP2 validity
- contract coverage
- cross-corr validity
- duplicate-ID / structural integrity checks

Output lives in:

```text
state/runs/RUN_<...>/lab_contract_audit.json
```

The grade answers whether the run produced structurally acceptable checkpoints, not whether the market thesis was economically wise.

## Contract Ledger

Each run records contract usage so grading and UI surfaces can reconstruct which contracts were invoked.

Core artifacts:

- `contract_ledger.jsonl`
- `contracts_used_combined.json`
- per-run `contracts/` snapshots

For Oracle runs, the engine also emits `observation_report.json` after `oracle_cp2_emitter` succeeds. That report is a secondary summary sidecar over the four primary Oracle artifacts. It preserves the legacy top-level diff fields and adds an `oracle` block with realized-move and attribution summaries. The four primary artifacts (`prediction_reconciliation`, `realized_hindsight_brief`, `ideal_cp2`, `cp2_critique`) are the canonical Oracle outputs; `observation_report.json` is additive context, not the main deliverable.

## Change Protocol

If you change a contract:

1. update the contract file under `codex/substrate/contracts/`
2. update this doctrine file
3. update `lab.md` and `oracle.md` if checkpoint meaning changed
4. update the Oracle scope or error dossiers if the change alters critique boundaries or miss taxonomy
4. update node expectations/prompts that reference the changed fields
5. update validators or audit code if runtime enforcement changed
6. run:

```bash
python3 kernel.py --scratchpad
python3 kernel.py --build
```

If the change is structural, add targeted tests as well.
