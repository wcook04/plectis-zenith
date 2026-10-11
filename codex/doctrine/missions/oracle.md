---
id: "oracle_mission"
kind: "mission"
summary: "Mission doctrine for Oracle: asymmetric hindsight reconstruction, factual reconciliation, and structured critique of Lab's forward call."
focus_paths:
  - codex/substrate/nodes/oracle/oracle_subject_index.json
  - codex/substrate/nodes/oracle/oracle_subject_lab_director.json
  - codex/substrate/nodes/oracle/oracle_subject_stock_feed.json
  - codex/substrate/nodes/oracle/oracle_truth_map.json
  - codex/substrate/nodes/oracle/oracle_attribution_map.json
  - codex/substrate/nodes/oracle/oracle_cp2_emitter.json
  - tools/oracle/subject_index.py
  - tools/oracle/truth_diff_equity.py
  - tools/oracle/truth_diff_macro.py
  - system/lib/observer_report.py
  - system/lib/run_compare.py
  - system/core/engine.py
doc_links:
  - codex/doctrine/flows/contracts_and_grading.md
  - codex/doctrine/flows/temporal_contract.md
  - codex/doctrine/components/observation_report.md
  - codex/doctrine/operations/oracle_proof_runbook.md
  - codex/doctrine/operations/codex_change_protocol.md
  - codex/doctrine/components/codex_nodes.md
last_verified_at: "2026-03-07"
---
<!-- DOCTRINE_STRUCTURED_BLOCK -->
## Purpose
Mission doctrine for Oracle: asymmetric hindsight reconstruction, factual reconciliation, and structured critique of Lab's forward call.

## Scope
- This doctrine file is `codex/doctrine/missions/oracle.md`. [focus:codex/substrate/nodes/oracle/oracle_subject_index.json]
- Source of truth includes `codex/substrate/nodes/oracle/oracle_subject_index.json`. [focus:codex/substrate/nodes/oracle/oracle_subject_index.json]
- Source of truth includes `codex/substrate/nodes/oracle/oracle_subject_lab_director.json`. [focus:codex/substrate/nodes/oracle/oracle_subject_lab_director.json]
- Source of truth includes `codex/substrate/nodes/oracle/oracle_subject_stock_feed.json`. [focus:codex/substrate/nodes/oracle/oracle_subject_stock_feed.json]
- Source of truth includes `codex/substrate/nodes/oracle/oracle_truth_map.json`. [focus:codex/substrate/nodes/oracle/oracle_truth_map.json]
- Source of truth includes `codex/substrate/nodes/oracle/oracle_attribution_map.json`. [focus:codex/substrate/nodes/oracle/oracle_attribution_map.json]
- Source of truth includes `codex/substrate/nodes/oracle/oracle_cp2_emitter.json`. [focus:codex/substrate/nodes/oracle/oracle_cp2_emitter.json]
- Source of truth includes `tools/oracle/subject_index.py`. [focus:tools/oracle/subject_index.py]
- Source of truth includes `tools/oracle/truth_diff_equity.py`. [focus:tools/oracle/truth_diff_equity.py]
- Source of truth includes `tools/oracle/truth_diff_macro.py`. [focus:tools/oracle/truth_diff_macro.py]
- Source of truth includes `system/lib/observer_report.py`. [focus:system/lib/observer_report.py]
- Source of truth includes `system/lib/run_compare.py`. [focus:system/lib/run_compare.py]
- Source of truth includes `system/core/engine.py`. [focus:system/core/engine.py]

## Claims
- Canonical claim path: `codex/substrate/nodes/oracle/oracle_subject_index.json`. [focus:codex/substrate/nodes/oracle/oracle_subject_index.json]
- Canonical claim path: `codex/substrate/nodes/oracle/oracle_subject_lab_director.json`. [focus:codex/substrate/nodes/oracle/oracle_subject_lab_director.json]
- Canonical claim path: `codex/substrate/nodes/oracle/oracle_subject_stock_feed.json`. [focus:codex/substrate/nodes/oracle/oracle_subject_stock_feed.json]
- Canonical claim path: `codex/substrate/nodes/oracle/oracle_truth_map.json`. [focus:codex/substrate/nodes/oracle/oracle_truth_map.json]
- Canonical claim path: `codex/substrate/nodes/oracle/oracle_attribution_map.json`. [focus:codex/substrate/nodes/oracle/oracle_attribution_map.json]
- Canonical claim path: `codex/substrate/nodes/oracle/oracle_cp2_emitter.json`. [focus:codex/substrate/nodes/oracle/oracle_cp2_emitter.json]
- Canonical claim path: `tools/oracle/subject_index.py`. [focus:tools/oracle/subject_index.py]
- Canonical claim path: `tools/oracle/truth_diff_equity.py`. [focus:tools/oracle/truth_diff_equity.py]
- Canonical claim path: `tools/oracle/truth_diff_macro.py`. [focus:tools/oracle/truth_diff_macro.py]
- Canonical claim path: `system/lib/observer_report.py`. [focus:system/lib/observer_report.py]
- Canonical claim path: `system/lib/run_compare.py`. [focus:system/lib/run_compare.py]
- Canonical claim path: `system/core/engine.py`. [focus:system/core/engine.py]

## Interfaces
- Focus paths:
  - `codex/substrate/nodes/oracle/oracle_subject_index.json`
  - `codex/substrate/nodes/oracle/oracle_subject_lab_director.json`
  - `codex/substrate/nodes/oracle/oracle_subject_stock_feed.json`
  - `codex/substrate/nodes/oracle/oracle_truth_map.json`
  - `codex/substrate/nodes/oracle/oracle_attribution_map.json`
  - `codex/substrate/nodes/oracle/oracle_cp2_emitter.json`
  - `tools/oracle/subject_index.py`
  - `tools/oracle/truth_diff_equity.py`
  - `tools/oracle/truth_diff_macro.py`
  - `system/lib/observer_report.py`
  - `system/lib/run_compare.py`
  - `system/core/engine.py`
- Related docs:
  - `codex/doctrine/flows/contracts_and_grading.md`
  - `codex/doctrine/flows/temporal_contract.md`
  - `codex/doctrine/components/observation_report.md`
  - `codex/doctrine/operations/oracle_proof_runbook.md`
  - `codex/doctrine/operations/codex_change_protocol.md`
  - `codex/doctrine/components/codex_nodes.md`
<!-- END_DOCTRINE_STRUCTURED_BLOCK -->
# Oracle Mission Theory

Oracle is not a second Lab. It is an asymmetric hindsight mission:

- it reads `T-n` from the subject Lab run
- it reads realized `T` from the paired truth run
- it grades Lab's forward call against realized outcomes
- it reconstructs the best CP2 that should have been emitted from `T-n`
- it critiques where and how Lab's actual call deviated from that ideal

That asymmetry is the whole point. Truth is allowed to explain. Truth is not allowed to ground.

Oracle answers three questions:

1. What actually happened at `T`, deterministically and interpretively?
2. What is the best subject-grounded hindsight CP2 Oracle can reconstruct?
3. Where and why did Lab's actual CP2 fail relative to that ideal?

It does not prescribe patches. It does not mutate Lab. It grades, reconstructs, and critiques.

## Runtime Contract

Oracle runs on a paired temporal contract:

- `oracle_subject_run_dir` = the original Lab run at `T-n`
- `oracle_truth_run_dir` = the later truth run at `T`
- A feed-replay Lab run may carry a replay-source pointer for `T-n` provenance, but that replay source is not Oracle truth.

Engine rules:

- Oracle snapshot anchoring comes from the subject run, not the truth run.
- Oracle `global_*` feed hydration reads from the truth run by default.
- Subject-side raw reads happen only through dedicated Oracle tools such as `oracle_subject_index`.
- Golden-id validation remains bound to the subject snapshot ledger set.
- `oracle_explain` is the only Oracle node allowed to browse, and only after attribution.

If Oracle lacks a paired truth run, it is invalid. There is no single-run Oracle mode.

## Oracle Spine

```text
oracle_subject_lab_decide / oracle_subject_lab_director / oracle_subject_lab_cross_corr_v2
7x oracle_subject_<lane>_feed
        │
        ├── oracle_subject_index
        ├── oracle_truth_diff_equity
        ├── oracle_truth_diff_macro
        └── 7x oracle_truth_<lane> (subject-side T-n proxy + truth-side T feed)
                │
                ▼
          oracle_truth_map
                │
                ▼
        oracle_attribution_map
                │
                ├── oracle_explain (optional, explanatory only)
                ▼
          oracle_cp2_emitter
```

### 1. Subject Index

`oracle_subject_index` is still the only Oracle v1 node that is allowed to build subject-side grounding context directly from the Lab run.

Oracle now makes the T-n side explicit in topology by materializing:

- subject-side Lab checkpoint proxy nodes
- subject-side feed proxy nodes

These proxy nodes are graph-visible surfaces for Oracle's T-n context. They do not change the grounding rule; they make the temporal split inspectable.

It emits:

- eligible subject ledger ids
- evidence grouped by subject
- Lab CP2 predictions
- valid prediction targets
- subject-side stock+ETF snapshot prices

This is the grounding envelope for the final Oracle CP2.

### 2. Deterministic Truth Diffs

Two tool nodes create the mechanical before/after layer:

- `oracle_truth_diff_equity`
  - deterministic stock+ETF comparison
  - top movers
  - realized outcomes for all Lab targets
  - combined grading table
- `oracle_truth_diff_macro`
  - deterministic macro before/after comparison
  - compact changed-series output
  - no same-run `as_of` equality requirement

These tools are the low-hallucination substrate. They replace the legacy same-run observer diff chain as Oracle's primary factual surface.

### 3. Truth Miners

Seven `oracle_truth_<lane>` nodes read truth-side feeds plus deterministic diff outputs where relevant and answer one question per lane:

What actually happened here, and was it already priced or genuinely surprising?

These miners are interpretive, but they are downstream of deterministic truth artifacts rather than downstream of same-run ledger overlap.

### 4. Truth Map

`oracle_truth_map` is the Oracle v1 orient layer.

It must classify major realized drivers as exactly one of:

- `SURPRISE`
- `ALREADY_PRICED`
- `PARTIAL_REPRICING`

This is the durable realized-regime artifact for the run.

### 5. Attribution Map

`oracle_attribution_map` maps realized truth back onto subject-side evidence:

- what `T-n` really pointed toward the realized outcome
- what was loud, public, or already expressed
- what the Lab construction missed
- what the hindsight CP2 should preserve or drop

This is the durable failure-diagnosis artifact for the run.

### 6. Explanatory Search

`oracle_explain` is optional and post-attribution.

Its job is narrow:

- explain misses
- explain why something was already priced
- add narrative context only

It may not:

- introduce new ledger ids
- introduce new target ids
- create new grounding claims

### 7. Final CP2

`oracle_cp2_emitter` stays the sink id for compatibility.

Its job is to emit the hindsight CP2 reconstruction using the shared CP2 schema while obeying two strict rules:

1. Truth can inform construction.
2. Only subject-run evidence can ground the final artifact.

That means a realized driver may dominate the truth map and attribution map but still be absent from Oracle CP2 if no subject-side evidence supported it.

### 7A. Hindsight Reconstruction Discipline (v1.1)

`oracle_cp2_emitter` must maintain reconstruction traceability:

1. For each retained claim in the hindsight CP2, record which subject-side evidence supports it and which truth-side influence informed the reconstruction.
2. For each excluded realized driver, record why the exclusion was necessary (no subject-side support, non-comparable macro, or exogenous shock).
3. The `oracle_meta.explicit_exclusions` array is the canonical surface for this discipline.
4. A hindsight CP2 that reconstructs without explicit exclusion accounting is incomplete even if it passes schema validation.

This discipline enables downstream Evolve learning: the exclusion pattern across runs reveals which types of signals the Lab systematically fails to capture.

## Durable Outputs

Oracle produces four primary artifacts per run:

### `prediction_reconciliation`

A deterministic grading surface produced by `oracle_truth_diff_equity`. For every Lab prediction target, it records:

- subject-side snapshot price at `T-n`
- Lab's predicted target price and direction
- realized truth-side price at `T`
- absolute delta, percent delta, and directional correctness
- `feed_health`, a deterministic stock+ETF readiness block that says whether each Lab CP2 target had subject and truth prices before interpretive stages read the grade

Stock and ETF rows are mandatory. Macro rows appear only when there is an explicit comparable macro prediction surface. Missing or non-comparable targets are hard failures.

### `realized_hindsight_brief`

A realized-state contextualizer produced by `oracle_truth_map`. It answers: what is happening at `T` in realized market terms? It classifies drivers as SURPRISE, ALREADY_PRICED, or PARTIAL_REPRICING and ranks them. It is primarily truth-side oriented and uses deterministic diffs for context, but it is not the critique and not the ideal CP2.

### `ideal_cp2`

Oracle's reconstruction of the best CP2 that should have been emitted from `T-n`, produced by `oracle_cp2_emitter`. It preserves the shared CP2-core fields:

- `evidence_dictionary`
- `epicentre_thesis`
- `predictions_t`
- `trade_rationale`

and may add an optional `oracle_meta` object with:

- `truth_influence_refs`
- `realized_diff_refs`
- `explicit_exclusions`
- `oracle_hindsight_notes`

The grounding law is hard: only subject-side `T-n` ledger ids may ground the CP2-core claims. Truth-side refs may be cited and preserved in Oracle-meta fields, but they are never admissible grounding for the CP2-core itself.

### `cp2_critique`

A structured comparison produced by `oracle_attribution_map`, critiquing each scope of Lab's CP2 in its own lane:

- `thesis`: was the thesis wrong, and if so, was it wrong because the subject evidence was insufficient, or because it was misread?
- `prediction`: was the prediction target, direction, or sizing wrong?
- `prediction_justification`: did the justification mis-extrapolate from the thesis, even if the thesis was correct?
- `citations / grounding`: was the evidence selection weak, missing, or mismatched?

Each critique item includes the scope, the relevant subject-side grounding refs, the realized explanatory refs, what was wrong, and an error class. Oracle explains and classifies the miss. It does not prescribe patches.

Scope boundaries for `ideal_cp2` and `cp2_critique` live in `codex/substrate/dossiers/oracle_cp2_scope_dossier.json`.

Provisional error classes: `OBSERVATION_MISS`, `OBSERVATION_NOISE`, `SYNTHESIS_BLIND`, `SYNTHESIS_LEAP`, `PREDICTION_DRIFT`, `EXOGENOUS_SHOCK`. The canonical authored taxonomy lives in `codex/substrate/dossiers/oracle_error_taxonomy.json` and remains provisional until Oracle has processed real runs.

### `observation_report.json`

A secondary summary sidecar over the four primary artifacts. It is not the main deliverable. It provides a compact top-level view for backward-compatible surfaces and carries an `oracle` block with top-movers, realized target table, grading summary, and attribution summary.

## Quartet Repair / Readiness

Modern engine runs dual-write canonical aliases from the source node ids:

- `oracle_truth_diff_equity` -> `prediction_reconciliation`
- `oracle_truth_map` -> `realized_hindsight_brief`
- `oracle_attribution_map` -> `cp2_critique`
- `oracle_cp2_emitter` -> `ideal_cp2`

Older runs can be structurally useful but incomplete for Evolve because they may have source-node outputs without the canonical aliases, or may lack the interpretive Oracle nodes entirely. `tools/oracle/run_quartet.py` is the bounded operator surface for that case:

- `--plan` emits `oracle_quartet_repair_plan` with canonical artifact status, aliasable source-node outputs, missing source nodes, and repair actions.
- `--materialize-aliases` only writes canonical aliases for source-node artifacts that already exist. It does not call bridge or reinterpret truth.
- `--run-missing --target <oracle_node>` resumes `GodModeEngine` on the existing Oracle truth run with the subject/truth pair attached. This may invoke bridge-backed reasoning and is therefore an explicit operator action.

Station exposes the safe planner and the explicit detached runner as `oracle_quartet_plan` and `oracle_quartet_run_missing`, backed by the `oracle_quartet_repair` meta-mission pack. Pair candidates in `/station/lab-oracle-evolve` also project recent pair-matched launcher events from `tools/meta/control/orchestration_events.jsonl` and detached `state/launcher_ops/*.log` receipts, so the same surface shows whether the repair is running, completed with a parsed post-plan, failed, or exited without a parseable result. Evolve's `--input-check` embeds the same repair plan so a blocked learning pass names the missing Oracle target rather than leaving the operator to infer it from absent files.

## CP2 Semantics

Oracle uses the same CP2 schema family as Lab for comparability, but Oracle CP2 differs in authority and structure:

- Lab CP2 = forward consequence claim from `T-n`
- Oracle `ideal_cp2` = hindsight reconstruction of what the correct `T-n` construction should have been, with an additional Oracle-meta layer recording which `T` evidence shaped the reconstruction

Oracle CP2 core claims may target stock or ETF tickers, but the evidence dictionary must still come from subject-run ledger ids only. The Oracle-meta layer records the truth-side influence but does not let it contaminate grounding.

## Node Input Size Tracking

The engine records approximate input size per node call as part of run diagnostics. When a node produces poor output, the first diagnostic question is whether its context was near the model's practical limit. Per-node input sizes are surfaced in `--run-context` and stored in the run artifact set. This is diagnostic, not a gate.

## Legacy Chain Status

The old `oracle_diff_*`, `oracle_evaluate_*`, `oracle_score_*`, `oracle_search_*`, `oracle_trade_check_*`, `oracle_shadow_extractor`, `oracle_survival_classifier`, and `oracle_crosslane_attribution` chain has been removed. The current Oracle spine is the only Oracle path.

## Hard Fail Conditions

Oracle fails hard when:

- no paired truth run is supplied
- truth feed hydration is missing for a required `global_*` node
- final CP2 uses a truth-only ledger id
- final CP2 uses `oracle_explain` output as grounding
- the final CP2 cites a target without subject-side stock/ETF grounding

## Draft-and-Verify Epistemic Architecture (Hindsight Mode)

Oracle applies the same Draft-and-Verify loop as Lab, but in the opposite temporal direction. Where Lab uses a "Forward Draft" to direct miners toward T, Oracle uses a "Hindsight Draft" (a spoiler) to direct miners back toward T-n.

The intended wave structure:

1. **Seed State** (`oracle_truth_diff_equity` / `oracle_truth_diff_macro`): Deterministic tool nodes produce the raw "Crime Scene Report" — the mathematical deltas between T-n and T. No interpretation, just realized facts.
2. **Seed Synthesis** (`oracle_truth_map`): Reads the deterministic diffs and classifies the realized regime: which drivers were `SURPRISE`, `ALREADY_PRICED`, or `PARTIAL_REPRICING`. This is Oracle's version of `lab_seed_state`.
3. **Internet Research** (`oracle_explain`): Reads the Lab CP2 (what was predicted) and the truth map (what happened). Searches the internet for news published between T-n and T to find the true causal mechanism. This is the "Spoiler" — it tells the system *why* the regime shifted before the hindsight miners begin.
4. **Attribution Map** (`oracle_attribution_map`): Combines the internet research narrative and the truth map into a structured draft — which T-n signals actually foreshadowed the realized outcome, and which the Lab missed. This is Oracle's "Hindsight Draft".
5. **Directed Hindsight Mining** (7x `oracle_truth_<lane>` nodes): These miners receive the attribution map and hunt for T-n evidence that the draft says *should* have been visible. They are not mining blindly — they are finding the breadcrumbs that prove the regime shift was predictable at T-n.
6. **Final CP2** (`oracle_cp2_emitter`): Locks the hindsight draft plus the miners' T-n citations into a final CP2. All grounding must come from subject-run ledger ids, not from realized T data.

**The symmetry with Lab:**

| Layer | Lab (Forward) | Oracle (Hindsight) |
|-------|--------------|-------------------|
| Data compression | `lab_seed_state` | `oracle_truth_diff_*` |
| Draft generation | `lab_orient` (forward hypothesis) | `oracle_truth_map` + internet research (spoiler) |
| Directed miners | 7x `lab_miner_*` (confirm/deny draft) | 7x `oracle_truth_*` (find T-n breadcrumbs) |
| Thesis lock | `lab_decide` | `oracle_attribution_map` |
| Final output | `lab_director` CP2 | `oracle_cp2_emitter` CP2 |

**Why this matters:** Without the spoiler, Oracle truth miners would extract T-n data without knowing what they are looking for. The internet research step hands the miners the answer key first, then asks them to show their work using only T-n evidence. This guarantees coherent hindsight without hallucination.

---

## Oracle -> Lab Feedback

Oracle does not mutate Lab automatically.

The feedback loop is:

1. `realized_hindsight_brief` describes what actually happened.
2. `cp2_critique` isolates where and why Lab's construction failed or partially held.
3. `ideal_cp2` gives the comparable hindsight checkpoint.
4. `prediction_reconciliation` gives the deterministic grade.
5. Humans or agents decide whether doctrine, dossiers, or prompts should change.

That review boundary is explicit and manual. Oracle classifies and explains the miss. Remediation is a separate decision.
