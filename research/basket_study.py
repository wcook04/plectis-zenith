"""A bounded basket comparison, using native engine runs and provider budgets.

Usage: python -m research.basket_study prepare|run|report ...
Outcomes are opened by the evaluator only after all arms commit at a cutoff.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import shutil
from decimal import Decimal
from pathlib import Path

from zenith import runtime
from zenith.basket_panel import Panel
from zenith.providers import digest, write_json
from zenith.daily import substrate_hashes
from zenith.market_data import sha256
from system.lib.reasoning_policy import policy_sha256


def load(path): return json.loads(Path(path).read_text())


def prepare(data, study, model="inclusionai/ling-3.0-flash", max_cost_usd="2", max_calls=260):
    study = Path(study).resolve()
    if study.exists(): raise ValueError("study exists; frozen studies are not overwritten")
    panel = Panel(data)
    desired = {"development": ["2023-02-01", "2023-05-01", "2023-08-01", "2023-11-01"],
               "holdout": ["2024-02-01", "2024-04-01", "2024-06-01", "2024-08-01", "2024-10-01", "2024-12-01"]}
    cases = []
    study.mkdir(parents=True)
    for split, dates in desired.items():
        for desired_date in dates:
            cutoff = next(str(d) for d in panel.dates if d >= desired_date)
            i = panel.cutoff_index(cutoff)
            arms = ["directed", "undirected"] if split == "development" else ["directed", "undirected", "revised", "serial"]
            case = {"cutoff": cutoff, "target_date": str(panel.dates[i+5]), "split": split, "arms": arms}
            for arm in arms:
                snapshot = study / "inputs" / cutoff / arm
                overview = panel.snapshot(cutoff, snapshot, mode="undirected" if arm == "undirected" else "directed")
                case[arm] = str(snapshot)
            case["baseline"] = overview["baseline"]
            cases.append(case)
    protocol = {"schema": "zenith_native_basket_study_v1", "model": model, "data": str(Path(data).resolve()),
                "max_cost_usd": max_cost_usd, "max_calls": max_calls, "max_output_tokens": 1024,
                "cases": cases, "basket_manifest": panel.manifest, "root": str(runtime.DEFAULT_ROOT),
                "native_graph_sha256": digest({k: v for k, v in runtime.implementation_hashes().items()}),
                "substrate_sha256": digest(substrate_hashes(runtime.DEFAULT_ROOT)), "study_code_sha256": sha256(__file__),
                "score": "mean squared fractional five-session basket return error, equal basket and cutoff weight",
                "failure_policy": "retain the entire baseline forecast on a failed native run; include the case and report failures",
                "retention_policy": "strictly lower aggregate held-out MSE and no increase in worst per-cutoff universe MSE; otherwise retain incumbent",
                "limit": "small retrospective smoke experiment, not evidence of general financial skill or statistical superiority",
                "budget": "one immutable shared dollar/call cap, six queries per arm, identical base model; serial receives all first-pass numerical rows and may use the same query catalogue",
                "data_qualifications": panel.manifest["qualifications"], "import_audit": load(Path(data)/"audit.json")}
    protocol["sha256"] = digest(protocol)
    write_json(study / "protocol.json", protocol)
    shutil.copyfile(Path(data)/"SOURCE_LICENSE.txt", study/"SOURCE_LICENSE.txt")
    return {"study": str(study), "cases": len(cases), "constituents": len(panel.symbols), "baskets": len(panel.groups), "model": model}


def verify_protocol(study):
    p = load(study / "protocol.json")
    if p["sha256"] != digest({k: v for k, v in p.items() if k != "sha256"}): raise ValueError("protocol changed")
    if p["native_graph_sha256"] != digest(runtime.implementation_hashes()): raise ValueError("implementation changed after study preparation")
    if p["substrate_sha256"] != digest(substrate_hashes(Path(p["root"]))) or p["study_code_sha256"] != sha256(__file__): raise ValueError("study graph or evaluation code changed")
    return p


def run_arm(study, protocol, case, arm):
    label = study.name.replace("_", "-")
    run_id = f"{label}-{case['cutoff']}-{arm}"
    directory = runtime.runs_root(Path(protocol["root"])) / run_id
    mission = "basket_serial" if arm == "serial" else "basket"
    args = {"root": Path(protocol["root"]), "mission": mission, "run_id": run_id,
            "provider": "openrouter_budgeted", "model": protocol["model"], "feed_source": case[arm],
            "time_anchor": case["cutoff"]+"T23:59:59+00:00", "horizon": case["target_date"]+"T23:59:59+00:00",
            "max_cost_usd": protocol["max_cost_usd"], "max_calls": protocol["max_calls"],
            "max_output_tokens": protocol["max_output_tokens"], "budget_dir": study / "budget"}
    if arm == "revised": args["policy"] = str(study/"revision.json")
    result_file = study/"commitments"/case["cutoff"]/(arm+".json")
    if result_file.exists(): return load(result_file)
    status = runtime.status(Path(protocol["root"]), run_id) if directory.exists() else runtime.start(**args)
    final_node = runtime.MISSION_TARGETS[mission]
    if status["status"] == "completed":
        cp2 = load(directory/"artifacts"/(final_node+".json"))["data"]
        forecasts = cp2["forecasts"]
    else:
        cp2 = None
        forecasts = case["baseline"]
    record = {"run_id": run_id, "cutoff": case["cutoff"], "arm": arm, "status": status["status"],
              "forecasts": forecasts, "cp2": cp2, "native_run": str(directory), "native_status": status}
    record["sha256"] = digest(record)
    write_json(result_file, record)
    print(json.dumps({"event": "forecast_committed", "run": run_id, "status": status["status"]}), flush=True)
    return record


def score_case(study, protocol, case, panel):
    records = {a: load(study/"commitments"/case["cutoff"]/(a+".json")) for a in case["arms"]}
    for record in records.values():
        if record["sha256"] != digest({k:v for k,v in record.items() if k != "sha256"}): raise ValueError("forecast commitment changed")
    # First evaluator access to these outcomes comes after every arm has a saved commitment.
    truth = panel.outcome(case["cutoff"])
    forecasts = {a:r["forecasts"] for a,r in records.items()}
    forecasts.update(numerical=case["baseline"], zero={b:0. for b in case["baseline"]})
    errors = {}
    for arm, predicted in forecasts.items():
        if set(predicted) != set(truth["returns"]): raise ValueError("incomplete target universe")
        errors[arm] = {b:(truth["returns"][b]-predicted[b])**2 for b in predicted}
    result = {"cutoff": case["cutoff"], "split": case["split"], "truth": truth,
              "commitment_hashes": {a:r["sha256"] for a,r in records.items()},
              "per_target_squared_error": errors, "mse": {a:sum(v.values())/len(v) for a,v in errors.items()}}
    write_json(study/"scores"/(case["cutoff"]+".json"), result)
    return result


def propose_revision(study, protocol):
    destination = study/"revision.json"
    if destination.exists(): return load(destination)
    evidence = []
    for case in protocol["cases"]:
        if case["split"] != "development": continue
        score = load(study/"scores"/(case["cutoff"]+".json"))
        record = load(study/"commitments"/case["cutoff"]/"directed.json")
        directory = Path(record["native_run"])
        traces = {}
        for name in ("basket_plan", "basket_investigations", "basket_final"):
            path = directory/"artifacts"/(name+".json")
            if path.exists(): traces[name] = load(path).get("data")
        evidence.append({"score": score, "traces": traces})
    source = study/"evolve-input"
    last = max(c["target_date"] for c in protocol["cases"] if c["split"] == "development")
    asof = last+"T23:59:59+00:00"
    if not source.exists():
        write_json(source/"artifacts/basket_review_feed.json", {"status":"success", "metadata":{"as_of":asof}, "data":{"development_only":True,"cases":evidence}})
        write_json(source/"runtime_context.json", {"as_of":asof})
    run_id = study.name+"-evolve"
    root = Path(protocol["root"])
    directory = runtime.runs_root(root)/run_id
    result = runtime.status(root,run_id) if directory.exists() else runtime.start(root,mission="basket_evolve",run_id=run_id,
        feed_source=str(source),provider="openrouter_budgeted",model=protocol["model"],time_anchor=asof,horizon=min(c["cutoff"] for c in protocol["cases"] if c["split"]=="holdout")+"T23:59:59+00:00",
        max_cost_usd=protocol["max_cost_usd"],max_calls=protocol["max_calls"],max_output_tokens=protocol["max_output_tokens"],budget_dir=study/"budget")
    if result["status"] != "completed": raise RuntimeError("Evolve did not complete; no revision fabricated")
    proposal = load(directory/"artifacts/basket_evolve.json")["data"]
    addon = proposal.get("skill_addon") if isinstance(proposal,dict) else None
    if not isinstance(addon,str) or len(addon)>512: raise ValueError("Evolve instruction exceeds the registered contract")
    policy = {"variant_id":"basket-development-revision-v1", "nodes":{"basket_plan":{"skill_addon":addon}}}
    policy["policy_sha256"] = policy_sha256(policy)
    from system.lib.reasoning_policy import validate_reasoning_policy
    validate_reasoning_policy(policy,runtime.load_graph(root))
    write_json(study/"revision-proposal.json",proposal)
    write_json(destination,policy)
    print(json.dumps({"event":"revision_frozen","policy_sha256":policy["policy_sha256"]}),flush=True)
    return policy


def report(study):
    p=load(study/"protocol.json")
    rows=[load(path) for path in sorted((study/"scores").glob("*.json"))]
    summaries={}
    for split in ("development","holdout"):
        cases=[r for r in rows if r["split"]==split]
        if not cases:continue
        arms=set.intersection(*(set(r["mse"]) for r in cases))
        summaries[split]={"origins":len(cases),"basket_predictions_per_arm":len(cases)*len(p["basket_manifest"]["groups"]),
            "mean_mse":{a:sum(r["mse"][a] for r in cases)/len(cases) for a in sorted(arms)},
            "worst_origin_mse":{a:max(r["mse"][a] for r in cases) for a in sorted(arms)}}
    hold=summaries.get("holdout")
    complete=len(rows)==len(p["cases"])
    commits=[load(f) for f in (study/"commitments").glob("*/*.json")]
    failures=[r for r in commits if r["status"]!="completed"]
    retained=bool(complete and not failures and hold and hold["mean_mse"]["revised"]<hold["mean_mse"]["directed"] and hold["worst_origin_mse"]["revised"]<=hold["worst_origin_mse"]["directed"])
    budget=load(study/"budget/budget.json") if (study/"budget/budget.json").exists() else {}
    costs = {}
    for entry in budget.get("entries", {}).values():
        arm = entry["run_id"].rsplit("-", 1)[-1]
        row = costs.setdefault(arm, {"calls":0,"reported_cost_usd":"0","unknown_cost_calls":0,"input_tokens":0,"output_tokens":0})
        row["calls"] += 1
        if entry.get("cost") is None: row["unknown_cost_calls"] += 1
        else: row["reported_cost_usd"] = str(Decimal(row["reported_cost_usd"])+Decimal(entry["cost"]))
        usage = entry.get("provider_receipt", {}).get("usage", {})
        row["input_tokens"] += usage.get("prompt_tokens", 0)
        row["output_tokens"] += usage.get("completion_tokens", 0)
    query_counts = {a:sum(r["cp2"]["query_count"] for r in commits if r["arm"]==a and r.get("cp2")) for a in {r["arm"] for r in commits}}
    answer={"schema":"zenith_basket_result_v1","complete":complete,"protocol_sha256":p["sha256"],"summary":summaries,
            "revision_retained":retained,"decision":"retain_revision" if retained else "retain_incumbent" if complete else "incomplete",
            "model":p["model"],"model_calls":len(budget.get("entries",{})),"cost_usd":budget.get("total_reported_cost_usd","0"),
            "cost_by_role":costs,"executed_queries":query_counts,
            "unknown_cost_calls":sum(v["unknown_cost_calls"] for v in costs.values()),
            "failed_arms":[{"run_id":r["run_id"],"status":r["status"]} for r in commits if r["status"]!="completed"],
            "claim_boundary":p["limit"],"data_qualifications":p["data_qualifications"],
            "source_commit":p["basket_manifest"]["source_commit"],"constituents":sum(map(len,p["basket_manifest"]["groups"].values()))}
    write_json(study/"result.json",answer)
    return answer


def run_study(study, env_file):
    study=Path(study).resolve();p=verify_protocol(study)
    from system.lib.openrouter_free_runtime import load_env_file
    load_env_file(Path(env_file))
    panel=Panel(p["data"])
    if panel.manifest!=p["basket_manifest"]:raise ValueError("basket formation changed")
    for split in ("development","holdout"):
        if split=="holdout":propose_revision(study,p)
        for case in p["cases"]:
            if case["split"]!=split:continue
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
                list(pool.map(lambda arm:run_arm(study,p,case,arm),case["arms"]))
            if load(study/"budget/budget.json").get("halted"):
                raise RuntimeError("shared provider budget halted; preserve attempts and stop the study")
            score_case(study,p,case,panel)
            report(study)
    return report(study)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command",choices=["prepare","run","report"])
    parser.add_argument("--study",type=Path,required=True)
    parser.add_argument("--data",type=Path)
    parser.add_argument("--env-file",type=Path)
    parser.add_argument("--model",default="inclusionai/ling-3.0-flash")
    args=parser.parse_args()
    if args.command=="prepare":result=prepare(args.data,args.study,args.model)
    elif args.command=="run":result=run_study(args.study,args.env_file)
    else:result=report(args.study)
    print(json.dumps(result,indent=2))


if __name__=="__main__":main()
