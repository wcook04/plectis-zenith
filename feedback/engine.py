"""Measure locked CP2 forecasts against exact, dated observations.

This lane reads existing Lab/Oracle artifacts; it never supplies truth to Lab or
changes a skill. Missing observations are data gaps, not failed predictions.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
import hashlib
import importlib.metadata
import json
import math
from pathlib import Path
import re
import sqlite3

from system.lib.run_compare import combined_prices, _iter_tables
from system.lib.schema_validator import validate_cp2
from tools.finance.resolve_forecasts import _iter_price_rows, _load_price_index
from zenith import runtime
from zenith.providers import write_json
from system.lib.hashing import hash_node

ROOT = Path(__file__).resolve().parents[1]
FEEDS = ("global_stock_feed", "global_etf_feed")


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def timestamp(value):
    if not isinstance(value, str):
        raise ValueError("timestamp must be an ISO string with an explicit timezone")
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise ValueError("timestamp requires an explicit timezone")
    return result.astimezone(timezone.utc)


def finite_price(value, *, allow_nonpositive=False):
    if isinstance(value, bool):
        raise ValueError("price cannot be boolean")
    result = float(value)
    if not math.isfinite(result) or (result <= 0 and not allow_nonpositive):
        raise ValueError("price must be finite and positive unless it is a predicted target")
    return result


def read_object(path):
    def unique_keys(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate JSON field: {key}")
            result[key] = value
        return result
    value = json.loads(Path(path).read_text(), object_pairs_hook=unique_keys)
    if not isinstance(value, dict):
        raise ValueError(f"JSON object required: {Path(path).name}")
    return value


def source_ref(path, *, root=ROOT, pointer=None):
    path = Path(path).resolve()
    try:
        label = str(path.relative_to(Path(root).resolve()))
    except ValueError:
        label = path.name
    result = {"path": label, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    if pointer is not None:
        result["pointer"] = pointer
    return result


def connection(store, *, create=False):
    store = Path(store)
    if create:
        store.mkdir(parents=True, exist_ok=True)
    if not create and not (store / "feedback.sqlite3").exists():
        raise ValueError("feedback store does not exist; register a validated Lab run first")
    db = sqlite3.connect(store / "feedback.sqlite3", timeout=30)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    if create:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS forecasts (
          forecast_id TEXT PRIMARY KEY, logical_key TEXT UNIQUE NOT NULL, record TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS evaluations (
          forecast_id TEXT PRIMARY KEY REFERENCES forecasts(forecast_id), record TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS score_attempts (
          attempt_id TEXT PRIMARY KEY, record TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS proposals (
          proposal_id TEXT PRIMARY KEY, record TEXT NOT NULL);
        """)
    return db


def policy_from(path):
    policy = read_object(path)
    required = {"schema", "policy_id", "price_basis", "currency", "observation_precision", "relative_error_threshold"}
    if not required.issubset(policy) or policy["schema"] != "zenith_forecast_feedback_policy_v1":
        raise ValueError("feedback policy requires the documented v1 fields")
    if set(policy) - required - {"calendar_id", "calendar_version"}:
        raise ValueError("unknown feedback policy fields")
    for key in ("policy_id", "price_basis", "currency"):
        if not isinstance(policy[key], str) or not policy[key].strip():
            raise ValueError(f"nonempty {key} required")
    threshold = policy["relative_error_threshold"]
    if type(threshold) not in (int, float) or not math.isfinite(threshold) or threshold < 0:
        raise ValueError("relative_error_threshold must be finite and nonnegative")
    if policy["observation_precision"] not in {"timestamp", "session_close"}:
        raise ValueError("observation_precision must be timestamp or session_close")
    if policy["observation_precision"] == "session_close":
        if policy.get("calendar_id") != "XNYS":
            raise ValueError("session_close currently requires the native XNYS calendar")
        actual = importlib.metadata.version("exchange_calendars")
        if policy.get("calendar_version") != actual:
            raise ValueError("session_close requires the exact installed exchange_calendars version")
    return policy


def observation_time(raw, policy):
    if policy["observation_precision"] == "timestamp":
        return timestamp(raw)
    if not isinstance(raw, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
        raise ValueError("session_close observation needs an explicit bar date")
    day = date.fromisoformat(raw)
    if importlib.metadata.version("exchange_calendars") != policy["calendar_version"]:
        raise ValueError("frozen calendar version changed")
    from system.core.engine import _xnys_calendar
    calendar = _xnys_calendar(day.year)
    session = calendar.date_to_session(day.isoformat(), direction="none")
    return calendar.session_close(session).to_pydatetime().astimezone(timezone.utc)


def dated_rows(path):
    """Reuse Oracle table and historical-price parsers, retaining duplicate rows.

    Only row-level observation fields count. Envelope fetch/as_of timestamps do
    not identify the bar. Duplicate rows stay visible rather than last-wins.
    """
    payload = read_object(path)
    metadata = payload.get("metadata", {})
    if not isinstance(metadata, dict):
        raise ValueError("price metadata must be an object")
    if payload.get("status", "success") not in {"success", "loaded"} or metadata.get("status", "success") not in {"success", "loaded"}:
        raise ValueError("failed price artifact is not truth")
    records = []
    for columns, rows in _iter_tables(payload.get("data", {})):
        if not all(isinstance(col, str) for col in columns):
            raise ValueError("price table columns must be strings")
        for row in rows:
            if isinstance(row, list):
                records.append(dict(zip(columns, row)))
            elif isinstance(row, dict):
                records.append(row)
    if not records:
        records = list(_iter_price_rows(payload))
        if not records:
            # Mapping-form historical price observations retain their exact key.
            raw_data = payload.get("data", payload)
            for series in raw_data.get("prices", {}).values() if isinstance(raw_data, dict) and isinstance(raw_data.get("prices", {}), dict) else []:
                if isinstance(series, dict):
                    for value in series.values():
                        finite_price(value)  # Preserve rejection of booleans before coercion.
            for symbol, series in _load_price_index(payload).items():
                for observed, price in series.items():
                    records.append({"target_id": symbol, "timestamp": observed, "price": price})
    result = []
    for record in records:
        symbol = record.get("Ticker") or record.get("ticker") or record.get("symbol") or record.get("target_id") or record.get("id")
        if not isinstance(symbol, str) or not symbol.strip():
            continue
        diagnostics = metadata.get("diagnostics", {})
        observations = diagnostics.get("price_observations", {}) if isinstance(diagnostics, dict) else {}
        if not isinstance(observations, dict):
            raise ValueError("price_observations must be an object")
        observed_meta = observations.get(symbol.strip().upper(), {})
        if not isinstance(observed_meta, dict):
            observed_meta = {}
        observed = next((record[key] for key in ("observation_time", "bar_time", "price_time", "PriceTimestamp", "timestamp", "date", "Date", "PriceDate", "price_date") if record.get(key) is not None), None)
        if observed is None:
            observed = observed_meta.get("bar_date") or observed_meta.get("session_date")
        basis = record.get("price_basis", metadata.get("price_basis", observed_meta.get("price_basis")))
        if basis is None and observed_meta.get("interval") == "1d" and observed_meta.get("auto_adjust") is False:
            # This is the provider's adjustment setting, not a claim that all
            # corporate-action history has been independently established.
            basis = "daily_close_auto_adjust_false"
        price = next((record[key] for key in ("Price", "price", "close", "adj_close", "value") if record.get(key) is not None), None)
        alternatives = [record[key] for key in ("Price", "price", "close", "adj_close", "value") if record.get(key) is not None]
        if len(alternatives) > 1 and len({finite_price(value) for value in alternatives}) != 1:
            raise ValueError("ambiguous price columns; supply a normalized price with declared basis")
        result.append({"target_id": symbol.strip().upper(), "observed": observed, "price": price,
            "price_basis": basis,
            "currency": record.get("currency", metadata.get("currency", observed_meta.get("currency"))),
            "provider_observation": observed_meta,
            "row_sha256": digest(record), "source": source_ref(path)})
    return result


def lineage(root, manifest, subject):
    graph = runtime.graph_for_manifest(root, manifest)
    if "lab_director" not in graph:
        raise ValueError("native graph has no lab_director")
    visited = set()
    def walk(node_id):
        if node_id in visited:
            return
        visited.add(node_id)
        for parent in graph[node_id].dependencies:
            walk(parent)
    walk("lab_director")
    frozen = manifest.get("node_hashes", {})
    known = bool(frozen) and all(frozen.get(key) == hash_node(graph[key]) for key in visited)
    if frozen and not known:
        raise ValueError("ancestor graph differs from frozen Lab run")
    reasoning = manifest.get("reasoning_policy")
    if reasoning:
        from system.lib.reasoning_policy import validate_reasoning_policy
        validate_reasoning_policy(reasoning, graph)
    participants = []
    for key in sorted(visited):
        row = (reasoning or {}).get("nodes", {}).get(key, {})
        receipts = []
        for path in sorted((Path(subject) / "artifacts/context_policy").glob(f"{key}.*.json")):
            receipt = read_object(path)
            if receipt.get("node_id") != key:
                raise ValueError("context policy receipt node mismatch")
            if receipt.get("policy_sha256") != (reasoning or {}).get("policy_sha256"):
                raise ValueError("context policy receipt differs from frozen reasoning policy")
            declared = receipt.get("receipt_sha256")
            if declared != digest({k: v for k, v in receipt.items() if k != "receipt_sha256"}):
                raise ValueError("context policy receipt hash mismatch")
            receipts.append({**source_ref(path, root=root), "receipt_sha256": declared,
                             "incoming_edges": receipt.get("incoming_edges", [])})
        participants.append({"node_id": key, "node_sha256": hash_node(graph[key]),
            "participation_type": "structural_ancestor; actual input consumption requires context receipt evidence",
            "parent_ids": list(graph[key].dependencies),
            "incoming_edge_ids": [f"{parent}->{key}" for parent in graph[key].dependencies],
            "skill_addon_sha256": hashlib.sha256(row["skill_addon"].encode()).hexdigest() if row.get("skill_addon") else None,
            "context_policy_receipts": receipts})
    return {"frozen_graph_verified": known, "reasoning_policy": reasoning,
            "participants": participants, "interpretation": "structural ancestry; context consumption only where evidenced by receipts, not causal blame"}


def model_identity(subject):
    receipts = []
    for path in sorted((Path(subject) / "handoff/receipts").glob("*.json")):
        row = read_object(path)
        if row.get("schema") == "zenith_provider_attempt_v1" and row.get("run_id") == Path(subject).name and row.get("node_id") == "lab_director" and row.get("status") in {"response_supplied", "replayed"}:
            receipts.append((row.get("recorded_at", ""), path, row))
    if not receipts:
        return {"actual_model": None, "requested_model": None, "status": "unavailable", "source": None}
    _, path, row = sorted(receipts, key=lambda item: (item[0], str(item[1])))[-1]
    return {"actual_model": row.get("actual_model"), "requested_model": row.get("requested_model"),
            "provider": row.get("provider"), "execution_kind": row.get("execution_kind", row.get("provider")),
            "prompt_sha256": row.get("prompt_sha256"), "response_sha256": row.get("response_sha256"),
            "status": "observed" if isinstance(row.get("actual_model"), str) and row["actual_model"].strip() else "unavailable", "source": source_ref(path)}


def register(store, subject_run, policy_path, horizon_id, *, root=ROOT):
    subject = Path(subject_run).resolve()
    if not isinstance(horizon_id, str) or not horizon_id.strip():
        raise ValueError("declared horizon_id required")
    policy = policy_from(policy_path)
    cp2_path = subject / "artifacts/lab_director.json"
    envelope = read_object(cp2_path)
    if envelope.get("status") not in {"success", "loaded"}:
        raise ValueError("Lab CP2 must be an engine-accepted success/loaded artifact")
    if not isinstance(envelope.get("metadata", {}), dict):
        raise ValueError("CP2 artifact metadata must be an object")
    payload = envelope.get("data")
    if not isinstance(payload, dict) or "oracle_meta" in payload:
        raise ValueError("only forward Lab CP2 can be registered")
    manifest_path = subject / "zenith_run.json"
    manifest = read_object(manifest_path) if manifest_path.exists() else {}
    if manifest and manifest.get("mission") != "lab":
        raise ValueError("forecast source must be a Lab run")
    validated = validate_cp2(payload, subject_run_dir=subject,
                             expected_snapshot_time=manifest.get("time_anchor"),
                             expected_target_time_iso=manifest.get("horizon"))
    if not validated.ok:
        raise ValueError("CP2 validation failed: " + "; ".join(validated.errors))
    reasoning = manifest.get("reasoning_policy")
    if reasoning and envelope.get("metadata", {}).get("reasoning_policy_sha256") != reasoning["policy_sha256"]:
        raise ValueError("CP2 artifact is not bound to the frozen reasoning policy")
    ancestry = lineage(root, manifest, subject)
    identity = model_identity(subject)
    prices = combined_prices(subject)
    observations = []
    for feed in FEEDS:
        path = subject / "artifacts" / f"{feed}.json"
        if path.exists():
            observations.extend(dated_rows(path))
    frozen_policy = {"definition": policy, "sha256": digest(policy), "source": source_ref(policy_path)}
    now = datetime.now(timezone.utc)
    records = []
    pairs = set()
    for index, pred in enumerate(payload["predictions_t"]):
        target = str(pred["target_id"]).strip().upper()
        issue, horizon = timestamp(pred["snapshot_time"]), timestamp(pred["target_time_iso"])
        if horizon <= issue or issue > now:
            raise ValueError("forecast needs an already-issued snapshot and a later horizon")
        duration = re.fullmatch(r"(\d+)([hd])", horizon_id)
        if duration:
            hours = int(duration[1]) * (24 if duration[2] == "d" else 1)
            if hours <= 0 or horizon - issue != timedelta(hours=hours):
                raise ValueError("duration horizon_id disagrees with the exact CP2 target time")
        elif horizon_id == "next_us_close":
            from system.core.engine import GodModeEngine
            resolved = timestamp(GodModeEngine.resolve_horizon(horizon_id, issue)["target_time"])
            if resolved != horizon:
                raise ValueError("next_us_close horizon_id disagrees with the native exchange calendar")
        if (target, issue.isoformat(), horizon.isoformat()) in pairs:
            raise ValueError("duplicate target/issue/horizon in CP2")
        pairs.add((target, issue.isoformat(), horizon.isoformat()))
        snapshot = finite_price(pred["snapshot_price"])
        # Preserve even implausible finite point forecasts in the measured
        # corpus; discarding poor targets would bias the error denominator.
        expected = finite_price(pred["target_price"], allow_nonpositive=True)
        actual_snapshot = (prices.get(target) or {}).get("Price")
        if actual_snapshot is None or not math.isclose(snapshot, finite_price(actual_snapshot), rel_tol=1e-9, abs_tol=1e-9):
            raise ValueError("snapshot_price differs from subject-run equity baseline")
        candidates = [row for row in observations if row["target_id"] == target]
        gaps = []
        source_observation = candidates[0] if len(candidates) == 1 else None
        if source_observation is None:
            gaps.append("missing_or_duplicate_subject_observation")
        else:
            if source_observation["price_basis"] != policy["price_basis"] or source_observation["currency"] != policy["currency"]:
                gaps.append("subject_price_basis_or_currency_unverified")
            try:
                observed = observation_time(source_observation["observed"], policy)
                if observed > issue:
                    raise ValueError("subject observation was after issue")
                source_observation["observed_time"] = observed.isoformat()
                source_observation["age_at_issue_seconds"] = (issue - observed).total_seconds()
            except (ValueError, TypeError):
                gaps.append("subject_observation_time_unverified")
        binding = {"issue_run_id": subject.name, "target_id": target, "issue_time": issue.isoformat(),
            "target_time": horizon.isoformat(), "horizon_id": horizon_id}
        source = source_ref(cp2_path, root=root, pointer=f"/data/predictions_t/{index}")
        # A second label for the same actual target horizon is not a new trial.
        logical_key = digest({k: v for k, v in binding.items() if k != "horizon_id"})
        record = {"schema": "zenith_registered_forecast_v1", **binding,
            "forecast_id": digest({**binding, "cp2_sha256": source["sha256"]}),
            "snapshot_price": snapshot, "target_price": expected, "direction": pred["direction"],
            "horizon_seconds": (horizon - issue).total_seconds(), "policy": frozen_policy,
            "source": source, "subject_observation": source_observation,
            "measurement_source": source_ref(Path(__file__)),
            "subject_data_gaps": gaps, "model": identity, "ancestry": ancestry,
            "synthetic_fixture": envelope.get("metadata", {}).get("synthetic_fixture") is True,
            "run_manifest": source_ref(manifest_path, root=root) if manifest else None,
            "evaluation_posture": "historical_import" if now >= horizon else "prospective_pending",
            "claim_boundary": "local source provenance; registration alone does not prove contemporaneous publication"}
        records.append((logical_key, record))
    admitted = []
    with connection(store, create=True) as db:
        db.execute("BEGIN IMMEDIATE")
        for key, record in records:
            previous = db.execute("SELECT record FROM forecasts WHERE logical_key=?", (key,)).fetchone()
            if previous:
                old = json.loads(previous["record"])
                comparable = {k: v for k, v in record.items() if k != "evaluation_posture"}
                if {k: v for k, v in old.items() if k != "evaluation_posture"} != comparable:
                    raise ValueError("registered forecast provenance changed; use a new Lab run")
                admitted.append(old)
            else:
                db.execute("INSERT INTO forecasts VALUES (?,?,?)", (record["forecast_id"], key, canonical(record)))
                admitted.append(record)
    return {"schema": "zenith_forecast_registration_v1", "forecasts": admitted, "count": len(admitted)}


def truth_files(path):
    path = Path(path)
    if path.is_file():
        return [path]
    if path.is_dir():
        return [path / "artifacts" / f"{feed}.json" for feed in FEEDS
                if (path / "artifacts" / f"{feed}.json").is_file()]
    return []


def measurement(forecast, rows, as_of, source_errors):
    base = {"schema": "zenith_forecast_evaluation_v1", "forecast_id": forecast["forecast_id"],
            "issue_run_id": forecast["issue_run_id"], "horizon_id": forecast["horizon_id"],
            "issue_time": forecast["issue_time"], "target_time": forecast["target_time"],
            "as_of": as_of.isoformat(), "source": forecast["source"],
            "measurement_source": source_ref(Path(__file__))}
    horizon = timestamp(forecast["target_time"])
    if as_of < horizon:
        return {**base, "status": "pending", "data_gaps": ["horizon_not_mature"], "metrics": None, "error_classes": []}
    gaps = list(forecast["subject_data_gaps"])
    if source_errors:
        gaps.extend(source_errors)
    policy = forecast["policy"]["definition"]
    matches = []
    saw_symbol, saw_wrong_basis, invalid_observation = False, False, False
    for row in rows:
        if row["target_id"] != forecast["target_id"]:
            continue
        saw_symbol = True
        try:
            observed = observation_time(row["observed"], policy)
        except (ValueError, TypeError):
            invalid_observation = True
            continue
        if observed != horizon:
            continue
        if row["price_basis"] != policy["price_basis"] or row["currency"] != policy["currency"]:
            saw_wrong_basis = True
            continue
        try:
            price = finite_price(row["price"])
        except (ValueError, TypeError, OverflowError):
            gaps.append("invalid_truth_price")
            continue
        matches.append({**row, "observed_time": observed.isoformat(), "price": price})
    if len(matches) > 1:
        gaps.append("duplicate_truth_observation")
    elif not matches:
        if saw_wrong_basis:
            gaps.append("truth_price_basis_or_currency_mismatch")
        elif invalid_observation:
            gaps.append("truth_bar_observation_time_unverified")
        else:
            gaps.append("missing_exact_horizon_observation" if saw_symbol else "missing_truth_target")
    if gaps:
        return {**base, "status": "data_gap", "data_gaps": sorted(set(gaps)), "metrics": None, "error_classes": []}
    truth = matches[0]
    actual = truth["price"]
    snapshot, target = forecast["snapshot_price"], forecast["target_price"]
    absolute_error = abs(target - actual)
    baseline_error = abs(snapshot - actual)
    direction = "UP" if actual > snapshot else "DOWN" if actual < snapshot else "FLAT"
    hit = forecast["direction"] == direction
    classes = []
    if not hit:
        classes.append("direction_miss")
    if absolute_error > baseline_error:
        classes.append("target_worse_than_no_change")
    if absolute_error / actual > policy["relative_error_threshold"]:
        classes.append("relative_target_error_above_declared_threshold")
    metrics = {"realized_price": actual, "target_price_absolute_error": absolute_error,
        "target_price_relative_error": absolute_error / actual, "signed_target_error": target - actual,
        "actual_direction": direction, "direction_hit": hit,
        "no_change_target_price": snapshot, "no_change_absolute_error": baseline_error,
        "no_change_relative_error": baseline_error / actual,
        "target_better_than_no_change": absolute_error < baseline_error,
        "price_basis": policy["price_basis"], "currency": policy["currency"]}
    return {**base, "status": "scored", "data_gaps": [], "metrics": metrics,
            "error_classes": classes, "truth": truth,
            "interpretation": "price and direction forecast error, not returns or causal diagnosis"}


def score(store, truth_source, as_of):
    as_of = timestamp(as_of)
    files = truth_files(truth_source)
    observations, errors, refs = [], [], []
    for path in files:
        refs.append(source_ref(path))
        try:
            observations.extend(dated_rows(path))
        except (ValueError, TypeError, OSError, json.JSONDecodeError):
            errors.append("invalid_truth_artifact")
    if not files:
        errors.append("missing_truth_artifact")
    results = []
    with connection(store) as db:
        db.execute("BEGIN IMMEDIATE")
        forecasts = [json.loads(row["record"]) for row in db.execute("SELECT record FROM forecasts ORDER BY forecast_id")]
        for forecast in forecasts:
            previous = db.execute("SELECT record FROM evaluations WHERE forecast_id=?", (forecast["forecast_id"],)).fetchone()
            old = json.loads(previous["record"]) if previous else None
            # Scoring is immutable once resolved. Later revisions cannot replace
            # the recorded truth; a correction needs a distinct explicit study.
            frozen_score = old and old["status"] == "scored"
            if frozen_score and timestamp(old["as_of"]) > as_of:
                result = measurement(forecast, [], as_of, ["recorded_evaluation_not_available_at_requested_as_of"])
            else:
                result = old if frozen_score else measurement(forecast, observations, as_of, errors)
            if not frozen_score:
                db.execute("INSERT INTO evaluations VALUES (?,?) ON CONFLICT(forecast_id) DO UPDATE SET record=excluded.record",
                           (forecast["forecast_id"], canonical(result)))
            results.append(result)
        attempt = {"schema": "zenith_forecast_score_attempt_v1", "as_of": as_of.isoformat(), "truth_sources": refs,
                   "forecast_ids": [r["forecast_id"] for r in results], "statuses": dict(Counter(r["status"] for r in results))}
        attempt_id = digest(attempt)
        db.execute("INSERT OR IGNORE INTO score_attempts VALUES (?,?)", (attempt_id, canonical(attempt)))
    return {"schema": "zenith_forecast_scoring_v1", "attempt_id": attempt_id, "evaluations": results,
            "statuses": dict(Counter(r["status"] for r in results))}


def group_key(forecast):
    return canonical({"horizon_id": forecast["horizon_id"], "feedback_policy_sha256": forecast["policy"]["sha256"],
        "synthetic_fixture": forecast["synthetic_fixture"],
        "evaluation_posture": forecast["evaluation_posture"],
        "reasoning_policy_sha256": (forecast["ancestry"].get("reasoning_policy") or {}).get("policy_sha256"),
        "actual_model": forecast["model"].get("actual_model"), "execution_kind": forecast["model"].get("execution_kind")})


def selected_records(store, as_of, window_days):
    if type(window_days) is not int or window_days < 1:
        raise ValueError("window_days must be a positive integer")
    as_of = timestamp(as_of)
    lower = as_of - timedelta(days=window_days)
    groups = defaultdict(list)
    with connection(store) as db:
        for row in db.execute("SELECT f.record AS forecast,e.record AS evaluation FROM forecasts f LEFT JOIN evaluations e USING(forecast_id)"):
            forecast = json.loads(row["forecast"])
            if lower <= timestamp(forecast["issue_time"]) <= as_of:
                evaluation = json.loads(row["evaluation"]) if row["evaluation"] else None
                # A report at an earlier clock cannot read a later resolution.
                if evaluation and timestamp(evaluation["as_of"]) > as_of:
                    evaluation = None
                key = json.loads(group_key(forecast))
                key["measurement_source_sha256"] = (evaluation or forecast)["measurement_source"]["sha256"]
                groups[canonical(key)].append((forecast, evaluation))
    return as_of, groups


def summary(store, as_of, *, window_days=30):
    as_of, groups = selected_records(store, as_of, window_days)
    reports = []
    for key, samples in sorted(groups.items()):
        resolved = [(f, e) for f, e in samples if e and e["status"] == "scored"]
        status_counts = Counter(e["status"] if e else "unscored" for _, e in samples)
        metrics = [e["metrics"] for _, e in resolved]
        def mean(field):
            return math.fsum(m[field] for m in metrics) / len(metrics) if metrics else None
        reports.append({**json.loads(key), "forecast_count": len(samples), "distinct_issue_times": len({f["issue_time"] for f, _ in samples}),
            "resolved": len(resolved), "statuses": dict(status_counts),
            "data_gap_counts": dict(Counter(gap for _, e in samples if e and e["status"] == "data_gap" for gap in e["data_gaps"])),
            "error_class_counts": dict(Counter(code for _, e in resolved for code in e["error_classes"])),
            "mean_target_price_absolute_error": mean("target_price_absolute_error"),
            "mean_target_price_relative_error": mean("target_price_relative_error"),
            "mean_no_change_absolute_error": mean("no_change_absolute_error"),
            "mean_no_change_relative_error": mean("no_change_relative_error"),
            "direction_hit_fraction": mean("direction_hit"),
            "price_basis": samples[0][0]["policy"]["definition"]["price_basis"],
            "currency": samples[0][0]["policy"]["definition"]["currency"],
            "dependency_warning": "Same-issue assets, overlapping horizons and sliding windows are not independent observations."})
    return {"schema": "zenith_rolling_forecast_summary_v1", "as_of": as_of.isoformat(), "window_days": window_days,
            "issue_window_start_inclusive": (as_of - timedelta(days=window_days)).isoformat(), "groups": reports,
            "window_overlap": "Successive rolling reports reuse observations; do not count reports as new trials."}


def propose(store, as_of, *, window_days=90, minimum_issue_times=20, minimum_failure_issues=3, bucket_days=7):
    if type(minimum_issue_times) is not int or minimum_issue_times < 20:
        raise ValueError("minimum_issue_times is an operational batch gate of at least 20")
    if type(minimum_failure_issues) is not int or minimum_failure_issues < 3:
        raise ValueError("minimum_failure_issues must be at least 3")
    if type(bucket_days) is not int or bucket_days < 1:
        raise ValueError("bucket_days must be positive")
    as_of, groups = selected_records(store, as_of, window_days)
    proposals, eligibility = [], []
    def bucket(forecast):
        # Fixed nonoverlapping UTC buckets, not overlapping report windows.
        return timestamp(forecast["issue_time"]).date().toordinal() // bucket_days
    for key, samples in sorted(groups.items()):
        resolved = [(f, e) for f, e in samples if e and e["status"] == "scored"]
        issues = {f["issue_time"] for f, _ in resolved}
        windows = {bucket(f) for f, _ in resolved}
        model_known = bool(resolved) and all(f["model"].get("status") == "observed" for f, _ in resolved)
        graph_known = bool(resolved) and all(f["ancestry"]["frozen_graph_verified"] for f, _ in resolved)
        enough = len(issues) >= minimum_issue_times and len(windows) >= 3 and model_known and graph_known
        eligibility.append({**json.loads(key), "resolved": len(resolved), "distinct_issue_times": len(issues),
                            "nonoverlapping_issue_buckets": len(windows), "actual_model_known": model_known,
                            "frozen_ancestry_verified": graph_known, "eligible_batch": enough})
        if not enough:
            continue
        classes = sorted({code for _, e in resolved for code in e["error_classes"]})
        for code in classes:
            failures = [(f, e) for f, e in resolved if code in e["error_classes"]]
            failure_issues = {f["issue_time"] for f, _ in failures}
            failure_windows = {bucket(f) for f, _ in failures}
            failure_runs = {f["issue_run_id"] for f, _ in failures}
            if len(failure_issues) < minimum_failure_issues or len(failure_windows) < 3 or len(failure_runs) < 3:
                continue
            participants = {digest(p): p for f, _ in resolved for p in f["ancestry"]["participants"]}
            evidence = [{"forecast_id": f["forecast_id"], "issue_run_id": f["issue_run_id"],
                "issue_time": f["issue_time"], "forecast_ref": f["source"], "truth_ref": e["truth"]["source"],
                "truth_row_sha256": e["truth"]["row_sha256"], "truth_observed_time": e["truth"]["observed_time"],
                "supports_candidate_class": code in e["error_classes"], "metrics": e["metrics"]} for f, e in resolved]
            row = {"schema": "zenith_skill_feedback_proposal_v1", **json.loads(key), "candidate_error_class": code,
                "analysis_window": {"as_of": as_of.isoformat(), "days": window_days,
                                    "start_inclusive": (as_of - timedelta(days=window_days)).isoformat()},
                "total_registered_samples_in_window": len(samples),
                "sample_status_counts": dict(Counter(e["status"] if e else "unscored" for _, e in samples)),
                "total_failures": len(failures), "total_resolved": len(resolved),
                "support_fraction": len(failures) / len(resolved),
                "distinct_resolved_issue_times": len(issues), "distinct_failure_issue_times": len(failure_issues),
                "issue_support_fraction": len(failure_issues) / len(issues),
                "failure_issue_runs": sorted(failure_runs), "nonoverlapping_failure_buckets": len(failure_windows),
                "bucket_days": bucket_days, "minimum_issue_times": minimum_issue_times,
                "minimum_failure_issues": minimum_failure_issues,
                "operational_gate_interpretation": "Minimum counts are routing gates, not statistical validation or confidence levels.",
                "participating_ancestors": [participants[p] for p in sorted(participants)],
                "evidence": sorted(evidence, key=lambda e: e["forecast_id"]),
                "claim_boundary": "Repeated measured error with ancestry/skill participation signals; no causal blame or gradient.",
                "requires": "review source evidence, propose one falsifiable skill change, then test heldout/prospective shadow evidence and uncertainty before promotion",
                "live_mutation_permission": False,
                "window_overlap": "Forecast horizons and later rolling reports may overlap; issue buckets only prevent counting overlapping reports as independent replication."}
            row["proposal_id"] = digest(row)
            proposals.append(row)
    with connection(store) as db:
        for row in proposals:
            db.execute("INSERT OR IGNORE INTO proposals VALUES (?,?)", (row["proposal_id"], canonical(row)))
            write_json(Path(store) / "proposals" / f"{row['proposal_id']}.json", row)
    return {"schema": "zenith_skill_feedback_v1", "as_of": as_of.isoformat(), "window_days": window_days,
            "eligibility": eligibility, "proposals": proposals, "live_mutation_permission": False}
