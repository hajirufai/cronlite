"""Basic scheduling example — parse expressions, add jobs, trigger them."""

from datetime import datetime

from cronlite import CronParser, Job, MemoryStore, SchedulerEngine, Config


def main():
    print("=== CronLite: Basic Scheduling ===\n")

    # 1. Parse cron expressions
    parser = CronParser()

    expressions = [
        "*/15 * * * *",
        "0 9-17 * * MON-FRI",
        "30 2 * * *",
        "@daily",
        "@hourly",
    ]

    print("Parsing cron expressions:")
    for expr_str in expressions:
        expr = parser.parse(expr_str)
        print(f"  {expr_str:<25} → {expr.explain()}")
        runs = expr.next_n_runs(datetime.now(), 3)
        for r in runs:
            print(f"    Next: {r.strftime('%Y-%m-%d %H:%M')} ({r.strftime('%A')})")
        print()

    # 2. Create a scheduler with in-memory store
    store = MemoryStore()
    engine = SchedulerEngine(store, Config(max_workers=2))

    # 3. Add some jobs
    jobs = [
        Job(id="", name="health-check", expression="*/5 * * * *",
            command="echo 'System healthy!'"),
        Job(id="", name="backup-db", expression="0 2 * * *",
            command="echo 'Backing up database...'"),
        Job(id="", name="send-report", expression="0 9 * * MON",
            command="echo 'Sending weekly report'"),
    ]

    print("Adding jobs to scheduler:")
    for job in jobs:
        added = engine.add_job(job)
        print(f"  ✓ {added.name} [{added.id}] — {added.expression}")

    # 4. Trigger a job manually
    print("\nTriggering health-check manually:")
    exec_result = engine.trigger_job(jobs[0].id)
    print(f"  State:    {exec_result.state.value}")
    print(f"  Duration: {exec_result.duration_ms}ms")
    print(f"  Output:   {exec_result.stdout.strip()}")

    # 5. Get stats
    stats = engine.get_stats()
    print(f"\nScheduler stats:")
    print(f"  Total jobs:    {stats.total_jobs}")
    print(f"  Executions:    {stats.total_executions}")
    print(f"  Successes:     {stats.success_count}")


if __name__ == "__main__":
    main()
