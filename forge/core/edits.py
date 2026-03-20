from __future__ import annotations

from pathlib import Path
from typing import Any


def normalize_operations(
    payload: dict[str, Any],
    *,
    legacy_key: str = "files",
) -> list[dict[str, Any]]:
    operations = payload.get("operations")
    if operations is not None:
        if not isinstance(operations, list):
            raise ValueError("'operations' must be a list.")
        return operations

    normalized: list[dict[str, Any]] = []
    for file_spec in payload.get(legacy_key, []):
        normalized.append(
            {
                "type": "write_file",
                "path": file_spec["path"],
                "content": file_spec["content"],
            }
        )
    return normalized


def validate_relative_path(path: str) -> str:
    candidate = Path(path)
    if candidate.is_absolute():
        raise ValueError(f"Absolute paths are not allowed: {path}")
    if ".." in candidate.parts:
        raise ValueError(f"Path traversal is not allowed: {path}")
    normalized = candidate.as_posix().lstrip("./")
    if not normalized:
        raise ValueError("Operation path cannot be empty.")
    return normalized


def apply_operations(repo_path: str, operations: list[dict[str, Any]]) -> list[str]:
    changed_paths: list[str] = []
    root = Path(repo_path)

    for operation in operations:
        op_type = operation.get("type")
        path = validate_relative_path(operation["path"])
        full_path = root / path

        if op_type == "write_file":
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(operation.get("content", ""), encoding="utf-8")
            changed_paths.append(path)
            continue

        if op_type == "replace_in_file":
            if not full_path.exists():
                raise ValueError(f"Cannot patch missing file: {path}")

            content = full_path.read_text(encoding="utf-8")
            for change in operation.get("changes", []):
                old = change["old"]
                new = change.get("new", "")
                replace_all = bool(change.get("replace_all", False))

                if old not in content:
                    raise ValueError(f"Patch text not found in {path}: {old[:80]}")

                if replace_all:
                    content = content.replace(old, new)
                else:
                    content = content.replace(old, new, 1)

            full_path.write_text(content, encoding="utf-8")
            changed_paths.append(path)
            continue

        if op_type == "delete_file":
            if full_path.exists():
                full_path.unlink()
            changed_paths.append(path)
            continue

        raise ValueError(f"Unsupported operation type: {op_type}")

    return sorted(set(changed_paths))


def materialize_file_specs(repo_path: str, paths: list[str]) -> list[dict[str, str]]:
    root = Path(repo_path)
    files: list[dict[str, str]] = []

    for path in sorted(set(paths)):
        full_path = root / path
        if not full_path.exists() or not full_path.is_file():
            continue
        files.append(
            {
                "path": path,
                "content": full_path.read_text(encoding="utf-8"),
            }
        )

    return files

