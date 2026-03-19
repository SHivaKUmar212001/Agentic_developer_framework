from __future__ import annotations

from pathlib import Path
import re
import subprocess
from typing import Optional

from forge.agents.base import BaseAgent
from forge.core.state import SharedState, Task


class Tester(BaseAgent):
    name = "tester"

    system_prompt = """You are a test engineer.

YOUR JOB: Write runnable tests for the supplied code and acceptance criteria.

RULES:
- Use the project's native test framework.
- Cover happy paths and edge cases.
- Output complete test files.

OUTPUT FORMAT - respond with ONLY this JSON:
{
  "test_files": [
    {
      "path": "tests/test_something.py",
      "content": "full test file content"
    }
  ],
  "run_command": "pytest tests -q",
  "framework": "pytest"
}"""

    async def run(
        self,
        state: SharedState,
        task: Optional[Task] = None,
        *,
        code_output: Optional[dict] = None,
    ) -> dict:
        if task is None:
            raise ValueError("Tester requires a task.")
        if code_output is None:
            raise ValueError("Tester requires code output.")

        files_text = "\n\n".join(
            f"### {file_spec['path']}\n```\n{file_spec['content']}\n```"
            for file_spec in code_output.get("files", [])
        )

        prompt = f"""## Task
{task.id}: {task.description}
Acceptance criteria: {task.acceptance_criteria}

## Code to test
{files_text}

Write comprehensive tests for this task."""

        response = await self.call(prompt)
        test_spec = self.parse_json(response)

        for test_file in test_spec.get("test_files", []):
            full_path = Path(state.repo_path) / test_file["path"]
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(test_file["content"], encoding="utf-8")
            state.written_files[test_file["path"]] = test_file["content"]

        run_command = test_spec.get("run_command", "pytest tests -q")
        result = {
            "test_files": test_spec.get("test_files", []),
            "run_command": run_command,
            **self._run_tests(run_command, state.repo_path),
        }
        state.test_results = result
        state.add_log(
            self.name,
            f"{task.id}: {result.get('passed', 0)} passed, {result.get('failed', 0)} failed",
        )
        return result

    def _run_tests(self, command: str, cwd: str) -> dict:
        try:
            result = subprocess.run(
                command,
                cwd=cwd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=180,
            )
            output = (result.stdout or "") + "\n" + (result.stderr or "")

            passed = sum(int(match.group(1)) for match in re.finditer(r"(\d+)\s+passed", output))
            failed = sum(
                int(match.group(1))
                for match in re.finditer(r"(\d+)\s+(?:failed|error|errors)", output)
            )
            if result.returncode != 0 and failed == 0:
                failed = 1

            return {
                "all_passed": result.returncode == 0,
                "passed": passed,
                "failed": failed,
                "output": output[-4000:],
                "return_code": result.returncode,
            }
        except subprocess.TimeoutExpired:
            return {
                "all_passed": False,
                "passed": 0,
                "failed": 1,
                "output": "TIMEOUT: tests took longer than 180 seconds",
                "return_code": -1,
            }
        except Exception as exc:
            return {
                "all_passed": False,
                "passed": 0,
                "failed": 1,
                "output": f"Failed to run tests: {exc}",
                "return_code": -1,
            }
