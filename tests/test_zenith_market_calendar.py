"""Regression checks for the extracted engine's exchange-close horizon."""
from datetime import datetime, timezone
import unittest

from system.core.engine import GodModeEngine


class MarketCalendarTests(unittest.TestCase):
    def target(self, anchor):
        return GodModeEngine.resolve_horizon("next_us_close", datetime.fromisoformat(anchor))

    def test_thanksgiving_skips_closed_session(self):
        receipt = self.target("2026-11-26T12:00:00+00:00")
        self.assertEqual(receipt["target_time"], "2026-11-27T18:00:00+00:00")
        self.assertEqual(receipt["target_time_et"], "2026-11-27T13:00:00-05:00")
        self.assertIn("01:00 PM", receipt["horizon_label"])

    def test_early_close_rolls_to_next_session_at_exact_boundary(self):
        self.assertEqual(self.target("2026-11-27T17:59:59+00:00")["target_time"], "2026-11-27T18:00:00+00:00")
        self.assertEqual(self.target("2026-11-27T18:00:00+00:00")["target_time"], "2026-11-30T21:00:00+00:00")

    def test_march_dst_changes_utc_close(self):
        self.assertEqual(self.target("2026-03-06T12:00:00+00:00")["target_time"], "2026-03-06T21:00:00+00:00")
        self.assertEqual(self.target("2026-03-08T12:00:00+00:00")["target_time"], "2026-03-09T20:00:00+00:00")

    def test_naive_anchor_refused(self):
        with self.assertRaisesRegex(ValueError, "explicit timezone"):
            GodModeEngine.resolve_horizon("next_us_close", datetime(2026, 11, 26, 12))
