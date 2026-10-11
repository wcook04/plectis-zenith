"""BYOK and provider boundaries use fake credentials and mocked transports only."""
import contextlib
import io
import json
import os
import tempfile
import traceback
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from system.lib import openrouter_free_runtime as api
from zenith.cli import main
from zenith.provider_setup import check
from zenith.providers import NvidiaNimProvider, OpenRouterFreeProvider, NVIDIA_ENDPOINT

SENTINEL = "sk-or-v1-NEVER_LOG_THIS_FAKE_SENTINEL_12345"
NVIDIA_SENTINEL = "nvapi-NEVER_LOG_THIS_FAKE_SENTINEL_67890"
MODEL = "synthetic/model:free"
ROW = {"id": MODEL, "name": "Synthetic", "context_length": 131072,
       "pricing": {"prompt": "0", "completion": "0", "request": "0"}, "supported_parameters": []}
CONFIG = {"meta": {"node_id": "lab_seed_state", "session_id": "RUN"}}


class ProviderSetupTests(unittest.TestCase):
    def test_catalogue_check_is_unauthenticated_and_does_not_infer(self):
        seen = []
        def get(url, headers, timeout):
            seen.append((url, headers))
            return {"data": [ROW, {**ROW, "id": "expensive/model:free", "pricing": {"prompt": "1", "completion": "0"}}]}
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": SENTINEL}, clear=True):
            result = check(http_get=get)
        self.assertTrue(result["key_configured"])
        self.assertEqual([row["id"] for row in result["models"]], [MODEL])
        self.assertEqual(result["models"][0]["context_length"], 131072)
        self.assertFalse(result["inference_performed"])
        self.assertEqual(len(seen), 1)
        self.assertEqual(seen[0][0], "https://openrouter.ai/api/v1/models")
        self.assertNotIn("Authorization", seen[0][1])
        self.assertNotIn(SENTINEL, json.dumps(result))

    def test_no_dotenv_autodiscovery_and_explicit_file_keeps_env_precedence(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".env"
            path.write_text("OPENROUTER_API_KEY=placeholder\nNVIDIA_API_KEY=placeholder\n")
            loader = Mock(return_value={"OPENROUTER_API_KEY": SENTINEL, "NVIDIA_API_KEY": NVIDIA_SENTINEL,
                                        "PATH": "untrusted-do-not-import"})
            with patch.dict(os.environ, {"OPENROUTER_API_KEY": "existing-own-key"}, clear=True), patch.dict("sys.modules", {"dotenv": SimpleNamespace(dotenv_values=loader)}):
                api._ensure_env_loaded()
                loader.assert_not_called()
                api.load_env_file(path)
                self.assertEqual(os.environ["OPENROUTER_API_KEY"], "existing-own-key")
                self.assertEqual(os.environ["NVIDIA_API_KEY"], NVIDIA_SENTINEL)
                self.assertNotIn("PATH", os.environ)
                loader.assert_called_once_with(path.resolve(), interpolate=False)

    def test_unknown_nonzero_and_missing_pricing_fail_before_post(self):
        cases = [None, {}, {"prompt": "0"}, {"prompt": "unknown", "completion": "0"},
                 {"prompt": "0", "completion": "NaN"}, {"prompt": "0", "completion": "Infinity"},
                 {"prompt": "0", "completion": "0", "request": "0.01"},
                 {"prompt": "0", "completion": "0", "internal_reasoning": "1"}]
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": SENTINEL}, clear=True):
            for pricing in cases:
                with self.subTest(pricing=pricing):
                    post = Mock()
                    with self.assertRaisesRegex(RuntimeError, "zero pricing"):
                        api.chat_completion_packet("hello", {"model": MODEL}, http_get=lambda *args: {"data": [{**ROW, "pricing": pricing}]}, http_post=post)
                    post.assert_not_called()
            post = Mock()
            with self.assertRaisesRegex(RuntimeError, "absent"):
                api.chat_completion_packet("hello", {"model": MODEL}, http_get=lambda *args: {"data": []}, http_post=post)
            post.assert_not_called()
            with self.assertRaisesRegex(RuntimeError, "never permits paid"):
                api.chat_completion_packet("hello", {"model": MODEL, "allow_paid": True}, http_get=Mock(), http_post=post)
            post.assert_not_called()

    def test_own_key_success_and_redacted_provider_packet(self):
        seen = []
        def post(url, headers, payload, timeout):
            seen.append((url, headers, payload))
            return {"model": "actual/synthetic:free", "choices": [{"message": {"content": "safe " + SENTINEL}}],
                    "usage": {"total_tokens": 3, "cost": 0, "api_key": SENTINEL}, "provider": "Bearer " + SENTINEL}
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": SENTINEL}, clear=True):
            packet = api.chat_completion_packet("hello", {"model": MODEL}, http_get=lambda *args: {"data": [ROW]}, http_post=post)
        self.assertEqual(seen[0][1]["Authorization"], "Bearer " + SENTINEL)
        self.assertEqual(seen[0][0], "https://openrouter.ai/api/v1/chat/completions")
        self.assertEqual(seen[0][2]["provider"]["max_price"], {"prompt": 0, "completion": 0, "request": 0})
        self.assertEqual(packet["requested_model"], MODEL)
        self.assertEqual(packet["model"], "actual/synthetic:free")
        self.assertNotIn(SENTINEL, json.dumps(packet))
        self.assertEqual(packet["cost"], 0)

    def test_untrusted_host_and_redirect_are_rejected_without_credential_forwarding(self):
        get = Mock()
        post = Mock()
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": SENTINEL, "OPENROUTER_BASE_URL": "https://evil.invalid"}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "official HTTPS"):
                api.chat_completion_packet("hello", http_get=get, http_post=post)
        get.assert_not_called()
        post.assert_not_called()
        redirect = Mock(status_code=307)
        with patch.object(api, "requests", SimpleNamespace(post=Mock(return_value=redirect))):
            transport = api.requests.post
            with self.assertRaisesRegex(RuntimeError, "redirects are disabled"):
                api._default_http_post("https://openrouter.ai/api/v1/chat/completions", {"Authorization": "Bearer " + SENTINEL}, {}, 30)
        self.assertFalse(transport.call_args.kwargs["allow_redirects"])

    def test_secrets_never_reach_exception_receipt_or_cli_output(self):
        def fail(*args, **kwargs):
            raise RuntimeError("Authorization: Bearer " + SENTINEL + " NVIDIA " + NVIDIA_SENTINEL)
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {"OPENROUTER_API_KEY": SENTINEL, "NVIDIA_API_KEY": NVIDIA_SENTINEL}, clear=True):
            run = Path(directory) / "RUN"
            provider = OpenRouterFreeProvider(run, caller=fail)
            try:
                provider.ask_ai("hello", CONFIG)
            except RuntimeError:
                text = traceback.format_exc()
            self.assertNotIn(SENTINEL, text)
            self.assertNotIn(NVIDIA_SENTINEL, text)
            for path in run.rglob("*.json"):
                self.assertNotIn(SENTINEL, path.read_text())
                self.assertNotIn(NVIDIA_SENTINEL, path.read_text())
            output = io.StringIO()
            with patch("zenith.provider_setup.openrouter.runtime_status", side_effect=RuntimeError(SENTINEL)), contextlib.redirect_stdout(output):
                self.assertEqual(main(["provider", "doctor"]), 1)
            self.assertNotIn(SENTINEL, output.getvalue())

    def test_key_status_is_explicit_and_does_not_guess_quota(self):
        seen = []
        def get(url, headers, timeout):
            seen.append((url, headers))
            if url.endswith("/models"):
                return {"data": [ROW]}
            return {"data": {"free_model_daily_requests": {"used": 2, "limit": 17, "remaining": 15}, "label": SENTINEL}}
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": SENTINEL}, clear=True):
            result = check(http_get=get, check_key=True)
        self.assertEqual(len(seen), 2)
        self.assertEqual(seen[1][0], "https://openrouter.ai/api/v1/key")
        self.assertIn("Authorization", seen[1][1])
        self.assertEqual(result["free_model_daily_requests"]["remaining"], 15)
        self.assertNotIn(SENTINEL, json.dumps(result))
        with patch.dict(os.environ, {}, clear=True):
            missing = check(offline=True)
        self.assertFalse(missing["key_configured"])
        self.assertIsNone(missing["free_model_daily_requests"])


class NvidiaProviderTests(unittest.TestCase):
    def test_explicit_model_official_endpoint_own_key_receipt_and_no_resend(self):
        seen = []
        def post(url, headers, payload, timeout):
            seen.append((url, headers, payload))
            return {"model": "actual/nim-model", "choices": [{"message": {"content": "synthetic " + NVIDIA_SENTINEL}}], "usage": {"total_tokens": 9}}
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {"NVIDIA_API_KEY": NVIDIA_SENTINEL}, clear=True):
            run = Path(directory) / "RUN"
            with self.assertRaisesRegex(ValueError, "explicit --model"):
                NvidiaNimProvider(run, None)
            provider = NvidiaNimProvider(run, "chosen/nim-model", caller=post)
            text = provider.ask_ai("hello", CONFIG)
            self.assertNotIn(NVIDIA_SENTINEL, text)
            provider.ask_ai("hello", CONFIG)
            self.assertEqual(len(seen), 1)
            self.assertEqual(seen[0][0], NVIDIA_ENDPOINT)
            self.assertEqual(seen[0][1]["Authorization"], "Bearer " + NVIDIA_SENTINEL)
            self.assertEqual(seen[0][2]["model"], "chosen/nim-model")
            receipts = [json.loads(path.read_text()) for path in (run / "handoff/receipts").glob("*.json")]
            response = next(row for row in receipts if row["status"] == "response_supplied")
            self.assertEqual(response["requested_model"], "chosen/nim-model")
            self.assertEqual(response["actual_model"], "actual/nim-model")
            self.assertEqual(response["usage"]["total_tokens"], 9)
            self.assertIsNone(response["cost"])
            for path in run.rglob("*.json"):
                self.assertNotIn(NVIDIA_SENTINEL, path.read_text())

    def test_nvidia_failure_and_missing_key_do_not_leak_or_retry(self):
        def fail(*args):
            raise RuntimeError("echo " + NVIDIA_SENTINEL)
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {"NVIDIA_API_KEY": NVIDIA_SENTINEL}, clear=True):
            run = Path(directory) / "RUN"
            provider = NvidiaNimProvider(run, "chosen/nim-model", caller=fail)
            with self.assertRaises(RuntimeError) as caught:
                provider.ask_ai("hello", CONFIG)
            self.assertNotIn(NVIDIA_SENTINEL, str(caught.exception))
            with self.assertRaisesRegex(RuntimeError, "not be silently resent"):
                provider.ask_ai("hello", CONFIG)
            for path in run.rglob("*.json"):
                self.assertNotIn(NVIDIA_SENTINEL, path.read_text())
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {}, clear=True):
            post = Mock()
            with self.assertRaisesRegex(RuntimeError, "NVIDIA_API_KEY is not configured"):
                NvidiaNimProvider(Path(directory) / "RUN", "chosen/nim-model", caller=post).ask_ai("hello", CONFIG)
            post.assert_not_called()
            result = check(provider="nvidia_nim")
            self.assertFalse(result["key_configured"])
            self.assertFalse(result["inference_performed"])
            self.assertIn("unknown", result["pricing"])


if __name__ == "__main__":
    unittest.main()
