from __future__ import annotations

from forge.core.state import Task


def get_execution_waves(tasks: list[Task]) -> list[list[Task]]:
    """Group tasks into dependency-safe execution waves."""
    task_map = {task.id: task for task in tasks}
    completed: set[str] = set()
    remaining = {task.id for task in tasks}
    waves: list[list[Task]] = []

    while remaining:
        ready: list[Task] = []
        for task_id in sorted(remaining):
            task = task_map[task_id]
            if set(task.dependencies).issubset(completed):
                ready.append(task)

        if not ready:
            ready = [task_map[task_id] for task_id in sorted(remaining)]

        waves.append(ready)
        for task in ready:
            completed.add(task.id)
            remaining.discard(task.id)

    return waves


def describe_execution_plan(waves: list[list[Task]]) -> str:
    lines: list[str] = []
    for index, wave in enumerate(waves, start=1):
        mode = "parallel-ready" if len(wave) > 1 else "sequential"
        task_summary = ", ".join(f"{task.id} - {task.description}" for task in wave)
        lines.append(f"  Wave {index} ({mode}): {task_summary}")
    return "\n".join(lines)

