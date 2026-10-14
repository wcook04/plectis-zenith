"""One native investigation, exact procedure trial, and measured-feedback decision.

prepare is offline; run uses the existing explicitly budgeted provider. Failed
attempts are terminal records, never resampled. No candidate is auto-adopted.
"""
from pathlib import Path
import argparse
import json
from zenith import runtime
from zenith.providers import digest, write_json
from zenith.market_data import sha256
from zenith.basket_panel import Panel, investigator_snapshot, InvestigationStore, SUMMARY_QUANTITIES
from zenith.investigator import read, subject_record
from zenith.investigator_contracts import PROFILE, REVIEW_CONTRACT, DEFAULT_PROCEDURE, MAX_TURNS
from system.lib.reasoning_policy import investigation_policy
from zenith.provider_policy import latest_model, require_model


def load(path):
    return json.loads(Path(path).read_text())


# Retained import path for older study owners. New callers use the custody owner.
from zenith.source_snapshot import archive_runtime


def prepare(data, study, model=None, cutoff="2025-02-02", max_cost_usd="0.25", *, provider_slug=None, smoke=False):
    model = model or latest_model()
    require_model(model)
    study = Path(study).resolve()
    if study.exists():
        raise ValueError("study exists; use a new identity rather than overwrite evidence")
    panel = Panel(data)
    i = panel.cutoff_index(cutoff)
    study.mkdir(parents=True)
    runtime_archive=archive_runtime(study)
    source = study/"input"
    investigator_snapshot(panel,cutoff,source)
    # A genuinely calculated earlier example, shared by every arm. No outcome is
    # read, and the model is not given the current case's preferred investigation.
    teacher_cutoff = str(panel.dates[i-126])
    teacher = InvestigationStore(investigator_snapshot(panel,teacher_cutoff,study/"teacher-input"))
    inspection = teacher.inspect("B01")
    comparison = teacher.compare("B01","positive_value_weight",1)
    example = {"author":"Type A engineering bootstrap, not autonomous discovery","cutoff":teacher_cutoff,
        "question":"Does the value-weighted participation representation warrant changing these reference forecasts?",
        "inspection":inspection,"comparison":comparison,
        "decision":"Retain the declared references. One exploratory feature comparison on eight shared origins does not establish a robust reason to replace them. This teaches a permissible conservative decision, not an optimal selection rule.",
        "commitment":teacher.commit(list(teacher.defaults.values()),[]),
        "boundary":"earlier cutoff, actual native tools, no revealed forecast outcome; choose current questions by their own value"}
    envelope = load(source/"artifacts/investigator_case.json")
    envelope["data"]["worked_example"] = example
    write_json(source/"artifacts/investigator_case.json",envelope)
    policy = investigation_policy(DEFAULT_PROCEDURE)
    write_json(study/"incumbent-policy.json",policy)
    protocol = {"schema":"zenith_investigator_study_v1","task_profile":PROFILE,"data":str(Path(data).resolve()),
        "root":str(runtime.DEFAULT_ROOT),"case":{"cutoff":cutoff,"target_date":str(panel.dates[i+5]),"source":str(source)},
        "model":model,"provider_slug":provider_slug,"smoke":smoke,"runtime_archive":runtime_archive,"max_cost_usd":str(max_cost_usd),"max_calls":MAX_TURNS+1 if smoke else 3*MAX_TURNS+2,"max_output_tokens":4096,"review_contract":REVIEW_CONTRACT,
        "implementation":runtime.implementation_hashes(),"runner_sha256":sha256(__file__),
        "input_hashes":runtime._source_hashes([source]),"incumbent_policy_sha256":policy["policy_sha256"],
        "schedule":["subject","review","unchanged_control","exact_candidate_if_proposed","feedback_review"],
        "replicates_per_condition":1,"automatic_retries":0,
        "numerical_comparator":"enumerate 21 legal summary/source contrasts plus three references; select by past validation only; 21 comparison allowance versus Lab maximum six, reported separately",
        "boundary":"exposed development integration episode; one pair cannot identify a stochastic treatment effect or establish transfer",
        "adoption":"none; next decision is recorded for evaluation, not installed"}
    protocol["sha256"] = digest(protocol)
    write_json(study/"protocol.json",protocol)
    return protocol


def score(commitment,outcome):
    if commitment["cutoff"] != outcome["cutoff"] or set(commitment["forecasts"]) != set(outcome["returns"]):
        raise ValueError("unmatched forecast/outcome targets")
    if not commitment.get("target_time") or commitment["target_time"][:10] != outcome["target_date"]:
        raise ValueError("unmatched forecast/outcome intervals")
    rows = {b:{"prediction":p,"realised":outcome["returns"][b],"squared_error":(p-outcome["returns"][b])**2}
            for b,p in commitment["forecasts"].items()}
    return {"rows":rows,"mse":sum(r["squared_error"] for r in rows.values())/len(rows)}


def action_sequence(directory):
    graph = load(Path(directory)/"execution_graph.json")["nodes"]
    rows = []
    for nid in graph:
        if nid.startswith("investigator_result_"):
            row = read(directory,nid)
            action = row["action"]
            # Local option IDs alone cannot distinguish different numerical recipes.
            signature = row["receipt"]["selections"] if action["kind"]=="commit" else action
            if action["kind"]=="commit":
                signature = {"kind":"commit","recipes":{b:s["recipe"] for b,s in signature.items()}}
            rows.append({"step":nid,"action":action,"signature":signature,"receipt_sha256":row["receipt_sha256"]})
    return rows


def measured_receipt(proposal, subject, control, candidate, outcome, candidate_failure=None):
    def arm(directory):
        if directory is None:
            return None
        final = read(directory,"investigator_final")
        return {"run_id":Path(directory).name,"commitment":final,"actions":action_sequence(directory),"score":score(final,outcome)}
    baseline, unchanged, changed = arm(subject), arm(control), arm(candidate)
    manifests = [load(Path(d)/"zenith_run.json") for d in (subject,control,candidate) if d is not None]
    invariant_fields = ("feed_source","time_anchor","horizon","task_profile","node_hashes","implementation_hashes","model","provider")
    matched = {field:all(m.get(field)==manifests[0].get(field) for m in manifests) for field in invariant_fields}
    if not all(matched.values()):
        raise ValueError("repair comparison changed frozen conditions: "+str(matched))
    def first_difference(a,b):
        if a is None or b is None:
            return None
        aa,bb = a["actions"],b["actions"]
        return next((i+1 for i in range(max(len(aa),len(bb))) if i>=len(aa) or i>=len(bb) or aa[i]["signature"]!=bb[i]["signature"]),None)
    expected = proposal["expected_effect"]
    def signature_position(arm):
        if arm is None or expected["action"]=="none":
            return None
        return next((i+1 for i,row in enumerate(arm["actions"]) if row["action"]["kind"]==expected["action"] and
            all(expected[k]=="none" or row["action"].get(k)==expected[k] for k in ("source","quantity"))),None)
    result = {"schema":"zenith_investigator_repair_receipt_v1","proposal":proposal,
        "subject":baseline,"unchanged_control":unchanged,"candidate":changed,"candidate_failure":candidate_failure,
        "first_action_difference_subject_control":first_difference(baseline,unchanged),
        "first_action_difference_control_candidate":first_difference(unchanged,changed),
        "expected_signature_positions":{"subject":signature_position(baseline),"control":signature_position(unchanged),"candidate":signature_position(changed)},
        "changed_forecasts":[] if changed is None or unchanged is None else [b for b,p in changed["commitment"]["forecasts"].items() if p!=unchanged["commitment"]["forecasts"][b]],
        "candidate_minus_control_mse":None if changed is None or unchanged is None else changed["score"]["mse"]-unchanged["score"]["mse"],
        "disposition":"staged_only_no_adoption" if changed else "no_completed_candidate",
        "semantic_effect":"unassessed by code; signature occurrence is not meaning, causal attribution or transfer",
        "invariants":{"matched_manifest_fields":matched,
            "all_targets":all(set(a["commitment"]["forecasts"])==set(outcome["returns"]) for a in (baseline,unchanged,changed) if a is not None),
            "whole_lab_replay":all(m.get("replay_receipt",{}).get("boundary")=="whole Lab from entry" for m in manifests[1:]),
            "candidate_completed":changed is not None},
        "interpretation":"development pair with one unchanged stochastic control; no claim of learning or held-out utility from this receipt alone"}
    result["sha256"] = digest(result)
    return result


def review_feed(destination, subject, incumbent, outcome, history):
    destination = Path(destination)
    record = subject_record(subject)
    case = next(iter(record["contexts"].values()))["inputs"]["case"]["data"]
    options = list(case["references"])
    for nid,row in record["outputs"].items():
        if nid.startswith("investigator_result_"):
            options.extend(row["receipt"].get("candidates",[]))
    audit = []
    for b,selection in record["commitment"]["selections"].items():
        ranked = sorted((o for o in options if o["target"]==b),key=lambda o:o["validation_mse"])
        chosen = next(o for o in ranked if o["candidate_id"]==selection["candidate_id"])
        audit.append({"target":b,"selected_id":chosen["candidate_id"],"selected_mse":chosen["validation_mse"],
            "default_id":case["default_selection"][b],"selected_matches_default":chosen["candidate_id"]==case["default_selection"][b],
            "lowest_available_validation_id":ranked[0]["candidate_id"],"selected_is_validation_minimum":chosen["validation_mse"]==ranked[0]["validation_mse"],
            "ordered_available_options":[{k:o[k] for k in ("candidate_id","validation_mse")} for o in ranked]})
    from zenith.investigator_contracts import MAX_COMPARISONS
    legal = {(source,quantity) for source in [*outcome["returns"],"ALL"] for quantity in SUMMARY_QUANTITIES}
    executed = [row["action"] for name,row in record["outputs"].items()
        if name.startswith("investigator_turn_") and row.get("action",{}).get("kind")=="compare"]
    tested = {(a["source"],a["quantity"]) for a in executed}
    capability = {"legal_recipe_count":len(legal),"executed_comparisons":len(executed),
        "distinct_tested_recipe_count":len(tested),"untried_recipe_count":len(legal-tested),
        "remaining_comparison_allowance":MAX_COMPARISONS-len(executed),
        "recipe_axes":{"source":[*outcome["returns"],"ALL"],"quantity":list(SUMMARY_QUANTITIES)},
        "meaning":"A recipe is a source AND summary pair. Testing each summary for one source does not exhaust all recipes. The final Lab slot is commit-only. Untested recipes need not be useful; this is a capability boundary, not a requirement to spend every call."}
    packet = {"schema":"zenith_investigator_review_feed_v2","active_phase":"feedback" if history else "initial_diagnosis",
        "repair_history":history,"history_sha256":digest(history),
        "decision_audit":{"rows":audit,"interpretation":"code-owned arithmetic, not a mandatory argmin policy. Departure from default is permitted and is not by itself a defect."},
        "capability_audit":capability,
        "incumbent_policy":incumbent,"baskets":list(outcome["returns"]),
        "later_outcome_evidence":{"outcome":outcome,"score":score(read(subject,"investigator_final"),outcome)},
        "subject":record,
        "history_boundary":"history explicitly supplied in this request; delivery is not proof of intelligent use"}
    if destination.exists():
        if read(destination,"investigator_review_feed") != packet:
            raise ValueError("immutable review feed mismatch")
    else:
        write_json(destination/"artifacts/investigator_review_feed.json",{"status":"success","data":packet})
        write_json(destination/"runtime_context.json",{"as_of":outcome["target_date"]+"T23:59:59+00:00"})
    return destination


def run(study,env_file):
    study = Path(study).resolve()
    p = load(study/"protocol.json")
    if digest({k:v for k,v in p.items() if k!="sha256"}) != p["sha256"]:
        raise ValueError("protocol identity drift")
    if p["implementation"] != runtime.implementation_hashes() or p["runner_sha256"] != sha256(__file__):
        raise ValueError("runtime/runner changed after freeze; preserve this experiment")
    case = p["case"]
    if p["input_hashes"] != runtime._source_hashes([Path(case["source"])]):
        raise ValueError("input drift")
    policy = load(study/"incumbent-policy.json")
    if policy["policy_sha256"] != p["incumbent_policy_sha256"]:
        raise ValueError("incumbent policy drift")
    from system.lib.openrouter_free_runtime import load_env_file
    load_env_file(Path(env_file))

    def execute(suffix,mission,source,policy_path=None,replay=None):
        name = study.name+"-"+suffix
        directory = runtime.runs_root(runtime.DEFAULT_ROOT)/name
        if (study/"failures"/(suffix+".json")).exists():
            raise RuntimeError("terminal native attempt: "+name)
        if directory.exists():
            runtime._check_frozen_graph(runtime.DEFAULT_ROOT,load(directory/"zenith_run.json"))
            status = runtime.status(runtime.DEFAULT_ROOT,name)
        else:
            try:
                status = runtime.start(runtime.DEFAULT_ROOT,mission=mission,run_id=name,task_profile=PROFILE,
                    provider="openrouter_budgeted",model=p["model"],provider_slug=p.get("provider_slug"),max_cost_usd=p["max_cost_usd"],
                    max_calls=p["max_calls"],max_output_tokens=p["max_output_tokens"],budget_dir=study/"budget",
                    feed_source=str(source),policy=str(policy_path) if policy_path else None,
                    time_anchor=(case["cutoff"] if mission=="lab" else case["target_date"])+"T23:59:59+00:00",
                    horizon=case["target_date"]+"T23:59:59+00:00" if mission=="lab" else None,
                    replay_from=str(replay) if replay else None,replay_node="investigator_entry" if replay else None)
            except (ValueError,RuntimeError,OSError) as exc:
                write_json(study/"failures"/(suffix+".json"),{"status":"failed_before_completion","error":str(exc),"run_id":name})
                raise RuntimeError("terminal native attempt: "+name) from exc
        print(json.dumps({"event":"native_run","run_id":name,"status":status["status"]}),flush=True)
        if status["status"] != "completed":
            write_json(study/"failures"/(suffix+".json"),status)
            raise RuntimeError("terminal native attempt: "+name)
        return directory

    subject = execute("subject","lab",case["source"],study/"incumbent-policy.json")
    # Only now does the coordinator ask the evaluator for the later outcome.
    outcome = Panel(p["data"]).outcome(case["cutoff"])
    write_json(study/"outcome.json",outcome)
    source = review_feed(study/"review-input",subject,policy,outcome,[])
    review = execute("review","refinement",source)
    proposal = read(review,"investigator_review")
    if p.get("smoke"):
        result = {"schema":"zenith_investigator_smoke_v1","subject":str(subject),"review":str(review),
            "review_output":proposal,"model":p["model"],"adopted":False,
            "scope":"One native Lab and review only; no learning or predictive improvement claim",
            "budget":load(study/"budget"/"budget.json") if (study/"budget"/"budget.json").exists() else None}
        write_json(study/"result.json",result)
        return result
    control = execute("control","lab",case["source"],study/"incumbent-policy.json",subject)
    candidate, failure = None, None
    if proposal["disposition"] in ("propose","revise"):
        candidate_policy = load(review/"candidate_policy.json")
        if candidate_policy["procedure"] != proposal["replacement_procedure"]:
            raise ValueError("proposal was not staged exactly")
        write_json(study/"candidate-policy.json",candidate_policy)
        try:
            candidate = execute("candidate","lab",case["source"],study/"candidate-policy.json",subject)
        except RuntimeError as exc:
            failure = {"error":str(exc),"status":load(study/"failures/candidate.json")}
    receipt = measured_receipt(proposal,subject,control,candidate,outcome,failure)
    write_json(study/"repair-receipt.json",receipt)
    source = review_feed(study/"feedback-input",subject,policy,outcome,[receipt])
    feedback = execute("feedback","refinement",source)
    context = load(feedback/"artifacts/context/investigator_review.json")
    supplied = context["inputs"]["investigator_review_feed"]["data"]["repair_history"]
    if supplied != [receipt] or json.dumps(receipt,separators=(",",":"),ensure_ascii=False) not in context["prompt"]:
        raise ValueError("measured feedback absent from exact next provider request")
    store = InvestigationStore(read(case["source"],"investigator_case"))
    default = store.commit(list(store.defaults.values()),[])
    default["target_time"] = case["target_date"]
    catalogue = []
    for quantity in SUMMARY_QUANTITIES:
        for source_id in store.baskets+["ALL"]:
            catalogue.extend(store.compare(source_id,quantity,len(catalogue)//6+1)["candidates"])
    available = [*store.options.values(),*catalogue]
    chosen = [min((c for c in available if c["target"]==b),key=lambda c:c["validation_mse"])["candidate_id"] for b in store.baskets]
    deterministic = store.commit(chosen,catalogue)
    deterministic["target_time"] = case["target_date"]
    write_json(study/"numerical-comparator.json",{"selection_rule":"minimum mature validation MSE, no outcome selection", "comparison_count":21,
        "llm_maximum_comparisons":6,"catalogue":available,"commitment":deterministic,"score":score(deterministic,outcome),
        "boundary":"larger deterministic search allowance; exposed development case, not a matched compute or held-out superiority claim"})
    summary = {"schema":"zenith_investigator_episode_v1","profile":PROFILE,"protocol_sha256":p["sha256"],
        "subject":str(subject),"review":str(review),"control":str(control),"candidate":str(candidate) if candidate else None,
        "feedback":str(feedback),"receipt_sha256":receipt["sha256"],"feedback_delivered_exactly":True,
        "proposal":proposal,"feedback_decision":read(feedback,"investigator_review"),
        "numerical_reference_score":score(default,outcome),"candidate_minus_control_mse":receipt["candidate_minus_control_mse"],
        "enumerated_numerical_score":score(deterministic,outcome),
        "learning_claim":"integration and recorded model behaviour only; semantic mechanism and transfer require further evidence",
        "adopted":False}
    write_json(study/"result.json",summary)
    return summary


def continue_review(previous, study, env_file, max_cost_usd="3"):
    """One explicitly versioned interface experiment over an archived episode.

    The old result stays authoritative. This tests a revised reviewer interface,
    not another Lab sample or an autonomous learned improvement.
    """
    previous, study = Path(previous).resolve(), Path(study).resolve()
    old = load(previous/"result.json")
    old_protocol = load(previous/"protocol.json")
    receipt = load(previous/"repair-receipt.json")
    if digest({k:v for k,v in receipt.items() if k!="sha256"}) != receipt["sha256"] or old["receipt_sha256"] != receipt["sha256"]:
        raise ValueError("previous measured receipt identity mismatch")
    if old["protocol_sha256"] != old_protocol["sha256"] or digest({k:v for k,v in old_protocol.items() if k!="sha256"}) != old_protocol["sha256"]:
        raise ValueError("previous protocol identity mismatch")
    if not old["feedback_delivered_exactly"]:
        raise ValueError("previous episode lacks completed measured-feedback delivery")
    subject = Path(old["subject"])
    if read(subject,"investigator_final") != receipt["subject"]["commitment"]:
        raise ValueError("previous subject commitment drift")
    policy, outcome = load(previous/"incumbent-policy.json"), load(previous/"outcome.json")
    source = review_feed(study/"review-input",subject,policy,outcome,[receipt])
    p = {"schema":"zenith_investigator_review_continuation_v1","review_contract":REVIEW_CONTRACT,
        "previous_study":str(previous),"previous_receipt_sha256":receipt["sha256"],
        "previous_result_file_sha256":sha256(previous/"result.json"),
        "implementation":runtime.implementation_hashes(),"runner_sha256":sha256(__file__),
        "input_hashes":runtime._source_hashes([source]),"model":old_protocol["model"],
        "max_calls":1,"max_output_tokens":4096,"max_cost_usd":str(max_cost_usd),
        "automatic_retries":0,"adoption":"none",
        "boundary":"Type A reviewer-interface correction on an exposed development episode; original evidence preserved, no learning or transfer claim"}
    p["sha256"] = digest(p)
    if (study/"protocol.json").exists():
        if load(study/"protocol.json") != p:
            raise ValueError("continuation identity drift")
    else:
        write_json(study/"protocol.json",p)
    if (study/"failure.json").exists():
        raise RuntimeError("terminal continuation attempt")
    if (study/"result.json").exists():
        return load(study/"result.json")
    name = study.name+"-feedback"
    directory = runtime.runs_root(runtime.DEFAULT_ROOT)/name
    from system.lib.openrouter_free_runtime import load_env_file
    load_env_file(Path(env_file))
    try:
        if directory.exists():
            runtime._check_frozen_graph(runtime.DEFAULT_ROOT,load(directory/"zenith_run.json"))
            status = runtime.status(runtime.DEFAULT_ROOT,name)
        else:
            status = runtime.start(runtime.DEFAULT_ROOT,mission="refinement",run_id=name,task_profile=PROFILE,
                provider="openrouter_budgeted",model=p["model"],max_cost_usd=p["max_cost_usd"],
                max_calls=1,max_output_tokens=4096,budget_dir=study/"budget",feed_source=str(source),
                time_anchor=outcome["target_date"]+"T23:59:59+00:00")
        if status["status"] != "completed":
            raise RuntimeError("incomplete continuation: "+str(status))
        context = load(directory/"artifacts/context/investigator_review.json")
        if context["inputs"]["investigator_review_feed"]["data"]["repair_history"] != [receipt] or json.dumps(receipt,separators=(",",":"),ensure_ascii=False) not in context["prompt"]:
            raise ValueError("measured feedback absent from continuation provider request")
        result = {"schema":"zenith_investigator_review_continuation_result_v1","protocol_sha256":p["sha256"],
            "run":str(directory),"previous_receipt_sha256":receipt["sha256"],"feedback_delivered_exactly":True,
            "decision":read(directory,"investigator_review"),"adopted":False,"boundary":p["boundary"]}
        write_json(study/"result.json",result)
        return result
    except (ValueError,RuntimeError,OSError) as exc:
        write_json(study/"failure.json",{"status":"terminal","run_id":name,"error":str(exc)})
        raise


def review_only(previous, study, env_file, *, model=None, provider_slug=None, max_cost_usd="0.08"):
    """Versioned review-interface intervention; never rerun the frozen Lab."""
    from system.lib.openrouter_free_runtime import load_env_file
    previous, study = Path(previous).resolve(), Path(study).resolve()
    if study.exists():
        raise ValueError("review-only study exists; failed and completed attempts are terminal")
    old = load(previous/"protocol.json")
    subject = runtime.runs_root(runtime.DEFAULT_ROOT)/(previous.name+"-subject")
    if runtime.status(runtime.DEFAULT_ROOT,subject.name)["status"]!="completed":
        raise ValueError("review-only requires a completed frozen Lab")
    model=model or latest_model();require_model(model)
    study.mkdir(parents=True)
    source=review_feed(study/"input",subject,load(previous/"incumbent-policy.json"),load(previous/"outcome.json"),[])
    protocol={"schema":"zenith_review_only_v1","previous_protocol_sha256":digest(old),"subject":str(subject),
        "input_hashes":runtime._source_hashes([source]),"implementation":runtime.implementation_hashes(),
        "runner_sha256":sha256(__file__),"model":model,"provider_slug":provider_slug,
        "max_cost_usd":str(max_cost_usd),"max_calls":1,"contract":REVIEW_CONTRACT,"runtime_archive":archive_runtime(study),
        "scope":"Review-interface intervention over a completed development Lab; no resampling of the failed attempt or learning claim"}
    write_json(study/"protocol.json",protocol)
    load_env_file(Path(env_file))
    status=runtime.start(runtime.DEFAULT_ROOT,mission="refinement",run_id=study.name,task_profile=PROFILE,
        provider="openrouter_budgeted",model=model,provider_slug=provider_slug,max_cost_usd=max_cost_usd,
        max_calls=1,max_output_tokens=4096,budget_dir=study/"budget",feed_source=str(source),
        time_anchor=old["case"]["target_date"]+"T23:59:59+00:00")
    result={"status":status,"adopted":False}
    if status["status"]=="completed":result["output"]=read(runtime.runs_root(runtime.DEFAULT_ROOT)/study.name,"investigator_review")
    write_json(study/"result.json",result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action",choices=("prepare","run","continue-review","review-only"))
    parser.add_argument("--study",type=Path,required=True)
    parser.add_argument("--data",type=Path)
    parser.add_argument("--model",help="Default: newest catalogue-verified cheap Chinese model")
    parser.add_argument("--provider-slug",help="Exact verified OpenRouter endpoint; unavailable routes fail without fallback")
    parser.add_argument("--smoke",action="store_true",help="Prepare only one Lab and one review, without a learning campaign")
    parser.add_argument("--cutoff",default="2025-02-02")
    parser.add_argument("--max-cost-usd",default="0.25")
    parser.add_argument("--env-file",type=Path)
    parser.add_argument("--previous",type=Path)
    args = parser.parse_args()
    if args.action=="prepare" and not args.data or args.action in ("run","continue-review","review-only") and not args.env_file or args.action in ("continue-review","review-only") and not args.previous:
        parser.error("prepare requires --data; run requires --env-file; continue-review requires --previous and --env-file")
    if args.action=="prepare":
        result = prepare(args.data,args.study,args.model,args.cutoff,args.max_cost_usd,provider_slug=args.provider_slug,smoke=args.smoke)
    elif args.action=="run":
        result = run(args.study,args.env_file)
    elif args.action=="review-only":
        result = review_only(args.previous,args.study,args.env_file,model=args.model,provider_slug=args.provider_slug,max_cost_usd=args.max_cost_usd)
    else:
        result = continue_review(args.previous,args.study,args.env_file,args.max_cost_usd)
    print(json.dumps(result,indent=2))


if __name__ == "__main__":
    main()
