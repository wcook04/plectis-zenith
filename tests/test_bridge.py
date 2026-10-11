"""Receipt joining, fail-closed aggregation and public HTTP boundary tests."""
from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import urlopen

from observatory.export import build_operations, write_operations
from observatory.serve import make_server

NOW = datetime(2026, 10, 11, 14, tzinfo=timezone.utc)
SECRET = "PRIVATE_SENTINEL_NEVER_PUBLISH"
PENDING_ID = "a" * 24
FAILED_ID = "b" * 24


def put(root, relative, data):
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def prediction(identity=PENDING_ID, status="pending_truth"):
    return {"schema": "market_model_experiment_v1", "experiment_id": identity,
            "status": status, "requested_model": "openrouter/free",
            "event_end": "2026-10-12T20:00:00Z",
            "claims": [{"private": SECRET} for _ in range(5)] if status == "pending_truth" else [],
            "prompt": SECRET, "error": SECRET,
            "snapshot": {"rows": {SECRET: {"Price": 123}}},
            "predictions": [{"ticker": SECRET, "rationale": SECRET, "probability_outperform_spy": .91}],
            "model_receipt": {"model": "poolside/laguna-xs-2.1:free", "response_text": SECRET,
                              "usage": {"cost": 0}, "credentials": SECRET} if status == "pending_truth" else {}}


class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)

    def tearDown(self):
        self.temporary.cleanup()

    def fixture(self):
        put(self.root, f"state/finance_eval/market_experiments/predictions/{PENDING_ID}.json", prediction())
        put(self.root, f"state/finance_eval/market_experiments/predictions/{FAILED_ID}.json", prediction(FAILED_ID, "model_failed"))
        base = "state/runs/FEEDS_20261011_validation/artifacts/"
        put(self.root, base + "feed_readiness_summary.json", {
            "schema_version": "feed_readiness_summary.v1", "run_id": "FEEDS_20261011_validation",
            "generated_at": "2026-10-11T13:59:59Z", "ready": True,
            "runtime_context": {"as_of": "2026-10-11T12:50:00Z", "error": SECRET},
            "feeds": [{"node_id": "global_etf_feed", "reason": SECRET}]})
        put(self.root, base + "global_etf_feed.json", {
            "status": "success", "metadata": {"items_count": 3, "timestamp_iso": "2026-10-11T12:48:44Z", "private": SECRET},
            "data": {"columns": ["Ticker", "Price"], "rows": [[SECRET, 1], [SECRET, None], [SECRET, 0]]}})
        clock = self.root / "system/lib/metabolism_market_clock.py"
        clock.parent.mkdir(parents=True)
        clock.write_text('DEFAULT_TIMEZONE = "America/New_York"\nDEFAULT_FIRE_POINTS = ({"name":"open","local_time":"09:30"},{"name":"close","local_time":"16:00"})\ndef capture_window_receipt(target, *, max_delay_seconds=900):\n    raise RuntimeError("MUST NOT EXECUTE PRIVATE SOURCE")\n')

    def test_aggregates_do_not_publish_private_fields_or_paths(self):
        self.fixture()
        result = build_operations(self.root, now=NOW)
        encoded = json.dumps(result)
        self.assertNotIn(SECRET, encoded)
        self.assertNotIn(str(self.root), encoded)
        self.assertNotIn("probability_outperform_spy", encoded)
        self.assertEqual(result["experiments"]["pending_count"], 1)
        self.assertEqual(result["experiments"]["failed_count"], 1)
        self.assertEqual(result["experiments"]["forecast_count"], 5)
        self.assertEqual(result["experiments"]["count_unit"], "model_attempts")
        self.assertEqual(result["collection"]["acquired_at"], "2026-10-11T12:48:44Z")
        self.assertEqual(result["collection"]["schedule_kind"], "manual_or_unspecified")
        self.assertEqual(result["collection"]["clock"]["capture_window_minutes"], 15)
        self.assertEqual(result["collection"]["lanes"][0]["missing_price_rows"], 2)

    def test_score_supersedes_immutable_pending_receipt(self):
        self.fixture()
        put(self.root, f"state/finance_eval/market_experiments/scores/{PENDING_ID}.json", {
            "schema": "market_experiment_score_v1", "experiment_id": PENDING_ID,
            "scored_at": "2026-10-12T20:03:00Z", "evaluation": {"private": SECRET}, "truth": SECRET})
        exp = build_operations(self.root, now=NOW)["experiments"]
        self.assertEqual((exp["pending_count"], exp["scored_count"], exp["forecast_count"]), (0, 1, 5))
        self.assertIsNone(exp["first_truth_due_at"])
        self.assertEqual(exp["models"][0]["status"], "scored")

    def test_unavailable_is_not_zero(self):
        for root in (None, self.root):
            result = build_operations(root, now=NOW)
            self.assertEqual(result["collection"]["readiness"], "unavailable")
            self.assertEqual(result["experiments"]["source_status"], "unavailable")
            self.assertIsNone(result["experiments"]["pending_count"])
        (self.root / "state/finance_eval/market_experiments/predictions").mkdir(parents=True)
        self.assertEqual(build_operations(self.root, now=NOW)["experiments"]["pending_count"], 0)

    def test_corrupt_receipt_invalidates_totals_without_error_dump(self):
        self.fixture()
        path = self.root / f"state/finance_eval/market_experiments/predictions/{PENDING_ID}.json"
        for content in (f'{{"error":"{SECRET}"', '{"schema": NaN}', '{"schema": "a", "schema": "b"}', '[]'):
            path.write_text(content)
            result = build_operations(self.root, now=NOW)
            self.assertEqual(result["experiments"]["source_status"], "invalid_source")
            self.assertIsNone(result["experiments"]["forecast_count"])
            self.assertNotIn(SECRET, json.dumps(result))

    def test_corrupt_latest_run_does_not_fall_back_to_older_success(self):
        self.fixture()
        put(self.root, "state/runs/FEEDS_20261012_close/artifacts/feed_readiness_summary.json", {"ready": SECRET})
        result = build_operations(self.root, now=NOW)
        self.assertEqual(result["collection"]["readiness"], "invalid_source")
        self.assertEqual(result["collection"]["last_run_id"], "FEEDS_20261012_close")
        self.assertEqual(result["collection"]["lanes"], [])

    def test_untrusted_model_id_and_cost_are_sanitized(self):
        self.fixture()
        receipt = prediction()
        receipt["requested_model"] = str(self.root / SECRET)
        receipt["model_receipt"]["model"] = SECRET
        receipt["model_receipt"]["usage"]["cost"] = -1
        put(self.root, f"state/finance_eval/market_experiments/predictions/{PENDING_ID}.json", receipt)
        model = build_operations(self.root, now=NOW)["experiments"]["models"][0]
        self.assertIsNone(model["requested"])
        self.assertIsNone(model["actual"])
        self.assertIsNone(model["cost"])

    def test_same_day_runs_are_ordered_by_acquisition_not_name_or_publication(self):
        self.fixture()
        for suffix, timestamp in (("open", "2026-10-12T13:31:00Z"), ("close", "2026-10-12T20:01:00Z")):
            base = f"state/runs/FEEDS_20261012_{suffix}/artifacts/"
            put(self.root, base + "feed_readiness_summary.json", {
                "schema_version": "feed_readiness_summary.v1", "run_id": f"FEEDS_20261012_{suffix}",
                "generated_at": "2026-10-13T23:59:59Z", "ready": True,
                "runtime_context": {"schedule": {"fire_point": suffix}},
                "feeds": [{"node_id": "global_etf_feed"}]})
            put(self.root, base + "global_etf_feed.json", {
                "status": "success", "metadata": {"items_count": 1, "timestamp_iso": timestamp}})
        result = build_operations(self.root, now=NOW)["collection"]
        self.assertEqual(result["last_run_id"], "FEEDS_20261012_close")
        self.assertEqual(result["acquired_at"], "2026-10-12T20:01:00Z")
        self.assertEqual(result["schedule_kind"], "close")

    def test_malformed_types_fail_closed(self):
        self.fixture()
        receipt = prediction()
        receipt["status"] = {"error": SECRET}
        put(self.root, f"state/finance_eval/market_experiments/predictions/{PENDING_ID}.json", receipt)
        self.assertEqual(build_operations(self.root, now=NOW)["experiments"]["source_status"], "invalid_source")

    def test_write_is_deterministic_and_atomic(self):
        self.fixture()
        first = build_operations(self.root, now=NOW)
        self.assertEqual(first, build_operations(self.root, now=NOW))
        output = self.root / "public/operations.json"
        write_operations(output, first)
        self.assertEqual(json.loads(output.read_text()), first)
        self.assertEqual(list(output.parent.glob("*.tmp")), [])
        with self.assertRaises(ValueError):
            write_operations(output, {"invalid": float("nan")})
        self.assertEqual(json.loads(output.read_text()), first)

    def test_http_server_exposes_only_public_files_and_aggregate(self):
        self.fixture()
        web = self.root / "web"
        web.mkdir()
        (web / "index.html").write_text("Public observatory")
        (web / "predictions.csv").write_text("forecast_id,probability\npublic,0.5\n")
        (web / "methodology.md").write_text("Public methodology")
        secret = self.root / "private.txt"
        secret.write_text(SECRET)
        (web / ".credentials.txt").write_text(SECRET)
        (web / "leak.txt").symlink_to(secret)
        server = make_server(port=0, web_root=web, source_root=self.root)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_port}"
        try:
            with urlopen(base + "/") as response:
                self.assertEqual(response.read(), b"Public observatory")
                self.assertIsNone(response.headers.get("Access-Control-Allow-Origin"))
            with urlopen(base + "/data/operations.json") as response:
                body = response.read().decode()
                self.assertNotIn(SECRET, body)
                self.assertEqual(json.loads(body)["experiments"]["forecast_count"], 5)
            for path, content_type in (("/predictions.csv", "text/csv"), ("/methodology.md", "text/plain")):
                with urlopen(base + path) as response:
                    self.assertEqual(response.status, 200)
                    self.assertTrue(response.headers["Content-Type"].startswith(content_type))
            for path in ("/../private.txt", "/%2e%2e/private.txt", "/.credentials.txt", "/leak.txt", "/observatory/export.py", "/%252e%252e/private.txt", "/..%5cprivate.txt"):
                with self.assertRaises(HTTPError) as caught:
                    urlopen(base + path)
                self.assertEqual(caught.exception.code, 404)
                self.assertNotIn(SECRET, caught.exception.read().decode())
                caught.exception.close()
            self.assertFalse((web / "data/operations.json").exists(), "GET must not write receipt files")
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)


if __name__ == "__main__":
    unittest.main()
