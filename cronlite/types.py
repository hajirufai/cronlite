"""Data types for CronLite."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class JobState(Enum):
    """Possible states for a job execution."""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    RETRYING = "retrying"
    SKIPPED = "skipped"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


class RetryStrategy(Enum):
    """Retry backoff strategies."""
    NONE = "none"
    FIXED = "fixed"
    LINEAR = "linear"
    EXPONENTIAL = "exponential"


@dataclass
class Job:
    """A scheduled job."""
    id: str
    name: str
    expression: str
    command: str
    enabled: bool = True
    created_at: datetime = field(default_factory=datetime.now)
    max_retries: int = 0
    retry_strategy: RetryStrategy = RetryStrategy.NONE
    retry_base_delay: float = 10.0
    retry_max_delay: float = 300.0
    timeout_seconds: int = 300
    depends_on: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    working_dir: str | None = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "expression": self.expression,
            "command": self.command,
            "enabled": self.enabled,
            "created_at": self.created_at.isoformat(),
            "max_retries": self.max_retries,
            "retry_strategy": self.retry_strategy.value,
            "retry_base_delay": self.retry_base_delay,
            "retry_max_delay": self.retry_max_delay,
            "timeout_seconds": self.timeout_seconds,
            "depends_on": self.depends_on,
            "tags": self.tags,
            "metadata": self.metadata,
            "working_dir": self.working_dir,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Job":
        return cls(
            id=data["id"],
            name=data["name"],
            expression=data["expression"],
            command=data["command"],
            enabled=data.get("enabled", True),
            created_at=datetime.fromisoformat(data["created_at"]),
            max_retries=data.get("max_retries", 0),
            retry_strategy=RetryStrategy(data.get("retry_strategy", "none")),
            retry_base_delay=data.get("retry_base_delay", 10.0),
            retry_max_delay=data.get("retry_max_delay", 300.0),
            timeout_seconds=data.get("timeout_seconds", 300),
            depends_on=data.get("depends_on", []),
            tags=data.get("tags", []),
            metadata=data.get("metadata", {}),
            working_dir=data.get("working_dir"),
        )


@dataclass
class Execution:
    """A record of a single job execution."""
    id: str
    job_id: str
    job_name: str
    started_at: datetime
    finished_at: datetime | None = None
    state: JobState = JobState.PENDING
    exit_code: int | None = None
    stdout: str = ""
    stderr: str = ""
    attempt: int = 1
    duration_ms: int | None = None
    trigger: str = "scheduled"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "job_id": self.job_id,
            "job_name": self.job_name,
            "started_at": self.started_at.isoformat(),
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "state": self.state.value,
            "exit_code": self.exit_code,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "attempt": self.attempt,
            "duration_ms": self.duration_ms,
            "trigger": self.trigger,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Execution":
        return cls(
            id=data["id"],
            job_id=data["job_id"],
            job_name=data.get("job_name", ""),
            started_at=datetime.fromisoformat(data["started_at"]),
            finished_at=(
                datetime.fromisoformat(data["finished_at"])
                if data.get("finished_at")
                else None
            ),
            state=JobState(data.get("state", "pending")),
            exit_code=data.get("exit_code"),
            stdout=data.get("stdout", ""),
            stderr=data.get("stderr", ""),
            attempt=data.get("attempt", 1),
            duration_ms=data.get("duration_ms"),
            trigger=data.get("trigger", "scheduled"),
        )


@dataclass
class SchedulerStats:
    """Aggregate scheduler statistics."""
    total_jobs: int = 0
    enabled_jobs: int = 0
    total_executions: int = 0
    success_count: int = 0
    failure_count: int = 0
    timeout_count: int = 0
    avg_duration_ms: float = 0.0
    uptime_seconds: float = 0.0
    is_running: bool = False

    def to_dict(self) -> dict:
        return {
            "total_jobs": self.total_jobs,
            "enabled_jobs": self.enabled_jobs,
            "total_executions": self.total_executions,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "timeout_count": self.timeout_count,
            "avg_duration_ms": round(self.avg_duration_ms, 2),
            "uptime_seconds": round(self.uptime_seconds, 2),
            "is_running": self.is_running,
        }
