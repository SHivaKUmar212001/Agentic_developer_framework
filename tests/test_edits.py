from __future__ import annotations

from forge.core.edits import apply_operations, materialize_file_specs, normalize_operations


def test_apply_operations_supports_write_replace_and_delete(tmp_path) -> None:
    target = tmp_path / "module.py"
    target.write_text("VALUE = 1\n", encoding="utf-8")

    operations = [
        {
            "type": "replace_in_file",
            "path": "module.py",
            "changes": [{"old": "VALUE = 1", "new": "VALUE = 2"}],
        },
        {
            "type": "write_file",
            "path": "tests/test_module.py",
            "content": "from module import VALUE\n",
        },
        {
            "type": "delete_file",
            "path": "obsolete.py",
        },
    ]

    changed_paths = apply_operations(str(tmp_path), operations)
    materialized = materialize_file_specs(str(tmp_path), changed_paths)

    assert target.read_text(encoding="utf-8") == "VALUE = 2\n"
    assert (tmp_path / "tests" / "test_module.py").exists()
    assert {item["path"] for item in materialized} == {"module.py", "tests/test_module.py"}


def test_normalize_operations_supports_legacy_files_payload() -> None:
    payload = {
        "files": [
            {"path": "app.py", "content": "print('hi')\n"},
        ]
    }

    normalized = normalize_operations(payload)

    assert normalized == [
        {
            "type": "write_file",
            "path": "app.py",
            "content": "print('hi')\n",
        }
    ]

