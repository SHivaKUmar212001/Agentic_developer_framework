from __future__ import annotations

from forge.core.config import ShellConfig
from forge.core.shell import ShellExecutor


def test_shell_executor_blocks_dangerous_commands() -> None:
    executor = ShellExecutor(ShellConfig())

    result = executor.run_command("rm -rf .", ".")

    assert result["allowed"] is False
    assert "Blocked binary" in result["output"]


def test_shell_executor_allows_safe_pytest_command(tmp_path) -> None:
    executor = ShellExecutor(ShellConfig())
    test_file = tmp_path / "test_sample.py"
    test_file.write_text("def test_ok():\n    assert True\n", encoding="utf-8")

    result = executor.run_command("python -m pytest test_sample.py -q", str(tmp_path))

    assert result["allowed"] is True
    assert result["return_code"] == 0
    assert "1 passed" in result["output"]

