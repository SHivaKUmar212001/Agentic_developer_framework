from __future__ import annotations

import asyncio
import shutil
import subprocess
from pathlib import Path

from forge.core.llm import clear_provider_cache
from forge.core.orchestrator import orchestrate
from forge.core.state import SharedState


FIXTURE_ROOT = Path(__file__).parent / "fixtures"


def init_repo(path: Path) -> None:
    subprocess.run(["git", "init", "-b", "main"], cwd=path, check=True, capture_output=True, text=True)
    subprocess.run(["git", "config", "user.name", "Fixture"], cwd=path, check=True, capture_output=True, text=True)
    subprocess.run(["git", "config", "user.email", "fixture@example.com"], cwd=path, check=True, capture_output=True, text=True)
    subprocess.run(["git", "add", "."], cwd=path, check=True, capture_output=True, text=True)
    subprocess.run(["git", "commit", "-m", "Initial fixture"], cwd=path, check=True, capture_output=True, text=True)


def test_fix_mode_fixture_runs_end_to_end(tmp_path, monkeypatch) -> None:
    source_repo = FIXTURE_ROOT / "counter_buggy"
    target_repo = tmp_path / "counter_buggy"
    shutil.copytree(source_repo, target_repo)
    init_repo(target_repo)

    monkeypatch.setenv("FORGE_PROVIDER", "mock")
    monkeypatch.setenv(
        "FORGE_MOCK_RESPONSES",
        str(FIXTURE_ROOT / "mock_responses" / "counter_fix.json"),
    )
    clear_provider_cache()

    state = SharedState(
        mode="fix",
        user_prompt="The increment helper returns the wrong value.",
        repo_path=str(target_repo),
        focus="counter increment logic",
    )

    asyncio.run(orchestrate(state))

    counter_file = target_repo / "counter_app" / "counter.py"
    test_file = target_repo / "tests" / "test_counter.py"
    git_log = subprocess.run(
        ["git", "log", "--oneline"],
        cwd=target_repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout

    assert "return value + 1" in counter_file.read_text(encoding="utf-8")
    assert test_file.exists()
    assert state.tasks[0].status == "done"
    assert "forge: T1 - Fix counter increment behavior" in git_log
    assert state.last_report.get("health") == "green"

