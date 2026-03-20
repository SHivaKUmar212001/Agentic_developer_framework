from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from forge.core.config import ShellConfig

BLOCKED_SUBSTRINGS = ["&&", "||", ";", "|", ">", "<", "`", "$("]
BLOCKED_BINARIES = {"bash", "curl", "git", "rm", "sh", "sudo", "wget"}
ALLOWED_PYTHON_MODULES = {"pip", "pytest", "unittest", "compileall", "venv"}


def build_command_env() -> dict[str, str]:
    env = {}
    for key, value in os.environ.items():
        if key in {"HOME", "PATH", "PYTHONPATH", "TMPDIR", "TMP", "TEMP", "USER", "VIRTUAL_ENV"}:
            env[key] = value
        elif key.startswith("FORGE_"):
            env[key] = value
        elif key.endswith("_API_KEY"):
            env[key] = value
        elif key in {"ANTHROPIC_API_KEY", "OPENAI_API_KEY", "OPENAI_BASE_URL", "OLLAMA_HOST"}:
            env[key] = value
    return env


class ShellExecutor:
    def __init__(self, config: ShellConfig) -> None:
        self.config = config

    def validate_command(self, command: str) -> list[str]:
        issues: list[str] = []
        stripped = command.strip()
        if not stripped:
            return ["Command is empty."]

        for token in BLOCKED_SUBSTRINGS:
            if token in stripped:
                issues.append(f"Blocked shell metacharacter sequence: {token}")

        try:
            argv = shlex.split(stripped)
        except ValueError as exc:
            return [f"Command could not be parsed: {exc}"]

        if not argv:
            return ["Command is empty after parsing."]

        binary = Path(argv[0]).name
        if binary in BLOCKED_BINARIES:
            issues.append(f"Blocked binary: {binary}")
        if binary not in self.config.allowed_commands:
            issues.append(f"Binary '{binary}' is not in the allowlist.")

        if binary in {"python", "python3"}:
            if "-c" in argv:
                issues.append("Inline Python execution via -c is blocked.")
            if "-m" in argv:
                module_index = argv.index("-m") + 1
                if module_index >= len(argv):
                    issues.append("Missing module name after -m.")
                else:
                    module_name = argv[module_index]
                    if module_name not in ALLOWED_PYTHON_MODULES:
                        issues.append(f"Python module '{module_name}' is not allowed.")

        return issues

    def run_command(self, command: str, cwd: str) -> dict[str, Any]:
        issues = self.validate_command(command)
        if issues:
            return {
                "allowed": False,
                "command": command,
                "return_code": -1,
                "stdout": "",
                "stderr": "\n".join(issues),
                "output": "\n".join(issues),
            }

        argv = shlex.split(command)
        binary = Path(argv[0]).name
        if binary in {"python", "python3"}:
            argv[0] = sys.executable
        elif shutil.which(argv[0]) is None:
            return {
                "allowed": False,
                "command": command,
                "return_code": -1,
                "stdout": "",
                "stderr": f"Executable not found: {argv[0]}",
                "output": f"Executable not found: {argv[0]}",
            }
        try:
            result = subprocess.run(
                argv,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=self.config.timeout_seconds,
                env=build_command_env(),
            )
            output = (result.stdout or "") + ("\n" if result.stdout or result.stderr else "") + (result.stderr or "")
            return {
                "allowed": True,
                "command": command,
                "return_code": result.returncode,
                "stdout": result.stdout or "",
                "stderr": result.stderr or "",
                "output": output,
            }
        except subprocess.TimeoutExpired:
            return {
                "allowed": True,
                "command": command,
                "return_code": -1,
                "stdout": "",
                "stderr": f"Command timed out after {self.config.timeout_seconds} seconds.",
                "output": f"Command timed out after {self.config.timeout_seconds} seconds.",
            }
