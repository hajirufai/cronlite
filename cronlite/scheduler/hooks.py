"""Lifecycle hooks for job execution events."""

import logging

from cronlite.types import Job, Execution


logger = logging.getLogger("cronlite.hooks")


class JobHooks:
    """Base class for job lifecycle hooks. Override methods as needed."""

    def on_start(self, job: Job, execution: Execution) -> None:
        """Called when a job begins execution."""
        pass

    def on_success(self, job: Job, execution: Execution) -> None:
        """Called when a job finishes successfully (exit code 0)."""
        pass

    def on_failure(self, job: Job, execution: Execution, error: str) -> None:
        """Called when a job fails (non-zero exit or exception)."""
        pass

    def on_retry(self, job: Job, attempt: int, delay: float) -> None:
        """Called before a retry attempt, with the computed delay."""
        pass

    def on_timeout(self, job: Job, execution: Execution) -> None:
        """Called when a job exceeds its timeout."""
        pass

    def on_skip(self, job: Job, reason: str) -> None:
        """Called when a job is skipped (e.g., dependency not met)."""
        pass


class LoggingHooks(JobHooks):
    """Default hooks that log all events."""

    def on_start(self, job: Job, execution: Execution) -> None:
        logger.info(
            "Job started: %s [%s] (exec %s)",
            job.name, job.id, execution.id,
        )

    def on_success(self, job: Job, execution: Execution) -> None:
        duration = execution.duration_ms or 0
        logger.info(
            "Job succeeded: %s [%s] in %dms",
            job.name, job.id, duration,
        )

    def on_failure(self, job: Job, execution: Execution, error: str) -> None:
        logger.warning(
            "Job failed: %s [%s] — %s",
            job.name, job.id, error,
        )

    def on_retry(self, job: Job, attempt: int, delay: float) -> None:
        logger.info(
            "Job retry: %s [%s] attempt %d after %.1fs",
            job.name, job.id, attempt + 1, delay,
        )

    def on_timeout(self, job: Job, execution: Execution) -> None:
        logger.warning(
            "Job timeout: %s [%s] exceeded %ds",
            job.name, job.id, job.timeout_seconds,
        )

    def on_skip(self, job: Job, reason: str) -> None:
        logger.info(
            "Job skipped: %s [%s] — %s",
            job.name, job.id, reason,
        )
