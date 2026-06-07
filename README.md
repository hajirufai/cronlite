# CronLite

A lightweight task scheduler with cron expression parsing built from scratch in Python. Zero external dependencies.

## Features

- **Complete Cron Parser** — Full POSIX cron syntax: wildcards, ranges, steps, lists, month/day names, presets (`@daily`, `@hourly`, etc.)
- **Smart Scheduling** — Priority-queue engine that efficiently computes and fires jobs at the right time
- **Reliable Execution** — Subprocess runner with timeout, output capture, and configurable retry strategies (fixed, linear, exponential backoff)
- **Job Dependencies** — DAG-based dependency graph with cycle detection and topological ordering
- **Persistent Storage** — SQLite backend for crash recovery and execution history
- **HTTP API** — RESTful endpoints for remote job management
- **CLI** — Full command-line interface for job management and cron expression tools
- **Health Monitoring** — Missed job detection, overdue alerts, execution statistics

## Quick Start

```bash
git clone https://github.com/hajirufai/cronlite.git
cd cronlite

# Run tests
python -m pytest -v

# Start the scheduler
python -m cronlite start

# Add a job
python -m cronlite add "backup" "0 2 * * *" "pg_dump mydb > backup.sql"

# Add a job with retry
python -m cronlite add "etl" "*/15 * * * *" "python etl.py" --retries 3 --timeout 600

# Add dependent job
python -m cronlite add "report" "@daily" "python report.py" --depends-on etl

# Explain a cron expression
python -m cronlite explain "*/15 9-17 * * MON-FRI"
# → Every 15 minutes, between 9:00 AM and 5:00 PM, Monday through Friday

# Get next run times
python -m cronlite next "0 2 * * *" --count 5

# List all jobs
python -m cronlite list

# View execution history
python -m cronlite history etl --last 10

# View stats
python -m cronlite stats etl

# Run demo
python -m cronlite demo
```

## Cron Expression Syntax

```
┌───────────── minute (0-59)
│ ┌───────────── hour (0-23)
│ │ ┌───────────── day of month (1-31)
│ │ │ ┌───────────── month (1-12 or JAN-DEC)
│ │ │ │ ┌───────────── day of week (0-6, SUN-SAT, 0=Sunday)
│ │ │ │ │
* * * * *
```

| Symbol | Meaning | Example |
|--------|---------|---------|
| `*` | Any value | `* * * * *` — every minute |
| `,` | List | `1,15,30 * * * *` — minutes 1, 15, 30 |
| `-` | Range | `9-17 * * * *` — hours 9 through 17 |
| `/` | Step | `*/15 * * * *` — every 15 minutes |
| Names | Month/day | `* * * JAN-MAR MON-FRI` |

### Named Presets

| Preset | Equivalent | Description |
|--------|-----------|-------------|
| `@yearly` | `0 0 1 1 *` | Once a year (Jan 1) |
| `@monthly` | `0 0 1 * *` | First of every month |
| `@weekly` | `0 0 * * 0` | Every Sunday |
| `@daily` | `0 0 * * *` | Every midnight |
| `@hourly` | `0 * * * *` | Every hour |

## Architecture

```
cronlite/
├── cron/
│   ├── parser.py          # Cron expression tokenizer + validator
│   ├── fields.py          # Field types with range validation
│   ├── expression.py      # CronExpression: matches(), next_run()
│   └── presets.py         # @daily, @hourly, etc.
├── scheduler/
│   ├── engine.py          # Priority-queue scheduling loop
│   ├── executor.py        # Subprocess runner with timeout
│   ├── pool.py            # Thread pool for concurrent execution
│   └── hooks.py           # Lifecycle callbacks
├── retry.py               # Fixed / linear / exponential backoff
├── dag.py                 # Dependency graph with cycle detection
├── store.py               # Memory + SQLite storage backends
├── history.py             # Execution history + analytics
├── health.py              # Missed jobs, overdue detection, stats
├── api.py                 # RESTful HTTP API
├── cli.py                 # Command-line interface
├── config.py              # Configuration management
├── types.py               # Data types and enums
├── errors.py              # Custom exceptions
└── utils.py               # ID generation, formatting helpers
```

## How It Works

### 1. Cron Parsing
The parser tokenizes a cron expression into five fields, each resolving to a set of valid values:

```python
from cronlite.cron import CronParser

parser = CronParser()
expr = parser.parse("*/15 9-17 * * MON-FRI")

# Check if a datetime matches
from datetime import datetime
dt = datetime(2026, 6, 2, 10, 30)  # Monday, 10:30 AM
print(expr.matches(dt))  # True

# Compute next run time
next_time = expr.next_run(datetime.now())
print(next_time)  # Next matching minute
```

### 2. The `next_run` Algorithm
Computing the next matching datetime is the most algorithmically interesting part. The algorithm walks forward through time, checking each field from most-significant (month) to least-significant (minute), carrying over when a field wraps around:

1. Start from `after + 1 minute` (truncated to minute boundary)
2. Check month — if no match, advance to next matching month, reset day/hour/minute
3. Check day (union of day-of-month and day-of-week per POSIX spec)
4. Check hour — advance if needed, reset minute
5. Check minute — advance if needed
6. Carry propagation: minute overflow → hour++, hour overflow → day++, etc.

### 3. Scheduling Engine
The engine uses a min-heap (priority queue) keyed by next-run timestamp. Each tick:
1. Peek at the queue head
2. If `next_run ≤ now`: pop the job, submit to worker pool, compute new `next_run`, re-push
3. Otherwise: sleep until the next job is due

### 4. Retry & Dependencies
Failed jobs are retried with configurable backoff. Jobs with dependencies only fire when all upstream jobs have succeeded in the current scheduling window.

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/jobs` | List all jobs |
| `POST` | `/api/v1/jobs` | Create a job |
| `GET` | `/api/v1/jobs/{id}` | Get job details |
| `PUT` | `/api/v1/jobs/{id}` | Update a job |
| `DELETE` | `/api/v1/jobs/{id}` | Delete a job |
| `POST` | `/api/v1/jobs/{id}/trigger` | Manually trigger |
| `POST` | `/api/v1/jobs/{id}/pause` | Pause a job |
| `POST` | `/api/v1/jobs/{id}/resume` | Resume a job |
| `GET` | `/api/v1/jobs/{id}/history` | Execution history |
| `GET` | `/api/v1/health` | Scheduler health |
| `POST` | `/api/v1/cron/validate` | Validate expression |
| `POST` | `/api/v1/cron/next` | Next N run times |

## Retry Strategies

```python
from cronlite import RetryStrategy

# Fixed delay: wait 30s between each retry
job.retry_strategy = RetryStrategy.FIXED
job.retry_base_delay = 30
job.max_retries = 3

# Exponential backoff: 10s → 20s → 40s → 80s (capped at 300s)
job.retry_strategy = RetryStrategy.EXPONENTIAL
job.retry_base_delay = 10
job.retry_max_delay = 300
job.max_retries = 5
```

## Requirements

- Python 3.11+
- No external dependencies

## Tests

```bash
python -m pytest -v              # Run all tests
python -m pytest tests/test_parser.py -v  # Just parser tests
python -m pytest --tb=short      # Compact output
```

## License

MIT
