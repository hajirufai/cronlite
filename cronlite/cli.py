"""Command-line interface for CronLite.

Provides commands for managing the scheduler, jobs, and cron expressions.
"""

import argparse
import json
import logging
import sys
import time
from datetime import datetime

from cronlite.api import APIServer
from cronlite.config import Config
from cronlite.cron import CronParser
from cronlite.errors import CronLiteError
from cronlite.health import HealthChecker
from cronlite.history import ExecutionHistory
from cronlite.scheduler.engine import SchedulerEngine
from cronlite.store import MemoryStore, SQLiteStore
from cronlite.types import Job, JobState, RetryStrategy
from cronlite.utils import format_duration, format_datetime, generate_job_id


def main(argv: list[str] | None = None) -> int:
    """Entry point for the CLI."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if not hasattr(args, "func"):
        parser.print_help()
        return 0

    try:
        return args.func(args)
    except CronLiteError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cronlite",
        description="CronLite — Lightweight Task Scheduler",
    )
    parser.add_argument(
        "--db", default="cronlite.db", help="Database file path (default: cronlite.db)"
    )
    sub = parser.add_subparsers(dest="command")

    # --- start ---
    p_start = sub.add_parser("start", help="Start the scheduler")
    p_start.add_argument("--workers", type=int, default=4, help="Max worker threads")
    p_start.add_argument("--port", type=int, default=8080, help="API port")
    p_start.add_argument("--no-api", action="store_true", help="Disable HTTP API")
    p_start.set_defaults(func=cmd_start)

    # --- add ---
    p_add = sub.add_parser("add", help="Add a job")
    p_add.add_argument("name", help="Job name")
    p_add.add_argument("expression", help="Cron expression or preset (@daily, etc.)")
    p_add.add_argument("command", help="Shell command to execute")
    p_add.add_argument("--retries", type=int, default=0, help="Max retries on failure")
    p_add.add_argument(
        "--retry-strategy",
        choices=["fixed", "linear", "exponential"],
        default="exponential",
        help="Retry backoff strategy",
    )
    p_add.add_argument("--timeout", type=int, default=300, help="Timeout in seconds")
    p_add.add_argument("--depends-on", nargs="*", default=[], help="Job names this depends on")
    p_add.add_argument("--tags", nargs="*", default=[], help="Tags for filtering")
    p_add.add_argument("--disabled", action="store_true", help="Create job as disabled")
    p_add.set_defaults(func=cmd_add)

    # --- remove ---
    p_rm = sub.add_parser("remove", help="Remove a job")
    p_rm.add_argument("name", help="Job name or ID")
    p_rm.set_defaults(func=cmd_remove)

    # --- list ---
    p_ls = sub.add_parser("list", help="List all jobs")
    p_ls.add_argument("--tag", help="Filter by tag")
    p_ls.add_argument("--json", action="store_true", dest="as_json", help="JSON output")
    p_ls.set_defaults(func=cmd_list)

    # --- enable / disable ---
    p_en = sub.add_parser("enable", help="Enable a job")
    p_en.add_argument("name", help="Job name or ID")
    p_en.set_defaults(func=cmd_enable)

    p_dis = sub.add_parser("disable", help="Disable a job")
    p_dis.add_argument("name", help="Job name or ID")
    p_dis.set_defaults(func=cmd_disable)

    # --- trigger ---
    p_trig = sub.add_parser("trigger", help="Manually trigger a job")
    p_trig.add_argument("name", help="Job name or ID")
    p_trig.set_defaults(func=cmd_trigger)

    # --- explain ---
    p_exp = sub.add_parser("explain", help="Explain a cron expression in plain English")
    p_exp.add_argument("expression", help="Cron expression")
    p_exp.set_defaults(func=cmd_explain)

    # --- next ---
    p_next = sub.add_parser("next", help="Show next run times for a cron expression")
    p_next.add_argument("expression", help="Cron expression")
    p_next.add_argument("--count", type=int, default=5, help="Number of run times")
    p_next.set_defaults(func=cmd_next)

    # --- history ---
    p_hist = sub.add_parser("history", help="Show execution history")
    p_hist.add_argument("name", nargs="?", help="Job name or ID (all jobs if omitted)")
    p_hist.add_argument("--last", type=int, default=10, help="Number of entries")
    p_hist.add_argument("--state", help="Filter by state (success/failed/timeout)")
    p_hist.set_defaults(func=cmd_history)

    # --- stats ---
    p_stats = sub.add_parser("stats", help="Show job execution statistics")
    p_stats.add_argument("name", nargs="?", help="Job name or ID (all jobs if omitted)")
    p_stats.set_defaults(func=cmd_stats)

    # --- status ---
    p_status = sub.add_parser("status", help="Show scheduler status")
    p_status.set_defaults(func=cmd_status)

    # --- demo ---
    p_demo = sub.add_parser("demo", help="Run an interactive demo")
    p_demo.set_defaults(func=cmd_demo)

    return parser


def _get_store(args) -> SQLiteStore:
    return SQLiteStore(args.db)


def _find_job(store, name_or_id: str) -> Job:
    """Find a job by name or ID."""
    # Try by name first
    job = store.get_job_by_name(name_or_id)
    if job:
        return job
    # Try by ID
    return store.get_job(name_or_id)


# --- Command implementations ---


def cmd_start(args) -> int:
    config = Config(
        max_workers=args.workers,
        db_path=args.db,
        api_port=args.port,
    )
    store = SQLiteStore(config.db_path)
    engine = SchedulerEngine(store, config)

    if not args.no_api:
        api = APIServer(engine, store, config)
        api.start()
        print(f"API server listening on http://{config.api_host}:{config.api_port}")

    print(f"Starting scheduler with {config.max_workers} workers...")
    print("Press Ctrl+C to stop")

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
    engine.start_blocking()
    return 0


def cmd_add(args) -> int:
    store = _get_store(args)
    parser = CronParser()

    # Validate expression
    parser.parse(args.expression)

    # Resolve depends_on names to IDs
    dep_ids = []
    for dep_name in args.depends_on:
        dep_job = store.get_job_by_name(dep_name)
        if dep_job:
            dep_ids.append(dep_job.id)
        else:
            dep_ids.append(dep_name)  # Assume it's already an ID

    strategy = RetryStrategy.NONE
    if args.retries > 0:
        strategy = RetryStrategy(args.retry_strategy)

    job = Job(
        id=generate_job_id(args.name),
        name=args.name,
        expression=args.expression,
        command=args.command,
        enabled=not args.disabled,
        created_at=datetime.now(),
        max_retries=args.retries,
        retry_strategy=strategy,
        timeout_seconds=args.timeout,
        depends_on=dep_ids,
        tags=args.tags,
    )

    store.save_job(job)
    expr = parser.parse(args.expression)
    next_run = expr.next_run(datetime.now())

    print(f"✓ Added job: {job.name}")
    print(f"  ID:         {job.id}")
    print(f"  Schedule:   {args.expression}")
    print(f"  Command:    {args.command}")
    print(f"  Next run:   {format_datetime(next_run)}")
    if args.retries > 0:
        print(f"  Retries:    {args.retries} ({args.retry_strategy})")
    if dep_ids:
        print(f"  Depends on: {', '.join(dep_ids)}")
    return 0


def cmd_remove(args) -> int:
    store = _get_store(args)
    job = _find_job(store, args.name)
    store.delete_job(job.id)
    print(f"✓ Removed job: {job.name} [{job.id}]")
    return 0


def cmd_list(args) -> int:
    store = _get_store(args)
    jobs = store.list_jobs()
    parser = CronParser()

    if args.tag:
        jobs = [j for j in jobs if args.tag in j.tags]

    if args.as_json:
        print(json.dumps([j.to_dict() for j in jobs], indent=2, default=str))
        return 0

    if not jobs:
        print("No jobs found.")
        return 0

    # Table format
    print(f"{'Name':<20} {'Schedule':<20} {'Enabled':<8} {'Next Run':<20} {'Tags'}")
    print("─" * 90)
    for job in jobs:
        try:
            expr = parser.parse(job.expression)
            next_run = format_datetime(expr.next_run(datetime.now()))
        except Exception:
            next_run = "—"

        tags = ", ".join(job.tags) if job.tags else "—"
        status = "✓" if job.enabled else "✗"
        print(f"{job.name:<20} {job.expression:<20} {status:<8} {next_run:<20} {tags}")

    print(f"\n{len(jobs)} job(s) total")
    return 0


def cmd_enable(args) -> int:
    store = _get_store(args)
    job = _find_job(store, args.name)
    job.enabled = True
    store.update_job(job)
    print(f"✓ Enabled job: {job.name}")
    return 0


def cmd_disable(args) -> int:
    store = _get_store(args)
    job = _find_job(store, args.name)
    job.enabled = False
    store.update_job(job)
    print(f"✓ Disabled job: {job.name}")
    return 0


def cmd_trigger(args) -> int:
    store = _get_store(args)
    job = _find_job(store, args.name)

    from cronlite.scheduler.executor import JobExecutor
    executor = JobExecutor()
    execution = executor.execute(job, trigger="manual")
    store.save_execution(execution)

    state_icon = "✓" if execution.state == JobState.SUCCESS else "✗"
    print(f"{state_icon} {job.name} — {execution.state.value}")
    print(f"  Duration: {format_duration(execution.duration_ms)}")
    print(f"  Exit code: {execution.exit_code}")
    if execution.stdout.strip():
        print(f"  stdout:\n{execution.stdout.rstrip()}")
    if execution.stderr.strip() and execution.state != JobState.SUCCESS:
        print(f"  stderr:\n{execution.stderr.rstrip()}")
    return 0 if execution.state == JobState.SUCCESS else 1


def cmd_explain(args) -> int:
    parser = CronParser()
    expr = parser.parse(args.expression)
    print(f"Expression: {args.expression}")
    print(f"Meaning:    {expr.explain()}")
    return 0


def cmd_next(args) -> int:
    parser = CronParser()
    expr = parser.parse(args.expression)
    runs = expr.next_n_runs(datetime.now(), args.count)
    print(f"Next {len(runs)} runs for '{args.expression}':")
    for i, r in enumerate(runs, 1):
        weekday = r.strftime("%A")
        print(f"  {i}. {format_datetime(r)}  ({weekday})")
    return 0


def cmd_history(args) -> int:
    store = _get_store(args)
    history = ExecutionHistory(store)

    job_id = None
    if args.name:
        job = _find_job(store, args.name)
        job_id = job.id

    if args.state:
        state = JobState(args.state)
        execs = history.get_by_state(state, limit=args.last)
        if job_id:
            execs = [e for e in execs if e.job_id == job_id]
    elif job_id:
        execs = history.get_last_n(job_id, n=args.last)
    else:
        execs = history.get_recent(limit=args.last)

    if not execs:
        print("No execution history found.")
        return 0

    print(f"{'Time':<20} {'Job':<18} {'State':<10} {'Duration':<10} {'Exit'}")
    print("─" * 70)
    for e in execs:
        icon = {"success": "✓", "failed": "✗", "timeout": "⏱", "running": "▶"}.get(
            e.state.value, "?"
        )
        print(
            f"{format_datetime(e.started_at):<20} "
            f"{e.job_name:<18} "
            f"{icon} {e.state.value:<8} "
            f"{format_duration(e.duration_ms):<10} "
            f"{e.exit_code if e.exit_code is not None else '—'}"
        )
    return 0


def cmd_stats(args) -> int:
    store = _get_store(args)
    history = ExecutionHistory(store)

    job_id = None
    label = "All jobs"
    if args.name:
        job = _find_job(store, args.name)
        job_id = job.id
        label = job.name

    stats = history.get_stats(job_id)
    print(f"Statistics for: {label}")
    print(f"  Total executions:  {stats['total_count']}")
    print(f"  Successful:        {stats['success_count']}")
    print(f"  Failed:            {stats['failure_count']}")
    print(f"  Timed out:         {stats['timeout_count']}")
    print(f"  Success rate:      {stats['success_rate']:.1f}%")
    print(f"  Avg duration:      {format_duration(stats['avg_duration_ms'])}")
    if stats["min_duration_ms"] is not None:
        print(f"  Min duration:      {format_duration(stats['min_duration_ms'])}")
        print(f"  Max duration:      {format_duration(stats['max_duration_ms'])}")
    if stats["last_run"]:
        print(f"  Last run:          {stats['last_run']}")
    if stats["last_success"]:
        print(f"  Last success:      {stats['last_success']}")
    if stats["last_failure"]:
        print(f"  Last failure:      {stats['last_failure']}")
    return 0


def cmd_status(args) -> int:
    store = _get_store(args)
    jobs = store.list_jobs()
    enabled = sum(1 for j in jobs if j.enabled)
    execs = store.get_executions(limit=100)

    print("CronLite Status")
    print(f"  Database:    {args.db}")
    print(f"  Total jobs:  {len(jobs)} ({enabled} enabled)")
    print(f"  Executions:  {len(execs)} (last 100)")

    if execs:
        success = sum(1 for e in execs if e.state == JobState.SUCCESS)
        failed = sum(1 for e in execs if e.state == JobState.FAILED)
        print(f"  Success:     {success}")
        print(f"  Failed:      {failed}")
    return 0


def cmd_demo(args) -> int:
    """Run an interactive demo showing CronLite's capabilities."""
    parser = CronParser()

    print("=" * 60)
    print("  CronLite Demo — Lightweight Task Scheduler")
    print("=" * 60)
    print()

    # 1. Parse some expressions
    examples = [
        ("*/15 * * * *", "Every 15 minutes"),
        ("0 2 * * *", "Daily at 2 AM"),
        ("0 9-17 * * MON-FRI", "Hourly during business hours"),
        ("0 0 1 * *", "First of every month at midnight"),
        ("30 4 1,15 * *", "4:30 AM on 1st and 15th"),
    ]

    print("1. Cron Expression Parsing")
    print("─" * 40)
    for expr_str, _desc in examples:
        expr = parser.parse(expr_str)
        print(f"  {expr_str:<25} → {expr.explain()}")
    print()

    # 2. Next run times
    print("2. Next Run Computation")
    print("─" * 40)
    expr = parser.parse("*/15 9-17 * * MON-FRI")
    runs = expr.next_n_runs(datetime.now(), 5)
    print(f"  Schedule: */15 9-17 * * MON-FRI")
    print(f"  ({expr.explain()})")
    print()
    for i, r in enumerate(runs, 1):
        print(f"    {i}. {format_datetime(r)} ({r.strftime('%A')})")
    print()

    # 3. Job execution
    print("3. Job Execution")
    print("─" * 40)
    store = MemoryStore()
    from cronlite.scheduler.executor import JobExecutor
    executor = JobExecutor()

    demo_job = Job(
        id="demo_001",
        name="hello-world",
        expression="* * * * *",
        command="echo 'Hello from CronLite!'",
        timeout_seconds=10,
    )
    store.save_job(demo_job)

    execution = executor.execute(demo_job, trigger="demo")
    store.save_execution(execution)
    print(f"  Job:      {demo_job.name}")
    print(f"  Command:  {demo_job.command}")
    print(f"  State:    {execution.state.value}")
    print(f"  Duration: {format_duration(execution.duration_ms)}")
    print(f"  Output:   {execution.stdout.strip()}")
    print()

    # 4. Presets
    print("4. Named Presets")
    print("─" * 40)
    from cronlite.cron.presets import PRESETS
    for name, expansion in sorted(PRESETS.items()):
        if name in ("@annually", "@midnight"):
            continue
        expr = parser.parse(name)
        print(f"  {name:<12} → {expansion:<15} ({expr.explain()})")
    print()

    print("=" * 60)
    print("  Demo complete! Run 'cronlite start' to start scheduling.")
    print("=" * 60)
    return 0
