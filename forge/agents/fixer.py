from __future__ import annotations

from typing import Optional

from forge.agents.base import BaseAgent
from forge.core.state import SharedState, Task


class Fixer(BaseAgent):
    name = "fixer"

    system_prompt = """You are a debugging specialist.

YOUR JOB: Given failing tests and source code, make minimal fixes.

RULES:
- Change as little as possible.
- Fix the failures directly instead of refactoring unrelated code.
- Output complete file contents for any file you change.

OUTPUT FORMAT - respond with ONLY this JSON:
{
  "diagnosis": "brief root cause summary",
  "files": [
    {
      "path": "relative/path.ext",
      "content": "full file content"
    }
  ],
  "changes_made": ["short bullet"]
}"""

    async def run(
        self,
        state: SharedState,
        task: Optional[Task] = None,
        *,
        code_output: Optional[dict] = None,
        test_result: Optional[dict] = None,
    ) -> dict:
        if task is None:
            raise ValueError("Fixer requires a task.")
        if code_output is None or test_result is None:
            raise ValueError("Fixer requires code output and test results.")

        source_text = "\n\n".join(
            f"### {file_spec['path']}\n```\n{file_spec['content']}\n```"
            for file_spec in code_output.get("files", [])
        )
        test_text = "\n\n".join(
            f"### {file_spec['path']}\n```\n{file_spec['content']}\n```"
            for file_spec in test_result.get("test_files", [])
        )

        prompt = f"""## Task
{task.id}: {task.description}

## Source code
{source_text}

## Tests
{test_text}

## Failing output
```
{test_result.get('output', 'No output captured')}
```

{test_result.get('passed', 0)} tests passed and {test_result.get('failed', 0)} failed.

Apply the smallest possible fix."""

        response = await self.call(prompt)
        result = self.parse_json(response)
        state.add_log(self.name, f"{task.id}: {len(result.get('files', []))} file(s) patched")
        return result
