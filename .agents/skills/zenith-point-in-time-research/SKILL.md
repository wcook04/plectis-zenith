---
name: zenith-point-in-time-research
description: Audit observable-time, vintage, lineage and execution-time boundaries before Zenith forward research or historical evaluation. Use for feed admission, factor/data joins, leakage review and temporal availability claims.
compatibility: Repository-local Zenith CLI and Python standard library; imported illustrative scripts are disabled.
---

# Zenith point-in-time research

Read `AGENTS.md`, `docs/skills.md`, and the selected native graph plan first.
The retained method is in
`third_party/skills/arthera/point-in-time-research/`; provenance and license
are in `third_party/skills/import_manifest.json`. Its original SKILL.md is
reference material. Use this adapter's native directions.

1. Inspect available graph and contracts with `python -m zenith missions`,
   `python -m zenith plan lab`, `python -m zenith inspect <node-id>`, and
   `python -m zenith validate`. Use IDs emitted by the plan. Read the exact
   selected node's input/output contracts before preparing a packet.
   `system/lib/schema_validator.py` supplies the engine's CP1/CP2,
   Oracle-artifact and evidence-ID checks. The `validate` CLI checks graph
   topology; neither it nor schema acceptance certifies a missing vintage
   or timestamp.
2. Establish the information set: pinned source/version/hash, decision as-of,
   observed publication or acceptance timestamp with timezone and precision,
   revision/version interval, and identifier/universe mapping valid at as-of.
   Period end alone is not publication time; latest revised data is not the
   version historically known.
3. For an execution-aware claim, additionally require a named/versioned
   exchange calendar, session boundary and execution lag. A weekday offset
   is not an exchange calendar. Every derived fact inherits the latest
   availability of its parents; retain parent evidence IDs.
4. Keep realized truth outside Lab input/context. Oracle receives an explicit
   subject/truth pair. Label unknown time precision, unavailable vintages and
   excluded rows; never fill them from hindsight. If the current native
   contract cannot represent a required field, report that limitation and
   withhold the stronger PIT/tradability claim.
5. Preserve the native validation result and evidence/exclusion references in
   the run receipt. Schema success alone does not establish temporal fidelity.

For the UCI demonstration, `benchmark.run.load_samples` enforces source hash,
future-feature exclusion, independent labels and a purged split. Exact
historical publication timestamps and corporate actions remain unverified;
retain those limits from `benchmark/README.md` in any result.

Do not run the upstream `information_set_compare.py`, install numpy/pandas,
or invoke Aria slash commands as part of normal Zenith operation. Its
date-only, weekday-based A–D example cannot certify strict timestamp or
exchange-calendar correctness. Use the native scientific study ledger for
controlled temporal-method comparisons; change one declared definition per
trial while holding the other inputs fixed.
