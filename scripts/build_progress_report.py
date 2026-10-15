#!/usr/bin/env python3
"""Project frozen Progress studies as separate, source-bound observations."""
from __future__ import annotations

import argparse
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import shutil
import sys
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.analyze_progress_campaign import analyze, digest
from scripts.build_conformance_report import safe_relative, verify_manifest


STUDIES = (
    ("v4", "qualification", "progress-qualification-v4", 3, 1),
    ("v5", "qualification", "progress-qualification-v5", 3, 1),
    ("v5", "diagnostic", "progress-diagnostic-v5", 12, 4),
)
REQUIRED_ARMS = {"ordinary", "fixed", "direct_batch", "direct_adaptive",
                 "direct_masked", "repair_only"}
FAMILIES = {"lru", "sqlite", "utf8"}
PROSPECTIVE = {version: Path(f"examples/conformance/progress-protocol-{version}")
               for version in ("v4", "v5")}
FREEZE_SOURCE_LAYOUT = {
    "v4": ("prospective-freeze.json", "prospective-source"),
    "v5": ("prospective-v5-freeze.json", "prospective-v5-source"),
}
LEARNER = Path("examples/continuation-memory/witness-preserving-v1")
FUNDING_AMENDMENT = Path("docs/studies/native/progress-v5-funding-amendment-20261015.json")
RESERVATION_STOP = Path("examples/conformance/progress-diagnostic-v5-reservation-stop")


def read(path: Path):
    return json.loads(path.read_text())


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def publish_prospective(external: Path, root: Path, version: str = "v4") -> Path:
    """Copy already-frozen inputs without changing their bytes or labels."""
    external = Path(external)
    root = Path(root)
    if version not in PROSPECTIVE:
        raise ValueError("Unknown Progress protocol version")
    freeze_name, source_name = FREEZE_SOURCE_LAYOUT[version]
    freeze_path = external / freeze_name
    freeze = read(freeze_path)
    if freeze.get("schema") != "zenith_progress_prospective_freeze_v1":
        raise ValueError("Unexpected prospective freeze")
    destination = root / PROSPECTIVE[version]
    if destination.exists():
        verify_prospective(root, version)
        if sha(destination / freeze_name) != sha(freeze_path):
            raise ValueError("Existing prospective publication binds a different freeze")
        return destination
    files = {freeze_name: sha(freeze_path)}
    for name, expected in freeze["files"].items():
        safe_relative(name)
        path = external / source_name / name
        if not path.is_file() or sha(path) != expected:
            raise ValueError(f"Prospective input differs from freeze: {name}")
        files["source/" + name] = expected
    destination.mkdir(parents=True)
    shutil.copyfile(freeze_path, destination / freeze_name)
    for name in freeze["files"]:
        target = destination / "source" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(external / source_name / name, target)
    manifest = {
        "schema": "zenith_progress_prospective_publication_v1",
        "files": files,
        "boundary": "Byte-identical pre-inference protocol, analyzer, plan, and model evidence; this publication does not amend the freeze.",
    }
    (destination / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    verify_prospective(root, version)
    return destination


def verify_prospective(root: Path, version: str = "v4") -> dict | None:
    folder = Path(root) / PROSPECTIVE[version]
    if not folder.exists():
        return None
    manifest = read(folder / "manifest.json")
    if manifest.get("schema") != "zenith_progress_prospective_publication_v1":
        raise ValueError("Unknown prospective publication manifest")
    actual = {str(path.relative_to(folder)) for path in folder.rglob("*") if path.is_file()}
    if any(path.is_symlink() for path in folder.rglob("*")) or actual != set(manifest["files"]) | {"manifest.json"}:
        raise ValueError("Prospective publication membership mismatch")
    for name, expected in manifest["files"].items():
        safe_relative(name)
        if sha(folder / name) != expected:
            raise ValueError(f"Prospective publication changed: {name}")
    freeze_name = FREEZE_SOURCE_LAYOUT[version][0]
    freeze = read(folder / freeze_name)
    if freeze.get("schema") != "zenith_progress_prospective_freeze_v1":
        raise ValueError("Unexpected prospective freeze")
    if set(manifest["files"]) != {freeze_name} | {
        "source/" + name for name in freeze["files"]
    } or any(manifest["files"]["source/" + name] != expected
             for name, expected in freeze["files"].items()):
        raise ValueError("Published prospective inputs differ from freeze")
    admission = None
    selection = None
    if version == "v5":
        source = folder / "source/work/progress-assimilation-20261014"
        admission = read(source / "v5-admission-test-receipt.json")
        selection = read(source / "v5-panel-disjointness-selection.json")
        result_words = admission.get("result", "").split()
        if (admission.get("schema") != "zenith_v5_admission_test_receipt_v1" or
                admission.get("before_v5_inference") is not True or
                len(result_words) < 2 or not result_words[0].isdigit() or
                result_words[1] != "passed" or
                not {"str.join", "chr", "LShift", "RShift"} <= set(admission["admitted"])):
            raise ValueError("V5 pre-inference admission regression receipt invalid")
        if (selection["selected_seeds"] != {
                stage: freeze[stage]["seed"] for stage in ("qualification", "diagnostic")
        } or not selection["criterion"].startswith("Exact-input panel disjointness only")):
            raise ValueError("V5 seed-selection receipt disagrees with freeze")
        for stage, seed in selection["selected_seeds"].items():
            matches = [row for row in selection["candidates"]
                       if row["stage"] == stage and row["seed"] == seed]
            if (len(matches) != 1 or matches[0]["accepted"] is not True or
                    any(matches[0]["overlap"].values())):
                raise ValueError("V5 selected seed has protected-query overlap")
    return {"freeze": freeze, "admission": admission, "seed_selection": selection,
            "manifest_sha256": sha(folder / "manifest.json"),
            "freeze_sha256": sha(folder / freeze_name)}


def verified_learner(root: Path) -> dict | None:
    folder = Path(root) / LEARNER
    if not folder.exists():
        return None
    manifest = read(folder / "manifest.json")
    if manifest.get("schema") != "zenith_witness_preserving_example_v1":
        raise ValueError("Unknown learner receipt")
    for row in manifest["files"]:
        path = Path(root) / safe_relative(row["path"])
        if (path.is_symlink() or not path.is_file() or path.stat().st_size != row["bytes"]
                or sha(path) != row["sha256"]):
            raise ValueError(f"Learner source custody mismatch: {row['path']}")
    results = read(folder / "results.json")
    rows = results["native_panel"]["rows"]
    by_condition = {}
    for condition in ("ordinary_witness", "generic_singletons"):
        subset = [row for row in rows if row["condition"] == condition]
        if len(subset) != 8 or len({row["task"] for row in subset}) != 8:
            raise ValueError("Learner native configuration mismatch")
        by_condition[condition] = {
            "acquisition_source_calls": sum(row["acquisition_source_calls"] for row in subset),
            "short_correct": sum(row["short"]["correct"] for row in subset),
            "short_total": sum(row["short"]["total"] for row in subset),
            "longer_correct": sum(row["longer"]["correct"] for row in subset),
            "longer_total": sum(row["longer"]["total"] for row in subset),
        }
    if (set(row["task"] for row in rows if row["condition"] == "ordinary_witness") !=
            set(row["task"] for row in rows if row["condition"] == "generic_singletons") or
            by_condition["ordinary_witness"]["acquisition_source_calls"] !=
            manifest["comparison"]["ordinary_witness_acquisition_source_calls"] or
            by_condition["generic_singletons"]["acquisition_source_calls"] !=
            manifest["comparison"]["generic_singletons_acquisition_source_calls"]):
        raise ValueError("Learner comparison disagrees with source-bound rows")
    difference = (by_condition["ordinary_witness"]["acquisition_source_calls"] -
                  by_condition["generic_singletons"]["acquisition_source_calls"])
    return {"id": LEARNER.name, "schema": manifest["schema"],
            "manifest_sha256": sha(folder / "manifest.json"),
            "results_sha256": sha(folder / "results.json"),
            "native_configurations": 8,
            "authored_native_families": manifest["comparison"]["authored_native_families"],
            "conditions": by_condition,
            "ordinary_minus_generic_acquisition_source_calls": difference,
            "boundary": manifest["boundary"]}


def qualification_checks(folder: Path, analysis: dict, *,
                         require_executable_repair: bool = False) -> dict:
    by_family = analysis["delivery_summary_by_family"]
    direct = ("direct_batch", "direct_adaptive", "direct_masked")
    valid = {family: {arm: by_family[family][arm]["valid"] > 0 for arm in direct}
             for family in sorted(FAMILIES)}
    frozen = read(folder / "frozen.json")
    executable = {family: {arm: (
        item["selected"]["candidate_selected"] is True and
        item["selected"]["development"]["total"] > 0 and
        item["selected"]["development"]["errors"] == 0
    ) for record in frozen["records"] if record["source_id"].split("-", 1)[0] == family
      for arm, item in record["arms"].items()} for family in sorted(FAMILIES)}
    misattributed = sum(
        ("policy_error" in row or "query_error" in row) and row.get("verified_counterexample") is True
        for record in frozen["records"] for arm in record["arms"].values()
        for row in arm["investigation"]["receipts"]
    )
    checks = {
        "valid_direct_delivery_each_contract": all(all(v.values()) for v in valid.values()),
        "paired_second_turn_with_distinct_legal_proposals":
            analysis["paired_second_distinct_legal_count"] > 0,
        "zero_investigator_error_misattributed_to_parent": misattributed == 0,
    }
    if require_executable_repair:
        checks["executable_repair_candidate_each_contract"] = all(
            any(values.values()) for values in executable.values())
    return {"passed": all(checks.values()), "checks": checks,
            "valid_by_contract_arm": valid,
            "executable_repair_by_contract_arm": executable,
            "paired_second_turn_count": analysis["paired_second_turn_count"],
            "paired_second_distinct_legal_count": analysis["paired_second_distinct_legal_count"],
            "misattributed_investigator_errors": misattributed}



def verify_funding_amendment(root: Path, folder: Path, protocol: dict,
                             prospective: dict) -> dict:
    """Bind the sole financial delta and the exact settled, unopened prefix."""
    receipt = read(root / FUNDING_AMENDMENT)
    original = dict(protocol, max_cost_usd=receipt["original_cap_usd"])
    original_bytes = (json.dumps(original, indent=2, ensure_ascii=False,
                                allow_nan=False) + "\n").encode()
    expected = prospective["freeze"]["diagnostic"]
    cap, old_cap = Decimal(receipt["amended_cap_usd"]), Decimal(receipt["original_cap_usd"])
    partial = receipt["terminal_partial_replay"]
    prior = verify_manifest(root / RESERVATION_STOP)
    prior_files = read(root / RESERVATION_STOP / "manifest.json")["files"]
    if (receipt.get("schema") != "zenith_conformance_funding_continuation_v1" or
            receipt["prospective_freeze_sha256"] != prospective["freeze_sha256"] or
            receipt["original_protocol_sha256"] != expected["protocol_sha256"] or
            hashlib.sha256(original_bytes).hexdigest() != expected["protocol_sha256"] or
            receipt["amended_protocol_sha256"] != sha(folder / "protocol.json") or
            receipt["dataset_sha256"] != expected["dataset_sha256"] or
            protocol["max_cost_usd"] != receipt["amended_cap_usd"] or
            not cap.is_finite() or not old_cap.is_finite() or not 0 < old_cap < cap <= 4 or
            prior["complete"] or prior["panels"] or
            prior["protocol"] != original or
            prior_files["protocol.json"] != receipt["original_protocol_sha256"] or
            not partial["ok"] or partial["complete"] or partial["protected_partitions"] or
            partial["unknown_cost_attempts"] != 0 or
            prior["calls"] != receipt["prior_paid_attempts"] or
            partial["known_cost_attempts"] != receipt["prior_paid_attempts"] or
            partial["response_files_replayed"] != receipt["prior_paid_attempts"]):
        raise ValueError("Funding amendment changed scientific freeze or unopened settled prefix")
    previous = {entry["call_id"]: entry for entry in prior["billing"]["entries"]}
    current = {entry["call_id"]: entry for entry in read(folder / "billing.json")["entries"]}
    if (sorted(previous) != receipt["prior_call_ids"] or
            sorted(entry["node_id"] for entry in previous.values()) != receipt["prior_node_ids"] or
            any(current.get(key) != entry for key, entry in previous.items()) or
            prior["billing"]["total_reported_cost_usd"] != receipt["prior_reported_cost_usd"] or
            prior["billing"]["total_reserved_usd"] != receipt["prior_reserved_usd"]):
        raise ValueError("Funding continuation changed previously settled call identities or charges")
    for name, expected_hash in receipt["original_files"].items():
        safe_relative(name)
        if name.startswith(("prompts/", "responses/")) or name in {
            "datasets.json", "runtime-source.zip"
        }:
            if (prior_files.get(name) != expected_hash or
                    sha(folder / name) != expected_hash):
                raise ValueError(f"Funding continuation changed prior scientific delivery: {name}")
    return {
        "receipt": str(FUNDING_AMENDMENT), "receipt_sha256": sha(root / FUNDING_AMENDMENT),
        "original_protocol_sha256": receipt["original_protocol_sha256"],
        "amended_protocol_sha256": receipt["amended_protocol_sha256"],
        "original_cap_usd": receipt["original_cap_usd"],
        "amended_cap_usd": receipt["amended_cap_usd"],
        "prior_paid_attempts": receipt["prior_paid_attempts"],
        "prior_reported_cost_usd": receipt["prior_reported_cost_usd"],
        "prior_reserved_usd": receipt["prior_reserved_usd"],
        "prior_evidence": str(RESERVATION_STOP),
        "prior_manifest_sha256": sha(root / RESERVATION_STOP / "manifest.json"),
        "boundary": "Administrative reservation-cap enlargement only. The original unopened terminal prefix is retained separately; every settled provider identity and previous prompt/response is unchanged and counted once. No model output was repaired or retried.",
    }


def observed_study(root: Path, version: str, stage: str, name: str,
                   expected_parents: int, expected_per_family: int,
                   prospective: dict | None) -> dict | None:
    folder = root / "examples" / "conformance" / name
    if not folder.exists():
        return None
    if prospective is None:
        raise ValueError(f"{name} has no published prospective freeze")
    verified = verify_manifest(folder)
    if not verified["complete"]:
        raise ValueError(f"{name} has no complete frozen construction")
    protocol = verified["protocol"]
    expected = prospective["freeze"][stage]
    if version == "v5":
        admission = prospective["admission"]
        with ZipFile(folder / "runtime-source.zip") as archive:
            for member in ("zenith/investigation_program.py", "research/decomposition_study.py",
                           "research/conformance_study.py"):
                if hashlib.sha256(archive.read(member)).hexdigest() != admission["files"][member]:
                    raise ValueError("V5 runtime does not match admitted pre-inference source")
    funding = None
    if sha(folder / "protocol.json") != expected["protocol_sha256"]:
        if version != "v5" or stage != "diagnostic":
            raise ValueError(f"{name} differs from prospective protocol freeze")
        funding = verify_funding_amendment(root, folder, protocol, prospective)
    if (digest(read(folder / "datasets.json")) != expected["dataset_sha256"] or
            protocol["max_calls"] != expected["maximum_model_calls"]):
        raise ValueError(f"{name} differs from prospective protocol or dataset freeze")
    expected_schema = (
        "zenith_conformance_study_v4_direct_actions" if version == "v4" else
        "zenith_conformance_study_v5_direct_actions_executor_compatibility"
    )
    if (protocol.get("schema") != expected_schema
            or set(protocol["arms"]) != REQUIRED_ARMS
            or protocol.get("shared_direct_first_turn") is not True):
        raise ValueError(f"{name} differs from the frozen Progress comparison")
    analysis = analyze(folder)
    families = {family: sum(row["family"] == family
                            for row in analysis["delivery"].values())
                for family in sorted(FAMILIES)}
    if analysis["parents"] != expected_parents or any(
        value != expected_per_family for value in families.values()
    ):
        raise ValueError(f"{name} has unexpected parent or contract membership")
    if analysis["feedback_isolation_status"] != (
        "shared_first_turn_verified_in_frozen_record; archived prompt replay still required"
    ):
        raise ValueError(f"{name} lacks verified shared first turns")
    frozen = read(folder / "frozen.json")
    parent_sources = {hashlib.sha256(row["parent"]["source"].encode()).hexdigest()
                      for row in frozen["records"]}
    parent_prompts = {row["parent"].get("prompt_sha256") for row in frozen["records"]}
    parent_prompts.discard(None)
    standalone = analysis["billing"]["standalone_arm_cost_by_task"]
    arm_accounting = {}
    for arm in analysis["arms"]:
        rows = [standalone[task][arm] for task in standalone]
        missing = sum(len(row["missing_billing_components"]) for row in rows)
        unknown = sum(row["unknown_cost_calls"] for row in rows)
        arm_accounting[arm] = {
            "valid_distinct_native_probes": sum(task[arm]["valid"]
                                                for task in analysis["delivery"].values()),
            "standalone_model_calls": None if missing else sum(row["model_calls"] for row in rows),
            "standalone_known_cost_usd": str(sum(
                (Decimal(row["known_cost_usd"]) for row in rows), Decimal(0))),
            "standalone_unknown_cost_calls": unknown,
            "standalone_missing_billing_components": missing,
        }
    result = {
        "id": name, "version": version, "stage": stage, "complete": True,
        "model": protocol["model"], "pinned_endpoints": protocol["providers"],
        "reasoning_effort": protocol["reasoning_effort"],
        "parent_episodes": analysis["parents"], "parents_by_contract": families,
        "unique_parent_source_hashes": len(parent_sources),
        "unique_parent_prompt_hashes": len(parent_prompts),
        "arms": analysis["arms"],
        "planned_calls_ceiling": protocol["max_calls"],
        "actual_calls": verified["calls"],
        "max_cost_usd": protocol["max_cost_usd"],
        "reported_cost_usd": verified["billing"]["total_reported_cost_usd"],
        "unknown_cost_calls": analysis["billing"]["unknown_cost_calls"],
        "panel_summary": analysis["panel_summary"],
        "comparisons": analysis["comparisons"],
        "primary_parent_signs": primary_parent_signs(
            analysis["comparisons"]["direct_adaptive_minus_direct_masked"]),
        "delivery_summary_by_family": analysis["delivery_summary_by_family"],
        "paired_second_turn_count": analysis["paired_second_turn_count"],
        "paired_second_distinct_legal_count": analysis["paired_second_distinct_legal_count"],
        "adaptive_masked_first_turn_equal": analysis["adaptive_masked_first_turn_equal"],
        "standalone_arm_cost_by_task": analysis["billing"]["standalone_arm_cost_by_task"],
        "arm_accounting": arm_accounting,
        "billing_boundary": analysis["billing"]["standalone_cost_boundary"],
        "native_work_boundary": "Native probe and work counters describe each frozen logical arm trajectory. They exclude deterministic reconstruction and offline audit reexecutions and are not total physical executions, CPU use, or wall-clock lifecycle work. Provider attempts and known charges use exact settled billing identities.",
        "manifest_sha256": sha(folder / "manifest.json"),
    }
    if funding is not None:
        result["funding_amendment"] = funding
    if stage == "qualification":
        result["qualification"] = qualification_checks(
            folder, analysis, require_executable_repair=version == "v5")
    if version == "v4":
        host_admission_witnesses = sum(
            row.get("verified_counterexample") is True and
            row.get("parent_error") == "ValueError: unsupported method: join"
            for record in frozen["records"] for item in record["arms"].values()
            for row in item["investigation"]["receipts"]
        )
        if host_admission_witnesses == 0:
            raise ValueError("Expected v4 host-admission witness missing from frozen receipt")
        result["qualification"]["mechanical_delivery_passed"] = result["qualification"]["passed"]
        result["qualification"]["checks"]["host_admission_attribution_valid"] = False
        result["qualification"]["passed"] = False
        result["qualification"]["host_admission_witnesses"] = host_admission_witnesses
        result["forfeited"] = True
        result["forfeiture_reason"] = (
            "Generic Python admission rejected ordinary UTF-8 repair expressions before behavioral testing."
        )
        result["repair_error_counts_by_contract"] = repair_error_counts(frozen)
    return result


def primary_parent_signs(comparison: dict) -> dict:
    """Count paired outcomes at the parent-episode unit, not by case row."""
    differences = [row["adaptive_minus_reference_correct"]
                   for row in comparison["paired_parents"].values()]
    return {"better": sum(value > 0 for value in differences),
            "tied": sum(value == 0 for value in differences),
            "worse": sum(value < 0 for value in differences),
            "range": [min(differences), max(differences)]}


def repair_error_counts(frozen: dict) -> dict:
    counts = {}
    for record in frozen["records"]:
        family = record["source_id"].split("-", 1)[0]
        for arm, item in record["arms"].items():
            error = item["candidate"].get("error")
            if error:
                counts.setdefault(family, {}).setdefault(arm, {})[error] = (
                    counts.setdefault(family, {}).setdefault(arm, {}).get(error, 0) + 1
                )
    return counts


def cross_stage_audit(root: Path) -> dict:
    """Describe repeated parent bytes and held-out query overlap across stages."""
    bound = {}
    for version, stage, name, _, _ in STUDIES:
        folder = Path(root) / "examples/conformance" / name
        frozen = read(folder / "frozen.json")
        dataset = read(folder / "datasets.json")
        source_hashes = {hashlib.sha256(row["parent"]["source"].encode()).hexdigest()
                         for row in frozen["records"]}
        prompt_hashes = {row["parent"].get("prompt_sha256") for row in frozen["records"]}
        prompt_hashes.discard(None)
        queries = {family: {panel: set() for panel in ("screen", "confirmation")}
                   for family in FAMILIES}
        for task in dataset["tasks"]:
            family = task["source_id"].split("-", 1)[0]
            for panel in ("screen", "confirmation"):
                queries[family][panel].update(digest(row["input"]) for row in task[panel])
        bound[(version, stage)] = {"sources": source_hashes, "prompts": prompt_hashes,
                                   "queries": queries}
    old = bound[("v4", "qualification")]
    qualification, diagnostic = bound[("v5", "qualification")], bound[("v5", "diagnostic")]
    def overlap(earlier, later):
        result = {}
        for family in sorted(FAMILIES):
            first = earlier["queries"][family]
            second = later["queries"][family]
            result[family] = {
                "screen": len(first["screen"] & second["screen"]),
                "confirmation": len(first["confirmation"] & second["confirmation"]),
                "any_later_panel": len((first["screen"] | first["confirmation"]) &
                                       (second["screen"] | second["confirmation"])),
            }
        return result
    return {
        "shared_unique_parent_source_hashes": len(qualification["sources"] & diagnostic["sources"]),
        "shared_unique_parent_prompt_hashes": len(qualification["prompts"] & diagnostic["prompts"]),
        "shared_v4_v5_qualification_parent_source_hashes": len(old["sources"] & qualification["sources"]),
        "shared_v4_v5_qualification_parent_prompt_hashes": len(old["prompts"] & qualification["prompts"]),
        "later_query_overlap_by_contract": overlap(qualification, diagnostic),
        "v4_exposed_query_overlap_by_v5_stage": {
            "qualification": overlap(old, qualification),
            "diagnostic": overlap(old, diagnostic),
        },
        "boundary": "Separate provider episodes and frozen later panels do not guarantee distinct generated parent programs or prompts.",
    }


def headline(studies: list[dict]) -> str:
    by_stage = {(study["version"], study["stage"]): study for study in studies}
    diagnostic = by_stage.get(("v5", "diagnostic"))
    if diagnostic is None:
        qualification = by_stage.get(("v5", "qualification"))
        if qualification is None:
            if ("v4", "qualification") in by_stage:
                return ("The v4 three-parent qualification was retained as an engineering attempt after "
                        "a Python admission failure; its diagnostic was never opened. No v5 result is published yet.")
            return "The prospective Progress campaign has no published qualification or diagnostic measurement yet."
        passed = qualification["qualification"]["passed"]
        return ("The v5 three-parent interface qualification " +
                ("passed" if passed else "did not pass") +
                "; no v5 twelve-parent diagnostic result is published.")
    overall = diagnostic["panel_summary"]["confirmation"]["overall"]
    primary = diagnostic["comparisons"]["direct_adaptive_minus_direct_masked"]
    adaptive = overall["direct_adaptive"]
    masked = overall["direct_masked"]
    fixed = overall["fixed"]
    repair = overall["repair_only"]
    difference = primary["total_correct_difference"]
    sign = "+" if difference > 0 else ""
    return (
        f"The v5 twelve-parent diagnostic recorded {adaptive['correct']}/{adaptive['total']} "
        f"confirmation answers for feedback-aware direct investigation and "
        f"{masked['correct']}/{masked['total']} for outcome-masked investigation "
        f"(paired difference {sign}{difference} answers). Fixed probing scored "
        f"{fixed['correct']}/{fixed['total']} and repair-only "
        f"{repair['correct']}/{repair['total']}. These are parents within three "
        "authored native contracts, not independent mechanism or transfer evidence."
    )


def build(root: Path = ROOT) -> dict:
    root = Path(root)
    studies = []
    bindings = {}
    prospective = {version: verify_prospective(root, version) for version in PROSPECTIVE}
    for version, receipt in prospective.items():
        if receipt is not None:
            bindings[str(PROSPECTIVE[version] / "manifest.json")] = receipt["manifest_sha256"]
            bindings[str(PROSPECTIVE[version] / FREEZE_SOURCE_LAYOUT[version][0])] = receipt["freeze_sha256"]
    for version, stage, name, count, per_family in STUDIES:
        study = observed_study(root, version, stage, name, count, per_family,
                               prospective[version])
        if study is None:
            continue
        studies.append(study)
        path = f"examples/conformance/{name}/manifest.json"
        bindings[path] = study["manifest_sha256"]
        if "funding_amendment" in study:
            funding = study["funding_amendment"]
            bindings[funding["receipt"]] = funding["receipt_sha256"]
            bindings[funding["prior_evidence"] + "/manifest.json"] = funding["prior_manifest_sha256"]
    stages = {(study["version"], study["stage"]) for study in studies}
    cross_stage = cross_stage_audit(root) if {
        ("v4", "qualification"), ("v5", "qualification"), ("v5", "diagnostic")
    } <= stages else None
    query_overlap = bool(cross_stage and (
        any(row["any_later_panel"] for row in cross_stage["later_query_overlap_by_contract"].values()) or
        any(row["any_later_panel"] for stage in cross_stage["v4_exposed_query_overlap_by_v5_stage"].values()
            for row in stage.values())
    ))
    qualification = next((study for study in studies if
                          (study["version"], study["stage"]) == ("v5", "qualification")), None)
    learner = verified_learner(root)
    if learner is not None:
        bindings[str(LEARNER / "manifest.json")] = learner["manifest_sha256"]
        bindings[str(LEARNER / "results.json")] = learner["results_sha256"]
    status = ("protocol_deviation" if ("v5", "diagnostic") in stages and
              (qualification is None or not qualification["qualification"]["passed"] or query_overlap)
              else "complete" if {("v4", "qualification"), ("v5", "qualification"),
                                  ("v5", "diagnostic")} <= stages and learner
              else "qualification_failed" if qualification and not qualification["qualification"]["passed"]
              else "diagnostic_pending" if qualification
              else "pending")
    reservation_stop = None
    if (root / RESERVATION_STOP / "manifest.json").exists():
        stopped = verify_manifest(root / RESERVATION_STOP)
        stopped_protocol = stopped["protocol"]
        if (stopped["complete"] or stopped["panels"] or prospective["v5"] is None or
                sha(root / RESERVATION_STOP / "protocol.json") !=
                prospective["v5"]["freeze"]["diagnostic"]["protocol_sha256"]):
            raise ValueError("Reservation-stop publication differs from unopened original freeze")
        amendment = read(root / FUNDING_AMENDMENT)
        if (amendment.get("schema") != "zenith_conformance_funding_continuation_v1" or
                amendment["original_protocol_sha256"] != sha(root / RESERVATION_STOP / "protocol.json") or
                amendment["prospective_freeze_sha256"] != prospective["v5"]["freeze_sha256"] or
                amendment["prior_paid_attempts"] != stopped["calls"] or
                amendment["prior_reported_cost_usd"] != stopped["billing"]["total_reported_cost_usd"]):
            raise ValueError("Funding amendment differs from published reservation stop")
        reservation_stop = {
            "evidence": str(RESERVATION_STOP), "complete": False, "protected_panels": [],
            "calls": stopped["calls"],
            "reported_cost_usd": stopped["billing"]["total_reported_cost_usd"],
            "original_cap_usd": stopped_protocol["max_cost_usd"],
            "amended_cap_usd": amendment["amended_cap_usd"],
            "funding_amendment": str(FUNDING_AMENDMENT),
            "boundary": "Unopened terminal prefix, retained as audit evidence. Its calls are reused within the funded diagnostic and do not constitute a separate population or additional charges.",
        }
        bindings[str(RESERVATION_STOP / "manifest.json")] = sha(root / RESERVATION_STOP / "manifest.json")
        bindings[str(FUNDING_AMENDMENT)] = sha(root / FUNDING_AMENDMENT)
    summary = headline(studies)
    if learner is not None:
        difference = learner["ordinary_minus_generic_acquisition_source_calls"]
        if difference >= 0:
            summary += (f" The separate finite witness-learner demonstration used "
                        f"{difference} more acquisition source calls than its generic control; "
                        "it does not show an acquired-question gain.")
        else:
            summary += (f" The separate finite witness-learner demonstration used "
                        f"{-difference} fewer acquisition source calls than its generic control "
                        "on authored panels; this is not independent transfer evidence.")
    return {
        "schema": "zenith_progress_campaign_report_v1",
        "status": status,
        "summary": summary,
        "claim_boundary": "The v4 qualification is a forfeited engineering attempt, not part of v5 estimates. V5 uses three authored native contracts; its qualification is excluded from diagnostic estimates. Fresh provider episodes and separately frozen later panels do not guarantee unique parent programs. Parent episodes and case rows are not independent source mechanisms. No transfer or acquired memory claim.",
        "conformance_studies": studies,
        "learner": learner,
        "cross_stage_custody": cross_stage,
        "v5_diagnostic_reservation_stop": reservation_stop,
        "prospective_freezes": {version: {
            "path": str(PROSPECTIVE[version] / FREEZE_SOURCE_LAYOUT[version][0]),
            "sha256": receipt["freeze_sha256"],
            "qualification_protocol_sha256": receipt["freeze"]["qualification"]["protocol_sha256"],
            "diagnostic_protocol_sha256": receipt["freeze"]["diagnostic"]["protocol_sha256"],
        } for version, receipt in prospective.items() if receipt is not None},
        "v5_preinference": None if prospective["v5"] is None else {
            "admission_test_result": prospective["v5"]["admission"]["result"],
            "admitted_forms": prospective["v5"]["admission"]["admitted"],
            "admission_tested_source_hashes": prospective["v5"]["admission"]["files"],
            "selected_seeds": prospective["v5"]["seed_selection"]["selected_seeds"],
            "seed_selection_criterion": prospective["v5"]["seed_selection"]["criterion"],
            "rejected_initial_seeds": prospective["v5"]["seed_selection"]["rejected_initial_seeds"],
        },
        "source_bindings": bindings,
    }


def render_markdown(report: dict) -> str:
    lines = ["# Progress campaign: measured receipt", "", report["summary"], "",
             "The [v4 protocol](../../progress-protocol-20261014.md) and "
             "[v5 amendment](../../progress-protocol-v5-20261014.md) fix the arms and decision rules. "
             "The [machine receipt](progress-campaign-20261014.json) binds the published source manifests.", ""]
    by_stage = {(study["version"], study["stage"]): study
                for study in report["conformance_studies"]}
    preinference = report["v5_preinference"]
    if preinference:
        lines += ["## V5 pre-inference custody", "",
                  f"The frozen admission regression recorded `{preinference['admission_test_result']}` "
                  "for join, `chr`, and bit shifts before v5 model inference. "
                  f"The qualification seed is {preinference['selected_seeds']['qualification']} "
                  f"and the diagnostic seed is {preinference['selected_seeds']['diagnostic']}. "
                  "Earlier candidates were rejected using exact protected-input overlap only, "
                  "before any v5 model response.", ""]
    old_qualification = by_stage.get(("v4", "qualification"))
    if old_qualification:
        utf8_errors = old_qualification["repair_error_counts_by_contract"].get("utf8", {})
        rejected = sum(sum(reasons.values()) for reasons in utf8_errors.values())
        lines += ["## Preserved v4 engineering attempt", "",
                  f"The v4 qualification used {old_qualification['actual_calls']} model "
                  f"attempts and reported ${old_qualification['reported_cost_usd']} in known "
                  f"charges ({old_qualification['unknown_cost_calls']} unknown-charge attempts). "
                  f"{rejected} UTF-8 repair candidate(s) recorded execution or admission errors; "
                  f"{old_qualification['qualification']['host_admission_witnesses']} native probes "
                  "mislabelled the host's `.join` admission failure as a parent technical witness. "
                  "Its diagnostic was never opened; no v4 qualification answers enter v5 estimates. "
                  + old_qualification["forfeiture_reason"], ""]
    qualification = by_stage.get(("v5", "qualification"))
    if qualification:
        result = qualification["qualification"]
        lines += ["## V5 interface qualification", "",
                  f"{qualification['parent_episodes']} parent episodes; {qualification['actual_calls']} "
                  f"model attempts; known reported cost ${qualification['reported_cost_usd']}; "
                  f"unknown-charge attempts {qualification['unknown_cost_calls']}. "
                  f"Qualification {'passed' if result['passed'] else 'did not pass'}; "
                  "its panel scores are excluded from the diagnostic.", "",
                  "| Prespecified check | Result |", "|---|---|" ]
        for key, value in result["checks"].items():
            lines.append(f"| {key.replace('_', ' ')} | {'pass' if value else 'fail'} |")
        lines.append("")
    diagnostic = by_stage.get(("v5", "diagnostic"))
    reservation_stop = report.get("v5_diagnostic_reservation_stop")
    if diagnostic is None and reservation_stop:
        lines += ["## Diagnostic awaiting completion", "",
                  f"The original diagnostic stopped at {reservation_stop['calls']} settled calls "
                  f"and ${reservation_stop['reported_cost_usd']} in reported charges, "
                  "with no later panel opened. A separate "
                  "[funding amendment](progress-v5-funding-amendment-20261015.md) enlarges its "
                  f"reservation ceiling from ${reservation_stop['original_cap_usd']} to "
                  f"${reservation_stop['amended_cap_usd']} while reusing the exact settled responses. "
                  "No completed diagnostic measurement is published. A reservation cap is not a charge.", ""]
    if diagnostic:
        overall = diagnostic["panel_summary"]["confirmation"]["overall"]
        lines += ["## V5 twelve-parent diagnostic", "",
                  f"{diagnostic['actual_calls']} actual model attempts (ceiling "
                  f"{diagnostic['planned_calls_ceiling']}); known reported cost "
                  f"${diagnostic['reported_cost_usd']}; unknown-charge attempts "
                  f"{diagnostic['unknown_cost_calls']}. Shared first-turn provider calls "
                  "are billed once; each paired arm separately executes and counts its native probes.", "",
                  "| Condition | Confirmation answers | Distinct legal probes | Standalone model calls | Known standalone cost |",
                  "|---|---:|---:|---:|---:|"]
        funding = diagnostic.get("funding_amendment")
        if funding:
            lines[-2:-2] = [
                f"The [funding amendment](progress-v5-funding-amendment-20261015.md) "
                f"raised the cumulative reservation ceiling from ${funding['original_cap_usd']} "
                f"to ${funding['amended_cap_usd']} before resumed inference. The original "
                f"{funding['prior_paid_attempts']}-call terminal prefix reported "
                f"${funding['prior_reported_cost_usd']} and opened no later panel. All its "
                "settled responses were reused unchanged; its charges are included once in the "
                "completed diagnostic. The cap is not a reported charge.", ""]
        for arm in ("parent", "repair_only", "fixed", "ordinary", "direct_batch",
                    "direct_masked", "direct_adaptive"):
            score = overall[arm]
            if arm == "parent":
                lines.append(f"| `{arm}` | {score['correct']}/{score['total']} | 0 | — | — |")
            else:
                account = diagnostic["arm_accounting"][arm]
                lines.append(f"| `{arm}` | {score['correct']}/{score['total']} | "
                             f"{account['valid_distinct_native_probes']} | "
                             f"{account['standalone_model_calls']} | "
                             f"${account['standalone_known_cost_usd']} |")
        lines += ["", "Standalone costs count the shared parent call and, for each paired "
                  "direct arm, its shared first investigator call. The actual study ledger "
                  "charges each unique provider call once. Unknown charges remain unknown in the receipt."]
        lines += ["", "| Condition | Repair candidate selected | Selected source changed | Candidate identical to parent |",
                  "|---|---:|---:|---:|"]
        for arm in ("repair_only", "fixed", "ordinary", "direct_batch", "direct_masked", "direct_adaptive"):
            counts = {key: sum(values[arm][key] for values in
                               diagnostic["delivery_summary_by_family"].values())
                      for key in ("selected_repair", "selected_source_changed", "unchanged_candidate")}
            lines.append(f"| `{arm}` | {counts['selected_repair']}/{diagnostic['parent_episodes']} | "
                         f"{counts['selected_source_changed']}/{diagnostic['parent_episodes']} | "
                         f"{counts['unchanged_candidate']}/{diagnostic['parent_episodes']} |")
        primary = diagnostic["comparisons"]["direct_adaptive_minus_direct_masked"]
        signs = diagnostic["primary_parent_signs"]
        lines += ["", f"The all-parent paired adaptive-minus-masked difference is "
                  f"{primary['total_correct_difference']:+d} confirmation answers. "
                  f"Across parent episodes, adaptive was better in {signs['better']}, "
                  f"tied in {signs['tied']}, and worse in {signs['worse']} "
                  f"(per-parent difference range {signs['range'][0]:+d} to "
                  f"{signs['range'][1]:+d}). "
                  f"Both arms reached a second decision in "
                  f"{diagnostic['paired_second_turn_count']}/{diagnostic['parent_episodes']} "
                  f"parents and both delivered a distinct legal second-turn query in "
                  f"{diagnostic['paired_second_distinct_legal_count']}. "
                  "These counts describe an intervention opportunity; they do not by themselves show a benefit.", "",
                  "| Contract | Paired answer difference | Parent episodes |", "|---|---:|---:|"]
        for family, values in primary["by_family"].items():
            lines.append(f"| {family} | {values['sum']:+d} | {values['parents']} |")
        lines.append("")
        custody = report["cross_stage_custody"]
        lines += [f"Within the diagnostic, {diagnostic['unique_parent_source_hashes']} of "
                  f"{diagnostic['parent_episodes']} parent source hashes are unique; "
                  f"{diagnostic['unique_parent_prompt_hashes']} of "
                  f"{diagnostic['parent_episodes']} parent prompt hashes are unique. "
                  f"Across stages, {custody['shared_unique_parent_source_hashes']} unique "
                  f"parent source hash(es) and {custody['shared_unique_parent_prompt_hashes']} "
                  "parent prompt hash(es) recur. Query overlap between qualification and "
                  "diagnostic later panels, by contract:", "",
                  "| Contract | Screen overlap | Confirmation overlap | Any later-panel overlap |",
                  "|---|---:|---:|---:|"]
        for family, values in custody["later_query_overlap_by_contract"].items():
            lines.append(f"| {family} | {values['screen']} | {values['confirmation']} | "
                         f"{values['any_later_panel']} |")
        lines += ["", "V4's opened qualification queries overlapping v5 later panels:", "",
                  "| V5 stage | LRU | SQLite | UTF-8 |", "|---|---:|---:|---:|"]
        for stage, values in custody["v4_exposed_query_overlap_by_v5_stage"].items():
            lines.append(f"| {stage} | {values['lru']['any_later_panel']} | "
                         f"{values['sqlite']['any_later_panel']} | "
                         f"{values['utf8']['any_later_panel']} |")
        lines.append("")
    learner = report["learner"]
    if learner:
        ordinary = learner["conditions"]["ordinary_witness"]
        generic = learner["conditions"]["generic_singletons"]
        lines += ["## Separate finite learner demonstration", "",
                  f"Ordinary witness acquisition used {ordinary['acquisition_source_calls']} "
                  f"native source calls across {learner['native_configurations']} configurations; "
                  f"generic no-experience singleton acquisition used "
                  f"{generic['acquisition_source_calls']}. The ordinary-minus-generic difference "
                  f"is {learner['ordinary_minus_generic_acquisition_source_calls']:+d} calls, "
                  "so these panels show no acquired-question saving. Later panels are scored "
                  "separately from acquisition cost. " + learner["boundary"], ""]
    lines += ["## Interpretation boundary", "",
              report["claim_boundary"], "",
              "The earlier exposed Ling campaign and PROGRESS return cases are engineering evidence, "
              "not pooled with this fresh diagnostic. The repair-only arm distinguishes a new probe "
              "from another repair attempt. The fixed arm carries a declared standards-informed UTF-8 prior. "
              "Costs are settled provider attempts where known; a reservation is not a bill. "
              "Native probe and work counters describe the frozen logical trajectories. They exclude "
              "reconstruction and offline audit reexecutions, so they are not total physical executions, "
              "CPU use or wall-clock lifecycle work. Native work units are comparable only within a source family.", ""]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--output-json", type=Path)
    parser.add_argument("--output-md", type=Path)
    parser.add_argument("--publish-prospective-from", type=Path)
    parser.add_argument("--prospective-version", choices=sorted(PROSPECTIVE), default="v4")
    args = parser.parse_args()
    if args.publish_prospective_from:
        publish_prospective(args.publish_prospective_from, args.root,
                            args.prospective_version)
    report = build(args.root)
    if report["status"] == "pending" and (args.output_json or args.output_md):
        raise ValueError("Measured report outputs require a completed stage; no pending result is published")
    if args.output_json:
        args.output_json.write_text(json.dumps(report, indent=2, ensure_ascii=False,
                                              allow_nan=False) + "\n")
    if args.output_md:
        args.output_md.write_text(render_markdown(report))
    print(json.dumps({"status": report["status"],
                      "studies": [row["id"] for row in report["conformance_studies"]]}))


if __name__ == "__main__":
    main()
