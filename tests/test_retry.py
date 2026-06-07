"""Tests for retry strategies."""

import unittest

from cronlite.retry import RetryPolicy
from cronlite.types import RetryStrategy


class TestRetryPolicy(unittest.TestCase):

    def test_none_never_retries(self):
        policy = RetryPolicy(strategy=RetryStrategy.NONE)
        self.assertFalse(policy.should_retry(1))
        self.assertFalse(policy.should_retry(5))

    def test_fixed_delay(self):
        policy = RetryPolicy(
            strategy=RetryStrategy.FIXED,
            max_retries=3,
            base_delay=30.0,
        )
        self.assertEqual(policy.compute_delay(1), 30.0)
        self.assertEqual(policy.compute_delay(2), 30.0)
        self.assertEqual(policy.compute_delay(3), 30.0)

    def test_linear_delay(self):
        policy = RetryPolicy(
            strategy=RetryStrategy.LINEAR,
            max_retries=3,
            base_delay=10.0,
        )
        self.assertEqual(policy.compute_delay(1), 10.0)
        self.assertEqual(policy.compute_delay(2), 20.0)
        self.assertEqual(policy.compute_delay(3), 30.0)

    def test_exponential_delay(self):
        policy = RetryPolicy(
            strategy=RetryStrategy.EXPONENTIAL,
            max_retries=5,
            base_delay=10.0,
        )
        self.assertEqual(policy.compute_delay(1), 10.0)
        self.assertEqual(policy.compute_delay(2), 20.0)
        self.assertEqual(policy.compute_delay(3), 40.0)
        self.assertEqual(policy.compute_delay(4), 80.0)

    def test_exponential_capped(self):
        policy = RetryPolicy(
            strategy=RetryStrategy.EXPONENTIAL,
            max_retries=10,
            base_delay=10.0,
            max_delay=100.0,
        )
        # 10 * 2^4 = 160, but capped at 100
        self.assertEqual(policy.compute_delay(5), 100.0)

    def test_should_retry_within_limit(self):
        policy = RetryPolicy(
            strategy=RetryStrategy.FIXED,
            max_retries=3,
            base_delay=10.0,
        )
        self.assertTrue(policy.should_retry(1))
        self.assertTrue(policy.should_retry(2))
        self.assertFalse(policy.should_retry(3))
        self.assertFalse(policy.should_retry(4))

    def test_linear_capped(self):
        policy = RetryPolicy(
            strategy=RetryStrategy.LINEAR,
            max_retries=10,
            base_delay=100.0,
            max_delay=250.0,
        )
        self.assertEqual(policy.compute_delay(3), 250.0)

    def test_none_delay_is_zero(self):
        policy = RetryPolicy(strategy=RetryStrategy.NONE)
        self.assertEqual(policy.compute_delay(1), 0.0)

    def test_repr(self):
        policy = RetryPolicy(
            strategy=RetryStrategy.EXPONENTIAL,
            max_retries=3,
            base_delay=10.0,
        )
        r = repr(policy)
        self.assertIn("exponential", r)
        self.assertIn("3", r)


if __name__ == "__main__":
    unittest.main()
