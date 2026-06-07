"""Health monitoring example — check for missed, overdue, and failed jobs."""

from datetime import datetime, timedelta

from cronlite import Job, MemoryStore, SchedulerEngine, Config
from cronlite.health import HealthChecker
from cronlite.types import Execution, JobState


def main():
    print("=== CronLite: Health Monitoring ===\n")

    store = MemoryStore()
    engine = SchedulerEngine(store, Config(max_workers=2))
    checker = HealthChecker(store)

    # Add jobs
    jobs = [
        Job(id="", name="healthy-job", expression="*/5 * * * *",
            command="echo OK"),
        Job(id="", name="failing-job", expression="*/10 * * * *",
            command="exit 1"),
        Job(id="", name="slow-job", expression="0 * * * *",
            command="sleep 0.1", timeout_seconds=60),
    ]

    for j in jobs:
        engine.add_job(j)

    # Execute some jobs
    print("Running jobs:")
    for j in store.list_jobs():
        result = engine.trigger_job(j.id)
        icon = "✓" if result.state == JobState.SUCCESS else "✗"
        print(f"  {icon} {j.name}: {result.state.value}")

    # Simulate a "running" job that's overdue
    overdue_exec = Execution(
        id="overdue_001",
        job_id=jobs[2].id,
        job_name="slow-job",
        started_at=datetime.now() - timedelta(minutes=5),
        state=JobState.RUNNING,
    )
    store.save_execution(overdue_exec)

    # Get health report
    print("\n--- Health Report ---")
    report = checker.get_health_report()
    print(f"  Status:        {report['status']}")
    print(f"  Total jobs:    {report['total_jobs']}")
    print(f"  Enabled:       {report['enabled_jobs']}")
    print(f"  Disabled:      {report['disabled_jobs']}")

    if report["overdue_jobs"]:
        print(f"\n  ⚠ Overdue jobs:")
        for o in report["overdue_jobs"]:
            print(f"    {o['job_name']} — running for {o['elapsed_seconds']:.0f}s "
                  f"(timeout: {o['timeout_seconds']}s)")

    if report["recent_failures"]:
        print(f"\n  ✗ Recent failures:")
        for f in report["recent_failures"]:
            print(f"    {f['job_name']} — {f['state']}")

    if report["missed_jobs"]:
        print(f"\n  ⏭ Missed jobs:")
        for m in report["missed_jobs"]:
            print(f"    {m['job_name']} — expected at {m['expected_run']}")

    print(f"\n  Checked at: {report['checked_at']}")


if __name__ == "__main__":
    main()
