"""Tests for CLI commands."""

import os
import tempfile
import unittest

from cronlite.cli import main


class TestCLI(unittest.TestCase):

    def setUp(self):
        self._tmpfile = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._tmpfile.close()
        self._db = self._tmpfile.name

    def tearDown(self):
        os.unlink(self._db)

    def _run(self, *args):
        return main(["--db", self._db] + list(args))

    def test_demo(self):
        ret = self._run("demo")
        self.assertEqual(ret, 0)

    def test_explain(self):
        ret = self._run("explain", "*/15 * * * *")
        self.assertEqual(ret, 0)

    def test_next(self):
        ret = self._run("next", "0 * * * *", "--count", "3")
        self.assertEqual(ret, 0)

    def test_add_and_list(self):
        ret = self._run("add", "test-job", "*/5 * * * *", "echo hello")
        self.assertEqual(ret, 0)
        ret = self._run("list")
        self.assertEqual(ret, 0)

    def test_add_and_trigger(self):
        self._run("add", "echo-job", "* * * * *", "echo triggered")
        ret = self._run("trigger", "echo-job")
        self.assertEqual(ret, 0)

    def test_add_disable_enable(self):
        self._run("add", "toggle-job", "* * * * *", "echo toggle")
        ret = self._run("disable", "toggle-job")
        self.assertEqual(ret, 0)
        ret = self._run("enable", "toggle-job")
        self.assertEqual(ret, 0)

    def test_add_and_remove(self):
        self._run("add", "rm-job", "* * * * *", "echo rm")
        ret = self._run("remove", "rm-job")
        self.assertEqual(ret, 0)

    def test_history_empty(self):
        ret = self._run("history")
        self.assertEqual(ret, 0)

    def test_stats_empty(self):
        ret = self._run("stats")
        self.assertEqual(ret, 0)

    def test_status(self):
        ret = self._run("status")
        self.assertEqual(ret, 0)

    def test_list_json(self):
        self._run("add", "json-job", "* * * * *", "echo json")
        ret = self._run("list", "--json")
        self.assertEqual(ret, 0)

    def test_add_with_retries(self):
        ret = self._run(
            "add", "retry-job", "* * * * *", "echo retry",
            "--retries", "3", "--retry-strategy", "exponential",
        )
        self.assertEqual(ret, 0)

    def test_add_with_tags(self):
        ret = self._run(
            "add", "tagged-job", "* * * * *", "echo tags",
            "--tags", "data", "pipeline",
        )
        self.assertEqual(ret, 0)

    def test_trigger_failed_command(self):
        self._run("add", "fail-job", "* * * * *", "exit 1")
        ret = self._run("trigger", "fail-job")
        self.assertEqual(ret, 1)  # Failed command

    def test_no_command_shows_help(self):
        ret = main([])
        self.assertEqual(ret, 0)


if __name__ == "__main__":
    unittest.main()
