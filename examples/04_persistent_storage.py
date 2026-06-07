"""Persistent storage example — SQLite backend for job and execution data."""

import os
import tempfile
from datetime import datetime

from cronlite import Job, SQLiteStore, SchedulerEngine, Config
from cronlite.history import ExecutionHistory
from cronlite.types import RetryStrategy


def main():
    print("=== CronLite: Persistent Storage (SQLite) ===\n")

    # Use a temp file for the demo
    db_path = os.path.join(tempfile.gettempdir(), "cronlite_demo.db")

    # Clean up from previous runs
    if os.path.exists(db_path):
        os.remove(db_path)

    store = SQLiteStore(db_path)
    config = Config(db_path=db_path, max_workers=2)
    engine = SchedulerEngine(store, config)

    print(f"Database: {db_path}\n")

    # Add jobs
    jobs_data = [
        ("disk-check", "*/30 * * * *", "df -h / | tail -1"),
        ("memory-check", "*/15 * * * *", "free -m | head -2"),
        ("uptime-log", "0 * * * *", "uptime"),
    ]

    for name, expr, cmd in jobs_data:
        job = Job(id="", name=name, expression=expr, command=cmd)
        engine.add_job(job)
        print(f"  Added: {name} — {expr}")

    # Run each job once
    print("\nExecuting jobs:")
    for job in store.list_jobs():
        execution = engine.trigger_job(job.id)
        print(f"  {job.name}: {execution.state.value} ({execution.duration_ms}ms)")
        if execution.stdout.strip():
            for line in execution.stdout.strip().split("\n"):
                print(f"    | {line}")

    # Query execution history
    history = ExecutionHistory(store)
    print("\nExecution history:")
    for e in history.get_recent(limit=10):
        print(f"  [{e.started_at.strftime('%H:%M:%S')}] {e.job_name}: {e.state.value}")

    # Get stats
    print("\nStatistics:")
    stats = history.get_stats()
    print(f"  Total executions: {stats['total_count']}")
    print(f"  Success rate:     {stats['success_rate']:.0f}%")
    print(f"  Avg duration:     {stats['avg_duration_ms']:.0f}ms")

    # Verify persistence: create a new store from the same DB
    print("\nVerifying persistence (new connection):")
    store2 = SQLiteStore(db_path)
    jobs2 = store2.list_jobs()
    print(f"  Jobs in DB: {len(jobs2)}")
    for j in jobs2:
        print(f"    {j.name} — {j.expression} (enabled: {j.enabled})")

    # Cleanup
    os.remove(db_path)
    print(f"\nCleaned up {db_path}")


if __name__ == "__main__":
    main()
