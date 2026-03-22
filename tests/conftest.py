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
                        filters=CalendarFilters(exclude_titles=["tv off", "bed", "lights out"]),
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
