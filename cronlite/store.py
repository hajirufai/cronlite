"""Storage backends for CronLite.

Provides MemoryStore (for testing) and SQLiteStore (for production).
Both implement the same interface for job and execution persistence.
"""

import json
import sqlite3
import threading
from abc import ABC, abstractmethod
from datetime import datetime

from cronlite.errors import JobNotFoundError, DuplicateJobError, StoreError
from cronlite.types import Job, Execution, JobState, RetryStrategy


class Store(ABC):
    """Abstract base for storage backends."""

    @abstractmethod
    def save_job(self, job: Job) -> None: ...

    @abstractmethod
    def get_job(self, job_id: str) -> Job: ...

    @abstractmethod
    def get_job_by_name(self, name: str) -> Job | None: ...

    @abstractmethod
    def list_jobs(self) -> list[Job]: ...

    @abstractmethod
    def delete_job(self, job_id: str) -> None: ...

    @abstractmethod
    def update_job(self, job: Job) -> None: ...

    @abstractmethod
    def save_execution(self, execution: Execution) -> None: ...

    @abstractmethod
    def get_executions(
        self, job_id: str | None = None, limit: int = 50
    ) -> list[Execution]: ...

    @abstractmethod
    def get_execution(self, exec_id: str) -> Execution | None: ...

    @abstractmethod
    def update_execution(self, execution: Execution) -> None: ...


class MemoryStore(Store):
    """In-memory storage backend for testing."""

    def __init__(self):
        self._jobs: dict[str, Job] = {}
        self._executions: list[Execution] = []
        self._lock = threading.Lock()

    def save_job(self, job: Job) -> None:
        with self._lock:
            if job.id in self._jobs:
                raise DuplicateJobError(f"Job '{job.id}' already exists")
            # Check name uniqueness
            for existing in self._jobs.values():
                if existing.name == job.name:
                    raise DuplicateJobError(f"Job name '{job.name}' already exists")
            self._jobs[job.id] = job

    def get_job(self, job_id: str) -> Job:
        with self._lock:
            if job_id not in self._jobs:
                raise JobNotFoundError(f"Job '{job_id}' not found")
            return self._jobs[job_id]

    def get_job_by_name(self, name: str) -> Job | None:
        with self._lock:
            for job in self._jobs.values():
                if job.name == name:
                    return job
            return None

    def list_jobs(self) -> list[Job]:
        with self._lock:
            return sorted(self._jobs.values(), key=lambda j: j.created_at)

    def delete_job(self, job_id: str) -> None:
        with self._lock:
            if job_id not in self._jobs:
                raise JobNotFoundError(f"Job '{job_id}' not found")
            del self._jobs[job_id]

    def update_job(self, job: Job) -> None:
        with self._lock:
            if job.id not in self._jobs:
                raise JobNotFoundError(f"Job '{job.id}' not found")
            self._jobs[job.id] = job

    def save_execution(self, execution: Execution) -> None:
        with self._lock:
            self._executions.append(execution)

    def get_executions(
        self, job_id: str | None = None, limit: int = 50
    ) -> list[Execution]:
        with self._lock:
            execs = self._executions
            if job_id:
                execs = [e for e in execs if e.job_id == job_id]
            return sorted(execs, key=lambda e: e.started_at, reverse=True)[:limit]

    def get_execution(self, exec_id: str) -> Execution | None:
        with self._lock:
            for e in self._executions:
                if e.id == exec_id:
                    return e
            return None

    def update_execution(self, execution: Execution) -> None:
        with self._lock:
            for i, e in enumerate(self._executions):
                if e.id == execution.id:
                    self._executions[i] = execution
                    return


class SQLiteStore(Store):
    """SQLite-backed persistent storage."""

    def __init__(self, db_path: str = "cronlite.db"):
        self._db_path = db_path
        self._local = threading.local()
        self._init_schema()

    def _get_conn(self) -> sqlite3.Connection:
        if not hasattr(self._local, "conn") or self._local.conn is None:
            self._local.conn = sqlite3.connect(self._db_path)
            self._local.conn.row_factory = sqlite3.Row
            self._local.conn.execute("PRAGMA journal_mode=WAL")
            self._local.conn.execute("PRAGMA foreign_keys=ON")
        return self._local.conn

    def _init_schema(self) -> None:
        conn = self._get_conn()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                name TEXT UNIQUE NOT NULL,
                expression TEXT NOT NULL,
                command TEXT NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                max_retries INTEGER NOT NULL DEFAULT 0,
                retry_strategy TEXT NOT NULL DEFAULT 'none',
                retry_base_delay REAL NOT NULL DEFAULT 10.0,
                retry_max_delay REAL NOT NULL DEFAULT 300.0,
                timeout_seconds INTEGER NOT NULL DEFAULT 300,
                depends_on TEXT NOT NULL DEFAULT '[]',
                tags TEXT NOT NULL DEFAULT '[]',
                metadata TEXT NOT NULL DEFAULT '{}',
                working_dir TEXT
            );

            CREATE TABLE IF NOT EXISTS executions (
                id TEXT PRIMARY KEY,
                job_id TEXT NOT NULL,
                job_name TEXT NOT NULL DEFAULT '',
                started_at TEXT NOT NULL,
                finished_at TEXT,
                state TEXT NOT NULL DEFAULT 'pending',
                exit_code INTEGER,
                stdout TEXT NOT NULL DEFAULT '',
                stderr TEXT NOT NULL DEFAULT '',
                attempt INTEGER NOT NULL DEFAULT 1,
                duration_ms INTEGER,
                trigger TEXT NOT NULL DEFAULT 'scheduled',
                FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_exec_job_id ON executions(job_id);
            CREATE INDEX IF NOT EXISTS idx_exec_started ON executions(started_at);
            CREATE INDEX IF NOT EXISTS idx_exec_state ON executions(state);
        """)
        conn.commit()

    def save_job(self, job: Job) -> None:
        conn = self._get_conn()
        try:
            conn.execute(
                """INSERT INTO jobs
                   (id, name, expression, command, enabled, created_at,
                    max_retries, retry_strategy, retry_base_delay, retry_max_delay,
                    timeout_seconds, depends_on, tags, metadata, working_dir)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    job.id, job.name, job.expression, job.command,
                    int(job.enabled), job.created_at.isoformat(),
                    job.max_retries, job.retry_strategy.value,
                    job.retry_base_delay, job.retry_max_delay,
                    job.timeout_seconds,
                    json.dumps(job.depends_on), json.dumps(job.tags),
                    json.dumps(job.metadata), job.working_dir,
                ),
            )
            conn.commit()
        except sqlite3.IntegrityError as e:
            raise DuplicateJobError(str(e))

    def get_job(self, job_id: str) -> Job:
        conn = self._get_conn()
        row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        if row is None:
            raise JobNotFoundError(f"Job '{job_id}' not found")
        return self._row_to_job(row)

    def get_job_by_name(self, name: str) -> Job | None:
        conn = self._get_conn()
        row = conn.execute("SELECT * FROM jobs WHERE name = ?", (name,)).fetchone()
        if row is None:
            return None
        return self._row_to_job(row)

    def list_jobs(self) -> list[Job]:
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM jobs ORDER BY created_at"
        ).fetchall()
        return [self._row_to_job(r) for r in rows]

    def delete_job(self, job_id: str) -> None:
        conn = self._get_conn()
        cursor = conn.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
        conn.commit()
        if cursor.rowcount == 0:
            raise JobNotFoundError(f"Job '{job_id}' not found")

    def update_job(self, job: Job) -> None:
        conn = self._get_conn()
        cursor = conn.execute(
            """UPDATE jobs SET
               name=?, expression=?, command=?, enabled=?,
               max_retries=?, retry_strategy=?, retry_base_delay=?,
               retry_max_delay=?, timeout_seconds=?, depends_on=?,
               tags=?, metadata=?, working_dir=?
               WHERE id=?""",
            (
                job.name, job.expression, job.command, int(job.enabled),
                job.max_retries, job.retry_strategy.value,
                job.retry_base_delay, job.retry_max_delay,
                job.timeout_seconds,
                json.dumps(job.depends_on), json.dumps(job.tags),
                json.dumps(job.metadata), job.working_dir,
                job.id,
            ),
        )
        conn.commit()
        if cursor.rowcount == 0:
            raise JobNotFoundError(f"Job '{job.id}' not found")

    def save_execution(self, execution: Execution) -> None:
        conn = self._get_conn()
        conn.execute(
            """INSERT INTO executions
               (id, job_id, job_name, started_at, finished_at, state,
                exit_code, stdout, stderr, attempt, duration_ms, trigger)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                execution.id, execution.job_id, execution.job_name,
                execution.started_at.isoformat(),
                execution.finished_at.isoformat() if execution.finished_at else None,
                execution.state.value,
                execution.exit_code, execution.stdout, execution.stderr,
                execution.attempt, execution.duration_ms, execution.trigger,
            ),
        )
        conn.commit()

    def get_executions(
        self, job_id: str | None = None, limit: int = 50
    ) -> list[Execution]:
        conn = self._get_conn()
        if job_id:
            rows = conn.execute(
                "SELECT * FROM executions WHERE job_id = ? ORDER BY started_at DESC LIMIT ?",
                (job_id, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM executions ORDER BY started_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [self._row_to_execution(r) for r in rows]

    def get_execution(self, exec_id: str) -> Execution | None:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM executions WHERE id = ?", (exec_id,)
        ).fetchone()
        if row is None:
            return None
        return self._row_to_execution(row)

    def update_execution(self, execution: Execution) -> None:
        conn = self._get_conn()
        conn.execute(
            """UPDATE executions SET
               finished_at=?, state=?, exit_code=?, stdout=?, stderr=?,
               attempt=?, duration_ms=?
               WHERE id=?""",
            (
                execution.finished_at.isoformat() if execution.finished_at else None,
                execution.state.value,
                execution.exit_code, execution.stdout, execution.stderr,
                execution.attempt, execution.duration_ms,
                execution.id,
            ),
        )
        conn.commit()

    @staticmethod
    def _row_to_job(row: sqlite3.Row) -> Job:
        return Job(
            id=row["id"],
            name=row["name"],
            expression=row["expression"],
            command=row["command"],
            enabled=bool(row["enabled"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            max_retries=row["max_retries"],
            retry_strategy=RetryStrategy(row["retry_strategy"]),
            retry_base_delay=row["retry_base_delay"],
            retry_max_delay=row["retry_max_delay"],
            timeout_seconds=row["timeout_seconds"],
            depends_on=json.loads(row["depends_on"]),
            tags=json.loads(row["tags"]),
            metadata=json.loads(row["metadata"]),
            working_dir=row["working_dir"],
        )

    @staticmethod
    def _row_to_execution(row: sqlite3.Row) -> Execution:
        return Execution(
            id=row["id"],
            job_id=row["job_id"],
            job_name=row["job_name"],
            started_at=datetime.fromisoformat(row["started_at"]),
            finished_at=(
                datetime.fromisoformat(row["finished_at"])
                if row["finished_at"]
                else None
            ),
            state=JobState(row["state"]),
            exit_code=row["exit_code"],
            stdout=row["stdout"],
            stderr=row["stderr"],
            attempt=row["attempt"],
            duration_ms=row["duration_ms"],
            trigger=row["trigger"],
        )
