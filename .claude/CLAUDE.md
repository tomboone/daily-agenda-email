# CLAUDE.md

## Project

<!-- Describe your project here -->

## Stack

- Python 3.12, FastAPI, uvicorn
- uv for package management
- go-task for task running
- Docker for deployment

## Commands

- `task dev` — run locally with hot reload
- `task test` — run tests
- `task lint` — ruff lint and format check
- `task typecheck` — pyright type checking
- `task check` — run all checks (lint, typecheck, test)
- `task fmt` — auto-format
- `task up` — build and start in Docker
- `task down` — stop Docker services
- `task` — list all available tasks

## Conventions

- Format and lint with ruff
- Type check with pyright (basic mode)
- Tests in `tests/` using pytest, use httpx for async test client
- App source in `src/`, entrypoint is `src/main.py`
- Type hints required on all functions
- Pre-commit hooks run ruff and pyright on commit, pytest on push
