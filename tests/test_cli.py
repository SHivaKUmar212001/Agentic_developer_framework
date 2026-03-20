from __future__ import annotations

from click.testing import CliRunner

from forge.cli import cli


def test_help_lists_build_and_fix_commands() -> None:
    result = CliRunner().invoke(cli, ["--help"])

    assert result.exit_code == 0
    assert "build" in result.output
    assert "fix" in result.output


def test_build_command_labels_output_path(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    result = CliRunner().invoke(
        cli,
        ["build", "create a dashboard", "-o", str(tmp_path / "out")],
        env={"FORGE_PROVIDER": "anthropic"},
    )

    assert result.exit_code != 0
    assert "Output:" in result.output
