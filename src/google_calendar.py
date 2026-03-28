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


def filter_overnight_events(
    events: list[CalendarEvent], today: date, tz: ZoneInfo
) -> list[CalendarEvent]:
    """Drop timed events that started the previous day and end before 6am today."""
    cutoff = datetime.combine(today, datetime.min.time(), tzinfo=tz).replace(hour=6)
    return [
        e
        for e in events
        if e.is_all_day
        or e.start_time is None
        or e.start_time.date() >= today
        or (e.end_time is not None and e.end_time >= cutoff)
    ]


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
    return {item["id"]: item.get("backgroundColor", "#4285f4") for item in result.get("items", [])}


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
            _parse_event(raw, cal.label, color, cal.section, tz) for raw in result.get("items", [])
        ]
        events = filter_events(events, cal.filters.exclude_titles)
        events = filter_overnight_events(events, today, tz)
        all_events.extend(events)

    return sort_events(all_events, tz)
