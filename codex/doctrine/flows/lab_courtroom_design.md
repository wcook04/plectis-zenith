---
id: "lab_courtroom_design"
kind: "flow"
summary: "Draft design doctrine for the future Lab courtroom topology: prosecutor, defender, and verdict stages between contradiction surfacing and CP1 lock."
focus_paths:
  - codex/doctrine/missions/lab.md
  - codex/doctrine/missions/oracle.md
  - codex/doctrine/references/reasoning_doctrine.md
  - codex/substrate/nodes/lab/orient.json
  - codex/substrate/nodes/lab/decide.json
  - codex/substrate/nodes/lab/integrity.json
doc_links:
  - codex/doctrine/missions/lab.md
  - codex/doctrine/missions/oracle.md
  - codex/doctrine/references/reasoning_doctrine.md
  - codex/doctrine/operations/oracle_proof_runbook.md
last_verified_at: "2026-03-07"
---
<!-- DOCTRINE_STRUCTURED_BLOCK -->
## Purpose
Draft design doctrine for the future Lab courtroom topology: prosecutor, defender, and verdict stages between contradiction surfacing and CP1 lock.

## Scope
- This doctrine file is `codex/doctrine/flows/lab_courtroom_design.md`. [focus:codex/doctrine/missions/lab.md]
- Source of truth includes current Lab and Oracle doctrine in `codex/doctrine/missions/lab.md` and `codex/doctrine/missions/oracle.md`. [focus:codex/doctrine/missions/lab.md] [focus:codex/doctrine/missions/oracle.md]
- Source of truth includes shared contradiction doctrine in `codex/doctrine/references/reasoning_doctrine.md`. [focus:codex/doctrine/references/reasoning_doctrine.md]
- Source of truth includes the current pre-courtroom Lab checkpoints in `codex/substrate/nodes/lab/orient.json`, `codex/substrate/nodes/lab/decide.json`, and `codex/substrate/nodes/lab/integrity.json`. [focus:codex/substrate/nodes/lab/orient.json] [focus:codex/substrate/nodes/lab/decide.json] [focus:codex/substrate/nodes/lab/integrity.json]

## Claims
- This document is a target-state draft, not a claim that courtroom topology already exists in the live DAG. [focus:codex/substrate/nodes/lab/orient.json] [focus:codex/substrate/nodes/lab/decide.json]
- The courtroom exists to preserve adversarial contradiction inside Lab before CP1 is locked. [focus:codex/doctrine/missions/lab.md] [focus:codex/doctrine/references/reasoning_doctrine.md]
- Oracle proof comes first; courtroom implementation should follow only after Oracle is operationally proven. [focus:codex/doctrine/missions/oracle.md] [focus:codex/doctrine/operations/oracle_proof_runbook.md]
- The courtroom must remain subject-side and forward-looking; it is not a way to import Oracle hindsight into Lab. [focus:codex/doctrine/missions/lab.md] [focus:codex/doctrine/missions/oracle.md]

## Interfaces
- Focus paths:
  - `codex/doctrine/missions/lab.md`
  - `codex/doctrine/missions/oracle.md`
  - `codex/doctrine/references/reasoning_doctrine.md`
  - `codex/substrate/nodes/lab/orient.json`
  - `codex/substrate/nodes/lab/decide.json`
  - `codex/substrate/nodes/lab/integrity.json`
- Related docs:
  - `codex/doctrine/missions/lab.md`
  - `codex/doctrine/missions/oracle.md`
  - `codex/doctrine/references/reasoning_doctrine.md`
  - `codex/doctrine/operations/oracle_proof_runbook.md`
<!-- END_DOCTRINE_STRUCTURED_BLOCK -->
# Lab Courtroom Design

Status: draft target state. This is not the live topology today.

## Why Introduce A Courtroom

Current Lab doctrine already says contradiction should be preserved instead of collapsed too early.

The courtroom formalizes that into explicit roles:

- **Prosecutor** argues the strongest case for the dominant path
- **Defender** argues the strongest disconfirming case against premature commitment
- **Verdict** locks one executable CP1 while preserving the losing side as structured invalidation

## Placement In The Flow

The courtroom belongs after contradiction surfacing and before final CP1 lock.

Current conceptual sequence:

`miners -> cross_corr_v1 -> orient -> decide`

Target conceptual sequence:

`miners -> cross_corr_v1 -> orient -> prosecutor/defender -> verdict -> phase 2 -> director`

Public ids and exact node names are not locked in this doc. The role topology is the contract; final ids should be frozen in a dedicated implementation batch.

## Design Principles

- Both sides read the same `T-n` evidence surface.
- Neither side may use realized truth or Oracle hindsight.
- The verdict emits one executable CP1, not two soft options.
- The losing case is preserved as explicit invalidation and stress, not discarded prose.
- Integrity remains downstream and should still hard-fail silent contradiction loss.

## Proposed Role Contracts

### Prosecutor

- build the strongest flow-consistent dominant thesis
- make the positive execution case legible
- cite the evidence that actually supports commitment

### Defender

- build the strongest falsification or contradiction case
- identify pre-pricing, already-expressed, or structurally weak continuation logic
- force the system to confront what would make the dominant path wrong

### Verdict

- choose one executable CP1
- record why the losing case lost
- preserve the losing case as primary invalidation logic

## Non-Goals

- not a truth-side critique layer
- not an Oracle replacement
- not a free-form debate engine with no contract output
- not a license to weaken CP1 into narrative indecision

## Gate Before Implementation

Do not implement this topology until:

1. Oracle has one clean real proof run
2. the courtroom contract fields are explicitly frozen
3. batch ordering is defined so current Lab behavior can be compared before and after the rewrite
