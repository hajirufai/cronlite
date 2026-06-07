"""Job executor — runs commands as subprocesses."""

import os
import subprocess
import time
from datetime import datetime

from cronlite.errors import ExecutionError, JobTimeoutError
from cronlite.types import Job, Execution, JobState
from cronlite.utils import generate_execution_id, truncate_output


class JobExecutor:
    """Executes job commands as subprocesses with timeout and output capture."""

    def __init__(self, max_output_bytes: int = 10240):
        self._max_output = max_output_bytes

    def execute(
        self,
        job: Job,
        attempt: int = 1,
        trigger: str = "scheduled",
    ) -> Execution:
        """Execute a job's command and return an Execution record.

        Args:
            job: The job to execute.
            attempt: Which retry attempt this is (1-based).
            trigger: What triggered this execution (scheduled/manual/dependency).

        Returns:
            An Execution record with the result.
        """
        exec_id = generate_execution_id()
        started_at = datetime.now()

        execution = Execution(
            id=exec_id,
            job_id=job.id,
            job_name=job.name,
            started_at=started_at,
            state=JobState.RUNNING,
            attempt=attempt,
            trigger=trigger,
        )

        try:
            cwd = job.working_dir if job.working_dir and os.path.isdir(job.working_dir) else None

            proc = subprocess.Popen(
                job.command,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=cwd,
                env=os.environ.copy(),
            )

            try:
                stdout_bytes, stderr_bytes = proc.communicate(
                    timeout=job.timeout_seconds
                )
            except subprocess.TimeoutExpired:
                # Kill the process tree
                proc.kill()
                try:
                    proc.communicate(timeout=5)
                except Exception:
                    pass

                finished_at = datetime.now()
                duration_ms = int((finished_at - started_at).total_seconds() * 1000)

                execution.finished_at = finished_at
                execution.state = JobState.TIMEOUT
                execution.exit_code = -1
                execution.stderr = f"Job timed out after {job.timeout_seconds}s"
                execution.duration_ms = duration_ms
                return execution

            finished_at = datetime.now()
            duration_ms = int((finished_at - started_at).total_seconds() * 1000)

            stdout_text = stdout_bytes.decode("utf-8", errors="replace")
            stderr_text = stderr_bytes.decode("utf-8", errors="replace")

            execution.finished_at = finished_at
            execution.exit_code = proc.returncode
            execution.stdout = truncate_output(stdout_text, self._max_output)
            execution.stderr = truncate_output(stderr_text, self._max_output)
            execution.duration_ms = duration_ms

            if proc.returncode == 0:
                execution.state = JobState.SUCCESS
            else:
                execution.state = JobState.FAILED

        except OSError as e:
            finished_at = datetime.now()
            duration_ms = int((finished_at - started_at).total_seconds() * 1000)
            execution.finished_at = finished_at
            execution.state = JobState.FAILED
            execution.exit_code = -1
            execution.stderr = f"Failed to start process: {e}"
            execution.duration_ms = duration_ms

        return execution
