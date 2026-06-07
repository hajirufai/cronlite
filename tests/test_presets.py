"""Tests for named cron presets."""

import unittest

from cronlite.cron.presets import PRESETS, resolve_preset, is_preset


class TestPresets(unittest.TestCase):

    def test_daily_exists(self):
        self.assertIn("@daily", PRESETS)

    def test_hourly_exists(self):
        self.assertIn("@hourly", PRESETS)

    def test_weekly_exists(self):
        self.assertIn("@weekly", PRESETS)

    def test_monthly_exists(self):
        self.assertIn("@monthly", PRESETS)

    def test_yearly_exists(self):
        self.assertIn("@yearly", PRESETS)

    def test_annually_equals_yearly(self):
        self.assertEqual(PRESETS["@annually"], PRESETS["@yearly"])

    def test_midnight_equals_daily(self):
        self.assertEqual(PRESETS["@midnight"], PRESETS["@daily"])

    def test_resolve_preset_daily(self):
        self.assertEqual(resolve_preset("@daily"), "0 0 * * *")

    def test_resolve_preset_case_insensitive(self):
        self.assertEqual(resolve_preset("@DAILY"), "0 0 * * *")

    def test_resolve_preset_not_found(self):
        self.assertIsNone(resolve_preset("*/5 * * * *"))

    def test_is_preset_true(self):
        self.assertTrue(is_preset("@daily"))

    def test_is_preset_false(self):
        self.assertFalse(is_preset("* * * * *"))

    def test_is_preset_with_whitespace(self):
        self.assertTrue(is_preset("  @daily  "))


if __name__ == "__main__":
    unittest.main()
