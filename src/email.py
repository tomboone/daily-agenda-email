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

    meal_planning_events = [e for e in events if e.section == CalendarSection.MEAL_PLANNING]
    self_events = [e for e in events if e.section == CalendarSection.SELF]
    wife_events = [e for e in events if e.section == CalendarSection.WIFE]

    self_all_day = [e for e in self_events if e.is_all_day]
    self_timed = [e for e in self_events if not e.is_all_day]
    wife_all_day = [e for e in wife_events if e.is_all_day]
    wife_timed = [e for e in wife_events if not e.is_all_day]

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
    logger.info("Email sent, status: %s", result.status)  # type: ignore[union-attr]
