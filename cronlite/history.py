"""Execution history queries and analytics."""

from datetime import datetime

from cronlite.store import Store
from cronlite.types import Execution, JobState


class ExecutionHistory:
    """Query and analyze past job executions."""

    def __init__(self, store: Store):
        self._store = store

    def get_last_n(self, job_id: str, n: int = 10) -> list[Execution]:
        """Get the last N executions for a job."""
        return self._store.get_executions(job_id=job_id, limit=n)

    def get_recent(self, limit: int = 50) -> list[Execution]:
        """Get the most recent executions across all jobs."""
        return self._store.get_executions(limit=limit)

    def get_by_state(self, state: JobState, limit: int = 50) -> list[Execution]:
        """Get executions filtered by state."""
        all_execs = self._store.get_executions(limit=limit * 3)
        return [e for e in all_execs if e.state == state][:limit]

    def get_timeline(
        self, start: datetime, end: datetime, job_id: str | None = None
    ) -> list[Execution]:
        """Get executions within a time range."""
        execs = self._store.get_executions(job_id=job_id, limit=10000)
        return [
            e for e in execs
            if start <= e.started_at <= end
        ]

    def get_stats(self, job_id: str | None = None) -> dict:
        """Compute statistics for a job or all jobs.

        Returns:
            Dict with success_count, failure_count, timeout_count,
            total_count, success_rate, avg_duration_ms, min_duration_ms,
            max_duration_ms, last_run, last_success, last_failure.
        """
        execs = self._store.get_executions(job_id=job_id, limit=10000)

        if not execs:
            return {
                "total_count": 0,
                "success_count": 0,
                "failure_count": 0,
                "timeout_count": 0,
                "success_rate": 0.0,
                "avg_duration_ms": 0.0,
                "min_duration_ms": None,
                "max_duration_ms": None,
                "last_run": None,
                "last_success": None,
                "last_failure": None,
            }

        success = [e for e in execs if e.state == JobState.SUCCESS]
        failed = [e for e in execs if e.state == JobState.FAILED]
        timeout = [e for e in execs if e.state == JobState.TIMEOUT]

        durations = [e.duration_ms for e in execs if e.duration_ms is not None]

        last_run = max(execs, key=lambda e: e.started_at).started_at
        last_success = (
            max(success, key=lambda e: e.started_at).started_at if success else None
        )
        last_failure = (
            max(failed + timeout, key=lambda e: e.started_at).started_at
            if (failed or timeout) else None
        )

        return {
            "total_count": len(execs),
            "success_count": len(success),
            "failure_count": len(failed),
            "timeout_count": len(timeout),
            "success_rate": (
                len(success) / len(execs) * 100 if execs else 0.0
            ),
            "avg_duration_ms": (
                sum(durations) / len(durations) if durations else 0.0
            ),
            "min_duration_ms": min(durations) if durations else None,
            "max_duration_ms": max(durations) if durations else None,
            "last_run": last_run.isoformat() if last_run else None,
            "last_success": last_success.isoformat() if last_success else None,
            "last_failure": last_failure.isoformat() if last_failure else None,
        }
