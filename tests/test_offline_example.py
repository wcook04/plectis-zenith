"""Offline example regression: synthetic inputs, real native graph, no provider calls."""
from __future__ import annotations

import json
import io
from contextlib import redirect_stdout
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from zenith import cli, offline_example, runtime
from zenith.providers import NvidiaNimProvider, OpenRouterFreeProvider
from system.core.loader import _NodeIndexer
from system.lib.schema_validator import validate_cp1, validate_cp2, validate_cross_corr_v2

ROOT = Path(__file__).resolve().parents[1]


class OfflineExampleTests(unittest.TestCase):
    def test_cli_help_and_json_retain_research_notice(self):
        self.assertIn("This is not financial advice.", " ".join(cli.parser().format_help().split()))
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(cli.main(["validate"]), 0)
        value = json.loads(output.getvalue())
        self.assertTrue(value["ok"])
        self.assertEqual(value["notice"], "This is not financial advice.")
        self.assertEqual(value["notice_path"], "RESEARCH_NOTICE.md")

    def test_hidden_node_files_remain_excluded_under_hidden_checkout(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / ".checkout"
            nodes = root / "codex" / "nodes"
            (nodes / ".ignored").mkdir(parents=True)
            (nodes / "visible.json").write_text('{"id":"visible"}')
            (nodes / ".ignored" / "duplicate.json").write_text('{"id":"visible"}')
            self.assertEqual(set(_NodeIndexer(root).scan()), {"visible"})

    @classmethod
    def setUpClass(cls):
        # One real run, into a path that deliberately contains spaces.
        cls._temp = tempfile.TemporaryDirectory()
        cls.output = Path(cls._temp.name) / ".hidden parent" / "offline demo output"
        with patch.object(OpenRouterFreeProvider, "ask_ai", side_effect=AssertionError("no provider calls")), \
                patch.object(NvidiaNimProvider, "__init__", side_effect=AssertionError("no provider construction")), \
                patch("system.lib.openrouter_free_runtime.chat_completion_packet",
                      side_effect=AssertionError("no network calls")):
            cls.result = offline_example.run(ROOT, cls.output)

    @classmethod
    def tearDownClass(cls):
        cls._temp.cleanup()

    def test_real_native_graph_completes_without_provider_calls(self):
        self.assertTrue(self.result["ok"])
        self.assertEqual(self.result["status"], "completed")
        self.assertEqual(self.result["lab_completed_count"], self.result["lab_scope_count"])
        # Counts are derived from the native graph, not hardcoded.
        self.assertEqual(self.result["graph_node_count"], runtime.validate(ROOT)["node_count"])
        run_dir = self.output / "demo_root" / "runs" / offline_example.RUN_ID
        spec = json.loads((run_dir / "zenith_run.json").read_text())
        self.assertEqual(spec["provider"], "agent")
        self.assertTrue((run_dir / "artifacts" / "lab_director.json").exists())
        self.assertTrue(str(self.output).endswith("offline demo output"))

    def test_deliberate_rejection_is_retained_then_corrected(self):
        self.assertEqual(self.result["rejected_responses"], 1)
        self.assertEqual(self.result["corrected_responses"], 1)
        summary = json.loads((self.output / "summary.json").read_text())
        archived_paths = summary["evidence_paths"]["rejected_responses"]
        self.assertEqual(len(archived_paths), 1)
        archived = json.loads((self.output / archived_paths[0]).read_text())
        self.assertEqual(archived["response_text"], offline_example.INVALID_RESPONSE)
        self.assertFalse(archived["engine_validation"]["engine_accepted"])
        decide = json.loads((self.output / summary["evidence_paths"]["lab_decide_artifact"]).read_text())
        self.assertEqual(decide["status"], "success")

    def test_generic_native_contracts_are_exercised(self):
        run_dir = self.output / "demo_root" / "runs" / offline_example.RUN_ID
        artifacts = run_dir / "artifacts"
        measurements = json.loads((artifacts / "global_measurements_feed.json").read_text())
        decide = json.loads((artifacts / "lab_decide.json").read_text())
        director = json.loads((artifacts / "lab_director.json").read_text())
        cross_corr = json.loads((artifacts / "lab_cross_corr_v2.json").read_text())

        self.assertEqual(measurements["data"]["rows"], [["SIGNAL_A", 100.0]])
        self.assertTrue(validate_cp1(decide["data"]).ok)
        self.assertTrue(validate_cp2(director["data"], subject_run_dir=run_dir).ok)
        self.assertTrue(validate_cross_corr_v2(cross_corr["data"]).ok)
        self.assertEqual(director["data"]["predictions_t"][0]["target_id"], "SIGNAL_A")
        self.assertEqual(cross_corr["data"]["solo_targets"][0]["target_ids"], ["SIGNAL_A"])

    def test_outputs_are_labelled_synthetic_and_offline(self):
        summary = json.loads((self.output / "summary.json").read_text())
        self.assertEqual(summary["notice"], "This is not financial advice.")
        self.assertEqual(summary["synthetic_contract_demonstration"], "Synthetic contract demonstration")
        self.assertEqual((summary["network_calls"], summary["model_calls"], summary["private_inputs"]), (0, 0, False))
        readme = (self.output / "README.md").read_text()
        self.assertIn("This is not financial advice.", readme)
        self.assertIn("Synthetic contract demonstration", readme)

    def test_existing_nonempty_output_is_refused_without_touching_sentinel(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "occupied"
            output.mkdir()
            sentinel = output / "sentinel.txt"
            sentinel.write_text("keep me")
            with self.assertRaisesRegex(ValueError, "new or empty"):
                offline_example.run(ROOT, output)
            self.assertEqual(sentinel.read_text(), "keep me")
            self.assertFalse((output / "demo_root").exists())


if __name__ == "__main__":
    unittest.main()
