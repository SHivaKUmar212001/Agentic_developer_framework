from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import shutil

from forge.core.state import SKIP_DIRS, TEXT_SUFFIXES


@dataclass
class TaskWorkspace:
    task_id: str
    path: str
    base_snapshot: dict[str, str]


def _copy_ignore(_: str, names: list[str]) -> set[str]:
    ignored = set(SKIP_DIRS)
    ignored.add(".git")
    return {name for name in names if name in ignored}


def snapshot_text_files(root_path: str, *, max_chars: int = 200_000) -> dict[str, str]:
    root = Path(root_path)
    snapshot: dict[str, str] = {}

    for current_root, dirs, files in os.walk(root):
        dirs[:] = sorted(directory for directory in dirs if directory not in SKIP_DIRS and directory != ".git")
        current = Path(current_root)
        for filename in sorted(files):
            full_path = current / filename
            suffix = full_path.suffix.lower()
            if suffix not in TEXT_SUFFIXES:
                continue

            rel_path = full_path.relative_to(root).as_posix()
            try:
                content = full_path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue

            if len(content) > max_chars:
                continue
            snapshot[rel_path] = content

    return snapshot


def create_task_workspace(repo_path: str, task_id: str, runtime_dir: str) -> TaskWorkspace:
    source = Path(repo_path)
    runtime_root = source / runtime_dir / "workspaces"
    workspace_path = runtime_root / task_id

    if workspace_path.exists():
        shutil.rmtree(workspace_path)

    runtime_root.mkdir(parents=True, exist_ok=True)
    base_snapshot = snapshot_text_files(repo_path)
    shutil.copytree(source, workspace_path, ignore=_copy_ignore)

    return TaskWorkspace(
        task_id=task_id,
        path=str(workspace_path),
        base_snapshot=base_snapshot,
    )


def collect_workspace_operations(base_snapshot: dict[str, str], workspace_path: str) -> tuple[list[dict], set[str]]:
    current_snapshot = snapshot_text_files(workspace_path)
    changed_paths: set[str] = set()
    operations: list[dict] = []

    for path in sorted(set(base_snapshot) | set(current_snapshot)):
        before = base_snapshot.get(path)
        after = current_snapshot.get(path)
        if before == after:
            continue

        changed_paths.add(path)
        if after is None:
            operations.append({"type": "delete_file", "path": path})
        else:
            operations.append({"type": "write_file", "path": path, "content": after})

    return operations, changed_paths


def remove_workspace(workspace_path: str) -> None:
    path = Path(workspace_path)
    if path.exists():
        shutil.rmtree(path)
