from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
import os
import re
import subprocess

SKIP_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    "node_modules",
    "dist",
    "build",
    ".next",
}

TEXT_SUFFIXES = {
    "",
    ".c",
    ".cc",
    ".cfg",
    ".css",
    ".go",
    ".html",
    ".ini",
    ".java",
    ".js",
    ".json",
    ".jsx",
    ".md",
    ".mjs",
    ".py",
    ".rb",
    ".rs",
    ".sh",
    ".sql",
    ".toml",
    ".ts",
    ".tsx",
    ".txt",
    ".yaml",
    ".yml",
}


@dataclass
class Task:
    id: str
    description: str
    dependencies: list[str] = field(default_factory=list)
    acceptance_criteria: str = ""
    status: str = "pending"


@dataclass
class SharedState:
    mode: str = "build"
    user_prompt: str = ""
    repo_path: str = "."
    focus: str = ""

    plan: dict[str, Any] = field(default_factory=dict)
    tasks: list[Task] = field(default_factory=list)
    written_files: dict[str, str] = field(default_factory=dict)
    current_review: dict[str, Any] = field(default_factory=dict)
    review_history: list[dict[str, Any]] = field(default_factory=list)
    test_results: dict[str, Any] = field(default_factory=dict)
    retry_count: int = 0
    max_retries: int = 3
    log: list[str] = field(default_factory=list)
    last_report: dict[str, Any] = field(default_factory=dict)

    def add_log(self, agent: str, message: str) -> None:
        entry = f"[{datetime.now():%H:%M:%S}] [{agent}] {message}"
        self.log.append(entry)

    def get_existing_code_summary(self) -> str:
        if not self.written_files:
            return "No generated files yet."

        lines = []
        for path in sorted(self.written_files):
            line_count = self.written_files[path].count("\n") + 1
            lines.append(f"  {path} ({line_count} lines)")
        return "Generated files so far:\n" + "\n".join(lines)

    def list_repo_files(self, *, max_files: int = 200) -> list[str]:
        repo_root = Path(self.repo_path)
        if not repo_root.exists():
            return []

        results: list[str] = []
        for root, dirs, files in os.walk(repo_root):
            dirs[:] = sorted(directory for directory in dirs if directory not in SKIP_DIRS)
            root_path = Path(root)

            for filename in sorted(files):
                full_path = root_path / filename
                rel_path = full_path.relative_to(repo_root)
                suffix = full_path.suffix.lower()
                if suffix not in TEXT_SUFFIXES:
                    continue
                results.append(str(rel_path))
                if len(results) >= max_files:
                    return results

        return results

    def get_relevant_repo_files(
        self,
        query: str,
        *,
        max_files: int = 5,
        max_chars: int = 4000,
    ) -> list[tuple[str, str]]:
        keywords = {
            token.lower()
            for token in re.findall(r"[A-Za-z_][A-Za-z0-9_]+", query)
            if len(token) > 2
        }

        scored_paths: list[tuple[int, str]] = []
        for rel_path in self.list_repo_files():
            path_lower = rel_path.lower()
            name_lower = Path(rel_path).name.lower()
            score = 0
            for keyword in keywords:
                if keyword in name_lower:
                    score += 3
                elif keyword in path_lower:
                    score += 1
            scored_paths.append((score, rel_path))

        scored_paths.sort(key=lambda item: (-item[0], item[1]))
        selected = [path for score, path in scored_paths if score > 0][:max_files]
        if not selected:
            selected = [path for _, path in scored_paths[:max_files]]

        results: list[tuple[str, str]] = []
        for rel_path in selected:
            try:
                content = (Path(self.repo_path) / rel_path).read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue

            if len(content) > max_chars:
                content = content[:max_chars] + "\n... [truncated]\n"
            results.append((rel_path, content))

        return results

    def commit(self, task: Task, repo_path: str) -> bool:
        try:
            add_result = subprocess.run(
                ["git", "add", "."],
                cwd=repo_path,
                capture_output=True,
                text=True,
            )
            if add_result.returncode != 0:
                self.add_log("git", f"git add failed for {task.id}: {add_result.stderr.strip()}")
                return False

            diff_result = subprocess.run(
                ["git", "diff", "--cached", "--quiet"],
                cwd=repo_path,
                capture_output=True,
                text=True,
            )
            if diff_result.returncode == 0:
                self.add_log("git", f"No changes to commit for {task.id}")
                return False

            commit_result = subprocess.run(
                ["git", "commit", "-m", f"forge: {task.id} - {task.description}"],
                cwd=repo_path,
                capture_output=True,
                text=True,
            )
            if commit_result.returncode != 0:
                error = commit_result.stderr.strip() or commit_result.stdout.strip()
                self.add_log("git", f"Commit failed for {task.id}: {error}")
                return False

            self.add_log("git", f"Committed task {task.id}")
            return True
        except Exception as exc:
            self.add_log("git", f"Commit failed for {task.id}: {exc}")
            return False

