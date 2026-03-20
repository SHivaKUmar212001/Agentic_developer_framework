from __future__ import annotations

import asyncio
import copy
import os
import subprocess
from pathlib import Path
from dataclasses import dataclass
from typing import Any

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
from forge.core.edits import apply_operations, materialize_file_specs, normalize_operations
from forge.core.parallel import describe_execution_plan, get_execution_waves
from forge.core.shell import ShellExecutor
from forge.core.state import SharedState, Task
from forge.core.workspaces import (
    collect_workspace_operations,
    create_task_workspace,
    remove_workspace,
)

console = Console()


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


@dataclass
class TaskRunResult:
    task_id: str
    success: bool
    workspace_path: str
    merge_operations: list[dict[str, Any]]
    changed_paths: set[str]
    task_state: SharedState
    new_logs: list[str]
    new_reviews: list[dict[str, Any]]
    test_result: dict[str, Any]
    error: str = ""


def apply_output_payload(
    payload: dict[str, Any],
    repo_path: str,
    *,
    legacy_key: str,
    output_key: str,
) -> list[str]:
    operations = normalize_operations(payload, legacy_key=legacy_key)
    changed_paths = apply_operations(repo_path, operations)
    payload["operations"] = operations
    payload[output_key] = materialize_file_specs(repo_path, changed_paths)
    return changed_paths


def run_safe_commands(
    commands: list[str],
    repo_path: str,
    state: SharedState,
    executor: ShellExecutor,
) -> None:
    for command in commands:
        state.add_log("shell", f"Running: {command}")
        result = executor.run_command(command, repo_path)
        if not result.get("allowed"):
            state.add_log("shell", f"Blocked command: {result.get('output', '')}")
            continue

        if result.get("return_code", 1) != 0:
            output = result.get("output", "").strip()
            state.add_log("shell", f"Command failed ({result['return_code']}): {output}")


def execute_test_spec(
    task: Task,
    task_state: SharedState,
    tester: Tester,
    test_spec: dict[str, Any],
    executor: ShellExecutor,
) -> dict[str, Any]:
    test_paths = apply_output_payload(
        test_spec,
        task_state.repo_path,
        legacy_key="test_files",
        output_key="test_files",
    )
    run_command = test_spec.get("run_command", "python -m pytest tests -q")
    command_result = executor.run_command(run_command, task_state.repo_path)
    summary = tester.summarize_test_command(command_result)
    result = {
        "test_files": materialize_file_specs(task_state.repo_path, test_paths),
        "run_command": run_command,
        **summary,
    }
    task_state.test_results = result
    task_state.test_history.append(result)
    task_state.add_log(
        tester.name,
        f"{task.id}: {result.get('passed', 0)} passed, {result.get('failed', 0)} failed",
    )
    return result


async def process_single_task(
    task: Task,
    state: SharedState,
    workspace_path: str,
    base_snapshot: dict[str, str],
    config: ForgeConfig,
    coder: Coder,
    reviewer: Reviewer,
    tester: Tester,
    fixer: Fixer,
    executor: ShellExecutor,
    log_offset: int,
    review_offset: int,
) -> TaskRunResult:
    repo_path = workspace_path
    state.repo_path = workspace_path
    task.status = "in_progress"

    console.print(Panel(f"Task {task.id}: {task.description}", style="bold green"))

    console.print("[cyan]  Coder[/cyan] writing code...")
    try:
        code_output = await coder.run(state, task)
        apply_output_payload(code_output, repo_path, legacy_key="files", output_key="files")
        for file_spec in code_output.get("files", []):
            state.written_files[file_spec["path"]] = file_spec["content"]
        run_safe_commands(code_output.get("commands", []), repo_path, state, executor)
    except Exception as exc:
        task.status = "failed"
        state.add_log("coder", f"{task.id} failed: {exc}")
        console.print(f"[red]  Coder failed: {exc}[/red]")
        return TaskRunResult(
            task_id=task.id,
            success=False,
            workspace_path=workspace_path,
            merge_operations=[],
            changed_paths=set(),
            task_state=state,
            new_logs=state.log[log_offset:],
            new_reviews=state.review_history[review_offset:],
            test_result=state.test_results,
            error=str(exc),
        )

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
                    apply_output_payload(
                        code_output,
                        repo_path,
                        legacy_key="files",
                        output_key="files",
                    )
                    for file_spec in code_output.get("files", []):
                        state.written_files[file_spec["path"]] = file_spec["content"]
                    run_safe_commands(code_output.get("commands", []), repo_path, state, executor)
                except Exception as exc:
                    state.add_log("coder", f"{task.id} review fix failed: {exc}")
                    break
    else:
        console.print("[dim]  Review skipped by config.[/dim]")

    if not config.skip_tests:
        console.print("[magenta]  Tester[/magenta] writing and running tests...")
        try:
            test_spec = await tester.run(state, task, code_output=code_output)
            test_result = execute_test_spec(task, state, tester, test_spec, executor)
        except Exception as exc:
            state.add_log("tester", f"{task.id} failed: {exc}")
            console.print(f"[red]  Test run failed: {exc}[/red]")
            task.status = "failed"
            return TaskRunResult(
                task_id=task.id,
                success=False,
                workspace_path=workspace_path,
                merge_operations=[],
                changed_paths=set(),
                task_state=state,
                new_logs=state.log[log_offset:],
                new_reviews=state.review_history[review_offset:],
                test_result=state.test_results,
                error=str(exc),
            )

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

                try:
                    fixed_paths = apply_output_payload(
                        fix_output,
                        repo_path,
                        legacy_key="files",
                        output_key="files",
                    )
                    fixed_files = materialize_file_specs(repo_path, fixed_paths)
                    for fixed_file in fixed_files:
                        state.written_files[fixed_file["path"]] = fixed_file["content"]

                    file_map = {
                        file_spec["path"]: file_spec
                        for file_spec in code_output.get("files", [])
                    }
                    for fixed_file in fixed_files:
                        file_map[fixed_file["path"]] = fixed_file
                    code_output["files"] = list(file_map.values())

                    console.print("[magenta]  Tester[/magenta] re-running...")
                    command_result = executor.run_command(test_result["run_command"], repo_path)
                    test_result = {
                        "test_files": test_result.get("test_files", []),
                        "run_command": test_result["run_command"],
                        **tester.summarize_test_command(command_result),
                    }
                    state.test_results = test_result
                    state.test_history.append(test_result)
                    if test_result.get("all_passed"):
                        console.print(
                            f"[green]  All {test_result.get('passed', 0)} tests passed[/green]"
                        )
                        break
                except Exception as exc:
                    state.add_log("fixer", f"{task.id} apply failed: {exc}")
                    break

            if not test_result.get("all_passed"):
                task.status = "failed"
                state.add_log("tester", f"{task.id} still failing after retries")
                return TaskRunResult(
                    task_id=task.id,
                    success=False,
                    workspace_path=workspace_path,
                    merge_operations=[],
                    changed_paths=set(),
                    task_state=state,
                    new_logs=state.log[log_offset:],
                    new_reviews=state.review_history[review_offset:],
                    test_result=test_result,
                    error="Tests still failing after retries.",
                )
    else:
        console.print("[dim]  Tests skipped by config.[/dim]")

    task.status = "done"
    merge_operations, final_paths = collect_workspace_operations(base_snapshot, workspace_path)
    return TaskRunResult(
        task_id=task.id,
        success=True,
        workspace_path=workspace_path,
        merge_operations=merge_operations,
        changed_paths=final_paths,
        task_state=state,
        new_logs=state.log[log_offset:],
        new_reviews=state.review_history[review_offset:],
        test_result=state.test_results,
    )


def merge_task_result(task: Task, state: SharedState, result: TaskRunResult) -> None:
    apply_operations(state.repo_path, result.merge_operations)
    for file_spec in materialize_file_specs(state.repo_path, list(result.changed_paths)):
        state.written_files[file_spec["path"]] = file_spec["content"]
    for operation in result.merge_operations:
        if operation.get("type") == "delete_file":
            state.written_files.pop(operation["path"], None)

    state.log.extend(result.new_logs)
    state.review_history.extend(result.new_reviews)
    if result.test_result:
        state.test_results = result.test_result
        state.test_history.append(result.test_result)

    task.status = "done"
    committed = state.commit(task, state.repo_path)
    if committed:
        console.print(f"[dim]  Committed {task.id}[/dim]")
    else:
        console.print(f"[dim]  No git commit created for {task.id}[/dim]")


async def orchestrate(state: SharedState) -> None:
    repo_path = state.repo_path
    config = ForgeConfig.load(repo_path)
    shell_executor = ShellExecutor(config.shell)

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
        runnable_tasks: list[Task] = []
        for task in wave:
            dep_statuses = {
                dep: next((item.status for item in state.tasks if item.id == dep), "missing")
                for dep in task.dependencies
            }
            if all(status == "done" for status in dep_statuses.values()):
                runnable_tasks.append(task)
            else:
                task.status = "failed"
                state.add_log("orchestrator", f"{task.id} skipped because dependencies failed: {dep_statuses}")
                console.print(f"[red]Skipping {task.id} because a dependency did not complete.[/red]")

        workspace_specs = [
            create_task_workspace(repo_path, task.id, config.runtime_dir)
            for task in runnable_tasks
        ]

        task_runs = []
        for task, workspace in zip(runnable_tasks, workspace_specs):
            task_state = copy.deepcopy(state)
            task_runs.append(
                process_single_task(
                    task,
                    task_state,
                    workspace.path,
                    workspace.base_snapshot,
                    config,
                    coder,
                    reviewer,
                    tester,
                    fixer,
                    shell_executor,
                    len(task_state.log),
                    len(task_state.review_history),
                )
            )

        if len(task_runs) > 1 and config.parallel:
            results = await asyncio.gather(*task_runs)
        else:
            results = []
            for task_run in task_runs:
                results.append(await task_run)

        path_to_tasks: dict[str, list[str]] = {}
        for result in results:
            if not result.success:
                task = next(item for item in state.tasks if item.id == result.task_id)
                task.status = "failed"
                state.log.extend(result.new_logs)
                state.review_history.extend(result.new_reviews)
                if result.test_result:
                    state.test_results = result.test_result
                    state.test_history.append(result.test_result)
                continue
            for path in result.changed_paths:
                path_to_tasks.setdefault(path, []).append(result.task_id)

        conflicting_tasks = {
            task_id
            for task_ids in path_to_tasks.values()
            if len(task_ids) > 1
            for task_id in task_ids
        }
        if conflicting_tasks:
            conflict_paths = {
                path: task_ids for path, task_ids in path_to_tasks.items() if len(task_ids) > 1
            }
            console.print(f"[red]Wave conflict detected: {conflict_paths}[/red]")
            state.add_log("orchestrator", f"Wave conflict detected: {conflict_paths}")

        for task, result in zip(runnable_tasks, results):
            if task.id in conflicting_tasks:
                task.status = "failed"
                state.log.extend(result.new_logs)
                state.review_history.extend(result.new_reviews)
                if result.test_result:
                    state.test_results = result.test_result
                    state.test_history.append(result.test_result)
                state.add_log("orchestrator", f"{task.id} failed due to overlapping file edits.")
                continue
            if result.success:
                merge_task_result(task, state, result)

        if not config.keep_workspaces:
            for workspace in workspace_specs:
                remove_workspace(workspace.path)

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
