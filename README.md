# Agentic Developer Framework

An experimental multi-agent developer workflow packaged as `forge`.

The framework takes a single goal, turns it into a task graph, and then runs
planning, coding, review, testing, fixing, and reporting steps in order. The
control flow is deterministic Python, while the agents themselves are prompt
driven.

## What is included

- A CLI entry point: `forge run`
- Agent roles for planning, coding, review, testing, fixing, and reporting
- Isolated per-task workspaces for parallel-ready waves
- Structured edit operations instead of prompt-only full-file rewrites
- Provider adapters for Anthropic, OpenAI, Ollama, and mock testing
- Hardened shell execution through an allowlist and no-shell subprocess policy
- Project-level configuration through `forge.yaml`
- Fixture-based tests plus GitHub Actions CI

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

export ANTHROPIC_API_KEY="sk-ant-..."
export FORGE_PROVIDER="anthropic"

# Build mode
forge run "build a todo app with auth and SQLite"

# Fix mode
forge run --fix ./my-repo --focus "the login endpoint returns 500"
```

## Configuration

Copy [forge.example.yaml]
to `forge.yaml` in the repo you want `forge` to work on, then adjust the flags
you need.

You can also override the default model globally:

```bash
export FORGE_MODEL="claude-sonnet-4-20250514"
export FORGE_MAX_TOKENS="8192"
```

Provider options:

- `FORGE_PROVIDER=anthropic`
- `FORGE_PROVIDER=openai`
- `FORGE_PROVIDER=ollama`
- `FORGE_PROVIDER=mock`

The mock provider is used in the fixture-based end-to-end tests and reads its
responses from `FORGE_MOCK_RESPONSES`.

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

- Parallel tasks still rely on non-overlapping file edits. If two tasks touch
  the same file in a wave, the framework now detects that and fails the wave
  merge for safety.
- Structured edit operations are safer than whole-file blobs, but they still
  depend on the model producing valid targeted replacements.
- The shell policy is hardened, but it is still an allowlist, not a true OS
  sandbox.

## Verification

- Unit tests cover config loading, edit application, workspace diffs, shell
  allowlisting, and provider JSON parsing.
- A realistic fix-mode fixture test runs the orchestrator end to end with the
  mock provider.
- GitHub Actions runs the suite on every push and pull request.

See [WALKTHROUGH.md]
for a sample end-to-end run.
