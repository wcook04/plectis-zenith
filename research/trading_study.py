"""A bounded, two-node reasoning experiment with executable return accounting.

This adapter reuses the research serialization, numerical baseline and budgeted
provider. It is an explicit experimental graph, not a CP1/CP2 replay. Only the
forecast node's short skill changes; the interpretation is shared within a date.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path

import numpy as np

from benchmarks.stocknet import fit_ridge, ridge_predict
from benchmarks.trading_task import build_dataset, evaluate_predictions, public_projection
from research.engine import canonical, read_json, write_json
from research import trading_protocol as contract
from zenith.budgeted import OpenRouterBudgetedProvider
from zenith.providers import digest as provider_digest
from system.lib.openrouter_free_runtime import safe_error

ROOT = Path(__file__).resolve().parents[1]
ARMS = ("trace_feedback", "outcome_only", "feedback_blinded")
SPLITS = {"fit": ["2013-01-01", "2015-01-01"],
          "training": ["2015-01-01", "2016-01-01"],
          "validation": ["2016-01-01", "2016-07-01"],
          "test": ["2016-07-01", "2017-09-01"]}
COUNTS = {"training": 20, "validation": 10, "test": 40}
RICH_SPLITS = {"fit": ["2019-01-01", "2022-06-01"],
               "training": ["2022-06-08", "2023-06-01"],
               "validation": ["2023-06-01", "2024-01-01"],
               "test": ["2024-01-01", "2025-03-29"]}
RICH_COUNTS = {"training": 9, "validation": 6, "test": 12}
BASE_SKILL = ("Start from the supplied regularized numerical anchor. Treat the trailing "
    "history as weak, noisy evidence: distinguish overnight gaps from intraday returns. "
    "Use the interpretation as a hypothesis, not an additional independent observation. "
    "Assess whether continuation, reversal, volatility or volume supplies a concrete reason "
    "to adjust the expected next-session open-to-close arithmetic return. Account for "
    "asymmetric plausible gains and losses; direction probability is not expected return. "
    "For supplied news and filings, distinguish new horizon-relevant information from "
    "old facts, repeated reports and events likely already priced in. Explain any causal "
    "hypothesis without treating it as established. Prefer a small or zero correction "
    "when evidence is weak. Do not invent catalysts or "
    "use remembered outcomes. Give each asset a calibrated mean and a short explanation "
    "with supplied evidence references. Abstain for unavailable inputs, not merely uncertainty.")


def sha(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def source_hashes():
    names = ["research/trading_study.py", "research/trading_protocol.py",
             "benchmarks/trading_task.py", "benchmarks/stocknet.py",
             "research/engine.py", "zenith/budgeted.py", "zenith/providers.py",
             "system/lib/openrouter_free_runtime.py"]
    names += ["benchmarks/finmultitime.py"]
    if (ROOT / "benchmarks/finmultitime_trading.py").exists():
        names += ["benchmarks/finmultitime_trading.py"]
    return {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in names}


def choose_dates(rows, count):
    """Deterministic coverage-only spacing, never consulted outcomes."""
    dates = sorted({r["issue_date"] for r in rows})
    if count < 1 or len(dates) < count:
        raise ValueError("insufficient dates for the frozen schedule")
    indices = np.linspace(0, len(dates) - 1, count, dtype=int)
    return [dates[int(i)] for i in indices]


def available(rows):
    return [r for r in rows if r.get("features") is not None and r.get("actual_return") is not None]


def fit_anchor(rows, names):
    fit = fit_ridge(available(rows))
    fit["feature_names"] = list(names)
    return fit


def grouped(rows):
    result = defaultdict(list)
    for row in rows:
        result[row["issue_date"]].append(row)
    return dict(sorted(result.items()))


def freeze(dataset, study, *, budget, authorization, profile="stocknet"):
    if study.exists():
        raise ValueError("refuse to overwrite a study")
    if profile == "finmultitime":
        from benchmarks.finmultitime_trading import build_dataset as rich_dataset
        split_spec, counts = RICH_SPLITS, RICH_COUNTS
        data = rich_dataset(dataset, split_spec, counts)
    elif profile == "stocknet":
        split_spec, counts = SPLITS, COUNTS
        data = build_dataset(dataset, split_spec, symbols=["AAPL", "MSFT", "GOOG"])
    else:
        raise ValueError("unknown data profile")
    selected = {phase: choose_dates(data["splits"][phase], count) for phase, count in counts.items()}
    splits = {phase: [r for r in rows if phase == "fit" or r["issue_date"] in selected[phase]]
              for phase, rows in data["splits"].items()}
    fit = fit_anchor(splits["fit"], data["feature_names"])
    # A stronger numerical control receives the same matured training outcomes
    # as the learner; the old anchor is not its only opponent.
    refit = fit_anchor(splits["fit"] + splits["training"], data["feature_names"])
    compact = {phase: [{k: v for k, v in row.items() if k not in ("history20", "preceding_close")}
                       for row in rows] for phase, rows in splits.items()}
    # Preserve exact actual prediction packets separately from evaluator truth.
    packets = {}
    symbols = sorted(data["symbols"])
    for phase in counts:
        for stamp, rows in grouped(splits[phase]).items():
            packets[stamp] = packet_from_rows(rows, fit, symbols, data["feature_names"])
    spec = {"schema": "zenith_trading_study_v1", "created_at": datetime.now(timezone.utc).isoformat(),
        "profile": profile, "splits": split_spec, "selected_dates": selected, "symbols": symbols, "feature_names": data["feature_names"],
        "question": "Does feedback-conditioned forecast-skill revision improve later net decisions beyond a frozen competent graph and equally funded proposal generation?",
        "target": "conditional mean of next-session Close/Open-1; issue after prior close",
        "base_skill": BASE_SKILL, "arms": list(ARMS), "rounds": 2, "candidates_per_arm_per_round": 1,
        "selection": "mean validation daily net return among fully schema-accepted candidate responses; unchanged wins ties; no selection on test",
        "costs": {"fee_bps_per_side": 1, "slippage_bps_per_side": 4, "cash_return": 0},
        "test_controls": ["baseline", "baseline_repeat", "flat", "zero", "always_long", "ridge", "refit_ridge", "shrinkage"] + (["price_only"] if profile == "finmultitime" else []),
        "block_bootstrap": {"block_sessions": 5, "replicates": 10000, "seed": 104729,
                            "interval": "Bonferroni family coverage .95 for three selected update arms versus baseline"},
        "source_hashes": source_hashes(), "dataset_source_manifest_sha256": data["source_manifest_sha256"],
        "anchor": fit, "refit_anchor": refit, "budget": budget, "authorization": authorization,
        "coverage": data["coverage"], "input_sha256": sha(compact), "packets_sha256": sha(packets),
        "exposure": "Prior StockNet study outcomes informed design; these are not pristine research-development conditions. All periods were publicly obtainable; masking does not establish absence of model training contamination. Retrospective reconstruction, not prospective performance.",
        "execution": "Experimental interpretation -> forecast graph using existing provider and typed validator; not the original CP1/CP2 graph. All candidate arms reuse each date's exact interpretation. Interpretation failure omits that dependency and remains recorded; forecast failure stays cash. A schema-rejected validation response disqualifies candidate selection.",
        "limits": "One adaptive study on the declared stocks/dates. No live orders, no established novelty or profitable strategy. Blocks on the sparse schedule preserve schedule adjacency, not all market sessions.",
        "critic_boundary": "Only training review evidence reaches the trace-guided proposer. These later articles are hypotheses about events, not causal labels. Manual investigator comments do not enter any proposal. Assessment outcomes are never used to rewrite the frozen skill or selector."}
    # Label maturity is enforced by the dataset builder; verify the actual split.
    for phase, rows in compact.items():
        if any(r["target_date"] >= split_spec[phase][1] for r in rows):
            raise ValueError("outcome crosses split end")
    study.mkdir(parents=True)
    write_json(study / "inputs.json", compact)
    write_json(study / "packets.json", packets)
    write_json(study / "frozen.json", spec)
    write_json(study / "binding.json", {"frozen_sha256": sha(spec)})
    return {"study": str(study), "frozen_sha256": sha(spec), "dates": selected}


def packet_from_rows(rows, fit, symbols, names):
    assets = []
    for row in sorted(rows, key=lambda r: r["symbol"]):
        aid = "asset_" + str(symbols.index(row["symbol"]) + 1)
        projection = public_projection(row)
        history = [{k: r[k] for k in ("Open", "High", "Low", "Close", "Volume")}
                   for r in projection.get("history20", [])]
        asset = {"asset_id": aid, "evidence_refs": [aid + ":history", aid + ":state", aid + ":anchor"],
            "history20": history, "preceding_close": projection.get("preceding_close"),
            "features": dict(zip(names, row["features"], strict=True)) if row.get("features") else None,
            "anchor_mean_return": ridge_predict(row, fit) if row.get("features") else None,
            "info_status": row["info_status"]}
        if "context_evidence" in row:
            asset["context_evidence"] = [{**r, "ref_id": aid + ":" + r["ref_id"]} for r in row["context_evidence"]]
            asset["evidence_refs"] += [r["ref_id"] for r in asset["context_evidence"]]
        assets.append(asset)
    first = rows[0]
    packet = {"schema": "zenith_trading_packet_v1", **{k: first[k] for k in ("issue_date", "issue_at", "entry_at", "exit_at")}, "assets": assets}
    if any("context_evidence" in a for a in assets):
        packet["schema"] = "zenith_trading_packet_v2"
    packet["packet_sha256"] = sha(packet)
    return packet


def price_packet(packet):
    """Remove only admitted text/filings; keep the identical numerical state."""
    result = json.loads(canonical(packet))
    result.pop("packet_sha256")
    result["schema"] = "zenith_trading_packet_v1"
    for asset in result["assets"]:
        asset.pop("context_evidence", None)
        asset["evidence_refs"] = [asset["asset_id"] + ":" + k for k in ("history", "state", "anchor")]
    result["packet_sha256"] = sha(result)
    return result


def load(study):
    spec = read_json(study / "frozen.json")
    if sha(spec) != read_json(study / "binding.json")["frozen_sha256"]:
        raise ValueError("frozen protocol changed")
    if spec["source_hashes"] != source_hashes():
        raise ValueError("study source changed; do not edit an active study")
    inputs, packets = read_json(study / "inputs.json"), read_json(study / "packets.json")
    if sha(inputs) != spec["input_sha256"] or sha(packets) != spec["packets_sha256"]:
        raise ValueError("frozen data changed")
    return spec, inputs, packets


def ask(study, key, prompt, spec):
    directory = study / "calls" / key
    directory.mkdir(parents=True, exist_ok=True)
    request = {"prompt": prompt, "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest()}
    path = directory / "request.json"
    if path.exists() and read_json(path) != request:
        raise ValueError("existing exact request differs")
    write_json(path, request)
    options = spec["budget"]
    provider = OpenRouterBudgetedProvider(directory, options["model"], options["max_cost_usd"],
        options["max_calls"], options["max_output_tokens"], Path(options["budget_dir"]), provider_slug=options["provider_slug"])
    return provider.ask_ai(prompt, {"meta": {"session_id": directory.name, "node_id": "reasoning"}})


def _seal_record(record):
    record = dict(record)
    record.pop("record_sha256", None)
    record["record_sha256"] = sha(record)
    return record


def _response_source(study, key, prompt, raw, spec):
    """Join recorded response bytes to the exact settled paid call, without calls."""
    options = spec["budget"]
    if not options and spec.get("authorization", {}).get("synthetic") is True:
        return {"verification_boundary": "injected synthetic test transport; no paid identity"}
    identity = {"run_id": key, "node_id": "reasoning",
                "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
                "provider": "openrouter_budgeted", "requested_model": options["model"]}
    if options.get("provider_slug") is not None:
        identity["provider_slug"] = options["provider_slug"]
    call_id = provider_digest(identity)
    directory = study / "calls" / key
    request = {"prompt": prompt, "prompt_sha256": identity["prompt_sha256"]}
    if read_json(directory / "request.json") != request:
        raise ValueError("cached request differs from exact prompt")
    path = directory / "handoff/api_calls/openrouter_budgeted" / (call_id + ".json")
    ledger_path = Path(options["budget_dir"]) / "budget.json"
    if not path.exists():
        ledger = read_json(ledger_path) if ledger_path.exists() else {}
        if raw is None and call_id not in ledger.get("entries", {}):
            return {"verification_boundary": "no reservation receipt; failure before recorded paid attempt"}
        raise ValueError("cached response has no recorded paid attempt")
    call = read_json(path)
    ledger = read_json(ledger_path)
    if call != ledger["entries"].get(call_id):
        raise ValueError("cached local call differs from shared budget authority")
    for field in ("run_id", "node_id", "prompt_sha256", "provider", "requested_model"):
        if call.get(field) != identity[field]:
            raise ValueError("cached call identity differs")
    if (call.get("call_id") != call_id or call.get("execution_kind") != "openrouter_budgeted"
            or call.get("max_output_tokens") != options["max_output_tokens"]
            or call.get("requested_provider_slug") != options.get("provider_slug")
            or Path(call["budget_dir"]).resolve() != Path(options["budget_dir"]).resolve()):
        raise ValueError("cached call budget binding differs")
    if raw is None:
        if call.get("status") != "failed":
            raise ValueError("failed node observation differs from paid call state")
    else:
        receipt = call.get("provider_receipt", {})
        if (call.get("status") != "response_supplied" or call.get("cost") is None
                or receipt.get("response_text") != raw
                or call.get("response_sha256") != hashlib.sha256(raw.encode()).hexdigest()):
            raise ValueError("cached raw response differs from settled paid response")
        if options.get("provider_slug") is not None and (
                call.get("requested_provider_slug") != options["provider_slug"]
                or not call.get("verified_provider_name")
                or receipt.get("actual_provider") != call["verified_provider_name"]):
            raise ValueError("cached response provider differs from frozen pin")
    return {"call_id": call_id, "call_path": str(path), "call_sha256": sha(call),
            "verification_boundary": "recorded settled local and shared-budget bytes; not external billing certification"}


def _node_record(raw, parser):
    try:
        value = parser(raw)
        result = {"status": "accepted", "value": value}
    except ValueError as exc:
        result = {"status": "rejected", "error": str(exc), "value": None}
    return {**result, "raw_response": raw,
            "raw_response_sha256": hashlib.sha256(raw.encode()).hexdigest()}


def _cached_record(path, binding, parser, *, study, key, prompt, spec):
    record = read_json(path)
    if record != _seal_record(record) or record.get("binding") != binding:
        raise ValueError("cached node record hash or binding differs")
    raw = record.get("raw_response")
    if record.get("status") == "transport_failed":
        if (raw is not None or record.get("raw_response_sha256") is not None
                or record.get("value") is not None or not isinstance(record.get("error"), str)):
            raise ValueError("invalid cached transport failure")
    else:
        if not isinstance(raw, str):
            raise ValueError("cached node raw response missing")
        parsed = _node_record(raw, parser)
        if any(record.get(k) != v for k, v in parsed.items()):
            raise ValueError("cached node differs from semantic reparse")
    if record.get("response_source") != _response_source(study, key, prompt, raw, spec):
        raise ValueError("cached node response source differs")
    return record


def _observe_node(path, binding, parser, *, study, key, prompt, spec):
    if path.exists():
        return _cached_record(path, binding, parser, study=study, key=key, prompt=prompt, spec=spec)
    try:
        text = ask(study, key, prompt, spec)
    except Exception as exc:
        record = {"status": "transport_failed", "value": None, "raw_response": None,
                  "raw_response_sha256": None, "error": safe_error(exc), "binding": binding}
        record["response_source"] = _response_source(study, key, prompt, None, spec)
        write_json(path, _seal_record(record))
        raise  # Stop this execution on provider/unknown-cost failure; no automatic continuation.
    record = {**_node_record(text, parser), "binding": binding,
              "response_source": _response_source(study, key, prompt, text, spec)}
    write_json(path, _seal_record(record))
    return _seal_record(record)


def interpreted(study, stamp, packet, spec):
    path = study / "interpretations" / (stamp + ".json")
    return _observe_node(path, {"packet_sha256": packet["packet_sha256"]},
        lambda text: contract.parse_interpretation(text, packet), study=study,
        key="interpret_" + stamp, prompt=contract.interpretation_prompt(packet), spec=spec)


def forecast(study, stamp, packet, interpretation, skill, name, spec):
    path = study / "forecasts" / name / (stamp + ".json")
    binding = {"packet_sha256": packet["packet_sha256"], "interpretation_sha256": sha(interpretation), "skill_sha256": sha(skill)}
    dependency = interpretation.get("value") if interpretation is not None else None
    return _observe_node(path, binding, lambda text: contract.parse_forecast(text, packet, dependency),
        study=study, key=name + "_" + stamp,
        prompt=contract.forecast_prompt(packet, dependency, skill), spec=spec)


def predictions(rows, records, symbols):
    result = {}
    for stamp, group in grouped(rows).items():
        record = records.get(stamp, {})
        values = record.get("value") or {}
        forecasts = {r["asset_id"]: r for r in values.get("forecasts", [])}
        for row in group:
            aid = "asset_" + str(symbols.index(row["symbol"]) + 1)
            value = forecasts.get(aid)
            result[row["sample_id"]] = (value["mean_expected_return"] if value and not value["abstain"] else {"status": "rejected"})
    return result


def evaluate(rows, records, symbols):
    result = evaluate_predictions(rows, predictions(rows, records, symbols))
    result["summary"]["schema_rejected_dates"] = sum(r.get("status") != "accepted" for r in records.values())
    add_forecast_metrics(result)
    return result


def add_forecast_metrics(result):
    rows = result["asset_rows"]
    squared = [(r["predicted_return"] - r["actual_return"]) ** 2 for r in rows
               if r["forecast_status"] == "accepted" and r["actual_return"] is not None]
    result["summary"].update(numeric_forecasts=len(squared), forecast_allowances=len(rows),
        mean_squared_return_error=math.fsum(squared) / len(squared) if len(squared) == len(rows) else None,
        mse_support="complete only; abstention/failure cannot improve an error score through omitted cases")


def run_forecasts(study, phase, policies, *, flat=(), price_only=()):
    spec, inputs, packets = load(study)
    if phase == "test" and not (study / "selection.json").exists():
        raise ValueError("freeze selection before test inference")
    rows = inputs[phase]
    results = {name: {} for name in policies}
    for stamp in spec["selected_dates"][phase]:
        packet = packets[stamp]
        interpretation = interpreted(study, stamp, packet, spec)
        reduced = price_packet(packet) if price_only else None
        reduced_interpretation = interpreted(study, "price_only_" + stamp, reduced, spec) if price_only else None
        with ThreadPoolExecutor(max_workers=3) as pool:
            futures = {name: pool.submit(forecast, study, stamp, reduced if name in price_only else packet,
                None if name in flat else reduced_interpretation if name in price_only else interpretation,
                skill, name, spec) for name, skill in policies.items()}
            for name, future in futures.items():
                results[name][stamp] = future.result()
        print(json.dumps({"phase": phase, "date": stamp, "policies": list(policies)}), flush=True)
    evaluated = {name: evaluate(rows, records, spec["symbols"]) for name, records in results.items()}
    for name, result in evaluated.items():
        write_json(study / "evaluations" / phase / (name + ".json"), result)
    return evaluated


def all_training_feedback(study, spec, inputs, packets, names):
    """Complete training denominator; no validation/test values enter proposals."""
    result = []
    for name in names:
        evaluation_path = study / "evaluations/training" / (name + ".json")
        if not evaluation_path.exists():
            candidate = read_json(study / "candidates" / (name + ".json"))
            if candidate["status"] != "rejected":
                raise ValueError("missing training evaluation for an accepted candidate")
            result.append({"policy_id": name, "summary": {"status": "proposal_rejected"}, "daily": [], "traces": []})
            continue
        evaluation = read_json(evaluation_path)
        traces = []
        for stamp, rows in grouped(inputs["training"]).items():
            record = read_json(study / "forecasts" / name / (stamp + ".json"))
            # Complete date/asset support, compact state view. Full historical
            # OHLCV requests remain on disk; the proposer receives this declared
            # summary, not a purported complete language-model thought trace.
            case = {"case_id": "training_" + str(spec["selected_dates"]["training"].index(stamp)),
                "forecast": [{**{k: v for k, v in f.items() if k != "reasoning"}, "reasoning_excerpt": f["reasoning"][:160]}
                             for f in (record["value"] or {}).get("forecasts", [])],
                "status": record["status"], "outcomes": [{"asset_id": "asset_" + str(spec["symbols"].index(row["symbol"]) + 1),
                                                        "actual_return": row["actual_return"]} for row in rows]}
            if name == "baseline":
                case["state"] = [{k: a[k] for k in ("asset_id", "features", "anchor_mean_return")} for a in packets[stamp]["assets"]]
                interpretation = read_json(study / "interpretations" / (stamp + ".json"))["value"]
                case["interpretation"] = [{"asset_id": r["asset_id"], "summary_excerpt": r["summary"][:160]}
                                           for r in (interpretation or {}).get("interpretations", [])]
                if spec["profile"] == "finmultitime":
                    case["admitted_context"] = [{"asset_id": a["asset_id"], "evidence": [{**e, "content": e["content"][:240]}
                        for e in a.get("context_evidence", [])]} for a in packets[stamp]["assets"]]
                    case["later_review_evidence"] = [{**e, "content": e["content"][:240]}
                        for row in rows for e in row.get("review_evidence", [])]
            traces.append(case)
        result.append({"policy_id": name, "summary": evaluation["summary"], "daily": evaluation["daily"], "traces": traces})
    return result


def development(study):
    spec, _, _ = load(study)
    if (study / "selection.json").exists():
        raise ValueError("development closed after selection")
    policies = {"baseline": spec["base_skill"]}
    reduced = ("price_only",) if spec["profile"] == "finmultitime" else ()
    if reduced:
        policies["price_only"] = spec["base_skill"]
    scores = run_forecasts(study, "training", policies, price_only=reduced)
    return {name: result["summary"] for name, result in scores.items()}


def learn(study):
    spec, inputs, packets = load(study)
    if (study / "selection.json").exists() or (study / "final-seal.json").exists():
        raise ValueError("learning is closed after selection")
    run_forecasts(study, "training", {"baseline": spec["base_skill"]})
    for round_id in range(spec["rounds"]):
        policies = {}
        for arm in ARMS:
            name = f"{arm}_r{round_id + 1}"
            path = study / "candidates" / (name + ".json")
            previous = [f"{arm}_r{i + 1}" for i in range(round_id)]
            feedback = all_training_feedback(study, spec, inputs, packets, ["baseline", *previous])
            archive = [read_json(study / "candidates" / (n + ".json")) for n in previous]
            matrix = np.asarray([r["features"] for r in inputs["training"] if r["features"] is not None])
            marginals = {feature: {"count": len(matrix), "mean": float(matrix[:, j].mean()),
                "std": float(matrix[:, j].std()), "min": float(matrix[:, j].min()), "max": float(matrix[:, j].max())}
                for j, feature in enumerate(spec["feature_names"])}
            refs = ["training_" + str(i) for i in range(len(spec["selected_dates"]["training"]))]
            context = {"feature_names": spec["feature_names"], "feature_marginals": marginals,
                "baseline_skill": spec["base_skill"], "allowed_evidence_refs": refs,
                "outcomes": [{"policy_id": f["policy_id"], "summary": f["summary"],
                    "daily": [{k: r[k] for k in ("net_return", "gross_return", "cost_return", "invested_allowances", "forecast_failure_count")} for r in f["daily"]]} for f in feedback],
                "trace_bins": [{"policy_id": f["policy_id"], "cases": f["traces"]} for f in feedback]}
            # No feedback-bearing incumbent/ordering enters blind generation.
            archive_view = [{"skill": r["skill"]} for r in archive if r["status"] == "accepted"]
            prompt = contract.skill_prompt(arm, context, archive_view, name)
            prompt_hash = hashlib.sha256(prompt.encode()).hexdigest()
            observation = _observe_node(study / "proposals" / (name + ".json"),
                {"prompt_sha256": prompt_hash}, lambda text: contract.parse_skill_update(text, refs),
                study=study, key="proposal_" + name, prompt=prompt, spec=spec)
            record = {"candidate_id": name, "arm": arm, "round": round_id + 1,
                "status": observation["status"], "proposal_prompt_sha256": prompt_hash,
                "proposal_record_sha256": observation["record_sha256"]}
            if observation["status"] == "accepted":
                record.update(skill=observation["value"]["skill"], proposal=observation["value"])
            else:
                record["error"] = observation["error"]
                record["status"] = "rejected"
            if path.exists() and read_json(path) != record:
                raise ValueError("candidate projection differs from recorded proposal")
            write_json(path, record)
            if record["status"] == "accepted":
                policies[name] = record["skill"]
        if policies:
            run_forecasts(study, "training", policies)
    return {"status": "learning_complete", "attempts": len(list((study / "candidates").glob("*.json")))}


def mean_net(result):
    values = [r["net_return"] for r in result["daily"]]
    if not values or any(v is None or not math.isfinite(v) for v in values):
        raise ValueError("incomplete economic support; no favorable partial score")
    return math.fsum(values) / len(values)


def select(study):
    spec, _, _ = load(study)
    if (study / "selection.json").exists():
        result = read_json(study / "selection.json")
        validate_selection(result, spec)
        return result
    candidates = [read_json(p) for p in sorted((study / "candidates").glob("*.json"))]
    if len(candidates) != len(ARMS) * spec["rounds"]:
        raise ValueError("all preregistered candidate attempts are required")
    policies = {"baseline": spec["base_skill"], **{r["candidate_id"]: r["skill"] for r in candidates if r["status"] == "accepted"}}
    scores = run_forecasts(study, "validation", policies)
    selected = {}
    for arm in ARMS:
        names = ["baseline", *[r["candidate_id"] for r in candidates if r["arm"] == arm and r["status"] == "accepted"
                              and scores[r["candidate_id"]]["summary"]["schema_rejected_dates"] == 0]]
        winner = max(names, key=lambda n: (mean_net(scores[n]), n == "baseline", -names.index(n)))
        selected[arm] = {"candidate_id": winner, "skill": policies[winner], "validation_mean_net": mean_net(scores[winner])}
    result = {"schema": "zenith_trading_selection_v1", "frozen_sha256": sha(spec), "selected": selected,
              "validation_scores": {k: mean_net(v) for k, v in scores.items()}, "live_mutation_permission": False}
    result["selection_sha256"] = sha(result)
    write_json(study / "selection.json", result)
    return result


def validate_selection(selection, spec):
    declared = dict(selection)
    checksum = declared.pop("selection_sha256")
    if sha(declared) != checksum or selection["frozen_sha256"] != sha(spec):
        raise ValueError("selection changed")
    return checksum


def paired_interval(left, right, *, family=3, seed=104729):
    if [r["issue_date"] for r in left] != [r["issue_date"] for r in right]:
        raise ValueError("paired dates differ")
    delta = np.array([a["net_return"] - b["net_return"] for a, b in zip(left, right, strict=True)])
    if not len(delta) or not np.isfinite(delta).all():
        raise ValueError("paired outcomes incomplete")
    rng = np.random.default_rng(seed)
    block = min(5, len(delta))
    starts = rng.integers(0, len(delta), size=(10000, math.ceil(len(delta) / block)))
    indices = ((starts[:, :, None] + np.arange(block)) % len(delta)).reshape(10000, -1)[:, :len(delta)]
    draws = delta[indices].mean(axis=1)
    alpha = .05 / family
    return {"mean_daily_difference": float(delta.mean()), "interval": np.quantile(draws, [alpha / 2, 1 - alpha / 2]).tolist(),
            "positive_dates": int((delta > 0).sum()), "date_count": len(delta), "family_size": family,
            "interpretation": "Descriptive dependent bootstrap on the fixed sampled-date schedule; not proof of independence or population superiority."}


def final(study):
    spec, inputs, _ = load(study)
    selection = read_json(study / "selection.json")
    checksum = validate_selection(selection, spec)
    seal = {"frozen_sha256": sha(spec), "selection_sha256": checksum}
    path = study / "final-seal.json"
    if path.exists() and read_json(path) != seal:
        raise ValueError("final seal differs")
    write_json(path, seal)  # Failures consume this selection; exact resume only.
    if (study / "result.json").exists():
        result = read_json(study / "result.json")
        if result != _seal_record(result) or any(result.get(k) != v for k, v in seal.items()):
            raise ValueError("final result changed")
        return result
    policies = {"baseline": spec["base_skill"], "baseline_repeat": spec["base_skill"], "flat": spec["base_skill"],
                **{arm: record["skill"] for arm, record in selection["selected"].items() if record["candidate_id"] != "baseline"}}
    reduced = ("price_only",) if spec["profile"] == "finmultitime" else ()
    if reduced:
        policies["price_only"] = spec["base_skill"]
    scores = run_forecasts(study, "test", policies, flat=("flat",), price_only=reduced)
    unchanged = [arm for arm, r in selection["selected"].items() if r["candidate_id"] == "baseline"]
    for arm in unchanged:
        scores[arm] = scores["baseline"]
        write_json(study / "evaluations/test" / (arm + ".json"), scores[arm])
    # Numerical controls are fitted without test access. Shrinkage fits a scalar
    # to all completed baseline TRAIN forecasts, not test predictions.
    train_records = {d: read_json(study / "forecasts/baseline" / (d + ".json")) for d in spec["selected_dates"]["training"]}
    train_predictions = predictions(inputs["training"], train_records, spec["symbols"])
    pairs = [(train_predictions[r["sample_id"]], r["actual_return"]) for r in inputs["training"]
             if isinstance(train_predictions[r["sample_id"]], (int, float)) and r["actual_return"] is not None]
    denominator = math.fsum(p * p for p, _ in pairs)
    shrink = max(0, min(1, math.fsum(p * y for p, y in pairs) / denominator)) if denominator else 0
    test_records = {d: read_json(study / "forecasts/baseline" / (d + ".json")) for d in spec["selected_dates"]["test"]}
    test_predictions = predictions(inputs["test"], test_records, spec["symbols"])
    for name in ("zero", "always_long", "ridge", "refit_ridge", "shrinkage"):
        mapped = {}
        for row in inputs["test"]:
            value = test_predictions[row["sample_id"]]
            if name == "zero": value = 0.0
            elif name == "always_long": value = 1.0
            elif name in ("ridge", "refit_ridge"):
                fit = spec["anchor" if name == "ridge" else "refit_anchor"]
                value = ridge_predict(row, fit) if row.get("features") else {"status": "rejected"}
            elif isinstance(value, (int, float)): value *= shrink
            mapped[row["sample_id"]] = value
        scores[name] = evaluate_predictions(inputs["test"], mapped)
        add_forecast_metrics(scores[name])
        write_json(study / "evaluations/test" / (name + ".json"), scores[name])
    result = {"schema": "zenith_trading_result_v1", **seal, "selection": selection,
        "metrics": {name: {"mean_daily_net": mean_net(v), **v["summary"]} for name, v in scores.items()},
        "paired_updates": {arm: paired_interval(scores[arm]["daily"], scores["baseline"]["daily"]) for arm in ARMS},
        "repeat_variability": paired_interval(scores["baseline_repeat"]["daily"], scores["baseline"]["daily"], family=1),
        "shrinkage_lambda": shrink, "date_count": len(spec["selected_dates"]["test"]),
        "unchanged_aliases": {arm: "baseline" for arm in unchanged},
        "all_attempts": [read_json(p) for p in sorted((study / "candidates").glob("*.json"))],
        "claim": "Historical conditional forecast-skill comparison, not autonomous topology learning, a published benchmark reproduction or prospective trading evidence."}
    result = _seal_record(result)
    write_json(study / "result.json", result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["freeze", "development", "learn", "select", "final"])
    parser.add_argument("--study", type=Path, required=True)
    parser.add_argument("--dataset", type=Path, default=Path("work/datasets/stocknet"))
    parser.add_argument("--authorization", type=Path)
    parser.add_argument("--profile", choices=["stocknet", "finmultitime"], default="stocknet")
    parser.add_argument("--env-file", type=Path)
    args = parser.parse_args()
    if args.env_file:
        from dotenv import load_dotenv
        load_dotenv(args.env_file, override=False)
    if args.action == "freeze":
        if not args.authorization: parser.error("freeze requires --authorization")
        auth = read_json(args.authorization)
        result = freeze(args.dataset, args.study, budget=auth["budget"], authorization=auth, profile=args.profile)
    else:
        result = {"development": development, "learn": learn, "select": select, "final": final}[args.action](args.study)
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
