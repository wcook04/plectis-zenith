"""A citation remains a reviewed source/claim binding after export or editing."""
import hashlib
import json

import pytest

from zenith.web_content import paper_citations, reference_bibliography


def source_record(excerpt):
    return {"id": "example", "title": "A measured method", "authors": ["A. Author"],
            "author_label": "A. Author", "venue": "Proceedings", "year_label": "2024",
            "url": "https://example.org/paper/v2", "verification_state": "source_verified",
            "application": "Background only; no local replication.",
            "reviewed_source": {"edition": "v2", "sha256": "a" * 64},
            "source_locators": [{"id": "method", "locator": "Section 2",
                                 "supports": "A bounded method.", "boundary": "No transfer result."}],
            "artifact_links": [{"path": "paper/zenith.tex", "expected_text": excerpt,
                                "excerpt_sha256": hashlib.sha256(excerpt.encode()).hexdigest(),
                                "source_locator_ids": ["method"]}]}


def write_registry(root, record):
    (root / "paper").mkdir(exist_ok=True)
    (root / "paper/references.json").write_text(json.dumps(
        {"schema": "zenith_reviewed_references_v1", "sources": [record]}))


def test_optional_locator_and_moved_claim_preserve_exact_review(tmp_path):
    excerpt = r"A bounded claim~\cite[Section 2]{example}."
    record = source_record(excerpt)
    write_registry(tmp_path, record)
    tex = "% A commented unknown citation \\cite{unreviewed}\n\n" + excerpt + "\n" + reference_bibliography([record])
    citations, _ = paper_citations(tmp_path, tex)
    assert citations[0]["used_at"] == [{"line": 3, "locator": "Section 2"}]
    assert citations[0]["review"]["reviewed_source"]["edition"] == "v2"
    assert citations[0]["review"]["source_locators"][0]["boundary"] == "No transfer result."


@pytest.mark.parametrize("mutation, message", [
    (lambda tex: tex.replace("A bounded claim", "A general transfer claim"), "Stale manuscript binding"),
    (lambda tex: "An extra claim \\cite{example}. " + tex, "Unreviewed citation use"),
    (lambda tex: "An unknown source \\cite{missing}.\n" + tex, "Unknown bibliography key"),
    (lambda tex: tex.replace("Proceedings, 2024", "Proceedings, 2025"), "Bibliography differs"),
])
def test_rejects_changed_claims_and_unreviewed_citations(tmp_path, mutation, message):
    excerpt = r"A bounded claim~\cite{example}."
    record = source_record(excerpt)
    write_registry(tmp_path, record)
    tex = excerpt + "\n" + reference_bibliography([record])
    with pytest.raises(ValueError, match=message):
        paper_citations(tmp_path, mutation(tex))


@pytest.mark.parametrize("field, value, message", [
    ("excerpt_sha256", "b" * 64, "Stale manuscript binding"),
    ("source_locator_ids", ["absent"], "Unknown source support"),
    ("path", "/private/source.tex", "Stale manuscript binding"),
])
def test_rejects_false_or_private_bindings(tmp_path, field, value, message):
    excerpt = r"A bounded claim~\cite{example}."
    record = source_record(excerpt)
    record["artifact_links"][0][field] = value
    write_registry(tmp_path, record)
    with pytest.raises(ValueError, match=message):
        paper_citations(tmp_path, excerpt + "\n" + reference_bibliography([record]))
