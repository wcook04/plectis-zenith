"""Compact context is metadata projection; full feed data and bar provenance survive."""
from __future__ import annotations

import copy
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from zenith.context import compact_feed_envelope
from zenith import runtime
from zenith.providers import write_json

ROOT = Path(__file__).resolve().parents[1]
ANCHOR = "2026-03-04T14:30:00+00:00"


class CompactContextTests(unittest.TestCase):
    def test_metadata_duplicates_removed_full_data_and_price_basis_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "global_etf_feed.json"
            data = {"columns": ["Ticker", "Price", "Chg_5d"], "rows": [[f"T{index}", 100.0 + index, index] for index in range(100)]}
            price_observations = {"T1": {"session_date": "2026-03-03", "interval": "1d", "auto_adjust": False,
                                          "provider": "synthetic", "currency": "USD", "bar_date": "2026-03-03", "price_basis": "unadjusted daily close"}}
            envelope = {"id": "global_etf_feed", "status": "success", "data": data, "metadata": {
                "status": "success", "as_of": ANCHOR, "timestamp_iso": ANCHOR, "effective_time": ANCHOR, "price_basis": "unadjusted daily close",
                "diagnostics": {"price_observations": price_observations, "warnings": ["synthetic_fixture"],
                                "input_rows": 100, "provider_raw_payload": "X" * 100000},
                "raw_response": "Y" * 100000, "data_quality": {"status": "READY"}}}
            original = copy.deepcopy(envelope)
            write_json(path, envelope)
            original_bytes = path.read_bytes()
            projected = compact_feed_envelope(envelope, artifact_path=path, artifact_ref="artifacts/global_etf_feed.json")
            self.assertEqual(projected["data"], data)
            self.assertEqual(envelope, original)
            self.assertEqual(path.read_bytes(), original_bytes)
            self.assertEqual(projected["metadata"]["diagnostics"]["price_observations"], price_observations)
            self.assertEqual(projected["metadata"]["price_basis"], "unadjusted daily close")
            self.assertEqual(projected["metadata"]["effective_time"], ANCHOR)
            self.assertEqual(projected["metadata"]["data_quality"], {"status": "READY"})
            receipt = projected["metadata"]["context_projection"]
            self.assertIn("raw_response", receipt["omitted_metadata_keys"])
            self.assertIn("provider_raw_payload", receipt["omitted_diagnostic_keys"])
            self.assertTrue(receipt["data_preserved"])
            self.assertEqual(receipt["full_artifact_ref"], "artifacts/global_etf_feed.json")
            self.assertLess(len(json.dumps(projected)), len(json.dumps(envelope)) / 10)

    def test_explicit_profile_is_before_engine_prompt_hash_and_retains_every_row(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copytree(ROOT / "codex", root / "codex")
            write_json(root / "master_config.json", {"paths": {"runs_dir": "state/runs"}})
            source = root / "state/runs/FEEDS"
            write_json(source / "runtime_context.json", {"as_of": ANCHOR})
            data = {"columns": ["Ticker", "Price", "Chg_5d"], "rows": [[f"T{index}", 100 + index, index] for index in range(100)]}
            for node in runtime.load_graph(root).values():
                if node.meta.get("is_feed"):
                    write_json(source / "artifacts" / (node.id + ".json"), {
                        "id": node.id, "status": "success", "metadata": {"status": "success", "as_of": ANCHOR,
                        "timestamp_iso": ANCHOR, "raw_response": "X" * 10000},
                        "data": data if node.id == "global_stock_feed" else {"synthetic": True}})
            result = runtime.start(root, mission="lab", run_id="COMPACT", feed_source=str(source),
                                   horizon="2026-03-05T21:00:00+00:00", context_profile="compact_feeds")
            packet = json.loads(Path(result["pending"][0]["packet_path"]).read_text())
            feed_text = packet["prompt"].split("<global_stock_feed>\n", 1)[1].split("\n</global_stock_feed>", 1)[0]
            view = json.loads(feed_text)
            self.assertEqual(view["data"], data)
            self.assertEqual(view["metadata"]["context_projection"]["profile"], "compact_feeds")
            stored = json.loads((root / "state/runs/COMPACT/artifacts/global_stock_feed.json").read_text())
            self.assertIn("raw_response", stored["metadata"])
            self.assertEqual(result["failed_nodes"], [])
            self.assertEqual(result["status"], "awaiting_agent")
            spec = json.loads((root / "state/runs/COMPACT/zenith_run.json").read_text())
            self.assertEqual(spec["context_profile"], "compact_feeds")
            self.assertIn("system/core/engine.py", spec["implementation_hashes"])
            self.assertIn("system/lib/schema_validator.py", spec["implementation_hashes"])
            self.assertIn("zenith/context.py", spec["implementation_hashes"])
            with patch.object(runtime, "implementation_hashes", return_value={}):
                with self.assertRaisesRegex(ValueError, "pipeline implementation changed"):
                    runtime.resume(root, "COMPACT")


if __name__ == "__main__":
    unittest.main()
