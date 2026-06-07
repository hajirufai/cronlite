"""Named cron schedule presets."""

# Standard cron presets
PRESETS: dict[str, str] = {
    "@yearly": "0 0 1 1 *",
    "@annually": "0 0 1 1 *",
    "@monthly": "0 0 1 * *",
    "@weekly": "0 0 * * 0",
    "@daily": "0 0 * * *",
    "@midnight": "0 0 * * *",
    "@hourly": "0 * * * *",
}


def resolve_preset(expression: str) -> str | None:
    """If the expression is a named preset, return its cron string.

    Returns None if not a preset.
    """
    return PRESETS.get(expression.strip().lower())


def is_preset(expression: str) -> bool:
    """Check if the expression is a named preset."""
    return expression.strip().lower() in PRESETS
