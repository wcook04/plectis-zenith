"""Original graph/engine regression tests; all system observations are synthetic."""
from __future__ import annotations

import copy
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from zenith import runtime
from zenith.providers import CapturedProvider, OpenRouterFreeProvider, digest, text_digest, write_json
from system.lib.schema_validator import validate_cp1, validate_cp2

ROOT = Path(__file__).resolve().parents[1]
ANCHOR = "2026-03-04T14:30:00+00:00"
HORIZON = "2026-03-05T21:00:00+00:00"


def fixture_root(root: Path) -> Path:
    shutil.copytree(ROOT / "codex", root / "codex")
    write_json(root / "master_config.json", {"paths": {"runs_dir": "state/runs"}, "execution": {"max_workers": 8}})
    source = root / "state/runs/SYNTHETIC_FEEDS"
    write_json(source / "runtime_context.json", {"as_of": ANCHOR, "time_anchor": ANCHOR, "subject_group": "feeds"})
    graph = runtime.load_graph(root)
    for node in graph.values():
        if not node.meta.get("is_feed"):
            continue
        if node.id in ("global_measurements_feed", "global_subsystems_feed"):
            target_id = "SIGNAL_A" if node.id == "global_measurements_feed" else "SUBSYSTEM_A"
            data = {"columns": ["target_id", "Value"], "rows": [[target_id, 100.0]],
                    "evidence_dictionary": [{"ledger_id": "S_ABCD0001", "subject": "SIGNAL_A"}]}
        elif node.id == "global_environment_feed":
            data = {"columns": ["target_id", "Proxy", "pct_change", "z_score"], "rows": [["DGS10", 4.0, 0.1, 0.2]]}
        else:
            data = {"items": [], "synthetic_fixture": True}
        write_json(source / "artifacts" / (node.id + ".json"), {
            "id": node.id, "status": "success", "metadata": {"status": "success", "as_of": ANCHOR,
            "timestamp_iso": ANCHOR, "synthetic_fixture": True}, "data": data})
    return source


def cp1() -> dict:
    # Test grammar only: this repeated prose is explicitly not a research example.
    return {"evidence_dictionary": [{"ref_id": "[1]", "ledger_id": "S_ABCD0001", "subject": "SIGNAL_A",
                                      "signal_summary": "Synthetic fixture value anchor."}],
            "epicentre_thesis": "[1] " + "Synthetic fixture transmission persists unless value drops below the declared baseline. " * 20}


def response_for(node_id: str) -> str:
    if node_id == "lab_decide":
        return json.dumps(cp1())
    if node_id == "lab_director":
        payload = cp1()
        payload["predictions_t"] = [{"target_id": "SIGNAL_A", "direction": "UP", "unit": "dimensionless", "snapshot_value": 100.0,
                                     "target_value": 105.0, "invalidation": "SIGNAL_A below 98 at horizon"}]
        payload["forecast_rationale"] = "[1] " + "Synthetic fixture consequence uses the same baseline and explicit horizon invalidation. " * 15
        return json.dumps(payload)
    if node_id == "lab_cross_corr_v1":
        return json.dumps({"swarms": [], "bifurcations": [], "orphans": [], "confidence_asymmetries": []})
    if node_id == "lab_cross_corr_v2":
        return json.dumps({"target_swarms": [], "directional_conflicts": [], "solo_targets": [
            {"id": "fixture_solo", "name": "Synthetic SIGNAL_A", "summary": "Fixture grounding only", "target_ids": ["SIGNAL_A"], "lanes": ["MEASUREMENTS"], "direction_consensus": "INCREASE"}],
            "thesis_stress": [], "valid_prediction_targets": ["SIGNAL_A"]})
    return "Synthetic recorded response; contract plumbing only."


class ZenithGraphTests(unittest.TestCase):
    def test_exact_authored_graph_and_offline_scope(self):
        self.assertEqual(runtime.validate(ROOT)["node_count"], 75)
        self.assertTrue(runtime.validate(ROOT)["ok"])
        lab = runtime.plan(ROOT, "lab", "lab_decide")
        oracle = runtime.plan(ROOT, "oracle")
        self.assertEqual((lab["node_count"], lab["wave_count"]), (25, 11))
        self.assertEqual((oracle["node_count"], oracle["wave_count"]), (28, 7))
        # Even an early target includes its mission siblings, as the real engine does.
        self.assertIn("lab_integrity", {node["id"] for node in lab["nodes"]})
        self.assertEqual(lab["waves"][3], ["lab_miner_derived", "lab_miner_environment", "lab_miner_events",
                                            "lab_miner_interventions", "lab_miner_measurements", "lab_miner_subsystems"])

    def test_offline_inspection_does_not_construct_engine_or_create_state(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copytree(ROOT / "codex", root / "codex")
            with patch.object(runtime.GodModeEngine, "__init__", side_effect=AssertionError("must stay offline")):
                runtime.validate(root)
                runtime.plan(root, "oracle")
            self.assertFalse((root / "state").exists())


class ZenithHandoffTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source = fixture_root(self.root)

    def tearDown(self):
        self.temp.cleanup()

    def prepare(self, run_id="SYNTHETIC_LAB"):
        return runtime.start(self.root, mission="lab", run_id=run_id,
                             feed_source=str(self.source), horizon=HORIZON, time_anchor=ANCHOR)

    def import_pending(self, item, text=None):
        response = self.root / "answer.txt"
        response.write_text(text if text is not None else response_for(item["node_id"]))
        return runtime.import_response(self.root, packet_path=Path(item["packet_path"]),
                                       response_path=response, model="synthetic-captured-fixture")

    def test_full_original_lab_graph_handoff_schema_context_and_resume(self):
        result = self.prepare()
        self.assertEqual(result["status"], "awaiting_agent")
        self.assertEqual([item["node_id"] for item in result["pending"]], ["lab_seed_state"])
        packet = json.loads(Path(result["pending"][0]["packet_path"]).read_text())
        self.assertIn("[CONTEXT_INJECTION]", packet["prompt"])
        self.assertIn("<global_measurements_feed>", packet["prompt"])
        self.assertEqual(text_digest(packet["prompt"]), packet["prompt_sha256"])
        completed_responses = 0
        saw_sibling_wave = False
        while result["status"] == "awaiting_agent" and completed_responses < 35:
            saw_sibling_wave = saw_sibling_wave or len(result["pending"]) == 6
            imported = self.import_pending(result["pending"][0])
            self.assertTrue(imported["import"]["engine_accepted"], imported)
            result = imported["run"]
            completed_responses += 1
        self.assertEqual(result["status"], "completed", result)
        self.assertTrue(saw_sibling_wave)
        self.assertEqual(result["completed_count"], 25)
        run_dir = self.root / "state/runs/SYNTHETIC_LAB"
        decide = json.loads((run_dir / "artifacts/lab_decide.json").read_text())
        director = json.loads((run_dir / "artifacts/lab_director.json").read_text())
        self.assertTrue(validate_cp1(decide["data"]).ok)
        self.assertTrue(validate_cp2(director["data"], run_dir).ok)
        self.assertEqual(director["data"]["predictions_t"][0]["snapshot_time"], ANCHOR)
        self.assertEqual(director["data"]["predictions_t"][0]["target_time_iso"], HORIZON)
        before = {p.name: p.read_bytes() for p in (run_dir / "artifacts").glob("lab_*.json") if p.stem != "lab_contract_audit"}
        resumed = runtime.resume(self.root, "SYNTHETIC_LAB")
        self.assertEqual(resumed["status"], "completed")
        self.assertEqual(before, {p.name: p.read_bytes() for p in (run_dir / "artifacts").glob("lab_*.json") if p.stem != "lab_contract_audit"})
        # The derived deterministic audit is refreshed at finalization; authored node artifacts remain cached.
        # Completion here demonstrates graph execution only, not prediction quality.
        self.assertIn("do not establish forecasting accuracy", resumed["claim_boundary"])

    def test_frozen_topology_variant_uses_original_scope_and_resume(self):
        from variants.graph import build_base_identity, variant_sha256
        variant = json.loads((ROOT / "examples/variants/lab_evidence_check.json").read_text())
        variant.update(build_base_identity(runtime.load_graph(self.root)))
        variant["variant_sha256"] = variant_sha256(variant)
        path = self.root / "variant.json"
        write_json(path, variant)
        expected = runtime.plan(self.root, "lab", graph_variant=variant)
        self.assertEqual((expected["node_count"], expected["wave_count"]), (26, 12))
        self.assertIn("lab_evidence_check", {node["id"] for node in expected["nodes"]})
        result = runtime.start(self.root, mission="lab", run_id="VARIANT", feed_source=str(self.source),
                               horizon=HORIZON, time_anchor=ANCHOR, graph_variant=str(path))
        self.assertEqual(result["scope_count"], 26)
        spec = json.loads((self.root / "state/runs/VARIANT/zenith_run.json").read_text())
        self.assertEqual(spec["graph_variant"]["variant_sha256"], variant["variant_sha256"])
        effective = runtime.graph_for_manifest(self.root, spec)
        self.assertIn("lab_evidence_check", effective["lab_decide"].dependencies)
        self.assertNotIn("lab_evidence_check", runtime.load_graph(self.root))
        self.assertEqual(runtime.resume(self.root, "VARIANT")["status"], "awaiting_agent")
        path.write_text(path.read_text() + "\n")
        with self.assertRaisesRegex(ValueError, "graph variant source changed"):
            runtime.resume(self.root, "VARIANT")

    def test_oracle_uses_explicit_subject_and_truth_before_reasoning(self):
        # Synthetic pair exercises the original subject proxy/diff tools, not a fake oracle verdict.
        subject = self.source
        payload = cp1()
        payload.update(predictions_t=[{"target_id": "SIGNAL_A", "direction": "UP", "unit": "dimensionless", "snapshot_value": 100.0,
                                      "target_value": 105.0, "snapshot_time": ANCHOR, "target_time_iso": HORIZON,
                                      "invalidation": "SIGNAL_A below 98"}],
                       forecast_rationale="[1] " + "Synthetic fixture consequence remains bound to its baseline and horizon. " * 15)
        for node_id, data in (("lab_decide", cp1()), ("lab_director", payload),
                              ("lab_cross_corr_v2", json.loads(response_for("lab_cross_corr_v2")))):
            write_json(subject / "artifacts" / (node_id + ".json"), {"id": node_id, "status": "success", "data": data})
        context = json.loads((subject / "runtime_context.json").read_text())
        context["horizon"] = {"target_time_iso": HORIZON, "horizon_label": "Synthetic fixture horizon", "horizon_policy": HORIZON}
        write_json(subject / "runtime_context.json", context)
        truth = self.root / "state/runs/SYNTHETIC_TRUTH"
        shutil.copytree(subject, truth)
        write_json(truth / "runtime_context.json", {"as_of": HORIZON, "time_anchor": HORIZON, "subject_group": "feeds"})
        for path in (truth / "artifacts").glob("global_*.json"):
            envelope = json.loads(path.read_text())
            envelope["metadata"].update(as_of=HORIZON, timestamp_iso=HORIZON)
            if path.stem == "global_measurements_feed":
                envelope["data"]["rows"][0][1] = 110.0
            write_json(path, envelope)
        result = runtime.start(self.root, mission="oracle", run_id="SYNTHETIC_ORACLE",
                               subject_run=str(subject), truth_run=str(truth))
        self.assertEqual(result["status"], "awaiting_agent", result)
        self.assertEqual(len(result["pending"]), 6)
        oracle_dir = self.root / "state/runs/SYNTHETIC_ORACLE"
        reconciliation = json.loads((oracle_dir / "artifacts/prediction_reconciliation.json").read_text())["data"]
        self.assertEqual(reconciliation["subject_run_id"], "SYNTHETIC_FEEDS")
        self.assertEqual(reconciliation["truth_run_id"], "SYNTHETIC_TRUTH")
        self.assertEqual(reconciliation["feed_health"]["status"], "READY")
        self.assertEqual(reconciliation["rows"][0]["target_id"], "SIGNAL_A")
        subject_proxy = json.loads((oracle_dir / "artifacts/oracle_subject_measurements_feed.json").read_text())
        truth_feed = json.loads((oracle_dir / "artifacts/global_measurements_feed.json").read_text())
        self.assertEqual(subject_proxy["data"]["rows"][0][1], 100.0)
        self.assertEqual(truth_feed["data"]["rows"][0][1], 110.0)
        with self.assertRaisesRegex(ValueError, "both"):
            runtime.start(self.root, mission="oracle", run_id="UNPAIRED", subject_run=str(subject))

    def test_frozen_policy_and_feed_bytes_are_checked_on_resume(self):
        from system.lib.reasoning_policy import policy_sha256
        policy = {"variant_id": "synthetic_skill_variant", "nodes": {"lab_seed_state": {
            "skill_addon": "SYNTHETIC_VARIANT_ADDON", "incoming_weights": {"global_events_feed": 0}, "max_context_chars": 512}}}
        policy["policy_sha256"] = policy_sha256(policy)
        path = self.root / "policy.json"
        write_json(path, policy)
        result = runtime.start(self.root, mission="lab", run_id="POLICY", feed_source=str(self.source),
                               horizon=HORIZON, time_anchor=ANCHOR, policy=str(path))
        packet = json.loads(Path(result["pending"][0]["packet_path"]).read_text())
        self.assertIn("SYNTHETIC_VARIANT_ADDON", packet["prompt"])
        spec = json.loads((self.root / "state/runs/POLICY/zenith_run.json").read_text())
        self.assertEqual(spec["reasoning_policy"]["policy_sha256"], policy["policy_sha256"])
        path.write_text(path.read_text() + "\n")
        with self.assertRaisesRegex(ValueError, "policy source changed"):
            runtime.resume(self.root, "POLICY")
        self.prepare()
        feed = self.source / "artifacts/global_measurements_feed.json"
        envelope = json.loads(feed.read_text())
        envelope["data"]["rows"][0][1] = 999.0
        write_json(feed, envelope)
        with self.assertRaisesRegex(ValueError, "source run changed"):
            runtime.resume(self.root, "SYNTHETIC_LAB")

    def test_invalid_cp1_can_be_corrected_without_losing_rejected_response(self):
        result = self.prepare()
        while result["status"] == "awaiting_agent" and result["pending"][0]["node_id"] != "lab_decide":
            result = self.import_pending(result["pending"][0])["run"]
        packet = result["pending"][0]
        rejected = self.import_pending(packet, '{}')
        self.assertFalse(rejected["import"]["engine_accepted"])
        self.assertTrue(rejected["import"]["engine_errors"])
        corrected = self.import_pending(packet)
        self.assertTrue(corrected["import"]["engine_accepted"])
        rejected_dir = self.root / "state/runs/SYNTHETIC_LAB/handoff/rejected_responses" / packet["packet_id"]
        archived = [json.loads(path.read_text()) for path in rejected_dir.glob("*.json")]
        self.assertEqual(archived[0]["response_text"], '{}')
        self.assertFalse(archived[0]["engine_validation"]["engine_accepted"])

    def test_import_wrong_binding_and_arbitrary_packet_location_are_rejected(self):
        result = self.prepare()
        original = Path(result["pending"][0]["packet_path"])
        packet = json.loads(original.read_text())
        forged = self.root / "copied_packet.json"
        write_json(forged, packet)
        answer = self.root / "answer.txt"
        answer.write_text("Synthetic")
        with self.assertRaisesRegex(ValueError, "original request"):
            runtime.import_response(self.root, packet_path=forged, response_path=answer)
        record = {"schema": "zenith_agent_response_v1", **{key: packet[key] for key in
                  ("packet_id", "run_id", "node_id", "prompt_sha256")}, "response_text": "Synthetic"}
        record["node_id"] = "lab_director"
        write_json(answer, record)
        with self.assertRaisesRegex(ValueError, "node_id mismatch"):
            runtime.import_response(self.root, packet_path=original, response_path=answer)

    def test_schema_failure_generates_original_repair_packet_and_keeps_failure_artifact(self):
        result = self.prepare()
        while result["pending"][0]["node_id"] != "lab_cross_corr_v1":
            result = self.import_pending(result["pending"][0])["run"]
        imported = self.import_pending(result["pending"][0], '{}')
        self.assertFalse(imported["import"]["engine_accepted"])
        repairs = imported["run"]["pending"]
        self.assertTrue(repairs)
        packet = json.loads(Path(repairs[-1]["packet_path"]).read_text())
        self.assertIn("[SYSTEM_CORRECTION]", packet["prompt"])
        self.assertIn("MISSING_FIELD", packet["prompt"])
        artifact = self.root / "state/runs/SYNTHETIC_LAB/artifacts/lab_cross_corr_v1.json"
        failed = json.loads(artifact.read_text())
        self.assertEqual(failed["status"], "failure")
        self.assertFalse((artifact.parent / "lab_decide.json").exists())
        recovered = self.import_pending(repairs[-1])
        self.assertTrue(recovered["import"]["engine_accepted"])

    def test_lab_refuses_future_truth_and_oracle_pair_args_before_creating_run(self):
        path = self.source / "artifacts/global_measurements_feed.json"
        envelope = json.loads(path.read_text())
        envelope["metadata"]["as_of"] = HORIZON
        write_json(path, envelope)
        with self.assertRaisesRegex(ValueError, "later than"):
            self.prepare()
        self.assertFalse((self.root / "state/runs/SYNTHETIC_LAB").exists())
        with self.assertRaisesRegex(ValueError, "forward-only"):
            runtime.start(self.root, mission="lab", run_id="BAD", feed_source=str(self.source), truth_run=str(self.source))

    def test_lab_refuses_future_observation_availability_with_past_acquisition(self):
        path = self.source / "artifacts/global_measurements_feed.json"
        envelope = json.loads(path.read_text())
        envelope["data"]["observations"] = [{"target_id":"SIGNAL_A", "value":1, "unit":"dimensionless", "observed_at":ANCHOR, "available_at":HORIZON}]
        write_json(path, envelope)
        with self.assertRaisesRegex(ValueError, "later than cutoff"):
            self.prepare()
        self.assertFalse((self.root / "state/runs/SYNTHETIC_LAB").exists())

    def test_changed_node_source_refuses_resume(self):
        self.prepare()
        path = self.root / "codex/substrate/nodes/lab/seed_state.json"
        node = json.loads(path.read_text())
        node["instruction"] += " changed"
        write_json(path, node)
        with self.assertRaisesRegex(ValueError, "source changed"):
            runtime.resume(self.root, "SYNTHETIC_LAB")

    def test_captured_provider_must_match_exact_node_and_prompt(self):
        result = self.prepare()
        packet = json.loads(Path(result["pending"][0]["packet_path"]).read_text())
        captures = self.root / "captures.json"
        write_json(captures, {"responses": [{"node_id": packet["node_id"], "prompt_sha256": packet["prompt_sha256"],
                                           "response_text": "Synthetic", "actual_model": "captured-fixture"}]})
        spec_path = self.root / "state/runs/SYNTHETIC_LAB/zenith_run.json"
        spec = json.loads(spec_path.read_text())
        spec.update(provider="captured", responses=str(captures))
        write_json(spec_path, spec)
        runtime.resume(self.root, "SYNTHETIC_LAB")
        artifact = spec_path.parent / "artifacts/lab_seed_state.json"
        self.assertEqual(json.loads(artifact.read_text())["status"], "success")
        provider = CapturedProvider(spec_path.parent, captures)
        with self.assertRaisesRegex(ValueError, "exact node and prompt"):
            provider.ask_ai("tampered", config=packet["engine_config"])


class FreeProviderTests(unittest.TestCase):
    def test_free_only_guard_and_actual_model_receipt(self):
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory) / "RUN"
            with self.assertRaises(ValueError):
                OpenRouterFreeProvider(run, "paid/model")
            seen = []
            def call(prompt, config):
                seen.append(config)
                return {"response_text": "synthetic", "model": "qwen/actual-model:free", "usage": {"total_tokens": 7}, "cost": 0}
            provider = OpenRouterFreeProvider(run, model="qwen/fixture:free", caller=call)
            self.assertEqual(provider.ask_ai("hello", {"meta": {"node_id": "lab_seed_state", "session_id": "RUN"}}), "synthetic")
            self.assertTrue(seen[0]["free_only"])
            self.assertFalse(seen[0]["allow_paid"])
            receipts = [json.loads(path.read_text()) for path in (run / "handoff/receipts").glob("*.json")]
            returned = next(row for row in receipts if row["status"] == "response_supplied")
            self.assertEqual(returned["actual_model"], "qwen/actual-model:free")
            self.assertEqual(returned["requested_model"], "qwen/fixture:free")
            self.assertEqual(returned["usage"]["total_tokens"], 7)
            provider.ask_ai("hello", {"meta": {"node_id": "lab_seed_state", "session_id": "RUN"}})
            self.assertEqual(len(seen), 1, "resume must reuse the durable response without another API attempt")

    def test_failed_free_api_attempt_is_durable_and_not_silently_reissued(self):
        with tempfile.TemporaryDirectory() as directory:
            count = []
            def fail(prompt, config):
                count.append(1)
                raise RuntimeError("synthetic network failure")
            run = Path(directory) / "RUN"
            provider = OpenRouterFreeProvider(run, model="qwen/fixture:free", caller=fail)
            config = {"meta": {"node_id": "lab_seed_state", "session_id": "RUN"}}
            with self.assertRaisesRegex(RuntimeError, "synthetic network failure"):
                provider.ask_ai("prompt", config)
            with self.assertRaisesRegex(RuntimeError, "not be silently resent"):
                OpenRouterFreeProvider(run, model="qwen/fixture:free", caller=fail).ask_ai("prompt", config)
            self.assertEqual(len(count), 1)


if __name__ == "__main__":
    unittest.main()
