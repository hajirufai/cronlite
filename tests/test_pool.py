"""Tests for the worker pool."""

import threading
import time
import unittest

from cronlite.scheduler.pool import WorkerPool


class TestWorkerPool(unittest.TestCase):

    def test_basic_submit(self):
        pool = WorkerPool(max_workers=2)
        pool.start()
        results = []
        event = threading.Event()

        def task():
            results.append(1)
            event.set()

        pool.submit(task)
        event.wait(timeout=5)
        pool.shutdown()
        self.assertEqual(results, [1])

    def test_multiple_tasks(self):
        pool = WorkerPool(max_workers=4)
        pool.start()
        results = []
        lock = threading.Lock()
        done = threading.Event()
        count = 0

        def task(val):
            nonlocal count
            with lock:
                results.append(val)
                count += 1
                if count >= 5:
                    done.set()

        for i in range(5):
            pool.submit(task, i)

        done.wait(timeout=10)
        pool.shutdown()
        self.assertEqual(len(results), 5)
        self.assertEqual(sorted(results), [0, 1, 2, 3, 4])

    def test_concurrent_execution(self):
        pool = WorkerPool(max_workers=4)
        pool.start()
        timestamps = []
        lock = threading.Lock()
        barrier = threading.Barrier(4, timeout=5)

        def task():
            barrier.wait()
            with lock:
                timestamps.append(time.time())

        for _ in range(4):
            pool.submit(task)

        time.sleep(2)
        pool.shutdown()
        self.assertEqual(len(timestamps), 4)
        # All should execute at approximately the same time
        spread = max(timestamps) - min(timestamps)
        self.assertLess(spread, 2.0)

    def test_exception_doesnt_crash_pool(self):
        pool = WorkerPool(max_workers=2)
        pool.start()
        results = []
        done = threading.Event()

        def bad_task():
            raise RuntimeError("boom")

        def good_task():
            results.append("ok")
            done.set()

        pool.submit(bad_task)
        pool.submit(good_task)
        done.wait(timeout=5)
        pool.shutdown()
        self.assertEqual(results, ["ok"])

    def test_submit_before_start_raises(self):
        pool = WorkerPool()
        with self.assertRaises(RuntimeError):
            pool.submit(lambda: None)

    def test_active_count(self):
        pool = WorkerPool(max_workers=2)
        pool.start()
        self.assertEqual(pool.active_count, 0)
        pool.shutdown()

    def test_shutdown_idempotent(self):
        pool = WorkerPool(max_workers=1)
        pool.start()
        pool.shutdown()
        pool.shutdown()  # Should not raise


if __name__ == "__main__":
    unittest.main()
