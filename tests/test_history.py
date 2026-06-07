"""Tests for execution history queries."""

import unittest
from datetime import datetime

from cronlite.history import ExecutionHistory
from cronlite.store import MemoryStore
from cronlite.types import Job, Execution, JobState


class TestExecutionHistory(unittest.TestCase):

    def setUp(self):
        self.store = MemoryStore()
        self.history = ExecutionHistory(self.store)
        self.job = Job(
            id="job_001",
            name="test-job",
            expression="* * * * *",
            command="echo hello",
        )
        self.store.save_job(self.job)

    def _add_exec(self, exec_id, state=JobState.SUCCESS, started_hour=12):
        e = Execution(
            id=exec_id,
            job_id="job_001",
            job_name="test-job",
            started_at=datetime(2026, 6, 1, started_hour, 0, 0),
            finished_at=datetime(2026, 6, 1, started_hour, 0, 1),
            state=state,
            exit_code=0 if state == JobState.SUCCESS else 1,
            duration_ms=1000,
        )
        self.store.save_execution(e)
        return e

    def test_get_last_n(self):
        self._add_exec("e1", started_hour=10)
        self._add_exec("e2", started_hour=11)
        self._add_exec("e3", started_hour=12)
        results = self.history.get_last_n("job_001", 2)
        self.assertEqual(len(results), 2)

    def test_get_recent(self):
        self._add_exec("e1")
        self._add_exec("e2")
        results = self.history.get_recent(limit=10)
        self.assertEqual(len(results), 2)

    def test_get_by_state(self):
        self._add_exec("e1", JobState.SUCCESS)
        self._add_exec("e2", JobState.FAILED)
        self._add_exec("e3", JobState.SUCCESS)
        results = self.history.get_by_state(JobState.FAILED)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].state, JobState.FAILED)

    def test_get_timeline(self):
        self._add_exec("e1", started_hour=9)
        self._add_exec("e2", started_hour=12)
        self._add_exec("e3", started_hour=18)
        results = self.history.get_timeline(
            datetime(2026, 6, 1, 10, 0, 0),
            datetime(2026, 6, 1, 15, 0, 0),
        )
        self.assertEqual(len(results), 1)

    def test_get_stats(self):
        self._add_exec("e1", JobState.SUCCESS, 10)
        self._add_exec("e2", JobState.SUCCESS, 11)
        self._add_exec("e3", JobState.FAILED, 12)
        stats = self.history.get_stats("job_001")
        self.assertEqual(stats["total_count"], 3)
        self.assertEqual(stats["success_count"], 2)
        self.assertEqual(stats["failure_count"], 1)
        self.assertAlmostEqual(stats["success_rate"], 66.67, places=1)

    def test_get_stats_empty(self):
        stats = self.history.get_stats("job_001")
        self.assertEqual(stats["total_count"], 0)
        self.assertIsNone(stats["last_run"])


if __name__ == "__main__":
    unittest.main()
