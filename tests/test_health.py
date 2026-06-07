"""Tests for health checking."""

import unittest
from datetime import datetime, timedelta

from cronlite.health import HealthChecker
from cronlite.store import MemoryStore
from cronlite.types import Job, Execution, JobState


class TestHealthChecker(unittest.TestCase):

    def setUp(self):
        self.store = MemoryStore()
        self.checker = HealthChecker(self.store)

    def test_health_report_no_jobs(self):
        report = self.checker.get_health_report()
        self.assertEqual(report["status"], "healthy")
        self.assertEqual(report["total_jobs"], 0)

    def test_health_report_with_jobs(self):
        job = Job(
            id="j1", name="test", expression="* * * * *",
            command="echo hi", enabled=True,
        )
        self.store.save_job(job)
        report = self.checker.get_health_report()
        self.assertEqual(report["total_jobs"], 1)
        self.assertEqual(report["enabled_jobs"], 1)

    def test_health_report_disabled_job(self):
        job = Job(
            id="j1", name="test", expression="* * * * *",
            command="echo hi", enabled=False,
        )
        self.store.save_job(job)
        report = self.checker.get_health_report()
        self.assertEqual(report["disabled_jobs"], 1)

    def test_overdue_detection(self):
        job = Job(
            id="j1", name="test", expression="* * * * *",
            command="sleep 1000", timeout_seconds=60,
        )
        self.store.save_job(job)
        # Add a "running" execution started 2 minutes ago
        e = Execution(
            id="e1",
            job_id="j1",
            job_name="test",
            started_at=datetime.now() - timedelta(minutes=2),
            state=JobState.RUNNING,
        )
        self.store.save_execution(e)
        overdue = self.checker.check_overdue_jobs()
        self.assertEqual(len(overdue), 1)
        self.assertEqual(overdue[0]["job_id"], "j1")

    def test_recent_failure_in_report(self):
        job = Job(
            id="j1", name="test", expression="* * * * *",
            command="exit 1",
        )
        self.store.save_job(job)
        e = Execution(
            id="e1",
            job_id="j1",
            job_name="test",
            started_at=datetime.now(),
            finished_at=datetime.now(),
            state=JobState.FAILED,
            exit_code=1,
            stderr="Something went wrong",
        )
        self.store.save_execution(e)
        report = self.checker.get_health_report()
        self.assertEqual(report["status"], "warning")
        self.assertGreater(len(report["recent_failures"]), 0)

    def test_healthy_with_success(self):
        job = Job(id="j1", name="test", expression="* * * * *", command="echo hi")
        self.store.save_job(job)
        e = Execution(
            id="e1",
            job_id="j1",
            job_name="test",
            started_at=datetime.now(),
            finished_at=datetime.now(),
            state=JobState.SUCCESS,
            exit_code=0,
        )
        self.store.save_execution(e)
        report = self.checker.get_health_report()
        self.assertEqual(report["status"], "healthy")


if __name__ == "__main__":
    unittest.main()
