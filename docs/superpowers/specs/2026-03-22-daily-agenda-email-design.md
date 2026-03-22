# Daily Agenda Email — Design Spec

## Overview

A Python/FastAPI app deployed as a containerized Azure App Service that sends a daily morning email with a meal planning note, combined calendar agenda, Todoist tasks, and a separate section for a spouse's calendar. The app authenticates to multiple Google accounts via OAuth, fetches and filters events/tasks, composes an HTML email, and sends it via Azure Communication Services.

## Architecture

Modular, pragmatic structure — focused modules with clear responsibilities, no unnecessary abstraction.

```
src/
  main.py              — FastAPI app, routes, lifespan
  scheduler.py         — APScheduler setup
  config.py            — YAML config loading + Pydantic validation
  secrets.py           — Azure Key Vault wrapper
  google_auth.py       — Google OAuth flow + token management
  google_calendar.py   — Fetch & filter calendar events
  todoist.py           — Fetch & filter Todoist tasks
  email.py             — Compose HTML + send via Azure Communication Services
  templates/
    agenda.html        — Jinja2 email template
```

## Configuration

A `config.yaml` file at the project root (gitignored) defines all non-secret structured data. Validated at startup by a Pydantic model. The app fails fast on invalid config.

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
      - id: "meal_planning_id@group.calendar.google.com"
        label: "Meal Planning"
        section: "meal_planning"
        filters:
          exclude_titles: ["Meal Planning"]
      - id: "family123@group.calendar.google.com"
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

### Config field reference

- `send_time` — 24-hour HH:MM format
- `timezone` — IANA timezone string
- `recipient_email` — email address to receive the daily agenda
- `sender_email` — Azure Communication Services sender address
- `google_accounts[].name` — unique identifier, used to key OAuth tokens in Key Vault
- `google_accounts[].calendars[].id` — Google Calendar ID
- `google_accounts[].calendars[].label` — display name in the email
- `google_accounts[].calendars[].section` — strict enum: `"self"`, `"wife"`, or `"meal_planning"` (validated by Pydantic, startup fails on invalid value). Determines which email section the events appear in
- `google_accounts[].calendars[].filters.exclude_titles` — list of event titles to exclude (exact match, case-insensitive)
- `todoist.filters.exclude_projects` — Todoist project names to exclude (exact match, case-insensitive)
- `todoist.filters.exclude_titles` — Todoist task titles to exclude (exact match, case-insensitive)
- `meal_planning_section_label` — heading for the meal planning section in the email (e.g., "Dinner")
- `wife_section_label` — heading for the spouse's section in the email

## Secrets & Key Vault

All secrets live in Azure Key Vault, accessed via `DefaultAzureCredential` (Managed Identity in production, Azure CLI in local dev).

### Bootstrap

A single environment variable is required: `KEY_VAULT_URL` — the URI of the Key Vault instance. This is the only env var the app needs.

### Secrets stored

| Key Vault Secret Name | Contents |
|---|---|
| `google-oauth-client` | JSON: `{"client_id": "...", "client_secret": "..."}` |
| `google-token-{account_name}` | JSON: `{"access_token": "...", "refresh_token": "...", "expiry": "..."}` |
| `todoist-api-token` | Plain string |
| `azure-comms-connection-string` | Azure Communication Services connection string |
| `send-endpoint-token` | Shared secret for authenticating `POST /send` requests |

### `secrets.py` module

- Wraps `azure.identity.DefaultAzureCredential` + `azure.keyvault.secrets.SecretClient`
- `get_secret(name: str) -> str` — read a secret
- `set_secret(name: str, value: str) -> None` — write a secret (for OAuth token updates)

## Google OAuth

### OAuth app

A single Google Cloud OAuth app (created in the user's personal Google account) with the `https://www.googleapis.com/auth/calendar.readonly` scope.

### Flow (`google_auth.py`)

Two FastAPI routes handle the interactive OAuth dance:

- `GET /auth/google/start/{account_name}` — Builds the Google authorization URL with `account_name` in the OAuth `state` parameter. Redirects the user to Google's consent screen.
- `GET /auth/google/callback` — Receives the authorization code from Google, exchanges it for access + refresh tokens, and stores them in Key Vault as `google-token-{account_name}`.

The `/start/` prefix avoids a route conflict where `callback` would match the `{account_name}` path parameter.

### Redirect URI

The OAuth redirect URI (`/auth/google/callback`) must be registered in the Google Cloud Console. The app derives the full redirect URI from the incoming request's host, so it works for both `http://localhost:8000` (local dev) and the production Azure App Service URL. Both URIs must be registered in the Google Cloud Console as authorized redirect URIs.

### Token refresh

During calendar fetching, if the access token is expired, the Google auth library automatically refreshes it using the stored refresh token. The updated tokens are written back to Key Vault.

## Google Calendar (`google_calendar.py`)

- For each Google account in config, loads its token from Key Vault and builds an authenticated Google Calendar API client.
- Fetches the calendar list to retrieve each calendar's `backgroundColor` (hex color). This color is carried through to the email template for visual coding.
- Fetches today's events (midnight to midnight in the configured timezone) from each calendar ID listed under that account.
- Applies exact-match, case-insensitive title filters per the calendar's `exclude_titles` config.
- Returns a list of event objects:
  - `title: str`
  - `start_time: datetime | None` (None for all-day events)
  - `end_time: datetime | None`
  - `is_all_day: bool`
  - `calendar_label: str`
  - `calendar_color: str` (hex color from Google Calendar API, e.g., `"#4285f4"`)
  - `section: str` ("self", "wife", or "meal_planning")
- Events sorted by start time. All-day events sort before timed events.

## Todoist (`todoist.py`)

- Uses the Todoist REST API v2 directly via `httpx` (no SDK).
- API token loaded from Key Vault.
- Fetches all active tasks, then filters to tasks due today or earlier (overdue).
- Fetches projects separately to map project IDs to names for project-level filtering.
- Applies filters:
  - Excludes tasks in projects matching `exclude_projects` (exact match, case-insensitive)
  - Excludes tasks with titles matching `exclude_titles` (exact match, case-insensitive)
- Returns a list of task objects:
  - `title: str`
  - `project_name: str`
  - `project_color: str` (hex color derived from Todoist's project color name)
  - `due_date: date`
  - `is_overdue: bool`
- Sorted: overdue tasks first (oldest to newest), then today's tasks.

## Email Composition & Sending (`email.py`)

### Template

A Jinja2 template at `src/templates/agenda.html` renders the email body. Clean, minimal HTML with inline CSS for email client compatibility.

### Email structure

```
Subject: Daily Agenda — Monday, March 22

┌─────────────────────────────────────┐
│  Monday, March 22, 2026             │
│                                     │
│  DINNER                             │
│  Chicken Tikka Masala               │
│                                     │
│  ALL-DAY EVENTS                     │
│  • Spring begins (Personal)         │
│                                     │
│  CALENDAR                           │
│  • 9:00 AM – 10:00 AM  Team sync   │
│  • 12:30 PM – 1:00 PM  Lunch w/ Jo │
│  • 3:00 PM – 3:30 PM   Dentist     │
│                                     │
│  TASKS                              │
│  Overdue:                           │
│  • File taxes (Personal, due Mar 20)│
│  Today:                             │
│  • Buy groceries (Shopping)         │
│  • Review PR #42 (Work)             │
│                                     │
│  ─────────────────────────────────  │
│                                     │
│  SARAH'S SCHEDULE                   │
│  • 8:00 AM – 9:00 AM   Yoga        │
│  • 2:00 PM – 3:00 PM   Book club   │
└─────────────────────────────────────┘
```

- **Meal planning section** appears first. Shows the event title from the meal planning calendar as a simple line (no time, no bullet — it's always an all-day event). Heading is configurable via `meal_planning_section_label`.
- **Color coding** — each event and task has a colored dot (or left-border accent) using the color assigned in Google Calendar or Todoist. Colors are fetched from the APIs at send time, not configured manually. This matches the visual coding users already see in their apps.
- Calendar label shown in parentheses when multiple calendars contribute to a section.
- Overdue tasks visually distinguished.
- Wife's section uses the configurable `wife_section_label`.
- Empty sections are omitted entirely.

### Sending

- Uses `azure.communication.email` SDK.
- Connection string loaded from Key Vault.
- Sends to `recipient_email` from config, from `sender_email` in config.

## Scheduler (`scheduler.py`)

- APScheduler 3.x with a `CronTrigger`.
- Configured from `send_time` and `timezone` in config.
- Single job: fetch all data → compose email → send.
- Starts on FastAPI lifespan startup, shuts down on lifespan shutdown.

### Error handling

If the send job fails (API down, token expired, etc.), the error is logged but the app does not crash. No retry logic for MVP — a failed send means that day is missed. Retries can be added later if needed.

### Execution model

The scheduler job runs in APScheduler's default thread pool (not on the async event loop). This is appropriate because `google-api-python-client` is synchronous. The Todoist calls use `httpx` synchronously in this context as well. FastAPI's async routes (health, OAuth, send) run on the event loop as usual.

## FastAPI App (`main.py`)

```
FastAPI app
├── lifespan
│   ├── on startup: load config, init Key Vault client, start scheduler
│   └── on shutdown: stop scheduler
├── GET  /health                          — {"status": "ok"}
├── GET  /auth/google/start/{account_name} — Start Google OAuth flow
├── GET  /auth/google/callback            — Complete Google OAuth flow
└── POST /send                            — Manually trigger email send
```

- `POST /send` allows on-demand triggering for testing without waiting for the scheduler. Protected by a shared secret: the request must include an `X-Send-Token` header matching a value stored in Key Vault (`send-endpoint-token`). This prevents unauthorized triggers in production.
- Health check is simple — does not validate external dependencies.

## Dependencies

| Package | Purpose |
|---|---|
| `fastapi` | Web framework (existing) |
| `uvicorn[standard]` | ASGI server (existing) |
| `apscheduler` | In-process cron scheduler |
| `google-auth-oauthlib` | Google OAuth flow |
| `google-api-python-client` | Google Calendar API client |
| `azure-identity` | Managed Identity / DefaultAzureCredential |
| `azure-keyvault-secrets` | Key Vault secret access |
| `azure-communication-email` | Email sending via Azure Communication Services |
| `httpx` | HTTP client for Todoist API (move from dev to main deps) |
| `pyyaml` | Parse config.yaml |
| `jinja2` | HTML email templating |
| `pydantic` | Config validation (bundled with FastAPI) |

## Configuration deployment

In production, `config.yaml` is mounted into the container as a read-only file. Azure App Service supports path mappings from Azure Files or Blob Storage — the config file is stored there and mounted at `/app/config.yaml`. The `CONFIG_PATH` environment variable (defaulting to `config.yaml`) tells the app where to find it. This keeps config out of the image and editable without redeployment.

## Logging

Uses Python's standard `logging` module. Structured logging (JSON) or Azure Monitor / Application Insights integration is deferred — plain text logs to stdout are sufficient for MVP and are captured by Azure App Service's built-in log streaming.

## Bootstrap sequence

On first deployment, the scheduler job will fail because no Google tokens exist yet. This is expected. The bootstrap sequence is:

1. Deploy the app and set `KEY_VAULT_URL`
2. Populate Key Vault with `google-oauth-client`, `todoist-api-token`, `azure-comms-connection-string`, and `send-endpoint-token`
3. Visit `/auth/google/start/{account_name}` for each Google account to authorize and store tokens
4. Use `POST /send` to verify the email works
5. The scheduler takes over from there

At startup, the app logs a warning for any Google account that has no token in Key Vault.

## Local development

- `az login` provides credentials for Key Vault access via `DefaultAzureCredential`.
- `config.yaml` at project root with real calendar IDs and settings.
- `KEY_VAULT_URL` set in `.env` (documented in `.env.example`).
- `POST /send` for manual testing.
- OAuth flow works locally via `http://localhost:8000/auth/google/start/{account_name}`.
