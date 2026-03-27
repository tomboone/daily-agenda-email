import logging
from dataclasses import replace
from datetime import date, datetime
from pathlib import Path

from azure.communication.email import EmailClient
from jinja2 import Environment, FileSystemLoader

from src.config import CalendarSection
from src.google_calendar import CalendarEvent
from src.todoist import TodoistTask

logger = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).parent / "templates"


def merge_duplicate_events(events: list[CalendarEvent]) -> list[CalendarEvent]:
    """Merge events with the same title and time, combining their calendar labels."""
    seen: dict[tuple[str, datetime | None, datetime | None, bool], int] = {}
    merged: list[CalendarEvent] = []

    for event in events:
        key = (event.title, event.start_time, event.end_time, event.is_all_day)
        if key in seen:
            idx = seen[key]
            existing = merged[idx]
            merged[idx] = replace(
                existing,
                calendar_label=f"{existing.calendar_label}, {event.calendar_label}",
            )
        else:
            seen[key] = len(merged)
            merged.append(event)

    return merged


def compose_email(
    events: list[CalendarEvent],
    tasks: list[TodoistTask],
    today: date,
    timezone: str,
    meal_planning_section_label: str,
    wife_section_label: str,
    sports_section_label: str = "Sports",
) -> tuple[str, str]:
    """Compose the email subject and HTML body. Returns (subject, html)."""
    date_heading = today.strftime("%A, %B %-d, %Y")
    subject = f"Daily Agenda — {today.strftime('%A, %B %-d')}"

    meal_planning_events = [e for e in events if e.section == CalendarSection.MEAL_PLANNING]
    self_events = [e for e in events if e.section == CalendarSection.SELF]
    wife_events = [e for e in events if e.section == CalendarSection.WIFE]
    sports_events = [e for e in events if e.section == CalendarSection.SPORTS]

    self_all_day = merge_duplicate_events([e for e in self_events if e.is_all_day])
    self_timed = merge_duplicate_events([e for e in self_events if not e.is_all_day])
    wife_all_day = [e for e in wife_events if e.is_all_day]
    wife_timed = [e for e in wife_events if not e.is_all_day]
    sports_all_day = [e for e in sports_events if e.is_all_day]
    sports_timed = [e for e in sports_events if not e.is_all_day]

    self_calendar_labels = {e.calendar_label for e in self_events}
    show_calendar_labels = len(self_calendar_labels) > 1

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
        sports_all_day_events=sports_all_day,
        sports_timed_events=sports_timed,
        sports_section_label=sports_section_label,
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
    logger.info("Email sent, status: %s", result["status"])
