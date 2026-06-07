"""Retry strategies for failed job executions.

Supports fixed delay, linear backoff, and exponential backoff with
an optional maximum delay cap.
"""

from cronlite.types import RetryStrategy


class RetryPolicy:
    """Computes retry delays and decides whether to retry."""

    def __init__(
        self,
        strategy: RetryStrategy = RetryStrategy.NONE,
        max_retries: int = 0,
        base_delay: float = 10.0,
        max_delay: float = 300.0,
    ):
        self.strategy = strategy
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay

    def should_retry(self, attempt: int) -> bool:
        """Return True if the job should be retried after this attempt."""
        if self.strategy == RetryStrategy.NONE:
            return False
        return attempt < self.max_retries

    def compute_delay(self, attempt: int) -> float:
        """Compute the delay in seconds before the next retry.

        Args:
            attempt: The just-completed attempt number (1-based).
                     Delay is before attempt+1.

        Returns:
            Seconds to wait before retrying.
        """
        if self.strategy == RetryStrategy.NONE:
            return 0.0

        if self.strategy == RetryStrategy.FIXED:
            delay = self.base_delay

        elif self.strategy == RetryStrategy.LINEAR:
            delay = self.base_delay * attempt

        elif self.strategy == RetryStrategy.EXPONENTIAL:
            delay = self.base_delay * (2 ** (attempt - 1))

        else:
            delay = self.base_delay

        return min(delay, self.max_delay)

    @classmethod
    def from_job(cls, job) -> "RetryPolicy":
        """Create a RetryPolicy from a Job's configuration."""
        return cls(
            strategy=job.retry_strategy,
            max_retries=job.max_retries,
            base_delay=job.retry_base_delay,
            max_delay=job.retry_max_delay,
        )

    def __repr__(self) -> str:
        return (
            f"RetryPolicy(strategy={self.strategy.value}, "
            f"max_retries={self.max_retries}, "
            f"base_delay={self.base_delay}s, "
            f"max_delay={self.max_delay}s)"
        )
