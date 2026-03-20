# Agentic Developer Framework

An experimental multi-agent developer workflow packaged as `forge`.

Important: do not ship your personal API key inside the package or repository.
If you embed your key in a public build, anyone who installs it can extract that
key and use your paid model account.

The framework takes a single goal, turns it into a task graph, and then runs
planning, coding, review, testing, fixing, and reporting steps in order. The
control flow is deterministic Python, while the agents themselves are prompt
driven.

## What is included

- CLI entry points: `forge run`, `forge build`, and `forge fix`
- Agent roles for planning, coding, review, testing, fixing, and reporting
- Isolated per-task workspaces for parallel-ready waves
- Structured edit operations instead of prompt-only full-file rewrites
- Provider adapters for Anthropic, OpenAI, Ollama, and mock testing
- Hardened shell execution through an allowlist and no-shell subprocess policy
- Project-level configuration through `forge.yaml`
- Fixture-based tests plus GitHub Actions CI

## Install

### One-command install from PyPI

Once the package is published, the simplest install is:

```bash
pip install forge-agents
```

If the `forge` command is not on your shell path after install, use:

```bash
python -m forge.cli --help
```

### One-command install from GitHub

If you want the latest repository version directly:

```bash
pip install git+https://github.com/SHivaKUmar212001/Agentic_developer_framework.git
```

## Quick start on macOS and Linux

```bash
python -m venv .venv
source .venv/bin/activate
pip install forge-agents

export ANTHROPIC_API_KEY="sk-ant-..."
export FORGE_PROVIDER="anthropic"

# Build mode
forge build "build a todo app with auth and SQLite"

# Fix mode
forge fix ./my-repo --focus "the login endpoint returns 500"
```

## Quick start on Windows PowerShell

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install forge-agents

$env:FORGE_PROVIDER = "anthropic"
$env:ANTHROPIC_API_KEY = "sk-ant-..."

forge --help
forge build "build a todo app with auth and SQLite"
```

If `forge` is not found, run:

```powershell
py -m forge.cli --help
```

## Install from source

If someone wants to develop or modify the framework locally:

```bash
git clone https://github.com/SHivaKUmar212001/Agentic_developer_framework.git
cd Agentic_developer_framework
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Configuration

Copy [`forge.example.yaml`](https://github.com/SHivaKUmar212001/Agentic_developer_framework/blob/main/forge.example.yaml)
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

## Local-model architecture with Ollama

If you want the right local-first setup, keep the model on the user's machine
with Ollama instead of shipping a shared cloud API key.

Recommended flow:

1. Install Ollama on the local machine.
2. Start the Ollama server.
3. Pull a local model once.
4. Point forge at Ollama.

macOS and Linux:

```bash
ollama serve
ollama pull llama3.1:8b

echo 'export FORGE_PROVIDER="ollama"' >> ~/.zshrc
echo 'export FORGE_MODEL="llama3.1:8b"' >> ~/.zshrc
source ~/.zshrc

forge build "create a dashboard to track my gym progress"
```

Windows PowerShell:

```powershell
ollama serve
ollama pull llama3.1:8b

Add-Content $PROFILE '$env:FORGE_PROVIDER = "ollama"'
Add-Content $PROFILE '$env:FORGE_MODEL = "llama3.1:8b"'
. $PROFILE

forge build "create a dashboard to track my gym progress"
```

Why this architecture is better:

- no shared cloud API key in the client package
- users can run locally without exposing your billing account
- setup is still one-time per machine
- it can work offline once Ollama and the model are present

## Persist your API key once on your own machine

For your own local use, set the provider and API key once in your shell profile
so you do not have to re-enter them every time.

macOS and Linux with `zsh`:

```bash
echo 'export FORGE_PROVIDER="anthropic"' >> ~/.zshrc
echo 'export ANTHROPIC_API_KEY="sk-ant-..."' >> ~/.zshrc
source ~/.zshrc
```

Windows PowerShell profile:

```powershell
Add-Content $PROFILE '$env:FORGE_PROVIDER = "anthropic"'
Add-Content $PROFILE '$env:ANTHROPIC_API_KEY = "sk-ant-..."'
. $PROFILE
```

That removes repeated setup for you, but end users should still use their own
key or a local provider such as Ollama.

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

## Publishing

Build and validate the package locally:

```bash
python -m build
twine check dist/*
```

Publish to PyPI:

```bash
twine upload dist/*
```

Or publish from GitHub Actions after adding a repository secret named
`PYPI_API_TOKEN`, then either:

- run the `Publish` workflow manually, or
- push a version tag like `v0.1.1`

See [`WALKTHROUGH.md`](https://github.com/SHivaKUmar212001/Agentic_developer_framework/blob/main/WALKTHROUGH.md)
for a sample end-to-end run.
