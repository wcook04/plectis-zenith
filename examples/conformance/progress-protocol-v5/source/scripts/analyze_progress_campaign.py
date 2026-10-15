#!/usr/bin/env python3
"""Descriptive, source-bound analysis of a frozen native conformance campaign.

Reads the existing frozen/panel/billing JSON contract. It makes no model calls,
does not regenerate panels, and never treats panel rows as independent tasks.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path


def read(path: Path):
    return json.loads(path.read_text())


def digest(value) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"),
                     ensure_ascii=False, allow_nan=False).encode()
    return hashlib.sha256(raw).hexdigest()


def amount(value) -> Decimal:
    if value is None or isinstance(value, bool):
        raise ValueError("Unknown or invalid charge")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("Invalid charge") from exc
    if not result.is_finite() or result < 0:
        raise ValueError("Invalid charge")
    return result


def family(source_id: str) -> str:
    return source_id.split("-", 1)[0]


def check_score(score: dict) -> dict:
    rows = score["rows"]
    if not isinstance(rows, list) or not rows:
        raise ValueError("Panel score has no answer rows")
    actual = {"correct": sum(row["correct"] is True for row in rows),
              "total": len(rows),
              "errors": sum(row["error"] is not None for row in rows)}
    if any(type(row["correct"]) is not bool for row in rows) or any(
        score.get(key) != value for key, value in actual.items()
    ):
        raise ValueError("Panel aggregate disagrees with answer rows")
    return actual


def paired_obligations(score: dict) -> list[str]:
    return [digest({"input": row["input"], "expected": row["expected"]})
            for row in score["rows"]]


def classify(receipts: list) -> dict:
    counts = dict(slots=len(receipts), valid=0, duplicate=0, invalid=0,
                  policy_error=0, stop=0, semantic_defect=0, technical_defect=0)
    for row in receipts:
        if "policy_error" in row:
            counts["policy_error"] += 1
        elif row.get("stopped") is True:
            counts["stop"] += 1
        elif "query_error" in row:
            key = "duplicate" if str(row["query_error"]).startswith("Duplicate") else "invalid"
            counts[key] += 1
        elif "expected" in row:
            counts["valid"] += 1
            if row.get("verified_counterexample") is True:
                key = "technical_defect" if row.get("parent_error") is not None else "semantic_defect"
                counts[key] += 1
        else:
            raise ValueError("Unclassified investigation receipt")
    return counts


def ledger(folder: Path, task_ids: set[str], arms: set[str]) -> dict:
    path = folder / "billing.json"
    if not path.exists():
        path = folder / "budget" / "budget.json"
    if not path.exists():
        return {"available": False, "reason": "No settled billing ledger"}
    data = read(path)
    entries = data["entries"]
    if isinstance(entries, dict):
        entries = list(entries.values())
    if not isinstance(entries, list):
        raise ValueError("Billing entries must be a list or mapping")
    task_order = sorted(task_ids, key=len, reverse=True)
    buckets = defaultdict(lambda: {"calls": 0, "known_cost_usd": Decimal(0),
                                  "unknown_cost_calls": 0, "prompt_tokens": 0,
                                  "completion_tokens": 0, "reasoning_tokens": 0,
                                  "cached_prompt_tokens": 0,
                                  "unknown_usage_calls": 0,
                                  "unknown_reasoning_token_calls": 0,
                                  "unknown_cached_token_calls": 0})
    seen = set()
    for entry in entries:
        node = entry["node_id"]
        if node in seen:
            raise ValueError("Duplicate billing node")
        seen.add(node)
        task_id = next((t for t in task_order if node.startswith(t + "-")), None)
        if task_id is None:
            raise ValueError("Billing node outside frozen tasks")
        suffix = node[len(task_id) + 1:]
        role = ("parent" if suffix == "parent" else
                "shared_direct" if suffix == "direct-shared-turn-1" else next(
                    (a for a in sorted(arms, key=len, reverse=True)
                     if suffix.startswith(a + "-")), None))
        if role is None:
            raise ValueError("Billing node outside frozen arms")
        bucket = buckets[(task_id, role)]
        bucket["calls"] += 1
        if entry.get("cost") is None:
            bucket["unknown_cost_calls"] += 1
        else:
            bucket["known_cost_usd"] += amount(entry["cost"])
        usage = entry.get("usage")
        if not isinstance(usage, dict) or any(
            type(usage.get(key)) is not int or usage[key] < 0
            for key in ("prompt_tokens", "completion_tokens")
        ):
            bucket["unknown_usage_calls"] += 1
        else:
            bucket["prompt_tokens"] += usage["prompt_tokens"]
            bucket["completion_tokens"] += usage["completion_tokens"]
            reasoning = usage.get("completion_tokens_details", {}).get("reasoning_tokens")
            if type(reasoning) is int and reasoning >= 0:
                bucket["reasoning_tokens"] += reasoning
            else:
                bucket["unknown_reasoning_token_calls"] += 1
            cached = usage.get("prompt_tokens_details", {}).get("cached_tokens")
            if type(cached) is int and cached >= 0:
                bucket["cached_prompt_tokens"] += cached
            else:
                bucket["unknown_cached_token_calls"] += 1
    result = {}
    for (task, role), bucket in sorted(buckets.items()):
        result.setdefault(task, {})[role] = {
            **{key: value for key, value in bucket.items() if key != "known_cost_usd"},
            "known_cost_usd": str(bucket["known_cost_usd"]),
            "total_cost_usd": None if bucket["unknown_cost_calls"] else str(bucket["known_cost_usd"]),
        }
    # These are per-arm standalone comparisons, so the shared parent and
    # paired first turn appear in each applicable arm's counterfactual total.
    # The actual study ledger above still charges each unique call only once.
    counterfactual = {}
    for task in sorted(task_ids):
        counterfactual[task] = {}
        for arm in sorted(arms):
            roles = ["parent", arm]
            if arm in ("direct_adaptive", "direct_masked") and "shared_direct" in result.get(task, {}):
                roles.append("shared_direct")
            missing = [role for role in roles if role not in result.get(task, {})]
            known = sum((Decimal(result[task][role]["known_cost_usd"])
                         for role in roles if role not in missing), Decimal(0))
            unknown = sum(result[task][role]["unknown_cost_calls"]
                          for role in roles if role not in missing)
            counterfactual[task][arm] = {
                "components": roles, "missing_billing_components": missing,
                "known_cost_usd": str(known),
                "total_cost_usd": None if missing or unknown else str(known),
                "unknown_cost_calls": unknown,
                "model_calls": None if missing else sum(result[task][role]["calls"] for role in roles),
            }
    return {"available": True, "tasks": result,
            "standalone_arm_cost_by_task": counterfactual,
            "standalone_cost_boundary": "Parent and shared direct first call counted in each standalone arm, but once in actual study spend",
            "reported_total_cost_usd": data.get("total_reported_cost_usd"),
            "known_cost_usd": str(sum((amount(e["cost"]) for e in entries
                                       if e.get("cost") is not None), Decimal(0))),
            "unknown_cost_calls": sum(e.get("cost") is None for e in entries)}


def analyze(folder: Path) -> dict:
    folder = Path(folder)
    protocol, frozen = read(folder / "protocol.json"), read(folder / "frozen.json")
    if frozen.get("protocol_sha256") != digest(protocol):
        raise ValueError("Frozen construction does not bind the protocol")
    dataset_path = folder / "datasets.json"
    if not dataset_path.is_file():
        raise ValueError("Dataset evidence is missing")
    dataset = read(dataset_path)
    if digest(dataset) != protocol.get("dataset_sha256"):
        raise ValueError("Dataset does not bind the protocol")
    dataset_tasks = {task["id"]: task for task in dataset["tasks"]}
    if len(dataset_tasks) != len(dataset["tasks"]) or set(dataset_tasks) != {
        row["task_id"] for row in frozen["records"]
    }:
        raise ValueError("Dataset task membership differs from freeze")
    source = protocol.get("source")
    if source is not None:
        source_path = folder / source["path"]
        if not source_path.is_file() or hashlib.sha256(source_path.read_bytes()).hexdigest() != source["sha256"]:
            raise ValueError("Archived runtime source hash mismatch")
    if frozen.get("complete") is not True or frozen.get("failures"):
        raise ValueError("Only a complete frozen construction may be analysed")
    frozen_hash = digest(frozen)
    receipt_path = folder / "frozen-receipt.json"
    if not receipt_path.is_file() or read(receipt_path).get("frozen_sha256") != frozen_hash:
        raise ValueError("Frozen construction receipt mismatch")
    task_records = {row["task_id"]: row for row in frozen["records"]}
    if len(task_records) != len(frozen["records"]) or not task_records:
        raise ValueError("Duplicate or empty frozen task set")
    for task_id, record in task_records.items():
        source_task = dataset_tasks[task_id]
        if record["source_id"] != source_task["source_id"]:
            raise ValueError("Frozen source differs from bound dataset")
    arms = set(protocol["arms"])
    if len(arms) != len(protocol["arms"]):
        raise ValueError("Duplicate protocol arm")
    if any(set(row["arms"]) != arms for row in task_records.values()):
        raise ValueError("Incomplete or unexpected frozen arms")

    panels = {}
    for panel in ("screen", "confirmation"):
        panel_path = folder / (panel + ".json")
        if not panel_path.is_file():
            continue
        data = read(panel_path)
        if data.get("partition") != panel or data.get("frozen_sha256") != frozen_hash:
            raise ValueError("Panel does not bind the frozen construction")
        if set(data["tasks"]) != set(task_records):
            raise ValueError("Panel task membership differs from freeze")
        selection_path = folder / (panel + "-selection.json")
        if not selection_path.is_file():
            raise ValueError("Panel lacks selection receipt")
        selection = read(selection_path)
        expected = {task: {arm: digest(record["arms"][arm]["selected"])
                           for arm in arms} for task, record in task_records.items()}
        if selection != {"frozen_sha256": frozen_hash, "selection": expected}:
            raise ValueError("Panel selection receipt mismatch")
        tasks = {}
        for task_id, item in data["tasks"].items():
            record = task_records[task_id]
            if item["source_id"] != record["source_id"] or set(item["arms"]) != arms:
                raise ValueError("Panel source or arm mismatch")
            tasks[task_id] = {"source_id": item["source_id"], "family": family(item["source_id"]),
                              "parent": check_score(item["parent"])}
            obligations = paired_obligations(item["parent"])
            if obligations != [digest({"input": row["input"], "expected": row["expected"]})
                               for row in dataset_tasks[task_id][panel]]:
                raise ValueError("Panel obligations differ from bound dataset")
            for arm in sorted(arms):
                selected = item["arms"][arm]["selected"]
                if paired_obligations(selected) != obligations:
                    raise ValueError("Panel obligations differ between parent and arm")
                tasks[task_id][arm] = check_score(selected)
        panels[panel] = tasks
    if "confirmation" not in panels:
        raise ValueError("No protected confirmation panel")

    delivery = {}
    for task_id, record in sorted(task_records.items()):
        delivery[task_id] = {"source_id": record["source_id"],
                             "family": family(record["source_id"])}
        for arm in sorted(arms):
            investigation = record["arms"][arm]["investigation"]
            counts = classify(investigation["receipts"])
            if counts["valid"] != investigation["native_probes"]:
                raise ValueError("Investigation valid count disagrees with receipts")
            turns = investigation.get("turns", [])
            delivery[task_id][arm] = {**counts,
                "query_attempts": investigation["query_attempts"],
                "query_units": investigation["query_units"],
                "detected": investigation["detected"],
                "direct_turns": len(turns),
                "direct_stop": sum(turn.get("stopped") is True for turn in turns),
                "second_turn_distinct_legal": sum(
                    row.get("turn") == 2 and "expected" in row
                    for row in investigation["receipts"]),
                "invalid_deliveries": sum(turn.get("delivery_error") is not None for turn in turns),
                "selected_repair": record["arms"][arm]["selected"]["candidate_selected"],
                "unchanged_candidate": record["arms"][arm]["candidate"]["source"] == record["parent"]["source"],
                "selected_source_changed": record["arms"][arm]["selected"]["source"] != record["parent"]["source"]}

    panel_summary = {}
    for panel, tasks in panels.items():
        by_family = {}
        overall = {}
        for task in tasks.values():
            for role in ("parent", *sorted(arms)):
                values = task[role]
                for bucket in (overall.setdefault(role, {"correct": 0, "total": 0, "errors": 0}),
                               by_family.setdefault(task["family"], {}).setdefault(
                                   role, {"correct": 0, "total": 0, "errors": 0})):
                    for key in ("correct", "total", "errors"):
                        bucket[key] += values[key]
        panel_summary[panel] = {"overall": overall, "by_family": by_family}
    delivery_summary = {}
    for task in delivery.values():
        for arm in sorted(arms):
            values = task[arm]
            bucket = delivery_summary.setdefault(task["family"], {}).setdefault(
                arm, {key: 0 for key in ("slots", "valid", "duplicate", "invalid",
                                        "policy_error", "stop", "semantic_defect",
                                        "technical_defect", "direct_turns", "direct_stop",
                                        "second_turn_distinct_legal",
                                        "invalid_deliveries", "query_attempts", "query_units",
                                        "selected_repair", "unchanged_candidate",
                                        "selected_source_changed")})
            for key in bucket:
                bucket[key] += values[key]

    comparisons = {}
    reference_arms = ["direct_masked", "fixed", "direct_batch", "ordinary", "repair_only", "parent"]
    if "direct_adaptive" in arms:
        for other in reference_arms:
            if other != "parent" and other not in arms:
                continue
            paired = {}
            for task_id, task in sorted(panels["confirmation"].items()):
                paired[task_id] = {"family": task["family"],
                                   "adaptive_minus_reference_correct":
                                   task["direct_adaptive"]["correct"] - task[other]["correct"],
                                   "denominator": task["direct_adaptive"]["total"]}
            by_family = {}
            for name in sorted({row["family"] for row in paired.values()}):
                values = [row["adaptive_minus_reference_correct"] for row in paired.values()
                          if row["family"] == name]
                by_family[name] = {"parents": len(values), "sum": sum(values),
                                   "mean_per_parent": sum(values) / len(values),
                                   "range": [min(values), max(values)]}
            comparisons["direct_adaptive_minus_" + other] = {
                "paired_parents": paired, "by_family": by_family,
                "total_correct_difference": sum(v["adaptive_minus_reference_correct"]
                                                for v in paired.values()),
                "family_macro_mean_per_parent": sum(v["mean_per_parent"]
                                                    for v in by_family.values()) / len(by_family)}
    first_turn_same = None
    second_turn_issued = None
    if {"direct_adaptive", "direct_masked"} <= arms:
        first_turn_same = {}
        second_turn_issued = {}
        for task_id, record in sorted(task_records.items()):
            adaptive = record["arms"]["direct_adaptive"]["investigation"]
            masked = record["arms"]["direct_masked"]["investigation"]
            a_turns, m_turns = adaptive.get("turns", []), masked.get("turns", [])
            a_first = [r for r in adaptive["receipts"] if r.get("turn") == 1]
            m_first = [r for r in masked["receipts"] if r.get("turn") == 1]
            fields = ("slot", "turn", "query", "query_error", "expected",
                      "parent_answer", "parent_error", "verified_counterexample", "query_units")
            def core(rows):
                return [{key: row[key] for key in fields if key in row} for row in rows]
            first_turn_same[task_id] = bool(a_turns and m_turns and
                all(a_turns[0].get(key) == m_turns[0].get(key)
                    for key in ("call_id", "envelope", "raw", "action")) and
                core(a_first) == core(m_first) and
                a_turns[0].get("call_id", "").endswith("direct-shared-turn-1"))
            second_turn_issued[task_id] = {
                "adaptive": len(a_turns) > 1,
                "masked": len(m_turns) > 1,
                "both": len(a_turns) > 1 and len(m_turns) > 1,
            }
            if protocol.get("shared_direct_first_turn") and len(a_turns) > 1:
                a_prompt = a_turns[1]["envelope"]["prompt"]
                if a_prompt.get("outcomes_available") is not True or a_prompt.get("receipts") != a_first:
                    raise ValueError("Adaptive second turn does not receive measured first receipts")
            if protocol.get("shared_direct_first_turn") and len(m_turns) > 1:
                m_prompt = m_turns[1]["envelope"]["prompt"]
                if m_prompt.get("outcomes_available") is not False or any(
                    set(row) - {"slot", "turn", "query"} for row in m_prompt.get("receipts", [])
                ) or [row.get("query") for row in m_prompt.get("receipts", [])] != [
                    row.get("query") for row in m_first
                ]:
                    raise ValueError("Masked second turn leaks outcome or query-legality evidence")
        if protocol.get("shared_direct_first_turn") and not all(first_turn_same.values()):
            raise ValueError("Frozen paired arms do not share exact first action and receipts")

    return {"schema": "zenith_progress_descriptive_analysis_v1",
            "claim_boundary": "Paired parent episodes within three authored native contract families; no independent-mechanism inference",
            "frozen_sha256": frozen_hash, "parents": len(task_records),
            "arms": sorted(arms), "panels": panels, "panel_summary": panel_summary,
            "delivery": delivery, "delivery_summary_by_family": delivery_summary,
            "comparisons": comparisons,
            "adaptive_masked_first_turn_equal": first_turn_same,
            "adaptive_masked_second_turn_issued": second_turn_issued,
            "paired_second_turn_count": (sum(v["both"] for v in second_turn_issued.values())
                                         if second_turn_issued is not None else None),
            "paired_second_distinct_legal_count": (
                sum(delivery[task]["direct_adaptive"]["second_turn_distinct_legal"] > 0 and
                    delivery[task]["direct_masked"]["second_turn_distinct_legal"] > 0
                    for task in task_records)
                if second_turn_issued is not None else None),
            "feedback_isolation_status": (
                "shared_first_turn_verified_in_frozen_record; archived prompt replay still required"
                if protocol.get("shared_direct_first_turn") and first_turn_same and all(first_turn_same.values())
                else "unverified_or_not_declared"),
            "billing": ledger(folder, set(task_records), arms)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", type=Path, help="Frozen run directory or exported evidence bundle")
    parser.add_argument("--output", type=Path, help="Write JSON only to a new output file")
    args = parser.parse_args()
    result = analyze(args.folder)
    rendered = json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    if args.output:
        with args.output.open("x") as stream:
            stream.write(rendered)
    else:
        print(rendered, end="")


if __name__ == "__main__":
    main()
