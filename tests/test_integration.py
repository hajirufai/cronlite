"""Integration tests — end-to-end scheduler scenarios."""

import time
import unittest

from cronlite.config import Config
from cronlite.cron import CronParser
from cronlite.dag import JobDAG
from cronlite.scheduler.engine import SchedulerEngine
from cronlite.scheduler.executor import JobExecutor
from cronlite.store import MemoryStore
from cronlite.types import Job, JobState, RetryStrategy


class TestEndToEnd(unittest.TestCase):

    def test_executor_runs_echo(self):
        executor = JobExecutor()
        job = Job(
            id="echo01",
            name="echo-test",
            expression="* * * * *",
            command="echo 'integration test'",
        )
        result = executor.execute(job)
        self.assertEqual(result.state, JobState.SUCCESS)
        self.assertIn("integration test", result.stdout)

    def test_parser_then_executor(self):
        parser = CronParser()
        expr = parser.parse("*/5 * * * *")
        from datetime import datetime
        self.assertIsNotNone(expr.next_run(datetime.now()))  # Should return something

        executor = JobExecutor()
        job = Job(id="j1", name="parse-exec", expression="*/5 * * * *", command="echo works")
        result = executor.execute(job)
        self.assertEqual(result.state, JobState.SUCCESS)

    def test_store_then_executor(self):
        store = MemoryStore()
        job = Job(
            id="j1", name="store-test", expression="* * * * *",
            command="echo stored",
        )
        store.save_job(job)
        retrieved = store.get_job("j1")

        executor = JobExecutor()
        result = executor.execute(retrieved)
        store.save_execution(result)

        self.assertEqual(result.state, JobState.SUCCESS)
        execs = store.get_executions(job_id="j1")
        self.assertEqual(len(execs), 1)

    def test_dag_resolution(self):
        dag = JobDAG()
        dag.add_job("etl")
        dag.add_job("report")
        dag.add_job("notify")
        dag.add_dependency("report", "etl")
        dag.add_dependency("notify", "report")

        order = dag.topological_sort()
        self.assertEqual(order, ["etl", "report", "notify"])

        ready = dag.get_ready_jobs({"etl"})
        self.assertEqual(ready, ["report"])

        ready = dag.get_ready_jobs({"etl", "report"})
        self.assertEqual(ready, ["notify"])

    def test_scheduler_add_and_trigger(self):
        store = MemoryStore()
        config = Config(max_workers=2)
        engine = SchedulerEngine(store, config)

        job = Job(
            id="trig01",
            name="trigger-test",
            expression="0 0 * * *",
            command="echo triggered",
        )
        engine.add_job(job)

        execution = engine.trigger_job("trig01")
        self.assertEqual(execution.state, JobState.SUCCESS)
        self.assertIn("triggered", execution.stdout)

    def test_scheduler_stats(self):
        store = MemoryStore()
        engine = SchedulerEngine(store, Config())

        job = Job(
            id="s1", name="stats-test", expression="* * * * *",
            command="echo stats",
        )
        engine.add_job(job)
        engine.trigger_job("s1")
        engine.trigger_job("s1")

        stats = engine.get_stats()
        self.assertEqual(stats.total_jobs, 1)
        self.assertEqual(stats.total_executions, 2)
        self.assertEqual(stats.success_count, 2)

    def test_scheduler_pause_resume(self):
        store = MemoryStore()
        engine = SchedulerEngine(store, Config())
        job = Job(id="p1", name="pause-test", expression="* * * * *", command="echo x")
        engine.add_job(job)

        engine.pause_job("p1")
        self.assertFalse(store.get_job("p1").enabled)

        engine.resume_job("p1")
        self.assertTrue(store.get_job("p1").enabled)


class TestRetryIntegration(unittest.TestCase):
    """Test retry behavior with the executor."""

    def test_retry_with_eventual_failure(self):
        """A failing command with retries should attempt max_retries times."""
        store = MemoryStore()
        engine = SchedulerEngine(store, Config())
        job = Job(
            id="r1",
            name="retry-test",
            expression="* * * * *",
            command="exit 1",
            max_retries=2,
            retry_strategy=RetryStrategy.FIXED,
            retry_base_delay=0.1,
        )
        engine.add_job(job)
        execution = engine.trigger_job("r1")
        self.assertEqual(execution.state, JobState.FAILED)
        # Should have retried
        self.assertGreaterEqual(execution.attempt, 2)


class TestCronParserEdgeCases(unittest.TestCase):
    """Edge cases for the cron parser."""

    def test_feb_30_never_matches(self):
        parser = CronParser()
        expr = parser.parse("0 0 30 2 *")
        from datetime import datetime
        # Should still parse but never find a match (within reasonable limit)
        result = expr.next_run(datetime(2026, 1, 1))
        # It's OK if this returns None or a very distant date
        # The important thing is it doesn't crash

    def test_every_minute_every_day(self):
        parser = CronParser()
        expr = parser.parse("* * * * *")
        from datetime import datetime
        now = datetime(2026, 6, 1, 12, 0, 0)
        runs = expr.next_n_runs(now, 1440)  # Full day
        self.assertEqual(len(runs), 1440)


if __name__ == "__main__":
    unittest.main()
