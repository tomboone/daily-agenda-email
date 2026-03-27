import enum
from pathlib import Path

import yaml
from pydantic import BaseModel


class CalendarSection(str, enum.Enum):
    SELF = "self"
    WIFE = "wife"
    MEAL_PLANNING = "meal_planning"
    SPORTS = "sports"


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
    sports_section_label: str = "Sports"


def load_config(path: str) -> AppConfig:
    """Load and validate config from a YAML file."""
    text = Path(path).read_text()
    return load_config_from_yaml(text)


def load_config_from_yaml(text: str) -> AppConfig:
    """Parse and validate config from a YAML string."""
    data = yaml.safe_load(text)
    return AppConfig.model_validate(data)
