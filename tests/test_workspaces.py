from __future__ import annotations

from forge.core.workspaces import collect_workspace_operations, create_task_workspace, remove_workspace


def test_workspace_diff_captures_changes(tmp_path) -> None:
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "app.py").write_text("VALUE = 1\n", encoding="utf-8")

    workspace = create_task_workspace(str(tmp_path), "T1", ".forge_runtime")
    workspace_file = tmp_path / ".forge_runtime" / "workspaces" / "T1" / "pkg" / "app.py"
    workspace_file.write_text("VALUE = 2\n", encoding="utf-8")

    operations, changed_paths = collect_workspace_operations(workspace.base_snapshot, workspace.path)

    assert changed_paths == {"pkg/app.py"}
    assert operations == [
        {"type": "write_file", "path": "pkg/app.py", "content": "VALUE = 2\n"}
    ]

    remove_workspace(workspace.path)
    assert not workspace_file.parent.parent.exists()

