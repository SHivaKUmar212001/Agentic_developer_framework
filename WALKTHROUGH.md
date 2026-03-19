# End-to-end walkthrough

This is the intended flow for a build request such as:

```bash
forge run "build a bookmark manager CLI with SQLite storage and tag support"
```

## High-level phases

1. `Planner` breaks the request into a dependency-aware task graph.
2. `Coder` implements one task at a time.
3. `Reviewer` rejects unsafe or incomplete work and sends issues back.
4. `Tester` writes tests and runs them in a subprocess.
5. `Fixer` makes minimal patches when tests fail.
6. `Reporter` writes `FORGE_REPORT.md` with a final summary.

## Example execution plan

```text
Wave 1: T1 - Project setup
Wave 2: T2 - Database layer
Wave 3: T3 - CRUD operations, T4 - Tag system
Wave 4: T5 - CLI interface
Wave 5: T6 - Search and filtering
```

The scheduler can identify independent tasks in the same wave. The current
executor still applies them one at a time so sibling tasks do not overwrite one
another or fight over git state.

## Output you can expect

- A repo or output directory with generated source files
- Tests created and executed for each task
- One git commit per completed task when commit metadata is configured
- A `FORGE_REPORT.md` summary with limitations and next steps

