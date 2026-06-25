"""Google Calendar: OAuth authentication, availability checking, event creation."""

import logging
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/calendar"]


class CalendarService:
    def __init__(self, config):
        self.config = config
        self.tz = ZoneInfo(config.google_timezone)
        self.service = None

    def initialize(self) -> None:
        """Run OAuth flow if needed, then build the Calendar API client."""
        creds = self._get_credentials()
        self.service = build("calendar", "v3", credentials=creds)
        logger.info("Google Calendar service ready.")

    def _get_credentials(self) -> Credentials:
        creds: Credentials | None = None
        token_path = self.config.token_file
        creds_path = self.config.credentials_file

        if token_path.exists():
            creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not creds_path.exists():
                    raise FileNotFoundError(
                        f"Google credentials file not found: {creds_path}\n"
                        "Download an OAuth 2.0 Desktop client from Google Cloud Console "
                        "and save it as credentials.json in the project root."
                    )
                flow = InstalledAppFlow.from_client_secrets_file(str(creds_path), SCOPES)
                creds = flow.run_local_server(port=0)

            token_path.write_text(creds.to_json())
            logger.info(f"OAuth token saved to {token_path}")

        return creds

    # ------------------------------------------------------------------
    # Business-hours validation (pure logic, no API calls)
    # ------------------------------------------------------------------

    def is_business_hours(self, dt: datetime) -> bool:
        """
        Return True if dt is a weekday within configured business hours,
        AND the 30-minute appointment ends by the configured end time.
        """
        local = dt.astimezone(self.tz)
        if local.weekday() >= 5:  # Saturday=5, Sunday=6
            return False

        sh, sm = self.config.business_start_hour
        eh, em = self.config.business_end_hour
        start_bound = local.replace(hour=sh, minute=sm, second=0, microsecond=0)
        end_bound = local.replace(hour=eh, minute=em, second=0, microsecond=0)
        apt_end = local + timedelta(minutes=self.config.appointment_duration_minutes)

        return local >= start_bound and apt_end <= end_bound

    # ------------------------------------------------------------------
    # Availability
    # ------------------------------------------------------------------

    def check_availability(self, start_dt: datetime) -> bool:
        """Return True when the 30-minute slot starting at start_dt is free."""
        end_dt = start_dt + timedelta(minutes=self.config.appointment_duration_minutes)

        body = {
            "timeMin": start_dt.isoformat(),
            "timeMax": end_dt.isoformat(),
            "timeZone": self.config.google_timezone,
            "items": [{"id": self.config.google_calendar_id}],
        }
        try:
            result = self.service.freebusy().query(body=body).execute()
            busy = (
                result.get("calendars", {})
                .get(self.config.google_calendar_id, {})
                .get("busy", [])
            )
            return len(busy) == 0
        except HttpError as exc:
            logger.error(f"freebusy query failed: {exc}")
            raise

    def find_available_slots(self, near: datetime, count: int = 3) -> list[datetime]:
        """
        Search forward from `near` in 30-minute steps, returning up to
        `count` available slots within business hours.
        """
        slots: list[datetime] = []
        candidate = near
        # Check up to 5 working days worth of 30-min slots
        for _ in range(5 * 8 * 2):
            if self.is_business_hours(candidate) and self.check_availability(candidate):
                slots.append(candidate)
                if len(slots) >= count:
                    break
            candidate += timedelta(minutes=30)
        return slots

    # ------------------------------------------------------------------
    # Event creation
    # ------------------------------------------------------------------

    def create_appointment(
        self, name: str, email: str, start_dt: datetime
    ) -> dict:
        """
        Create a 30-minute calendar event. Returns the created event dict.
        Raises HttpError on failure — never silently swallows errors.
        """
        end_dt = start_dt + timedelta(minutes=self.config.appointment_duration_minutes)

        event = {
            "summary": f"Appointment: {name}",
            "description": (
                f"Customer: {name}\n"
                f"Email: {email}\n"
                f"Duration: {self.config.appointment_duration_minutes} minutes\n"
                "Note: Created by local voice-agent prototype."
            ),
            "start": {
                "dateTime": start_dt.isoformat(),
                "timeZone": self.config.google_timezone,
            },
            "end": {
                "dateTime": end_dt.isoformat(),
                "timeZone": self.config.google_timezone,
            },
            "attendees": [{"email": email, "displayName": name}],
        }

        try:
            created = (
                self.service.events()
                .insert(
                    calendarId=self.config.google_calendar_id,
                    body=event,
                    sendUpdates="all",
                )
                .execute()
            )
            logger.info(f"Event created: {created.get('id')} for {name} at {start_dt}")
            return created
        except HttpError as exc:
            logger.error(f"Event creation failed: {exc}")
            raise
