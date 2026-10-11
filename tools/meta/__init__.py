"""
[PURPOSE]
- Teleology: Mark the package boundary for repo-local meta tooling under `tools.meta`.
- Mechanism: Package marker only; importers descend into subpackages such as `apply`, `bridge`, `factory`, and `annex` for executable behavior.

[INTERFACE]
- Exports: None declared here; consumers import concrete modules from `tools.meta.*`.
- Navigation-group: meta_tooling

[FLOW]
- Orders: Import resolution lands here before descending into leaf modules that provide the actual CLI and library surfaces.
- When-needed: Open when confirming the package boundary for `tools.meta.*` imports or assigning files to the `meta_tooling` cohort.
- Escalates-to: codex/standards/std_python.py; tools/meta/annex/batch_acquire.py; tools/meta/annex/research_prompt.py

[DEPENDENCIES]
- None.

[CONSTRAINTS]
- Non-goal: This package marker does not define runtime behavior, CLI entrypoints, or shared initialization side effects.
"""
