from __future__ import annotations

from forge.core.config import ForgeConfig


def test_loads_project_config(tmp_path) -> None:
    config_file = tmp_path / "forge.yaml"
    config_file.write_text(
        "\n".join(
            [
                "model: test-model",
                "max_retries: 4",
                "max_fix_retries: 2",
                "parallel: false",
                "agents:",
                "  reviewer:",
                "    temperature: 0.1",
            ]
        ),
        encoding="utf-8",
    )

    config = ForgeConfig.load(str(tmp_path))

    assert config.model == "test-model"
    assert config.max_review_retries == 4
    assert config.max_fix_retries == 2
    assert config.parallel is False
    assert config.get_agent_config("reviewer").temperature == 0.1

