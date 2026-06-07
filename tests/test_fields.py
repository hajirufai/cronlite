"""Tests for cron field types and validation."""

import unittest

from cronlite.cron.fields import CronField, FieldType
from cronlite.errors import FieldRangeError


class TestCronField(unittest.TestCase):
    """Test CronField creation, matching, and validation."""

    def test_minute_matches(self):
        field = CronField(FieldType.MINUTE, frozenset({0, 15, 30, 45}))
        self.assertTrue(field.matches(0))
        self.assertTrue(field.matches(15))
        self.assertTrue(field.matches(30))
        self.assertTrue(field.matches(45))
        self.assertFalse(field.matches(1))
        self.assertFalse(field.matches(59))

    def test_hour_matches(self):
        field = CronField(FieldType.HOUR, frozenset({9, 10, 11, 12, 13, 14, 15, 16, 17}))
        self.assertTrue(field.matches(9))
        self.assertTrue(field.matches(17))
        self.assertFalse(field.matches(8))
        self.assertFalse(field.matches(18))

    def test_day_of_month_matches(self):
        field = CronField(FieldType.DAY_OF_MONTH, frozenset({1, 15}))
        self.assertTrue(field.matches(1))
        self.assertTrue(field.matches(15))
        self.assertFalse(field.matches(2))

    def test_month_matches(self):
        field = CronField(FieldType.MONTH, frozenset({1, 6, 12}))
        self.assertTrue(field.matches(1))
        self.assertTrue(field.matches(6))
        self.assertFalse(field.matches(3))

    def test_day_of_week_matches(self):
        field = CronField(FieldType.DAY_OF_WEEK, frozenset({1, 2, 3, 4, 5}))
        self.assertTrue(field.matches(1))  # Monday
        self.assertTrue(field.matches(5))  # Friday
        self.assertFalse(field.matches(0))  # Sunday
        self.assertFalse(field.matches(6))  # Saturday

    def test_wildcard_minute(self):
        field = CronField(FieldType.MINUTE, frozenset(range(0, 60)))
        self.assertTrue(field.is_wildcard)

    def test_not_wildcard(self):
        field = CronField(FieldType.MINUTE, frozenset({0}))
        self.assertFalse(field.is_wildcard)

    def test_wildcard_hour(self):
        field = CronField(FieldType.HOUR, frozenset(range(0, 24)))
        self.assertTrue(field.is_wildcard)

    def test_wildcard_day_of_month(self):
        field = CronField(FieldType.DAY_OF_MONTH, frozenset(range(1, 32)))
        self.assertTrue(field.is_wildcard)

    def test_invalid_minute_too_high(self):
        with self.assertRaises(FieldRangeError):
            CronField(FieldType.MINUTE, frozenset({60}))

    def test_invalid_minute_negative(self):
        with self.assertRaises(FieldRangeError):
            CronField(FieldType.MINUTE, frozenset({-1}))

    def test_invalid_hour_too_high(self):
        with self.assertRaises(FieldRangeError):
            CronField(FieldType.HOUR, frozenset({24}))

    def test_invalid_day_of_month_zero(self):
        with self.assertRaises(FieldRangeError):
            CronField(FieldType.DAY_OF_MONTH, frozenset({0}))

    def test_invalid_month_13(self):
        with self.assertRaises(FieldRangeError):
            CronField(FieldType.MONTH, frozenset({13}))

    def test_invalid_dow_7(self):
        with self.assertRaises(FieldRangeError):
            CronField(FieldType.DAY_OF_WEEK, frozenset({7}))

    def test_field_equality(self):
        a = CronField(FieldType.MINUTE, frozenset({0, 30}))
        b = CronField(FieldType.MINUTE, frozenset({0, 30}))
        self.assertEqual(a, b)

    def test_field_inequality(self):
        a = CronField(FieldType.MINUTE, frozenset({0, 30}))
        b = CronField(FieldType.MINUTE, frozenset({0, 15}))
        self.assertNotEqual(a, b)

    def test_repr(self):
        field = CronField(FieldType.MINUTE, frozenset({0, 15}))
        self.assertIn("minute", repr(field))


class TestFieldType(unittest.TestCase):
    """Test FieldType enum ranges."""

    def test_minute_range(self):
        self.assertEqual(FieldType.MINUTE.min_val, 0)
        self.assertEqual(FieldType.MINUTE.max_val, 59)

    def test_hour_range(self):
        self.assertEqual(FieldType.HOUR.min_val, 0)
        self.assertEqual(FieldType.HOUR.max_val, 23)

    def test_day_of_month_range(self):
        self.assertEqual(FieldType.DAY_OF_MONTH.min_val, 1)
        self.assertEqual(FieldType.DAY_OF_MONTH.max_val, 31)

    def test_month_range(self):
        self.assertEqual(FieldType.MONTH.min_val, 1)
        self.assertEqual(FieldType.MONTH.max_val, 12)

    def test_day_of_week_range(self):
        self.assertEqual(FieldType.DAY_OF_WEEK.min_val, 0)
        self.assertEqual(FieldType.DAY_OF_WEEK.max_val, 6)


if __name__ == "__main__":
    unittest.main()
