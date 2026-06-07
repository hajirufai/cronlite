"""RESTful HTTP API for CronLite.

Built on stdlib http.server — no Flask, no FastAPI.
Provides endpoints for job management, execution history, health checks,
and cron expression tools.
"""

import json
import logging
import re
import threading
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler

from cronlite.config import Config
from cronlite.cron import CronParser
from cronlite.errors import (
    CronLiteError,
    JobNotFoundError,
    DuplicateJobError,
    ParseError,
)
from cronlite.health import HealthChecker
from cronlite.history import ExecutionHistory
from cronlite.scheduler.engine import SchedulerEngine
from cronlite.store import Store
from cronlite.types import Job, RetryStrategy
from cronlite.utils import generate_job_id

logger = logging.getLogger("cronlite.api")


class APIHandler(BaseHTTPRequestHandler):
    """HTTP request handler for the CronLite API."""

    # These are set by the APIServer before starting
    engine: SchedulerEngine = None  # type: ignore
    store: Store = None  # type: ignore
    parser: CronParser = None  # type: ignore
    history: ExecutionHistory = None  # type: ignore
    health_checker: HealthChecker = None  # type: ignore

    def log_message(self, format, *args):
        logger.debug(format, *args)

    def do_GET(self):
        self._route("GET")

    def do_POST(self):
        self._route("POST")

    def do_PUT(self):
        self._route("PUT")

    def do_DELETE(self):
        self._route("DELETE")

    def _route(self, method: str):
        path = self.path.rstrip("/")
        try:
            # Job routes
            if method == "GET" and path == "/api/v1/jobs":
                return self._list_jobs()
            if method == "POST" and path == "/api/v1/jobs":
                return self._create_job()

            # Job by ID
            m = re.match(r"^/api/v1/jobs/([^/]+)$", path)
            if m:
                job_id = m.group(1)
                if method == "GET":
                    return self._get_job(job_id)
                if method == "PUT":
                    return self._update_job(job_id)
                if method == "DELETE":
                    return self._delete_job(job_id)

            # Job actions
            m = re.match(r"^/api/v1/jobs/([^/]+)/trigger$", path)
            if m and method == "POST":
                return self._trigger_job(m.group(1))

            m = re.match(r"^/api/v1/jobs/([^/]+)/pause$", path)
            if m and method == "POST":
                return self._pause_job(m.group(1))

            m = re.match(r"^/api/v1/jobs/([^/]+)/resume$", path)
            if m and method == "POST":
                return self._resume_job(m.group(1))

            m = re.match(r"^/api/v1/jobs/([^/]+)/history$", path)
            if m and method == "GET":
                return self._job_history(m.group(1))

            # Executions
            if method == "GET" and path == "/api/v1/executions":
                return self._list_executions()

            m = re.match(r"^/api/v1/executions/([^/]+)$", path)
            if m and method == "GET":
                return self._get_execution(m.group(1))

            # Health
            if method == "GET" and path == "/api/v1/health":
                return self._health()
            if method == "GET" and path == "/api/v1/status":
                return self._status()

            # Cron tools
            if method == "POST" and path == "/api/v1/cron/validate":
                return self._validate_cron()
            if method == "POST" and path == "/api/v1/cron/next":
                return self._cron_next()

            self._send_json(404, {"error": "Not found"})

        except JobNotFoundError as e:
            self._send_json(404, {"error": str(e)})
        except DuplicateJobError as e:
            self._send_json(409, {"error": str(e)})
        except ParseError as e:
            self._send_json(400, {"error": str(e)})
        except CronLiteError as e:
            self._send_json(400, {"error": str(e)})
        except Exception as e:
            logger.exception("API error")
            self._send_json(500, {"error": "Internal server error"})

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        body = self.rfile.read(length)
        return json.loads(body.decode("utf-8"))

    def _send_json(self, status: int, data: dict | list) -> None:
        body = json.dumps(data, indent=2, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    # --- Job endpoints ---

    def _list_jobs(self):
        jobs = self.store.list_jobs()
        self._send_json(200, {"jobs": [j.to_dict() for j in jobs]})

    def _create_job(self):
        data = self._read_json()
        if not data.get("name") or not data.get("expression") or not data.get("command"):
            return self._send_json(400, {
                "error": "name, expression, and command are required"
            })

        # Validate expression
        self.parser.parse(data["expression"])

        job = Job(
            id=generate_job_id(data["name"]),
            name=data["name"],
            expression=data["expression"],
            command=data["command"],
            enabled=data.get("enabled", True),
            created_at=datetime.now(),
            max_retries=data.get("max_retries", 0),
            retry_strategy=RetryStrategy(data.get("retry_strategy", "none")),
            retry_base_delay=data.get("retry_base_delay", 10.0),
            retry_max_delay=data.get("retry_max_delay", 300.0),
            timeout_seconds=data.get("timeout_seconds", 300),
            depends_on=data.get("depends_on", []),
            tags=data.get("tags", []),
            metadata=data.get("metadata", {}),
            working_dir=data.get("working_dir"),
        )

        job = self.engine.add_job(job)
        self._send_json(201, {"job": job.to_dict()})

    def _get_job(self, job_id: str):
        job = self.store.get_job(job_id)
        # Include next run times
        expr = self.parser.parse(job.expression)
        next_runs = expr.next_n_runs(datetime.now(), 5)
        data = job.to_dict()
        data["next_runs"] = [r.isoformat() for r in next_runs]
        self._send_json(200, {"job": data})

    def _update_job(self, job_id: str):
        data = self._read_json()
        job = self.store.get_job(job_id)

        if "expression" in data:
            self.parser.parse(data["expression"])
            job.expression = data["expression"]
        if "command" in data:
            job.command = data["command"]
        if "enabled" in data:
            job.enabled = data["enabled"]
        if "max_retries" in data:
            job.max_retries = data["max_retries"]
        if "retry_strategy" in data:
            job.retry_strategy = RetryStrategy(data["retry_strategy"])
        if "timeout_seconds" in data:
            job.timeout_seconds = data["timeout_seconds"]
        if "tags" in data:
            job.tags = data["tags"]

        self.store.update_job(job)
        self._send_json(200, {"job": job.to_dict()})

    def _delete_job(self, job_id: str):
        self.engine.remove_job(job_id)
        self._send_json(200, {"deleted": job_id})

    def _trigger_job(self, job_id: str):
        execution = self.engine.trigger_job(job_id)
        self._send_json(200, {"execution": execution.to_dict()})

    def _pause_job(self, job_id: str):
        self.engine.pause_job(job_id)
        self._send_json(200, {"paused": job_id})

    def _resume_job(self, job_id: str):
        self.engine.resume_job(job_id)
        self._send_json(200, {"resumed": job_id})

    def _job_history(self, job_id: str):
        execs = self.history.get_last_n(job_id, n=50)
        self._send_json(200, {"executions": [e.to_dict() for e in execs]})

    # --- Execution endpoints ---

    def _list_executions(self):
        execs = self.history.get_recent(limit=50)
        self._send_json(200, {"executions": [e.to_dict() for e in execs]})

    def _get_execution(self, exec_id: str):
        execution = self.store.get_execution(exec_id)
        if execution is None:
            return self._send_json(404, {"error": f"Execution '{exec_id}' not found"})
        self._send_json(200, {"execution": execution.to_dict()})

    # --- Health endpoints ---

    def _health(self):
        report = self.health_checker.get_health_report()
        self._send_json(200, report)

    def _status(self):
        stats = self.engine.get_stats()
        self._send_json(200, stats.to_dict())

    # --- Cron tool endpoints ---

    def _validate_cron(self):
        data = self._read_json()
        expression = data.get("expression", "")
        try:
            expr = self.parser.parse(expression)
            self._send_json(200, {
                "valid": True,
                "expression": expression,
                "description": expr.explain(),
            })
        except ParseError as e:
            self._send_json(200, {
                "valid": False,
                "expression": expression,
                "error": str(e),
            })

    def _cron_next(self):
        data = self._read_json()
        expression = data.get("expression", "")
        count = min(data.get("count", 5), 50)

        expr = self.parser.parse(expression)
        runs = expr.next_n_runs(datetime.now(), count)
        self._send_json(200, {
            "expression": expression,
            "description": expr.explain(),
            "next_runs": [r.isoformat() for r in runs],
        })


class APIServer:
    """HTTP API server for CronLite."""

    def __init__(
        self,
        engine: SchedulerEngine,
        store: Store,
        config: Config | None = None,
    ):
        self._engine = engine
        self._store = store
        self._config = config or Config()
        self._server: HTTPServer | None = None
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        """Start the API server in a background thread."""
        # Set shared references on the handler class
        APIHandler.engine = self._engine
        APIHandler.store = self._store
        APIHandler.parser = CronParser()
        APIHandler.history = ExecutionHistory(self._store)
        APIHandler.health_checker = HealthChecker(self._store)

        self._server = HTTPServer(
            (self._config.api_host, self._config.api_port),
            APIHandler,
        )
        self._thread = threading.Thread(
            target=self._server.serve_forever,
            name="cronlite-api",
            daemon=True,
        )
        self._thread.start()
        logger.info(
            "API server started on %s:%d",
            self._config.api_host, self._config.api_port,
        )

    def stop(self) -> None:
        """Stop the API server."""
        if self._server:
            self._server.shutdown()
            logger.info("API server stopped")
