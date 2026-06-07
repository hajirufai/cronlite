"""Retry strategies example — fixed, linear, and exponential backoff."""

from cronlite import Job, MemoryStore, SchedulerEngine, Config
from cronlite.types import RetryStrategy


def main():
    print("=== CronLite: Retry Strategies ===\n")

    store = MemoryStore()
    engine = SchedulerEngine(store, Config(max_workers=2))

    # Job with exponential backoff
    job = Job(
        id="",
        name="flaky-api-call",
        expression="*/10 * * * *",
        command="exit 1",  # Always fails for demo
        max_retries=3,
        retry_strategy=RetryStrategy.EXPONENTIAL,
        retry_base_delay=0.1,  # Short delays for demo
        retry_max_delay=1.0,
    )

    engine.add_job(job)
    print(f"Added job: {job.name}")
    print(f"  Retries: {job.max_retries} (exponential)")
    print(f"  Base delay: {job.retry_base_delay}s")
    print()

    # Trigger it — will fail and retry
    print("Triggering (will fail with retries)...")
    execution = engine.trigger_job(job.id)
    print(f"  Final state: {execution.state.value}")
    print(f"  Attempts: {execution.attempt}")
    print(f"  Duration: {execution.duration_ms}ms")
    print()

    # Show retry delay calculations
    from cronlite.retry import RetryPolicy

    strategies = [
        ("fixed", RetryStrategy.FIXED, 10.0),
        ("linear", RetryStrategy.LINEAR, 10.0),
        ("exponential", RetryStrategy.EXPONENTIAL, 5.0),
    ]

    print("Retry delay comparison (base=10s for fixed/linear, 5s for exponential):")
    print(f"  {'Attempt':<10} {'Fixed':<12} {'Linear':<12} {'Exponential':<12}")
    print(f"  {'─' * 46}")

    for attempt in range(1, 6):
        delays = []
        for name, strategy, base in strategies:
            policy = RetryPolicy(
                strategy=strategy, max_retries=10,
                base_delay=base, max_delay=300.0,
            )
            delays.append(f"{policy.compute_delay(attempt):.1f}s")
        print(f"  {attempt:<10} {delays[0]:<12} {delays[1]:<12} {delays[2]:<12}")


if __name__ == "__main__":
    main()
