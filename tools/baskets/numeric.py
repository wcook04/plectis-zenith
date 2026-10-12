"""Deterministic tools executed by the existing GodModeEngine."""
import json
from pathlib import Path
from zenith.basket_panel import investigate
from zenith.providers import digest


def artifact(run_dir, name):
    return json.loads((Path(run_dir)/"artifacts"/(name+".json")).read_text())["data"]


def run(config, run_dir=None, **kwargs):
    operation = config["operation"]
    panel = artifact(run_dir, "basket_panel_feed")
    overview = panel["overview"]
    if operation == "serial_inventory":
        data = overview
    elif operation == "inventory":
        data = {k: v for k, v in overview.items() if k != "stock_observations"}
    elif operation == "slice":
        group = overview["basket_ids"][config["slice"]]
        data = {"cutoff": panel["cutoff"], "group": group, "observations": [r for r in overview["stock_observations"] if r["basket"] == group],
                "query_contract": overview["query_contract"], "baseline": overview["baseline"], "universe_sha256": overview["universe_sha256"]}
    elif operation == "investigate":
        plan = artifact(run_dir, config.get("plan_node", "basket_plan"))
        if not isinstance(plan, dict) or not isinstance(plan.get("queries"), list):
            raise ValueError("CP1 requires a bounded queries array")
        queries = plan["queries"]
        if panel["mode"] == "undirected":
            queries = [{"target": b, "source": b, "operation": "trend", "lag": 0,
                        "reason": "Predeclared undirected own-basket trend inspection"} for b in overview["basket_ids"]]
        results = investigate(panel, queries)
        data = {"cutoff": panel["cutoff"], "baseline": overview["baseline"], "candidates": results,
                "cp1_sha256": digest(plan), "executed_queries": queries, "query_count": len(queries),
                "mode": panel["mode"], "forecast_basis": "EMPIRICAL", "note": "Validation gains are training-history diagnostics, not held-out performance."}
    elif operation == "final":
        choices = artifact(run_dir, config.get("director_node", "basket_director"))
        investigation = artifact(run_dir, config.get("investigation_node", "basket_investigations"))
        approved = choices.get("selected_candidates") if isinstance(choices, dict) else None
        if not isinstance(approved, list) or any(not isinstance(c, str) for c in approved):
            raise ValueError("CP2 requires an explicit selected_candidates array")
        candidates = {r["candidate_id"]: r for r in investigation["candidates"]}
        forecasts = dict(overview["baseline"])
        selected = {b: "baseline" for b in overview["basket_ids"]}
        assigned = set()
        for choice in approved:
            if choice not in candidates:
                raise ValueError("unknown candidate selection")
            target = candidates[choice]["query"]["target"]
            if target in assigned:
                raise ValueError("multiple candidates for the same target")
            assigned.add(target)
            selected[target] = choice
            forecasts[target] = candidates[choice]["prediction"]
        data = {"schema": "zenith_basket_cp2_v1", "cutoff": panel["cutoff"], "horizon_sessions": 5,
                "universe_sha256": overview["universe_sha256"], "forecast_basis": "EMPIRICAL",
                "forecasts": forecasts, "provisional_forecasts": overview["baseline"], "selections": selected,
                "cp1_sha256": investigation["cp1_sha256"], "investigation_sha256": digest(investigation),
                "changes": {b: forecasts[b]-overview["baseline"][b] for b in forecasts}, "query_count": investigation["query_count"]}
    else:
        raise ValueError("unknown basket operation")
    return {"metadata": {"status": "success", "as_of": panel["cutoff"]+"T23:59:59+00:00"}, "data": data}
