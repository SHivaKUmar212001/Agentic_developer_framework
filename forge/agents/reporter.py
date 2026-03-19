from __future__ import annotations

from typing import Optional

from forge.agents.base import BaseAgent
from forge.core.state import SharedState, Task


class Reporter(BaseAgent):
    name = "reporter"

    system_prompt = """You are a technical writer summarizing a pipeline run.

YOUR JOB: Produce a concise developer-facing summary.

INCLUDE:
- What was built or fixed
- Architecture summary
- Files grouped by purpose
- Known limitations
- Next steps

OUTPUT FORMAT - respond with ONLY this JSON:
{
  "title": "one-line summary",
  "overview": "2-3 sentence summary",
  "architecture": "stack and key patterns",
  "files": {
    "source": ["src/app.py"]
  },
  "limitations": ["known limitation"],
  "next_steps": ["next improvement"],
  "health": "green|yellow|red"
}"""

    async def run(
        self,
        state: SharedState,
        task: Optional[Task] = None,
        **_: object,
    ) -> dict:
        task_summary = "\n".join(
            f"- {task_item.id}: {task_item.description} [{task_item.status}]"
            for task_item in state.tasks
        )
        review_summary = []
        for review in state.review_history:
            if not review.get("approved"):
                for issue in review.get("issues", []):
                    review_summary.append(
                        f"- [{issue['severity']}] {issue['file']}: {issue['description']}"
                    )

        test_results = (
            f"{state.test_results.get('passed', 0)} passed, "
            f"{state.test_results.get('failed', 0)} failed"
            if state.test_results
            else "No tests recorded."
        )

        prompt = f"""## Run summary
Mode: {state.mode}
User prompt: {state.user_prompt}

## Tasks
{task_summary}

## Files written
{chr(10).join(f"- {path}" for path in sorted(state.written_files))}

## Review issues
{chr(10).join(review_summary) if review_summary else "All review rounds approved or no blocking issues remained."}

## Test results
{test_results}

## Activity log
{chr(10).join(state.log[-20:])}

Generate the final project summary."""

        return self.parse_json(await self.call(prompt, temperature=0.2))
