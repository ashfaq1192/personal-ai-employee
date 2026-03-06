"""Google Calendar MCP server — exposes calendar tools to Claude."""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from src.core.config import Config
from src.mcp_servers.google_calendar_client import GoogleCalendarClient

log = logging.getLogger(__name__)

server = Server("calendar-mcp")
_config = Config()
_client: GoogleCalendarClient | None = None


def _get_client() -> GoogleCalendarClient:
    global _client
    if _client is None:
        _client = GoogleCalendarClient(_config.gmail_credentials_path)
    return _client


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="calendar_list_upcoming",
            description="List upcoming calendar events (next N events from now)",
            inputSchema={
                "type": "object",
                "properties": {
                    "max_results": {"type": "integer", "default": 10, "description": "Max events to return"},
                },
            },
        ),
        Tool(
            name="calendar_get_today",
            description="Get all events scheduled for today",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="calendar_create_event",
            description="Create a calendar event",
            inputSchema={
                "type": "object",
                "required": ["summary", "start_iso"],
                "properties": {
                    "summary": {"type": "string", "description": "Event title"},
                    "start_iso": {"type": "string", "description": "Start datetime in ISO 8601 format with timezone (e.g. 2026-03-06T14:00:00+05:00)"},
                    "duration_minutes": {"type": "integer", "default": 60},
                    "description": {"type": "string", "default": ""},
                    "location": {"type": "string", "default": ""},
                    "attendees": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of attendee email addresses",
                        "default": [],
                    },
                },
            },
        ),
        Tool(
            name="calendar_create_recurring",
            description="Create a recurring calendar event",
            inputSchema={
                "type": "object",
                "required": ["summary", "start_iso", "recurrence_rule"],
                "properties": {
                    "summary": {"type": "string"},
                    "start_iso": {"type": "string"},
                    "recurrence_rule": {
                        "type": "string",
                        "description": "RFC 5545 RRULE e.g. 'RRULE:FREQ=WEEKLY;BYDAY=MO,WE,FR'",
                    },
                    "duration_minutes": {"type": "integer", "default": 60},
                    "description": {"type": "string", "default": ""},
                },
            },
        ),
        Tool(
            name="calendar_delete_event",
            description="Delete a calendar event by ID",
            inputSchema={
                "type": "object",
                "required": ["event_id"],
                "properties": {
                    "event_id": {"type": "string"},
                },
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if _config.dev_mode:
        return [TextContent(type="text", text=f"[DEV_MODE] Would call: {name}({arguments})")]

    client = _get_client()

    try:
        if name == "calendar_list_upcoming":
            events = client.list_upcoming_events(max_results=arguments.get("max_results", 10))
            return [TextContent(type="text", text=json.dumps(events, indent=2))]

        elif name == "calendar_get_today":
            events = client.get_todays_schedule()
            return [TextContent(type="text", text=json.dumps(events, indent=2))]

        elif name == "calendar_create_event":
            start = datetime.fromisoformat(arguments["start_iso"])
            result = client.create_event(
                summary=arguments["summary"],
                start=start,
                duration_minutes=arguments.get("duration_minutes", 60),
                description=arguments.get("description", ""),
                location=arguments.get("location", ""),
                attendees=arguments.get("attendees") or [],
            )
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "calendar_create_recurring":
            start = datetime.fromisoformat(arguments["start_iso"])
            result = client.create_recurring_event(
                summary=arguments["summary"],
                start=start,
                recurrence_rule=arguments["recurrence_rule"],
                duration_minutes=arguments.get("duration_minutes", 60),
                description=arguments.get("description", ""),
            )
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "calendar_delete_event":
            client.delete_event(arguments["event_id"])
            return [TextContent(type="text", text=json.dumps({"status": "deleted", "id": arguments["event_id"]}))]

        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]

    except Exception as exc:
        log.exception("Calendar MCP tool %s failed", name)
        return [TextContent(type="text", text=json.dumps({"error": str(exc)}))]


async def main() -> None:
    async with stdio_server() as streams:
        await server.run(streams[0], streams[1], server.create_initialization_options())


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    import asyncio
    asyncio.run(main())
