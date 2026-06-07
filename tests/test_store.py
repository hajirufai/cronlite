"""Tests for storage backends."""

import os
import tempfile
import unittest
from datetime import datetime

from cronlite.errors import JobNotFoundError, DuplicateJobError
from cronlite.store import MemoryStore, SQLiteStore
from cronlite.types import Job, Execution, JobState


def _make_job(name="test-job", job_id="job_001", expression="* * * * *"):
    return Job(
        id=job_id,
        name=name,
        expression=expression,
        command="echo hello",
        enabled=True,
        created_at=datetime(2026, 6, 1, 12, 0, 0),
    )


def _make_execution(job_id="job_001", exec_id="exec_001", state=JobState.SUCCESS):
    return Execution(
        id=exec_id,
        job_id=job_id,
        job_name="test-job",
        started_at=datetime(2026, 6, 1, 12, 0, 0),
        finished_at=datetime(2026, 6, 1, 12, 0, 1),
        state=state,
        exit_code=0 if state == JobState.SUCCESS else 1,
        stdout="hello\n",
        stderr="",
        attempt=1,
        duration_ms=1000,
    )


class _StoreTests:
    """Mixin for store tests — works with both Memory and SQLite."""

    store = None  # Set by subclass

    def test_save_and_get_job(self):
        job = _make_job()
        self.store.save_job(job)
        retrieved = self.store.get_job("job_001")
        self.assertEqual(retrieved.name, "test-job")
        self.assertEqual(retrieved.command, "echo hello")

    def test_get_nonexistent_job(self):
        with self.assertRaises(JobNotFoundError):
            self.store.get_job("nonexistent")

    def test_duplicate_job(self):
        self.store.save_job(_make_job())
        with self.assertRaises(DuplicateJobError):
            self.store.save_job(_make_job())

    def test_duplicate_name(self):
        self.store.save_job(_make_job())
        with self.assertRaises(DuplicateJobError):
            self.store.save_job(_make_job(job_id="job_002"))

    def test_list_jobs(self):
        self.store.save_job(_make_job("a", "j1"))
        self.store.save_job(_make_job("b", "j2"))
        jobs = self.store.list_jobs()
        self.assertEqual(len(jobs), 2)

    def test_delete_job(self):
        self.store.save_job(_make_job())
        self.store.delete_job("job_001")
        with self.assertRaises(JobNotFoundError):
            self.store.get_job("job_001")

    def test_delete_nonexistent_job(self):
        with self.assertRaises(JobNotFoundError):
            self.store.delete_job("nonexistent")

    def test_update_job(self):
        job = _make_job()
        self.store.save_job(job)
        job.command = "echo updated"
        job.enabled = False
        self.store.update_job(job)
        retrieved = self.store.get_job("job_001")
        self.assertEqual(retrieved.command, "echo updated")
        self.assertFalse(retrieved.enabled)

    def test_get_job_by_name(self):
        self.store.save_job(_make_job())
        job = self.store.get_job_by_name("test-job")
        self.assertIsNotNone(job)
        self.assertEqual(job.id, "job_001")

    def test_get_job_by_name_not_found(self):
        job = self.store.get_job_by_name("nonexistent")
        self.assertIsNone(job)

    def test_save_and_get_execution(self):
        self.store.save_job(_make_job())
        exec_ = _make_execution()
        self.store.save_execution(exec_)
        retrieved = self.store.get_execution("exec_001")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.state, JobState.SUCCESS)

    def test_get_executions_by_job(self):
        self.store.save_job(_make_job())
        self.store.save_execution(_make_execution(exec_id="e1"))
        self.store.save_execution(_make_execution(exec_id="e2"))
        execs = self.store.get_executions(job_id="job_001")
        self.assertEqual(len(execs), 2)

    def test_get_executions_limit(self):
        self.store.save_job(_make_job())
        for i in range(20):
            self.store.save_execution(_make_execution(exec_id=f"e{i}"))
        execs = self.store.get_executions(limit=5)
        self.assertEqual(len(execs), 5)

    def test_update_execution(self):
        self.store.save_job(_make_job())
        exec_ = _make_execution()
        self.store.save_execution(exec_)
        exec_.state = JobState.FAILED
        exec_.exit_code = 1
        self.store.update_execution(exec_)
        retrieved = self.store.get_execution("exec_001")
        self.assertEqual(retrieved.state, JobState.FAILED)


class TestMemoryStore(_StoreTests, unittest.TestCase):

    def setUp(self):
        self.store = MemoryStore()


class TestSQLiteStore(_StoreTests, unittest.TestCase):

    def setUp(self):
        self._tmpfile = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._tmpfile.close()
        self.store = SQLiteStore(self._tmpfile.name)

    def tearDown(self):
        os.unlink(self._tmpfile.name)


if __name__ == "__main__":
    unittest.main()
