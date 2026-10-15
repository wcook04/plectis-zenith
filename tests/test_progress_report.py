"""Source custody and conservative projection for the new Progress campaign."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil

import pytest

from scripts.build_progress_report import (
    ROOT, build, cross_stage_audit, headline, publish_prospective, qualification_checks,
    primary_parent_signs, render_markdown, verified_learner, verify_prospective,
)


def put(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n")


def hash_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_missing_studies_are_pending_without_invented_measurement(tmp_path):
    report = build(tmp_path)
    assert report["status"] == "pending"
    assert report["conformance_studies"] == []
    assert "no published" in report["summary"]
    assert "no published" in render_markdown(report)


@pytest.mark.parametrize("version,freeze_name,source_name", [
    ("v4", "prospective-freeze.json", "prospective-source"),
    ("v5", "prospective-v5-freeze.json", "prospective-v5-source"),
])
def test_prospective_publication_preserves_exact_frozen_bytes(
        tmp_path, version, freeze_name, source_name):
    external = tmp_path / "external"
    root = tmp_path / "repo"
    source = external / source_name / "docs" / "protocol.md"
    source.parent.mkdir(parents=True)
    source.write_text("Frozen protocol.\n")
    freeze = {
        "schema": "zenith_progress_prospective_freeze_v1",
        "files": {"docs/protocol.md": hash_file(source)},
        "qualification": {"protocol_sha256": "a", "dataset_sha256": "b", "maximum_model_calls": 36},
        "diagnostic": {"protocol_sha256": "c", "dataset_sha256": "d", "maximum_model_calls": 144},
    }
    if version == "v5":
        freeze["qualification"]["seed"] = 11
        freeze["diagnostic"]["seed"] = 12
        base = external / source_name / "work/progress-assimilation-20261014"
        admission_path = base / "v5-admission-test-receipt.json"
        put(admission_path, {"schema": "zenith_v5_admission_test_receipt_v1",
                             "before_v5_inference": True, "result": "5 passed in 0.1s",
                             "admitted": ["str.join", "chr", "LShift", "RShift"],
                             "files": {}})
        selection_path = base / "v5-panel-disjointness-selection.json"
        put(selection_path, {"criterion": "Exact-input panel disjointness only; before inference.",
                             "selected_seeds": {"qualification": 11, "diagnostic": 12},
                             "candidates": [
                                 {"stage": "qualification", "seed": 11, "accepted": True,
                                  "overlap": {"lru": 0}},
                                 {"stage": "diagnostic", "seed": 12, "accepted": True,
                                  "overlap": {"lru": 0}},
                             ]})
        freeze["files"]["work/progress-assimilation-20261014/v5-admission-test-receipt.json"] = hash_file(admission_path)
        freeze["files"]["work/progress-assimilation-20261014/v5-panel-disjointness-selection.json"] = hash_file(selection_path)
    put(external / freeze_name, freeze)
    folder = publish_prospective(external, root, version)
    assert (folder / "source/docs/protocol.md").read_bytes() == source.read_bytes()
    assert verify_prospective(root, version)["freeze"] == freeze
    (folder / "source/docs/protocol.md").write_text("Changed after freeze.\n")
    with pytest.raises(ValueError, match="Prospective publication changed"):
        verify_prospective(root, version)


def test_learner_receipt_is_separate_and_detects_changed_results(tmp_path):
    learner = verified_learner(ROOT)
    assert learner["ordinary_minus_generic_acquisition_source_calls"] == 16
    assert learner["native_configurations"] == 8
    relative = Path("examples/continuation-memory/witness-preserving-v1")
    shutil.copytree(ROOT / relative, tmp_path / relative)
    # The published manifest also binds maintained source and test files.
    for name in ("research/continuation_learning.py", "scripts/demo_continuation_learning.py",
                 "tests/test_continuation_learning.py"):
        destination = tmp_path / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, destination)
    result_path = tmp_path / relative / "results.json"
    result_path.write_text("{}\n")
    with pytest.raises(ValueError, match="Learner source custody mismatch"):
        verified_learner(tmp_path)


def test_qualification_gate_requires_actual_second_legal_question(tmp_path):
    folder = tmp_path / "qualification"
    frozen = {"records": [{"source_id": family + "-0", "arms": {
        arm: {"selected": {"candidate_selected": True,
                           "development": {"total": 1, "errors": 0}},
              "investigation": {"receipts": ([
                  {"policy_error": "selector failed", "verified_counterexample": False}
              ] if family == "lru" and arm == "direct_adaptive" else [])}}
        for arm in ("direct_batch", "direct_adaptive", "direct_masked")}}
        for family in ("lru", "sqlite", "utf8")]}
    put(folder / "frozen.json", frozen)
    analysis = {
        "delivery_summary_by_family": {
            family: {arm: {"valid": 1} for arm in
                     ("direct_batch", "direct_adaptive", "direct_masked")}
            for family in ("lru", "sqlite", "utf8")
        },
        "paired_second_turn_count": 1,
        "paired_second_distinct_legal_count": 0,
    }
    gate = qualification_checks(folder, analysis, require_executable_repair=True)
    assert not gate["passed"]
    assert not gate["checks"]["paired_second_turn_with_distinct_legal_proposals"]
    assert gate["misattributed_investigator_errors"] == 0
    analysis["paired_second_distinct_legal_count"] = 1
    assert qualification_checks(folder, analysis, require_executable_repair=True)["passed"]
    frozen["records"][0]["arms"]["direct_adaptive"]["investigation"]["receipts"][0][
        "verified_counterexample"] = True
    put(folder / "frozen.json", frozen)
    assert not qualification_checks(folder, analysis, require_executable_repair=True)["passed"]
    frozen["records"][0]["arms"]["direct_adaptive"]["investigation"]["receipts"][0][
        "verified_counterexample"] = False
    for item in frozen["records"][2]["arms"].values():
        item["selected"]["candidate_selected"] = False
    put(folder / "frozen.json", frozen)
    assert not qualification_checks(folder, analysis, require_executable_repair=True)["checks"][
        "executable_repair_candidate_each_contract"]


def test_headline_uses_measured_pair_and_controls_without_pooling():
    study = {
        "version": "v5", "stage": "diagnostic",
        "panel_summary": {"confirmation": {"overall": {
            "direct_adaptive": {"correct": 61, "total": 96},
            "direct_masked": {"correct": 62, "total": 96},
            "fixed": {"correct": 70, "total": 96},
            "repair_only": {"correct": 60, "total": 96},
        }}},
        "comparisons": {"direct_adaptive_minus_direct_masked": {
            "total_correct_difference": -1}},
    }
    text = headline([study])
    assert "61/96" in text and "62/96" in text and "70/96" in text
    assert "paired difference -1" in text
    assert "three authored native contracts" in text


def test_primary_pair_aggregates_parent_episodes_not_case_rows():
    comparison = {"paired_parents": {
        "one": {"adaptive_minus_reference_correct": 7, "denominator": 48},
        "two": {"adaptive_minus_reference_correct": -2, "denominator": 48},
        "three": {"adaptive_minus_reference_correct": 0, "denominator": 48},
    }}
    assert primary_parent_signs(comparison) == {
        "better": 1, "tied": 1, "worse": 1, "range": [-2, 7],
    }


def test_cross_stage_audit_distinguishes_parent_repetition_from_panel_overlap(tmp_path):
    for name, query in (("progress-qualification-v4", 3),
                        ("progress-qualification-v5", 1),
                        ("progress-diagnostic-v5", 2)):
        folder = tmp_path / "examples/conformance" / name
        put(folder / "frozen.json", {"records": [{"parent": {
            "source": "same generated source", "prompt_sha256": "same prompt"}}]})
        put(folder / "datasets.json", {"tasks": [{"source_id": "lru-0",
            "screen": [{"input": {"q": query}}],
            "confirmation": [{"input": {"q": query + 10}}]}]})
    audit = cross_stage_audit(tmp_path)
    assert audit["shared_unique_parent_source_hashes"] == 1
    assert audit["shared_unique_parent_prompt_hashes"] == 1
    assert audit["later_query_overlap_by_contract"]["lru"]["any_later_panel"] == 0
    assert audit["v4_exposed_query_overlap_by_v5_stage"]["qualification"]["lru"]["any_later_panel"] == 0


def test_v4_forfeiture_is_retained_without_treating_legacy_gate_as_success():
    report = build(ROOT)
    old = next(row for row in report["conformance_studies"]
               if row["id"] == "progress-qualification-v4")
    assert old["version"] == "v4" and old["stage"] == "qualification"
    assert old["forfeited"] is True
    assert old["actual_calls"] == 34
    assert old["reported_cost_usd"] == "0.02961306"
    assert old["qualification"]["mechanical_delivery_passed"] is True
    assert old["qualification"]["passed"] is False
    assert old["qualification"]["host_admission_witnesses"] == 4
    assert sum(sum(errors.values()) for errors in
               old["repair_error_counts_by_contract"]["utf8"].values()) == 6
    assert "forfeited engineering" in report["claim_boundary"]


def test_v5_public_qualification_passes_source_bound_four_part_gate():
    report = build(ROOT)
    stage = next(row for row in report["conformance_studies"]
                 if row["id"] == "progress-qualification-v5")
    assert stage["version"] == "v5" and stage["stage"] == "qualification"
    assert stage["qualification"]["passed"] is True
    assert all(stage["qualification"]["checks"].values())
    assert stage["qualification"]["paired_second_distinct_legal_count"] == 2
    assert stage["actual_calls"] == 36
    assert stage["reported_cost_usd"] == "0.03058272"
    assert stage["unknown_cost_calls"] == 0


@pytest.fixture
def funding_fixture(tmp_path):
    """Use the actual immutable public prefix; no inference or native rescoring."""
    from scripts.build_progress_report import FUNDING_AMENDMENT, RESERVATION_STOP
    source = ROOT / RESERVATION_STOP
    if not source.exists():
        pytest.skip("Funding prefix not published in this checkout")
    original = tmp_path / RESERVATION_STOP
    shutil.copytree(source, original)
    final = tmp_path / "examples/conformance/progress-diagnostic-v5"
    shutil.copytree(source, final)
    receipt_path = tmp_path / FUNDING_AMENDMENT
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ROOT / FUNDING_AMENDMENT, receipt_path)
    receipt = json.loads(receipt_path.read_text())
    protocol_path = final / "protocol.json"
    protocol = json.loads(protocol_path.read_text())
    protocol["max_cost_usd"] = receipt["amended_cap_usd"]
    put(protocol_path, protocol)
    prospective = verify_prospective(ROOT, "v5")
    return tmp_path, final, protocol, prospective


def test_funding_amendment_preserves_original_freeze_and_reuses_settled_prefix(funding_fixture):
    from scripts.build_progress_report import verify_funding_amendment
    root, folder, protocol, prospective = funding_fixture
    amendment = verify_funding_amendment(root, folder, protocol, prospective)
    assert amendment["prior_paid_attempts"] == 40
    assert amendment["prior_reported_cost_usd"] == "0.05197758"
    assert amendment["original_cap_usd"] == "0.60"
    assert amendment["amended_cap_usd"] == "4"
    assert amendment["original_protocol_sha256"] == prospective["freeze"]["diagnostic"]["protocol_sha256"]


@pytest.mark.parametrize("change", ["scientific_field", "prior_response", "prior_billing", "prior_ids", "opened_panel", "dataset"])
def test_funding_amendment_rejects_changes_beyond_financial_cap(funding_fixture, change):
    from scripts.build_progress_report import FUNDING_AMENDMENT, verify_funding_amendment
    root, folder, protocol, prospective = funding_fixture
    receipt = json.loads((root / FUNDING_AMENDMENT).read_text())
    if change == "scientific_field":
        protocol["reasoning_effort"] = "medium"
        put(folder / "protocol.json", protocol)
        receipt["amended_protocol_sha256"] = hash_file(folder / "protocol.json")
    elif change == "prior_response":
        path = next((folder / "responses").glob("*.json"))
        path.write_text(path.read_text() + " ")
    elif change == "prior_billing":
        billing = json.loads((folder / "billing.json").read_text())
        billing["entries"][0]["cost"] = "0"
        put(folder / "billing.json", billing)
    elif change == "prior_ids":
        receipt["prior_call_ids"] = []
    elif change == "opened_panel":
        receipt["terminal_partial_replay"]["protected_partitions"] = ["screen"]
    else:
        receipt["dataset_sha256"] = "0" * 64
    put(root / FUNDING_AMENDMENT, receipt)
    with pytest.raises(ValueError, match="Funding"):
        verify_funding_amendment(root, folder, protocol, prospective)


def test_passed_qualification_with_no_diagnostic_is_explicitly_pending(tmp_path, monkeypatch):
    from scripts import build_progress_report as publication
    monkeypatch.setattr(publication, 'verify_prospective', lambda *args: None)
    monkeypatch.setattr(publication, 'verified_learner', lambda *args: None)
    def observed(root, version, stage, name, *args):
        if (version, stage) != ('v5', 'qualification'):
            return None
        return {'id':name, 'version':version, 'stage':stage,
                'manifest_sha256':'fixture', 'qualification':{'passed':True}}
    monkeypatch.setattr(publication, 'observed_study', observed)
    report = publication.build(tmp_path)
    assert report['status'] == 'diagnostic_pending'
    assert 'no v5 twelve-parent diagnostic result is published' in report['summary']
