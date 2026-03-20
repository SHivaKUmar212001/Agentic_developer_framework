from __future__ import annotations

from click.testing import CliRunner

from forge.cli import cli


def test_help_lists_build_and_fix_commands() -> None:
    result = CliRunner().invoke(cli, ["--help"])

    assert result.exit_code == 0
    assert "build" in result.output
    assert "fix" in result.output
