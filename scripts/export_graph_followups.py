"""Publish completed, separately identified repair checks without rewriting them."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.export_graph_study import scrub
from zenith import runtime
from zenith.market_graph import read_data
from zenith.providers import digest, write_json


def load(path):
    return json.loads(path.read_text())


def protocol(study):
    value = load(study / "protocol.json")
    if digest({k: v for k, v in value.items() if k != "sha256"}) != value["sha256"]:
        raise ValueError(f"Changed protocol: {study.name}")
    return value


def accounting(study):
    value = load(study / "budget/budget.json")
    entries = list(value["entries"].values())
    return {"attempted_calls": len(entries),
            "reported_cost_usd": value["total_reported_cost_usd"],
            "repeated_node_attempts": len(entries) - len({(e["run_id"], e["node_id"]) for e in entries})}


def selection_audit(run):
    context = load(run / "artifacts/context/lab_director.json")
    numerical = context["inputs"]["lab_cross_corr_v2"]["data"]["numerical_candidates"]
    record = read_data(run, "lab_director")
    selected = set(record["result"]["selected_candidates"])
    rows = [{"candidate_id": c["candidate_id"], "target": c["query"]["target"],
             "validation_gain": c["validation_gain"], "validation_cases": c["validation_cases"],
             "selected": c["candidate_id"] in selected} for c in numerical["candidates"]]
    return {"source": "saved Director input: lab_cross_corr_v2/numerical_candidates",
            "numerical_receipt_sha256": digest(numerical), "rows": rows,
            "selected_nonpositive_gain_ids": [c["candidate_id"] for c in rows
                                               if c["selected"] and c["validation_gain"] <= 0],
            "boundary": "Descriptive compliance check for the reviewed instruction; it does not establish that rejecting these candidates improves forecasts."}


def export(root, work, destination):
    runs = runtime.runs_root(root)
    studies = {}
    for name, result_file in (("zenith-evolve-context-20261013", "result.json"),
                              ("zenith-phase-context-20261013", "evolve-result.json"),
                              ("zenith-reviewed-repair-20261013", "result.json")):
        study = work / name
        frozen = protocol(study)
        result = load(study / result_file)
        if result["protocol_sha256"] != frozen["sha256"]:
            raise ValueError(f"Unbound result: {name}")
        if result_file == "result.json" and not result.get("complete"):
            raise ValueError(f"Uncollected study: {name}")
        projected = {k: v for k, v in frozen.items() if k != "input_hashes"}
        if "input_hashes" in frozen:
            projected["input_content_hashes"] = list(frozen["input_hashes"].values())
        public = {"study_id": name, "protocol": scrub(projected), "result": scrub(result),
                  "revision": load(study / "revision.json"), "accounting": accounting(study),
                  "protocol_note": "Original SHA binds the local full protocol. Paths in this public projection are redacted; its own hash is in manifest.json."}
        if name == "zenith-evolve-context-20261013":
            public["author_annotation"] = "The updater clarification was authored by the engineering assistant. The frozen protocol's term 'human-authored' is inaccurate; it was not written by Will or the experimental Evolve model."
            public["evolve_records"] = {n: read_data(runs / result["evolve_run"], n)
                                        for n in ("delta_analyzer", "dossier_updater", "version_committer")}
        elif name == "zenith-phase-context-20261013":
            public["disposition"] = "The v4 system-message context check again produced freeze_selected_candidates. It was not replayed or adopted."
        else:
            public["author_annotation"] = "Reviewer-authored instruction from the engineering assistant, not autonomous experimental Evolve output."
            public["replay_records"] = {}
            for arm, score in result["arms"].items():
                run = runs / score["run_id"]
                public["replay_records"][arm] = {
                    "selection_audit": selection_audit(run),
                    "nodes": {n: read_data(run, n) for n in score["replay_receipt"]["rerun_nodes"]}}
        studies[name] = public
    write_json(destination / "followups.json", {
        "schema": "zenith_repair_followups_v1", "studies": studies,
        "boundary": "Explicitly versioned engineering checks. No automatic retries, adopted policies or demonstrated autonomous repair gain. Collection can include failed arms."})
    manifest = load(destination / "manifest.json")
    manifest["files"] = {p.name: digest(load(p)) for p in sorted(destination.glob("*.json"))
                         if p.name != "manifest.json"}
    manifest["schema_versions"] = {"experiment": "zenith.reasoning.v3", "current": "zenith.reasoning.v4"}
    write_json(destination / "manifest.json", manifest)
    print(json.dumps({"exported": str(destination / "followups.json"), "studies": list(studies)}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=runtime.DEFAULT_ROOT)
    args = parser.parse_args()
    root = args.root.resolve()
    export(root, root / "work", root / "examples/full-graph")
