---
id: "oracle_proof_runbook"
kind: "operation"
summary: "Runbook for proving one full paired Oracle run end to end and verifying the required artifacts and temporal conditions."
focus_paths:
  - codex/doctrine/missions/oracle.md
  - codex/doctrine/flows/temporal_contract.md
  - codex/doctrine/components/observation_report.md
  - system/core/engine.py
  - system/lib/run_compare.py
  - kernel.py
doc_links:
  - codex/doctrine/missions/oracle.md
  - codex/doctrine/flows/temporal_contract.md
  - codex/doctrine/components/observation_report.md
  - codex/doctrine/flows/contracts_and_grading.md
last_verified_at: "2026-03-07"
---
<!-- DOCTRINE_STRUCTURED_BLOCK -->
## Purpose
Runbook for proving one full paired Oracle run end to end and verifying the required artifacts and temporal conditions.

## Scope
- This doctrine file is `codex/doctrine/operations/oracle_proof_runbook.md`. [focus:codex/doctrine/missions/oracle.md]
- Source of truth includes Oracle doctrine and temporal rules in `codex/doctrine/missions/oracle.md`, `codex/doctrine/flows/temporal_contract.md`, and `codex/doctrine/components/observation_report.md`. [focus:codex/doctrine/missions/oracle.md] [focus:codex/doctrine/flows/temporal_contract.md] [focus:codex/doctrine/components/observation_report.md]
- Source of truth includes runtime enforcement in `system/core/engine.py` and `system/lib/run_compare.py`. [focus:system/core/engine.py] [focus:system/lib/run_compare.py]
- Source of truth includes the operator command surface in `kernel.py`. [focus:kernel.py]

## Claims
- A valid Oracle proof run is paired, temporally ordered, and artifact-complete. [focus:codex/doctrine/flows/temporal_contract.md] [focus:system/core/engine.py]
- The proof is not complete until the Oracle sink artifacts and `observation_report.json` both exist. [focus:codex/doctrine/missions/oracle.md] [focus:codex/doctrine/components/observation_report.md]
- Kernel run commands are the primary verification surface for timing, lineage, evidence, predictions, and comparison. [focus:kernel.py] [focus:system/lib/run_compare.py]
- If the truth side is actually a replay source, the run is not a valid Oracle proof. [focus:codex/doctrine/flows/temporal_contract.md] [focus:system/lib/run_compare.py]

## Interfaces
- Focus paths:
  - `codex/doctrine/missions/oracle.md`
  - `codex/doctrine/flows/temporal_contract.md`
  - `codex/doctrine/components/observation_report.md`
  - `system/core/engine.py`
  - `system/lib/run_compare.py`
  - `kernel.py`
- Related docs:
  - `codex/doctrine/missions/oracle.md`
  - `codex/doctrine/flows/temporal_contract.md`
  - `codex/doctrine/components/observation_report.md`
  - `codex/doctrine/flows/contracts_and_grading.md`
<!-- END_DOCTRINE_STRUCTURED_BLOCK -->
# Oracle Proof Runbook

The goal is one thing: prove that the paired Oracle path works on a real subject/truth pair from start to finish.

## Preconditions

You need:

- one Lab subject run at `T-n` with a valid `lab_director` artifact
- one later truth-capable run at `T`
- a matched horizon where realized comparison is meaningful
- a build/runtime surface that already contains the Oracle v1 topology

## Preflight

Run these first:

```bash
python3 kernel.py --runs
python3 kernel.py --run-timeline <subject_run> <truth_run>
python3 kernel.py --run-lineage <subject_run>
python3 kernel.py --orient oracle
```

A pair is acceptable only if:

- the truth run is later than the subject run
- the truth run is realized truth, not just replay provenance
- the subject run still resolves to the intended Lab lineage

## Execution Contract

The ignition surface you use must pass both:

- `oracle_subject_run_dir`
- `oracle_truth_run_dir`

Do not treat a single run or replay-only input as sufficient. Oracle v1 is explicitly paired.

## Success Artifacts

After execution, confirm these exist under the Oracle run:

- `oracle_subject_index.json`
- `oracle_truth_diff_equity.json`
- `oracle_truth_diff_macro.json`
- `oracle_truth_map.json`
- `oracle_attribution_map.json`
- `oracle_cp2_emitter.json`
- `observation_report.json`

The proof is incomplete if the sink artifact exists but `observation_report.json` does not.

## Verification Pass

Use the kernel, not ad hoc scripts:

```bash
python3 kernel.py --run-context <oracle_run>
python3 kernel.py --run-artifact <oracle_run> oracle_truth_map
python3 kernel.py --run-artifact <oracle_run> oracle_attribution_map
python3 kernel.py --run-artifact <oracle_run> oracle_cp2_emitter
python3 kernel.py --run-grade-predictions <subject_run> <truth_run>
python3 kernel.py --run-compare <subject_run> <truth_run>
```

## Required Success Conditions

- Oracle run completes without temporal-contract rejection.
- `oracle_truth_map` classifies realized drivers cleanly.
- `oracle_attribution_map` explains what the subject run pointed to, missed, or overstated.
- `oracle_cp2_emitter` emits a CP2-compatible artifact without violating subject-only grounding.
- `observation_report.json` is present and includes the additive `oracle_v1` summary block.

## Failure Conditions

Treat the proof as failed if any of these happen:

- no paired truth run was supplied
- truth ordering is invalid
- truth side is actually replay provenance
- sink artifact exists but sidecar report is missing
- emitted Oracle CP2 uses truth-only grounding

## After The First Clean Proof

Only after a clean proof run should the next design stage move up the queue. The immediate next design target is the Lab courtroom rewrite, not before.
