# Python Devcontainer Template

A project template for Python/FastAPI development using Docker devcontainers, Claude Code, and uv.

## What's Included

- **Devcontainer** with Python 3.12, uv, go-task, gh CLI, Azure CLI, and Claude Code
- **FastAPI** starter app with health check endpoint
- **Taskfile** for common dev tasks (run, test, lint, format, typecheck, docker)
- **Pre-commit hooks** running ruff, pyright, and pytest (on push)
- **Production Dockerfile** with multi-stage build using system Python
- **Docker Compose** for local container testing
- **Claude Code** project config (`.claude/CLAUDE.md`)

## Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/)
- [PyCharm Professional](https://www.jetbrains.com/pycharm/) (for devcontainer support)
- SSH key configured for GitHub (`~/.ssh/`)
- Anthropic account for Claude Code

The following host directories are bind-mounted into the container:

- `~/.claude/` — Claude Code config, auth, and plugins
- `~/.config/gh/` — GitHub CLI auth
- `~/.azure/` — Azure CLI auth
- `~/.ssh/` — SSH keys (copied with correct permissions)

## Create a New Project

```bash
gh repo create my-new-project --template tomboone/python-devcontainer-template --clone --private
cd my-new-project
```

## Start the Devcontainer

Open the project in PyCharm, then open `.devcontainer/devcontainer.json` and click the gutter icon → **Create Dev Container and Mount Sources**.

Once the JetBrains Client opens, use the integrated terminal for all commands.

### Set the Python Interpreter

In the JetBrains Client: bottom-right interpreter selector → Add Interpreter → Existing → `/home/vscode/.venv/bin/python`

## Common Tasks

All tasks are run inside the devcontainer terminal:

```bash
task                  # List all tasks
task dev              # Run app with hot reload (localhost:8000)
task test             # Run pytest
task lint             # Ruff lint + format check
task typecheck        # Pyright type checking
task check            # Run all checks (lint, typecheck, test)
task fmt              # Auto-format with ruff
```

### Docker (run from host)

```bash
docker compose up --build    # Build and run the production container
docker compose down          # Stop it
```

## Claude Code

Claude Code is available inside the devcontainer:

```bash
claude                # Start Claude Code
```

Your host's Claude Code settings, auth, and plugins (including Superpowers) carry through via the bind mount.

## Project Structure

```
├── .claude/
│   └── CLAUDE.md                 # Claude Code project instructions
├── .devcontainer/
│   ├── devcontainer.json         # Dev environment config
│   └── Dockerfile                # Dev container image
├── .pre-commit-config.yaml       # Pre-commit hook config
├── compose.yaml                  # App container (local testing)
├── Dockerfile                    # App production image
├── pyproject.toml                # Dependencies and tool config
├── Taskfile.yml                  # Task runner commands
├── src/
│   └── main.py                   # FastAPI entrypoint
└── tests/
    └── __init__.py
```

## After Creating a New Project

1. Update `name` in `pyproject.toml`
2. Edit `.claude/CLAUDE.md` with project-specific details
3. Add dependencies: `uv add <package>`
4. Run `/init` in Claude Code to enrich CLAUDE.md based on your codebase
