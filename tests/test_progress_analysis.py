"""Source binding and paired accounting for the prospective progress campaign."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.analyze_progress_campaign import analyze, digest


ARMS = ("direct_adaptive", "direct_masked", "fixed", "repair_only")


def put(path: Path, value) -> None:
    path.write_text(json.dumps(value, indent=2) + "\n")


def score(correct: int) -> dict:
    rows = [{"input": {"case": i}, "expected": {"result": i},
             "correct": i < correct, "error": None} for i in range(3)]
    return {"correct": correct, "total": 3, "errors": 0, "rows": rows}


def fixture(folder: Path, *, shared: bool = False) -> Path:
    records = []
    tasks = {}
    for task_id, source, adaptive, masked in (
        ("native-lru-0", "lru-0", 3, 2),
        ("native-sqlite-0", "sqlite-0", 1, 2),
    ):
        parent = {"source": "parent " + task_id}
        arms = {}
        for arm in ARMS:
            receipts = ([{"slot": 1, "query": {"x": 1},
                          "query_error": "Duplicate of an example or earlier query"},
                         {"slot": 2, "query": {"x": 2}, "expected": {"ok": True},
                          "parent_error": None, "verified_counterexample": False}]
                        if arm.startswith("direct") else [])
            if shared and arm.startswith("direct"):
                receipts = [{**row, "turn": 1} for row in receipts]
            investigation = {"receipts": receipts, "native_probes": int(bool(receipts)),
                             "query_attempts": int(bool(receipts)),
                             "query_units": int(bool(receipts)), "detected": False}
            if shared and arm in ("direct_adaptive", "direct_masked"):
                investigation["turns"] = [{"turn": 1,
                    "call_id": task_id + "-direct-shared-turn-1",
                    "envelope": {"prompt": {"turn": 1}},
                    "raw": '{"queries":[],"note":null}', "delivery_error": None}]
                visible = (receipts if arm == "direct_adaptive" else
                           [{k: row[k] for k in ("slot", "turn", "query") if k in row}
                            for row in receipts])
                investigation["turns"].append({"turn": 2,
                    "call_id": task_id + "-" + arm + "-turn-2",
                    "envelope": {"prompt": {"turn": 2, "receipts": visible,
                                            "outcomes_available": arm == "direct_adaptive"}},
                    "raw": '{"queries":[],"note":null}', "delivery_error": None})
            arms[arm] = {"investigation": investigation,
                         "candidate": {"source": "candidate " + arm},
                         "selected": {"source": "selected " + arm,
                                      "candidate_selected": True}}
        records.append({"task_id": task_id, "source_id": source,
                        "parent": parent, "arms": arms})
        tasks[task_id] = {"source_id": source, "parent": score(1),
                          "arms": {arm: {"selected": score(
                              adaptive if arm == "direct_adaptive" else
                              masked if arm == "direct_masked" else 1)}
                              for arm in ARMS}}
    dataset = {"tasks": [{"id": r["task_id"], "source_id": r["source_id"],
                          "confirmation": [{"input": row["input"], "expected": row["expected"]}
                                           for row in score(1)["rows"]]}
                         for r in records]}
    protocol = {"arms": list(ARMS), "dataset_sha256": digest(dataset),
                "shared_direct_first_turn": shared}
    frozen = {"complete": True, "failures": [], "records": records,
              "protocol_sha256": digest(protocol)}
    put(folder / "protocol.json", protocol)
    put(folder / "datasets.json", dataset)
    put(folder / "frozen.json", frozen)
    put(folder / "frozen-receipt.json", {"frozen_sha256": digest(frozen)})
    put(folder / "confirmation.json", {"partition": "confirmation",
                                        "frozen_sha256": digest(frozen), "tasks": tasks})
    put(folder / "confirmation-selection.json", {
        "frozen_sha256": digest(frozen),
        "selection": {r["task_id"]: {arm: digest(r["arms"][arm]["selected"])
                                      for arm in ARMS} for r in records}})
    put(folder / "billing.json", {"entries": [
        {"node_id": "native-lru-0-parent", "cost": "0.001",
         "usage": {"prompt_tokens": 10, "completion_tokens": 20,
                   "completion_tokens_details": {"reasoning_tokens": 2}}},
        {"node_id": "native-lru-0-direct_adaptive-turn1", "cost": None,
         "usage": {"prompt_tokens": 11, "completion_tokens": 21,
                   "completion_tokens_details": {"reasoning_tokens": 0}}},
    ]})
    if shared:
        billing = json.loads((folder / "billing.json").read_text())
        billing["entries"][1]["node_id"] = "native-lru-0-direct-shared-turn-1"
        put(folder / "billing.json", billing)
    return folder


def test_parent_paired_family_summary_and_unknown_charge(tmp_path):
    report = analyze(fixture(tmp_path))
    comparison = report["comparisons"]["direct_adaptive_minus_direct_masked"]
    assert comparison["total_correct_difference"] == 0
    assert comparison["by_family"]["lru"]["mean_per_parent"] == 1
    assert comparison["by_family"]["sqlite"]["mean_per_parent"] == -1
    assert comparison["family_macro_mean_per_parent"] == 0
    assert report["panel_summary"]["confirmation"]["overall"]["direct_adaptive"]["correct"] == 4
    assert report["panel_summary"]["confirmation"]["overall"]["direct_masked"]["correct"] == 4
    assert report["delivery"]["native-lru-0"]["direct_adaptive"]["duplicate"] == 1
    assert report["billing"]["unknown_cost_calls"] == 1
    assert report["billing"]["tasks"]["native-lru-0"]["direct_adaptive"]["total_cost_usd"] is None
    assert report["billing"]["tasks"]["native-lru-0"]["parent"]["known_cost_usd"] == "0.001"


def test_shared_first_turn_is_charged_once_and_required_by_protocol(tmp_path):
    folder = fixture(tmp_path, shared=True)
    report = analyze(folder)
    assert report["feedback_isolation_status"].startswith("shared_first_turn_verified")
    assert report["paired_second_turn_count"] == 2
    assert report["billing"]["tasks"]["native-lru-0"]["shared_direct"]["calls"] == 1
    assert report["billing"]["standalone_arm_cost_by_task"]["native-lru-0"]["direct_adaptive"]["components"] == [
        "parent", "direct_adaptive", "shared_direct"]
    frozen = json.loads((folder / "frozen.json").read_text())
    frozen["records"][0]["arms"]["direct_masked"]["investigation"]["turns"][0]["raw"] = "changed"
    put(folder / "frozen.json", frozen)
    put(folder / "frozen-receipt.json", {"frozen_sha256": digest(frozen)})
    panel = json.loads((folder / "confirmation.json").read_text())
    panel["frozen_sha256"] = digest(frozen)
    put(folder / "confirmation.json", panel)
    selection = json.loads((folder / "confirmation-selection.json").read_text())
    selection["frozen_sha256"] = digest(frozen)
    put(folder / "confirmation-selection.json", selection)
    with pytest.raises(ValueError, match="share exact first action"):
        analyze(folder)


def test_masked_prompt_cannot_leak_native_legality(tmp_path):
    folder = fixture(tmp_path, shared=True)
    frozen = json.loads((folder / "frozen.json").read_text())
    prompt = frozen["records"][0]["arms"]["direct_masked"]["investigation"]["turns"][1]["envelope"]["prompt"]
    prompt["receipts"][0]["query_error"] = "native decided query was illegal"
    put(folder / "frozen.json", frozen)
    put(folder / "frozen-receipt.json", {"frozen_sha256": digest(frozen)})
    panel = json.loads((folder / "confirmation.json").read_text())
    panel["frozen_sha256"] = digest(frozen)
    put(folder / "confirmation.json", panel)
    selection = json.loads((folder / "confirmation-selection.json").read_text())
    selection["frozen_sha256"] = digest(frozen)
    put(folder / "confirmation-selection.json", selection)
    with pytest.raises(ValueError, match="leaks outcome"):
        analyze(folder)


@pytest.mark.parametrize("mutate,expected", [
    ("score", "Panel aggregate"),
    ("selection", "selection receipt"),
    ("freeze", "Frozen construction receipt"),
])
def test_tampering_cannot_create_a_measured_gain(tmp_path, mutate, expected):
    folder = fixture(tmp_path)
    if mutate == "score":
        path = folder / "confirmation.json"
        value = json.loads(path.read_text())
        value["tasks"]["native-lru-0"]["arms"]["direct_adaptive"]["selected"]["correct"] = 2
    elif mutate == "selection":
        path = folder / "confirmation-selection.json"
        value = json.loads(path.read_text())
        value["selection"]["native-lru-0"]["direct_adaptive"] = "0" * 64
    else:
        path = folder / "frozen.json"
        value = json.loads(path.read_text())
        value["records"][0]["parent"]["source"] = "changed"
    put(path, value)
    with pytest.raises(ValueError, match=expected):
        analyze(folder)


def test_panel_obligations_must_match_bound_dataset(tmp_path):
    folder = fixture(tmp_path)
    panel_path = folder / "confirmation.json"
    panel = json.loads(panel_path.read_text())
    task = panel["tasks"]["native-lru-0"]
    task["parent"]["rows"][0]["expected"] = {"wrong": True}
    for arm in ARMS:
        task["arms"][arm]["selected"]["rows"][0]["expected"] = {"wrong": True}
    put(panel_path, panel)
    with pytest.raises(ValueError, match="Panel obligations differ from bound dataset"):
        analyze(folder)


def test_old_complete_archive_remains_a_descriptive_input():
    root = Path(__file__).resolve().parents[1]
    archive = root / "examples/conformance/ling-full-v3b"
    report = analyze(archive)
    assert report["parents"] == 6
    assert report["panel_summary"]["confirmation"]["overall"]["fixed"]["correct"] == 239
    assert report["panel_summary"]["confirmation"]["overall"]["ordinary"]["correct"] == 216
    assert report["comparisons"] == {}
