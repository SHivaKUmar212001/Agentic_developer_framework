from __future__ import annotations

import asyncio
import subprocess
from pathlib import Path

from forge.core.llm import clear_provider_cache
from forge.core.orchestrator import orchestrate
from forge.core.state import SharedState


FIXTURE_ROOT = Path(__file__).parent / "fixtures"


def test_parallel_wave_runs_in_isolated_workspaces(tmp_path, monkeypatch) -> None:
    repo_path = tmp_path / "parallel_build"
    repo_path.mkdir()
    (repo_path / "forge.yaml").write_text(
        "\n".join(
            [
                "parallel: true",
                "skip_tests: true",
            ]
        ),
        encoding="utf-8",
    )

    monkeypatch.setenv("FORGE_PROVIDER", "mock")
    monkeypatch.setenv(
        "FORGE_MOCK_RESPONSES",
        str(FIXTURE_ROOT / "mock_responses" / "parallel_build.json"),
    )
    clear_provider_cache()

    state = SharedState(
        mode="build",
        user_prompt="Create alpha and beta notes in parallel.",
        repo_path=str(repo_path),
    )

    asyncio.run(orchestrate(state))

    git_log = subprocess.run(
        ["git", "log", "--oneline"],
        cwd=repo_path,
        check=True,
        capture_output=True,
        text=True,
    ).stdout

    assert (repo_path / "alpha.txt").read_text(encoding="utf-8") == "alpha\n"
    assert (repo_path / "beta.txt").read_text(encoding="utf-8") == "beta\n"
    assert state.tasks[0].status == "done"
    assert state.tasks[1].status == "done"
    assert "forge: T1 - Create alpha note" in git_log
    assert "forge: T2 - Create beta note" in git_log

