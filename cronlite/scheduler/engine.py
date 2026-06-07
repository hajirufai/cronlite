"""Scheduler engine — the main scheduling loop.

Uses a min-heap (priority queue) keyed by next-run timestamp.
Each tick, the engine checks the queue head and fires jobs whose
next_run time has arrived.
"""

import heapq
import logging
import threading
import time
from datetime import datetime

from cronlite.config import Config
from cronlite.cron import CronParser
from cronlite.dag import JobDAG
from cronlite.retry import RetryPolicy
from cronlite.scheduler.executor import JobExecutor
from cronlite.scheduler.hooks import JobHooks, LoggingHooks
from cronlite.scheduler.pool import WorkerPool
from cronlite.store import Store
from cronlite.types import Job, Execution, JobState, SchedulerStats
from cronlite.utils import generate_job_id

logger = logging.getLogger("cronlite.engine")


class SchedulerEngine:
    """Priority-queue based task scheduler.

    The engine maintains a min-heap of (next_run, job_id) entries.
    On each tick:
      1. Peek at queue head.
      2. If next_run <= now: pop, execute, compute new next_run, re-push.
      3. Else: sleep until next_run or tick_interval, whichever is shorter.
    """

    def __init__(
        self,
        store: Store,
        config: Config | None = None,
        hooks: JobHooks | None = None,
    ):
        self._store = store
        self._config = config or Config()
        self._hooks = hooks or LoggingHooks()
        self._parser = CronParser()
        self._executor = JobExecutor(self._config.max_output_bytes)
        self._pool = WorkerPool(self._config.max_workers)
        self._dag = JobDAG()

        # Priority queue: list of (next_run_timestamp, job_id)
        self._queue: list[tuple[float, str]] = []
        self._queue_lock = threading.Lock()

        # Cron expressions cache: job_id → CronExpression
        self._expressions: dict[str, object] = {}

        self._running = False
        self._started_at: datetime | None = None
        self._thread: threading.Thread | None = None

        # Track recently completed jobs for dependency resolution
        self._completed_in_window: set[str] = set()
        self._completed_lock = threading.Lock()

    def start(self) -> None:
        """Start the scheduler loop in a background thread."""
        if self._running:
            logger.warning("Scheduler is already running")
            return

        self._running = True
        self._started_at = datetime.now()
        self._pool.start()

        # Load all jobs and build the schedule
        self._load_jobs()

        self._thread = threading.Thread(
            target=self._run_loop,
            name="cronlite-scheduler",
            daemon=True,
        )
        self._thread.start()
        logger.info("Scheduler started")

    def start_blocking(self) -> None:
        """Start the scheduler and block until stopped."""
        self.start()

        # Set up signal handlers for graceful shutdown
        try:
            import signal

            def handler(signum, frame):
                logger.info("Received signal %d, shutting down...", signum)
                self.stop()

            signal.signal(signal.SIGINT, handler)
            signal.signal(signal.SIGTERM, handler)
        except (ValueError, OSError):
            # Signal handlers only work in main thread
            pass

        try:
            while self._running:
                time.sleep(1)
        except KeyboardInterrupt:
            self.stop()

    def stop(self) -> None:
        """Stop the scheduler gracefully."""
        if not self._running:
            return
        self._running = False
        self._pool.shutdown(wait=True)
        if self._thread:
            self._thread.join(timeout=10)
        logger.info("Scheduler stopped")

    def add_job(self, job: Job) -> Job:
        """Add a new job to the scheduler.

        Args:
            job: The job to add. If id is empty, one will be generated.

        Returns:
            The job with its ID set.
        """
        if not job.id:
            job.id = generate_job_id(job.name)

        # Parse and cache the cron expression
        expr = self._parser.parse(job.expression)
        self._expressions[job.id] = expr

        # Save to store
        self._store.save_job(job)

        # Set up dependencies
        self._dag.add_job(job.id)
        for dep_id in job.depends_on:
            self._dag.add_dependency(job.id, dep_id)

        # Schedule if enabled
        if job.enabled:
            self._schedule_job(job.id, expr)

        logger.info("Added job: %s [%s] — %s", job.name, job.id, job.expression)
        return job

    def remove_job(self, job_id: str) -> None:
        """Remove a job from the scheduler and store."""
        self._store.delete_job(job_id)
        self._dag.remove_job(job_id)
        self._expressions.pop(job_id, None)
        # Note: can't efficiently remove from heapq, but the job won't
        # be found in the store when it pops, so it'll be skipped.
        logger.info("Removed job: %s", job_id)

    def pause_job(self, job_id: str) -> None:
        """Pause a job (keep in store but don't execute)."""
        job = self._store.get_job(job_id)
        job.enabled = False
        self._store.update_job(job)
        logger.info("Paused job: %s [%s]", job.name, job_id)

    def resume_job(self, job_id: str) -> None:
        """Resume a paused job."""
        job = self._store.get_job(job_id)
        job.enabled = True
        self._store.update_job(job)

        expr = self._expressions.get(job_id)
        if expr is None:
            expr = self._parser.parse(job.expression)
            self._expressions[job_id] = expr
        self._schedule_job(job_id, expr)

        logger.info("Resumed job: %s [%s]", job.name, job_id)

    def trigger_job(self, job_id: str) -> Execution:
        """Manually trigger a job immediately.

        Returns the execution record.
        """
        job = self._store.get_job(job_id)
        execution = self._execute_job(job, trigger="manual")
        return execution

    def get_stats(self) -> SchedulerStats:
        """Get current scheduler statistics."""
        jobs = self._store.list_jobs()
        executions = self._store.get_executions(limit=1000)

        success = sum(1 for e in executions if e.state == JobState.SUCCESS)
        failed = sum(1 for e in executions if e.state == JobState.FAILED)
        timeout = sum(1 for e in executions if e.state == JobState.TIMEOUT)

        durations = [e.duration_ms for e in executions if e.duration_ms is not None]
        avg_dur = sum(durations) / len(durations) if durations else 0.0

        uptime = 0.0
        if self._started_at:
            uptime = (datetime.now() - self._started_at).total_seconds()

        return SchedulerStats(
            total_jobs=len(jobs),
            enabled_jobs=sum(1 for j in jobs if j.enabled),
            total_executions=len(executions),
            success_count=success,
            failure_count=failed,
            timeout_count=timeout,
            avg_duration_ms=avg_dur,
            uptime_seconds=uptime,
            is_running=self._running,
        )

    @property
    def is_running(self) -> bool:
        return self._running

    # --- Internal methods ---

    def _load_jobs(self) -> None:
        """Load all jobs from the store and schedule them."""
        jobs = self._store.list_jobs()
        for job in jobs:
            try:
                expr = self._parser.parse(job.expression)
                self._expressions[job.id] = expr
                self._dag.add_job(job.id)
                for dep_id in job.depends_on:
                    try:
                        self._dag.add_dependency(job.id, dep_id)
                    except Exception:
                        logger.warning(
                            "Failed to add dependency %s → %s", job.id, dep_id
                        )
                if job.enabled:
                    self._schedule_job(job.id, expr)
            except Exception:
                logger.exception("Failed to load job: %s [%s]", job.name, job.id)

        logger.info("Loaded %d jobs (%d enabled)", len(jobs), sum(1 for j in jobs if j.enabled))

    def _schedule_job(self, job_id: str, expr) -> None:
        """Compute next_run and push to the priority queue."""
        now = datetime.now()
        next_run = expr.next_run(now)
        if next_run:
            with self._queue_lock:
                heapq.heappush(self._queue, (next_run.timestamp(), job_id))

    def _run_loop(self) -> None:
        """Main scheduler loop."""
        while self._running:
            try:
                self._tick()
            except Exception:
                logger.exception("Error in scheduler tick")
            time.sleep(self._config.tick_interval)

    def _tick(self) -> None:
        """Process one scheduler tick: fire due jobs."""
        now = datetime.now()
        now_ts = now.timestamp()

        while True:
            with self._queue_lock:
                if not self._queue:
                    break
                next_ts, job_id = self._queue[0]
                if next_ts > now_ts:
                    break
                heapq.heappop(self._queue)

            # Check if job still exists and is enabled
            try:
                job = self._store.get_job(job_id)
            except Exception:
                continue

            if not job.enabled:
                continue

            # Check dependencies
            if job.depends_on:
                with self._completed_lock:
                    deps_met = all(
                        dep in self._completed_in_window for dep in job.depends_on
                    )
                if not deps_met:
                    self._hooks.on_skip(job, "dependencies not met")
                    # Reschedule
                    expr = self._expressions.get(job_id)
                    if expr:
                        self._schedule_job(job_id, expr)
                    continue

            # Submit to worker pool
            self._pool.submit(self._run_job, job)

            # Reschedule for next occurrence
            expr = self._expressions.get(job_id)
            if expr:
                self._schedule_job(job_id, expr)

    def _run_job(self, job: Job) -> None:
        """Execute a job with retry logic (runs in a worker thread)."""
        execution = self._execute_job(job, trigger="scheduled")

        if execution.state == JobState.SUCCESS:
            with self._completed_lock:
                self._completed_in_window.add(job.id)

            # Check if any dependent jobs are now ready
            ready = self._dag.get_ready_jobs(self._completed_in_window)
            for dep_job_id in ready:
                try:
                    dep_job = self._store.get_job(dep_job_id)
                    if dep_job.enabled:
                        self._pool.submit(
                            self._execute_job, dep_job, trigger="dependency"
                        )
                except Exception:
                    logger.exception("Error triggering dependent job: %s", dep_job_id)

    def _execute_job(self, job: Job, trigger: str = "scheduled") -> Execution:
        """Execute a job, handling retries."""
        retry_policy = RetryPolicy.from_job(job)
        attempt = 1

        while True:
            execution = self._executor.execute(job, attempt=attempt, trigger=trigger)
            self._store.save_execution(execution)

            self._hooks.on_start(job, execution)

            if execution.state == JobState.SUCCESS:
                self._hooks.on_success(job, execution)
                return execution

            if execution.state == JobState.TIMEOUT:
                self._hooks.on_timeout(job, execution)

            if retry_policy.should_retry(attempt):
                delay = retry_policy.compute_delay(attempt)
                self._hooks.on_retry(job, attempt, delay)
                time.sleep(delay)
                attempt += 1
                continue

            # No more retries
            self._hooks.on_failure(
                job, execution,
                execution.stderr or f"Exit code: {execution.exit_code}",
            )
            return execution
