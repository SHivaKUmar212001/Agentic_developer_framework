from __future__ import annotations

from typing import Optional

from forge.agents.base import BaseAgent
from forge.core.state import SharedState, Task


class Reviewer(BaseAgent):
    name = "reviewer"

    system_prompt = """You are a senior code reviewer. Be skeptical and precise.

YOUR JOB: Review the proposed code against the task requirements and find real
bugs, security issues, or missing edge cases.

RULES:
- Reject code when you find a high-risk correctness or security problem.
- Include file paths, line numbers when possible, and a clear explanation.
- Focus on correctness, robustness, and safety, not style nitpicks.

OUTPUT FORMAT - respond with ONLY this JSON:
{
  "approved": true,
  "summary": "one-line verdict",
  "issues": [
    {
      "file": "path/to/file",
      "line": 42,
      "severity": "low|medium|high|critical",
      "description": "what is wrong"
    }
  ]
}"""

    async def run(
        self,
        state: SharedState,
        task: Optional[Task] = None,
        *,
        code_output: Optional[dict] = None,
    ) -> dict:
        if task is None:
            raise ValueError("Reviewer requires a task.")
        if code_output is None:
            raise ValueError("Reviewer requires code output.")

        files_text = "\n\n".join(
            f"### {file_spec['path']}\n```\n{file_spec['content']}\n```"
            for file_spec in code_output.get("files", [])
        )

        prompt = f"""## Task
{task.id}: {task.description}
Acceptance criteria: {task.acceptance_criteria}

## Architecture
{state.plan.get('architecture', 'Not specified')}

## Code to review
{files_text}

Review this code thoroughly."""

        response = await self.call(prompt)
        result = self.parse_json(response)
        state.current_review = result
        state.review_history.append(result)
        verdict = "approved" if result.get("approved") else "rejected"
        state.add_log(self.name, f"{task.id}: {verdict}")
        return result
