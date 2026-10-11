"""
[PURPOSE]
- Teleology: Provide canonical citation extraction, malformed detection, and resolution checking
  for CP artifact text fields (epicentre_thesis, trade_rationale).
- Mechanism: Regex-based citation parser where malformed detection always runs before extraction
  to prevent the valid-looking [1] inside [1-3] from silently passing validation.

[INTERFACE]
- Reads: Text strings and evidence dictionaries (list of dicts with ref_id keys).
- Writes: None (pure computation).
- Fails: Empty text yields empty collections; callers must supply text strings and an iterable evidence collection for validation.

[FLOW]
- detect_malformed_citations: scan for range / CSV / leading-zero citation forms.
- extract_citations: extract unique citation integers using CITATION_RE.
- validate_citations: check every extracted citation resolves against evidence ref_ids.
- When-needed: Open when validating CP artifact citation syntax or evidence ref_id resolution without reopening downstream artifact readers and validators separately.
- Escalates-to: system/lib/artifacts.py::load_artifact_data
- Navigation-group: kernel_lib

[DEPENDENCIES]
- Couples: CP artifact readers must screen malformed citation forms before singleton extraction; ref_id strings use bracketed citation tokens.

[CONSTRAINTS]
- detect_malformed_citations MUST be called before extract_citations in any validation pipeline.
  Rationale: CITATION_RE matches [1] inside [1-3]; running extraction first silently accepts malformed forms.
- Word count for callers: use len(re.findall(r"\\S+", text)) on raw text (do not strip citations).
- This module must remain free of engine, server, and tool imports.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Set

# ---------------------------------------------------------------------------
# Canonical citation regex — individual [N] where N >= 1, no leading zeros.
# ---------------------------------------------------------------------------
CITATION_RE = re.compile(r"\[([1-9]\d*)\]")

# ---------------------------------------------------------------------------
# Malformed citation patterns — detected BEFORE valid extraction.
# ---------------------------------------------------------------------------
_MALFORMED_RANGE_RE = re.compile(r"\[\d+\s*-\s*\d+\]")
_MALFORMED_CSV_RE = re.compile(r"\[\d+(?:\s*,\s*\d+)+\]")
_MALFORMED_LEADING_ZERO_RE = re.compile(r"\[0\d*\]")


def detect_malformed_citations(text: str) -> List[str]:
    """
    [ACTION]
    - Teleology: Catch malformed citation syntax before singleton extraction can silently accept part of an invalid token.
    - Mechanism: Scan the text for range, CSV, and leading-zero citation patterns and return the matched token strings in encounter order.
    - Guarantee: Returns a list of malformed citation tokens or [] when the text is empty or contains no malformed forms.
    - Fails: None.
    - When-needed: Open when a validation pipeline must reject `[1-3]`, `[1, 2]`, or `[01]`-style citations before calling extract_citations().
    - Escalates-to: system/lib/artifacts.py::load_artifact_data
    """
    if not text:
        return []

    found: List[str] = []
    for match in _MALFORMED_RANGE_RE.finditer(text):
        found.append(match.group(0))
    for match in _MALFORMED_CSV_RE.finditer(text):
        found.append(match.group(0))
    for match in _MALFORMED_LEADING_ZERO_RE.finditer(text):
        found.append(match.group(0))
    return found


def extract_citations(text: str) -> Set[int]:
    """
    [ACTION]
    - Teleology: Normalize valid singleton citation tokens into the integer set that downstream resolution checks consume.
    - Mechanism: Apply CITATION_RE to the text and convert every matched citation id into an int with set-based deduplication.
    - Guarantee: Returns a set of citation integers or an empty set when the text is empty or contains no valid singleton citations.
    - Fails: None.
    - When-needed: Open when a caller needs the canonical extraction rule for valid `[N]` citations after malformed syntax has already been screened out.
    - Escalates-to: system/lib/artifacts.py::load_artifact_data
    """
    if not text:
        return set()
    return {int(m) for m in CITATION_RE.findall(text)}


def validate_citations(text: str, evidence: List[Any]) -> List[str]:
    """
    [ACTION]
    - Teleology: Prove that each extracted citation token resolves against the evidence rows accompanying one artifact payload.
    - Mechanism: Extract singleton citations, collect ref_id values from dict-shaped evidence rows, and emit one CITATION_UNRESOLVED error per missing reference.
    - Guarantee: Returns a sorted list of unresolved-citation error strings or [] when the text is empty or every extracted citation resolves.
    - Fails: None.
    - When-needed: Open when a caller needs the exact ref_id resolution rule for `[N]` citations against evidence dictionaries.
    - Escalates-to: system/lib/artifacts.py::load_artifact_data
    """
    if not text:
        return []

    cited = extract_citations(text)
    ref_ids: Set[str] = set()
    for entry in evidence:
        if isinstance(entry, dict):
            ref_id = entry.get("ref_id")
            if ref_id:
                ref_ids.add(str(ref_id))

    errors: List[str] = []
    for n in sorted(cited):
        ref = f"[{n}]"
        if ref not in ref_ids:
            errors.append(f"CITATION_UNRESOLVED: [{n}] not found in evidence ref_ids")
    return errors
