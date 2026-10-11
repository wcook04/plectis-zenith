"""
[PURPOSE]
- Teleology: Mark the Oracle v1 package as the shared home for deterministic subject/truth comparison tools.
- Mechanism: Package marker only; sibling modules carry the executable tool surfaces.

[INTERFACE]
- Exports: None. Import sibling modules directly for Oracle tool entrypoints.

[FLOW]
- Reads: None.
- Writes: None.

[DEPENDENCIES]
- None.

[CONSTRAINTS]
- Non-goal: This package file does not re-export tool entrypoints or execute Oracle logic.
- When-needed: Open when orienting to Oracle v1 package surfaces and deciding whether to read subject_index, subject_snapshot, or truth_diff_equity next.
- Escalates-to: tools/oracle/subject_index.py::run; tools/oracle/subject_snapshot.py::run; tools/oracle/truth_diff_equity.py::run
- Navigation-group: market_intelligence
"""
