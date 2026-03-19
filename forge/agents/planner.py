from __future__ import annotations

import os
import subprocess
from typing import Optional

from forge.agents.base import BaseAgent
from forge.core.state import SharedState, Task


class Planner(BaseAgent):
    name = "planner"

    system_prompt = """You are a senior software architect acting as a planning agent.

YOUR JOB: Given a project goal (build mode) or a repo with issues (fix mode),
produce a structured task graph. You never write code.

RULES:
- Each task must have: id, description, dependencies, and acceptance_criteria.
- Keep tasks small and dependency aware.
- In fix mode, create targeted repair tasks instead of a full rebuild plan.
- Include setup work when it is actually required.

OUTPUT FORMAT - respond with ONLY this JSON:
{
  "architecture": "brief stack summary",
  "tasks": [
    {
      "id": "T1",
      "description": "what to build or fix",
      "dependencies": [],
      "acceptance_criteria": "how to verify it"
    }
  ]
}"""

    async def run(
        self,
        state: SharedState,
        task: Optional[Task] = None,
        **_: object,
    ) -> dict[str, object]:
        if state.mode == "fix":
            repo_structure = self._analyze_repo(state.repo_path)
            relevant_files = state.get_relevant_repo_files(
                f"{state.user_prompt} {state.focus}",
                max_files=4,
            )
            relevant_text = "\n\n".join(
                f"### {path}\n```\n{content}\n```"
                for path, content in relevant_files
            ) or "No representative files were captured."

            prompt = f"""FIX MODE

Repo structure:
{repo_structure}

Relevant files:
{relevant_text}

Problem statement:
{state.user_prompt}
{f"Focus: {state.focus}" if state.focus else ""}

Create a targeted fix plan."""
        else:
            prompt = f"""BUILD MODE

User request:
{state.user_prompt}

Create a complete implementation plan from setup through integration."""

        response = await self.call(prompt)
        plan = self.parse_json(response)

        state.plan = plan
        state.tasks = [
            Task(
                id=item["id"],
                description=item["description"],
                dependencies=item.get("dependencies", []),
                acceptance_criteria=item.get("acceptance_criteria", ""),
            )
            for item in plan.get("tasks", [])
        ]
        state.add_log(self.name, f"Created {len(state.tasks)} task(s)")
        return plan

    def _analyze_repo(self, repo_path: str) -> str:
        lines: list[str] = []
        for root, dirs, files in os.walk(repo_path):
            dirs[:] = sorted(
                directory
                for directory in dirs
                if directory
                not in {
                    ".git",
                    ".venv",
                    "venv",
                    "__pycache__",
                    ".pytest_cache",
                    "node_modules",
                    "dist",
                    "build",
                    ".next",
                }
            )
            level = root.replace(repo_path, "").count(os.sep)
            if level > 3:
                continue
            indent = "  " * level
            lines.append(f"{indent}{os.path.basename(root) or root}/")
            for filename in sorted(files)[:15]:
                lines.append(f"{indent}  {filename}")

        try:
            result = subprocess.run(
                ["git", "log", "--oneline", "-10"],
                cwd=repo_path,
                capture_output=True,
                text=True,
            )
            if result.returncode == 0 and result.stdout.strip():
                lines.append("\nRecent commits:")
                lines.append(result.stdout.strip())
        except Exception:
            pass

        return "\n".join(lines[:120])
