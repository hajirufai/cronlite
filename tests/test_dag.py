"""Tests for the job dependency graph."""

import unittest

from cronlite.dag import JobDAG
from cronlite.errors import CyclicDependencyError


class TestJobDAG(unittest.TestCase):

    def setUp(self):
        self.dag = JobDAG()

    def test_add_job(self):
        self.dag.add_job("a")
        self.assertIn("a", self.dag.job_ids)

    def test_remove_job(self):
        self.dag.add_job("a")
        self.dag.remove_job("a")
        self.assertNotIn("a", self.dag.job_ids)

    def test_add_dependency(self):
        self.dag.add_job("a")
        self.dag.add_job("b")
        self.dag.add_dependency("b", "a")  # b depends on a
        self.assertEqual(self.dag.get_dependencies("b"), {"a"})
        self.assertEqual(self.dag.get_dependents("a"), {"b"})

    def test_remove_dependency(self):
        self.dag.add_job("a")
        self.dag.add_job("b")
        self.dag.add_dependency("b", "a")
        self.dag.remove_dependency("b", "a")
        self.assertEqual(self.dag.get_dependencies("b"), set())

    def test_cycle_detection_direct(self):
        self.dag.add_job("a")
        self.dag.add_job("b")
        self.dag.add_dependency("b", "a")
        with self.assertRaises(CyclicDependencyError):
            self.dag.add_dependency("a", "b")  # would create a→b→a cycle

    def test_cycle_detection_indirect(self):
        self.dag.add_job("a")
        self.dag.add_job("b")
        self.dag.add_job("c")
        self.dag.add_dependency("b", "a")
        self.dag.add_dependency("c", "b")
        with self.assertRaises(CyclicDependencyError):
            self.dag.add_dependency("a", "c")  # a→c→b→a

    def test_self_cycle(self):
        self.dag.add_job("a")
        with self.assertRaises(CyclicDependencyError):
            self.dag.add_dependency("a", "a")

    def test_get_ready_jobs(self):
        self.dag.add_job("a")
        self.dag.add_job("b")
        self.dag.add_job("c")
        self.dag.add_dependency("b", "a")
        self.dag.add_dependency("c", "a")

        # Nothing completed yet
        ready = self.dag.get_ready_jobs(set())
        self.assertEqual(ready, [])

        # a completed
        ready = self.dag.get_ready_jobs({"a"})
        self.assertEqual(set(ready), {"b", "c"})

    def test_get_ready_jobs_chain(self):
        self.dag.add_job("a")
        self.dag.add_job("b")
        self.dag.add_job("c")
        self.dag.add_dependency("b", "a")
        self.dag.add_dependency("c", "b")

        ready = self.dag.get_ready_jobs({"a"})
        self.assertEqual(ready, ["b"])

        ready = self.dag.get_ready_jobs({"a", "b"})
        self.assertEqual(ready, ["c"])

    def test_topological_sort(self):
        self.dag.add_job("a")
        self.dag.add_job("b")
        self.dag.add_job("c")
        self.dag.add_dependency("b", "a")
        self.dag.add_dependency("c", "b")

        order = self.dag.topological_sort()
        self.assertEqual(order.index("a"), 0)
        self.assertLess(order.index("a"), order.index("b"))
        self.assertLess(order.index("b"), order.index("c"))

    def test_topological_sort_diamond(self):
        # a → b, a → c, b → d, c → d
        self.dag.add_job("a")
        self.dag.add_job("b")
        self.dag.add_job("c")
        self.dag.add_job("d")
        self.dag.add_dependency("b", "a")
        self.dag.add_dependency("c", "a")
        self.dag.add_dependency("d", "b")
        self.dag.add_dependency("d", "c")

        order = self.dag.topological_sort()
        self.assertLess(order.index("a"), order.index("b"))
        self.assertLess(order.index("a"), order.index("c"))
        self.assertLess(order.index("b"), order.index("d"))
        self.assertLess(order.index("c"), order.index("d"))

    def test_len(self):
        self.dag.add_job("a")
        self.dag.add_job("b")
        self.assertEqual(len(self.dag), 2)

    def test_repr(self):
        self.dag.add_job("a")
        self.dag.add_job("b")
        self.dag.add_dependency("b", "a")
        r = repr(self.dag)
        self.assertIn("2", r)

    def test_remove_job_cleans_edges(self):
        self.dag.add_job("a")
        self.dag.add_job("b")
        self.dag.add_job("c")
        self.dag.add_dependency("b", "a")
        self.dag.add_dependency("c", "b")
        self.dag.remove_job("b")
        self.assertEqual(self.dag.get_dependents("a"), set())
        self.assertEqual(self.dag.get_dependencies("c"), set())


if __name__ == "__main__":
    unittest.main()
