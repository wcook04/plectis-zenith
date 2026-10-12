"""Prepare mixed demonstration inputs locally; never fetch data or call a model."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path

from tools.calculator.calculator import run as calculate

REAL_LANES = ("stock", "etf", "polymarket")
REPLACED_LANES = ("macro", "news")


def write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def synthetic(lane: str, anchor: str, later: bool) -> dict:
    """Independent authored examples. No original macro values or news are read."""
    if lane == "macro":
        data = {"columns": ["ticker", "Proxy", "pct_change", "z_score"],
                "rows": [["SYNTH_RATE", "Fictional rates", 0.2 if later else 0.1, 0.4],
                         ["SYNTH_ACTIVITY", "Fictional activity", -0.3 if later else 0.2, -0.2]],
                "synthetic_fixture": True}
    elif lane == "news":
        data = {"items": [{"id": "synthetic-notice-2" if later else "synthetic-notice-1",
                           "text": ("Fictional example: Demo Harbour delays its invented project."
                                    if later else "Fictional example: Demo Harbour announces an invented project."),
                           "timestamp_iso": anchor, "source": "authored teaching fixture",
                           "synthetic_fixture": True}], "synthetic_fixture": True}
    else:
        raise ValueError("No synthetic replacement defined for this lane")
    return {"id": f"global_{lane}_feed", "status": "success",
            "metadata": {"status": "success", "as_of": anchor, "timestamp_iso": anchor,
                         "synthetic_fixture": True, "data_origin": "authored_synthetic",
                         "notice": "Invented independently; not an anonymised historical observation."},
            "data": data}


def prepare(root: Path, earlier: Path, later: Path, output: Path) -> dict:
    root, earlier, later, output = (Path(p).resolve() for p in (root, earlier, later, output))
    if output.exists():
        raise ValueError("Demo output must be a new directory; existing evidence is never overwritten")
    # Validate both sources before creating any output. Read only retained lanes.
    sources = []
    for source in (earlier, later):
        context = json.loads((source / "runtime_context.json").read_text())
        anchor = context.get("as_of") or context.get("time_anchor")
        clock = datetime.fromisoformat(str(anchor).replace("Z", "+00:00"))
        if clock.tzinfo is None:
            raise ValueError("Source snapshot needs a timezone-aware clock")
        payloads = {}
        for lane in REAL_LANES:
            raw = (source / "artifacts" / f"global_{lane}_feed.json").read_bytes()
            artifact = json.loads(raw)
            if artifact.get("status") != "success" or not isinstance(artifact.get("data"), dict):
                raise ValueError(f"Retained {lane} source must be a successful saved artifact")
            if artifact.get("metadata", {}).get("synthetic_fixture") or artifact["data"].get("synthetic_fixture"):
                raise ValueError(f"The mixed demo requires real {lane} input, not a replacement fixture")
            payloads[lane] = raw
        sources.append((anchor, clock, payloads))
    if sources[0][1] >= sources[1][1]:
        raise ValueError("Later snapshot must follow the earlier snapshot")
    receipt = {"schema": "zenith_mixed_demo_v1", "data_mode": "mixed",
               "notice": "This is not financial advice.", "snapshots": [],
               "model_calls": 0, "execution_status": "inputs_prepared",
               "claim_boundary": "Real inputs are retained; only macro and news are synthetic replacements. "
                                 "Preparation does not establish forecasting skill or permission to redistribute real payloads.",
               "clock_boundary": "Saved snapshot anchors and copied artifact clocks are retained. Underlying observation availability and model training leakage remain unverified."}
    fixtures = {"schema": "zenith_synthetic_replacements_v1", "snapshots": []}
    for index, (anchor, _, payloads) in enumerate(sources):
        name = "earlier" if index == 0 else "later"
        directory = output / name
        write(directory / "runtime_context.json", {"as_of": anchor, "time_anchor": anchor,
              "subject_group": "feeds", "data_mode": "mixed", "publication": "private_inputs"})
        lanes = []
        for lane, raw in payloads.items():
            destination = directory / "artifacts" / f"global_{lane}_feed.json"
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(raw)
            lanes.append({"node_id": f"global_{lane}_feed", "input_origin": "real_saved_input",
                          "source_sha256": sha(raw), "input_sha256": sha(raw),
                          "public_payload": "withheld_pending_permissions_review",
                          "permission_status": "not_cleared_by_this_receipt"})
        examples = {}
        for lane in REPLACED_LANES:
            value = synthetic(lane, anchor, bool(index))
            destination = directory / "artifacts" / f"global_{lane}_feed.json"
            write(destination, value)
            examples[value["id"]] = value
            lanes.append({"node_id": value["id"], "input_origin": "authored_synthetic",
                          "input_sha256": sha(destination.read_bytes()),
                          "public_payload": "included", "permission_status": "original_fixture"})
        config = json.loads((root / "codex/substrate/configs/calculator_default.json").read_text())
        config.get("data", config)["runtime"] = {"as_of": anchor, "run_id": name}
        derived = calculate(config, run_dir=directory)
        if derived.get("metadata", {}).get("status") != "success":
            raise ValueError("Calculator failed on the assembled mixed inputs")
        derived.update(id="global_calculator_feed", status="success")
        derived["metadata"].update(as_of=anchor, timestamp_iso=anchor, data_origin="derived_mixed_inputs",
                                   input_snapshot_time=anchor,
                                   notice="Recomputed from retained stock/ETF and synthetic macro; not the historical calculator payload.")
        destination = directory / "artifacts/global_calculator_feed.json"
        write(destination, derived)
        lanes.append({"node_id": "global_calculator_feed", "input_origin": "derived_mixed_inputs",
                      "input_sha256": sha(destination.read_bytes()),
                      "public_payload": "withheld_pending_upstream_permissions_review",
                      "dependencies": ["global_stock_feed", "global_etf_feed", "global_macro_feed"]})
        receipt["snapshots"].append({"id": name, "as_of": anchor, "lanes": lanes})
        fixtures["snapshots"].append({"id": name, "as_of": anchor, "artifacts": examples})
    # Public exports are explicit allowlists. No raw retained input, path, prompt or derived table.
    write(output / "public/provenance.json", receipt)
    write(output / "public/replacements.json", fixtures)
    return receipt
