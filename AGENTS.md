# Working in Zenith

Read README.md, docs/architecture.md and program.md. The executable node JSON, loader, engine and schema validators own behavior. Inspect the graph before changing it. Preserve dependencies, mission sibling scope, contract injection, temporal rules and artifact provenance.

For graph learning or diagnosis, read docs/learning-design.md: one trainable forward graph, dated evaluation, and reviewed transitions between versions. Distinguish mechanical facts from causal hypotheses. The current 28-node Lab is the baseline; a smaller replacement graph needs an explicit ablation contract, not a display-only simplification.

Public metadata uses zenith/public_graph.py and the read-only API in zenith/api.py. Follow docs/backend-api.md and docs/frontend-handoff.md. Never replace the allowlisted projection with hydrated CLI inspection or private run state; regenerate data/graph/public-graph.json through scripts/build_demo_data.py.

Use the standalone CLI from this checkout. Inspect and plan without provider calls; use an explicit provider for execution. Agent packets must go through the native import/validation path. Do not fabricate completed artifacts or call browser providers as an incidental consequence of inspection.

Research work uses the frozen specification and complete trial ledger in `research/`. Change one declared variable per trial; keep the evaluator and data fixed. Failed and rejected trials count. Development selection and final holdout assessment are separate. Never automatically alter live dossiers, prompts or providers from a favorable score.

Before freezing a paid cohort, use an excluded-date native compatibility pilot to verify the chosen model against the actual output validators and provider receipt contract. A JSON response alone is insufficient. Preserve rejected pilots and their source revisions; prompt calibration must not rewrite their outputs or weaken acceptance. All probes and study calls within one spending authorization share one immutable budget ledger. Reserve ordinary uncached input costs even when the provider advertises cache discounts.

Read the selected repo-local skill in `.agents/skills/` when applicable. Imported originals live under `third_party/` with source pins and licenses; treat their scripts as optional examples, not as temporal or release authority.

Keep credentials and runtime artifacts out of Git. Feed acquisition is explicit; absent sources remain unavailable. Record requested and actual model, provider, usage and cost. Free-model execution must fail closed if zero-price eligibility cannot be established. Never silently fall back to a paid model.

New paid cohort comparisons require the same exact upstream provider tag in both arms and matching actual-provider receipts. A halted budget cannot be reset or replaced. Explicit operator-authorized HTTP 429 recovery must use the audited recovery command, bound to the exact prior ledger and failed call; retain unknown cost, full reservation and attempt history. Never treat recovery as permission to resend an old run or increase its limits.

Run `python -m pytest tests` after changing runtime behavior. Keep synthetic regression fixtures, historical benchmarks and prospective market evidence clearly distinguished. Capture follow-ups in docs/status.md. Commit only owned changes, preserve other work, and review source/data rights before any public release.
