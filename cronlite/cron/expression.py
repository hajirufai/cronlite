"""CronExpression — the compiled cron schedule.

Provides matches() to test if a datetime fits the schedule, and next_run()
to compute the next datetime that matches.
"""

from datetime import datetime, timedelta
import calendar

from cronlite.cron.fields import CronField, FieldType


# Maximum years to search forward when computing next_run.
# If no match is found within this window, the expression is effectively
# impossible (e.g., Feb 31).
_MAX_SEARCH_YEARS = 4


class CronExpression:
    """A compiled cron expression that can match times and compute schedules."""

    def __init__(
        self,
        minute: CronField,
        hour: CronField,
        day_of_month: CronField,
        month: CronField,
        day_of_week: CronField,
        raw: str = "",
    ):
        self.minute = minute
        self.hour = hour
        self.day_of_month = day_of_month
        self.month = month
        self.day_of_week = day_of_week
        self.raw = raw

    def matches(self, dt: datetime) -> bool:
        """Check if a datetime matches this cron expression.

        Per POSIX cron semantics:
        - If both day_of_month and day_of_week are restricted (not wildcards),
          the day matches if EITHER field matches (union).
        - If only one is restricted, the day must match that field.
        """
        if not self.minute.matches(dt.minute):
            return False
        if not self.hour.matches(dt.hour):
            return False
        if not self.month.matches(dt.month):
            return False

        # Day matching: POSIX union semantics
        dom_restricted = not self.day_of_month.is_wildcard
        dow_restricted = not self.day_of_week.is_wildcard

        if dom_restricted and dow_restricted:
            # Union: either day-of-month OR day-of-week must match
            return (
                self.day_of_month.matches(dt.day)
                or self.day_of_week.matches(self.weekday_sunday_zero(dt))
            )
        elif dom_restricted:
            return self.day_of_month.matches(dt.day)
        elif dow_restricted:
            return self.day_of_week.matches(self.weekday_sunday_zero(dt))
        else:
            # Both are wildcards — any day matches
            return True

    @staticmethod
    def weekday_sunday_zero(dt: datetime) -> int:
        """Convert Python's weekday (Mon=0) to cron's (Sun=0)."""
        # Python: Monday=0 ... Sunday=6
        # Cron:   Sunday=0 ... Saturday=6
        return (dt.weekday() + 1) % 7

    def next_run(self, after: datetime) -> datetime | None:
        """Compute the next datetime that matches this expression.

        Args:
            after: Start searching from this datetime (exclusive).

        Returns:
            The next matching datetime, or None if no match within 4 years.

        Algorithm:
            Walk forward from after+1min, checking fields from most-significant
            (month) to least (minute). When a field doesn't match, advance to
            the next matching value and reset all less-significant fields.
        """
        # Start from the next whole minute
        candidate = _truncate_to_minute(after) + timedelta(minutes=1)
        deadline = after + timedelta(days=_MAX_SEARCH_YEARS * 366)

        while candidate <= deadline:
            # --- Month ---
            if not self.month.matches(candidate.month):
                candidate = self._advance_month(candidate)
                if candidate is None or candidate > deadline:
                    return None
                continue

            # --- Day ---
            if not self._day_matches(candidate):
                candidate = candidate.replace(hour=0, minute=0) + timedelta(days=1)
                # If we rolled into a new month, loop to re-check month
                continue

            # --- Hour ---
            if not self.hour.matches(candidate.hour):
                next_hour = self._next_value(candidate.hour, self.hour.values)
                if next_hour is not None and next_hour > candidate.hour:
                    candidate = candidate.replace(hour=next_hour, minute=0)
                    # Re-check minute in next iteration
                    # Actually we can check minute now since we set it to 0
                    if self.minute.matches(0):
                        return candidate
                    # Advance to first matching minute
                    next_min = self._next_value(0, self.minute.values)
                    if next_min is not None:
                        candidate = candidate.replace(minute=next_min)
                        return candidate
                    # No matching minute — shouldn't happen since minute has values
                # Wrapped — advance to next day
                candidate = candidate.replace(hour=0, minute=0) + timedelta(days=1)
                continue

            # --- Minute ---
            if not self.minute.matches(candidate.minute):
                next_min = self._next_value(candidate.minute, self.minute.values)
                if next_min is not None and next_min > candidate.minute:
                    candidate = candidate.replace(minute=next_min)
                    return candidate
                # Wrapped — advance to next hour
                next_hour = self._next_value(candidate.hour + 1, self.hour.values)
                if next_hour is not None:
                    first_min = min(self.minute.values)
                    candidate = candidate.replace(hour=next_hour, minute=first_min)
                    # Need to re-check day since we're still on same day
                    continue
                # No more hours today — advance to next day
                candidate = candidate.replace(hour=0, minute=0) + timedelta(days=1)
                continue

            # All fields match
            return candidate

        return None

    def next_n_runs(self, after: datetime, n: int) -> list[datetime]:
        """Compute the next N matching datetimes."""
        results: list[datetime] = []
        current = after
        for _ in range(n):
            nxt = self.next_run(current)
            if nxt is None:
                break
            results.append(nxt)
            current = nxt
        return results

    def previous_run(self, before: datetime) -> datetime | None:
        """Compute the most recent datetime that matches, before the given time.

        Searches backward up to _MAX_SEARCH_YEARS.
        """
        candidate = _truncate_to_minute(before) - timedelta(minutes=1)
        deadline = before - timedelta(days=_MAX_SEARCH_YEARS * 366)

        while candidate >= deadline:
            if self.matches(candidate):
                return candidate
            candidate -= timedelta(minutes=1)
            # Optimisation: skip days that can't match
            if not self._day_matches(candidate) or not self.month.matches(
                candidate.month
            ):
                # Jump back to end of previous day
                candidate = candidate.replace(hour=23, minute=59) - timedelta(days=1)

        return None

    def explain(self) -> str:
        """Return a human-readable description of this expression."""
        parts: list[str] = []

        # Minute
        if self.minute.is_wildcard:
            parts.append("Every minute")
        else:
            vals = sorted(self.minute.values)
            if len(vals) == 1:
                parts.append(f"At minute {vals[0]}")
            else:
                # Check for step pattern
                step = _detect_step(vals, 0, 59)
                if step:
                    parts.append(f"Every {step} minutes")
                else:
                    parts.append(f"At minutes {', '.join(str(v) for v in vals)}")

        # Hour
        if not self.hour.is_wildcard:
            vals = sorted(self.hour.values)
            if len(vals) == 1:
                parts.append(f"at {vals[0]:02d}:00")
            elif vals == list(range(vals[0], vals[-1] + 1)):
                parts.append(
                    f"between {vals[0]:02d}:00 and {vals[-1]:02d}:59"
                )
            else:
                parts.append(
                    f"during hours {', '.join(str(v) for v in vals)}"
                )

        # Day of month
        if not self.day_of_month.is_wildcard:
            vals = sorted(self.day_of_month.values)
            parts.append(f"on day{'s' if len(vals) > 1 else ''} {', '.join(str(v) for v in vals)} of the month")

        # Month
        if not self.month.is_wildcard:
            month_names_map = [
                "", "January", "February", "March", "April", "May", "June",
                "July", "August", "September", "October", "November", "December",
            ]
            vals = sorted(self.month.values)
            names = [month_names_map[v] for v in vals]
            parts.append(f"in {', '.join(names)}")

        # Day of week
        if not self.day_of_week.is_wildcard:
            dow_names = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
            vals = sorted(self.day_of_week.values)
            names = [dow_names[v] for v in vals]
            if vals == list(range(1, 6)):
                parts.append("on weekdays")
            elif vals == [0, 6]:
                parts.append("on weekends")
            else:
                parts.append(f"on {', '.join(names)}")

        return ", ".join(parts) if parts else "Every minute"

    def _day_matches(self, dt: datetime) -> bool:
        """Check if the day (DOM + DOW) matches using POSIX semantics."""
        dom_restricted = not self.day_of_month.is_wildcard
        dow_restricted = not self.day_of_week.is_wildcard

        if dom_restricted and dow_restricted:
            return (
                self.day_of_month.matches(dt.day)
                or self.day_of_week.matches(self.weekday_sunday_zero(dt))
            )
        elif dom_restricted:
            return self.day_of_month.matches(dt.day)
        elif dow_restricted:
            return self.day_of_week.matches(self.weekday_sunday_zero(dt))
        return True

    def _advance_month(self, dt: datetime) -> datetime | None:
        """Advance to the first day of the next matching month."""
        year = dt.year
        month = dt.month + 1
        deadline_year = dt.year + _MAX_SEARCH_YEARS

        while year <= deadline_year:
            if month > 12:
                month = 1
                year += 1
            if self.month.matches(month):
                return datetime(year, month, 1, 0, 0)
            month += 1

        return None

    @staticmethod
    def _next_value(current: int, values: frozenset[int]) -> int | None:
        """Find the smallest value in the set >= current. Returns None if none."""
        candidates = [v for v in values if v >= current]
        return min(candidates) if candidates else None

    def __repr__(self) -> str:
        return f"CronExpression('{self.raw}')"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, CronExpression):
            return NotImplemented
        return (
            self.minute == other.minute
            and self.hour == other.hour
            and self.day_of_month == other.day_of_month
            and self.month == other.month
            and self.day_of_week == other.day_of_week
        )


def _truncate_to_minute(dt: datetime) -> datetime:
    """Truncate a datetime to the minute boundary."""
    return dt.replace(second=0, microsecond=0)


def _detect_step(values: list[int], range_min: int, range_max: int) -> int | None:
    """Detect if a sorted list of values follows a step pattern from range_min."""
    if len(values) < 2:
        return None
    step = values[1] - values[0]
    if step <= 0:
        return None
    expected = list(range(range_min, range_max + 1, step))
    if values == expected:
        return step
    return None
