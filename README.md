# Agentic Developer Framework

An experimental multi-agent developer workflow packaged as `forge`.

The framework takes a single goal, turns it into a task graph, and then runs
planning, coding, review, testing, fixing, and reporting steps in order. The
control flow is deterministic Python, while the agents themselves are prompt
driven.

## What is included

- A CLI entry point: `forge run`
- Agent roles for planning, coding, review, testing, fixing, and reporting
- Wave-based task planning that surfaces parallelizable work
- Project-level configuration through `forge.yaml`
- A small smoke-test suite for the package internals

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

export ANTHROPIC_API_KEY="sk-ant-..."

# Build mode
forge run "build a todo app with auth and SQLite"

# Fix mode
forge run --fix ./my-repo --focus "the login endpoint returns 500"
```

## Configuration

Copy [forge.example.yaml](/Users/shibapalo/Documents/AI agentic developer framework/forge.example.yaml)
to `forge.yaml` in the repo you want `forge` to work on, then adjust the flags
you need.

You can also override the default model globally:

```bash
export FORGE_MODEL="claude-sonnet-4-20250514"
export FORGE_MAX_TOKENS="8192"
```

## Repository layout

```text
forge/
  cli.py
  core/
    config.py
    llm.py
    orchestrator.py
    parallel.py
    state.py
  agents/
    base.py
    planner.py
    coder.py
    reviewer.py
    tester.py
    fixer.py
    reporter.py
tests/
```

## Current limitations

- The framework currently uses Anthropic directly; provider abstraction is still
  thin.
- Task waves are identified up front, but execution stays serialized to avoid
  file and git conflicts inside a shared working tree.
- Shell commands are model generated, so sandboxing and allowlists are an
  important next hardening step.

## Suggested improvement areas

1. Add isolated task sandboxes so independent tasks can truly run in parallel.
2. Replace prompt-only file writes with structured diffs or tool calling.
3. Add real integration tests against small fixture repositories.
4. Support multiple LLM providers behind a single adapter interface.

See [WALKTHROUGH.md](/Users/shibapalo/Documents/AI agentic developer framework/WALKTHROUGH.md)
for a sample end-to-end run.

