from pathlib import Path

import pytest

from src.config import (
    CalendarSection,
    load_config,
    load_config_from_yaml,
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


def test_load_config_from_yaml_string() -> None:
    yaml_text = """
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
"""
    config = load_config_from_yaml(yaml_text)
    assert config.send_time == "06:00"
    assert config.recipient_email == "test@example.com"
    assert len(config.google_accounts) == 1
