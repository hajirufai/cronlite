"""Tests for the job executor."""

import unittest

from cronlite.scheduler.executor import JobExecutor
from cronlite.types import Job, JobState


def _make_job(command="echo hello", timeout=30, name="test"):
    return Job(
        id="job_test",
        name=name,
        expression="* * * * *",
        command=command,
        timeout_seconds=timeout,
    )


class TestJobExecutor(unittest.TestCase):

    def setUp(self):
        self.executor = JobExecutor(max_output_bytes=4096)

    def test_successful_command(self):
        job = _make_job("echo 'Hello, World!'")
        result = self.executor.execute(job)
        self.assertEqual(result.state, JobState.SUCCESS)
        self.assertEqual(result.exit_code, 0)
        self.assertIn("Hello, World!", result.stdout)
        self.assertIsNotNone(result.duration_ms)

    def test_failed_command(self):
        job = _make_job("exit 1")
        result = self.executor.execute(job)
        self.assertEqual(result.state, JobState.FAILED)
        self.assertEqual(result.exit_code, 1)

    def test_nonzero_exit(self):
        job = _make_job("exit 42")
        result = self.executor.execute(job)
        self.assertEqual(result.state, JobState.FAILED)
        self.assertEqual(result.exit_code, 42)

    def test_stderr_capture(self):
        job = _make_job("echo error >&2 && exit 1")
        result = self.executor.execute(job)
        self.assertIn("error", result.stderr)

    def test_timeout(self):
        job = _make_job("sleep 10", timeout=1)
        result = self.executor.execute(job)
        self.assertEqual(result.state, JobState.TIMEOUT)
        self.assertEqual(result.exit_code, -1)

    def test_command_not_found(self):
        job = _make_job("nonexistent_command_xyz123")
        result = self.executor.execute(job)
        # The shell returns 127 for command not found
        self.assertEqual(result.state, JobState.FAILED)

    def test_trigger_recorded(self):
        job = _make_job("echo test")
        result = self.executor.execute(job, trigger="manual")
        self.assertEqual(result.trigger, "manual")

    def test_attempt_recorded(self):
        job = _make_job("echo test")
        result = self.executor.execute(job, attempt=3)
        self.assertEqual(result.attempt, 3)

    def test_execution_has_unique_id(self):
        job = _make_job("echo test")
        r1 = self.executor.execute(job)
        r2 = self.executor.execute(job)
        self.assertNotEqual(r1.id, r2.id)

    def test_multiline_output(self):
        job = _make_job("echo line1 && echo line2 && echo line3")
        result = self.executor.execute(job)
        self.assertEqual(result.state, JobState.SUCCESS)
        lines = result.stdout.strip().split("\n")
        self.assertEqual(len(lines), 3)

    def test_output_truncation(self):
        executor = JobExecutor(max_output_bytes=20)
        job = _make_job("echo " + "A" * 100)
        result = executor.execute(job)
        self.assertLessEqual(len(result.stdout), 50)  # some overhead is ok

    def test_duration_is_positive(self):
        job = _make_job("echo fast")
        result = self.executor.execute(job)
        self.assertGreater(result.duration_ms, 0)


if __name__ == "__main__":
    unittest.main()
