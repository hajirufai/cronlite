"""Health checks for the scheduler.

Detects missed jobs, overdue executions, and produces health reports.
"""

from datetime import datetime, timedelta

from cronlite.cron import CronParser
from cronlite.store import Store
from cronlite.types import Job, JobState


class HealthChecker:
    """Monitor scheduler health."""

    def __init__(self, store: Store):
        self._store = store
        self._parser = CronParser()

    def check_missed_jobs(self, window_minutes: int = 10) -> list[dict]:
        """Find jobs that should have run recently but have no execution.

        Args:
            window_minutes: How far back to check for missed runs.

        Returns:
            List of dicts with job info and expected run times.
        """
        now = datetime.now()
        window_start = now - timedelta(minutes=window_minutes)
        missed = []

        for job in self._store.list_jobs():
            if not job.enabled:
                continue

            try:
                expr = self._parser.parse(job.expression)
            except Exception:
                continue

            # Check if the job should have run in the window
            expected = expr.next_run(window_start)
            if expected and expected <= now:
                # Check if there's a recent execution
                recent = self._store.get_executions(job_id=job.id, limit=1)
                if not recent or recent[0].started_at < window_start:
                    missed.append({
                        "job_id": job.id,
                        "job_name": job.name,
                        "expected_run": expected.isoformat(),
                        "last_run": (
                            recent[0].started_at.isoformat() if recent else None
                        ),
                    })

        return missed

    def check_overdue_jobs(self) -> list[dict]:
        """Find jobs that are currently running past their timeout.

        Returns:
            List of dicts with job info and how long they've been running.
        """
        now = datetime.now()
        overdue = []

        for job in self._store.list_jobs():
            recent = self._store.get_executions(job_id=job.id, limit=1)
            if not recent:
                continue
            latest = recent[0]
            if latest.state != JobState.RUNNING:
                continue

            elapsed = (now - latest.started_at).total_seconds()
            if elapsed > job.timeout_seconds:
                overdue.append({
                    "job_id": job.id,
                    "job_name": job.name,
                    "execution_id": latest.id,
                    "started_at": latest.started_at.isoformat(),
                    "elapsed_seconds": round(elapsed, 1),
                    "timeout_seconds": job.timeout_seconds,
                })

        return overdue

    def get_health_report(self) -> dict:
        """Generate a full health report.

        Returns:
            Dict with status, job counts, recent failures, missed jobs, etc.
        """
        jobs = self._store.list_jobs()
        recent_execs = self._store.get_executions(limit=100)
        missed = self.check_missed_jobs()
        overdue = self.check_overdue_jobs()

        recent_failures = [
            {
                "job_name": e.job_name,
                "job_id": e.job_id,
                "state": e.state.value,
                "time": e.started_at.isoformat(),
                "error": e.stderr[:200] if e.stderr else "",
            }
            for e in recent_execs[:20]
            if e.state in (JobState.FAILED, JobState.TIMEOUT)
        ]

        # Determine overall health status
        if overdue:
            status = "degraded"
        elif missed:
            status = "warning"
        elif recent_failures:
            status = "warning"
        else:
            status = "healthy"

        return {
            "status": status,
            "total_jobs": len(jobs),
            "enabled_jobs": sum(1 for j in jobs if j.enabled),
            "disabled_jobs": sum(1 for j in jobs if not j.enabled),
            "missed_jobs": missed,
            "overdue_jobs": overdue,
            "recent_failures": recent_failures,
            "checked_at": datetime.now().isoformat(),
        }
