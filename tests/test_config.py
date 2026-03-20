from __future__ import annotations

from forge.core.config import ForgeConfig


def test_loads_project_config(tmp_path) -> None:
    config_file = tmp_path / "forge.yaml"
    config_file.write_text(
        "\n".join(
            [
                "provider: openai",
                "model: test-model",
                "max_retries: 4",
                "max_fix_retries: 2",
                "parallel: false",
                "runtime_dir: .forge-runtime",
                "shell:",
                "  timeout_seconds: 90",
                "  allowed_commands:",
                "    - python",
                "    - pytest",
                "agents:",
                "  reviewer:",
                "    provider: ollama",
                "    temperature: 0.1",
            ]
        ),
        encoding="utf-8",
    )

    config = ForgeConfig.load(str(tmp_path))

    assert config.provider == "openai"
    assert config.model == "test-model"
    assert config.max_review_retries == 4
    assert config.max_fix_retries == 2
    assert config.parallel is False
    assert config.runtime_dir == ".forge-runtime"
    assert config.shell.timeout_seconds == 90
    assert config.shell.allowed_commands == ["python", "pytest"]
    assert config.get_agent_config("reviewer").provider == "ollama"
    assert config.get_agent_config("reviewer").temperature == 0.1
