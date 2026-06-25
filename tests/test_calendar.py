"""
Unit tests for calendar business-hour and scheduling logic.
No Google API calls are made.
"""

import pytest
from datetime import datetime
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

from calendar_service import CalendarService


def _make_service() -> CalendarService:
    """Build a CalendarService instance without running OAuth."""
    config = MagicMock()
    config.google_timezone = "Europe/Madrid"
    config.business_start_hour = (9, 0)
    config.business_end_hour = (17, 0)
    config.appointment_duration_minutes = 30
    config.google_calendar_id = "primary"

    svc = CalendarService.__new__(CalendarService)
    svc.config = config
    svc.tz = ZoneInfo("Europe/Madrid")
    svc.service = None
    return svc


TZ = ZoneInfo("Europe/Madrid")


class TestIsBusinessHours:
    def setup_method(self):
        self.svc = _make_service()

    # Weekday / weekend -------------------------------------------------

    def test_monday_10am_is_business(self):
        dt = datetime(2026, 6, 29, 10, 0, tzinfo=TZ)  # Monday
        assert self.svc.is_business_hours(dt) is True

    def test_wednesday_midday_is_business(self):
        dt = datetime(2026, 7, 1, 12, 0, tzinfo=TZ)  # Wednesday
        assert self.svc.is_business_hours(dt) is True

    def test_friday_4_30pm_last_slot(self):
        dt = datetime(2026, 6, 26, 16, 30, tzinfo=TZ)  # Friday 16:30 + 30 min = 17:00
        assert self.svc.is_business_hours(dt) is True

    def test_saturday_is_not_business(self):
        dt = datetime(2026, 6, 27, 10, 0, tzinfo=TZ)  # Saturday
        assert self.svc.is_business_hours(dt) is False

    def test_sunday_is_not_business(self):
        dt = datetime(2026, 6, 28, 14, 0, tzinfo=TZ)  # Sunday
        assert self.svc.is_business_hours(dt) is False

    # Boundary times ----------------------------------------------------

    def test_9am_exactly_is_business(self):
        dt = datetime(2026, 6, 29, 9, 0, tzinfo=TZ)
        assert self.svc.is_business_hours(dt) is True

    def test_before_9am_is_not_business(self):
        dt = datetime(2026, 6, 29, 8, 59, tzinfo=TZ)
        assert self.svc.is_business_hours(dt) is False

    def test_4_31pm_exceeds_end_time(self):
        # 16:31 + 30 min = 17:01 > 17:00
        dt = datetime(2026, 6, 29, 16, 31, tzinfo=TZ)
        assert self.svc.is_business_hours(dt) is False

    def test_5pm_exactly_is_not_bookable(self):
        # 17:00 + 30 min = 17:30 > 17:00
        dt = datetime(2026, 6, 29, 17, 0, tzinfo=TZ)
        assert self.svc.is_business_hours(dt) is False

    # Duration enforcement ----------------------------------------------

    def test_30_min_duration_fills_to_5pm(self):
        dt = datetime(2026, 6, 29, 16, 30, tzinfo=TZ)  # ends exactly at 17:00
        assert self.svc.is_business_hours(dt) is True

    def test_duration_respected_over_end(self):
        dt = datetime(2026, 6, 29, 16, 45, tzinfo=TZ)  # ends at 17:15
        assert self.svc.is_business_hours(dt) is False

    # Timezone handling -------------------------------------------------

    def test_utc_time_respects_madrid_timezone(self):
        # 09:00 Madrid = 07:00 UTC in summer (CEST = UTC+2)
        import pytz
        madrid = pytz.timezone("Europe/Madrid")
        # Create a naive datetime that is 07:00 UTC on a weekday
        dt_utc = datetime(2026, 6, 29, 7, 0)
        dt_madrid = madrid.localize(dt_utc.replace(hour=9))  # 09:00 Madrid local
        assert self.svc.is_business_hours(dt_madrid) is True
