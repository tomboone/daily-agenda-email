from datetime import date, datetime
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

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
    filter_overnight_events,
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

        mock_service.calendarList().list().execute.return_value = {
            "items": [
                {"id": "primary", "backgroundColor": "#4285f4"},
                {"id": "family@group.calendar.google.com", "backgroundColor": "#0b8043"},
            ]
        }

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
        sorted_events = sorted(
            events,
            key=lambda e: (not e.is_all_day, e.start_time or datetime.min.replace(tzinfo=tz)),
        )
        assert sorted_events[0].title == "All day"
        assert sorted_events[1].title == "Meeting"


class TestFilterOvernightEvents:
    """Test filtering of previous-day events that end early in the morning."""

    tz = ZoneInfo("America/New_York")
    today = date(2026, 3, 22)

    def _make(
        self, title: str, start: datetime | None, end: datetime | None, is_all_day: bool = False
    ) -> CalendarEvent:
        return CalendarEvent(
            title=title,
            start_time=start,
            end_time=end,
            is_all_day=is_all_day,
            calendar_label="Cal",
            calendar_color="#4285f4",
            section=CalendarSection.SELF,
        )

    def test_drops_previous_day_event_ending_before_6am(self) -> None:
        events = [
            self._make(
                "Late show",
                datetime(2026, 3, 21, 22, 0, tzinfo=self.tz),
                datetime(2026, 3, 22, 1, 0, tzinfo=self.tz),
            ),
        ]
        result = filter_overnight_events(events, self.today, self.tz)
        assert len(result) == 0

    def test_keeps_previous_day_event_ending_at_6am_or_later(self) -> None:
        events = [
            self._make(
                "Overnight shift",
                datetime(2026, 3, 21, 22, 0, tzinfo=self.tz),
                datetime(2026, 3, 22, 6, 0, tzinfo=self.tz),
            ),
            self._make(
                "Long event",
                datetime(2026, 3, 21, 20, 0, tzinfo=self.tz),
                datetime(2026, 3, 22, 8, 0, tzinfo=self.tz),
            ),
        ]
        result = filter_overnight_events(events, self.today, self.tz)
        assert len(result) == 2

    def test_keeps_same_day_events(self) -> None:
        events = [
            self._make(
                "Morning meeting",
                datetime(2026, 3, 22, 9, 0, tzinfo=self.tz),
                datetime(2026, 3, 22, 10, 0, tzinfo=self.tz),
            ),
        ]
        result = filter_overnight_events(events, self.today, self.tz)
        assert len(result) == 1

    def test_keeps_all_day_events(self) -> None:
        events = [self._make("Holiday", None, None, is_all_day=True)]
        result = filter_overnight_events(events, self.today, self.tz)
        assert len(result) == 1
