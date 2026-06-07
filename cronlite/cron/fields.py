"""Cron field types and validation."""

from enum import Enum

from cronlite.errors import FieldRangeError


# Month and day-of-week name mappings
MONTH_NAMES = {
    "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
    "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12,
}

DOW_NAMES = {
    "SUN": 0, "MON": 1, "TUE": 2, "WED": 3,
    "THU": 4, "FRI": 5, "SAT": 6,
}


class FieldType(Enum):
    """Cron field types with their valid ranges."""
    MINUTE = ("minute", 0, 59)
    HOUR = ("hour", 0, 23)
    DAY_OF_MONTH = ("day_of_month", 1, 31)
    MONTH = ("month", 1, 12)
    DAY_OF_WEEK = ("day_of_week", 0, 6)

    def __init__(self, label: str, min_val: int, max_val: int):
        self.label = label
        self.min_val = min_val
        self.max_val = max_val


class CronField:
    """A single parsed cron field with a set of matching integer values."""

    def __init__(self, field_type: FieldType, values: frozenset[int]):
        self.field_type = field_type
        self.values = values
        self._validate()

    def _validate(self) -> None:
        ft = self.field_type
        for v in self.values:
            if v < ft.min_val or v > ft.max_val:
                raise FieldRangeError(ft.label, v, ft.min_val, ft.max_val)

    def matches(self, value: int) -> bool:
        """Check if a value matches this field."""
        return value in self.values

    @property
    def is_wildcard(self) -> bool:
        """True if this field matches every value in its range."""
        ft = self.field_type
        return self.values == frozenset(range(ft.min_val, ft.max_val + 1))

    def __repr__(self) -> str:
        return f"CronField({self.field_type.label}, {sorted(self.values)})"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, CronField):
            return NotImplemented
        return self.field_type == other.field_type and self.values == other.values
