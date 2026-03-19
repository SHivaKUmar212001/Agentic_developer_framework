from __future__ import annotations

from typing import Optional

from forge.agents.base import BaseAgent
from forge.core.state import SharedState, Task


class DocWriter(BaseAgent):
    name = "docwriter"

    system_prompt = """You are a technical documentation writer.

OUTPUT FORMAT - respond with ONLY this JSON:
{
  "files": [
    {
      "path": "README.md",
      "content": "full markdown content"
    }
  ]
}"""

    async def run(
        self,
        state: SharedState,
        task: Optional[Task] = None,
        **_: object,
    ) -> dict:
        code_summary = []
        for path, content in sorted(state.written_files.items()):
            preview = content if len(content) < 3000 else content[:3000] + "\n... [truncated]\n"
            code_summary.append(f"### {path}\n```\n{preview}\n```")

        prompt = f"""Prompt: {state.user_prompt}
Architecture: {state.plan.get('architecture', 'Not specified')}

Files:
{chr(10).join(code_summary)}

Generate concise developer documentation."""

        return self.parse_json(await self.call(prompt))


class SecurityAuditor(BaseAgent):
    name = "security_auditor"

    system_prompt = """You are a security auditor.

OUTPUT FORMAT - respond with ONLY this JSON:
{
  "risk_level": "low|medium|high|critical",
  "findings": [
    {
      "severity": "low|medium|high|critical",
      "file": "path/to/file",
      "line": 42,
      "category": "hardcoded_secret|sql_injection|xss|auth",
      "description": "what is wrong",
      "recommendation": "how to fix it"
    }
  ],
  "summary": "one paragraph assessment"
}"""

    async def run(
        self,
        state: SharedState,
        task: Optional[Task] = None,
        **_: object,
    ) -> dict:
        all_code = "\n\n".join(
            f"### {path}\n```\n{content}\n```"
            for path, content in sorted(state.written_files.items())
        )
        return self.parse_json(await self.call(f"Audit this codebase:\n\n{all_code}"))
