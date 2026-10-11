"""Prepare and orchestrate a frozen compact native StockNet study, never flat inference.

Execution, response admission, price measurement, pairing and final sealing belong
to the existing Zenith engine and research.cohort. This adapter only admits dated
price snapshots and invokes those owners. No external acquisition is performed.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime
import json
from pathlib import Path
import time

from benchmarks.stocknet import _git, canonical_digest, digest, features, parse_prices, protocol
from benchmarks.stocknet_aggregation import close_utc
from research import cohort
from research.engine import read_json, write_json
from system.core.engine import GodModeEngine
from system.lib.reasoning_policy import policy_sha256
from variants.predictor import build_replacement, PROFILE
from zenith import runtime

SYMBOLS = ("AAPL", "MSFT", "GOOG")
PRICE_BASIS = "stocknet_yahoo_close_as_supplied"
CONTEXT_CHARS = 24000
SKILL_ADDON = (
    "Use current Close as a short-horizon persistence prior. "
    "Before choosing target_price, separate directional belief from move size. "
    "Use the supplied past one-session returns to justify scale; shrink the projected "
    "move toward zero when magnitude evidence is weak. Do not amplify a weak thesis "
    "into a large point forecast. Preserve every declared target, current quote, "
    "horizon, grounding citation and invalidation condition."
)


def _sources(dataset):
    dataset = Path(dataset).resolve()
    source = read_json(dataset / "source-manifest.json")
    spec = protocol()
    if source.get("dataset_commit") != spec["dataset_commit"]:
        raise ValueError("pinned StockNet dataset identity differs")
    records = {record.get("symbol"): record for record in source["files"]}
    prices, references, exclusions = {}, {}, {}
    for symbol in SYMBOLS:
        record = records[symbol]
        path = (dataset / record["path"]).resolve()
        if not path.is_relative_to(dataset):
            raise ValueError("price source escapes dataset")
        content = path.read_bytes()
        if digest(content) != record["sha256"]:
            raise ValueError("price source hash differs")
        prices[symbol], exclusions[symbol] = parse_prices(content)
        references[symbol] = deepcopy(record)
    return prices, references, exclusions, source


def _dates(prices, split, count):
    start, end = protocol()["splits"][split]
    indices = {symbol: {row["Date"]: index for index, row in enumerate(rows)
                if start <= row["Date"] < end and index >= 20 and index + 1 < len(rows)
                and rows[index + 1]["Date"] < end}
               for symbol, rows in prices.items()}
    dates = sorted(set.intersection(*(set(values) for values in indices.values())))[:count]
    if len(dates) != count:
        raise ValueError("insufficient common dated price support")
    return dates, indices


def _policy(candidate=False):
    value = {"variant_id": "compact_magnitude_shrink_v1" if candidate else "compact_baseline_v1",
             "nodes": {node: {"max_context_chars": CONTEXT_CHARS}
                       for node in ("lab_decide", "lab_director")}}
    if candidate:
        value["nodes"]["lab_director"]["skill_addon"] = SKILL_ADDON
    value["policy_sha256"] = policy_sha256(value)
    return value


def _snapshot(prices, indices, stamp, references):
    anchor = close_utc(stamp)
    horizon = datetime.fromisoformat(GodModeEngine.resolve_horizon("next_us_close", anchor)["target_time"])
    rows, assets, truth = [], [], []
    for position, symbol in enumerate(SYMBOLS, 1):
        index = indices[symbol][stamp]
        history = prices[symbol][index - 19:index + 1]
        current, target = prices[symbol][index], prices[symbol][index + 1]
        if close_utc(target["Date"]) != horizon:
            raise ValueError("next observed row differs from native exchange horizon")
        ledger = f"S_{position:08X}"
        rows.append([symbol, current["Close"], anchor.isoformat(), ledger])
        assets.append({"symbol": symbol, "ledger_id": ledger,
                       "observed_ohlcv": {key: current[key] for key in protocol()["feature_fields"]},
                       "past_20_rows": [{key: row[key] for key in ["Date", *protocol()["feature_fields"]]}
                                        for row in history],
                       "derived_features": dict(zip(
                           ["return_1", "return_5", "return_20", "intraday_range", "open_gap",
                            "intraday_return", "volume_relative_20", "close_range_position"],
                           features(prices[symbol], index))),
                       "price_source_sha256": references[symbol]["sha256"]})
        truth.append({"target_id": symbol, "timestamp": horizon.isoformat(), "price": target["Close"]})
    metadata = {"status": "success", "as_of": anchor.isoformat(), "timestamp_iso": anchor.isoformat(),
                "price_basis": PRICE_BASIS, "currency": "USD", "synthetic_fixture": False,
                "dataset_commit": protocol()["dataset_commit"], "available_feed_lanes": ["STOCK"],
                "unavailable_feed_lanes": ["ETF", "MACRO", "NEWS", "POLYMARKET", "STOCKGRID", "CALCULATOR"],
                "historical_replay": True,
                "availability_boundary": "Dated close assumed available after session close; vintage and original ingest clocks unverified.",
                "preparation_source_sha256": digest(Path(__file__).read_bytes())}
    feed = {"id": "global_stock_feed", "status": "success", "metadata": metadata,
            "data": {"columns": ["Ticker", "Price", "timestamp", "ledger_id"], "rows": rows,
                     "assets": assets, "declared_targets": list(SYMBOLS),
                     "target_time_iso": horizon.isoformat(), "target_definition": "next XNYS session Close as supplied"}}
    return anchor, horizon, feed, truth


def prepare(dataset, output, model, *, actual_model=None, provider_slug=None, development_count=20, holdout_count=5):
    """Freeze both graph/policy arms and native cohort before any provider call."""
    output = Path(output).resolve()
    if output.exists():
        raise ValueError("refuse to overwrite a prepared study")
    if not isinstance(model, str) or not model.strip():
        raise ValueError("a concrete model identity is required")
    from zenith.budgeted import normalize_provider_slug
    provider_slug = normalize_provider_slug(provider_slug)
    if provider_slug is None:
        raise ValueError("native paid study requires an exact provider_slug")
    if type(development_count) is not int or development_count < 1 or type(holdout_count) is not int or holdout_count < 0:
        raise ValueError("positive development/nonnegative holdout counts required")
    prices, references, exclusions, source = _sources(dataset)
    source_commit = _git(runtime.DEFAULT_ROOT, "rev-parse", "HEAD").decode().strip()
    source_dirty = bool(_git(runtime.DEFAULT_ROOT, "status", "--porcelain").strip())
    dev, dev_indices = _dates(prices, "dev", development_count)
    held, held_indices = _dates(prices, "test", holdout_count)
    graph = build_replacement(runtime.load_graph(runtime.DEFAULT_ROOT))
    output.mkdir(parents=True)
    write_json(output / "predictor.json", graph)
    policies = {name: _policy(name != "baseline") for name in ("baseline", "candidate")}
    for name, policy in policies.items():
        write_json(output / f"{name}-policy.json", policy)
    truth_rows, issues, reference_issues = [], [], {name: {} for name in ("no_change", "past_one_session_momentum")}
    for split, dates, indices in (("development", dev, dev_indices), ("holdout", held, held_indices)):
        for stamp in dates:
            anchor, target, feed, truth = _snapshot(prices, indices, stamp, references)
            feed_dir = output / "recorded" / stamp
            write_json(feed_dir / "artifacts/global_stock_feed.json", feed)
            write_json(feed_dir / "runtime_context.json", {"as_of": anchor.isoformat(), "time_anchor": anchor.isoformat()})
            truth_rows.extend(truth)
            for reference in reference_issues:
                predictions = []
                for asset, observation in zip(feed["data"]["assets"], truth):
                    quote = asset["observed_ohlcv"]["Close"]
                    movement = 0 if reference == "no_change" else asset["derived_features"]["return_1"]
                    predicted = quote * (1 + movement)
                    predictions.append({"target_id": asset["symbol"], "target_price": predicted,
                        "target_price_relative_error": abs(predicted - observation["price"]) / observation["price"]})
                reference_issues[reference][stamp] = {"split": split, "target_count": len(predictions),
                    "per_target": predictions,
                    "issue_score": sum(row["target_price_relative_error"] for row in predictions) / len(predictions)}
            issues.append({"issue_id": stamp, "feed_source": str(feed_dir), "time_anchor": anchor.isoformat(),
                           "target_time": target.isoformat(), "horizon_id": "next_us_close",
                           "target_ids": list(SYMBOLS), "split": split})
    write_json(output / "truth.json", {"metadata": {"status": "success", "price_basis": PRICE_BASIS,
        "currency": "USD", "synthetic_fixture": False, "dataset_commit": source["dataset_commit"]},
        "data": {"rows": truth_rows}})
    write_json(output / "feedback-policy.json", {"schema": "zenith_forecast_feedback_policy_v1",
        "policy_id": "stocknet_next_session_close_v1", "price_basis": PRICE_BASIS,
        "currency": "USD", "observation_precision": "timestamp", "relative_error_threshold": 0.05})
    candidates = []
    for name in ("baseline", "candidate"):
        candidates.append({"candidate_id": name,
            "hypothesis": "fixed compact price-only predictor" if name == "baseline" else
                          "Conservative movement sizing reduces recurring target magnitude error on matched episodes.",
            "change": "none" if name == "baseline" else "lab_director.skill_addon only: " + SKILL_ADDON,
            "source_commit": source_commit,
            "model": model, "actual_model": actual_model or model,
            "provider": "openrouter_budgeted", "execution_kind": "openrouter_budgeted",
            "graph_variant": "predictor.json", "reasoning_policy": f"{name}-policy.json",
            "context_profile": "original", "prompt_sha256": canonical_digest({
                "profile": PROFILE, "graph": graph, "policy": policies[name],
                "meaning": "static template identity; dated prompt bytes recorded by native provider"})})
        if provider_slug is not None:
            candidates[-1]["provider_slug"] = provider_slug
    raw = {"schema": cohort.SCHEMA, "issues": issues, "candidates": candidates,
           "feedback_policy": "feedback-policy.json", "truth_source": "truth.json",
           "truth_as_of": "2016-01-01T00:00:00+00:00", "max_trials": 2,
           "max_calls_per_run": 2, "minimum_improvement": 0.0, "embargo_days": 1}
    write_json(output / "spec.json", raw)
    cohort.freeze(output / "spec.json", output / "cohort")
    reference_report = {"metric": "mean_issue_mean_target_price_relative_error", "model_arms": False,
        "scope": "deterministic references on the full fixed issue/target support; no model-response filtering",
        "per_issue": reference_issues,
        "scores": {split: {name: sum(row["issue_score"] for row in values.values() if row["split"] == split)
                   / sum(row["split"] == split for row in values.values())
                   for name, values in reference_issues.items()}
                   for split in ("development", "holdout")
                   if any(issue["split"] == split for issue in issues)}}
    write_json(output / "reference-baselines.json", reference_report)
    preparation = {"schema": "stocknet_compact_native_preparation_v1", "profile": PROFILE,
        "source_manifest_sha256": digest((Path(dataset) / "source-manifest.json").read_bytes()),
        "price_sources": references, "price_row_exclusions": exclusions,
        "development_issue_dates": dev, "holdout_issue_dates": held,
        "available_feed_lanes": ["STOCK"], "native_lab_execution": "explicit 3-node replacement, not original 28-node Lab",
        "candidate_diff": {"node_id": "lab_director", "parameter": "skill_addon", "before": "", "after": SKILL_ADDON},
        "preparation_source_sha256": digest(Path(__file__).read_bytes()),
        "source_commit": source_commit, "checkout_dirty_at_preparation": source_dirty,
        "source_identity_boundary": "Git HEAD identifies the checkout; exact native implementation, graph and input hashes bind any uncommitted source bytes.",
        "cohort_sha256": digest((output / "cohort/cohort.json").read_bytes()),
        "reference_baselines_sha256": digest((output / "reference-baselines.json").read_bytes()),
        "selection": "first common mature dates in fixed dev/test splits, not outcome-selected",
        "historical_exposure": "Earlier flat study exposed some August development outcomes; no new unseen-development claim. StockNet test prices were previously scored by deterministic baselines; no pristine-holdout claim.",
        "limitations": ["Modern pretrained model may remember historical outcomes.",
                        "Yahoo price vintage, adjustments and original availability not authenticated.",
                        "Count gates and descriptive paired losses do not establish statistical significance.",
                        "One predeclared candidate, not automatic graph learning or StockNet paper reproduction."]}
    write_json(output / "preparation.json", preparation)
    return preparation


def plan(study):
    """Read-only scope/resource projection; no provider or target observations read."""
    study = Path(study).resolve()
    spec = read_json(study / "cohort/cohort.json")
    prepared = read_json(study / "preparation.json")
    if digest((study / "cohort/cohort.json").read_bytes()) != prepared["cohort_sha256"]:
        raise ValueError("prepared cohort identity differs")
    graph = runtime.load_graph(runtime.DEFAULT_ROOT, spec["candidates"][0]["graph_variant_payload"])
    instruction_bytes = {key: len(graph[key].instruction.encode()) for key in ("lab_decide", "lab_director")}
    feed_bytes = max(len((study / "cohort" / issue["feed_source"] / "artifacts/global_stock_feed.json").read_bytes())
                     for issue in spec["issues"])
    # Source views have a frozen character cap; UTF-8 is at most four bytes per
    # character. Receipt/tool/JSON guardrail overhead is accounted separately.
    overhead = 16000
    request_bound = 4 * CONTEXT_CHARS + max(instruction_bytes.values()) + overhead
    calls = len(spec["issues"]) * len(spec["candidates"]) * 2
    return {"schema": "stocknet_compact_native_plan_v1", "model": spec["candidates"][0]["model"],
            "graph_nodes": sorted(graph), "waves": [["global_stock_feed"], ["lab_decide"], ["lab_director"]],
            "maximum_calls": calls, "calls_per_complete_run": 2, "validation_attempts_per_skill": 1,
            "development_issues": len([issue for issue in spec["issues"] if issue["split"] == "development"]),
            "holdout_issues": len([issue for issue in spec["issues"] if issue["split"] == "holdout"]),
            "maximum_recorded_feed_utf8_bytes": feed_bytes, "instruction_utf8_bytes": instruction_bytes,
            "maximum_request_utf8_bytes_estimate": request_bound,
            "request_bound_interpretation": "Conservative source-view cap plus 16000-byte native prompt/receipt allowance; provider checks exact request capacity and reserves exact byte bound before every call.",
            "maximum_output_tokens_per_call": 4096, "maximum_input_token_reservation_estimate": calls * request_bound,
            "maximum_output_tokens": calls * 4096, "paid_calls_here": False,
            "holdout_execution": "Only baseline and development-selected eligible candidate; ceiling includes both arms.",
            "claim_boundary": "Resource plan only, no completed execution or empirical result."}


def run(study, *, phase, budget_dir, max_cost_usd="5", max_calls=128,
        max_output_tokens=4096, pause_seconds=2.0, env_file=None):
    """Invoke existing native run/import owners once per missing episode, no retry."""
    study = Path(study).resolve()
    prepared = read_json(study / "preparation.json")
    if prepared["preparation_source_sha256"] != digest(Path(__file__).read_bytes()):
        raise ValueError("study preparation source changed")
    if phase not in {"development", "holdout"}:
        raise ValueError("phase must be development or holdout")
    if pause_seconds < 0:
        raise ValueError("pause_seconds must be nonnegative")
    if env_file is not None:
        from system.lib.openrouter_free_runtime import load_env_file
        load_env_file(env_file)
    selected = {"baseline", "candidate"}
    if phase == "holdout":
        development = cohort.evaluate(study / "cohort")
        if development["state"] != "complete" or development["issue_count"] < 20:
            raise ValueError("complete twenty-issue development required before holdout execution")
        eligible = [key for key, value in development["decisions"].items() if value == "candidate_proposal"]
        selected = {"baseline", min(eligible, key=lambda name: (development["scores"][name], name))} if eligible else {"baseline"}
    actions = cohort.next_actions(study / "cohort")
    spec = read_json(study / "cohort/cohort.json")
    receipts = []
    for row in actions["actions"]:
        if row["split"] != phase or row["candidate_id"] not in selected:
            continue
        candidate, issue = cohort.select(spec, row["candidate_id"], row["issue_id"])
        marker = study / "native-attempts" / f"{row['candidate_id']}-{row['issue_id']}.json"
        if marker.exists():
            raise ValueError("native episode already attempted; no automatic retry")
        run_id = "COHORT_" + digest((study / "cohort/cohort.json").read_bytes())[:12] + "_" + row["candidate_id"] + "_" + row["issue_id"]
        run_dir = runtime.runs_root(runtime.DEFAULT_ROOT) / run_id
        if run_dir.exists():
            raise ValueError("native run already exists; inspect and attach explicitly")
        write_json(marker, {"state": "started", "run_id": run_id, "candidate_id": row["candidate_id"], "issue_id": row["issue_id"]})
        outcome = None
        try:
            outcome = runtime.start(runtime.DEFAULT_ROOT, mission="lab", target="lab_director", run_id=run_id,
                provider=candidate["provider"], model=candidate["model"], provider_slug=candidate.get("provider_slug"),
                feed_source=str(study / "cohort" / issue["feed_source"]), time_anchor=issue["time_anchor"],
                horizon=issue["horizon_id"], graph_variant=str(study / "cohort" / candidate["graph_variant"]),
                policy=str(study / "cohort" / candidate["reasoning_policy"]), context_profile="original",
                max_cost_usd=max_cost_usd, max_calls=max_calls, max_output_tokens=max_output_tokens, budget_dir=budget_dir)
        except Exception as error:
            outcome = {"status": "error", "error": f"{type(error).__name__}: {error}"}
        receipt = cohort.attach(study / "cohort", candidate_id=row["candidate_id"], issue_id=row["issue_id"], run=run_dir)
        write_json(marker, {"state": "finished", "run_id": run_id, "native_result": outcome, "import_receipt": receipt})
        receipts.append(receipt)
        if receipt["state"] != "complete":
            break  # retain failure and stop; no incomplete comparison or subsequent spending
        if pause_seconds:
            time.sleep(pause_seconds)
    return {"phase": phase, "imports": receipts, "automatic_selection_or_promotion": False,
            "comparison": cohort.evaluate(study / "cohort") if phase == "development" else None,
            "final_seal": "Use research cohort-evaluate --final-key explicitly after heldout imports."}


def pilot(dataset, output, model, *, budget_dir, provider_slug=None, max_cost_usd="5", max_calls=128, max_output_tokens=4096, env_file=None):
    """One excluded July episode checks native/provider compatibility, not accuracy."""
    output = Path(output).resolve()
    if output.exists():
        raise ValueError("pilot output already exists; no retry")
    prices, references, _, _ = _sources(dataset)
    indices = {symbol: {row["Date"]: index for index, row in enumerate(rows)
                         if "2015-07-01" <= row["Date"] < "2015-07-15" and index >= 20}
               for symbol, rows in prices.items()}
    stamp = sorted(set.intersection(*(set(value) for value in indices.values())))[0]
    anchor, horizon, feed, _ = _snapshot(prices, indices, stamp, references)
    output.mkdir(parents=True)
    write_json(output / "recorded/artifacts/global_stock_feed.json", feed)
    write_json(output / "recorded/runtime_context.json", {"as_of": anchor.isoformat()})
    write_json(output / "predictor.json", build_replacement(runtime.load_graph(runtime.DEFAULT_ROOT)))
    write_json(output / "baseline-policy.json", _policy())
    run_id = "PILOT_" + canonical_digest({"path": str(output), "model": model, "provider_slug": provider_slug})[:16]
    write_json(output / "pilot.json", {"schema": "stocknet_native_compatibility_pilot_v1", "model": model,
        "issue_date": stamp, "run_id": run_id, "provider_slug": provider_slug, "study_membership": "excluded from dev/holdout",
        "maximum_calls": 2, "output_tokens_per_call": max_output_tokens,
        "source_sha256": digest(Path(__file__).read_bytes()), "accuracy_evaluation": False})
    if env_file is not None:
        from system.lib.openrouter_free_runtime import load_env_file
        load_env_file(env_file)
    result = runtime.start(runtime.DEFAULT_ROOT, mission="lab", target="lab_director", run_id=run_id,
        provider="openrouter_budgeted", model=model, provider_slug=provider_slug, feed_source=str(output / "recorded"),
        time_anchor=anchor.isoformat(), horizon="next_us_close", graph_variant=str(output / "predictor.json"),
        policy=str(output / "baseline-policy.json"), max_cost_usd=max_cost_usd, max_calls=max_calls,
        max_output_tokens=max_output_tokens, budget_dir=budget_dir)
    write_json(output / "native-result.json", result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prepare_cmd = commands.add_parser("prepare")
    prepare_cmd.add_argument("--dataset", type=Path, default=Path("work/datasets/stocknet"))
    prepare_cmd.add_argument("--output", type=Path, required=True)
    prepare_cmd.add_argument("--model", required=True)
    prepare_cmd.add_argument("--actual-model")
    prepare_cmd.add_argument("--provider-slug", required=True)
    plan_cmd = commands.add_parser("plan"); plan_cmd.add_argument("--study", type=Path, required=True)
    execute = commands.add_parser("run")
    execute.add_argument("--study", type=Path, required=True)
    execute.add_argument("--phase", choices=("development", "holdout"), required=True)
    execute.add_argument("--pause-seconds", type=float, default=2.0)
    pilot_cmd = commands.add_parser("pilot")
    pilot_cmd.add_argument("--dataset", type=Path, default=Path("work/datasets/stocknet"))
    pilot_cmd.add_argument("--output", type=Path, required=True)
    pilot_cmd.add_argument("--model", required=True)
    pilot_cmd.add_argument("--provider-slug")
    for command in (execute, pilot_cmd):
        command.add_argument("--budget-dir", type=Path, required=True)
        command.add_argument("--max-cost-usd", default="5")
        command.add_argument("--max-calls", type=int, default=128)
        command.add_argument("--max-output-tokens", type=int, default=4096)
        command.add_argument("--env-file", type=Path)
    args = vars(parser.parse_args()); name = args.pop("command")
    print(json.dumps(globals()[name](**args), indent=2))


if __name__ == "__main__":
    main()
