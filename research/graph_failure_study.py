"""Run the full Lab -> Oracle -> Evolve loop and test one local repair.

All model calls use native runtime.start. Original failures and replay controls
remain separate records. Later comparison inputs are fixed before diagnosis.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import numpy as np

from zenith import runtime
from zenith.basket_panel import Panel
from zenith.providers import write_json, digest
from zenith.market_data import sha256
from zenith.market_graph import LANES, VIEWS, read_data
from system.lib.reasoning_policy import policy_sha256


def load(path): return json.loads(Path(path).read_text())


def prepare_feeds(panel, cutoff, destination):
    panel.snapshot(cutoff,destination)
    payload=read_data(destination,"basket_panel_feed")
    overview=payload["overview"]
    stocks=overview["stock_observations"]
    current=np.load(destination/"history.npz",allow_pickle=False)["current"]
    features=dict(zip((r["name"] for r in payload["feature_info"]),current.tolist()))
    views={
        "measurements":[{k:r[k] for k in ("symbol","basket","return1","return5","return20")} for r in stocks],
        "subsystems":[{"basket":b,**overview["basket_observations"][b],**{k:features[b+":"+k] for k in ("breadth5","dispersion5")}} for b in overview["basket_ids"]],
        "environment":[{"index":s,**{k:features[s+":"+k] for k in ("return1","return5","return20")}} for s in overview["index_inputs"]],
        "events":[{k:r[k] for k in ("symbol","basket","return5","relative_volume")} for r in stocks],
        "interventions":[{"basket":b,**{k:features[b+":"+k] for k in ("return1","return5","return20")}} for b in overview["basket_ids"]],
        "derived":[{k:r[k] for k in ("symbol","basket","quote_age","volatility20")} for r in stocks],
    }
    for lane in LANES:
        data={"view":VIEWS[lane],"cutoff":cutoff,"rows":views[lane],"baseline":overview["baseline"],
              "inventory":{"basket_ids":overview["basket_ids"],"constituents":overview["constituent_count"],
                  "feature_count":overview["feature_count"],"training_origins":overview["training_origins"]},
              "query_contract":overview["query_contract"],"universe_sha256":overview["universe_sha256"],
              "limitations":panel.manifest["qualifications"]}
        # All deterministic query operations can address the shared cutoff store.
        data["panel"]=payload
        write_json(destination/"artifacts"/("global_"+lane+"_feed.json"),
            {"status":"success","metadata":{"as_of":cutoff+"T23:59:59+00:00"},"data":data})


def prepare(data, study):
    study=Path(study).resolve()
    if study.exists(): raise ValueError("study exists; preserve its evidence")
    panel=Panel(data);study.mkdir(parents=True)
    dates=["2025-02-02","2025-05-04","2025-08-03"]
    cases=[]
    for desired in dates:
        cutoff=next(str(d) for d in panel.dates if d>=desired)
        i=panel.cutoff_index(cutoff)
        destination=study/"inputs"/cutoff
        prepare_feeds(panel,cutoff,destination)
        cases.append({"cutoff":cutoff,"target_date":str(panel.dates[i+5]),"source":str(destination)})
    plans={m:runtime.plan(runtime.DEFAULT_ROOT,m,task_profile="financial") for m in ("lab","oracle","refinement")}
    protocol={"schema":"zenith_full_graph_failure_study_v1","root":str(runtime.DEFAULT_ROOT),
        "data":str(Path(data).resolve()),"cases":cases,"model":"openai/gpt-4.1-mini",
        "max_cost_usd":"5","max_calls":240,"max_output_tokens":4096,
        "implementation":runtime.implementation_hashes(),"study_code_sha256":sha256(__file__),
        "input_hashes":runtime._source_hashes([Path(c["source"]) for c in cases]),"plans":plans,"universe":panel.manifest,
        "purpose":"Test trace-grounded failure decomposition, a feasible local repair, and later behavior; initial accuracy is not the completion criterion.",
        "repair_test":"Frozen unaffected artifacts; rerun intervention and descendants. Include an empty-instruction replay control for sampling variation.",
        "later_test":"One frozen repair versus incumbent on two predeclared later cutoffs; commit both before opening outcomes. No automatic adoption from this small diagnostic experiment."}
    protocol["sha256"]=digest(protocol)
    write_json(study/"protocol.json",protocol)
    return {"study":str(study),"nodes":{m:p["node_count"] for m,p in plans.items()}}


def run_native(study, protocol, mission, suffix, case, **kwargs):
    run_id=study.name+"-"+suffix
    directory=runtime.runs_root(runtime.DEFAULT_ROOT)/run_id
    if directory.exists():
        runtime._check_frozen_graph(runtime.DEFAULT_ROOT,load(directory/"zenith_run.json"))
        status=runtime.status(runtime.DEFAULT_ROOT,run_id)
    else:
        status=runtime.start(runtime.DEFAULT_ROOT,mission=mission,run_id=run_id,task_profile="financial",
            provider="openrouter_budgeted",model=protocol["model"],
            max_cost_usd=protocol["max_cost_usd"],max_calls=protocol["max_calls"],
            max_output_tokens=protocol["max_output_tokens"],budget_dir=study/"budget",
            time_anchor=case["cutoff"]+"T23:59:59+00:00",horizon=case["target_date"]+"T23:59:59+00:00",**kwargs)
    print(json.dumps({"event":"native_run","run_id":run_id,"mission":mission,"status":status["status"]}),flush=True)
    if status["status"]!="completed":
        write_json(study/"failed-runs"/(run_id+".json"),status)
        raise RuntimeError("native run incomplete; preserved for diagnosis: "+run_id)
    return directory


def score(directory, outcome):
    cp2=read_data(directory,"lab_director")
    return {"run_id":directory.name,"forecasts":cp2["forecasts"],"cp2_sha256":digest(cp2),
        "rows":{b:{"prediction":p,"realised":outcome["returns"][b],"squared_error":(p-outcome["returns"][b])**2}
            for b,p in cp2["forecasts"].items()},
        "mse":sum((p-outcome["returns"][b])**2 for b,p in cp2["forecasts"].items())/6}


def make_truth(panel,case,study):
    outcome=panel.outcome(case["cutoff"])
    dest=study/"truth"/case["cutoff"]
    if not dest.exists():
        # Later views are prepared only AFTER Lab commits. No labels enter Lab stores.
        prepare_feeds(panel,case["target_date"],dest)
        for lane in LANES:
            path=dest/"artifacts"/("global_"+lane+"_feed.json")
            env=load(path);env["data"].pop("panel",None);env["data"]["outcome"]=outcome
            write_json(path,env)
        write_json(dest/"runtime_context.json",{"as_of":case["target_date"]+"T23:59:59+00:00","subject_group":"oracle","oracle_mode":True})
    return dest,outcome


def run(study,env_file):
    study=Path(study).resolve();p=load(study/"protocol.json")
    if digest({k:v for k,v in p.items() if k!="sha256"})!=p["sha256"]: raise ValueError("protocol drift")
    if p["implementation"]!=runtime.implementation_hashes(): raise ValueError("implementation changed after preparation")
    if p["study_code_sha256"]!=sha256(__file__): raise ValueError("study code changed after preparation")
    if p["input_hashes"]!=runtime._source_hashes([Path(c["source"]) for c in p["cases"]]): raise ValueError("frozen input packet changed")
    from system.lib.openrouter_free_runtime import load_env_file
    load_env_file(Path(env_file))
    panel=Panel(p["data"]);case=p["cases"][0]
    subject=run_native(study,p,"lab","subject",case,feed_source=case["source"])
    truth,outcome=make_truth(panel,case,study)
    write_json(study/"original-score.json",score(subject,outcome))
    oracle=run_native(study,p,"oracle","oracle",case,subject_run=str(subject),truth_run=str(truth))
    evolve_input=study/"evolve-input"
    if not evolve_input.exists():
        packet={"subject_forecast":read_data(subject,"lab_director"),
            "numeric_errors":read_data(oracle,"oracle_truth_diff_observations"),
            "attribution":read_data(oracle,"oracle_attribution_map"),"critique":read_data(oracle,"oracle_explain"),
            "oracle_proposals":read_data(oracle,"oracle_cp2_emitter"),
            "subject_record":read_data(oracle,"oracle_subject_index")}
        write_json(evolve_input/"artifacts/financial_evolve_feed.json",{"data":packet})
        write_json(evolve_input/"runtime_context.json",{"as_of":case["target_date"]+"T23:59:59+00:00"})
    evolve_case={**case,"cutoff":case["target_date"],"target_date":p["cases"][1]["cutoff"]}
    evolve=run_native(study,p,"refinement","evolve",evolve_case,feed_source=str(evolve_input))
    policy=load(evolve/"candidate_policy.json")
    node=next(iter(policy["nodes"]))
    # Policy remains a candidate. Its text and exact provenance are exposed for review.
    write_json(study/"revision.json",policy)
    control={"variant_id":"empty-instruction-control","nodes":{node:{"skill_addon":""}}}
    control["policy_sha256"]=policy_sha256(control)
    write_json(study/"replay-control-policy.json",control)
    replay_scores={}
    for arm,policy_path in (("control",study/"replay-control-policy.json"),("repair",study/"revision.json")):
        replay=run_native(study,p,"lab","replay-"+arm,case,feed_source=case["source"],
            policy=str(policy_path),replay_from=str(subject),replay_node=node)
        replay_scores[arm]={**score(replay,outcome),"replay_receipt":load(replay/"replay_receipt.json")}
        replay_scores[arm]["changed_outputs"]=[n["id"] for n in p["plans"]["lab"]["nodes"]
            if digest(read_data(subject,n["id"]))!=digest(read_data(replay,n["id"]))]
    write_json(study/"replay-comparison.json",replay_scores)
    later=[]
    for case in p["cases"][1:]:
        arms={}
        for arm in ("incumbent","revised"):
            args={"policy":str(study/"revision.json")} if arm=="revised" else {}
            arms[arm]=run_native(study,p,"lab",case["cutoff"]+"-"+arm,case,feed_source=case["source"],**args)
        outcome=panel.outcome(case["cutoff"])
        later.append({"cutoff":case["cutoff"],"outcome":outcome,"arms":{a:score(d,outcome) for a,d in arms.items()}})
        write_json(study/"later-comparison.json",later)
    result={"schema":"zenith_full_graph_failure_result_v1","complete":True,"protocol_sha256":p["sha256"],
        "original":load(study/"original-score.json"),"oracle_run":oracle.name,"evolve_run":evolve.name,
        "repair":read_data(evolve,"dossier_updater"),"replay":replay_scores,"later":later,
        "adoption":"candidate_only; local replay is outcome-informed and two later cases are diagnostic, not general validation",
        "nodes":{m:plan["node_count"] for m,plan in p["plans"].items()}}
    write_json(study/"result.json",result)
    return result


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("action",choices=("prepare","run"));parser.add_argument("--study",type=Path,required=True)
    parser.add_argument("--data",type=Path);parser.add_argument("--env-file",type=Path)
    args=parser.parse_args()
    result=prepare(args.data,args.study) if args.action=="prepare" else run(args.study,args.env_file)
    print(json.dumps(result,indent=2))


if __name__=="__main__": main()
