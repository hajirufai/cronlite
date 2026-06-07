"""Cron expression parser.

Parses standard 5-field cron expressions into CronExpression objects.

Supported syntax per field:
    *          any value
    5          specific value
    1-5        range (inclusive)
    */15       step from start of range
    1-30/5     step within a range
    1,3,5,7    list of values
    1-5,10,*/2 combined list of ranges, values, steps

Month field accepts JAN-DEC (case-insensitive).
Day-of-week field accepts SUN-SAT (case-insensitive), 0 = Sunday.

Named presets: @yearly, @annually, @monthly, @weekly, @daily, @midnight, @hourly
"""

from cronlite.cron.expression import CronExpression
from cronlite.cron.fields import (
    MONTH_NAMES,
    DOW_NAMES,
    CronField,
    FieldType,
)
from cronlite.cron.presets import resolve_preset
from cronlite.errors import InvalidExpressionError, FieldRangeError


class CronParser:
    """Parses cron expression strings into CronExpression objects."""

    def parse(self, expression: str) -> CronExpression:
        """Parse a cron expression string.

        Args:
            expression: A 5-field cron string or a named preset (@daily, etc.)

        Returns:
            A CronExpression that can match datetimes and compute next_run.

        Raises:
            InvalidExpressionError: if the expression syntax is invalid.
            FieldRangeError: if a value is out of range for its field.
        """
        raw = expression.strip()
        if not raw:
            raise InvalidExpressionError("Empty cron expression")

        # Check for named presets
        preset = resolve_preset(raw)
        if preset is not None:
            raw = preset

        parts = raw.split()
        if len(parts) != 5:
            raise InvalidExpressionError(
                f"Expected 5 fields, got {len(parts)}: '{expression}'"
            )

        field_types = [
            FieldType.MINUTE,
            FieldType.HOUR,
            FieldType.DAY_OF_MONTH,
            FieldType.MONTH,
            FieldType.DAY_OF_WEEK,
        ]

        fields: list[CronField] = []
        for part, ftype in zip(parts, field_types):
            values = self._parse_field(part, ftype)
            fields.append(CronField(ftype, frozenset(values)))

        return CronExpression(
            minute=fields[0],
            hour=fields[1],
            day_of_month=fields[2],
            month=fields[3],
            day_of_week=fields[4],
            raw=expression.strip(),
        )

    def _parse_field(self, text: str, field_type: FieldType) -> set[int]:
        """Parse a single cron field into a set of matching values.

        Handles wildcards, ranges, steps, lists, and name aliases.
        """
        result: set[int] = set()

        # Split on comma for list support: "1,3,5" or "1-5,10,*/2"
        for part in text.split(","):
            part = part.strip()
            if not part:
                raise InvalidExpressionError(
                    f"Empty element in list for {field_type.label}: '{text}'"
                )
            result.update(self._parse_atom(part, field_type))

        return result

    def _parse_atom(self, text: str, field_type: FieldType) -> set[int]:
        """Parse a single atom: *, value, range, or step expression."""
        min_val = field_type.min_val
        max_val = field_type.max_val

        # Check for step: "*/2" or "1-10/3"
        if "/" in text:
            range_part, step_str = text.split("/", 1)
            step = self._parse_int(step_str, field_type)
            if step <= 0:
                raise InvalidExpressionError(
                    f"Step must be positive for {field_type.label}: '{text}'"
                )
            # Determine the range to step over
            if range_part == "*":
                start, end = min_val, max_val
            elif "-" in range_part:
                start, end = self._parse_range_bounds(range_part, field_type)
            else:
                start = self._parse_int(range_part, field_type)
                end = max_val
            self._check_bounds(start, field_type)
            self._check_bounds(end, field_type)
            return set(range(start, end + 1, step))

        # Wildcard
        if text == "*":
            return set(range(min_val, max_val + 1))

        # Range: "1-5"
        if "-" in text:
            start, end = self._parse_range_bounds(text, field_type)
            self._check_bounds(start, field_type)
            self._check_bounds(end, field_type)
            return set(range(start, end + 1))

        # Single value
        val = self._parse_int(text, field_type)
        self._check_bounds(val, field_type)
        return {val}

    def _parse_range_bounds(
        self, text: str, field_type: FieldType
    ) -> tuple[int, int]:
        """Parse 'start-end' into (start, end) integers."""
        parts = text.split("-", 1)
        if len(parts) != 2 or not parts[0] or not parts[1]:
            raise InvalidExpressionError(
                f"Invalid range for {field_type.label}: '{text}'"
            )
        start = self._parse_int(parts[0], field_type)
        end = self._parse_int(parts[1], field_type)
        if start > end:
            raise InvalidExpressionError(
                f"Range start ({start}) > end ({end}) for {field_type.label}: '{text}'"
            )
        return start, end

    def _parse_int(self, text: str, field_type: FieldType) -> int:
        """Parse a string to an integer, handling name aliases for months/days."""
        upper = text.upper()

        if field_type == FieldType.MONTH and upper in MONTH_NAMES:
            return MONTH_NAMES[upper]
        if field_type == FieldType.DAY_OF_WEEK and upper in DOW_NAMES:
            return DOW_NAMES[upper]

        try:
            return int(text)
        except ValueError:
            raise InvalidExpressionError(
                f"Invalid value for {field_type.label}: '{text}'"
            )

    def _check_bounds(self, value: int, field_type: FieldType) -> None:
        """Validate that a value is within the field's allowed range."""
        if value < field_type.min_val or value > field_type.max_val:
            raise FieldRangeError(
                field_type.label, value, field_type.min_val, field_type.max_val
            )
