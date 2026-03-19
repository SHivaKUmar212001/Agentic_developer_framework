from __future__ import annotations

from forge.core.parallel import get_execution_waves
from forge.core.state import Task


def test_groups_tasks_into_dependency_waves() -> None:
    tasks = [
        Task(id="T1", description="setup"),
        Task(id="T2", description="auth", dependencies=["T1"]),
        Task(id="T3", description="db", dependencies=["T1"]),
        Task(id="T4", description="api", dependencies=["T2", "T3"]),
    ]

    waves = get_execution_waves(tasks)

    assert [[task.id for task in wave] for wave in waves] == [
        ["T1"],
        ["T2", "T3"],
        ["T4"],
    ]

