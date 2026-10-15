"""Custody, privacy and archived individual-output replay for public evidence."""
from decimal import Decimal
import json
from pathlib import Path
import shutil
from zipfile import ZipFile

import pytest

from research.observation_learning_study import prepare, run
from scripts.build_observation_report import (
    BUNDLE, REPORT, _archive_members, build, digest, project_calls, read,
    replay, sanitize, sha, verify_bundle, write,
)


def test_small_screen_portable_replay_and_custody(tmp_path):
    from dataclasses import asdict
    from research.investigator_study import archive_runtime
    from research.observation_learning_study import UNKNOWN
    from research.observation_repair_screen import VERSION, audit
    from research.observation_world import world, observe
    from scripts.build_observation_report import build_screen, replay_screen
    study = tmp_path / "private-screen"
    study.mkdir()
    config = world(73)
    data = {"targets": [{"id": "fixture", "source_id": config.source_id,
        "config": asdict(config), "starting_program": UNKNOWN,
        "history": [observe(config, [])]}], "screen_actions": [[]], "confirmation_actions": [[]]}
    protocol = {"schema": VERSION, "model": "fixture", "provider_slug": "fixture",
        "reasoning_effort": "none", "dataset_sha256": digest(data),
        "source": archive_runtime(study), "selection_boundary": "Offline publication fixture."}
    frozen = [{"id": "fixture", "arms": {"generic": {"champion": UNKNOWN, "rounds": []}}}]
    for name, value in {"protocol.json": protocol, "datasets.json": data,
        "all-frozen.json": frozen, "results.json": audit(protocol, data, frozen),
        "preparation-receipt.json": {"protocol_sha256": digest(protocol)},
        "all-frozen-receipt.json": {"protocol_sha256": digest(protocol), "frozen_sha256": digest(frozen)}}.items():
        write(study / name, value)
    root = tmp_path / "public"
    bundle = "examples/observation-learning/screen-fixture"
    with pytest.raises(ValueError, match="sealed confirmation"):
        build_screen(study, root=root, bundle=bundle)
    assert not (root / bundle).exists()
    write(study / "confirmation-forfeiture.json", {"forfeited": True,
        "reason": "Offline fixture deliberately ends without confirmation.",
        "protocol_sha256": digest(protocol), "frozen_sha256": digest(frozen),
        "confirmation_pool_sha256": digest(data["confirmation_actions"])})
    report = build_screen(study, root=root, bundle=bundle)
    assert report["total_calls"] == 0
    assert not (root / REPORT).exists()  # Never overwrite the original comparison.
    shutil.rmtree(study)  # Replay cannot depend on original absolute paths.
    result = replay_screen(root / bundle, expected_manifest_sha256=report["manifest_sha256"])
    assert result["exact_individual_screen_replay"] and result["inference_calls"] == 0
    manifest = read(root / bundle / "manifest.json")
    payload = root / bundle / "all-frozen.json"
    changed = read(payload)
    changed[0]["arms"]["generic"]["champion"]["source"] = "def investigate(context, acquire):\n    return 4"
    write(payload, changed)
    # Rebinding a public file hash cannot conceal a changed executable result.
    manifest["files"]["all-frozen.json"] = sha(payload.read_bytes())
    origin = manifest["originals"]["all-frozen.json"]
    origin.update(original_bytes_sha256=sha(payload.read_bytes()), published_bytes_sha256=sha(payload.read_bytes()),
                  original_json_sha256=digest(changed))
    write(root / bundle / "manifest.json", manifest)
    with pytest.raises(ValueError, match="replay failed"):
        replay_screen(root / bundle)


def test_zero_inference_active_screen_replays_after_private_records_are_removed(tmp_path):
    from dataclasses import asdict
    from research import observation_active_selection_screen as active
    from research.investigator_study import archive_runtime
    from research.observation_learning_study import UNKNOWN
    from research.observation_world import world, observe
    from scripts.build_observation_report import build_screen, replay_screen
    study = tmp_path / "active"
    study.mkdir()
    config = world(73)
    slots = [{"slot_id": "fixture", "proposal": UNKNOWN, "response_error": None}]
    data = {"targets": [{"id": "fixture", "source_id": config.source_id,
        "config": asdict(config), "history": [observe(config, [])],
        "inventory": slots, "historical_inventory": slots}],
        "probe_actions": [[], [{"op": "put", "key": "a", "value": 1}]],
        "final_actions": [[{"op": "put", "key": "b", "value": 2}]]}
    protocol = {"schema": active.VERSION, "probe_budget": 2,
        "dataset_sha256": digest(data), "source": archive_runtime(study)}
    frozen, measured = active.construct(protocol, data, record_round=lambda target, policy, step, row:
        write(study / "probes" / f"{target}-{policy}-{step}.json", row))
    assert measured == 4
    for name, value in {"protocol.json": protocol, "datasets.json": data,
        "all-frozen.json": frozen, "results.json": active.audit(protocol, data, frozen),
        "preparation-receipt.json": {"protocol_sha256": digest(protocol)},
        "all-frozen-receipt.json": {"protocol_sha256": digest(protocol), "frozen_sha256": digest(frozen)}}.items():
        write(study / name, value)
    root = tmp_path / "public"
    bundle = "examples/observation-learning/screen-active-fixture"
    report = build_screen(study, root=root, bundle=bundle)
    assert report["total_calls"] == 0 and report["aggregate"]["fixed_initial"]["total"] == 3
    assert len(list((root / bundle / "probes").glob("*.json"))) == 4
    shutil.rmtree(study)
    replayed = replay_screen(root / bundle)
    assert replayed["exact_individual_screen_replay"] and replayed["inference_calls"] == 0
    assert replayed["construction_check_unit"] == "individual unlabelled candidate query predictions"

LOOKUP = '''def investigate(context, acquire):
    for receipt in acquire("history"):
        if receipt["actions"] == context["actions"]:
            return {"value": receipt["observed"][context["goal"]], "unresolved": False}
    return {"value": None, "unresolved": True}
'''


class FixtureProvider:
    def __init__(self):
        self.entries = {}

    def ask_ai(self, prompt, config, **kwargs):
        node = config["meta"]["node_id"]
        if "probes" in node:
            answer = {"experiments": [[], [{"op": "put", "key": "a", "value": 3, "connection": "main"}],
                                      [{"op": "put", "key": "a", "value": 4, "connection": "other"}]],
                      "purpose": "fixture; no model learning"}
            content = json.dumps(answer)
        elif node.endswith("incremental-0-0"):
            content = '{"source":'  # Actual malformed content must survive publication.
        else:
            content = json.dumps({"source": LOOKUP, "scope": "Observed lookup only.", "lesson": "fixture"})
        call_id = digest([node, prompt])
        self.entries[call_id] = {"call_id": call_id, "run_id": "fixture", "node_id": node,
            "status": "response_supplied", "cost": "0.001", "reserved_cost_usd": "0.01",
            "requested_model": "fixture", "reasoning_effort": "low", "response_sha256": sha(content.encode()),
            "inference_mode": "bounded", "queue_elapsed_seconds": 0.1, "network_elapsed_seconds": 0.2,
            "global_inference_limit": 3, "provider_route_limit": 1, "provider_route_sha256": "a" * 64,
            "catalogue_pricing": {"prompt": "1.4E-7", "completion": "4.2E-7"},
            "prompt_sha256": sha(prompt.encode()),
            "private_headers": {"Authorization": "Bearer sk-or-v1-transport-secret-000000000000000000"},
            "provider_response": {"model": "actual-fixture", "usage": {"prompt_tokens": 20, "completion_tokens": 30,
                "completion_tokens_details": {"reasoning_tokens": 12}, "cost": 0.001},
                "private_transport": "must not be exported",
                "choices": [{"finish_reason": "stop", "message": {"content": content}}]}}
        return content


def ledger(path, entries):
    write(path / "budget/budget.json", {"entries": entries,
        "total_reported_cost_usd": str(sum((Decimal(e["cost"]) for e in entries.values() if e["cost"] is not None), Decimal(0))),
        "total_reserved_usd": str(sum((Decimal(e["reserved_cost_usd"]) for e in entries.values()), Decimal(0))),
        "halted": any(e["status"] == "failed" for e in entries.values())})


@pytest.fixture(scope="module")
def completed(tmp_path_factory):
    root = tmp_path_factory.mktemp("observation-public-fixture")
    study = root / "study"
    prepare(study, "fixture", "fixture", worlds=1)
    provider = FixtureProvider()
    run(study, provider=provider)
    ledger(study, provider.entries)
    canaries = []
    for number, name in enumerate(("qwen", "qwen-funded", "deepseek"), 1):
        canary = root / f"canary-{name}"
        canary.mkdir()
        write(canary / "protocol.json", {"model": "fixture", "prompt": "Return one JSON object", "schema": {"type": "object"}})
        call_id = str(number) * 64
        content = '{"source": "internal"}' if number == 2 else '{"source":"fixture"}'
        entry = {"call_id": call_id, "node_id": "canary", "status": "failed" if number == 1 else "response_supplied",
                 "cost": None if number == 1 else "0.002" if number == 2 else "0.003", "reserved_cost_usd": "0.01"}
        if number == 1:
            error = "HTTP 402 visit https://provider.example/keys/private-identifier and https://provider.example/help"
            entry["error"] = error
            write(canary / "result.json", {"ok": False, "error": error})
        else:
            entry["response_sha256"] = sha(content.encode())
            entry["provider_response"] = {"usage": {"completion_tokens": 7, "completion_tokens_details": {"reasoning_tokens": 2}},
                "choices": [{"finish_reason": "stop", "message": {"content": content}}]}
            write(canary / "raw-response.json", {"content": content})
            write(canary / "response.json", json.loads(content))
            write(canary / "result.json", {"ok": number == 3, "error": None if number == 3 else "non-executable model source"})
        ledger(canary, {call_id: entry})
        canaries.append(canary)
    return study, canaries


def test_full_report_retains_failed_canaries_and_reasoning_tokens(completed, tmp_path):
    study, canaries = completed
    report = build(study, canaries, root=tmp_path)
    assert report["complete"] and report["total_calls"] == 24
    assert report["unreported_cost_calls"] == 1
    assert report["cost_bounds_usd"] == ["0.026", "0.036"]
    assert len(report["per_world"]) == 1
    assert "freeze_and_grow" in report["aggregate"]
    assert report["canaries"][0]["result"]["ok"] is False
    assert "https://" not in report["canaries"][0]["result"]["error"]
    assert report["campaign_calls"]["calls"][0]["usage"]["completion_tokens_details"]["reasoning_tokens"] == 12
    assert report["campaign_calls"]["calls"][0]["actual_model"] == "actual-fixture"
    assert report["campaign_calls"]["calls"][0]["queue_elapsed_seconds"] == 0.1
    assert report["campaign_calls"]["calls"][0]["catalogue_pricing"]["prompt"] == "1.4E-7"
    manifest = verify_bundle(tmp_path / BUNDLE, report["manifest_sha256"])
    assert manifest["complete"] and manifest["source_transport_excluded"]
    assert read(tmp_path / BUNDLE / "report.json")["total_calls"] == report["total_calls"]
    text = "\n".join(p.read_text() for p in (tmp_path / BUNDLE).rglob("*.json"))
    assert "transport-secret" not in text and "private_headers" not in text and "private_transport" not in text
    contents = [read(p)["content"] for p in (tmp_path / BUNDLE / "model-content").glob("*.json")]
    assert '{"source":' in contents
    assert (tmp_path / BUNDLE / "responses/world-00-incremental-0-0-invalid.json").exists()
    assert (tmp_path / BUNDLE / "prompts/world-00-incremental-0-0.json").exists()


def test_replay_uses_archived_code_without_original_absolute_path(completed, tmp_path):
    study, canaries = completed
    copied = tmp_path / "input"
    shutil.copytree(study, copied)
    protocol = read(copied / "protocol.json")
    protocol["source"]["path"] = "/this/original/private/path/does/not/exist.zip"
    write(copied / "protocol.json", protocol)
    for name in ("started.json", "preparation-receipt.json", "results.json"):
        if not (copied / name).exists():
            continue
        value = read(copied / name)
        value["protocol_sha256"] = digest(protocol)
        write(copied / name, value)
    publication = tmp_path / "publication"
    report = build(copied, canaries, root=publication)
    # Later live files at the publication checkout must not enter the replay.
    (publication / "zenith").mkdir()
    (publication / "zenith/web_content.py").write_text("raise RuntimeError('live runtime must not be imported')\n")
    (publication / "research").mkdir()
    (publication / "research/observation_world.py").write_text("raise RuntimeError('live world must not be imported')\n")
    shutil.rmtree(copied)
    replayed = replay(root=publication)
    assert replayed["ok"] and replayed["inference_calls"] == 0
    assert replayed["protected_replayed"] and len(replayed["construction_checks"]) == 36
    assert replayed["archive_members_verified"] > 4
    assert read(publication / REPORT)["manifest_sha256"] == report["manifest_sha256"]


def test_hash_and_membership_tampering_fails_before_execution(completed, tmp_path):
    study, canaries = completed
    report = build(study, canaries, root=tmp_path)
    bundle = tmp_path / BUNDLE
    (bundle / "datasets.json").write_text("{}\n")
    with pytest.raises(ValueError, match="custody mismatch"):
        verify_bundle(bundle, report["manifest_sha256"])


def test_individual_traces_are_checked_even_when_headline_scores_unchanged(completed, tmp_path):
    study, canaries = completed
    build(study, canaries, root=tmp_path)
    bundle = tmp_path / BUNDLE
    value = read(bundle / "results.json")
    value["worlds"][0]["incremental"]["rows"][0]["trace"].append({"table": "history", "rows": 999, "sha256": "wrong"})
    write(bundle / "results.json", value)
    # Deliberately rebind fixture hashes: algorithmic replay must still detect the changed trace.
    manifest = read(bundle / "manifest.json")
    changed = sha((bundle / "results.json").read_bytes())
    manifest["files"]["results.json"] = changed
    manifest["originals"]["results.json"].update(original_bytes_sha256=changed,
        published_bytes_sha256=changed, original_json_sha256=digest(value))
    write(bundle / "manifest.json", manifest)
    report = read(tmp_path / REPORT)
    report["manifest_sha256"] = sha((bundle / "manifest.json").read_bytes())
    write(tmp_path / REPORT, report)
    with pytest.raises(ValueError, match="individual answer/trace/error"):
        replay(root=tmp_path)


def test_partial_failures_publish_no_fabricated_protected_score(completed, tmp_path):
    study, canaries = completed
    partial = tmp_path / "input"
    shutil.copytree(study, partial)
    (partial / "results.json").unlink()
    (partial / "all-frozen.json").unlink()
    write(partial / "failure.json", {"error": "failed at https://provider.example/keys/private-key", "completed_worlds": 1,
                                     "protected_evaluation_performed": False, "automatic_retry": False})
    report = build(partial, canaries, root=tmp_path / "public")
    assert report["status"] == "failed" and not report["complete"]
    assert report["aggregate"] is None and report["comparisons"] is None and report["per_world"] == []
    assert report["failure"]["automatic_retry"] is False
    assert "https://" not in report["failure"]["error"]


def test_active_campaign_requires_explicit_snapshot_mode(completed, tmp_path):
    study, _ = completed
    active = tmp_path / "input"
    shutil.copytree(study, active)
    (active / "results.json").unlink()
    (active / "all-frozen.json").unlink()
    with pytest.raises(ValueError, match="active"):
        build(active, [], root=tmp_path / "default")
    report = build(active, [], root=tmp_path / "snapshot", allow_partial=True)
    assert report["status"] == "partial_snapshot" and report["aggregate"] is None


def test_interrupted_campaign_retains_and_replays_partial_programs(completed, tmp_path):
    study, canaries = completed
    interrupted = tmp_path / "observation-learning-20261013-v2"
    shutil.copytree(study, interrupted)
    for name in ("results.json", "all-frozen.json", "all-frozen-receipt.json", "world-00-frozen.json"):
        (interrupted / name).unlink(missing_ok=True)
    write(interrupted / "interruption.json", {"protocol_sha256": digest(read(interrupted / "protocol.json")),
        "reason": "fixture stopped cleanly", "attempts": 21, "reported_cost_usd": "0.021",
        "completed_worlds": 0, "stopped_between_provider_calls": True,
        "protected_evaluation_performed": False, "automatic_retry": False})
    publication = tmp_path / "public"
    report = build(interrupted, canaries, root=publication)
    assert report["status"] == "interrupted" and report["frozen_worlds"] == 0
    assert not report["complete"] and not report["protected_evaluation_performed"]
    assert report["bundle"].endswith("/v2") and report["aggregate"] is None
    assert len(report["world_model_bindings"]) == 1
    replayed = replay(root=publication)
    assert replayed["partial_worlds"] == 1 and replayed["frozen_worlds"] == 0
    assert len(replayed["construction_checks"]) == 36 and not replayed["protected_replayed"]


def test_original_dataset_custody_failure_is_not_published(completed, tmp_path):
    study, _ = completed
    copied = tmp_path / "input"
    shutil.copytree(study, copied)
    write(copied / "datasets.json", {"wrong": "input"})
    with pytest.raises(ValueError, match="dataset custody"):
        build(copied, [], root=tmp_path / "public")
    assert not (tmp_path / "public" / BUNDLE).exists()


def test_partial_receipts_replay_against_actual_native_source(completed, tmp_path):
    from research.observation_learning_study import UNKNOWN
    study, _ = completed
    partial = tmp_path / "input"
    shutil.copytree(study, partial)
    for name in ("results.json", "all-frozen.json", "all-frozen-receipt.json", "world-00-frozen.json"):
        (partial / name).unlink(missing_ok=True)
    record = read(study / "world-00-frozen.json")
    for state in record["arms"].values():
        state.update(rounds=[], checkpoints=[], champion=UNKNOWN)
    receipt = record["history"][0]
    receipt["observed"]["channel"] += 1
    unsigned = {k: v for k, v in receipt.items() if k != "receipt_sha256"}
    receipt["receipt_sha256"] = digest(unsigned)
    write(partial / "world-00-partial.json", record)
    write(partial / "failure.json", {"error": "fixture stopped", "protected_evaluation_performed": False})
    publication = tmp_path / "public"
    build(partial, [], root=publication)
    with pytest.raises(ValueError, match="history does not match the actual native source"):
        replay(root=publication)


def test_actual_prompt_delivery_hash_is_checked(completed, tmp_path):
    study, _ = completed
    copied = tmp_path / "input"
    shutil.copytree(study, copied)
    prompt = next((copied / "prompts").glob("*.json"))
    value = read(prompt)
    value["prompt"]["request"] = "changed after delivery"
    write(prompt, value)
    with pytest.raises(ValueError, match="prompt delivery custody"):
        build(copied, [], root=tmp_path / "public")
    assert not (tmp_path / "public" / BUNDLE).exists()


def test_projection_does_not_invent_cost_for_failed_attempt(completed):
    _, canaries = completed
    calls, contents = project_calls(canaries[0])
    assert calls["reported_cost_usd"] == "0" and calls["unknown_reservations_usd"] == "0.01"
    assert calls["calls"][0]["cost"] is None and not contents
    assert len(calls["calls"][0]["original_error_sha256"]) == 64


def test_recursive_per_world_attempt_custody_and_mixed_routes(completed, tmp_path):
    study, _ = completed
    copied = tmp_path / "input"
    shutil.copytree(study, copied)
    entries = read(copied / "budget/budget.json")["entries"]
    for index, (call_id, entry) in enumerate(entries.items()):
        write(copied / f"provider-world-{index % 3:02d}/handoff/api_calls/openrouter_budgeted/{call_id}.json", entry)
    projected, _ = project_calls(copied)
    assert all(c["private_attempt_record"]["matches_ledger"] for c in projected["calls"])
    protocol = read(copied / "protocol.json")
    protocol["provider_slugs"] = ["one", "two", "three"]
    protocol["world_providers"] = ["two"]
    protocol["workers"] = 3
    protocol["inference_mode"] = "bounded"
    write(copied / "protocol.json", protocol)
    for name in ("started.json", "preparation-receipt.json", "results.json", "all-frozen-receipt.json"):
        if (copied / name).exists():
            value = read(copied / name)
            value["protocol_sha256"] = digest(protocol)
            write(copied / name, value)
    report = build(copied, [], root=tmp_path / "public")
    assert report["provider_slug"] == "mixed"
    assert report["world_model_bindings"][0]["provider_slug"] == "two"
    assert report["workers"] == 3


def test_version_two_collects_every_new_route_canary(completed, tmp_path):
    study, canaries = completed
    work = tmp_path / "work"
    work.mkdir()
    copied = work / "observation-learning-20261013-v2"
    shutil.copytree(study, copied)
    for index in range(3):
        shutil.copytree(canaries[index], work / f"openrouter-route-canary-20261013-route-{index}")
    report = build(copied, root=tmp_path / "public")
    assert report["bundle"].endswith("/v2")
    assert len(report["canaries"]) == 3
    assert {c["id"] for c in report["canaries"]} == {f"openrouter-route-canary-20261013-route-{i}" for i in range(3)}


def test_archived_canaries_replay_original_success_and_syntax_failure(completed, tmp_path):
    from zenith.investigation_program import execute
    study, _ = completed
    canaries = []
    for index, source in enumerate((
            'def investigate(context, acquire):\n    events = acquire("events")\n    return {"findings": [], "unresolved": [], "ratio": sum(row["work"] for row in events)}',
            "Return prose instead of an executable function")):
        canary = tmp_path / f"canary-{index}"
        canary.mkdir()
        shutil.copyfile(study / "runtime-source.zip", canary / "runtime-source.zip")
        fixture = {"tables": {"events": [{"event_id": "a", "work": 2}]},
                   "expected": {"findings": [], "unresolved": [], "ratio": 2}}
        protocol = {"prompt": {"request": "fixture canary"}, "schema": {"type": "object"},
                    "fixture": fixture, "runtime_source": {"sha256": sha((canary / "runtime-source.zip").read_bytes())}}
        write(canary / "protocol.json", protocol)
        response = {"source": source, "scope": "fixture", "lesson": "fixture"}
        text = json.dumps(response)
        write(canary / "raw-response.json", {"text": text})
        write(canary / "response.json", response)
        call_id = str(index + 1) * 64
        ledger(canary, {call_id: {"call_id": call_id, "node_id": "canary", "status": "response_supplied",
            "cost": "0.001", "reserved_cost_usd": "0.01", "response_sha256": sha(text.encode()),
            "prompt_sha256": sha(json.dumps(protocol["prompt"], ensure_ascii=False).encode()),
            "provider_response": {"choices": [{"message": {"content": text}}]}}})
        try:
            rows = execute(source, [{"id": "canary", "tables": fixture["tables"]}])
        except Exception as error:
            result = {"ok": False, "error": f"{type(error).__name__}: {error}"}
        else:
            write(canary / "execution.json", rows)
            result = {"ok": True, "rows": rows}
        write(canary / "result.json", {"protocol_sha256": digest(protocol), **result})
        canaries.append(canary)
    publication = tmp_path / "public"
    build(study, canaries, root=publication)
    checks = replay(root=publication)["canary_execution_checks"]
    assert len(checks) == 2 and [c["ok"] for c in checks] == [True, False]
    assert all(c["original_execution_matched"] and c["inference_calls"] == 0 for c in checks)
    # Rebinding a counterfeit original error cannot fool execution replay.
    bundle = publication / BUNDLE
    relative = "canaries/canary-1/result.json"
    original = read(bundle / relative)
    original["error"] = "SyntaxError: different error"
    write(bundle / relative, original)
    manifest = read(bundle / "manifest.json")
    changed = sha((bundle / relative).read_bytes())
    manifest["files"][relative] = changed
    manifest["originals"][relative].update(original_bytes_sha256=changed,
        published_bytes_sha256=changed, original_json_sha256=digest(original))
    write(bundle / "manifest.json", manifest)
    report = read(publication / REPORT)
    report["manifest_sha256"] = sha((bundle / "manifest.json").read_bytes())
    write(publication / REPORT, report)
    with pytest.raises(ValueError, match="canary original execution error mismatch"):
        replay(root=publication)


def test_unsafe_source_archive_is_rejected_before_extraction(tmp_path):
    path = tmp_path / "unsafe.zip"
    with ZipFile(path, "w") as archive:
        archive.writestr("../escape.py", "raise RuntimeError('not allowed')")
    with pytest.raises(ValueError, match="unsafe"):
        _archive_members(path)


def test_error_redaction_and_public_reference_urls_have_distinct_rules():
    value = {"error": "see https://api.example/keys/id?token=secret and https://api.example/help",
             "source": "https://sqlite.org/c3ref/changes.html"}
    projected = sanitize(value)
    assert "https://" not in projected["error"]
    assert projected["source"] == value["source"]
