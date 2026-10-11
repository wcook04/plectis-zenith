---
id: "evolve_mission"
kind: "mission"
summary: "Mission doctrine for Evolve: structured learning from Oracle hindsight, dossier evolution, and doctrine adaptation."
focus_paths:
  - codex/nodes/refinement/delta_analyzer.json
  - codex/nodes/refinement/dossier_updater.json
  - codex/nodes/refinement/version_committer.json
  - codex/substrate/contracts/schema_evolve_delta.json
  - codex/substrate/contracts/schema_cp2_critique.json
  - codex/substrate/contracts/schema_prediction_reconciliation.json
  - codex/substrate/contracts/schema_realized_hindsight_brief.json
  - codex/substrate/dossiers/stock.json
  - codex/substrate/dossiers/etf.json
  - codex/substrate/dossiers/macro.json
  - tools/refinement/run_evolve.py
  - tools/refinement/overnight_ledger.py
  - system/lib/lab_oracle_evolve_overnight.py
  - codex/standards/observe/mission_templates/meta_missions/lab_oracle_evolve_input_check/mission.json
  - codex/standards/observe/mission_templates/meta_missions/lab_oracle_evolve_overnight_ledger/mission.json
  - tools/oracle/run_quartet.py
  - tools/refinement/version_committer.py
doc_links:
  - codex/doctrine/missions/lab.md
  - codex/doctrine/missions/oracle.md
  - codex/doctrine/flows/contracts_and_grading.md
  - codex/doctrine/flows/temporal_contract.md
last_verified_at: "2026-04-21"
---
<!-- DOCTRINE_STRUCTURED_BLOCK -->
## Purpose
Mission doctrine for Evolve: structured learning from Oracle hindsight, dossier evolution, and doctrine adaptation.

## Scope
- This doctrine file is `codex/doctrine/missions/evolve.md`. [focus:codex/nodes/refinement/delta_analyzer.json]
- Source of truth includes `codex/nodes/refinement/delta_analyzer.json`. [focus:codex/nodes/refinement/delta_analyzer.json]
- Source of truth includes `codex/nodes/refinement/dossier_updater.json`. [focus:codex/nodes/refinement/dossier_updater.json]
- Source of truth includes `codex/nodes/refinement/version_committer.json`. [focus:codex/nodes/refinement/version_committer.json]
- Source of truth includes `tools/refinement/version_committer.py`. [focus:tools/refinement/version_committer.py]

## Claims
- Canonical claim path: `codex/nodes/refinement/delta_analyzer.json`. [focus:codex/nodes/refinement/delta_analyzer.json]
- Canonical claim path: `codex/nodes/refinement/dossier_updater.json`. [focus:codex/nodes/refinement/dossier_updater.json]
- Canonical claim path: `codex/nodes/refinement/version_committer.json`. [focus:codex/nodes/refinement/version_committer.json]

## Interfaces
- Focus paths:
  - `codex/nodes/refinement/delta_analyzer.json`
  - `codex/nodes/refinement/dossier_updater.json`
  - `codex/nodes/refinement/version_committer.json`
  - `codex/substrate/contracts/schema_evolve_delta.json`
  - `system/lib/lab_oracle_evolve_overnight.py`
  - `tools/refinement/overnight_ledger.py`
  - `tools/refinement/version_committer.py`
- Related docs:
  - `codex/doctrine/missions/lab.md`
  - `codex/doctrine/missions/oracle.md`
  - `codex/doctrine/flows/contracts_and_grading.md`
<!-- END_DOCTRINE_STRUCTURED_BLOCK -->
# Evolve Mission Theory v1.0

> Learn from hindsight. Adapt the substrate. Never mutate blind.

Evolve is the learning engine. It reads Oracle's structured outputs, extracts actionable patterns, and proposes specific mutations to the system's domain knowledge and operational doctrine. It closes the loop: Lab predicts, Oracle grades, Evolve learns.

## Mission Boundary

Evolve is NOT autonomous mutation. It is structured proposal with atomic application.

1. Evolve reads Oracle outputs. It does not read raw market data.
2. Evolve proposes dossier patches. It does not invent new dossier structures.
3. Evolve flags doctrine candidates. It does not rewrite Lab or Oracle prompts.
4. Every mutation flows through `version_committer` with a git audit trail.
5. Every proposal must cite the Oracle artifact and error class that motivated it.
6. Missing feed coverage is not a market-learning signal. If `prediction_reconciliation.feed_health` is `BLOCKED`, Evolve must stop before delta analysis and surface the data gap instead of appending learning.

The review boundary is explicit. Evolve classifies what to change and why. Whether to accept the change is a separate decision.

---

## What Evolve Consumes

Evolve reads the four Oracle durable outputs plus the original Lab CP2:

| Artifact | Schema | What Evolve Extracts |
|----------|--------|---------------------|
| `prediction_reconciliation` | `schema_prediction_reconciliation.json` | Directional accuracy, magnitude of misses, systematic bias per target class |
| `realized_hindsight_brief` | `schema_realized_hindsight_brief.json` | Which drivers were SURPRISE vs ALREADY_PRICED, regime classification |
| `cp2_critique` | `schema_cp2_critique.json` | Error classes per scope, root failure mode, reconstruction guidance |
| `ideal_cp2` | `schema_cp2.json` (with `oracle_meta`) | What the best hindsight CP2 looked like, explicit exclusions |
| Lab CP2 | `schema_cp2.json` | The original forward call for diff comparison |

Evolve does NOT consume raw feeds, truth-side diffs, or Oracle intermediate nodes. It works from the durable synthesis layer.

### Feed-Readiness Gate

Evolve treats two data-readiness layers separately. Pre-Lab/feed-run substrate quality comes from `artifacts/feed_readiness_summary.json` on the subject and truth run directories when those summaries exist. Oracle run-pair comparability comes from `prediction_reconciliation.feed_health`.

Explicit `feed_readiness_summary` blockers stop Evolve learning because the correct interpretation is a data-substrate gap, not a CP2 reasoning failure. Missing summaries on legacy runs are surfaced as missing but do not block by themselves.

For `prediction_reconciliation.feed_health`:

- `READY`: the artifact quartet can be interpreted normally.
- `DEGRADED`: delta analysis may proceed, but learning must be scoped to comparable targets and must cite the missing subject/truth target coverage.
- `BLOCKED`: no Evolve learning pass should run. The correct output is an input-readiness failure, not a dossier delta, doctrine flag, or learning-ledger entry.

`tools/refinement/run_evolve.py` loads canonical Oracle artifact ids first (`prediction_reconciliation`, `realized_hindsight_brief`, `cp2_critique`, `ideal_cp2`) and keeps legacy node ids as fallbacks for older runs. The delta prompt includes an Oracle input-readiness manifest so bridge analysis can distinguish artifact absence, pre-Lab feed readiness blockers, Oracle run-pair feed absence, and actual prediction failure.

Station exposes the pre-learning readiness check as the launchable `evolve_input_check` operation. It runs `run_evolve.py --input-check`, returns a JSON manifest, and writes no learning ledger or dossier output. That manifest surfaces subject/truth `feed_readiness_summary` status when present and embeds `oracle_repair_plan` from `tools/oracle/run_quartet.py`, so a `BLOCKED` Evolve check can point at either the data-feed blocker or the exact safe alias materialization action / bridge-backed Oracle node rerun needed before learning.

Station also exposes `evolve_bridge_dry_run` for the full bridge-backed Evolve analysis after readiness passes. It runs detached with `--bridge --dry-run`, so it may write `_last_delta_report.json`, `_last_patch_payload.json`, pair-local `artifacts/evolve_delta_report.json`, pair-local `artifacts/evolve_patch_payload.json`, pair-local `artifacts/evolve_input_readiness.json`, and the learning ledger, but dossier patch application remains review-only unless a separate live/apply path is invoked. `/station/lab-oracle-evolve` reads the pair's recent launcher history and detached log receipts, so operators can distinguish a still-running dry-run from a completed readiness/repair result or an exited log with no parseable Evolve output.

### Overnight Ledger

Evolve can now plan overnight training-data accumulation before it spends bridge/model budget. `tools/refinement/overnight_ledger.py` reads the Station Lab/Oracle/Evolve pair candidates, applies an abstract budget model, selects READY pairs before DEGRADED pairs, skips already-completed pairs by default, and emits `lab_oracle_evolve_overnight_plan`. When launched with `--write-ledger`, it writes `state/lab_oracle_evolve/overnight_plan.json` and appends `state/lab_oracle_evolve/overnight_ledger.jsonl`.

This is a planning and audit surface, not an executor. It produces reviewable `evolve_bridge_dry_run` commands and an escalation policy for later Codex exception gates. A future bridge worker may consume the ledger, but until that executor exists, the ledger must not be described as automatic overnight bridge dispatch.

---

## What Evolve Produces

### 1. Evolve Delta Report (`evolve_delta_report`)

The primary Evolve artifact. A structured analysis that maps Oracle findings to specific substrate mutations.

See Contract: `codex/substrate/contracts/schema_evolve_delta.json`

The delta report contains:
- `pattern_summary`: What recurring patterns emerged across Oracle artifacts
- `dossier_deltas`: Per-lane CRUD operations proposed for dossier files
- `doctrine_flags`: Candidate doctrine changes that require human review
- `learning_entries`: Compact learning statements for the learning ledger

### 2. Dossier Patch Payload

Generated by `dossier_updater` from the delta report. Uses the unified patch vocabulary (`set`, `merge`, `append` with slash-selectors) consumed by `version_committer`.

### 3. Learning Ledger Entry

Append-only record tracking what Evolve learned per run pair. Enables cross-run pattern analysis.

Successful Evolve runs persist their durable outputs beside the truth run as `artifacts/evolve_delta_report.json`, `artifacts/evolve_patch_payload.json`, and `artifacts/evolve_input_readiness.json`. The `_last_delta_report.json` and `_last_patch_payload.json` files under `tools/refinement/` remain latest-run debug conveniences, not the Station authority surface. `/station/lab-oracle-evolve` projects the pair-local artifacts so a detached dry-run can be inspected from the same subject/truth pair lens that launched it.

---

## Architecture — Three-Node Spine

```text
Oracle Outputs (4 artifacts + Lab CP2)
        |
        v
  evolve_delta_analyzer
  (Pattern extraction + delta proposal)
        |
        v
  evolve_dossier_updater
  (Patch payload generation)
        |
        v
  evolve_version_committer [TOOL]
  (Atomic dossier write + git commit)
```

### 1. Delta Analyzer

`delta_analyzer` reads all 4 Oracle outputs plus the Lab CP2 and produces the `evolve_delta_report`.

It must:
1. Extract error patterns from `cp2_critique.critique_items[]` grouped by `error_class`
2. Map `OBSERVATION_MISS` errors to dossier gaps (signals that should have been in domain knowledge)
3. Map `SYNTHESIS_BLIND` errors to doctrine candidates (decision rules that failed)
4. Map `PREDICTION_DRIFT` errors to target-specific dossier updates (wrong baseline assumptions)
5. Extract regime learning from `realized_hindsight_brief.driver_classification`
6. Compare Lab CP2 targets vs `ideal_cp2` targets to identify systematic target selection bias
7. Cite every delta to the specific Oracle artifact and field that motivated it

Platform: ChatGPT (extraction and structured reasoning).

### 2. Dossier Updater

`dossier_updater` reads the `evolve_delta_report` and produces a patch payload per affected dossier lane.

It must:
1. Convert each `dossier_deltas[]` entry into the unified patch vocabulary
2. Preserve existing dossier structure (no destructive overwrites of unrelated sections)
3. Validate that every `set` or `merge` op targets a key that exists in the dossier schema
4. For `CREATE` operations, emit `set` with the full new value
5. For `UPDATE` operations, emit `merge` with only the changed fields
6. For `DELETE` operations, emit `set` with `payload: null`

Platform: ChatGPT (constrained output generation).

### 3. Version Committer

`version_committer` is a tool node (no LLM). It applies the patch payload atomically via temp-file + fsync + rename, then commits to git with a structured message.

Implementation: `tools/refinement/version_committer.py` (already implemented).

---

## Dossier Evolution Rules

Dossiers are lane-scoped domain knowledge files under `codex/substrate/dossiers/`.

| Dossier | Lane | Contents |
|---------|------|----------|
| `stock.json` | STOCK | Equity baselines, sector relationships, regime sensitivities |
| `etf.json` | ETF | ETF composition, flow patterns, sector rotation signals |
| `macro.json` | MACRO | Economic regime knowledge, rate sensitivity, leading indicators |
| `oracle_error_taxonomy.json` | SPINE | Error class definitions and historical invariants |
| `oracle_cp2_scope_dossier.json` | SPINE | Oracle CP2 scope boundaries |

Evolution rules:
1. Dossier updates must be lane-scoped. A stock-lane miss updates `stock.json`, not `macro.json`.
2. New entries require both a key and a rationale citing the Oracle source.
3. Stale entries should be flagged for review, not auto-deleted.
4. Regime-dependent entries must include the regime context in which they were observed.
5. Dossiers carry structured knowledge, not raw data or prose narratives.

---

## Doctrine Flag Rules

Some Oracle findings point to operational rule changes rather than domain knowledge updates. These are **doctrine flags** — they go into the delta report but require explicit human/agent review before changing Lab or Oracle doctrine.

Doctrine flag triggers:
1. **Epistemic hierarchy override**: If `cp2_critique` repeatedly shows `NARRATIVE_LED` thesis outperforming `FLOW_LED` in a specific regime, flag for hierarchy adjustment.
2. **Pre-pricing threshold**: If prediction_reconciliation shows systematic over-prediction when news confidence was high, flag for pre-pricing threshold tightening.
3. **Target selection bias**: If ideal_cp2 consistently adds or drops targets that Lab selected, flag for cross_corr v2 target gate adjustment.
4. **Lane reliability shift**: If one lane's miners consistently contribute to OBSERVATION_MISS errors, flag for miner prompt review.

Doctrine flags are NOT auto-applied. They accumulate in the learning ledger until a pattern is clear across multiple runs.

---

## Learning Ledger

The learning ledger (`codex/substrate/dossiers/learning_ledger.jsonl`) is an append-only JSONL file tracking Evolve outputs per run pair.

Each entry:
```json
{
  "run_pair": { "subject_run_id": "...", "truth_run_id": "..." },
  "timestamp": "2026-04-09T...",
  "root_failure_mode": "SYNTHESIS_BLIND",
  "error_class_distribution": { "OBSERVATION_MISS": 2, "SYNTHESIS_BLIND": 1 },
  "dossier_ops_applied": 5,
  "dossier_ops_skipped": 1,
  "doctrine_flags_raised": ["epistemic_hierarchy_override"],
  "learning_statements": [
    "Stock lane consistently missed institutional flow reversals in high-energy regimes",
    "News-led thesis outperformed flow-led in 2 of 3 recent tariff-driven regimes"
  ]
}
```

Cross-run queries against the ledger surface systematic patterns that individual runs cannot reveal.

### Calibration Metrics (v1.1 addition)

When `prediction_reconciliation` data is available, the learning entry should also include:

```json
{
  "calibration": {
    "directional_accuracy": 0.6,
    "mean_absolute_error_pct": 2.3,
    "confidence_calibration": {
      "HIGH": {"predictions": 3, "correct": 2},
      "MEDIUM": {"predictions": 2, "correct": 1},
      "LOW": {"predictions": 1, "correct": 0}
    },
    "regime_accuracy": "goldilocks predicted, reflation realized"
  }
}
```

This enables cross-run analysis of:
- Whether the system is improving over time (directional accuracy trend)
- Whether confidence labels are well-calibrated (HIGH should be >70% accurate)
- Which regime transitions the system handles well vs poorly

---

## Platform Allocation

| Platform | Nodes | Rationale |
|----------|-------|-----------|
| ChatGPT | delta_analyzer, dossier_updater | Extraction precision and constrained output |
| N/A (tool) | version_committer | Deterministic file operations |

Evolve does not use Gemini. The reasoning load is extraction and structured diff generation, which suits ChatGPT's precision.

---

## Hard Fail Conditions

Evolve fails hard when:
1. No paired Oracle run outputs are available
2. `cp2_critique` has no critique_items (nothing to learn from)
3. Delta report proposes a patch to a dossier file that does not exist
4. Patch payload uses ops outside the unified vocabulary (set/merge/append)
5. version_committer encounters a write error (atomic guarantee broken)

---

## Anti-Patterns

1. **Hallucinated learning**: Proposing dossier updates based on general market knowledge rather than specific Oracle findings. Every delta must cite an artifact and field.
2. **Scope creep**: Updating Oracle or Lab node prompts directly. Evolve proposes; agents implement.
3. **Premature doctrine change**: Changing epistemic hierarchy after one run. Doctrine flags must accumulate evidence.
4. **Dossier bloat**: Adding raw data or prose narratives to dossiers. Dossiers carry structured domain knowledge.
5. **Autonomous mutation**: Running version_committer without approval. The approval gate is the contract.

---

## Integration with Pipeline

Evolve runs after Oracle completes a paired run. The seed pipeline can invoke Evolve as a post-Oracle step:

```text
Lab Run (T-n) -> Oracle Run (paired T-n + T) -> Evolve Run (Oracle outputs)
```

The pipeline controller should:
1. Detect Oracle completion (4 durable artifacts present)
2. Invoke Evolve delta_analyzer with Oracle output paths
3. Present delta report for review
4. On approval, invoke dossier_updater + version_committer
5. Append learning ledger entry

---

## Version History

1. v1.0: Initial mission doctrine. Three-node spine with delta report, patch payload, and learning ledger. Dossier-scoped mutations with doctrine flags for operational rule changes.
