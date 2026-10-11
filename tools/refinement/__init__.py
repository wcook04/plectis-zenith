"""
[PURPOSE]
- Teleology: Mark tools.refinement as the package boundary for dossier evolution and versioned refinement helpers.
- Mechanism: Provide a package-level routing surface only; concrete runtime behavior lives in sibling modules.

[INTERFACE]
- Exports: None.
- Reads: None.
- Writes: None.

[FLOW]
- When-needed: Open when a navigation pass has landed on the refinement package boundary and needs the next concrete module to inspect.
- Escalates-to: tools/refinement/run_evolve.py; tools/refinement/version_committer.py

[DEPENDENCIES]
- None.

[CONSTRAINTS]
- Non-goal: This package marker does not implement refinement logic or re-export a stable public API surface.
- Navigation-group: diff_refinement
"""
