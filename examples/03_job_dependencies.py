"""Job dependencies example — DAG-based execution ordering."""

from cronlite.dag import JobDAG


def main():
    print("=== CronLite: Job Dependencies (DAG) ===\n")

    dag = JobDAG()

    # Build a data pipeline DAG:
    #   extract → transform → load → report
    #                                  ↑
    #              validate ────────────┘

    jobs = ["extract", "transform", "load", "validate", "report"]
    for j in jobs:
        dag.add_job(j)

    dag.add_dependency("transform", "extract")
    dag.add_dependency("load", "transform")
    dag.add_dependency("report", "load")
    dag.add_dependency("report", "validate")  # report needs both load AND validate

    print("Pipeline structure:")
    print("  extract → transform → load → report")
    print("                       validate ──↗")
    print()

    # Topological sort
    order = dag.topological_sort()
    print(f"Execution order: {' → '.join(order)}")
    print()

    # Simulate step-by-step execution
    completed = set()
    print("Simulating execution:")
    for step in range(1, 6):
        ready = dag.get_ready_jobs(completed)
        # Also include jobs with no dependencies that haven't run
        standalone = [
            j for j in jobs
            if not dag.get_dependencies(j) and j not in completed
        ]
        runnable = list(set(ready + standalone))

        if not runnable:
            break

        job = runnable[0]
        completed.add(job)
        print(f"  Step {step}: Run '{job}' ✓  (completed: {completed})")

    print()

    # Cycle detection demo
    print("Cycle detection:")
    try:
        dag.add_dependency("extract", "report")
        print("  ✗ Should have raised an error!")
    except Exception as e:
        print(f"  ✓ Correctly detected cycle: {e}")

    print()
    print(f"DAG: {dag}")


if __name__ == "__main__":
    main()
