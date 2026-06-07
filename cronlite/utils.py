"""Utility functions for CronLite."""

import hashlib
import secrets
import time
from datetime import datetime


def generate_id(prefix: str = "") -> str:
    """Generate a short unique ID using random bytes."""
    raw = secrets.token_hex(8)
    if prefix:
        return f"{prefix}_{raw}"
    return raw


def generate_job_id(name: str) -> str:
    """Generate a deterministic job ID from a name plus timestamp."""
    seed = f"{name}:{time.time_ns()}"
    digest = hashlib.sha256(seed.encode()).hexdigest()[:12]
    return f"job_{digest}"


def generate_execution_id() -> str:
    """Generate a unique execution ID."""
    return generate_id("exec")


def truncate_output(text: str, max_bytes: int = 10240) -> str:
    """Truncate output to max_bytes, keeping the end if truncated."""
    if len(text.encode("utf-8", errors="replace")) <= max_bytes:
        return text
    # Keep the last max_bytes worth of text
    encoded = text.encode("utf-8", errors="replace")
    truncated = encoded[-max_bytes:]
    return "[...truncated...]\n" + truncated.decode("utf-8", errors="replace")


def format_duration(ms: int | float | None) -> str:
    """Format duration in milliseconds to a human-readable string."""
    if ms is None:
        return "—"
    if ms < 1000:
        return f"{int(ms)}ms"
    seconds = ms / 1000
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes = seconds / 60
    if minutes < 60:
        return f"{int(minutes)}m {int(seconds % 60)}s"
    hours = minutes / 60
    return f"{int(hours)}h {int(minutes % 60)}m"


def format_datetime(dt: datetime | None) -> str:
    """Format a datetime for display."""
    if dt is None:
        return "—"
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def parse_duration(text: str) -> int:
    """Parse a duration string like '30s', '5m', '2h' to seconds."""
    text = text.strip().lower()
    if text.endswith("s"):
        return int(text[:-1])
    if text.endswith("m"):
        return int(text[:-1]) * 60
    if text.endswith("h"):
        return int(text[:-1]) * 3600
    if text.endswith("d"):
        return int(text[:-1]) * 86400
    # Assume seconds if no suffix
    return int(text)
