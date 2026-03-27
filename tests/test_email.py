from datetime import date, datetime
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

from src.config import CalendarSection
from src.email import compose_email, merge_duplicate_events, send_email
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


class TestMergeDuplicateEvents:
    def test_merges_same_title_and_time(self) -> None:
        events = [
            _make_event("Game Break", 12, label="Ingest"),
            _make_event("Game Break", 12, label="Ingest Company"),
        ]
        merged = merge_duplicate_events(events)
        assert len(merged) == 1
        assert merged[0].calendar_label == "Ingest, Ingest Company"

    def test_different_times_not_merged(self) -> None:
        events = [
            _make_event("Standup", 9, label="Work"),
            _make_event("Standup", 10, label="Personal"),
        ]
        merged = merge_duplicate_events(events)
        assert len(merged) == 2

    def test_preserves_order(self) -> None:
        events = [
            _make_event("First", 9, label="A"),
            _make_event("Second", 10, label="B"),
            _make_event("First", 9, label="C"),
        ]
        merged = merge_duplicate_events(events)
        assert len(merged) == 2
        assert merged[0].title == "First"
        assert merged[0].calendar_label == "A, C"
        assert merged[1].title == "Second"

    def test_all_day_duplicates_merged(self) -> None:
        events = [
            _make_event("Holiday", label="Personal"),
            _make_event("Holiday", label="Work"),
        ]
        merged = merge_duplicate_events(events)
        assert len(merged) == 1
        assert merged[0].calendar_label == "Personal, Work"

    def test_uses_first_events_color(self) -> None:
        events = [
            _make_event("Game Break", 12, label="Ingest", color="#ff0000"),
            _make_event("Game Break", 12, label="Ingest Company", color="#0000ff"),
        ]
        merged = merge_duplicate_events(events)
        assert merged[0].calendar_color == "#ff0000"


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
