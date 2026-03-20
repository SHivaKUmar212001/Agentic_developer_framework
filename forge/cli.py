from __future__ import annotations

import asyncio
import os
from typing import Optional

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from forge import __version__

console = Console()


@click.group()
@click.version_option(version=__version__)
def cli() -> None:
    """forge - multi-agent developer workflow."""


def _execute(mode: str, user_prompt: str, repo_path: str, focus: str = "") -> None:
    from forge.core.orchestrator import orchestrate
    from forge.core.providers import ProviderSetupError
    from forge.core.state import SharedState

    state = SharedState(
        mode=mode,
        user_prompt=user_prompt,
        repo_path=repo_path,
        focus=focus,
    )

    console.print(
        Panel(
            f"Mode: {mode.upper()}\n"
            f"{'Repo' if mode == 'fix' else 'Output'}: {repo_path}\n"
            f"Prompt: {user_prompt}"
            + (f"\nFocus: {focus}" if focus else ""),
            title="forge",
            style="bold blue",
        )
    )

    try:
        asyncio.run(orchestrate(state))
    except ProviderSetupError as exc:
        raise click.ClickException(str(exc)) from exc


@cli.command()
@click.argument("prompt", required=False)
@click.option("--fix", type=click.Path(exists=True), help="Path to repo to fix")
@click.option("--focus", default="", help="Optional bug or area to focus on")
@click.option(
    "--output",
    "-o",
    default="./forge-output",
    help="Output directory to create in build mode",
)
def run(prompt: Optional[str], fix: Optional[str], focus: str, output: str) -> None:
    """Run the full pipeline in build mode or fix mode."""
    if fix is None and prompt is None:
        console.print("[red]Provide a prompt or use --fix <path>.[/red]")
        raise click.Abort()

    if fix:
        _execute(
            mode="fix",
            user_prompt=prompt or "Analyze and fix issues in this repository.",
            repo_path=os.path.abspath(fix),
            focus=focus,
        )
        return

    _execute(
        mode="build",
        user_prompt=prompt or "",
        repo_path=os.path.abspath(output),
        focus=focus,
    )


@cli.command()
@click.argument("prompt")
@click.option(
    "--output",
    "-o",
    default="./forge-output",
    help="Output directory to create in build mode",
)
def build(prompt: str, output: str) -> None:
    """Run the build pipeline."""
    _execute(
        mode="build",
        user_prompt=prompt,
        repo_path=os.path.abspath(output),
    )


@cli.command()
@click.argument("path", type=click.Path(exists=True))
@click.option("--prompt", default="Analyze and fix issues in this repository.")
@click.option("--focus", default="", help="Optional bug or area to focus on")
def fix(path: str, prompt: str, focus: str) -> None:
    """Run the fix pipeline against an existing repository."""
    _execute(
        mode="fix",
        user_prompt=prompt,
        repo_path=os.path.abspath(path),
        focus=focus,
    )


@cli.command()
def agents() -> None:
    """Show the built-in agent roles."""
    from forge.agents.coder import Coder
    from forge.agents.fixer import Fixer
    from forge.agents.planner import Planner
    from forge.agents.reporter import Reporter
    from forge.agents.reviewer import Reviewer
    from forge.agents.tester import Tester

    table = Table(title="Forge agents", show_lines=True)
    table.add_column("Agent", style="bold")
    table.add_column("Role")
    table.add_column("Writes code?")

    rows = [
        (Planner.name, "Breaks a goal into a task graph", "No"),
        (Coder.name, "Implements one task at a time", "Yes"),
        (Reviewer.name, "Finds correctness and security issues", "No"),
        (Tester.name, "Writes and runs tests", "Yes"),
        (Fixer.name, "Makes minimal bug-fix patches", "Yes"),
        (Reporter.name, "Summarizes the run", "No"),
    ]

    for row in rows:
        table.add_row(*row)

    console.print(table)


def main() -> None:
    cli()


if __name__ == "__main__":
    main()
