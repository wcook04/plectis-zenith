"""Synthetic fixtures for demonstrating the feedback contract without APIs."""
from datetime import datetime, timedelta, timezone
from pathlib import Path

from system.lib.hashing import hash_node
from zenith import runtime
from zenith.providers import write_json
from . import engine


def fixture_run(directory, issue, horizon, *, snapshot=100.0, target=101.0, root=engine.ROOT):
    """Create grammar/provenance fixtures, never a claimed real model forecast."""
    directory = Path(directory)
    graph = runtime.load_graph(root)
    scope = runtime.scope_for(graph, "lab_director")
    write_json(directory / "zenith_run.json", {"mission": "lab", "run_id": directory.name,
        "scope": sorted(scope), "node_hashes": {key: hash_node(graph[key]) for key in scope},
        "provider": "captured", "time_anchor": issue.isoformat(), "horizon": horizon.isoformat(),
        "synthetic_fixture": True})
    # Repetition is solely to exercise the existing minimum-word grammar.
    cp2 = {"evidence_dictionary": [{"ref_id": "[1]", "ledger_id": "S_00000001", "subject": "XOM",
                                   "signal_summary": "Synthetic fixture, not market evidence."}],
        "epicentre_thesis": "[1] " + "Synthetic fixture mechanism has a declared baseline and falsifiable condition. " * 25,
        "trade_rationale": "[1] " + "Synthetic fixture consequence follows the baseline at an explicitly declared horizon. " * 20,
        "predictions_t": [{"target_id": "XOM", "direction": "UP", "snapshot_price": snapshot,
            "target_price": target, "snapshot_time": issue.isoformat(), "target_time_iso": horizon.isoformat(),
            "invalidation": "Synthetic XOM at or below the baseline at the declared horizon."}]}
    write_json(directory / "artifacts/lab_director.json", {"status": "success",
        "metadata": {"synthetic_fixture": True}, "data": cp2})
    write_json(directory / "artifacts/global_stock_feed.json", {"status": "success",
        "metadata": {"status": "success", "price_basis": "synthetic_point_quote", "currency": "USD", "synthetic_fixture": True},
        "data": {"columns": ["Ticker", "Price", "timestamp"], "rows": [["XOM", snapshot, issue.isoformat()]]}})
    write_json(directory / "handoff/receipts/fixture.json", {"schema": "zenith_provider_attempt_v1",
        "run_id": directory.name, "node_id": "lab_director", "status": "replayed", "provider": "captured",
        "actual_model": "offline-synthetic-fixture", "requested_model": "offline-synthetic-fixture",
        "execution_kind": "captured_replay", "recorded_at": issue.isoformat(),
        "prompt_sha256": "0" * 64, "response_sha256": "1" * 64, "synthetic_fixture": True})
    return directory


def fixture_policy(path):
    write_json(path, {"schema": "zenith_forecast_feedback_policy_v1", "policy_id": "synthetic-example-v1",
        "price_basis": "synthetic_point_quote", "currency": "USD", "observation_precision": "timestamp",
        "relative_error_threshold": 0.05})
    return Path(path)


def run(store):
    store = Path(store)
    if store.exists():
        raise ValueError("demo needs a fresh store; existing evidence will not be overwritten")
    fixtures = store / "synthetic-fixtures"
    policy = fixture_policy(fixtures / "policy.json")
    first = datetime(2026, 1, 5, 20, tzinfo=timezone.utc)
    truth = []
    for index in range(20):
        issue = first + timedelta(days=2 * index)
        horizon = issue + timedelta(days=1)
        source = fixture_run(fixtures / f"SYNTHETIC_LAB_{index:02d}", issue, horizon)
        engine.register(store, source, policy, "24h")
        truth.append({"target_id": "XOM", "timestamp": horizon.isoformat(), "price": 99.0 if index % 5 == 0 else 101.0})
    truth_path = fixtures / "truth.json"
    write_json(truth_path, {"metadata": {"status": "success", "price_basis": "synthetic_point_quote", "currency": "USD", "synthetic_fixture": True},
        "data": {"rows": truth}})
    as_of = "2026-03-01T00:00:00+00:00"
    pending = engine.score(store, truth_path, "2026-01-05T20:01:00+00:00")
    measured = engine.score(store, truth_path, as_of)
    repeated = engine.score(store, truth_path, as_of)
    proposals = engine.propose(store, as_of)
    return {"schema": "zenith_forecast_feedback_demo_v1", "synthetic_fixture": True,
        "claim_boundary": "Offline contract demonstration, not market observations or model skill evidence.",
        "pending_statuses": pending["statuses"], "mature_statuses": measured["statuses"],
        "repeated_scoring_same_attempt": measured["attempt_id"] == repeated["attempt_id"],
        "summary": engine.summary(store, as_of, window_days=90),
        "candidate_feedback_proposals": [{key: row[key] for key in ("proposal_id", "candidate_error_class", "total_failures", "total_resolved", "support_fraction", "distinct_resolved_issue_times", "nonoverlapping_failure_buckets", "live_mutation_permission")} for row in proposals["proposals"]]}
