"""Directed Acyclic Graph for job dependencies.

Manages dependency relationships between jobs, validates that the graph
has no cycles, and computes which jobs are ready to run.
"""

from collections import deque

from cronlite.errors import CyclicDependencyError, JobNotFoundError


class JobDAG:
    """A directed acyclic graph tracking job dependencies.

    Edges point from dependency → dependent:
        If job B depends on job A, the edge is A → B.
        Internally we store the reverse: _deps[B] = {A} (B depends on A).
    """

    def __init__(self):
        self._deps: dict[str, set[str]] = {}   # job_id → set of dependency IDs
        self._rdeps: dict[str, set[str]] = {}   # job_id → set of dependent IDs

    def add_job(self, job_id: str) -> None:
        """Register a job in the DAG (with no dependencies initially)."""
        self._deps.setdefault(job_id, set())
        self._rdeps.setdefault(job_id, set())

    def remove_job(self, job_id: str) -> None:
        """Remove a job and all its dependency edges."""
        # Remove from deps
        for dep_id in list(self._deps.get(job_id, [])):
            self._rdeps.get(dep_id, set()).discard(job_id)
        self._deps.pop(job_id, None)

        # Remove from rdeps
        for dependent_id in list(self._rdeps.get(job_id, [])):
            self._deps.get(dependent_id, set()).discard(job_id)
        self._rdeps.pop(job_id, None)

    def add_dependency(self, job_id: str, depends_on: str) -> None:
        """Declare that job_id depends on depends_on.

        Raises CyclicDependencyError if adding this edge would create a cycle.
        """
        self._deps.setdefault(job_id, set())
        self._deps.setdefault(depends_on, set())
        self._rdeps.setdefault(job_id, set())
        self._rdeps.setdefault(depends_on, set())

        # Temporarily add and check for cycles
        self._deps[job_id].add(depends_on)
        self._rdeps[depends_on].add(job_id)

        if self._has_cycle():
            # Rollback
            self._deps[job_id].discard(depends_on)
            self._rdeps[depends_on].discard(job_id)
            raise CyclicDependencyError(
                f"Adding dependency {job_id} → {depends_on} would create a cycle"
            )

    def remove_dependency(self, job_id: str, depends_on: str) -> None:
        """Remove a dependency relationship."""
        self._deps.get(job_id, set()).discard(depends_on)
        self._rdeps.get(depends_on, set()).discard(job_id)

    def get_dependencies(self, job_id: str) -> set[str]:
        """Get the set of jobs that job_id depends on."""
        return set(self._deps.get(job_id, set()))

    def get_dependents(self, job_id: str) -> set[str]:
        """Get the set of jobs that depend on job_id."""
        return set(self._rdeps.get(job_id, set()))

    def get_ready_jobs(self, completed: set[str]) -> list[str]:
        """Return job IDs whose dependencies are all in the completed set.

        Only returns jobs that have at least one dependency (standalone jobs
        are not included — they run on their own schedule).
        """
        ready = []
        for job_id, deps in self._deps.items():
            if deps and deps.issubset(completed) and job_id not in completed:
                ready.append(job_id)
        return sorted(ready)

    def topological_sort(self) -> list[str]:
        """Return a topological ordering of all jobs (Kahn's algorithm).

        Raises CyclicDependencyError if the graph has a cycle.
        """
        # Compute in-degrees
        in_degree: dict[str, int] = {jid: 0 for jid in self._deps}
        for jid, deps in self._deps.items():
            for dep in deps:
                in_degree.setdefault(dep, 0)
            # Each dependency adds to the in-degree of jid
            # Wait — in_degree tracks how many deps each node has
            pass

        # Actually, in Kahn's algorithm with our edge direction:
        # in_degree of a node = number of dependencies it has
        in_degree = {}
        for jid in self._deps:
            in_degree[jid] = len(self._deps[jid])

        queue: deque[str] = deque()
        for jid, deg in in_degree.items():
            if deg == 0:
                queue.append(jid)

        result: list[str] = []
        while queue:
            node = queue.popleft()
            result.append(node)
            for dependent in self._rdeps.get(node, set()):
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    queue.append(dependent)

        if len(result) != len(in_degree):
            raise CyclicDependencyError("Job dependency graph contains a cycle")

        return result

    def has_cycle(self) -> bool:
        """Check if the dependency graph has any cycles."""
        return self._has_cycle()

    def _has_cycle(self) -> bool:
        """DFS-based cycle detection with three-color marking."""
        WHITE, GRAY, BLACK = 0, 1, 2
        color: dict[str, int] = {jid: WHITE for jid in self._deps}

        def dfs(node: str) -> bool:
            color[node] = GRAY
            for dep in self._deps.get(node, set()):
                if color.get(dep, WHITE) == GRAY:
                    return True  # Back edge → cycle
                if color.get(dep, WHITE) == WHITE and dfs(dep):
                    return True
            color[node] = BLACK
            return False

        for jid in self._deps:
            if color.get(jid, WHITE) == WHITE:
                if dfs(jid):
                    return True
        return False

    @property
    def job_ids(self) -> set[str]:
        """All job IDs registered in the DAG."""
        return set(self._deps.keys())

    def __len__(self) -> int:
        return len(self._deps)

    def __repr__(self) -> str:
        edges = sum(len(deps) for deps in self._deps.values())
        return f"JobDAG(jobs={len(self._deps)}, edges={edges})"
