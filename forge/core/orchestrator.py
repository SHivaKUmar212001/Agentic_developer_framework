from __future__ import annotations

import os
import subprocess
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from forge.agents.coder import Coder
from forge.agents.fixer import Fixer
from forge.agents.planner import Planner
from forge.agents.reporter import Reporter
from forge.agents.reviewer import Reviewer
from forge.agents.tester import Tester
from forge.core.config import ForgeConfig
from forge.core.parallel import describe_execution_plan, get_execution_waves
from forge.core.state import SharedState, Task

console = Console()


def write_files(files: list[dict], repo_path: str, state: SharedState) -> None:
    for file_spec in files:
        full_path = os.path.join(repo_path, file_spec["path"])
        directory = os.path.dirname(full_path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        with open(full_path, "w", encoding="utf-8") as handle:
            handle.write(file_spec["content"])
        state.written_files[file_spec["path"]] = file_spec["content"]


def run_commands(commands: list[str], repo_path: str, state: SharedState) -> None:
    for command in commands:
        state.add_log("shell", f"Running: {command}")
        try:
            result = subprocess.run(
                command,
                cwd=repo_path,
                shell=True,
                capture_output=True,
                text=True,
                timeout=180,
            )
            if result.returncode != 0:
                message = result.stderr.strip() or result.stdout.strip()
                state.add_log("shell", f"Command failed ({result.returncode}): {message}")
        except Exception as exc:
            state.add_log("shell", f"Command failed: {exc}")


def write_report(report: dict, repo_path: str) -> str:
    report_path = os.path.join(repo_path, "FORGE_REPORT.md")
    with open(report_path, "w", encoding="utf-8") as handle:
        handle.write(f"# {report.get('title', 'Forge Report')}\n\n")
        handle.write(f"Health: {report.get('health', 'unknown')}\n\n")
        handle.write(f"## Overview\n{report.get('overview', '')}\n\n")
        handle.write(f"## Architecture\n{report.get('architecture', '')}\n\n")

        files = report.get("files", {})
        if files:
            handle.write("## Files\n")
            for category, paths in files.items():
                handle.write(f"\n### {category}\n")
                for path in paths:
                    handle.write(f"- `{path}`\n")

        limitations = report.get("limitations", [])
        if limitations:
            handle.write("\n## Limitations\n")
            for limitation in limitations:
                handle.write(f"- {limitation}\n")

        next_steps = report.get("next_steps", [])
        if next_steps:
            handle.write("\n## Next steps\n")
            for step in next_steps:
                handle.write(f"- {step}\n")

    return report_path


async def process_single_task(
    task: Task,
    state: SharedState,
    config: ForgeConfig,
    coder: Coder,
    reviewer: Reviewer,
    tester: Tester,
    fixer: Fixer,
) -> bool:
    repo_path = state.repo_path
    task.status = "in_progress"

    console.print(Panel(f"Task {task.id}: {task.description}", style="bold green"))

    console.print("[cyan]  Coder[/cyan] writing code...")
    try:
        code_output = await coder.run(state, task)
    except Exception as exc:
        task.status = "failed"
        state.add_log("coder", f"{task.id} failed: {exc}")
        console.print(f"[red]  Coder failed: {exc}[/red]")
        return False

    write_files(code_output.get("files", []), repo_path, state)
    run_commands(code_output.get("commands", []), repo_path, state)

    if not config.skip_review:
        for attempt in range(1, config.max_review_retries + 1):
            console.print(f"[yellow]  Reviewer[/yellow] (attempt {attempt})...")
            try:
                review = await reviewer.run(state, task, code_output=code_output)
            except Exception as exc:
                state.add_log("reviewer", f"{task.id} failed: {exc}")
                console.print(f"[red]  Review error: {exc}[/red]")
                break

            if review.get("approved"):
                console.print("[green]  Approved[/green]")
                break

            issues = review.get("issues", [])
            console.print(f"[red]  Rejected - {len(issues)} issue(s)[/red]")
            for issue in issues[:5]:
                console.print(
                    f"    [{issue['severity']}] {issue['file']}:{issue.get('line', '?')} "
                    f"- {issue['description']}"
                )

            if attempt < config.max_review_retries:
                console.print("[cyan]  Coder[/cyan] fixing review issues...")
                try:
                    code_output = await coder.run(state, task, feedback=issues)
                    write_files(code_output.get("files", []), repo_path, state)
                    run_commands(code_output.get("commands", []), repo_path, state)
                except Exception as exc:
                    state.add_log("coder", f"{task.id} review fix failed: {exc}")
                    break
    else:
        console.print("[dim]  Review skipped by config.[/dim]")

    if not config.skip_tests:
        console.print("[magenta]  Tester[/magenta] writing and running tests...")
        try:
            test_result = await tester.run(state, task, code_output=code_output)
        except Exception as exc:
            state.add_log("tester", f"{task.id} failed: {exc}")
            console.print(f"[red]  Test run failed: {exc}[/red]")
            task.status = "failed"
            return False

        if test_result.get("all_passed"):
            console.print(f"[green]  {test_result.get('passed', 0)} tests passed[/green]")
        else:
            console.print(f"[red]  {test_result.get('failed', 0)} test(s) failed[/red]")
            for attempt in range(1, config.max_fix_retries + 1):
                console.print(f"[red]  Fixer[/red] (attempt {attempt})...")
                try:
                    fix_output = await fixer.run(
                        state,
                        task,
                        code_output=code_output,
                        test_result=test_result,
                    )
                except Exception as exc:
                    state.add_log("fixer", f"{task.id} failed: {exc}")
                    break

                fixed_files = fix_output.get("files", [])
                write_files(fixed_files, repo_path, state)

                file_map = {file_spec["path"]: file_spec for file_spec in code_output.get("files", [])}
                for fixed_file in fixed_files:
                    file_map[fixed_file["path"]] = fixed_file
                code_output["files"] = list(file_map.values())

                console.print("[magenta]  Tester[/magenta] re-running...")
                test_result = await tester.run(state, task, code_output=code_output)
                if test_result.get("all_passed"):
                    console.print(
                        f"[green]  All {test_result.get('passed', 0)} tests passed[/green]"
                    )
                    break

            if not test_result.get("all_passed"):
                task.status = "failed"
                state.add_log("tester", f"{task.id} still failing after retries")
                return False
    else:
        console.print("[dim]  Tests skipped by config.[/dim]")

    task.status = "done"
    committed = state.commit(task, repo_path)
    if committed:
        console.print(f"[dim]  Committed {task.id}[/dim]")
    else:
        console.print(f"[dim]  No git commit created for {task.id}[/dim]")
    return True


async def orchestrate(state: SharedState) -> None:
    repo_path = state.repo_path
    config = ForgeConfig.load(repo_path)

    if state.mode == "build":
        os.makedirs(repo_path, exist_ok=True)
        if not os.path.exists(os.path.join(repo_path, ".git")):
            subprocess.run(["git", "init"], cwd=repo_path, capture_output=True, text=True)
            state.add_log("git", "Initialized new repo")

    planner = Planner(config.get_agent_config("planner"))
    coder = Coder(config.get_agent_config("coder"))
    reviewer = Reviewer(config.get_agent_config("reviewer"))
    tester = Tester(config.get_agent_config("tester"))
    fixer = Fixer(config.get_agent_config("fixer"))
    reporter = Reporter(config.get_agent_config("reporter"))

    console.print(Panel("Phase 1: Planning", style="bold cyan"))
    await planner.run(state)

    task_table = Table(title="Task graph", show_lines=True)
    task_table.add_column("ID", style="bold")
    task_table.add_column("Description")
    task_table.add_column("Depends on")
    task_table.add_column("Acceptance criteria", style="dim")
    for task in state.tasks:
        task_table.add_row(
            task.id,
            task.description,
            ", ".join(task.dependencies) or "-",
            task.acceptance_criteria,
        )
    console.print(task_table)

    waves = get_execution_waves(state.tasks)
    console.print(f"\n[bold]Execution plan ({len(waves)} waves)[/bold]")
    console.print(describe_execution_plan(waves))

    console.print(Panel("Phase 2: Build, Review, and Test", style="bold green"))
    for wave_index, wave in enumerate(waves, start=1):
        console.print(f"\n{'=' * 60}")
        mode_label = "parallel-ready" if len(wave) > 1 else "sequential"
        console.print(f"[bold]Wave {wave_index}/{len(waves)} ({mode_label})[/bold]")
        if len(wave) > 1 and config.parallel:
            console.print(
                "[dim]Independent tasks were identified, but execution remains serialized "
                "to avoid shared workspace conflicts.[/dim]"
            )

        for task in wave:
            await process_single_task(task, state, config, coder, reviewer, tester, fixer)

    console.print(f"\n{'=' * 60}")
    console.print(Panel("Phase 3: Summary", style="bold blue"))

    try:
        report = await reporter.run(state)
        state.last_report = report
        report_path = write_report(report, repo_path)
        state.written_files["FORGE_REPORT.md"] = Path(report_path).read_text(encoding="utf-8")
        console.print(
            Panel(
                f"{report.get('overview', '')}\n\n"
                "Next steps:\n"
                + "\n".join(f"- {step}" for step in report.get("next_steps", [])),
                title=report.get("title", "Forge Report"),
                style="blue",
            )
        )
    except Exception as exc:
        state.add_log("reporter", f"Failed: {exc}")
        console.print(f"[red]Reporter failed: {exc}[/red]")

    stats = Table(show_header=False, box=None, padding=(0, 2))
    stats.add_column(style="dim")
    stats.add_column(style="bold")
    stats.add_row("Tasks completed", f"{sum(task.status == 'done' for task in state.tasks)}/{len(state.tasks)}")
    stats.add_row("Tasks failed", str(sum(task.status == 'failed' for task in state.tasks)))
    stats.add_row("Files written", str(len(state.written_files)))
    stats.add_row("Review rounds", str(len(state.review_history)))
    stats.add_row("Repo", os.path.abspath(repo_path))
    console.print(stats)
