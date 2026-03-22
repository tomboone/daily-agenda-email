# Daily Agenda Email Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a FastAPI app that sends a daily morning email combining Google Calendar events, Todoist tasks, and a spouse's calendar section.

**Architecture:** Modular Python app — each concern (config, secrets, calendar, tasks, email, scheduling) is a focused module under `src/`. External services are accessed through thin wrappers that are easy to mock in tests. APScheduler runs in-process for daily sends.

**Tech Stack:** Python 3.12, FastAPI, APScheduler, Google Calendar API, Todoist REST API v2, Azure Key Vault, Azure Communication Services, Jinja2, Pydantic, httpx

**Spec:** `docs/superpowers/specs/2026-03-22-daily-agenda-email-design.md`

---

## File Structure

```
src/
  __init__.py              (existing, empty)
  main.py                  (modify — lifespan, routes, wiring)
  config.py                (create — Pydantic models, YAML loading)
  secrets.py               (create — Key Vault wrapper)
  google_auth.py           (create — OAuth flow, token management)
  google_calendar.py       (create — fetch & filter calendar events)
  todoist.py               (create — fetch & filter tasks, color mapping)
  email.py                 (create — compose HTML, send via Azure)
  scheduler.py             (create — APScheduler cron job)
  templates/
    agenda.html            (create — Jinja2 email template)

tests/
  __init__.py              (existing, empty)
  conftest.py              (create — shared fixtures)
  test_config.py           (create)
  test_secrets.py          (create)
  test_google_calendar.py  (create)
  test_todoist.py          (create)
  test_email.py            (create)
  test_google_auth.py      (create)
  test_scheduler.py        (create)
  test_main.py             (create)

config.yaml                (create, gitignored — example only in tests)
.env.example               (modify — add KEY_VAULT_URL)
.gitignore                 (modify — add config.yaml)
pyproject.toml             (modify — add dependencies)
Dockerfile                 (modify — copy templates dir)
compose.yaml               (modify — mount config.yaml)
```

---

### Task 1: Project Setup

**Files:**
- Modify: `pyproject.toml`
- Modify: `.gitignore`
- Modify: `.env.example`

- [ ] **Step 1: Add production dependencies to pyproject.toml**

```toml
dependencies = [
    "fastapi",
    "uvicorn[standard]",
    "apscheduler>=3.10,<4",
    "google-auth-oauthlib",
    "google-api-python-client",
    "azure-identity",
    "azure-keyvault-secrets",
    "azure-communication-email",
    "httpx",
    "pyyaml",
    "jinja2",
]
```

Note: `httpx` moved from dev to main deps. `pydantic` is already bundled with FastAPI.

- [ ] **Step 2: Add pytest-asyncio to dev dependencies**

```toml
[dependency-groups]
dev = [
    "pytest",
    "pytest-asyncio",
    "pytest-watch",
    "httpx",
    "ruff",
    "pyright",
    "pre-commit",
]
```

- [ ] **Step 3: Add asyncio_mode to pytest config**

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
```

- [ ] **Step 4: Update .gitignore — add config.yaml**

Add to the `# Environment` section:

```
# Configuration (contains calendar IDs, email addresses)
config.yaml
```

- [ ] **Step 5: Update .env.example**

Replace contents with:

```
# Copy to .env and fill in values
KEY_VAULT_URL=https://your-vault-name.vault.azure.net/
# CONFIG_PATH=config.yaml  # optional, defaults to config.yaml
```

- [ ] **Step 6: Run uv sync**

Run: `uv sync --dev`
Expected: all new packages install successfully

- [ ] **Step 7: Verify lint and typecheck still pass**

Run: `task check`
Expected: PASS (lint, typecheck, test — tests are empty so they pass trivially)

- [ ] **Step 8: Commit**

```bash
git add pyproject.toml uv.lock .gitignore .env.example
git commit -m "chore: add project dependencies and update config"
```

---

### Task 2: Configuration Module

**Files:**
- Create: `src/config.py`
- Create: `tests/conftest.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: Write failing tests for config models**

Create `tests/test_config.py`:

```python
import pytest
from pathlib import Path
from src.config import (
    AppConfig,
    CalendarConfig,
    CalendarSection,
    GoogleAccountConfig,
    TodoistConfig,
    TodoistFilters,
    CalendarFilters,
    load_config,
)


def test_valid_config_parses(tmp_path: Path) -> None:
    config_file = tmp_path / "config.yaml"
    config_file.write_text("""
send_time: "06:00"
timezone: "America/New_York"
recipient_email: "test@example.com"
sender_email: "noreply@example.com"
google_accounts:
  - name: "personal"
    calendars:
      - id: "primary"
        label: "Personal"
        section: "self"
        filters:
          exclude_titles: []
todoist:
  filters:
    exclude_projects: []
    exclude_titles: []
meal_planning_section_label: "Dinner"
wife_section_label: "Her Schedule"
""")
    config = load_config(str(config_file))
    assert config.send_time == "06:00"
    assert config.timezone == "America/New_York"
    assert config.recipient_email == "test@example.com"
    assert len(config.google_accounts) == 1
    assert config.google_accounts[0].name == "personal"
    assert config.google_accounts[0].calendars[0].section == CalendarSection.SELF


def test_invalid_section_raises(tmp_path: Path) -> None:
    config_file = tmp_path / "config.yaml"
    config_file.write_text("""
send_time: "06:00"
timezone: "America/New_York"
recipient_email: "test@example.com"
sender_email: "noreply@example.com"
google_accounts:
  - name: "personal"
    calendars:
      - id: "primary"
        label: "Personal"
        section: "invalid_value"
        filters:
          exclude_titles: []
todoist:
  filters:
    exclude_projects: []
    exclude_titles: []
meal_planning_section_label: "Dinner"
wife_section_label: "Her Schedule"
""")
    with pytest.raises(Exception):
        load_config(str(config_file))


def test_missing_required_field_raises(tmp_path: Path) -> None:
    config_file = tmp_path / "config.yaml"
    config_file.write_text("""
send_time: "06:00"
""")
    with pytest.raises(Exception):
        load_config(str(config_file))


def test_multiple_accounts_and_calendars(tmp_path: Path) -> None:
    config_file = tmp_path / "config.yaml"
    config_file.write_text("""
send_time: "07:30"
timezone: "US/Eastern"
recipient_email: "user@example.com"
sender_email: "noreply@example.com"
google_accounts:
  - name: "personal"
    calendars:
      - id: "primary"
        label: "Personal"
        section: "self"
        filters:
          exclude_titles: ["standup"]
      - id: "meal@group.calendar.google.com"
        label: "Meal Planning"
        section: "meal_planning"
        filters:
          exclude_titles: ["Meal Planning"]
      - id: "wife@group.calendar.google.com"
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
""")
    config = load_config(str(config_file))
    assert len(config.google_accounts) == 2
    assert len(config.google_accounts[0].calendars) == 3
    assert config.google_accounts[0].calendars[1].section == CalendarSection.MEAL_PLANNING
    assert config.todoist.filters.exclude_projects == ["Dog"]
    assert config.meal_planning_section_label == "Dinner"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_config.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.config'`

- [ ] **Step 3: Implement config.py**

Create `src/config.py`:

```python
import enum
from pathlib import Path

import yaml
from pydantic import BaseModel


class CalendarSection(str, enum.Enum):
    SELF = "self"
    WIFE = "wife"
    MEAL_PLANNING = "meal_planning"


class CalendarFilters(BaseModel):
    exclude_titles: list[str] = []


class CalendarConfig(BaseModel):
    id: str
    label: str
    section: CalendarSection
    filters: CalendarFilters = CalendarFilters()


class GoogleAccountConfig(BaseModel):
    name: str
    calendars: list[CalendarConfig]


class TodoistFilters(BaseModel):
    exclude_projects: list[str] = []
    exclude_titles: list[str] = []


class TodoistConfig(BaseModel):
    filters: TodoistFilters = TodoistFilters()


class AppConfig(BaseModel):
    send_time: str
    timezone: str
    recipient_email: str
    sender_email: str
    google_accounts: list[GoogleAccountConfig]
    todoist: TodoistConfig
    meal_planning_section_label: str = "Dinner"
    wife_section_label: str = "Her Schedule"


def load_config(path: str) -> AppConfig:
    """Load and validate config from a YAML file."""
    text = Path(path).read_text()
    data = yaml.safe_load(text)
    return AppConfig.model_validate(data)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_config.py -v`
Expected: All 4 tests PASS

- [ ] **Step 5: Run full checks**

Run: `task check`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/config.py tests/test_config.py
git commit -m "feat: add configuration module with Pydantic validation"
```

---

### Task 3: Secrets Module

**Files:**
- Create: `src/secrets.py`
- Create: `tests/test_secrets.py`

- [ ] **Step 1: Write failing tests for secrets module**

Create `tests/test_secrets.py`:

```python
from unittest.mock import MagicMock, patch

from src.secrets import SecretsClient


@patch("src.secrets.SecretClient")
@patch("src.secrets.DefaultAzureCredential")
def test_get_secret(mock_cred_cls: MagicMock, mock_client_cls: MagicMock) -> None:
    mock_client = MagicMock()
    mock_client.get_secret.return_value = MagicMock(value="my-secret-value")
    mock_client_cls.return_value = mock_client

    client = SecretsClient("https://my-vault.vault.azure.net/")
    result = client.get_secret("test-secret")

    assert result == "my-secret-value"
    mock_client.get_secret.assert_called_once_with("test-secret")


@patch("src.secrets.SecretClient")
@patch("src.secrets.DefaultAzureCredential")
def test_set_secret(mock_cred_cls: MagicMock, mock_client_cls: MagicMock) -> None:
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client

    client = SecretsClient("https://my-vault.vault.azure.net/")
    client.set_secret("test-secret", "new-value")

    mock_client.set_secret.assert_called_once_with("test-secret", "new-value")


@patch("src.secrets.SecretClient")
@patch("src.secrets.DefaultAzureCredential")
def test_get_secret_returns_none_when_not_found(
    mock_cred_cls: MagicMock, mock_client_cls: MagicMock
) -> None:
    from azure.core.exceptions import ResourceNotFoundError

    mock_client = MagicMock()
    mock_client.get_secret.side_effect = ResourceNotFoundError("not found")
    mock_client_cls.return_value = mock_client

    client = SecretsClient("https://my-vault.vault.azure.net/")
    result = client.get_secret_or_none("test-secret")

    assert result is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_secrets.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.secrets'`

- [ ] **Step 3: Implement secrets.py**

Create `src/secrets.py`:

```python
import logging

from azure.core.exceptions import ResourceNotFoundError
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient

logger = logging.getLogger(__name__)


class SecretsClient:
    def __init__(self, vault_url: str) -> None:
        credential = DefaultAzureCredential()
        self._client = SecretClient(vault_url=vault_url, credential=credential)

    def get_secret(self, name: str) -> str:
        """Get a secret value. Raises if not found."""
        return self._client.get_secret(name).value  # type: ignore[return-value]

    def get_secret_or_none(self, name: str) -> str | None:
        """Get a secret value, returning None if not found."""
        try:
            return self._client.get_secret(name).value
        except ResourceNotFoundError:
            logger.warning("Secret '%s' not found in Key Vault", name)
            return None

    def set_secret(self, name: str, value: str) -> None:
        """Create or update a secret."""
        self._client.set_secret(name, value)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_secrets.py -v`
Expected: All 3 tests PASS

- [ ] **Step 5: Run full checks**

Run: `task check`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/secrets.py tests/test_secrets.py
git commit -m "feat: add Azure Key Vault secrets wrapper"
```

---

### Task 4: Google Calendar Module

**Files:**
- Create: `src/google_calendar.py`
- Create: `tests/test_google_calendar.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: Write shared test fixtures in conftest.py**

Create `tests/conftest.py`:

```python
import pytest

from src.config import (
    AppConfig,
    CalendarConfig,
    CalendarFilters,
    CalendarSection,
    GoogleAccountConfig,
    TodoistConfig,
    TodoistFilters,
)


@pytest.fixture
def sample_config() -> AppConfig:
    return AppConfig(
        send_time="06:00",
        timezone="America/New_York",
        recipient_email="test@example.com",
        sender_email="noreply@example.com",
        google_accounts=[
            GoogleAccountConfig(
                name="personal",
                calendars=[
                    CalendarConfig(
                        id="primary",
                        label="Personal",
                        section=CalendarSection.SELF,
                        filters=CalendarFilters(exclude_titles=[]),
                    ),
                    CalendarConfig(
                        id="meal@group.calendar.google.com",
                        label="Meal Planning",
                        section=CalendarSection.MEAL_PLANNING,
                        filters=CalendarFilters(exclude_titles=["Meal Planning"]),
                    ),
                    CalendarConfig(
                        id="family@group.calendar.google.com",
                        label="Family",
                        section=CalendarSection.SELF,
                        filters=CalendarFilters(
                            exclude_titles=["tv off", "bed", "lights out"]
                        ),
                    ),
                    CalendarConfig(
                        id="wife@group.calendar.google.com",
                        label="Wife",
                        section=CalendarSection.WIFE,
                        filters=CalendarFilters(exclude_titles=[]),
                    ),
                ],
            ),
            GoogleAccountConfig(
                name="work",
                calendars=[
                    CalendarConfig(
                        id="primary",
                        label="Work",
                        section=CalendarSection.SELF,
                        filters=CalendarFilters(exclude_titles=[]),
                    ),
                ],
            ),
        ],
        todoist=TodoistConfig(
            filters=TodoistFilters(
                exclude_projects=["Dog"],
                exclude_titles=["Outside"],
            ),
        ),
        meal_planning_section_label="Dinner",
        wife_section_label="Sarah's Schedule",
    )
```

- [ ] **Step 2: Write failing tests for Google Calendar module**

Create `tests/test_google_calendar.py`:

```python
from datetime import datetime, date
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

import pytest

from src.config import (
    CalendarConfig,
    CalendarFilters,
    CalendarSection,
    GoogleAccountConfig,
)
from src.google_calendar import (
    CalendarEvent,
    fetch_events_for_account,
    filter_events,
)


def _make_timed_event(summary: str, hour: int) -> dict:
    """Helper: create a Google Calendar API timed event dict."""
    return {
        "summary": summary,
        "start": {"dateTime": f"2026-03-22T{hour:02d}:00:00-04:00"},
        "end": {"dateTime": f"2026-03-22T{hour + 1:02d}:00:00-04:00"},
    }


def _make_all_day_event(summary: str) -> dict:
    """Helper: create a Google Calendar API all-day event dict."""
    return {
        "summary": summary,
        "start": {"date": "2026-03-22"},
        "end": {"date": "2026-03-23"},
    }


class TestFilterEvents:
    def test_excludes_exact_title_case_insensitive(self) -> None:
        events = [
            CalendarEvent(
                title="TV Off",
                start_time=None,
                end_time=None,
                is_all_day=True,
                calendar_label="Family",
                calendar_color="#4285f4",
                section=CalendarSection.SELF,
            ),
            CalendarEvent(
                title="Dentist",
                start_time=datetime(2026, 3, 22, 15, 0, tzinfo=ZoneInfo("America/New_York")),
                end_time=datetime(2026, 3, 22, 15, 30, tzinfo=ZoneInfo("America/New_York")),
                is_all_day=False,
                calendar_label="Personal",
                calendar_color="#4285f4",
                section=CalendarSection.SELF,
            ),
        ]
        exclude_titles = ["tv off"]
        result = filter_events(events, exclude_titles)
        assert len(result) == 1
        assert result[0].title == "Dentist"

    def test_no_filter_keeps_all(self) -> None:
        events = [
            CalendarEvent(
                title="Meeting",
                start_time=datetime(2026, 3, 22, 9, 0, tzinfo=ZoneInfo("America/New_York")),
                end_time=datetime(2026, 3, 22, 10, 0, tzinfo=ZoneInfo("America/New_York")),
                is_all_day=False,
                calendar_label="Work",
                calendar_color="#4285f4",
                section=CalendarSection.SELF,
            ),
        ]
        result = filter_events(events, [])
        assert len(result) == 1

    def test_exact_match_not_substring(self) -> None:
        events = [
            CalendarEvent(
                title="Bedtime routine",
                start_time=None,
                end_time=None,
                is_all_day=True,
                calendar_label="Family",
                calendar_color="#4285f4",
                section=CalendarSection.SELF,
            ),
        ]
        result = filter_events(events, ["bed"])
        assert len(result) == 1  # "Bedtime routine" != "bed"


class TestFetchEventsForAccount:
    @patch("src.google_calendar.build")
    def test_fetches_and_parses_events(self, mock_build: MagicMock) -> None:
        mock_service = MagicMock()
        mock_build.return_value = mock_service

        # Mock calendarList to return colors
        mock_service.calendarList().list().execute.return_value = {
            "items": [
                {"id": "primary", "backgroundColor": "#4285f4"},
                {"id": "family@group.calendar.google.com", "backgroundColor": "#0b8043"},
            ]
        }

        # Mock events().list() for "primary" calendar
        mock_events_list = MagicMock()
        mock_service.events().list.return_value = mock_events_list
        mock_events_list.execute.return_value = {
            "items": [
                _make_timed_event("Team sync", 9),
                _make_all_day_event("Spring begins"),
            ]
        }

        account = GoogleAccountConfig(
            name="personal",
            calendars=[
                CalendarConfig(
                    id="primary",
                    label="Personal",
                    section=CalendarSection.SELF,
                    filters=CalendarFilters(exclude_titles=[]),
                ),
            ],
        )

        tz = ZoneInfo("America/New_York")
        today = date(2026, 3, 22)
        creds = MagicMock()

        events = fetch_events_for_account(account, creds, today, tz)

        assert len(events) == 2
        all_day = [e for e in events if e.is_all_day]
        timed = [e for e in events if not e.is_all_day]
        assert len(all_day) == 1
        assert all_day[0].title == "Spring begins"
        assert len(timed) == 1
        assert timed[0].title == "Team sync"

    @patch("src.google_calendar.build")
    def test_filters_are_applied(self, mock_build: MagicMock) -> None:
        mock_service = MagicMock()
        mock_build.return_value = mock_service

        mock_service.calendarList().list().execute.return_value = {
            "items": [{"id": "family@group.calendar.google.com", "backgroundColor": "#0b8043"}]
        }

        mock_events_list = MagicMock()
        mock_service.events().list.return_value = mock_events_list
        mock_events_list.execute.return_value = {
            "items": [
                _make_all_day_event("tv off"),
                _make_all_day_event("bed"),
                _make_timed_event("Dentist", 15),
            ]
        }

        account = GoogleAccountConfig(
            name="personal",
            calendars=[
                CalendarConfig(
                    id="family@group.calendar.google.com",
                    label="Family",
                    section=CalendarSection.SELF,
                    filters=CalendarFilters(exclude_titles=["tv off", "bed"]),
                ),
            ],
        )

        tz = ZoneInfo("America/New_York")
        today = date(2026, 3, 22)
        creds = MagicMock()

        events = fetch_events_for_account(account, creds, today, tz)
        assert len(events) == 1
        assert events[0].title == "Dentist"


class TestEventSorting:
    def test_all_day_events_sort_before_timed(self) -> None:
        tz = ZoneInfo("America/New_York")
        events = [
            CalendarEvent(
                title="Meeting",
                start_time=datetime(2026, 3, 22, 9, 0, tzinfo=tz),
                end_time=datetime(2026, 3, 22, 10, 0, tzinfo=tz),
                is_all_day=False,
                calendar_label="Work",
                calendar_color="#4285f4",
                section=CalendarSection.SELF,
            ),
            CalendarEvent(
                title="All day",
                start_time=None,
                end_time=None,
                is_all_day=True,
                calendar_label="Personal",
                calendar_color="#0b8043",
                section=CalendarSection.SELF,
            ),
        ]
        sorted_events = sorted(events, key=lambda e: (not e.is_all_day, e.start_time or datetime.min.replace(tzinfo=tz)))
        assert sorted_events[0].title == "All day"
        assert sorted_events[1].title == "Meeting"
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/test_google_calendar.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.google_calendar'`

- [ ] **Step 4: Implement google_calendar.py**

Create `src/google_calendar.py`:

```python
import logging
from dataclasses import dataclass
from datetime import date, datetime
from zoneinfo import ZoneInfo

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from src.config import CalendarSection, GoogleAccountConfig

logger = logging.getLogger(__name__)


@dataclass
class CalendarEvent:
    title: str
    start_time: datetime | None  # None for all-day events
    end_time: datetime | None
    is_all_day: bool
    calendar_label: str
    calendar_color: str
    section: CalendarSection


def filter_events(events: list[CalendarEvent], exclude_titles: list[str]) -> list[CalendarEvent]:
    """Filter events by exact title match (case-insensitive)."""
    exclude_lower = {t.lower() for t in exclude_titles}
    return [e for e in events if e.title.lower() not in exclude_lower]


def sort_events(events: list[CalendarEvent], tz: ZoneInfo) -> list[CalendarEvent]:
    """Sort events: all-day first, then by start time."""
    return sorted(
        events,
        key=lambda e: (not e.is_all_day, e.start_time or datetime.min.replace(tzinfo=tz)),
    )


def _parse_event(
    raw: dict,
    calendar_label: str,
    calendar_color: str,
    section: CalendarSection,
    tz: ZoneInfo,
) -> CalendarEvent:
    """Parse a raw Google Calendar API event into a CalendarEvent."""
    start = raw.get("start", {})
    end = raw.get("end", {})
    is_all_day = "date" in start and "dateTime" not in start

    start_time = None
    end_time = None
    if not is_all_day:
        start_time = datetime.fromisoformat(start["dateTime"]).astimezone(tz)
        end_time = datetime.fromisoformat(end["dateTime"]).astimezone(tz)

    return CalendarEvent(
        title=raw.get("summary", "(No title)"),
        start_time=start_time,
        end_time=end_time,
        is_all_day=is_all_day,
        calendar_label=calendar_label,
        calendar_color=calendar_color,
        section=section,
    )


def _get_calendar_colors(service: object) -> dict[str, str]:
    """Fetch calendar colors from the calendarList API."""
    result = service.calendarList().list().execute()  # type: ignore[union-attr]
    return {
        item["id"]: item.get("backgroundColor", "#4285f4")
        for item in result.get("items", [])
    }


def fetch_events_for_account(
    account: GoogleAccountConfig,
    credentials: Credentials,
    today: date,
    tz: ZoneInfo,
) -> list[CalendarEvent]:
    """Fetch and filter today's events for all calendars in an account."""
    service = build("calendar", "v3", credentials=credentials)
    colors = _get_calendar_colors(service)

    time_min = datetime.combine(today, datetime.min.time(), tzinfo=tz).isoformat()
    time_max = datetime.combine(today, datetime.max.time(), tzinfo=tz).isoformat()

    all_events: list[CalendarEvent] = []

    for cal in account.calendars:
        color = colors.get(cal.id, "#4285f4")
        try:
            result = (
                service.events()
                .list(
                    calendarId=cal.id,
                    timeMin=time_min,
                    timeMax=time_max,
                    singleEvents=True,
                    orderBy="startTime",
                )
                .execute()
            )
        except Exception:
            logger.exception("Failed to fetch events for calendar %s", cal.id)
            continue

        events = [
            _parse_event(raw, cal.label, color, cal.section, tz)
            for raw in result.get("items", [])
        ]
        events = filter_events(events, cal.filters.exclude_titles)
        all_events.extend(events)

    return sort_events(all_events, tz)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_google_calendar.py -v`
Expected: All tests PASS

- [ ] **Step 6: Run full checks**

Run: `task check`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add src/google_calendar.py tests/test_google_calendar.py tests/conftest.py
git commit -m "feat: add Google Calendar module with event fetching and filtering"
```

---

### Task 5: Todoist Module

**Files:**
- Create: `src/todoist.py`
- Create: `tests/test_todoist.py`

- [ ] **Step 1: Write failing tests for Todoist module**

Create `tests/test_todoist.py`:

```python
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.config import TodoistFilters
from src.todoist import (
    TODOIST_COLOR_MAP,
    TodoistTask,
    fetch_tasks,
    filter_tasks,
    todoist_color_to_hex,
)


class TestTodoistColorMap:
    def test_known_color(self) -> None:
        assert todoist_color_to_hex("berry_red") == "#b8256f"

    def test_unknown_color_returns_default(self) -> None:
        assert todoist_color_to_hex("nonexistent") == "#808080"


class TestFilterTasks:
    def test_excludes_by_project_name(self) -> None:
        tasks = [
            TodoistTask(
                title="Walk the dog",
                project_name="Dog",
                project_color="#b8256f",
                due_date=date(2026, 3, 22),
                is_overdue=False,
            ),
            TodoistTask(
                title="Buy groceries",
                project_name="Shopping",
                project_color="#4073ff",
                due_date=date(2026, 3, 22),
                is_overdue=False,
            ),
        ]
        filters = TodoistFilters(exclude_projects=["Dog"], exclude_titles=[])
        result = filter_tasks(tasks, filters)
        assert len(result) == 1
        assert result[0].title == "Buy groceries"

    def test_excludes_by_title_exact_match(self) -> None:
        tasks = [
            TodoistTask(
                title="Outside",
                project_name="Dog",
                project_color="#b8256f",
                due_date=date(2026, 3, 22),
                is_overdue=False,
            ),
            TodoistTask(
                title="Outside play time",
                project_name="Dog",
                project_color="#b8256f",
                due_date=date(2026, 3, 22),
                is_overdue=False,
            ),
        ]
        filters = TodoistFilters(exclude_projects=[], exclude_titles=["Outside"])
        result = filter_tasks(tasks, filters)
        assert len(result) == 1
        assert result[0].title == "Outside play time"

    def test_case_insensitive(self) -> None:
        tasks = [
            TodoistTask(
                title="outside",
                project_name="Dog",
                project_color="#b8256f",
                due_date=date(2026, 3, 22),
                is_overdue=False,
            ),
        ]
        filters = TodoistFilters(exclude_projects=[], exclude_titles=["Outside"])
        result = filter_tasks(tasks, filters)
        assert len(result) == 0


class TestSortTasks:
    def test_overdue_sorted_before_today(self) -> None:
        tasks = [
            TodoistTask(
                title="Today task",
                project_name="Work",
                project_color="#4073ff",
                due_date=date(2026, 3, 22),
                is_overdue=False,
            ),
            TodoistTask(
                title="Old task",
                project_name="Work",
                project_color="#4073ff",
                due_date=date(2026, 3, 20),
                is_overdue=True,
            ),
        ]
        sorted_tasks = sorted(tasks, key=lambda t: (not t.is_overdue, t.due_date))
        assert sorted_tasks[0].title == "Old task"
        assert sorted_tasks[1].title == "Today task"


class TestFetchTasks:
    @patch("src.todoist.httpx.Client")
    def test_fetches_and_parses_tasks(self, mock_client_cls: MagicMock) -> None:
        mock_client = MagicMock()
        mock_client_cls.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)

        # Mock projects response
        projects_response = MagicMock()
        projects_response.json.return_value = [
            {"id": "1001", "name": "Shopping", "color": "blue"},
            {"id": "1002", "name": "Dog", "color": "berry_red"},
        ]
        projects_response.raise_for_status = MagicMock()

        # Mock tasks response
        tasks_response = MagicMock()
        tasks_response.json.return_value = [
            {
                "id": "2001",
                "content": "Buy groceries",
                "project_id": "1001",
                "due": {"date": "2026-03-22"},
            },
            {
                "id": "2002",
                "content": "Walk the dog",
                "project_id": "1002",
                "due": {"date": "2026-03-22"},
            },
            {
                "id": "2003",
                "content": "No due date task",
                "project_id": "1001",
                "due": None,
            },
        ]
        tasks_response.raise_for_status = MagicMock()

        mock_client.get.side_effect = [projects_response, tasks_response]

        filters = TodoistFilters(exclude_projects=["Dog"], exclude_titles=[])
        today = date(2026, 3, 22)

        result = fetch_tasks("fake-api-token", filters, today)

        assert len(result) == 1
        assert result[0].title == "Buy groceries"
        assert result[0].project_color == "#4073ff"  # blue
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_todoist.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.todoist'`

- [ ] **Step 3: Implement todoist.py**

Create `src/todoist.py`:

```python
import logging
from dataclasses import dataclass
from datetime import date

import httpx

from src.config import TodoistFilters

logger = logging.getLogger(__name__)

TODOIST_API_BASE = "https://api.todoist.com/rest/v2"

TODOIST_COLOR_MAP: dict[str, str] = {
    "berry_red": "#b8256f",
    "red": "#db4035",
    "orange": "#ff9933",
    "yellow": "#fad000",
    "olive_green": "#afb83b",
    "lime_green": "#7ecc49",
    "green": "#299438",
    "mint_green": "#6accbc",
    "teal": "#158fad",
    "sky_blue": "#14aaf5",
    "light_blue": "#96c3eb",
    "blue": "#4073ff",
    "grape": "#884dff",
    "violet": "#af38eb",
    "lavender": "#eb96eb",
    "magenta": "#e05194",
    "salmon": "#ff8d85",
    "charcoal": "#808080",
    "grey": "#b8b8b8",
    "taupe": "#ccac93",
}


def todoist_color_to_hex(color_name: str) -> str:
    """Convert a Todoist color name to a hex color string."""
    return TODOIST_COLOR_MAP.get(color_name, "#808080")


@dataclass
class TodoistTask:
    title: str
    project_name: str
    project_color: str  # hex
    due_date: date
    is_overdue: bool


def filter_tasks(tasks: list[TodoistTask], filters: TodoistFilters) -> list[TodoistTask]:
    """Filter tasks by project name and title (exact match, case-insensitive)."""
    exclude_projects = {p.lower() for p in filters.exclude_projects}
    exclude_titles = {t.lower() for t in filters.exclude_titles}
    return [
        t
        for t in tasks
        if t.project_name.lower() not in exclude_projects
        and t.title.lower() not in exclude_titles
    ]


def sort_tasks(tasks: list[TodoistTask]) -> list[TodoistTask]:
    """Sort tasks: overdue first (oldest to newest), then today's tasks."""
    return sorted(tasks, key=lambda t: (not t.is_overdue, t.due_date))


def fetch_tasks(api_token: str, filters: TodoistFilters, today: date) -> list[TodoistTask]:
    """Fetch today's and overdue tasks from Todoist, filtered and sorted."""
    headers = {"Authorization": f"Bearer {api_token}"}

    with httpx.Client(base_url=TODOIST_API_BASE, headers=headers) as client:
        # Fetch projects for name/color mapping
        projects_resp = client.get("/projects")
        projects_resp.raise_for_status()
        projects_by_id: dict[str, dict] = {
            p["id"]: p for p in projects_resp.json()
        }

        # Fetch all active tasks
        tasks_resp = client.get("/tasks")
        tasks_resp.raise_for_status()

        tasks: list[TodoistTask] = []
        for raw in tasks_resp.json():
            due = raw.get("due")
            if due is None:
                continue
            due_date = date.fromisoformat(due["date"][:10])
            if due_date > today:
                continue

            project = projects_by_id.get(raw["project_id"], {})
            project_name = project.get("name", "Unknown")
            project_color = todoist_color_to_hex(project.get("color", "charcoal"))

            tasks.append(
                TodoistTask(
                    title=raw["content"],
                    project_name=project_name,
                    project_color=project_color,
                    due_date=due_date,
                    is_overdue=due_date < today,
                )
            )

        tasks = filter_tasks(tasks, filters)
        return sort_tasks(tasks)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_todoist.py -v`
Expected: All tests PASS

- [ ] **Step 5: Run full checks**

Run: `task check`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/todoist.py tests/test_todoist.py
git commit -m "feat: add Todoist module with task fetching, filtering, and color mapping"
```

---

### Task 6: Email Module (Template + Compose + Send)

**Files:**
- Create: `src/templates/agenda.html`
- Create: `src/email.py`
- Create: `tests/test_email.py`

- [ ] **Step 1: Create the Jinja2 email template**

Create directory: `mkdir -p src/templates`

Create `src/templates/agenda.html`:

```html
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;background:#f5f5f5;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#f5f5f5;">
<tr><td align="center" style="padding:20px 10px;">
<table width="600" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:8px;overflow:hidden;">

<!-- Header -->
<tr><td style="background:#1a1a2e;padding:24px 32px;">
  <h1 style="margin:0;color:#ffffff;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;font-size:22px;font-weight:600;">
    {{ date_heading }}
  </h1>
</td></tr>

<tr><td style="padding:24px 32px;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;font-size:14px;color:#333333;">

{% if meal_planning_events %}
<!-- Meal Planning Section -->
<table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:24px;">
  <tr><td style="font-size:11px;font-weight:700;color:#888888;letter-spacing:1px;text-transform:uppercase;padding-bottom:8px;">
    {{ meal_planning_section_label }}
  </td></tr>
  {% for event in meal_planning_events %}
  <tr><td style="font-size:18px;font-weight:600;color:#1a1a2e;padding:4px 0;">
    {{ event.title }}
  </td></tr>
  {% endfor %}
</table>
{% endif %}

{% if self_all_day_events %}
<!-- All-Day Events -->
<table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:24px;">
  <tr><td style="font-size:11px;font-weight:700;color:#888888;letter-spacing:1px;text-transform:uppercase;padding-bottom:8px;">
    All-Day Events
  </td></tr>
  {% for event in self_all_day_events %}
  <tr><td style="padding:4px 0;">
    <span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:{{ event.calendar_color }};margin-right:8px;vertical-align:middle;"></span>
    <span style="vertical-align:middle;">{{ event.title }}{% if show_calendar_labels %} <span style="color:#999999;">({{ event.calendar_label }})</span>{% endif %}</span>
  </td></tr>
  {% endfor %}
</table>
{% endif %}

{% if self_timed_events %}
<!-- Timed Events -->
<table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:24px;">
  <tr><td style="font-size:11px;font-weight:700;color:#888888;letter-spacing:1px;text-transform:uppercase;padding-bottom:8px;">
    Calendar
  </td></tr>
  {% for event in self_timed_events %}
  <tr><td style="padding:6px 0;border-left:3px solid {{ event.calendar_color }};padding-left:12px;">
    <span style="color:#666666;font-size:13px;">{{ event.start_time.strftime('%-I:%M %p') }} – {{ event.end_time.strftime('%-I:%M %p') }}</span><br>
    <span style="font-weight:500;">{{ event.title }}{% if show_calendar_labels %} <span style="color:#999999;">({{ event.calendar_label }})</span>{% endif %}</span>
  </td></tr>
  {% endfor %}
</table>
{% endif %}

{% if overdue_tasks or today_tasks %}
<!-- Tasks -->
<table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:24px;">
  <tr><td style="font-size:11px;font-weight:700;color:#888888;letter-spacing:1px;text-transform:uppercase;padding-bottom:8px;">
    Tasks
  </td></tr>
  {% if overdue_tasks %}
  <tr><td style="font-size:12px;font-weight:600;color:#d32f2f;padding:4px 0 4px 0;">Overdue</td></tr>
  {% for task in overdue_tasks %}
  <tr><td style="padding:4px 0;border-left:3px solid {{ task.project_color }};padding-left:12px;">
    <span style="font-weight:500;">{{ task.title }}</span>
    <span style="color:#999999;font-size:12px;">({{ task.project_name }}, due {{ task.due_date.strftime('%b %-d') }})</span>
  </td></tr>
  {% endfor %}
  {% endif %}
  {% if today_tasks %}
  <tr><td style="font-size:12px;font-weight:600;color:#666666;padding:8px 0 4px 0;">Today</td></tr>
  {% for task in today_tasks %}
  <tr><td style="padding:4px 0;border-left:3px solid {{ task.project_color }};padding-left:12px;">
    <span style="font-weight:500;">{{ task.title }}</span>
    <span style="color:#999999;font-size:12px;">({{ task.project_name }})</span>
  </td></tr>
  {% endfor %}
  {% endif %}
</table>
{% endif %}

{% if wife_all_day_events or wife_timed_events %}
<!-- Wife's Section -->
<table width="100%" cellpadding="0" cellspacing="0" style="border-top:1px solid #eeeeee;padding-top:20px;margin-top:8px;">
  <tr><td style="font-size:11px;font-weight:700;color:#888888;letter-spacing:1px;text-transform:uppercase;padding-bottom:8px;">
    {{ wife_section_label }}
  </td></tr>
  {% for event in wife_all_day_events %}
  <tr><td style="padding:4px 0;">
    <span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:{{ event.calendar_color }};margin-right:8px;vertical-align:middle;"></span>
    <span style="vertical-align:middle;">{{ event.title }}</span>
  </td></tr>
  {% endfor %}
  {% for event in wife_timed_events %}
  <tr><td style="padding:6px 0;border-left:3px solid {{ event.calendar_color }};padding-left:12px;">
    <span style="color:#666666;font-size:13px;">{{ event.start_time.strftime('%-I:%M %p') }} – {{ event.end_time.strftime('%-I:%M %p') }}</span><br>
    <span style="font-weight:500;">{{ event.title }}</span>
  </td></tr>
  {% endfor %}
</table>
{% endif %}

</td></tr>
</table>
</td></tr>
</table>
</body>
</html>
```

- [ ] **Step 2: Write failing tests for email module**

Create `tests/test_email.py`:

```python
from datetime import date, datetime
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

from src.config import CalendarSection
from src.email import compose_email, send_email
from src.google_calendar import CalendarEvent
from src.todoist import TodoistTask


def _make_event(
    title: str,
    hour: int | None = None,
    section: CalendarSection = CalendarSection.SELF,
    label: str = "Personal",
    color: str = "#4285f4",
) -> CalendarEvent:
    tz = ZoneInfo("America/New_York")
    if hour is None:
        return CalendarEvent(
            title=title,
            start_time=None,
            end_time=None,
            is_all_day=True,
            calendar_label=label,
            calendar_color=color,
            section=section,
        )
    return CalendarEvent(
        title=title,
        start_time=datetime(2026, 3, 22, hour, 0, tzinfo=tz),
        end_time=datetime(2026, 3, 22, hour + 1, 0, tzinfo=tz),
        is_all_day=False,
        calendar_label=label,
        calendar_color=color,
        section=section,
    )


def _make_task(
    title: str,
    project: str = "Work",
    color: str = "#4073ff",
    due: date = date(2026, 3, 22),
    overdue: bool = False,
) -> TodoistTask:
    return TodoistTask(
        title=title,
        project_name=project,
        project_color=color,
        due_date=due,
        is_overdue=overdue,
    )


class TestComposeEmail:
    def test_basic_composition(self) -> None:
        events = [
            _make_event("Team sync", 9),
            _make_event("Dentist", 15),
        ]
        tasks = [_make_task("Buy groceries", project="Shopping")]
        today = date(2026, 3, 22)

        subject, html = compose_email(
            events=events,
            tasks=tasks,
            today=today,
            timezone="America/New_York",
            meal_planning_section_label="Dinner",
            wife_section_label="Sarah's Schedule",
        )

        assert "March 22" in subject
        assert "Team sync" in html
        assert "Dentist" in html
        assert "Buy groceries" in html

    def test_meal_planning_section(self) -> None:
        events = [
            _make_event(
                "Chicken Tikka Masala",
                section=CalendarSection.MEAL_PLANNING,
                label="Meal Planning",
            ),
        ]
        today = date(2026, 3, 22)

        subject, html = compose_email(
            events=events,
            tasks=[],
            today=today,
            timezone="America/New_York",
            meal_planning_section_label="Dinner",
            wife_section_label="Sarah's Schedule",
        )

        assert "Dinner" in html
        assert "Chicken Tikka Masala" in html

    def test_wife_section_separate(self) -> None:
        events = [
            _make_event("Yoga", 8, section=CalendarSection.WIFE, label="Wife"),
            _make_event("Meeting", 9, section=CalendarSection.SELF),
        ]
        today = date(2026, 3, 22)

        subject, html = compose_email(
            events=events,
            tasks=[],
            today=today,
            timezone="America/New_York",
            meal_planning_section_label="Dinner",
            wife_section_label="Sarah's Schedule",
        )

        assert "Sarah&#39;s Schedule" in html or "Sarah's Schedule" in html
        assert "Yoga" in html
        assert "Meeting" in html

    def test_empty_sections_omitted(self) -> None:
        today = date(2026, 3, 22)

        subject, html = compose_email(
            events=[],
            tasks=[],
            today=today,
            timezone="America/New_York",
            meal_planning_section_label="Dinner",
            wife_section_label="Sarah's Schedule",
        )

        assert "Dinner" not in html
        assert "Tasks" not in html
        assert "Sarah" not in html

    def test_overdue_tasks_shown(self) -> None:
        tasks = [
            _make_task("Old task", due=date(2026, 3, 20), overdue=True),
            _make_task("Today task"),
        ]
        today = date(2026, 3, 22)

        subject, html = compose_email(
            events=[],
            tasks=tasks,
            today=today,
            timezone="America/New_York",
            meal_planning_section_label="Dinner",
            wife_section_label="Sarah's Schedule",
        )

        assert "Overdue" in html
        assert "Old task" in html
        assert "Mar 20" in html


class TestSendEmail:
    @patch("src.email.EmailClient")
    def test_send_email(self, mock_email_cls: MagicMock) -> None:
        mock_client = MagicMock()
        mock_email_cls.from_connection_string.return_value = mock_client
        mock_poller = MagicMock()
        mock_client.begin_send.return_value = mock_poller
        mock_poller.result.return_value = MagicMock(status="Succeeded")

        send_email(
            connection_string="fake-connection-string",
            sender="noreply@example.com",
            recipient="test@example.com",
            subject="Daily Agenda",
            html_body="<p>Hello</p>",
        )

        mock_client.begin_send.assert_called_once()
        call_args = mock_client.begin_send.call_args[0][0]
        assert call_args["recipients"]["to"][0]["address"] == "test@example.com"
        assert call_args["senderAddress"] == "noreply@example.com"
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/test_email.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.email'`

- [ ] **Step 4: Implement email.py**

Create `src/email.py`:

```python
import logging
from datetime import date
from pathlib import Path

from azure.communication.email import EmailClient
from jinja2 import Environment, FileSystemLoader

from src.config import CalendarSection
from src.google_calendar import CalendarEvent
from src.todoist import TodoistTask

logger = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).parent / "templates"


def compose_email(
    events: list[CalendarEvent],
    tasks: list[TodoistTask],
    today: date,
    timezone: str,
    meal_planning_section_label: str,
    wife_section_label: str,
) -> tuple[str, str]:
    """Compose the email subject and HTML body. Returns (subject, html)."""
    date_heading = today.strftime("%A, %B %-d, %Y")
    subject = f"Daily Agenda — {today.strftime('%A, %B %-d')}"

    # Split events by section
    meal_planning_events = [e for e in events if e.section == CalendarSection.MEAL_PLANNING]
    self_events = [e for e in events if e.section == CalendarSection.SELF]
    wife_events = [e for e in events if e.section == CalendarSection.WIFE]

    self_all_day = [e for e in self_events if e.is_all_day]
    self_timed = [e for e in self_events if not e.is_all_day]
    wife_all_day = [e for e in wife_events if e.is_all_day]
    wife_timed = [e for e in wife_events if not e.is_all_day]

    # Determine if we need calendar labels (multiple calendars in self section)
    self_calendar_labels = {e.calendar_label for e in self_events}
    show_calendar_labels = len(self_calendar_labels) > 1

    # Split tasks
    overdue_tasks = [t for t in tasks if t.is_overdue]
    today_tasks = [t for t in tasks if not t.is_overdue]

    env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)), autoescape=True)
    template = env.get_template("agenda.html")

    html = template.render(
        date_heading=date_heading,
        meal_planning_events=meal_planning_events,
        meal_planning_section_label=meal_planning_section_label,
        self_all_day_events=self_all_day,
        self_timed_events=self_timed,
        show_calendar_labels=show_calendar_labels,
        overdue_tasks=overdue_tasks,
        today_tasks=today_tasks,
        wife_all_day_events=wife_all_day,
        wife_timed_events=wife_timed,
        wife_section_label=wife_section_label,
    )

    return subject, html


def send_email(
    connection_string: str,
    sender: str,
    recipient: str,
    subject: str,
    html_body: str,
) -> None:
    """Send an email via Azure Communication Services."""
    client = EmailClient.from_connection_string(connection_string)
    message = {
        "senderAddress": sender,
        "recipients": {"to": [{"address": recipient}]},
        "content": {"subject": subject, "html": html_body},
    }
    poller = client.begin_send(message)
    result = poller.result()
    logger.info("Email sent, status: %s", result.status)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_email.py -v`
Expected: All tests PASS

- [ ] **Step 6: Run full checks**

Run: `task check`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add src/email.py src/templates/agenda.html tests/test_email.py
git commit -m "feat: add email composition with Jinja2 template and Azure sending"
```

---

### Task 7: Google OAuth Module

**Files:**
- Create: `src/google_auth.py`
- Create: `tests/test_google_auth.py`

- [ ] **Step 1: Write failing tests for OAuth routes**

Create `tests/test_google_auth.py`:

```python
import json
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.google_auth import create_auth_router
from src.secrets import SecretsClient


@pytest.fixture
def mock_secrets() -> MagicMock:
    secrets = MagicMock(spec=SecretsClient)
    secrets.get_secret.return_value = json.dumps(
        {"client_id": "test-client-id", "client_secret": "test-client-secret"}
    )
    return secrets


@pytest.fixture
def app(mock_secrets: MagicMock) -> FastAPI:
    app = FastAPI()
    router = create_auth_router(mock_secrets)
    app.include_router(router)
    return app


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app)


class TestStartAuth:
    @patch("src.google_auth.Flow")
    def test_redirects_to_google(
        self, mock_flow_cls: MagicMock, client: TestClient
    ) -> None:
        mock_flow = MagicMock()
        mock_flow_cls.from_client_config.return_value = mock_flow
        mock_flow.authorization_url.return_value = (
            "https://accounts.google.com/o/oauth2/auth?...",
            "random-state",
        )

        response = client.get(
            "/auth/google/start/personal", follow_redirects=False
        )

        assert response.status_code == 307
        assert "accounts.google.com" in response.headers["location"]


class TestCallback:
    @patch("src.google_auth.Flow")
    def test_stores_token_on_success(
        self, mock_flow_cls: MagicMock, client: TestClient, mock_secrets: MagicMock
    ) -> None:
        mock_flow = MagicMock()
        mock_flow_cls.from_client_config.return_value = mock_flow
        mock_creds = MagicMock()
        mock_creds.token = "access-token"
        mock_creds.refresh_token = "refresh-token"
        mock_creds.expiry = None
        mock_flow.credentials = mock_creds

        response = client.get(
            "/auth/google/callback?code=test-auth-code&state=personal"
        )

        assert response.status_code == 200
        assert "personal" in response.json()["message"]
        mock_secrets.set_secret.assert_called_once()
        call_args = mock_secrets.set_secret.call_args
        assert call_args[0][0] == "google-token-personal"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_google_auth.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.google_auth'`

- [ ] **Step 3: Implement google_auth.py**

Create `src/google_auth.py`:

```python
import json
import logging

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from google_auth_oauthlib.flow import Flow

from src.secrets import SecretsClient

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]


def create_auth_router(secrets: SecretsClient) -> APIRouter:
    """Create the Google OAuth router with the given secrets client."""
    router = APIRouter(prefix="/auth/google")

    def _get_client_config() -> dict:
        raw = secrets.get_secret("google-oauth-client")
        parsed = json.loads(raw)
        return {
            "web": {
                "client_id": parsed["client_id"],
                "client_secret": parsed["client_secret"],
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        }

    @router.get("/start/{account_name}")
    async def start_auth(account_name: str, request: Request) -> RedirectResponse:
        """Redirect to Google's consent screen."""
        redirect_uri = str(request.url_for("auth_callback"))
        client_config = _get_client_config()

        flow = Flow.from_client_config(
            client_config, scopes=SCOPES, redirect_uri=redirect_uri
        )
        auth_url, _ = flow.authorization_url(
            access_type="offline",
            prompt="consent",
            state=account_name,
        )
        return RedirectResponse(url=auth_url)

    @router.get("/callback", name="auth_callback")
    async def auth_callback(code: str, state: str, request: Request) -> dict:
        """Handle the OAuth callback from Google."""
        redirect_uri = str(request.url_for("auth_callback"))
        client_config = _get_client_config()

        flow = Flow.from_client_config(
            client_config, scopes=SCOPES, redirect_uri=redirect_uri
        )
        flow.fetch_token(code=code)

        creds = flow.credentials
        token_data = json.dumps(
            {
                "access_token": creds.token,
                "refresh_token": creds.refresh_token,
                "expiry": creds.expiry.isoformat() if creds.expiry else None,
            }
        )

        secret_name = f"google-token-{state}"
        secrets.set_secret(secret_name, token_data)
        logger.info("Stored OAuth token for account '%s'", state)

        return {"message": f"Successfully authorized account '{state}'"}

    return router
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_google_auth.py -v`
Expected: All tests PASS

- [ ] **Step 5: Run full checks**

Run: `task check`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/google_auth.py tests/test_google_auth.py
git commit -m "feat: add Google OAuth flow with token storage"
```

---

### Task 8: Scheduler Module

**Files:**
- Create: `src/scheduler.py`
- Create: `tests/test_scheduler.py`

- [ ] **Step 1: Write failing tests for scheduler**

Create `tests/test_scheduler.py`:

```python
import json
from datetime import date
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

import pytest

from src.config import AppConfig
from src.scheduler import create_scheduler, send_agenda


class TestSendAgenda:
    @patch("src.scheduler.send_email")
    @patch("src.scheduler.compose_email")
    @patch("src.scheduler.fetch_tasks")
    @patch("src.scheduler.fetch_events_for_account")
    @patch("src.scheduler.Credentials")
    def test_orchestrates_full_send(
        self,
        mock_creds_cls: MagicMock,
        mock_fetch_events: MagicMock,
        mock_fetch_tasks: MagicMock,
        mock_compose: MagicMock,
        mock_send: MagicMock,
        sample_config: AppConfig,
    ) -> None:
        # Setup mocks
        secrets = MagicMock()
        secrets.get_secret.side_effect = lambda name: {
            "google-token-personal": json.dumps(
                {
                    "access_token": "at",
                    "refresh_token": "rt",
                    "expiry": None,
                }
            ),
            "google-token-work": json.dumps(
                {
                    "access_token": "at2",
                    "refresh_token": "rt2",
                    "expiry": None,
                }
            ),
            "google-oauth-client": json.dumps(
                {
                    "client_id": "cid",
                    "client_secret": "csec",
                }
            ),
            "todoist-api-token": "todoist-token",
            "azure-comms-connection-string": "conn-string",
        }[name]

        mock_fetch_events.return_value = []
        mock_fetch_tasks.return_value = []
        mock_compose.return_value = ("Subject", "<html>body</html>")

        send_agenda(sample_config, secrets)

        # Should fetch events for both accounts
        assert mock_fetch_events.call_count == 2
        # Should fetch todoist tasks
        mock_fetch_tasks.assert_called_once()
        # Should compose and send email
        mock_compose.assert_called_once()
        mock_send.assert_called_once()

    @patch("src.scheduler.send_email")
    @patch("src.scheduler.compose_email")
    @patch("src.scheduler.fetch_tasks")
    @patch("src.scheduler.fetch_events_for_account")
    @patch("src.scheduler.Credentials")
    def test_logs_error_on_missing_token(
        self,
        mock_creds_cls: MagicMock,
        mock_fetch_events: MagicMock,
        mock_fetch_tasks: MagicMock,
        mock_compose: MagicMock,
        mock_send: MagicMock,
        sample_config: AppConfig,
    ) -> None:
        secrets = MagicMock()
        secrets.get_secret_or_none.return_value = None
        secrets.get_secret.side_effect = lambda name: {
            "todoist-api-token": "todoist-token",
            "azure-comms-connection-string": "conn-string",
            "google-oauth-client": json.dumps(
                {"client_id": "cid", "client_secret": "csec"}
            ),
        }.get(name, None)

        mock_fetch_tasks.return_value = []
        mock_compose.return_value = ("Subject", "<html></html>")

        # Should not crash — just skip accounts with missing tokens
        send_agenda(sample_config, secrets)
        mock_compose.assert_called_once()


class TestCreateScheduler:
    def test_creates_scheduler_with_cron_trigger(
        self, sample_config: AppConfig
    ) -> None:
        secrets = MagicMock()
        scheduler = create_scheduler(sample_config, secrets)

        jobs = scheduler.get_jobs()
        assert len(jobs) == 1
        assert jobs[0].name == "send_agenda"

        # Don't start the scheduler in tests — just verify it's configured
        scheduler.shutdown(wait=False)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_scheduler.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.scheduler'`

- [ ] **Step 3: Implement scheduler.py**

Create `src/scheduler.py`:

```python
import json
import logging
from datetime import date, datetime
from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from google.oauth2.credentials import Credentials

from src.config import AppConfig
from src.email import compose_email, send_email
from src.google_calendar import fetch_events_for_account, CalendarEvent
from src.secrets import SecretsClient
from src.todoist import fetch_tasks

logger = logging.getLogger(__name__)


def _load_google_credentials(
    account_name: str, secrets: SecretsClient
) -> Credentials | None:
    """Load Google OAuth credentials from Key Vault for an account."""
    token_json = secrets.get_secret_or_none(f"google-token-{account_name}")
    if token_json is None:
        logger.warning("No token found for Google account '%s'", account_name)
        return None

    oauth_json = secrets.get_secret("google-oauth-client")
    oauth = json.loads(oauth_json)
    token = json.loads(token_json)

    return Credentials(
        token=token.get("access_token"),
        refresh_token=token.get("refresh_token"),
        token_uri="https://oauth2.googleapis.com/token",
        client_id=oauth["client_id"],
        client_secret=oauth["client_secret"],
    )


def send_agenda(config: AppConfig, secrets: SecretsClient) -> None:
    """Fetch all data, compose the email, and send it."""
    tz = ZoneInfo(config.timezone)
    today = date.today()

    # Fetch calendar events from all Google accounts
    all_events: list[CalendarEvent] = []
    for account in config.google_accounts:
        creds = _load_google_credentials(account.name, secrets)
        if creds is None:
            continue
        original_token = creds.token
        try:
            events = fetch_events_for_account(account, creds, today, tz)
            all_events.extend(events)

            # Only write back if the token was actually refreshed
            if creds.token != original_token:
                token_data = json.dumps(
                    {
                        "access_token": creds.token,
                        "refresh_token": creds.refresh_token,
                        "expiry": creds.expiry.isoformat() if creds.expiry else None,
                    }
                )
                secrets.set_secret(f"google-token-{account.name}", token_data)
                logger.info("Refreshed token saved for account '%s'", account.name)
        except Exception:
            logger.exception(
                "Failed to fetch events for account '%s'", account.name
            )

    # Fetch Todoist tasks
    tasks = []
    try:
        todoist_token = secrets.get_secret("todoist-api-token")
        tasks = fetch_tasks(todoist_token, config.todoist.filters, today)
    except Exception:
        logger.exception("Failed to fetch Todoist tasks")

    # Compose and send email
    subject, html = compose_email(
        events=all_events,
        tasks=tasks,
        today=today,
        timezone=config.timezone,
        meal_planning_section_label=config.meal_planning_section_label,
        wife_section_label=config.wife_section_label,
    )

    try:
        conn_string = secrets.get_secret("azure-comms-connection-string")
        send_email(
            connection_string=conn_string,
            sender=config.sender_email,
            recipient=config.recipient_email,
            subject=subject,
            html_body=html,
        )
        logger.info("Daily agenda email sent successfully")
    except Exception:
        logger.exception("Failed to send daily agenda email")


def create_scheduler(
    config: AppConfig, secrets: SecretsClient
) -> BackgroundScheduler:
    """Create and configure the APScheduler instance."""
    scheduler = BackgroundScheduler()
    hour, minute = config.send_time.split(":")

    trigger = CronTrigger(
        hour=int(hour),
        minute=int(minute),
        timezone=ZoneInfo(config.timezone),
    )

    scheduler.add_job(
        send_agenda,
        trigger=trigger,
        args=[config, secrets],
        name="send_agenda",
    )

    return scheduler
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_scheduler.py -v`
Expected: All tests PASS

- [ ] **Step 5: Run full checks**

Run: `task check`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/scheduler.py tests/test_scheduler.py
git commit -m "feat: add scheduler with send_agenda orchestration"
```

---

### Task 9: Main App Wiring

**Files:**
- Modify: `src/main.py`
- Create: `tests/test_main.py`
- Modify: `Dockerfile`
- Modify: `compose.yaml`

- [ ] **Step 1: Write failing tests for the main app**

Create `tests/test_main.py`:

```python
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.config import load_config
from src.secrets import SecretsClient


_TEST_CONFIG_YAML = """
send_time: "06:00"
timezone: "America/New_York"
recipient_email: "test@example.com"
sender_email: "noreply@example.com"
google_accounts:
  - name: "personal"
    calendars:
      - id: "primary"
        label: "Personal"
        section: "self"
        filters:
          exclude_titles: []
todoist:
  filters:
    exclude_projects: []
    exclude_titles: []
meal_planning_section_label: "Dinner"
wife_section_label: "Her Schedule"
"""


@pytest.fixture
def config_file(tmp_path: Path) -> Path:
    config_file = tmp_path / "config.yaml"
    config_file.write_text(_TEST_CONFIG_YAML)
    return config_file


@pytest.fixture
def mock_secrets() -> MagicMock:
    secrets = MagicMock(spec=SecretsClient)
    secrets.get_secret_or_none.return_value = None
    secrets.get_secret.return_value = "valid-token"
    return secrets


@pytest.fixture
def mock_scheduler() -> MagicMock:
    return MagicMock()


@pytest.fixture
def app(config_file: Path, mock_secrets: MagicMock, mock_scheduler: MagicMock) -> "FastAPI":
    from src.main import create_app
    config = load_config(str(config_file))
    return create_app(config, mock_secrets, mock_scheduler)


@pytest.fixture
def client(app: "FastAPI") -> TestClient:
    return TestClient(app)


class TestHealthEndpoint:
    def test_health_returns_ok(self, client: TestClient) -> None:
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


class TestSendEndpoint:
    @patch("src.main.send_agenda")
    def test_send_requires_token(
        self,
        mock_send: MagicMock,
        client: TestClient,
        mock_secrets: MagicMock,
    ) -> None:
        mock_secrets.get_secret.return_value = "valid-token"

        # No token — should fail
        response = client.post("/send")
        assert response.status_code == 401

        # Wrong token — should fail
        response = client.post("/send", headers={"X-Send-Token": "wrong"})
        assert response.status_code == 401

        # Correct token — should succeed
        response = client.post(
            "/send", headers={"X-Send-Token": "valid-token"}
        )
        assert response.status_code == 200
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_main.py -v`
Expected: FAIL — missing imports/functions in `src/main.py`

- [ ] **Step 3: Implement main.py**

Replace `src/main.py` with:

```python
import logging
import os
from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from fastapi import FastAPI, Header, HTTPException

from src.config import AppConfig, load_config
from src.google_auth import create_auth_router
from src.scheduler import create_scheduler, send_agenda
from src.secrets import SecretsClient

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")


def create_app(
    config: AppConfig,
    secrets: SecretsClient,
    scheduler: object | None = None,
) -> FastAPI:
    """App factory. Accepts pre-built config/secrets/scheduler for testability."""

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
        # Check for missing Google tokens
        for account in config.google_accounts:
            token = secrets.get_secret_or_none(f"google-token-{account.name}")
            if token is None:
                logger.warning(
                    "No OAuth token for Google account '%s'. "
                    "Visit /auth/google/start/%s to authorize.",
                    account.name,
                    account.name,
                )

        # Start scheduler if provided
        if scheduler is not None and hasattr(scheduler, "start"):
            scheduler.start()  # type: ignore[union-attr]
            logger.info(
                "Scheduler started — daily send at %s %s",
                config.send_time,
                config.timezone,
            )

        yield

        if scheduler is not None and hasattr(scheduler, "shutdown"):
            scheduler.shutdown(wait=False)  # type: ignore[union-attr]
            logger.info("Scheduler shut down")

    app = FastAPI(lifespan=lifespan)

    # Register OAuth routes
    auth_router = create_auth_router(secrets)
    app.include_router(auth_router)

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok"}

    @app.post("/send")
    async def manual_send(x_send_token: str | None = Header(default=None)) -> dict:
        expected_token = secrets.get_secret("send-endpoint-token")
        if x_send_token is None or x_send_token != expected_token:
            raise HTTPException(status_code=401, detail="Invalid or missing token")

        send_agenda(config, secrets)
        return {"message": "Agenda email sent"}

    return app


def build_app_from_env() -> FastAPI:
    """Build the app from environment variables. Used as the uvicorn factory entrypoint."""
    config_path = os.environ.get("CONFIG_PATH", "config.yaml")
    config = load_config(config_path)
    logger.info("Config loaded from %s", config_path)

    vault_url = os.environ["KEY_VAULT_URL"]
    secrets = SecretsClient(vault_url)

    scheduler = create_scheduler(config, secrets)
    return create_app(config, secrets, scheduler)
```

No module-level `app` variable — uvicorn uses factory mode (`--factory`) to call `build_app_from_env()` at startup. This avoids crashes when tests import `src.main`.

**Important:** Update the uvicorn command in `Taskfile.yml` and `Dockerfile` to use factory mode:

Taskfile `dev` task:
```yaml
  dev:
    desc: Run app locally with hot reload
    cmds:
      - uv run uvicorn src.main:build_app_from_env --factory --reload --port {{.APP_PORT}}
```

Dockerfile CMD:
```dockerfile
CMD ["uvicorn", "src.main:build_app_from_env", "--factory", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_main.py -v`
Expected: All tests PASS

- [ ] **Step 5: Update Dockerfile to use uvicorn factory mode**

Change the CMD in `Dockerfile` to:

```dockerfile
CMD ["uvicorn", "src.main:build_app_from_env", "--factory", "--host", "0.0.0.0", "--port", "8000"]
```

The existing `COPY src/ src/` already copies `src/templates/`. No other Dockerfile changes needed.

- [ ] **Step 5b: Update Taskfile.yml dev command to use factory mode**

Change the `dev` task in `Taskfile.yml` to:

```yaml
  dev:
    desc: Run app locally with hot reload
    cmds:
      - uv run uvicorn src.main:build_app_from_env --factory --reload --port {{.APP_PORT}}
```

- [ ] **Step 6: Update compose.yaml to mount config.yaml**

Replace `compose.yaml` with:

```yaml
services:
  app:
    build: .
    ports:
      - "8000:8000"
    env_file:
      - .env
    volumes:
      - ./src:/app/src
      - ./config.yaml:/app/config.yaml:ro
    restart: unless-stopped
```

- [ ] **Step 7: Run full checks**

Run: `task check`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add src/main.py tests/test_main.py compose.yaml Dockerfile Taskfile.yml
git commit -m "feat: wire up FastAPI app with lifespan, scheduler, and send endpoint"
```

---

### Task 10: Final Integration Verification

**Files:**
- No new files — verify everything works together

- [ ] **Step 1: Run full test suite**

Run: `uv run pytest -v`
Expected: All tests PASS

- [ ] **Step 2: Run full checks (lint, typecheck, test)**

Run: `task check`
Expected: All PASS

- [ ] **Step 3: Verify Docker build succeeds**

Run: `docker build -t daily-agenda-email .`
Expected: Build completes successfully

- [ ] **Step 4: Fix any lint or type errors**

If any issues from steps 1-3, fix them now.

Run: `task fmt` to auto-fix formatting, then manually fix any remaining type errors.

- [ ] **Step 5: Commit any fixes**

```bash
git add -A
git commit -m "chore: fix lint and type errors from integration"
```

- [ ] **Step 6: Final verification**

Run: `task check`
Expected: All PASS — clean build, all tests green, no lint or type errors.
