#!/usr/bin/env python3
"""Publish observation-study evidence and replay its archived runtime offline.

Adapted from build_learning_report.py: public records are explicit projections,
never copies of provider transport. Source ZIPs and executable content retain
their original bytes. Replay imports only a safely extracted frozen checkout.
"""
from __future__ import annotations

import argparse
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = "examples/observation-learning/v1"
REPORT = "docs/history/observation-learning-20261013.json"
CANARIES = ("qwen", "qwen-funded", "deepseek")
CALL_FIELDS = ("call_id", "run_id", "node_id", "status", "requested_model", "actual_provider",
               "requested_provider_slug", "verified_provider_name", "reasoning_effort", "cost",
               "reserved_cost_usd", "prompt_sha256", "system_prompt_sha256", "response_sha256",
               "response_format_sha256", "recorded_at", "max_output_tokens", "input_token_bound",
               "inference_mode", "queue_elapsed_seconds", "network_elapsed_seconds",
               "global_inference_limit", "provider_route_limit", "provider_route_sha256")
PRIVATE_URL = re.compile(r"https?://[^\s\"'<>]*(?:/keys/|[?&](?:api_key|token|key)=)[^\s\"'<>]*", re.I)
SECRET = re.compile(r"\b(?:sk-or-v1-|sk-proj-|sk-)[A-Za-z0-9_-]{16,}|\bBearer\s+[A-Za-z0-9._-]{20,}")
URL = re.compile(r"https?://[^\s\"'<>]+")


def digest(value):
    # Exactly the existing zenith.providers canonical contract, without a live import.
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                    ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n")
    temporary.replace(path)


def sanitize(value, *, error=False):
    """Preserve ordinary public links; remove every URL from error strings."""
    if isinstance(value, dict):
        return {k: sanitize(v, error=error or k in ("error", "halt_reason")) for k, v in value.items()}
    if isinstance(value, list):
        return [sanitize(v, error=error) for v in value]
    if isinstance(value, str):
        value = SECRET.sub("[credential omitted]", PRIVATE_URL.sub("[private key URL omitted]", value))
        return URL.sub("[error URL omitted]", value) if error else value
    return value


def _amount(value):
    number = Decimal(str(value))
    if not number.is_finite() or number < 0:
        raise ValueError("invalid monetary amount in original ledger")
    return number


def _numeric_usage(value):
    if isinstance(value, dict):
        return {k: projected for k, child in value.items()
                if (projected := _numeric_usage(child)) is not None}
    if type(value) in (int, float, bool):
        return value
    if isinstance(value, str):
        try:
            number = Decimal(value)
        except ArithmeticError:
            return None
        if number.is_finite():
            return value
    return None


def project_calls(study):
    path = Path(study) / "budget/budget.json"
    if not path.exists():
        return {"calls": [], "ledger_present": False, "reported_cost_usd": "0",
                "unknown_cost_calls": 0, "unknown_reservations_usd": "0"}, []
    ledger_bytes = path.read_bytes()
    ledger = json.loads(ledger_bytes)
    attempt_records = {}
    for record_path in Path(study).rglob("api_calls/openrouter_budgeted/*.json"):
        payload = record_path.read_bytes()
        record = json.loads(payload)
        call_id = record["call_id"]
        if call_id not in ledger["entries"] or call_id in attempt_records:
            raise ValueError("unbound or duplicate recursive provider attempt record")
        attempt_records[call_id] = {"path": record_path.relative_to(study).as_posix(),
            "original_bytes_sha256": sha(payload), "json_sha256": digest(record)}
    calls, contents = [], []
    for call_id, entry in ledger["entries"].items():
        if not re.fullmatch(r"[0-9a-f]{64}", call_id) or entry["call_id"] != call_id:
            raise ValueError("call identity mismatch")
        call = {k: entry.get(k) for k in CALL_FIELDS}
        response = entry.get("provider_response") or {}
        call["actual_model"] = response.get("model") or (entry.get("provider_receipt") or {}).get("model")
        call["usage"] = _numeric_usage(response.get("usage"))
        call["catalogue_pricing"] = _numeric_usage(entry.get("catalogue_pricing"))
        call["reservation_pricing"] = _numeric_usage(entry.get("reservation_pricing"))
        choices = response.get("choices") or []
        first = choices[0] if choices and isinstance(choices[0], dict) else {}
        call["finish_reason"] = first.get("finish_reason")
        call["original_entry_sha256"] = digest(entry)
        call["private_attempt_record"] = attempt_records.get(call_id)
        if call["private_attempt_record"] is not None:
            call["private_attempt_record"]["matches_ledger"] = attempt_records[call_id]["json_sha256"] == digest(entry)
        call["provider_transport_published"] = False
        if entry.get("error"):
            call["error"] = sanitize(entry["error"], error=True)
            call["original_error_sha256"] = sha(entry["error"].encode())
        content = (first.get("message") or {}).get("content")
        if isinstance(content, str):
            if entry.get("response_sha256") and sha(content.encode()) != entry["response_sha256"]:
                raise ValueError("model content custody mismatch")
            contents.append({"call_id": call_id, "content": sanitize(content),
                "original_content_sha256": sha(content.encode()),
                "projection": "assistant content only; transport, headers, routing and credentials omitted",
                "redacted": sanitize(content) != content})
        else:
            call["content_available"] = False
        calls.append(sanitize(call))
    reported = sum((_amount(c["cost"]) for c in calls if c["cost"] is not None), Decimal(0))
    reserved = sum((_amount(c["reserved_cost_usd"]) for c in calls), Decimal(0))
    if reported != _amount(ledger["total_reported_cost_usd"]) or reserved != _amount(ledger["total_reserved_usd"]):
        raise ValueError("original ledger totals do not match individual attempts")
    unknown = [c for c in calls if c["cost"] is None]
    return {"calls": calls, "ledger_present": True, "original_ledger_sha256": sha(ledger_bytes),
            "reported_cost_usd": str(reported), "unknown_cost_calls": len(unknown),
            "unknown_reservations_usd": str(sum((_amount(c["reserved_cost_usd"]) for c in unknown), Decimal(0))),
            "halted": bool(ledger.get("halted"))}, contents


def _archive_members(path):
    members = {}
    with ZipFile(path) as archive:
        for info in archive.infolist():
            name = PurePosixPath(info.filename)
            mode = info.external_attr >> 16
            if (name.is_absolute() or ".." in name.parts or "\\" in info.filename or ":" in name.parts[0]
                    or not name.parts or stat.S_ISLNK(mode) or info.filename in members):
                raise ValueError("unsafe or duplicate source archive member")
            if info.is_dir():
                raise ValueError("source archive contains unexpected directory entries")
            payload = archive.read(info)
            text = payload.decode("utf-8")
            if PRIVATE_URL.search(text) or SECRET.search(text):
                raise ValueError("source archive contains private credential-like material")
            members[info.filename] = sha(payload)
    required = {"research/observation_world.py", "research/observation_learning_study.py",
                "zenith/investigation_program.py", "zenith/providers.py"}
    if not required <= members.keys():
        raise ValueError("source archive lacks the exact observation runtime")
    return members


def _verify_delivery(study, projection, schema_name="observation"):
    for call in projection["calls"]:
        node = call["node_id"]
        if not isinstance(node, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", node):
            raise ValueError("invalid campaign node identity")
        artifact = read(study / "prompts" / f"{node}.json")
        encoded = json.dumps(artifact["prompt"], ensure_ascii=False).encode()
        if sha(encoded) != call["prompt_sha256"]:
            raise ValueError("actual prompt delivery custody mismatch")
        if call["system_prompt_sha256"] and sha(artifact["system"].encode()) != call["system_prompt_sha256"]:
            raise ValueError("system prompt delivery custody mismatch")
        response_format = {"type": "json_schema", "json_schema": {
            "name": schema_name, "strict": True, "schema": artifact["schema"]}}
        if call["response_format_sha256"] and digest(response_format) != call["response_format_sha256"]:
            raise ValueError("response schema delivery custody mismatch")
        raw = study / "responses" / f"{node}-raw.json"
        if raw.exists() and call["response_sha256"] and sha(read(raw)["content"].encode()) != call["response_sha256"]:
            raise ValueError("retained raw model content differs from actual response")
        call["prompt_delivery_verified"] = True


def _custody(study):
    protocol, data = read(study / "protocol.json"), read(study / "datasets.json")
    archive = study / "runtime-source.zip"
    if sha(archive.read_bytes()) != protocol["source"]["sha256"]:
        raise ValueError("source archive custody mismatch")
    if digest(data) != protocol["dataset_sha256"]:
        raise ValueError("dataset custody mismatch")
    for name in ("started.json", "preparation-receipt.json"):
        if (study / name).exists():
            receipt = read(study / name)
            if receipt["protocol_sha256"] != digest(protocol) or receipt["dataset_sha256"] != digest(data):
                raise ValueError("preparation/start custody mismatch")
    if (study / "interruption.json").exists() and read(study / "interruption.json")["protocol_sha256"] != digest(protocol):
        raise ValueError("interruption protocol custody mismatch")
    result = read(study / "results.json") if (study / "results.json").exists() else None
    frozen = read(study / "all-frozen.json") if (study / "all-frozen.json").exists() else None
    if result is not None:
        if frozen is None or len(frozen) != protocol["worlds"]:
            raise ValueError("completed result lacks the complete frozen cohort")
        if result["protocol_sha256"] != digest(protocol) or result["frozen_sha256"] != digest(frozen):
            raise ValueError("protected result custody mismatch")
    records = frozen if frozen is not None else [read(p) for p in sorted(study.glob("world-*-frozen.json"))]
    source_ids = [s["source_id"] for s in data["public"]["streams"]]
    if [r["source_id"] for r in records] != source_ids[:len(records)]:
        raise ValueError("frozen cohort identity/order mismatch")
    for index, record in enumerate(records):
        per_world = study / f"world-{index:02d}-frozen.json"
        if per_world.exists() and digest(read(per_world)) != digest(record):
            raise ValueError("individual frozen world differs from all-frozen record")
    record_ids = {r["source_id"] for r in records}
    partial = [read(path) for path in sorted(study.glob("world-*-partial.json"))
               if read(path)["source_id"] not in record_ids]
    for record in records + partial:
        if record["source_id"] not in source_ids:
            raise ValueError("partial source identity mismatch")
        for state in record["arms"].values():
            for entry in state["rounds"]:
                if entry["candidate_sha256"] != digest(entry["proposal"]):
                    raise ValueError("candidate custody mismatch")
            for checkpoint in state["checkpoints"]:
                if checkpoint["program_sha256"] != digest(checkpoint["program"]):
                    raise ValueError("checkpoint custody mismatch")
    return protocol, data, result, records, _archive_members(archive)


def _bundle(study, supplied=None):
    version = re.search(r"(?:^|-)(v[0-9]+)$", Path(study).name)
    relative = supplied or f"examples/observation-learning/{version.group(1) if version else 'v1'}"
    path = PurePosixPath(relative)
    if len(path.parts) != 3 or path.parts[:2] != ("examples", "observation-learning") or not re.fullmatch(r"v[0-9]+", path.parts[2]):
        raise ValueError("bundle must be an immutable examples/observation-learning/vN sibling")
    return path.as_posix()


def _build(study, canaries=None, *, root=ROOT, allow_partial=False, bundle=None):
    study, root = Path(study).resolve(), Path(root).resolve()
    protocol, data, result, records, members = _custody(study)
    failed = (study / "failure.json").exists()
    interruption = read(study / "interruption.json") if (study / "interruption.json").exists() else None
    if result is None and not failed and interruption is None and not allow_partial:
        raise ValueError("campaign is active; wait for a terminal record or explicitly allow a partial snapshot")
    bundle = _bundle(study, bundle)
    if canaries is None:
        canaries = ([study.parent / f"frontier-model-canary-20261013-{name}" for name in CANARIES]
                    if bundle.endswith("/v1") else sorted(study.parent.glob("openrouter-route-canary-20261013-*")))
        canaries = [path for path in canaries if path.exists()]
    target = root / bundle
    if target.exists():
        raise ValueError("public bundle exists; preserve it and use a separately versioned destination")
    target.mkdir(parents=True)
    originals = {}

    def copy_json(source, relative):
        payload = source.read_bytes()
        value = json.loads(payload)
        projected = sanitize(value)
        destination = target / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        if projected == value:
            destination.write_bytes(payload)
        else:
            write(destination, projected)
        originals[relative] = {"original_bytes_sha256": sha(payload), "original_json_sha256": digest(value),
            "published_bytes_sha256": sha(destination.read_bytes()),
            "projection": "unchanged" if projected == value else "credential/private-key/error URL redaction"}

    names = ["protocol.json", "datasets.json", "preparation-receipt.json", "started.json",
             "all-frozen.json", "results.json", "failure.json", "interruption.json",
             "freeze-receipt.json", "all-frozen-receipt.json", "pilot-checkpoint.json"]
    for name in names:
        if (study / name).exists():
            copy_json(study / name, name)
    for pattern in ("world-*-frozen.json", "world-*-partial.json", "prompts/*.json", "responses/*.json"):
        for source in sorted(study.glob(pattern)):
            copy_json(source, source.relative_to(study).as_posix())
    (target / "runtime-source.zip").write_bytes((study / "runtime-source.zip").read_bytes())
    # Runtime/program modifications cannot be smuggled through a sanitization pass.
    for name in ("protocol.json", "datasets.json", "all-frozen.json", "results.json"):
        if name in originals and originals[name]["projection"] != "unchanged":
            raise ValueError("executable replay evidence needs redaction; do not publish an altered result")
    projection, content = project_calls(study)
    _verify_delivery(study, projection)
    if interruption is not None:
        if (interruption["attempts"] != len(projection["calls"])
                or _amount(interruption["reported_cost_usd"]) != _amount(projection["reported_cost_usd"])
                or interruption["completed_worlds"] != len(records)
                or (interruption.get("stopped_between_provider_calls")
                    and any(c["status"] == "attempt_started" for c in projection["calls"]))):
            raise ValueError("interruption call/cost/cohort custody mismatch")
    write(target / "calls.json", projection)
    for item in content:
        write(target / "model-content" / f"{item['call_id']}.json", item)
    canary_reports = []
    canary_archives = {}
    for canary in map(Path, canaries):
        prefix = f"canaries/{canary.name}"
        for name in ("protocol.json", "result.json", "response.json", "raw-response.json", "execution.json", "failure.json"):
            if (canary / name).exists():
                copy_json(canary / name, f"{prefix}/{name}")
        calls, content = project_calls(canary)
        canary_protocol = read(canary / "protocol.json") if (canary / "protocol.json").exists() else {}
        if (canary / "runtime-source.zip").exists():
            archive = canary / "runtime-source.zip"
            archive_hash = sha(archive.read_bytes())
            if archive_hash != canary_protocol["runtime_source"]["sha256"]:
                raise ValueError("canary source archive custody mismatch")
            archive_relative = f"{prefix}/runtime-source.zip"
            (target / archive_relative).write_bytes(archive.read_bytes())
            archive_members = _archive_members(archive)
            for name, fingerprint in canary_protocol.get("loaded_runtime_fingerprints",
                    canary_protocol.get("runtime_fingerprints", {})).items():
                if archive_members.get(name) != fingerprint:
                    raise ValueError("canary loaded runtime fingerprint differs from archived source")
            canary_archives[archive_relative] = {"sha256": archive_hash, "members": archive_members}
            raw_path = canary / "raw-response.json"
            if raw_path.exists():
                raw = read(raw_path)
                text = raw.get("text", raw.get("content"))
                if not isinstance(text, str) or len(content) != 1 or sha(text.encode()) != content[0]["original_content_sha256"]:
                    raise ValueError("canary raw content differs from settled provider response")
                if (canary / "response.json").exists() and json.loads(text) != read(canary / "response.json"):
                    raise ValueError("canary parsed response differs from original model content")
            for call in calls["calls"]:
                if call["prompt_sha256"] and sha(json.dumps(canary_protocol["prompt"], ensure_ascii=False).encode()) != call["prompt_sha256"]:
                    raise ValueError("canary actual prompt delivery custody mismatch")
        if (canary / "result.json").exists():
            result_protocol = read(canary / "result.json").get("protocol_sha256")
            if result_protocol and result_protocol != digest(canary_protocol):
                raise ValueError("canary protocol/result custody mismatch")
        write(target / prefix / "calls.json", calls)
        for item in content:
            write(target / prefix / "model-content" / f"{item['call_id']}.json", item)
        canary_reports.append({"id": canary.name, **calls,
            "result": sanitize(read(canary / "result.json")) if (canary / "result.json").exists() else None})
    all_calls = projection["calls"] + [call for c in canary_reports for call in c["calls"]]
    if len({c["call_id"] for c in all_calls}) != len(all_calls):
        raise ValueError("duplicated paid attempt across campaign/canary inputs")
    reported = sum((_amount(c["cost"]) for c in all_calls if c["cost"] is not None), Decimal(0))
    unknown = [c for c in all_calls if c["cost"] is None]
    unknown_bound = sum((_amount(c["reserved_cost_usd"]) for c in unknown), Decimal(0))
    replay_context = {"runtime_archive": "runtime-source.zip", "original_protocol_sha256": digest(protocol),
        "portability_projection": "Use this relative archive, never resolve original protocol.source.path. "
            "Protocol bytes are preserved as provenance; call archived audit directly after independent custody checks.",
        "inference_calls": 0}
    write(target / "replay-context.json", replay_context)
    write(target / "publication-freeze-receipt.json", {"authority": "post-run publication custody check, not a newly executed learning freeze",
        "protocol_sha256": digest(protocol), "dataset_sha256": digest(data), "runtime_sha256": protocol["source"]["sha256"],
        "frozen_records": len(records), "all_frozen_sha256": digest(records) if (study / "all-frozen.json").exists() else None})
    manifest = {"schema": "zenith_observation_public_bundle_v1", "complete": result is not None,
        "status": "complete" if result is not None else "interrupted" if interruption is not None else "failed" if failed else "partial_snapshot",
        "protocol_sha256": digest(protocol), "dataset_sha256": digest(data),
        "source_archive_sha256": protocol["source"]["sha256"], "archive_members": members,
        "canary_archives": canary_archives,
        "originals": originals, "source_transport_excluded": True,
        "files": {p.relative_to(target).as_posix(): sha(p.read_bytes()) for p in sorted(target.rglob("*")) if p.is_file()}}
    write(target / "manifest.json", manifest)
    report = {"schema": "zenith_observation_learning_evidence_v1", "campaign": study.name,
        "status": manifest["status"], "complete": result is not None, "planned_worlds": protocol["worlds"],
        "frozen_worlds": len(records), "model": protocol["model"], "provider_slug": protocol["provider_slug"],
        "reasoning_effort": protocol["reasoning_effort"], "max_output_tokens": protocol["max_output_tokens"],
        "bundle": bundle, "manifest_sha256": sha((target / "manifest.json").read_bytes()),
        "protocol_sha256": digest(protocol), "source_archive_sha256": protocol["source"]["sha256"],
        "campaign_calls": projection, "canaries": canary_reports, "total_calls": len(all_calls),
        "total_reported_cost_usd": str(reported), "unreported_cost_calls": len(unknown),
        "unreported_cost_reservations_usd": str(unknown_bound),
        "cost_bounds_usd": [str(reported), str(reported + unknown_bound)],
        "aggregate": result["aggregate"] if result else None,
        "comparisons": result["comparisons"] if result else None,
        "per_world": [{"source_id": row["source_id"], **{arm: {k: row[arm][k] for k in ("correct", "total", "unsupported", "errors")}
            for arm in (*protocol["arms"], "freeze_and_grow", "empty_history", "cold")}} for row in result["worlds"]] if result else [],
        "failure": sanitize(read(study / "failure.json")) if failed else None,
        "interruption": sanitize(interruption),
        "pilot": sanitize(read(study / "pilot-checkpoint.json")) if (study / "pilot-checkpoint.json").exists() else None,
        "protected_evaluation_performed": True if result else interruption.get("protected_evaluation_performed") if interruption else read(study / "failure.json").get("protected_evaluation_performed") if failed else None,
        "provider_slugs": protocol.get("provider_slugs", [protocol["provider_slug"]]),
        "workers": protocol.get("workers", 1), "inference_mode": protocol.get("inference_mode", "serial"),
        "world_model_bindings": [{"source_id": stream["source_id"], "model": protocol["model"],
            "provider_slug": protocol.get("world_providers", [protocol["provider_slug"]] * protocol["worlds"])[index],
            "reasoning_effort": protocol["reasoning_effort"]} for index, stream in enumerate(data["public"]["streams"])],
        "boundary": "Configured sources in one native family. Authored protected compositions. "
            "No semantic-domain independence, arbitrary ontology discovery or special architecture benefit inferred from persistence."}
    routes = report["provider_slugs"]
    if len(set(routes)) > 1:
        report["provider_slug"] = "mixed"
    snapshot = {k: v for k, v in report.items() if k != "manifest_sha256"}
    snapshot["snapshot_projection"] = "Immutable version report; manifest hash omitted to avoid a self-reference."
    write(target / "report.json", snapshot)
    manifest["files"]["report.json"] = sha((target / "report.json").read_bytes())
    write(target / "manifest.json", manifest)
    report["manifest_sha256"] = sha((target / "manifest.json").read_bytes())
    write(root / REPORT, report)
    return report


def build(study, canaries=None, *, root=ROOT, allow_partial=False, bundle=None):
    target = Path(root).resolve() / _bundle(study, bundle)
    if target.exists():
        raise ValueError("public bundle exists; preserve it and use a separately versioned destination")
    try:
        return _build(study, canaries, root=root, allow_partial=allow_partial, bundle=bundle)
    except Exception:
        # Only this invocation's newly created output can be removed.
        if target.exists():
            shutil.rmtree(target)
        raise


def verify_bundle(bundle, expected_manifest_sha256):
    bundle = Path(bundle)
    manifest_bytes = (bundle / "manifest.json").read_bytes()
    if sha(manifest_bytes) != expected_manifest_sha256:
        raise ValueError("public manifest hash mismatch")
    manifest = json.loads(manifest_bytes)
    actual = {p.relative_to(bundle).as_posix(): p for p in bundle.rglob("*") if p.is_file() and p != bundle / "manifest.json"}
    if set(actual) != set(manifest["files"]):
        raise ValueError("public file membership mismatch")
    for name, path in actual.items():
        if path.is_symlink() or not path.resolve().is_relative_to(bundle.resolve()) or sha(path.read_bytes()) != manifest["files"][name]:
            raise ValueError("public file custody mismatch: " + name)
    for name, origin in manifest["originals"].items():
        if origin["published_bytes_sha256"] != manifest["files"][name]:
            raise ValueError("public projection binding mismatch")
        if origin["projection"] == "unchanged" and (
                origin["original_bytes_sha256"] != manifest["files"][name]
                or origin["original_json_sha256"] != digest(read(bundle / name))):
            raise ValueError("unchanged original custody mismatch")
    for path in bundle.rglob("model-content/*.json"):
        projection = read(path)
        if not projection["redacted"] and sha(projection["content"].encode()) != projection["original_content_sha256"]:
            raise ValueError("model content projection custody mismatch")
    if _archive_members(bundle / "runtime-source.zip") != manifest["archive_members"]:
        raise ValueError("archived member custody mismatch")
    if sha((bundle / "runtime-source.zip").read_bytes()) != manifest["source_archive_sha256"]:
        raise ValueError("archived runtime hash mismatch")
    for relative, info in manifest.get("canary_archives", {}).items():
        archive = bundle / relative
        if sha(archive.read_bytes()) != info["sha256"] or _archive_members(archive) != info["members"]:
            raise ValueError("archived canary runtime custody mismatch")
    protocol, data = read(bundle / "protocol.json"), read(bundle / "datasets.json")
    if digest(protocol) != manifest["protocol_sha256"] or digest(data) != manifest["dataset_sha256"]:
        raise ValueError("public protocol/dataset custody mismatch")
    return manifest


SCREEN_MODULES = {
    "zenith_observation_repair_screen_v1": "research.observation_repair_screen",
    "zenith_native_composition_screen_v1": "research.observation_composition_screen",
    "zenith_observation_candidate_pool_v1": "research.observation_candidate_pool_screen",
    "zenith_observation_active_selection_v1": "research.observation_active_selection_screen",
}


def build_screen(study, *, root=ROOT, bundle):
    """Publish a terminal small screen without replacing the V5 comparison receipt."""
    study, root = Path(study).resolve(), Path(root).resolve()
    relative = PurePosixPath(bundle)
    if (len(relative.parts) != 3 or relative.parts[:2] != ("examples", "observation-learning")
            or not re.fullmatch(r"screen-[a-z0-9-]+", relative.parts[2])):
        raise ValueError("screen bundle must be an immutable screen-* sibling")
    target = root / relative
    if target.exists():
        raise ValueError("public bundle exists; preserve the original")
    protocol, data = read(study / "protocol.json"), read(study / "datasets.json")
    if protocol.get("schema") not in SCREEN_MODULES:
        raise ValueError("unsupported screen schema")
    preparation = read(study / "preparation-receipt.json")
    if (preparation["protocol_sha256"] != digest(protocol)
            or protocol["dataset_sha256"] != digest(data)):
        raise ValueError("screen preparation custody mismatch")
    archive = study / "runtime-source.zip"
    if sha(archive.read_bytes()) != protocol["source"]["sha256"]:
        raise ValueError("screen source custody mismatch")
    members = _archive_members(archive)
    result = read(study / "results.json") if (study / "results.json").exists() else None
    if result is None and not (study / "failure.json").exists():
        raise ValueError("screen is not terminal")
    if result is not None:
        frozen = read(study / "all-frozen.json")
        receipt = read(study / "all-frozen-receipt.json")
        if (result["protocol_sha256"] != digest(protocol)
                or result["frozen_sha256"] != digest(frozen)
                or receipt["frozen_sha256"] != digest(frozen)
                or receipt["protocol_sha256"] != digest(protocol)):
            raise ValueError("screen frozen result custody mismatch")
    pool = (data.get("confirmation_actions") if "composition" not in protocol["schema"] else
            [s["confirmation"] for s in data.get("public", {}).get("streams", [])
             if "confirmation" in s])
    if pool:
        bindings = {"protocol_sha256": digest(protocol),
            "frozen_sha256": digest(read(study / "all-frozen.json"))
                if (study / "all-frozen.json").exists() else None,
            "confirmation_pool_sha256": digest(pool)}
        if (study / "confirmation.json").exists():
            selection = read(study / "confirmation-selection.json")
            if (any(selection.get(k) != v for k, v in bindings.items())
                    or read(study / "confirmation.json").get("selection") != selection):
                raise ValueError("confirmation selection custody mismatch")
        elif (study / "confirmation-forfeiture.json").exists():
            forfeiture = read(study / "confirmation-forfeiture.json")
            if (not forfeiture.get("forfeited") or not forfeiture.get("reason")
                    or any(forfeiture.get(k) != v for k, v in bindings.items())):
                raise ValueError("confirmation forfeiture custody mismatch")
        else:
            raise ValueError("sealed confirmation must be completed or explicitly forfeited before publication")
    projection, contents = project_calls(study)
    schema_name = "composition" if "composition" in protocol["schema"] else "observation"
    _verify_delivery(study, projection, schema_name)
    if any(c["status"] == "attempt_started" for c in projection["calls"]):
        raise ValueError("screen still has an unsettled call")
    originals = {}
    try:
        target.mkdir(parents=True)
        names = ("protocol.json", "datasets.json", "preparation-receipt.json", "started.json",
            "all-frozen.json", "all-frozen-receipt.json", "results.json", "failure.json",
            "confirmation-selection.json", "confirmation-forfeiture.json", "confirmation.json")
        sources = [study / name for name in names if (study / name).exists()]
        for pattern in ("world-*-frozen.json", "world-*-partial.json", "target-*-partial.json",
                        "prompts/*.json", "responses/*.json", "probes/*.json"):
            sources.extend(sorted(study.glob(pattern)))
        for source in sources:
            name = source.relative_to(study).as_posix()
            payload, value = source.read_bytes(), read(source)
            if sanitize(value) != value:
                raise ValueError("screen evidence requires redaction; preserve it privately")
            destination = target / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(payload)
            originals[name] = {"original_bytes_sha256": sha(payload),
                "original_json_sha256": digest(value), "published_bytes_sha256": sha(payload),
                "projection": "unchanged"}
        (target / "runtime-source.zip").write_bytes(archive.read_bytes())
        write(target / "calls.json", projection)
        for item in contents:
            write(target / "model-content" / f"{item['call_id']}.json", item)
        report = {"schema": protocol["schema"], "campaign": study.name,
            "bundle": relative.as_posix(), "status": "complete" if result is not None else "failed",
            "model": protocol.get("model"), "provider_slug": protocol.get("provider_slug"),
            "reasoning_effort": protocol.get("reasoning_effort"), "total_calls": len(projection["calls"]),
            "total_reported_cost_usd": projection["reported_cost_usd"],
            "unreported_cost_calls": projection["unknown_cost_calls"],
            "unreported_cost_reservations_usd": projection["unknown_reservations_usd"],
            "aggregate": result["aggregate"] if result else None,
            "confirmation": read(study / "confirmation.json").get("aggregate")
                if (study / "confirmation.json").exists() else None,
            "confirmation_forfeited": (study / "confirmation-forfeiture.json").exists(),
            "boundary": protocol.get("selection_boundary", protocol.get("boundary")),
            "protocol_sha256": digest(protocol), "source_archive_sha256": protocol["source"]["sha256"]}
        if "models" in protocol:
            report["models"] = protocol["models"]
            report["accounting"] = protocol["accounting"]
        write(target / "report.json", report)
        manifest = {"schema": "zenith_screen_public_bundle_v1", "protocol_sha256": digest(protocol),
            "dataset_sha256": digest(data), "source_archive_sha256": protocol["source"]["sha256"],
            "archive_members": members, "originals": originals, "source_transport_excluded": True,
            "files": {p.relative_to(target).as_posix(): sha(p.read_bytes())
                for p in sorted(target.rglob("*")) if p.is_file()}}
        write(target / "manifest.json", manifest)
        report["manifest_sha256"] = sha((target / "manifest.json").read_bytes())
        return report
    except BaseException:
        if target.exists():
            shutil.rmtree(target)
        raise


SCREEN_REPLAY_WORKER = r'''
import importlib,json,os,socket,sys
from pathlib import Path
runtime,bundle=map(Path,sys.argv[1:3])
sys.path.insert(0,str(runtime));os.chdir(runtime)
def no_network(*args,**kwargs):raise RuntimeError("offline replay forbids network access")
class OfflineSocket(socket.socket):
    connect=no_network
    connect_ex=no_network
socket.socket=OfflineSocket;socket.create_connection=no_network;socket.getaddrinfo=no_network
from zenith.providers import digest
from zenith.budgeted import OpenRouterBudgetedProvider
OpenRouterBudgetedProvider.ask_ai=no_network
def read(name):return json.loads((bundle/name).read_text())
p,d=read("protocol.json"),read("datasets.json")
if digest(d)!=p["dataset_sha256"]:raise ValueError("screen dataset/protocol bindings differ")
name={"zenith_native_composition_screen_v1":"research.observation_composition_screen",
      "zenith_observation_repair_screen_v1":"research.observation_repair_screen",
      "zenith_observation_candidate_pool_v1":"research.observation_candidate_pool_screen",
      "zenith_observation_active_selection_v1":"research.observation_active_selection_screen"}[p["schema"]]
m=importlib.import_module(name)
if not (bundle/"results.json").exists():
    print(json.dumps({"terminal_failure_preserved":True,"inference_calls":0}));sys.exit(0)
f=read("all-frozen.json")
receipt=read("all-frozen-receipt.json")
if receipt["protocol_sha256"]!=digest(p) or receipt["frozen_sha256"]!=digest(f):
    raise ValueError("screen frozen receipt bindings differ")
raw={path.name.removesuffix("-raw.json"):json.loads(path.read_text())["content"]
    for path in (bundle/"responses").glob("*-raw.json")}
construction_checks=0
construction_unit="program score comparisons"
if "candidate_pool" in p["schema"] or "active_selection" in p["schema"]:
    prompts={path.stem:json.loads(path.read_text()) for path in (bundle/"prompts").glob("*.json")}
    construction=m.replay_records(p,d,f,raw,prompts)
    construction_checks=construction["construction_checks"]
    construction_unit=construction.get("construction_check_unit","individual development answers")
elif "composition" in p["schema"]:
    construction_checks=m.replay_records(p,d,f,raw)["construction_checks"]
else:
    from research.observation_learning_study import UNKNOWN,development,score,adoption
    from research.observation_world import WorldConfig
    for target,record in zip(d["targets"],f):
        pairs=development(WorldConfig(**target["config"]),target["history"])
        for arm,state in record["arms"].items():
            champion=UNKNOWN if arm=="restart" else target["starting_program"]
            for step,trial in enumerate(state.get("rounds",[])):
                content=raw[target["id"]+"-"+arm+"-"+str(step)]
                failure=trial["response_error"]
                if failure:
                    if content!=failure["raw_content"]:raise ValueError("malformed response changed")
                elif json.loads(content)!=trial["proposal"]:raise ValueError("proposal differs from raw response")
                old=score(champion["source"],pairs);candidate=score(trial["proposal"]["source"],pairs)
                if failure:
                    for row in candidate["rows"]:row["error"]=failure["schema_error"]
                if old!=trial["old"] or candidate!=trial["candidate"]:
                    raise ValueError("repair construction answers/traces/errors differ")
                if adoption(old,candidate)!=(trial["accepted"],trial["regressions"]):
                    raise ValueError("repair selection differs")
                if trial["accepted"]:champion=trial["proposal"]
                construction_checks+=2
            if state.get("rounds") and champion!=state["champion"]:raise ValueError("retained repair differs")
actual=m.audit(p,d,f)
actual={k:v for k,v in actual.items() if k not in ("calls","cost")}
expected={k:v for k,v in read("results.json").items() if k not in ("calls","cost")}
if digest(actual)!=digest(expected):raise ValueError("individual screen answers/traces/errors differ")
confirmation=False
if (bundle/"confirmation-forfeiture.json").exists():
    forfeiture=read("confirmation-forfeiture.json")
    pool=d["confirmation_actions"] if "composition" not in p["schema"] else [s["confirmation"] for s in d["public"]["streams"]]
    bindings={"protocol_sha256":digest(p),"frozen_sha256":digest(f),"confirmation_pool_sha256":digest(pool)}
    if not forfeiture.get("forfeited") or any(forfeiture.get(k)!=v for k,v in bindings.items()):
        raise ValueError("confirmation forfeiture bindings differ")
    if (bundle/"confirmation.json").exists():raise ValueError("forfeited confirmation cannot be claimed")
if (bundle/"confirmation.json").exists():
    saved=read("confirmation.json");selection=read("confirmation-selection.json")
    if "candidate_pool" in p["schema"]:
        m.replay_confirmation(p,d,f,selection,saved)
    elif "composition" not in p["schema"]:
        bindings={"protocol_sha256":digest(p),"frozen_sha256":digest(f),
            "confirmation_pool_sha256":digest(d["confirmation_actions"])}
        if any(selection.get(k)!=v for k,v in bindings.items()):
            raise ValueError("confirmation selection bindings differ")
        arm=selection["arm"]
        if arm not in m.ARMS:raise ValueError("invalid confirmation arm")
        chosen=[{"id":r["id"],"arms":{arm:r["arms"][arm]}} for r in f]
        checked=m.audit(p,d,chosen,"confirmation");checked["selection"]=selection
        if digest(checked)!=digest(saved):raise ValueError("confirmation individual results differ")
    else:
        if not hasattr(m,"replay_confirmation"):raise ValueError("composition confirmation needs original replay")
        m.replay_confirmation(p,d,f,selection,saved)
    confirmation=True
print(json.dumps({"exact_individual_screen_replay":True,"confirmation_replayed":confirmation,
    "construction_checks":construction_checks,
    "construction_check_unit":construction_unit,
    "worlds":len(f),"inference_calls":0}))
'''


def replay_screen(bundle, *, expected_manifest_sha256=None, timeout=600):
    bundle = Path(bundle).resolve()
    manifest = verify_bundle(bundle, expected_manifest_sha256 or sha((bundle / "manifest.json").read_bytes()))
    if read(bundle / "protocol.json").get("schema") not in SCREEN_MODULES:
        raise ValueError("unsupported screen schema")
    with tempfile.TemporaryDirectory(prefix="zenith-screen-replay-") as directory:
        runtime = Path(directory) / "runtime"
        runtime.mkdir()
        with ZipFile(bundle / "runtime-source.zip") as archive:
            archive.extractall(runtime)
        result = _offline_worker(SCREEN_REPLAY_WORKER, runtime, bundle, timeout)
    return {**result, "public_files_verified": len(manifest["files"]),
            "archive_members_verified": len(manifest["archive_members"])}


REPLAY_WORKER = r'''
import hashlib,json,os,socket,sys
from pathlib import Path
runtime,bundle=map(Path,sys.argv[1:3])
sys.path.insert(0,str(runtime))
os.chdir(runtime)
def no_network(*args,**kwargs):raise RuntimeError("offline replay forbids network access")
class OfflineSocket(socket.socket):
    connect=no_network
    connect_ex=no_network
socket.socket=OfflineSocket
socket.create_connection=no_network
socket.getaddrinfo=no_network
from research.observation_learning_study import audit,adoption,development,score,UNKNOWN,PROGRAM_SCHEMA
from jsonschema import ValidationError,validate
from zenith.budgeted import OpenRouterBudgetedProvider
OpenRouterBudgetedProvider.ask_ai=no_network
from research.observation_world import WorldConfig,compatible
from zenith.providers import digest
def read(name):return json.loads((bundle/name).read_text())
protocol,data=read("protocol.json"),read("datasets.json")
if (bundle/"all-frozen.json").exists():frozen=read("all-frozen.json")
else:frozen=[json.loads(p.read_text()) for p in sorted(bundle.glob("world-*-frozen.json"))]
frozen_ids={r["source_id"] for r in frozen}
partial=[json.loads(p.read_text()) for p in sorted(bundle.glob("world-*-partial.json"))
         if json.loads(p.read_text())["source_id"] not in frozen_ids]
records=frozen+partial
checks=[]
for record in records:
    cfg=WorldConfig(**data["private"]["configs"][record["source_id"]])
    compatible(cfg,record["history"])  # Re-execute measured native observations without protected queries.
    for arm,state in record["arms"].items():
        champion=dict(UNKNOWN)
        for number,entry in enumerate(state["rounds"]):
            total=entry["old"]["total"]
            if total%3 or total>len(record["history"])*3:raise ValueError("invalid construction evidence prefix")
            pairs=development(cfg,record["history"][:total//3])
            if digest(champion)!=entry["parent_sha256"]:raise ValueError("construction parent custody mismatch")
            replayed={}
            for stage,program in (("old",champion),("candidate",entry["proposal"])):
                actual=score(program["source"],pairs)
                response_error=entry.get("response_error") if stage=="candidate" else None
                if response_error is not None:
                    try:
                        response=json.loads(response_error["raw_content"])
                        validate(response,PROGRAM_SCHEMA)
                    except (ValueError,ValidationError) as error:
                        error_text=f"{type(error).__name__}: {error}"
                    else:raise ValueError("recorded schema failure now validates")
                    if error_text!=response_error["schema_error"]:raise ValueError("raw response schema error mismatch")
                    for row in actual["rows"]:row["error"]=error_text
                if actual!=entry[stage]:raise ValueError("construction individual answer/trace/error mismatch")
                replayed[stage]=actual
                checks.append({"source_id":record["source_id"],"arm":arm,"round":number,"stage":stage,
                               "correct":actual["correct"],"total":actual["total"]})
            if adoption(replayed["old"],replayed["candidate"])!=(entry["accepted"],entry["regressions"]):
                raise ValueError("original adoption decision differs from frozen procedure")
            if entry["accepted"]:champion=entry["proposal"]
        if champion!=state["champion"]:raise ValueError("final champion differs from accepted trajectory")
complete=(bundle/"results.json").exists()
if complete:
    actual=audit(bundle,protocol,data,frozen)
    original={k:v for k,v in read("results.json").items() if k not in ("cost","calls")}
    if actual!=original:raise ValueError("protected individual answer/trace/error or summary mismatch")
print(json.dumps({"ok":True,"complete":complete,"frozen_worlds":len(frozen),"partial_worlds":len(partial),
                  "construction_checks":checks,"protected_replayed":complete,"inference_calls":0,
                  "runtime_root":str(runtime),"portability":"original absolute source path never resolved"}))
'''


CANARY_REPLAY_WORKER = r'''
import json,os,socket,sys
from pathlib import Path
runtime,bundle=map(Path,sys.argv[1:3])
sys.path.insert(0,str(runtime))
os.chdir(runtime)
def no_network(*args,**kwargs):raise RuntimeError("offline replay forbids network access")
class OfflineSocket(socket.socket):
    connect=no_network
    connect_ex=no_network
socket.socket=OfflineSocket
socket.create_connection=no_network
socket.getaddrinfo=no_network
from zenith.investigation_program import execute
from jsonschema import validate
def read(name):return json.loads((bundle/name).read_text())
protocol,result=read("protocol.json"),read("result.json")
raw=read("raw-response.json")
text=raw.get("text",raw.get("content"))
try:
    response=json.loads(text)
    validate(response,protocol["schema"])
    rows=execute(response["source"],[{"id":"canary","tables":protocol["fixture"]["tables"]}])
except Exception as error:
    actual=f"{type(error).__name__}: {error}"
    if result.get("ok") or actual!=result.get("error"):
        raise ValueError("canary original execution error mismatch")
    check={"ok":False,"error":actual}
else:
    if rows!=result.get("rows") or ((bundle/"execution.json").exists() and rows!=read("execution.json")):
        raise ValueError("canary original individual answer/trace/error mismatch")
    expected=protocol["fixture"]["expected"]
    succeeded=all(row["error"] is None and row["answer"]==expected for row in rows)
    if succeeded!=result["ok"]:raise ValueError("canary recorded success differs from fixture result")
    check={"ok":succeeded,"rows":rows}
print(json.dumps({"id":bundle.name,"original_execution_matched":True,**check,"inference_calls":0}))
'''


def _offline_worker(worker, runtime, bundle, timeout):
    process = subprocess.run([sys.executable, "-I", "-c", worker, str(runtime), str(bundle)],
        cwd=runtime, env={"PYTHONDONTWRITEBYTECODE": "1", "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"},
        text=True, capture_output=True, timeout=timeout)
    if process.returncode:
        raise ValueError("archived offline replay failed: " + sanitize(process.stderr[-2000:], error=True))
    return json.loads(process.stdout)


def replay(*, root=ROOT, timeout=300, bundle=None):
    root = Path(root).resolve()
    report = read(root / REPORT)
    relative = PurePosixPath(bundle or report["bundle"])
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("unsafe public bundle path")
    bundle = (root / relative).resolve()
    expected_manifest = report["manifest_sha256"] if relative.as_posix() == report["bundle"] else sha((bundle / "manifest.json").read_bytes())
    manifest = verify_bundle(bundle, expected_manifest)
    with tempfile.TemporaryDirectory(prefix="zenith-observation-replay-") as directory:
        runtime = Path(directory) / "runtime"
        runtime.mkdir()
        with ZipFile(bundle / "runtime-source.zip") as archive:
            archive.extractall(runtime)  # Member paths and symlinks already independently checked.
        result = _offline_worker(REPLAY_WORKER, runtime, bundle, timeout)
        canary_checks = []
        for index, relative in enumerate(manifest.get("canary_archives", {})):
            archive_path = bundle / relative
            canary = archive_path.parent
            if not (canary / "raw-response.json").exists():
                continue  # Failed transport has no model program to execute.
            canary_runtime = Path(directory) / f"canary-{index}"
            canary_runtime.mkdir()
            with ZipFile(archive_path) as archive:
                archive.extractall(canary_runtime)
            canary_checks.append(_offline_worker(CANARY_REPLAY_WORKER, canary_runtime, canary, timeout))
        result["canary_execution_checks"] = canary_checks
    result.pop("runtime_root", None)
    result.update(public_files_verified=len(manifest["files"]), archive_members_verified=len(manifest["archive_members"]))
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("build", "replay", "build-screen", "replay-screen"))
    parser.add_argument("--study", type=Path, default=ROOT / "work/observation-learning-20261013-v1")
    parser.add_argument("--canary", action="append", type=Path)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--bundle", help="Immutable version sibling, for example examples/observation-learning/v2")
    parser.add_argument("--allow-partial", action="store_true")
    args = parser.parse_args()
    if args.command in ("build-screen", "replay-screen") and not args.bundle:
        parser.error("screen commands require --bundle")
    if args.command == "build-screen":
        result = build_screen(args.study, root=args.root, bundle=args.bundle)
    elif args.command == "replay-screen":
        result = replay_screen(args.root / args.bundle)
    elif args.command == "build":
        result = build(args.study, args.canary, root=args.root, allow_partial=args.allow_partial, bundle=args.bundle)
    else:
        result = replay(root=args.root, bundle=args.bundle)
    print(json.dumps(result if args.command.startswith("replay") else {k: result[k] for k in ("status", "total_calls", "total_reported_cost_usd", "unreported_cost_calls")}, indent=2))
