"""A fully synthetic, offline teaching example over the real native Lab graph.

It authors its own feed snapshots, runs the actual engine through
``runtime.start`` / ``runtime.import_response`` and the original contract
validation, shows one deliberately invalid response being rejected and then
corrected, and reports the completion counts it actually observed. It makes no
network or model calls and reads no private inputs.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from . import runtime
from .providers import write_json

NOTICE = "This is not financial advice."
SYNTHETIC_LABEL = "Synthetic contract demonstration"
RUN_ID = "OFFLINE_EXAMPLE"
ANCHOR = "2026-03-04T14:30:00+00:00"
HORIZON = "2026-03-05T21:00:00+00:00"
INVALID_RESPONSE = "{}"


def _prepare_output(output: Path) -> None:
    """Refuse an existing nonempty directory; never overwrite prior evidence."""
    if output.exists():
        if not output.is_dir():
            raise ValueError("Demo output must be a directory")
        if any(output.iterdir()):
            raise ValueError("Demo output directory must be new or empty; existing evidence is never overwritten")
    else:
        output.mkdir(parents=True)


def _feed_artifact(node_id: str) -> dict:
    """Authored synthetic payloads; ids come from the native graph, not a fixed list."""
    if node_id in ("global_measurements_feed", "global_subsystems_feed"):
        target = "SIGNAL_A" if node_id == "global_measurements_feed" else "SUBSYSTEM_A"
        data = {"columns": ["target_id", "Value"], "rows": [[target, 100.0]],
                "evidence_dictionary": [{"ledger_id": "S_ABCD0001", "subject": "SIGNAL_A"}]}
    elif node_id == "global_environment_feed":
        data = {"columns": ["target_id", "Proxy", "pct_change", "z_score"],
                "rows": [["SYNTH_RATE", 4.0, 0.1, 0.2]]}
    else:
        data = {"items": [], "synthetic_fixture": True}
    return {"id": node_id, "status": "success",
            "metadata": {"status": "success", "as_of": ANCHOR, "timestamp_iso": ANCHOR,
                         "synthetic_fixture": True, "data_origin": "authored_synthetic",
                         "notice": NOTICE},
            "data": data}


def _author_feeds(root: Path, source: Path) -> list[str]:
    feed_ids = sorted(node.id for node in runtime.load_graph(root).values() if node.meta.get("is_feed"))
    if not feed_ids:
        raise RuntimeError("native graph exposes no feed nodes")
    for node_id in feed_ids:
        write_json(source / "artifacts" / f"{node_id}.json", _feed_artifact(node_id))
    return feed_ids


def _cp1() -> dict:
    return {"evidence_dictionary": [{"ref_id": "[1]", "ledger_id": "S_ABCD0001", "subject": "SIGNAL_A",
                                     "signal_summary": "Synthetic teaching anchor for SIGNAL_A."}],
            "epicentre_thesis": "[1] " + ("Synthetic teaching transmission persists unless the fictional "
                                          "SIGNAL_A value drops below its declared baseline. " * 20)}


def _cp2() -> dict:
    payload = _cp1()
    payload["predictions_t"] = [{"target_id": "SIGNAL_A", "direction": "UP", "unit": "dimensionless",
                                 "snapshot_value": 100.0, "target_value": 105.0,
                                 "snapshot_time": ANCHOR, "target_time_iso": HORIZON,
                                 "invalidation": "SIGNAL_A below 98 at horizon"}]
    payload["forecast_rationale"] = "[1] " + ("Synthetic teaching consequence uses the same baseline and an "
                                              "explicit horizon invalidation. " * 15)
    return payload


def _authored_response(node_id: str) -> str:
    """Authored captured responses that satisfy the native node contracts."""
    if node_id == "lab_decide":
        return json.dumps(_cp1())
    if node_id == "lab_director":
        return json.dumps(_cp2())
    if node_id == "lab_cross_corr_v1":
        return json.dumps({"swarms": [], "bifurcations": [], "orphans": [], "confidence_asymmetries": []})
    if node_id == "lab_cross_corr_v2":
        return json.dumps({"target_swarms": [], "directional_conflicts": [],
                           "solo_targets": [{"id": "synthetic_solo", "name": "Synthetic SIGNAL_A",
                                             "summary": "Fixture grounding only", "target_ids": ["SIGNAL_A"],
                                             "lanes": ["MEASUREMENTS"], "direction_consensus": "INCREASE"}],
                           "thesis_stress": [], "valid_prediction_targets": ["SIGNAL_A"]})
    return "Synthetic teaching response; contract plumbing only. " + NOTICE


def _import(root: Path, output: Path, packet: dict, text: str, name: str) -> dict:
    response_path = output / "handoff" / "authored" / name
    response_path.parent.mkdir(parents=True, exist_ok=True)
    response_path.write_text(text, encoding="utf-8")
    return runtime.import_response(root, packet_path=Path(packet["packet_path"]),
                                   response_path=response_path, model="synthetic-authored-example")


def _reject_once(root: Path, output: Path, packet: dict) -> Path:
    """Import a deliberately invalid response; the engine must refuse it.

    The rejected text is archived beside the run when the corrected response
    later replaces it, so return the archive directory for the caller to read.
    """
    outcome = _import(root, output, packet, INVALID_RESPONSE, "lab_decide.invalid.json")
    if outcome["import"]["engine_accepted"]:
        raise RuntimeError("deliberately invalid response was unexpectedly accepted")
    return runtime.runs_root(root) / RUN_ID / "handoff" / "rejected_responses" / packet["packet_id"]


def _relative(output: Path, path: Path) -> str:
    try:
        return str(path.relative_to(output))
    except ValueError:
        return str(path)


def run(root: Path, output: Path) -> dict:
    root, output = Path(root).resolve(), Path(output).resolve()
    _prepare_output(output)
    if not (root / "codex").is_dir():
        raise ValueError(f"native graph is unavailable under {root}")
    # A self-contained staging root keeps every generated byte inside the requested output.
    demo_root = output / "demo_root"
    shutil.copytree(root / "codex", demo_root / "codex")
    write_json(demo_root / "master_config.json",
               {"paths": {"runs_dir": "runs"}, "execution": {"max_workers": 4}})
    source = output / "inputs"
    write_json(source / "runtime_context.json",
               {"as_of": ANCHOR, "time_anchor": ANCHOR, "subject_group": "feeds",
                "data_mode": "synthetic_offline_example", "notice": NOTICE})
    feed_ids = _author_feeds(demo_root, source)

    result = runtime.start(demo_root, mission="lab", run_id=RUN_ID, feed_source=str(source),
                           horizon=HORIZON, time_anchor=ANCHOR)
    limit = result["scope_count"] * 3
    imported = rejected = corrected = 0
    rejected_paths: list[str] = []
    rejection_dir: Path | None = None
    while result["status"] == "awaiting_agent" and imported < limit:
        packet = result["pending"][0]
        node_id = packet["node_id"]
        if node_id == "lab_decide" and rejected == 0:
            rejection_dir = _reject_once(demo_root, output, packet)
            rejected, corrected = 1, 1
        outcome = _import(demo_root, output, packet, _authored_response(node_id), f"{node_id}.json")
        if not outcome["import"]["engine_accepted"]:
            raise RuntimeError(f"authored synthetic response for {node_id} was not accepted")
        result = outcome["run"]
        imported += 1
        if rejection_dir is not None and not rejected_paths:
            rejected_paths = [str(path.relative_to(output)) for path in sorted(rejection_dir.glob("*.json"))]
    if result["status"] != "completed":
        raise RuntimeError("offline example did not complete the native Lab graph")

    run_dir = runtime.runs_root(demo_root) / RUN_ID
    evidence = {
        "synthetic_inputs": _relative(output, source),
        "run_manifest": _relative(output, run_dir / "zenith_run.json"),
        "lab_decide_artifact": _relative(output, run_dir / "artifacts" / "lab_decide.json"),
        "lab_director_artifact": _relative(output, run_dir / "artifacts" / "lab_director.json"),
        "engine_validation_receipts": _relative(output, run_dir / "handoff" / "validation"),
        "rejected_responses": rejected_paths,
        "authored_responses": _relative(output, output / "handoff" / "authored"),
    }
    summary = {
        "schema": "zenith_offline_example_v1",
        "notice": NOTICE,
        "synthetic_contract_demonstration": SYNTHETIC_LABEL,
        "data_mode": "synthetic_offline_example",
        "network_calls": 0, "model_calls": 0, "private_inputs": False,
        "graph_node_count": len(runtime.load_graph(demo_root)),
        "lab_scope_count": result["scope_count"],
        "lab_completed_count": result["completed_count"],
        "feed_node_count": len(feed_ids),
        "authored_responses_imported": imported,
        "rejected_responses": rejected,
        "corrected_responses": corrected,
        "status": result["status"],
        "claim_boundary": "Synthetic contract demonstration: executing the native Lab graph and validating "
                          "authored responses does not establish forecasting accuracy or market usefulness.",
        "evidence_paths": evidence,
    }
    write_json(output / "summary.json", summary)
    _write_readme(output, summary)
    return {"ok": True, "status": result["status"], "notice": NOTICE,
            "synthetic_contract_demonstration": SYNTHETIC_LABEL,
            "graph_node_count": summary["graph_node_count"], "lab_scope_count": summary["lab_scope_count"],
            "lab_completed_count": summary["lab_completed_count"],
            "authored_responses_imported": imported, "rejected_responses": rejected,
            "corrected_responses": corrected, "summary_path": _relative(output, output / "summary.json"),
            "evidence_paths": evidence}


def _write_readme(output: Path, summary: dict) -> None:
    lines = [
        "# Offline teaching example",
        "",
        f"**{NOTICE}** {SYNTHETIC_LABEL}.",
        "",
        "This directory is entirely synthetic and was produced offline. It authors its own feed",
        "snapshots, runs the real native Lab graph through the original engine, validation and",
        "handoff contracts, and makes no network or model calls. It reads no private inputs.",
        "",
        f"- Native graph nodes: {summary['graph_node_count']}",
        f"- Lab scope completed: {summary['lab_completed_count']} / {summary['lab_scope_count']}",
        f"- Authored responses imported: {summary['authored_responses_imported']}",
        f"- Deliberately rejected responses retained: {summary['rejected_responses']}",
        "",
        "Completion here shows the graph and its contracts execute. It is not evidence of improved",
        "forecasting. See `summary.json` for the full evidence map.",
    ]
    (output / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
