"""Native client-workflow pilot; no acquired policy or independent-transfer claim."""

from copy import deepcopy

import pytest

from research.client_investigation_tasks import (
    ProbeOracle, heldout_queries, model_visible_receipt, prepare_task,
    public_family_spec, public_task, score, task_ids, validate_query,
)


def test_unfiltered_public_tasks_hide_implementation_and_panel():
    assert len(task_ids()) == 10
    assert len(task_ids("batch")) == len(task_ids("transfer")) == 5
    for task_id in task_ids():
        view = public_task(task_id)
        assert set(view) == {"id", "family", "contract", "query_shape",
                             "example", "probe_limit"}
        assert view["example"]["reference"] == view["example"]["client"]
        assert set(view["example"]) == {"query", "reference", "client", "discrepancy"}
        assert view["probe_limit"] == 6
        assert "savepoint" not in str(view).lower()
        assert "whole_rollback" not in str(view).lower()


def test_public_grammar_is_complete_and_benign_views_do_not_fingerprint_mode():
    for family in ("batch", "transfer"):
        prepared = [prepare_task(task_id) for task_id in task_ids(family)]
        baseline = deepcopy(prepared[0]["public"])
        baseline.pop("id")
        for task_id, item in zip(task_ids(family), prepared, strict=True):
            public = deepcopy(item["public"])
            assert public_task(task_id) == public
            public.pop("id")
            assert public == baseline
            full = item["audit"]["example_receipt"]
            assert full["cost"]["reference_calls"] == full["cost"]["client_calls"] == 1
            assert public["example"] == model_visible_receipt(full)
            assert "source_sha256" not in str(public)
            assert "reference_sql" not in str(public)
        grammar = baseline["query_shape"]
        assert all(key in grammar for key in ("outer", "initial", "steps", "steps_item", "continuation"))
        if family == "batch":
            assert "0..4" in grammar["initial"] and "1..10" in grammar["steps_item"]
        else:
            assert "2..4" in grammar["initial"] and "1..9" in grammar["steps_item"]


def test_prospective_family_spec_is_static_and_contains_no_target_evidence(monkeypatch):
    import research.client_investigation_tasks as tasks

    monkeypatch.setattr(tasks, "ProbeOracle", lambda *_: (_ for _ in ()).throw(AssertionError("native call")))
    spec = public_family_spec("transfer")
    assert set(spec) == {"family", "contract", "query_shape", "probe_limit"}
    assert spec["family"] == "transfer" and spec["probe_limit"] == 6
    assert "2..4" in spec["query_shape"]["initial"]
    assert not any(key in spec for key in ("id", "example", "source_sha256", "reference"))
    with pytest.raises(ValueError):
        public_family_spec("unknown")


def test_failed_import_is_batch_atomic_and_caller_can_continue_then_rollback():
    query = {"outer": True, "initial": [4], "steps": [[5, 5], [7]],
             "continuation": 6}
    correct = ProbeOracle("batch-k4").ask(query)
    assert not correct["discrepancy"]
    result = correct["reference"]
    assert result["steps"] == [
        {"ok": False, "state": [4], "transaction_open": True},
        {"ok": True, "state": [4, 7], "transaction_open": True},
    ]
    assert result["continuation_ok"]
    assert result["state_before_caller_rollback"] == [4, 6, 7]
    assert result["state_after_caller_rollback"] == []
    partial = ProbeOracle("batch-a7").ask(query)
    assert partial["discrepancy"]
    assert partial["client"]["steps"][0]["state"] == [4, 5]


def test_whole_rollback_and_premature_commit_damage_caller_ownership():
    failed = {"outer": True, "initial": [4], "steps": [[5, 5]],
              "continuation": 6}
    rollback = ProbeOracle("batch-r9").ask(failed)
    assert rollback["discrepancy"]
    assert rollback["reference"]["state_before_caller_rollback"] == [4, 6]
    assert rollback["client"]["state_before_caller_rollback"] == [6]
    assert rollback["client"]["state_after_caller_rollback"] == [6]

    valid = {"outer": True, "initial": [4], "steps": [[5]], "continuation": 6}
    commit = ProbeOracle("batch-u2").ask(valid)
    assert commit["discrepancy"]
    assert commit["reference"]["transaction_open_before_caller_rollback"]
    assert not commit["client"]["transaction_open_before_caller_rollback"]
    assert commit["reference"]["state_after_caller_rollback"] == []
    assert commit["client"]["state_after_caller_rollback"] == [4, 5, 6]


def test_transfer_failure_preserves_balances_and_later_credit():
    query = {"outer": True, "initial": [[4, 5], [5, 1]],
             "steps": [[4, 6, 2], [4, 5, 1]], "continuation": [5, 1]}
    correct = ProbeOracle("transfer-m6").ask(query)
    assert not correct["discrepancy"]
    result = correct["reference"]
    assert result["steps"][0] == {"ok": False,
                                   "state": [[4, 5], [5, 1]],
                                   "transaction_open": True}
    assert result["steps"][1]["state"] == [[4, 4], [5, 2]]
    assert result["state_before_caller_rollback"] == [[4, 4], [5, 3]]
    assert result["state_after_caller_rollback"] == []
    partial = ProbeOracle("transfer-f3").ask(query)
    assert partial["discrepancy"]
    assert partial["client"]["steps"][0]["state"] == [[4, 3], [5, 1]]


def test_same_failure_then_caller_scope_question_binds_across_workflows():
    batch = {"outer": False, "initial": [4], "steps": [[5, 5]],
             "continuation": 6}
    transfer = {"outer": False, "initial": [[4, 5], [5, 1]],
                "steps": [[4, 6, 2]], "continuation": [5, 1]}
    for task_id, first in (("batch-r9", batch), ("transfer-b8", transfer)):
        oracle = ProbeOracle(task_id)
        assert not oracle.ask(first)["discrepancy"]
        caller_owned = {**first, "outer": True}
        second = oracle.ask(caller_owned)
        assert second["discrepancy"]
        assert second["reference"]["transaction_open_before_caller_rollback"]
        assert not second["client"]["transaction_open_before_caller_rollback"]
        assert oracle.meter.reference_calls == oracle.meter.client_calls == 2


def test_opaque_oracle_records_source_identity_and_actual_native_work():
    query = {"outer": False, "initial": [4], "steps": [[5, 5]],
             "continuation": 6}
    original = deepcopy(query)
    oracle = ProbeOracle("batch-a7")
    first = oracle.ask(query)
    second = oracle.ask(query)
    assert query == original
    assert first["source_sha256"] == second["source_sha256"]
    assert first["query_sha256"] == second["query_sha256"]
    assert first["cost"]["reference_sql"] > 0
    assert first["cost"]["client_sql"] > 0
    assert oracle.meter.reference_calls == oracle.meter.client_calls == 2
    assert oracle.meter.reference_sql == 2 * first["cost"]["reference_sql"]
    assert oracle.meter.client_sql == 2 * first["cost"]["client_sql"]


def test_model_receipt_excludes_source_and_cost_fingerprints():
    query = {"outer": False, "initial": [4], "steps": [[5]], "continuation": 6}
    views = [model_visible_receipt(ProbeOracle(task_id).ask(query))
             for task_id in task_ids("batch")]
    assert all(view == views[0] for view in views)
    assert set(views[0]) == {"query", "reference", "client", "discrepancy"}


@pytest.mark.parametrize("family,query", [
    ("batch", {"outer": 1, "initial": [], "steps": [[1]], "continuation": 2}),
    ("batch", {"outer": False, "initial": [1, 1], "steps": [[2]], "continuation": 3}),
    ("batch", {"outer": False, "initial": [], "steps": [[True]], "continuation": 3}),
    ("transfer", {"outer": False, "initial": [[1, 5], [2, 1]],
                  "steps": [[1, 2, True]], "continuation": [2, 1]}),
])
def test_invalid_query_is_rejected_before_execution(family, query):
    with pytest.raises(ValueError):
        validate_query(family, query)
    oracle = ProbeOracle(task_ids(family)[0])
    with pytest.raises(ValueError):
        oracle.ask(query)
    assert oracle.meter.reference_calls == oracle.meter.client_calls == 0


def test_complete_heldout_panel_keeps_correct_and_incorrect_clients():
    assert len(heldout_queries("batch")) == len(heldout_queries("transfer")) == 80
    results = {task_id: score(task_id) for task_id in task_ids()}
    assert all(row["total"] == 80 for row in results.values())
    assert {task_id for task_id, row in results.items() if row["correct"] == 80} == {
        "batch-k4", "transfer-m6"}
    assert all(row["validation_cost"]["reference_calls"] == 80
               for row in results.values())
    assert all(row["validation_cost"]["client_calls"] == 80
               for row in results.values())
    assert all(row["failing_indices"] for task_id, row in results.items()
               if task_id not in ("batch-k4", "transfer-m6"))
