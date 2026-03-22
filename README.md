# Daily Agenda Email

A containerized Python app that sends a daily morning email combining your Google Calendar events, Todoist tasks, and your spouse's calendar — all in one glanceable digest.

## What it does

Every morning at a configured time, the app:

1. Fetches today's events from multiple Google Calendars across multiple Google accounts
2. Fetches today's and overdue tasks from Todoist
3. Applies per-calendar and per-project filters to exclude unwanted items
4. Composes an HTML email with color-coded sections
5. Sends it via Azure Communication Services

### Email sections

- **Dinner** — meal planning calendar entry for the day
- **All-Day Events** — birthdays, holidays, etc.
- **Calendar** — timed events sorted chronologically, color-coded by source calendar
- **Tasks** — overdue tasks first, then today's, color-coded by Todoist project
- **Spouse's Schedule** — separate section with events from shared calendars

Empty sections are omitted automatically.

## Stack

- Python 3.12, FastAPI, uvicorn
- APScheduler (in-process cron)
- Google Calendar API + OAuth
- Todoist REST API v2
- Azure Key Vault (secrets + OAuth token storage)
- Azure Communication Services (email)
- Jinja2 (HTML email template)
- Docker for deployment to Azure App Service
- OpenTofu for infrastructure provisioning

## Prerequisites

- A Google Cloud OAuth app with the `calendar.readonly` scope
- A Todoist API token
- An Azure subscription with an existing App Service Plan
- An Azure Communication Services resource with a verified sender domain
- OpenTofu (or Terraform) CLI installed for infrastructure provisioning

## Infrastructure

All Azure resources are provisioned via OpenTofu in the `infra/` directory.

### What it provisions

| Resource | Name |
|---|---|
| Resource Group | `rg-daily-agenda-email` |
| Key Vault | `kv-daily-agenda-email` |
| Linux Web App | `daily-agenda-email` |
| RBAC role assignments | Key Vault Secrets Officer for Web App + deployer |
| Key Vault secrets | `app-config`, `azure-comms-connection-string`, `send-endpoint-token` (auto), `google-oauth-client`, `todoist-api-token` (placeholders) |

It also references your existing App Service Plan and Azure Communication Services as data sources.

### Provision

```bash
cd infra
tofu init -backend-config=backend.hcl
tofu plan
tofu apply
```

`tofu apply` reads your `config.yaml` from the project root and stores it as the `app-config` Key Vault secret. Run `tofu apply` again whenever you update `config.yaml`.

## Setup

### 1. Environment (local dev)

Copy `.env.example` to `.env` and set your Key Vault URL:

```
KEY_VAULT_URL=https://kv-daily-agenda-email.vault.azure.net/
```

### 2. Configuration

Create a `config.yaml` at the project root (gitignored):

```yaml
send_time: "06:00"
timezone: "America/New_York"
recipient_email: "you@example.com"
sender_email: "DoNotReply@your-domain.azurecomm.net"

google_accounts:
  - name: "personal"
    calendars:
      - id: "primary"
        label: "Personal"
        section: "self"
        filters:
          exclude_titles: []
      - id: "meal_calendar_id@group.calendar.google.com"
        label: "Meal Planning"
        section: "meal_planning"
        filters:
          exclude_titles: ["Weekly Meal Planning"]
      - id: "shared_calendar_id@group.calendar.google.com"
        label: "Family"
        section: "self"
        filters:
          exclude_titles: ["tv off", "bed", "lights out"]
      - id: "wife_calendar_id@group.calendar.google.com"
        label: "Wife"
        section: "wife"
        filters:
          exclude_titles: []
  - name: "work"
    calendars:
      - id: "primary"
        label: "Work"
        section: "self"
        filters:
          exclude_titles: []

todoist:
  filters:
    exclude_projects: ["Dog"]
    exclude_titles: ["Outside"]

meal_planning_section_label: "Dinner"
wife_section_label: "Sarah's Schedule"
```

#### Calendar sections

Each calendar's `section` field controls where its events appear:

| Value | Section |
|---|---|
| `"self"` | Main calendar + all-day events sections |
| `"wife"` | Spouse's schedule (below a divider) |
| `"meal_planning"` | Meal planning (top of email, no time shown) |

#### Filters

- `exclude_titles` — exact match, case-insensitive. An event titled "bed" is filtered, but "Bedtime routine" is not.
- `exclude_projects` — Todoist project names, exact match, case-insensitive.

### 3. Key Vault secrets

After `tofu apply`, these secrets are **auto-populated** — no manual step:

| Secret name | Source |
|---|---|
| `app-config` | Your `config.yaml` (via `tofu apply`) |
| `azure-comms-connection-string` | Read from your existing ACS resource |
| `send-endpoint-token` | Auto-generated random string |

These require **manual population** after provisioning:

| Secret name | Value |
|---|---|
| `google-oauth-client` | `{"client_id": "...", "client_secret": "..."}` |
| `todoist-api-token` | Your Todoist API token |

At startup, the app loads config from the `app-config` Key Vault secret. If not found (local dev), it falls back to the local `config.yaml` file.

### 4. Google OAuth

Start the app, then authorize each Google account by visiting:

```
http://localhost:8000/auth/google/start/personal
http://localhost:8000/auth/google/start/work
```

Tokens are stored in Key Vault as `google-token-{account_name}` and refreshed automatically.

### 5. Verify

Trigger a manual send:

```bash
curl -X POST http://localhost:8000/send -H "X-Send-Token: your-token"
```

## Development

### Commands

```bash
task dev              # Run locally with hot reload
task test             # Run tests
task lint             # Ruff lint + format check
task typecheck        # Pyright type checking
task check            # Run all checks (lint, typecheck, test)
task fmt              # Auto-format
```

### Project structure

```
src/
  main.py              — FastAPI app factory, routes, lifespan
  config.py            — Pydantic config models, YAML loading
  secrets.py           — Azure Key Vault wrapper
  google_auth.py       — Google OAuth flow + token storage
  google_calendar.py   — Fetch & filter calendar events
  todoist.py           — Fetch & filter tasks, color mapping
  email.py             — Compose HTML + send via Azure
  scheduler.py         — APScheduler cron job
  templates/
    agenda.html        — Jinja2 email template

infra/
  providers.tf         — OpenTofu provider and backend config
  variables.tf         — Input variable declarations
  data.tf              — Existing App Service Plan + ACS data sources
  main.tf              — Resource group, Key Vault, Web App, secrets
  outputs.tf           — Web app URL/name, Key Vault URI
  terraform.tfvars     — Non-secret variable values (committed)
  backend.hcl          — State backend config (committed)
```

### Local development

The app uses `DefaultAzureCredential`, which falls back to Azure CLI auth locally:

```bash
az login
```

Then `task dev` to run the app. Use `POST /send` to test without waiting for the scheduler.

## Deployment

The app runs as a Docker container on Azure App Service, provisioned via OpenTofu.

```bash
task up       # Build and start locally in Docker
task down     # Stop
```

In production:
- Infrastructure provisioned via `tofu apply` (see [Infrastructure](#infrastructure))
- `KEY_VAULT_URL` set automatically as an App Service app setting by OpenTofu
- Config stored as Key Vault secret `app-config` (updated via `tofu apply`)
- Managed Identity authenticates to Key Vault (no credentials needed)
- GitHub Actions builds/pushes to GHCR, then deploys to App Service via OIDC
- The scheduler runs in-process at the configured time

### Manual steps after first provision

1. Add a federated credential to your Azure App Registration for this repo
2. Populate `google-oauth-client` and `todoist-api-token` in Key Vault
3. Set up GitHub Actions with 3 secrets: Azure client ID, tenant ID, subscription ID
4. Deploy the app, then visit `/auth/google/start/{account}` to authorize each Google account

## API

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Health check |
| `GET` | `/auth/google/start/{account}` | Start Google OAuth flow |
| `GET` | `/auth/google/callback` | OAuth callback (automatic) |
| `POST` | `/send` | Manually trigger email (requires `X-Send-Token` header) |
