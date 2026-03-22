# CLAUDE.md

## Project

Daily agenda email — a containerized FastAPI app that sends a daily morning email combining Google Calendar events, Todoist tasks, and a spouse's calendar. Deployed to Azure App Service.

## Stack

- Python 3.12, FastAPI, uvicorn
- uv for package management
- go-task for task running
- Docker for deployment to Azure App Service
- OpenTofu for infrastructure provisioning
- APScheduler for in-process cron scheduling
- Google Calendar API + OAuth (google-api-python-client, google-auth-oauthlib)
- Todoist REST API v2 (httpx)
- Azure Key Vault for secrets and OAuth token storage (azure-identity, azure-keyvault-secrets)
- Azure Communication Services for email sending (azure-communication-email)
- Jinja2 for HTML email templating
- Pydantic for config validation

## Architecture

App factory pattern — `create_app()` accepts config/secrets/scheduler for testability. No module-level app variable; uvicorn uses `--factory` mode with `build_app_from_env`.

```
src/
  main.py              — App factory, routes (/health, /send, OAuth), lifespan
  config.py            — Pydantic models, YAML loading (file or Key Vault)
  secrets.py           — Azure Key Vault wrapper (SecretsClient)
  google_auth.py       — OAuth flow (create_auth_router)
  google_calendar.py   — CalendarEvent model, fetch & filter events
  todoist.py           — TodoistTask model, fetch & filter tasks, color mapping
  email.py             — Compose HTML (Jinja2) + send via Azure Comms
  scheduler.py         — APScheduler cron job, send_agenda orchestrator
  templates/
    agenda.html        — Jinja2 email template
```

## Infrastructure

OpenTofu config in `infra/`. Provisions resource group, Key Vault, Linux Web App, RBAC role assignments, and Key Vault secrets. References existing App Service Plan and Azure Communication Services as data sources. State stored in Azure Storage.

```
infra/
  providers.tf         — azurerm ~> 4.14, random ~> 3.0, backend "azurerm" {}
  variables.tf         — input variable declarations
  data.tf              — data sources (existing App Service Plan, ACS)
  main.tf              — resource group, Key Vault, Web App, role assignments, secrets
  outputs.tf           — web app URL/name, Key Vault URI, resource group name
  terraform.tfvars     — committed non-secret values
  backend.hcl          — committed backend storage config
```

Key infra commands:
- `cd infra && tofu init -backend-config=backend.hcl` — initialize
- `tofu plan` — preview changes
- `tofu apply` — apply (also updates `app-config` secret from `config.yaml`)

## Configuration

- Non-secret config lives in `config.yaml` (local dev) or Key Vault secret `app-config` (production)
- `tofu apply` reads `config.yaml` from project root and stores it as the `app-config` Key Vault secret
- All secrets in Azure Key Vault: `google-oauth-client`, `google-token-{name}`, `todoist-api-token`, `azure-comms-connection-string`, `send-endpoint-token`, `app-config`
- Single required env var: `KEY_VAULT_URL`
- Optional env var: `CONFIG_PATH` (defaults to `config.yaml`, used only when Key Vault has no `app-config` secret)

## Commands

- `task dev` — run locally with hot reload (uvicorn --factory)
- `task test` — run tests
- `task lint` — ruff lint and format check
- `task typecheck` — pyright type checking
- `task check` — run all checks (lint, typecheck, test)
- `task fmt` — auto-format
- `task up` — build and start in Docker
- `task down` — stop Docker services
- `task` — list all available tasks

## Conventions

- Format and lint with ruff (line-length 100)
- Type check with pyright (basic mode)
- Tests in `tests/` using pytest, use httpx for async test client
- App source in `src/`, entrypoint is `src/main.py` (factory mode: `build_app_from_env`)
- Type hints required on all functions
- Pre-commit hooks run ruff and pyright on commit, pytest on push
- External services (Google, Todoist, Key Vault, Azure Email) are mocked in tests
- Config filters use exact-match, case-insensitive title comparison
