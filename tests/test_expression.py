"""Tests for CronExpression matching and next_run computation."""

import unittest
from datetime import datetime

from cronlite.cron.parser import CronParser


class TestCronExpressionMatches(unittest.TestCase):
    """Test CronExpression.matches()."""

    def setUp(self):
        self.parser = CronParser()

    def test_every_minute_matches_any(self):
        expr = self.parser.parse("* * * * *")
        dt = datetime(2026, 6, 1, 12, 30)
        self.assertTrue(expr.matches(dt))

    def test_specific_minute(self):
        expr = self.parser.parse("30 * * * *")
        self.assertTrue(expr.matches(datetime(2026, 6, 1, 12, 30)))
        self.assertFalse(expr.matches(datetime(2026, 6, 1, 12, 15)))

    def test_specific_hour(self):
        expr = self.parser.parse("0 14 * * *")
        self.assertTrue(expr.matches(datetime(2026, 6, 1, 14, 0)))
        self.assertFalse(expr.matches(datetime(2026, 6, 1, 13, 0)))

    def test_specific_day_of_month(self):
        expr = self.parser.parse("0 0 15 * *")
        self.assertTrue(expr.matches(datetime(2026, 6, 15, 0, 0)))
        self.assertFalse(expr.matches(datetime(2026, 6, 14, 0, 0)))

    def test_specific_month(self):
        expr = self.parser.parse("0 0 1 6 *")
        self.assertTrue(expr.matches(datetime(2026, 6, 1, 0, 0)))
        self.assertFalse(expr.matches(datetime(2026, 7, 1, 0, 0)))

    def test_specific_day_of_week(self):
        # 2026-06-01 is a Monday (weekday=0 in Python, dow=1 in cron)
        expr = self.parser.parse("0 0 * * 1")  # Monday
        self.assertTrue(expr.matches(datetime(2026, 6, 1, 0, 0)))
        self.assertFalse(expr.matches(datetime(2026, 6, 2, 0, 0)))  # Tuesday

    def test_dow_sunday_zero(self):
        # 2026-06-07 is a Sunday (weekday=6 in Python, dow=0 in cron)
        expr = self.parser.parse("0 0 * * 0")  # Sunday
        self.assertTrue(expr.matches(datetime(2026, 6, 7, 0, 0)))

    def test_posix_union_both_restricted(self):
        """When both DOM and DOW are restricted, match is a union (OR)."""
        # Match on 1st of month OR on Mondays
        expr = self.parser.parse("0 0 1 * 1")
        # June 1 is Monday — matches both
        self.assertTrue(expr.matches(datetime(2026, 6, 1, 0, 0)))
        # June 8 is Monday — matches DOW
        self.assertTrue(expr.matches(datetime(2026, 6, 8, 0, 0)))
        # June 15 is Monday — matches DOW
        self.assertTrue(expr.matches(datetime(2026, 6, 15, 0, 0)))
        # July 1 is Wednesday — matches DOM
        self.assertTrue(expr.matches(datetime(2026, 7, 1, 0, 0)))
        # June 2 is Tuesday, not 1st — no match
        self.assertFalse(expr.matches(datetime(2026, 6, 2, 0, 0)))

    def test_hour_range(self):
        expr = self.parser.parse("0 9-17 * * *")
        self.assertTrue(expr.matches(datetime(2026, 6, 1, 9, 0)))
        self.assertTrue(expr.matches(datetime(2026, 6, 1, 17, 0)))
        self.assertFalse(expr.matches(datetime(2026, 6, 1, 8, 0)))
        self.assertFalse(expr.matches(datetime(2026, 6, 1, 18, 0)))

    def test_every_15_minutes(self):
        expr = self.parser.parse("*/15 * * * *")
        self.assertTrue(expr.matches(datetime(2026, 6, 1, 12, 0)))
        self.assertTrue(expr.matches(datetime(2026, 6, 1, 12, 15)))
        self.assertTrue(expr.matches(datetime(2026, 6, 1, 12, 30)))
        self.assertTrue(expr.matches(datetime(2026, 6, 1, 12, 45)))
        self.assertFalse(expr.matches(datetime(2026, 6, 1, 12, 10)))


class TestCronExpressionNextRun(unittest.TestCase):
    """Test CronExpression.next_run() computation."""

    def setUp(self):
        self.parser = CronParser()

    def test_every_minute(self):
        expr = self.parser.parse("* * * * *")
        after = datetime(2026, 6, 1, 12, 30, 0)
        result = expr.next_run(after)
        self.assertEqual(result, datetime(2026, 6, 1, 12, 31, 0))

    def test_specific_minute_same_hour(self):
        expr = self.parser.parse("45 * * * *")
        after = datetime(2026, 6, 1, 12, 30, 0)
        result = expr.next_run(after)
        self.assertEqual(result, datetime(2026, 6, 1, 12, 45, 0))

    def test_specific_minute_next_hour(self):
        expr = self.parser.parse("15 * * * *")
        after = datetime(2026, 6, 1, 12, 30, 0)
        result = expr.next_run(after)
        self.assertEqual(result, datetime(2026, 6, 1, 13, 15, 0))

    def test_daily_at_2am(self):
        expr = self.parser.parse("0 2 * * *")
        after = datetime(2026, 6, 1, 3, 0, 0)
        result = expr.next_run(after)
        self.assertEqual(result, datetime(2026, 6, 2, 2, 0, 0))

    def test_daily_at_2am_before_time(self):
        expr = self.parser.parse("0 2 * * *")
        after = datetime(2026, 6, 1, 1, 0, 0)
        result = expr.next_run(after)
        self.assertEqual(result, datetime(2026, 6, 1, 2, 0, 0))

    def test_monthly_first_day(self):
        expr = self.parser.parse("0 0 1 * *")
        after = datetime(2026, 6, 2, 0, 0, 0)
        result = expr.next_run(after)
        self.assertEqual(result, datetime(2026, 7, 1, 0, 0, 0))

    def test_yearly_jan_1(self):
        expr = self.parser.parse("0 0 1 1 *")
        after = datetime(2026, 6, 1, 0, 0, 0)
        result = expr.next_run(after)
        self.assertEqual(result, datetime(2027, 1, 1, 0, 0, 0))

    def test_weekday_only(self):
        # 2026-06-01 is Monday, asking for Friday (5)
        expr = self.parser.parse("0 0 * * 5")
        after = datetime(2026, 6, 1, 0, 0, 0)
        result = expr.next_run(after)
        self.assertEqual(result, datetime(2026, 6, 5, 0, 0, 0))
        self.assertEqual(result.weekday(), 4)  # Python Friday = 4

    def test_every_15_min(self):
        expr = self.parser.parse("*/15 * * * *")
        after = datetime(2026, 6, 1, 12, 16, 0)
        result = expr.next_run(after)
        self.assertEqual(result, datetime(2026, 6, 1, 12, 30, 0))

    def test_business_hours_after_hours(self):
        expr = self.parser.parse("0 9-17 * * MON-FRI")
        # After business hours on a Friday
        after = datetime(2026, 6, 5, 18, 0, 0)  # Friday 6pm
        result = expr.next_run(after)
        # Next Monday at 9am
        self.assertEqual(result, datetime(2026, 6, 8, 9, 0, 0))

    def test_next_run_exclusive(self):
        """next_run should return a time strictly after the given time."""
        expr = self.parser.parse("30 12 * * *")
        after = datetime(2026, 6, 1, 12, 30, 0)
        result = expr.next_run(after)
        # Should skip to next day since we're exactly AT the match time
        self.assertEqual(result, datetime(2026, 6, 2, 12, 30, 0))

    def test_month_boundary(self):
        expr = self.parser.parse("0 0 * * *")
        after = datetime(2026, 6, 30, 23, 59, 0)
        result = expr.next_run(after)
        self.assertEqual(result, datetime(2026, 7, 1, 0, 0, 0))

    def test_year_boundary(self):
        expr = self.parser.parse("0 0 * * *")
        after = datetime(2026, 12, 31, 23, 59, 0)
        result = expr.next_run(after)
        self.assertEqual(result, datetime(2027, 1, 1, 0, 0, 0))

    def test_leap_year_feb_29(self):
        expr = self.parser.parse("0 0 29 2 *")
        after = datetime(2026, 1, 1, 0, 0, 0)
        result = expr.next_run(after)
        # 2028 is the next leap year
        self.assertIsNotNone(result)
        self.assertEqual(result.month, 2)
        self.assertEqual(result.day, 29)

    def test_next_n_runs(self):
        expr = self.parser.parse("0 * * * *")
        after = datetime(2026, 6, 1, 12, 0, 0)
        runs = expr.next_n_runs(after, 3)
        self.assertEqual(len(runs), 3)
        self.assertEqual(runs[0], datetime(2026, 6, 1, 13, 0, 0))
        self.assertEqual(runs[1], datetime(2026, 6, 1, 14, 0, 0))
        self.assertEqual(runs[2], datetime(2026, 6, 1, 15, 0, 0))


class TestCronExpressionExplain(unittest.TestCase):
    """Test human-readable explanation."""

    def setUp(self):
        self.parser = CronParser()

    def test_every_minute(self):
        expr = self.parser.parse("* * * * *")
        desc = expr.explain()
        self.assertIn("Every minute", desc)

    def test_every_15_minutes(self):
        expr = self.parser.parse("*/15 * * * *")
        desc = expr.explain()
        self.assertIn("15 minutes", desc)

    def test_daily(self):
        expr = self.parser.parse("0 0 * * *")
        desc = expr.explain()
        self.assertIn("minute 0", desc.lower())

    def test_weekdays(self):
        expr = self.parser.parse("0 9 * * MON-FRI")
        desc = expr.explain()
        self.assertIn("weekdays", desc.lower())

    def test_specific_month(self):
        expr = self.parser.parse("0 0 1 JAN *")
        desc = expr.explain()
        self.assertIn("January", desc)


class TestCronExpressionPreviousRun(unittest.TestCase):
    """Test CronExpression.previous_run()."""

    def setUp(self):
        self.parser = CronParser()

    def test_previous_every_hour(self):
        expr = self.parser.parse("0 * * * *")
        before = datetime(2026, 6, 1, 12, 30, 0)
        result = expr.previous_run(before)
        self.assertEqual(result, datetime(2026, 6, 1, 12, 0, 0))

    def test_previous_daily(self):
        expr = self.parser.parse("0 0 * * *")
        before = datetime(2026, 6, 1, 12, 0, 0)
        result = expr.previous_run(before)
        self.assertEqual(result, datetime(2026, 6, 1, 0, 0, 0))


if __name__ == "__main__":
    unittest.main()
