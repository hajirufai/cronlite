"""Custom exceptions for CronLite."""


class CronLiteError(Exception):
    """Base exception for all CronLite errors."""
    pass


class ParseError(CronLiteError):
    """Invalid cron expression syntax."""
    pass


class FieldRangeError(ParseError):
    """Value out of valid range for a cron field."""

    def __init__(self, field_name: str, value: int, min_val: int, max_val: int):
        self.field_name = field_name
        self.value = value
        self.min_val = min_val
        self.max_val = max_val
        super().__init__(
            f"{field_name}: value {value} is out of range [{min_val}-{max_val}]"
        )


class InvalidExpressionError(ParseError):
    """Malformed cron expression."""
    pass


class JobNotFoundError(CronLiteError):
    """Job with the given ID does not exist."""
    pass


class DuplicateJobError(CronLiteError):
    """A job with this name already exists."""
    pass


class CyclicDependencyError(CronLiteError):
    """Job dependency graph contains a cycle."""
    pass


class ExecutionError(CronLiteError):
    """Job command execution failed."""
    pass


class JobTimeoutError(ExecutionError):
    """Job exceeded its configured timeout."""
    pass


class SchedulerError(CronLiteError):
    """Internal scheduler error."""
    pass


class StoreError(CronLiteError):
    """Storage backend error."""
    pass
