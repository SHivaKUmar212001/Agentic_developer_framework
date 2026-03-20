from __future__ import annotations

import re
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
  "operations": [
    {
      "type": "write_file|replace_in_file|delete_file",
      "path": "tests/test_something.py",
      "content": "required for write_file",
      "changes": [
        {
          "old": "required for replace_in_file",
          "new": "replacement text",
          "replace_all": false
        }
      ]
    }
  ],
  "run_command": "python -m pytest tests -q",
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
        state.add_log(self.name, f"{task.id}: generated test plan")
        return test_spec

    @staticmethod
    def summarize_test_command(command_result: dict) -> dict:
        output = command_result.get("output", "")
        return_code = command_result.get("return_code", -1)

        passed = sum(int(match.group(1)) for match in re.finditer(r"(\d+)\s+passed", output))
        failed = sum(
            int(match.group(1))
            for match in re.finditer(r"(\d+)\s+(?:failed|error|errors)", output)
        )
        if return_code != 0 and failed == 0:
            failed = 1

        return {
            "all_passed": return_code == 0,
            "passed": passed,
            "failed": failed,
            "output": output[-4000:],
            "return_code": return_code,
        }
