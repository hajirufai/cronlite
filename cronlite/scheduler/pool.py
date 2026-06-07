"""Thread pool for concurrent job execution."""

import logging
import threading
from queue import Queue, Empty
from typing import Callable, Any

logger = logging.getLogger("cronlite.pool")


class WorkerPool:
    """Fixed-size thread pool for executing jobs concurrently.

    Workers pull tasks from a shared queue and execute them.
    Provides bounded concurrency to prevent resource exhaustion.
    """

    def __init__(self, max_workers: int = 4):
        self._max_workers = max_workers
        self._queue: Queue = Queue()
        self._workers: list[threading.Thread] = []
        self._running = False
        self._active_count = 0
        self._lock = threading.Lock()

    def start(self) -> None:
        """Start the worker threads."""
        if self._running:
            return
        self._running = True
        for i in range(self._max_workers):
            t = threading.Thread(
                target=self._worker_loop,
                name=f"cronlite-worker-{i}",
                daemon=True,
            )
            t.start()
            self._workers.append(t)
        logger.info("Worker pool started with %d workers", self._max_workers)

    def submit(self, func: Callable, *args: Any, **kwargs: Any) -> None:
        """Submit a task to the pool.

        Args:
            func: The callable to execute.
            *args, **kwargs: Arguments to pass to func.
        """
        if not self._running:
            raise RuntimeError("Worker pool is not running")
        self._queue.put((func, args, kwargs))

    def shutdown(self, wait: bool = True) -> None:
        """Stop the pool, optionally waiting for all tasks to complete."""
        self._running = False
        if wait:
            # Send poison pills
            for _ in self._workers:
                self._queue.put(None)
            for t in self._workers:
                t.join(timeout=30)
        self._workers.clear()
        logger.info("Worker pool shut down")

    @property
    def active_count(self) -> int:
        """Number of tasks currently being executed."""
        with self._lock:
            return self._active_count

    @property
    def queue_size(self) -> int:
        """Number of tasks waiting in the queue."""
        return self._queue.qsize()

    def _worker_loop(self) -> None:
        """Main loop for each worker thread."""
        while self._running:
            try:
                item = self._queue.get(timeout=1.0)
            except Empty:
                continue

            if item is None:
                # Poison pill — shut down
                break

            func, args, kwargs = item
            with self._lock:
                self._active_count += 1
            try:
                func(*args, **kwargs)
            except Exception:
                logger.exception("Unhandled exception in worker task")
            finally:
                with self._lock:
                    self._active_count -= 1
                self._queue.task_done()
