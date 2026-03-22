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

## Prerequisites

- A Google Cloud OAuth app with the `calendar.readonly` scope
- A Todoist API token
- An Azure Key Vault instance
- An Azure Communication Services resource with a verified sender domain

## Setup

### 1. Environment

Copy `.env.example` to `.env` and set your Key Vault URL:

```
KEY_VAULT_URL=https://your-vault-name.vault.azure.net/
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

Populate these secrets in your Azure Key Vault:

| Secret name | Value |
|---|---|
| `google-oauth-client` | `{"client_id": "...", "client_secret": "..."}` |
| `todoist-api-token` | Your Todoist API token |
| `azure-comms-connection-string` | Azure Communication Services connection string |
| `send-endpoint-token` | Any random string (protects the manual send endpoint) |
| `app-config` | *(production only)* Your `config.yaml` contents — see below |

For production, store your config in Key Vault instead of mounting a file:

```bash
az keyvault secret set --vault-name your-vault --name app-config --file config.yaml
```

At startup, the app checks for `app-config` in Key Vault first. If not found, it falls back to the local `config.yaml` file. This means local dev works without the secret, and production needs no file mounts.

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
```

### Local development

The app uses `DefaultAzureCredential`, which falls back to Azure CLI auth locally:

```bash
az login
```

Then `task dev` to run the app. Use `POST /send` to test without waiting for the scheduler.

## Deployment

The app runs as a Docker container on Azure App Service.

```bash
task up       # Build and start locally in Docker
task down     # Stop
```

In production:
- `KEY_VAULT_URL` is set as an App Service application setting
- Config is stored as Key Vault secret `app-config` (no file mounts needed)
- Managed Identity authenticates to Key Vault (no credentials needed)
- The scheduler runs in-process at the configured time

## API

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Health check |
| `GET` | `/auth/google/start/{account}` | Start Google OAuth flow |
| `GET` | `/auth/google/callback` | OAuth callback (automatic) |
| `POST` | `/send` | Manually trigger email (requires `X-Send-Token` header) |
