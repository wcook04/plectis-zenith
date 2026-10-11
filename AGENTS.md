# Working in Zenith

Read README.md, docs/architecture.md and program.md. The executable node JSON, loader, engine and schema validators own behavior. Inspect the graph before changing it. Preserve dependencies, mission sibling scope, contract injection, temporal rules and artifact provenance.

Use the standalone CLI from this checkout. Inspect and plan without provider calls; use an explicit provider for execution. Agent packets must go through the native import/validation path. Do not fabricate completed artifacts or call browser providers as an incidental consequence of inspection.

Research work uses the frozen specification and complete trial ledger in `research/`. Change one declared variable per trial; keep the evaluator and data fixed. Failed and rejected trials count. Development selection and final holdout assessment are separate. Never automatically alter live dossiers, prompts or providers from a favorable score.

Read the selected repo-local skill in `.agents/skills/` when applicable. Imported originals live under `third_party/` with source pins and licenses; treat their scripts as optional examples, not as temporal or release authority.

Keep credentials and runtime artifacts out of Git. Feed acquisition is explicit; absent sources remain unavailable. Record requested and actual model, provider, usage and cost. Free-model execution must fail closed if zero-price eligibility cannot be established. Never silently fall back to a paid model.

Run `python -m pytest tests` after changing runtime behavior. Keep synthetic regression fixtures, historical benchmarks and prospective market evidence clearly distinguished. Capture follow-ups in docs/status.md. Commit only owned changes, preserve other work, and review source/data rights before any public release.
