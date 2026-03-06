---
name: google-calendar
description: Setup and integration guide for Google Calendar API. Use when enabling Calendar API access, adding calendar scopes to an existing OAuth token, reading today's schedule or upcoming events, creating calendar events programmatically, wiring the Calendar tab in the dashboard, or debugging Calendar API errors (403 accessNotConfigured, insufficientPermissions, invalid_grant).
---

# Google Calendar API

## Two-Step Setup (both required)

### 1. Enable Calendar API in GCP Console
This is separate from OAuth and is frequently missed:
```
https://console.developers.google.com/apis/api/calendar-json.googleapis.com/overview?project=<PROJECT_NUMBER>
```
Click **Enable**. Wait ~1 minute. The project number appears in the `403 accessNotConfigured` error URL if you hit it before enabling.

### 2. Add Calendar Scopes to OAuth Token
The `gmail_credentials.json` must be re-generated to include calendar scopes. See the `gmail-oauth` skill for the OOB re-auth flow. Use these combined scopes:

```python
SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/calendar.events",
]
```

No separate credentials file needed — Calendar uses the same `gmail_credentials.json` as Gmail.

## GoogleCalendarClient Usage

File: `src/mcp_servers/google_calendar_client.py`

```python
from src.mcp_servers.google_calendar_client import GoogleCalendarClient
from pathlib import Path

cal = GoogleCalendarClient(Path("~/.config/ai-employee/gmail_credentials.json").expanduser())
```

### Read Events

```python
# Today's events
events = cal.get_todays_schedule()

# Upcoming events
events = cal.list_upcoming_events(max_results=10)

# Each event:
# { "id", "summary", "start", "end", "location", "description", "status" }
# start/end are ISO strings: "2026-03-10T09:00:00+05:00" (timed) or "2026-03-10" (all-day)
```

### Create Event

```python
from datetime import datetime, timezone

event = cal.create_event(
    summary="Meeting with Ahmed",
    start_dt=datetime(2026, 3, 10, 10, 0, tzinfo=timezone.utc),
    end_dt=datetime(2026, 3, 10, 11, 0, tzinfo=timezone.utc),
    description="Discuss proposal",
    location="Google Meet",
    attendees=["ahmed@example.com"],
)
event_id = event["id"]
```

### Delete Event

```python
cal.delete_event(event_id="abc123")
```

## Dashboard Wiring

- `GET /api/calendar/today` → `api_calendar_today()` → `cal.get_todays_schedule()`
- `GET /api/calendar/upcoming` → `api_calendar_upcoming()` → `cal.list_upcoming_events(max_results=10)`

Both registered in GET routes dict in `src/cli/web_dashboard.py`.

## Common Errors

| Error | Cause | Fix |
|-------|-------|-----|
| `403 accessNotConfigured` | Calendar API not enabled | Enable via URL in the error message |
| `403 insufficientPermissions` | Token missing calendar scopes | Re-run OOB auth with calendar scopes (gmail-oauth skill) |
| `invalid_grant` | Token expired | Re-run OOB auth flow (gmail-oauth skill) |
| `AttributeError: no attribute 'get_today_events'` | Wrong method name | Use `get_todays_schedule()` not `get_today_events()` |
