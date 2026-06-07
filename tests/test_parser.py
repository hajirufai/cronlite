"""Tests for the cron expression parser."""

import unittest

from cronlite.cron.parser import CronParser
from cronlite.cron.fields import FieldType
from cronlite.errors import InvalidExpressionError, FieldRangeError


class TestCronParser(unittest.TestCase):
    """Test cron expression parsing."""

    def setUp(self):
        self.parser = CronParser()

    # --- Valid expressions ---

    def test_all_wildcards(self):
        expr = self.parser.parse("* * * * *")
        self.assertTrue(expr.minute.is_wildcard)
        self.assertTrue(expr.hour.is_wildcard)
        self.assertTrue(expr.day_of_month.is_wildcard)
        self.assertTrue(expr.month.is_wildcard)
        self.assertTrue(expr.day_of_week.is_wildcard)

    def test_specific_values(self):
        expr = self.parser.parse("30 14 1 6 3")
        self.assertEqual(expr.minute.values, frozenset({30}))
        self.assertEqual(expr.hour.values, frozenset({14}))
        self.assertEqual(expr.day_of_month.values, frozenset({1}))
        self.assertEqual(expr.month.values, frozenset({6}))
        self.assertEqual(expr.day_of_week.values, frozenset({3}))

    def test_range(self):
        expr = self.parser.parse("0-30 * * * *")
        self.assertEqual(expr.minute.values, frozenset(range(0, 31)))

    def test_step_from_wildcard(self):
        expr = self.parser.parse("*/15 * * * *")
        self.assertEqual(expr.minute.values, frozenset({0, 15, 30, 45}))

    def test_step_from_range(self):
        expr = self.parser.parse("1-30/5 * * * *")
        self.assertEqual(expr.minute.values, frozenset({1, 6, 11, 16, 21, 26}))

    def test_step_from_value(self):
        expr = self.parser.parse("5/10 * * * *")
        self.assertEqual(expr.minute.values, frozenset({5, 15, 25, 35, 45, 55}))

    def test_list(self):
        expr = self.parser.parse("1,15,30,45 * * * *")
        self.assertEqual(expr.minute.values, frozenset({1, 15, 30, 45}))

    def test_combined_list_and_range(self):
        expr = self.parser.parse("1-5,10,20-25 * * * *")
        expected = frozenset({1, 2, 3, 4, 5, 10, 20, 21, 22, 23, 24, 25})
        self.assertEqual(expr.minute.values, expected)

    def test_hour_range(self):
        expr = self.parser.parse("0 9-17 * * *")
        self.assertEqual(expr.hour.values, frozenset(range(9, 18)))

    def test_every_two_hours(self):
        expr = self.parser.parse("0 */2 * * *")
        self.assertEqual(expr.hour.values, frozenset({0, 2, 4, 6, 8, 10, 12, 14, 16, 18, 20, 22}))

    # --- Month names ---

    def test_month_name_jan(self):
        expr = self.parser.parse("0 0 1 JAN *")
        self.assertEqual(expr.month.values, frozenset({1}))

    def test_month_name_range(self):
        expr = self.parser.parse("0 0 1 JAN-MAR *")
        self.assertEqual(expr.month.values, frozenset({1, 2, 3}))

    def test_month_name_list(self):
        expr = self.parser.parse("0 0 1 JAN,APR,JUL,OCT *")
        self.assertEqual(expr.month.values, frozenset({1, 4, 7, 10}))

    def test_month_name_case_insensitive(self):
        expr = self.parser.parse("0 0 1 jan *")
        self.assertEqual(expr.month.values, frozenset({1}))

    # --- Day-of-week names ---

    def test_dow_name_mon(self):
        expr = self.parser.parse("0 0 * * MON")
        self.assertEqual(expr.day_of_week.values, frozenset({1}))

    def test_dow_name_range(self):
        expr = self.parser.parse("0 0 * * MON-FRI")
        self.assertEqual(expr.day_of_week.values, frozenset({1, 2, 3, 4, 5}))

    def test_dow_name_sun(self):
        expr = self.parser.parse("0 0 * * SUN")
        self.assertEqual(expr.day_of_week.values, frozenset({0}))

    def test_dow_name_case_insensitive(self):
        expr = self.parser.parse("0 0 * * mon-fri")
        self.assertEqual(expr.day_of_week.values, frozenset({1, 2, 3, 4, 5}))

    # --- Presets ---

    def test_preset_daily(self):
        expr = self.parser.parse("@daily")
        self.assertEqual(expr.minute.values, frozenset({0}))
        self.assertEqual(expr.hour.values, frozenset({0}))
        self.assertTrue(expr.day_of_month.is_wildcard)

    def test_preset_hourly(self):
        expr = self.parser.parse("@hourly")
        self.assertEqual(expr.minute.values, frozenset({0}))
        self.assertTrue(expr.hour.is_wildcard)

    def test_preset_weekly(self):
        expr = self.parser.parse("@weekly")
        self.assertEqual(expr.minute.values, frozenset({0}))
        self.assertEqual(expr.hour.values, frozenset({0}))
        self.assertEqual(expr.day_of_week.values, frozenset({0}))

    def test_preset_monthly(self):
        expr = self.parser.parse("@monthly")
        self.assertEqual(expr.day_of_month.values, frozenset({1}))

    def test_preset_yearly(self):
        expr = self.parser.parse("@yearly")
        self.assertEqual(expr.month.values, frozenset({1}))
        self.assertEqual(expr.day_of_month.values, frozenset({1}))

    def test_preset_midnight(self):
        expr = self.parser.parse("@midnight")
        self.assertEqual(expr.minute.values, frozenset({0}))
        self.assertEqual(expr.hour.values, frozenset({0}))

    def test_preset_annually(self):
        expr = self.parser.parse("@annually")
        self.assertEqual(expr.month.values, frozenset({1}))

    # --- Invalid expressions ---

    def test_empty_string(self):
        with self.assertRaises(InvalidExpressionError):
            self.parser.parse("")

    def test_too_few_fields(self):
        with self.assertRaises(InvalidExpressionError):
            self.parser.parse("* * *")

    def test_too_many_fields(self):
        with self.assertRaises(InvalidExpressionError):
            self.parser.parse("* * * * * *")

    def test_invalid_value_text(self):
        with self.assertRaises(InvalidExpressionError):
            self.parser.parse("abc * * * *")

    def test_minute_out_of_range(self):
        with self.assertRaises(FieldRangeError):
            self.parser.parse("60 * * * *")

    def test_hour_out_of_range(self):
        with self.assertRaises(FieldRangeError):
            self.parser.parse("0 24 * * *")

    def test_day_of_month_zero(self):
        with self.assertRaises(FieldRangeError):
            self.parser.parse("0 0 0 * *")

    def test_day_of_month_32(self):
        with self.assertRaises(FieldRangeError):
            self.parser.parse("0 0 32 * *")

    def test_month_zero(self):
        with self.assertRaises(FieldRangeError):
            self.parser.parse("0 0 1 0 *")

    def test_month_13(self):
        with self.assertRaises(FieldRangeError):
            self.parser.parse("0 0 1 13 *")

    def test_dow_7(self):
        with self.assertRaises(FieldRangeError):
            self.parser.parse("0 0 * * 7")

    def test_range_inverted(self):
        with self.assertRaises(InvalidExpressionError):
            self.parser.parse("30-10 * * * *")

    def test_step_zero(self):
        with self.assertRaises(InvalidExpressionError):
            self.parser.parse("*/0 * * * *")

    def test_step_negative(self):
        with self.assertRaises(InvalidExpressionError):
            self.parser.parse("*/-1 * * * *")

    def test_empty_list_element(self):
        with self.assertRaises(InvalidExpressionError):
            self.parser.parse(",5 * * * *")

    def test_raw_stored(self):
        expr = self.parser.parse("*/5 * * * *")
        self.assertEqual(expr.raw, "*/5 * * * *")

    # --- Complex expressions ---

    def test_business_hours(self):
        expr = self.parser.parse("*/15 9-17 * * MON-FRI")
        self.assertEqual(expr.minute.values, frozenset({0, 15, 30, 45}))
        self.assertEqual(expr.hour.values, frozenset(range(9, 18)))
        self.assertEqual(expr.day_of_week.values, frozenset({1, 2, 3, 4, 5}))

    def test_biweekly_on_first_and_fifteenth(self):
        expr = self.parser.parse("0 0 1,15 * *")
        self.assertEqual(expr.day_of_month.values, frozenset({1, 15}))

    def test_quarterly(self):
        expr = self.parser.parse("0 0 1 1,4,7,10 *")
        self.assertEqual(expr.month.values, frozenset({1, 4, 7, 10}))


if __name__ == "__main__":
    unittest.main()
