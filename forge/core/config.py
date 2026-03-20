from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import os

try:
    import yaml

    HAS_YAML = True
except ImportError:
    HAS_YAML = False


@dataclass
class AgentConfig:
    provider: str = ""
    model: str = ""
    temperature: float = 0.3
    max_tokens: int = 8192


@dataclass
class ShellConfig:
    allowed_commands: list[str] = field(
        default_factory=lambda: [
            "node",
            "npm",
            "npx",
            "pip",
            "pip3",
            "pnpm",
            "pytest",
            "python",
            "python3",
            "ruff",
            "uv",
            "yarn",
        ]
    )
    timeout_seconds: int = 180


@dataclass
class ForgeConfig:
    provider: str = field(default_factory=lambda: os.getenv("FORGE_PROVIDER", "anthropic"))
    model: str = field(default_factory=lambda: os.getenv("FORGE_MODEL", "claude-sonnet-4-20250514"))
    max_review_retries: int = 3
    max_fix_retries: int = 3
    skip_tests: bool = False
    skip_review: bool = False
    parallel: bool = True
    runtime_dir: str = field(default_factory=lambda: os.getenv("FORGE_RUNTIME_DIR", ".forge_runtime"))
    keep_workspaces: bool = False
    shell: ShellConfig = field(default_factory=ShellConfig)
    agents: dict[str, AgentConfig] = field(default_factory=dict)

    @classmethod
    def load(cls, repo_path: str) -> "ForgeConfig":
        config = cls()
        config_path = Path(repo_path) / "forge.yaml"

        if config_path.exists() and HAS_YAML:
            with config_path.open(encoding="utf-8") as handle:
                raw = yaml.safe_load(handle) or {}

            config.provider = raw.get("provider", config.provider)
            config.model = raw.get("model", config.model)
            config.max_review_retries = raw.get(
                "max_retries",
                config.max_review_retries,
            )
            config.max_fix_retries = raw.get(
                "max_fix_retries",
                config.max_fix_retries,
            )
            config.skip_tests = raw.get("skip_tests", config.skip_tests)
            config.skip_review = raw.get("skip_review", config.skip_review)
            config.parallel = raw.get("parallel", config.parallel)
            config.runtime_dir = raw.get("runtime_dir", config.runtime_dir)
            config.keep_workspaces = raw.get("keep_workspaces", config.keep_workspaces)

            shell_raw = raw.get("shell", {}) or {}
            config.shell = ShellConfig(
                allowed_commands=shell_raw.get(
                    "allowed_commands",
                    config.shell.allowed_commands,
                ),
                timeout_seconds=shell_raw.get(
                    "timeout_seconds",
                    config.shell.timeout_seconds,
                ),
            )

            for agent_name, agent_raw in raw.get("agents", {}).items():
                config.agents[agent_name] = AgentConfig(
                    provider=agent_raw.get("provider", config.provider),
                    model=agent_raw.get("model", config.model),
                    temperature=agent_raw.get("temperature", 0.3),
                    max_tokens=agent_raw.get("max_tokens", 8192),
                )

        return config

    def get_agent_config(self, agent_name: str) -> AgentConfig:
        if agent_name in self.agents:
            agent_config = self.agents[agent_name]
            if not agent_config.provider:
                agent_config.provider = self.provider
            if not agent_config.model:
                agent_config.model = self.model
            return agent_config
        return AgentConfig(provider=self.provider, model=self.model)
