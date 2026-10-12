"""Disposable saved-run fixtures; never touch the repository's real run state."""

import json
from pathlib import Path

import pytest

from zenith.web_runs import RunStore


def write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


@pytest.fixture
def store(tmp_path: Path) -> RunStore:
    root = tmp_path / "runs"
    root.mkdir()
    for run_id, mission, timestamp in [
        ("EARLY.1", "oracle", 10),
        ("LATE_2", "lab", 20),
        ("REAL_JUL20_CONDITIONAL", None, 15),
    ]:
        run = root / run_id
        write(run / "run_summary.json", {
            "timestamp": timestamp,
            "grade": "red",
            "grade_reason": "fixture only",
            "node_outcomes": {"global_measurements_feed": "loaded", "cross_corr": "failure", "private_node": "success"},
        })
        if mission:
            write(run / "zenith_run.json", {"mission": mission})
        else:
            write(run / "conditional_lab.json", {"subject_run": "LATE_2"})
    return RunStore(root, {"global_measurements_feed", "cross_corr"})


def test_list_filter_sort_pagination_and_conditional_lineage(store: RunStore) -> None:
    page = store.list_runs(limit=2)
    assert page["total"] == 3
    assert [item["run_id"] for item in page["runs"]] == ["LATE_2", "REAL_JUL20_CONDITIONAL"]
    assert "private_node" not in page["runs"][0]["node_outcomes"]
    assert store.list_runs(mission="lab", offset=1, limit=1)["runs"][0]["run_id"] == "REAL_JUL20_CONDITIONAL"
    assert store.list_runs(query="early")["runs"][0]["run_id"] == "EARLY.1"
    conditional = page["runs"][1]
    assert (conditional["mission"], conditional["source_kind"], conditional["subject_run"]) == (
        "lab", "conditional_lab", "LATE_2"
    )
    with pytest.raises(ValueError, match="limit"):
        store.list_runs(limit=101)
    with pytest.raises(ValueError, match="mission"):
        store.list_runs(mission="unknown")


def test_large_saved_artifact_and_bounded_attempts(store: RunStore) -> None:
    run = store.runs_root / "LATE_2"
    rows = [{"symbol": f"T{index}", "value": index} for index in range(16000)]
    write(run / "artifacts/global_measurements_feed.json", {
        "status": "success", "timestamp": 22,
        "metadata": {"hydrated_from": "fixture", "input_node_ids": ["cross_corr", "private_node"],
                     "error": None, "unpublished_key": "not surfaced"},
        "data": {"rows": rows}, "unpublished_field": "not surfaced",
    })
    attempts = run / "debug/json_attempts"
    for index in range(1, 5):
        write(attempts / f"global_measurements_feed.attempt_{index:02d}.json", {
            "attempt": index, "status": "error", "error_class": "JSON_PARSE_ERROR",
            "errors": ["bad schema"], "json_error": {"message": "bad JSON"},
            "prompt_snippet": "p" * 9000, "output_text": "o" * 17000,
            "credential": "not surfaced",
        })
    evidence = store.node_evidence("LATE_2", "global_measurements_feed")
    assert evidence["status"] == "loaded"  # recorded status outranks artifact's success
    assert evidence["artifact_bytes"] > 256_000
    assert evidence["artifact_omitted"] is False
    assert len(evidence["artifact"]["data"]["rows"]) == 16000
    assert evidence["artifact"]["metadata"]["input_node_ids"] == ["cross_corr"]
    assert "unpublished_field" not in evidence["artifact"]
    assert [attempt["attempt"] for attempt in evidence["attempts"]] == [2, 3, 4]
    assert evidence["attempts"][0]["prompt_truncated"] is True
    assert evidence["attempts"][0]["output_truncated"] is True
    assert "credential" not in evidence["attempts"][0]
    assert "bad JSON" in evidence["attempts"][0]["json_error"]


def test_missing_malformed_oversize_and_symlinks(store: RunStore, tmp_path: Path) -> None:
    run = store.runs_root / "LATE_2"
    missing = store.node_evidence("LATE_2", "cross_corr")
    assert (missing["artifact"], missing["artifact_error"], missing["artifact_omitted"]) == (
        None, "missing", False
    )
    artifact = run / "artifacts/cross_corr.json"
    artifact.parent.mkdir()
    artifact.write_text("{bad json", encoding="utf-8")
    assert store.node_evidence("LATE_2", "cross_corr")["artifact_error"] == "malformed_json"
    artifact.write_text('{"status":"success","data":{"value":NaN}}', encoding="utf-8")
    assert store.node_evidence("LATE_2", "cross_corr")["artifact_error"] == "malformed_json"
    artifact.write_bytes(b"x" * (8 * 1024 * 1024 + 1))
    too_large = store.node_evidence("LATE_2", "cross_corr")
    assert too_large["artifact_omitted"] and too_large["artifact_bytes"] > 8 * 1024 * 1024
    artifact.unlink()
    outside = tmp_path / "outside.json"
    write(outside, {"status": "success", "data": {"unsafe": True}})
    artifact.symlink_to(outside)
    assert store.node_evidence("LATE_2", "cross_corr")["artifact_error"] == "not_regular_file"
    artifact.unlink()
    (run / "artifacts").rmdir()
    (run / "artifacts").symlink_to(tmp_path, target_is_directory=True)
    assert store.node_evidence("LATE_2", "cross_corr")["artifact"] is None
    with pytest.raises(ValueError, match="unknown node"):
        store.node_evidence("LATE_2", "../private_node")
    with pytest.raises(ValueError, match="run_id"):
        store.node_evidence("..", "cross_corr")
    with pytest.raises(FileNotFoundError):
        store.node_evidence("NO_SUCH_RUN", "cross_corr")
    bad_run = store.runs_root / "BAD_RUN"
    bad_run.mkdir()
    (bad_run / "run_summary.json").write_text("{", encoding="utf-8")
    with pytest.raises(ValueError, match="malformed_json"):
        store.node_evidence("BAD_RUN", "cross_corr")
    (store.runs_root / "LINKED").symlink_to(run, target_is_directory=True)
    assert "LINKED" not in [item["run_id"] for item in store.list_runs()["runs"]]


def test_markerless_and_invalid_marker_summaries_are_not_called_native(store: RunStore) -> None:
    for run_id, marker in (("NO_MARKER", None), ("BAD_MARKER", {"mission": "unrecognized"}),
                           ("BAD_TYPE", {"mission": ["lab"]})):
        run = store.runs_root / run_id
        write(run / "run_summary.json", {"node_outcomes": {"cross_corr": "success"}})
        if marker is not None:
            write(run / "zenith_run.json", marker)
        with pytest.raises(ValueError, match="marker"):
            store.node_evidence(run_id, "cross_corr")
    assert store.list_runs()["total"] == 3
