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
            sports_section_label="Sports",
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
            sports_section_label="Sports",
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
            sports_section_label="Sports",
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
            sports_section_label="Sports",
        )

        assert "Dinner" not in html
        assert "Tasks" not in html
        assert "Sarah" not in html
        assert "Sports" not in html

    def test_sports_section(self) -> None:
        events = [
            _make_event(
                "F1 Grand Prix",
                section=CalendarSection.SPORTS,
                label="Racing",
                color="#e91e63",
            ),
            _make_event(
                "LFC vs Arsenal",
                hour=11,
                section=CalendarSection.SPORTS,
                label="LFC",
                color="#c8102e",
            ),
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
            sports_section_label="Sports",
        )

        assert "Sports" in html
        assert "F1 Grand Prix" in html
        assert "LFC vs Arsenal" in html
        assert "Racing" in html
        assert "LFC" in html

    def test_sports_section_between_tasks_and_wife(self) -> None:
        events = [
            _make_event("LFC vs Arsenal", hour=11, section=CalendarSection.SPORTS, label="LFC"),
            _make_event("Yoga", 8, section=CalendarSection.WIFE, label="Wife"),
        ]
        tasks = [_make_task("Buy groceries")]
        today = date(2026, 3, 22)

        subject, html = compose_email(
            events=events,
            tasks=tasks,
            today=today,
            timezone="America/New_York",
            meal_planning_section_label="Dinner",
            wife_section_label="Sarah's Schedule",
            sports_section_label="Sports",
        )

        tasks_pos = html.index("Tasks")
        sports_pos = html.index("Sports")
        wife_pos = html.index("Sarah")
        assert tasks_pos < sports_pos < wife_pos

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
            sports_section_label="Sports",
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
