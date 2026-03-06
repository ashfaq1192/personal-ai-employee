"""Google Calendar API client — read events, create events, schedule agent work."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)


class GoogleCalendarClient:
    """Wraps Google Calendar API v3."""

    def __init__(self, credentials_path: Path) -> None:
        self._creds_path = credentials_path
        self._service = None

    def _get_service(self):
        if self._service is not None:
            return self._service

        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build

        creds = Credentials.from_authorized_user_file(
            str(self._creds_path),
            scopes=[
                "https://www.googleapis.com/auth/calendar",
                "https://www.googleapis.com/auth/gmail.modify",
            ],
        )
        if creds.expired and creds.refresh_token:
            from google.auth.transport.requests import Request
            creds.refresh(Request())
            self._creds_path.write_text(creds.to_json(), encoding="utf-8")

        self._service = build("calendar", "v3", credentials=creds)
        return self._service

    def list_upcoming_events(self, max_results: int = 10, calendar_id: str = "primary") -> list[dict[str, Any]]:
        """Return upcoming calendar events starting from now."""
        service = self._get_service()
        now = datetime.now(timezone.utc).isoformat()
        result = (
            service.events()
            .list(
                calendarId=calendar_id,
                timeMin=now,
                maxResults=max_results,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )
        events = []
        for e in result.get("items", []):
            start = e.get("start", {})
            events.append({
                "id": e.get("id", ""),
                "summary": e.get("summary", "(no title)"),
                "description": e.get("description", ""),
                "start": start.get("dateTime", start.get("date", "")),
                "end": e.get("end", {}).get("dateTime", e.get("end", {}).get("date", "")),
                "location": e.get("location", ""),
                "status": e.get("status", ""),
            })
        return events

    def create_event(
        self,
        summary: str,
        start: datetime,
        *,
        duration_minutes: int = 60,
        description: str = "",
        location: str = "",
        calendar_id: str = "primary",
        attendees: list[str] | None = None,
    ) -> dict[str, Any]:
        """Create a calendar event. start must be timezone-aware."""
        service = self._get_service()
        end = start + timedelta(minutes=duration_minutes)
        body: dict[str, Any] = {
            "summary": summary,
            "description": description,
            "location": location,
            "start": {"dateTime": start.isoformat(), "timeZone": "UTC"},
            "end": {"dateTime": end.isoformat(), "timeZone": "UTC"},
        }
        if attendees:
            body["attendees"] = [{"email": a} for a in attendees]

        result = service.events().insert(calendarId=calendar_id, body=body).execute()
        log.info("Created calendar event: %s (id=%s)", summary, result.get("id"))
        return {
            "id": result.get("id", ""),
            "summary": summary,
            "start": start.isoformat(),
            "link": result.get("htmlLink", ""),
        }

    def create_recurring_event(
        self,
        summary: str,
        start: datetime,
        recurrence_rule: str,
        *,
        duration_minutes: int = 60,
        description: str = "",
        calendar_id: str = "primary",
    ) -> dict[str, Any]:
        """Create a recurring event. recurrence_rule e.g. 'RRULE:FREQ=WEEKLY;BYDAY=MO'."""
        service = self._get_service()
        end = start + timedelta(minutes=duration_minutes)
        body: dict[str, Any] = {
            "summary": summary,
            "description": description,
            "start": {"dateTime": start.isoformat(), "timeZone": "UTC"},
            "end": {"dateTime": end.isoformat(), "timeZone": "UTC"},
            "recurrence": [recurrence_rule],
        }
        result = service.events().insert(calendarId=calendar_id, body=body).execute()
        log.info("Created recurring event: %s (id=%s)", summary, result.get("id"))
        return {"id": result.get("id", ""), "summary": summary, "link": result.get("htmlLink", "")}

    def delete_event(self, event_id: str, calendar_id: str = "primary") -> None:
        """Delete a calendar event by ID."""
        service = self._get_service()
        service.events().delete(calendarId=calendar_id, eventId=event_id).execute()
        log.info("Deleted calendar event: %s", event_id)

    def get_todays_schedule(self, calendar_id: str = "primary") -> list[dict[str, Any]]:
        """Return all events for today."""
        now = datetime.now(timezone.utc)
        start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = now.replace(hour=23, minute=59, second=59, microsecond=0)
        service = self._get_service()
        result = (
            service.events()
            .list(
                calendarId=calendar_id,
                timeMin=start_of_day.isoformat(),
                timeMax=end_of_day.isoformat(),
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )
        events = []
        for e in result.get("items", []):
            start = e.get("start", {})
            events.append({
                "id": e.get("id", ""),
                "summary": e.get("summary", "(no title)"),
                "start": start.get("dateTime", start.get("date", "")),
                "end": e.get("end", {}).get("dateTime", ""),
            })
        return events
