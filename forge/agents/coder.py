from __future__ import annotations

from typing import Any, Optional

from forge.agents.base import BaseAgent
from forge.core.state import SharedState, Task


class Coder(BaseAgent):
    name = "coder"

    system_prompt = """You are an expert software engineer acting as a coding agent.

YOUR JOB: Implement exactly one task from the plan.

RULES:
- Write complete, working code. Do not leave TODOs or pass statements.
- Only touch files required for the current task.
- Respect the existing architecture and conventions.
- If review feedback is provided, address every issue directly.

OUTPUT FORMAT - respond with ONLY this JSON:
{
  "operations": [
    {
      "type": "write_file|replace_in_file|delete_file",
      "path": "relative/path.ext",
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
  "commands": ["optional shell command"],
  "notes": "brief summary"
}"""

    async def run(
        self,
        state: SharedState,
        task: Optional[Task] = None,
        *,
        feedback: Optional[list[dict[str, Any]]] = None,
    ) -> dict[str, Any]:
        if task is None:
            raise ValueError("Coder requires a task.")

        prompt_parts = [
            f"## Current task\n{task.id}: {task.description}",
            f"Acceptance criteria: {task.acceptance_criteria}",
            f"\n## Architecture\n{state.plan.get('architecture', 'Not specified')}",
            f"\n## Existing generated code\n{state.get_existing_code_summary()}",
        ]

        if state.mode == "fix":
            relevant_files = state.get_relevant_repo_files(
                f"{task.description} {state.focus}",
                max_files=5,
            )
            if relevant_files:
                prompt_parts.append("\n## Relevant repository files")
                for path, content in relevant_files:
                    prompt_parts.append(f"\n### {path}\n```\n{content}\n```")

        if feedback:
            prompt_parts.append("\n## Review feedback to fix")
            prompt_parts.extend(
                f"- [{issue['severity']}] {issue['file']}:{issue.get('line', '?')} - {issue['description']}"
                for issue in feedback
            )

        prompt_parts.append(
            "\n## Editing rules\n"
            "- Prefer replace_in_file for existing files.\n"
            "- Use write_file only for brand new files or complete rewrites that are truly necessary.\n"
            "- Never touch files outside the current task."
        )

        response = await self.call("\n".join(prompt_parts))
        result = self.parse_json(response)
        operation_count = len(result.get("operations", [])) or len(result.get("files", []))
        state.add_log(self.name, f"{task.id}: proposed {operation_count} edit operation(s)")
        return result
