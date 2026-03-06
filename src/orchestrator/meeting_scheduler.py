"""Meeting Scheduler — detects meeting requests in emails and proposes calendar slots.

Workflow:
1. GmailWatcher creates EMAIL_*.md in Needs_Action/
2. Orchestrator triggers reasoning
3. MeetingScheduler detects "let's meet" intent
4. Finds 3 free calendar slots in the next 7 days
5. Drafts a reply with the time options → writes to Pending_Approval/
6. Human approves → email is sent → calendar event created on confirmation
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

from src.core.config import Config
from src.core.logger import AuditLogger

log = logging.getLogger(__name__)

MEETING_KEYWORDS = [
    "let's meet", "lets meet", "schedule a call", "schedule a meeting",
    "book a call", "book a meeting", "can we meet", "can we talk",
    "set up a call", "arrange a meeting", "sync up", "catch up",
    "video call", "zoom call", "teams call", "google meet",
    "when are you available", "what time works", "free for a call",
    "30 minutes", "15 minutes", "quick call", "hop on a call",
]


class MeetingScheduler:
    """Detects meeting requests and proposes available calendar slots."""

    def __init__(self, config: Config | None = None) -> None:
        self.config = config or Config()
        self.audit = AuditLogger(self.config.vault_path)
        self._calendar = None

    def _get_calendar(self):
        if self._calendar is None:
            from src.mcp_servers.google_calendar_client import GoogleCalendarClient
            self._calendar = GoogleCalendarClient(self.config.gmail_credentials_path)
        return self._calendar

    def is_meeting_request(self, subject: str, body: str = "") -> bool:
        """Return True if the email appears to be a meeting request."""
        text = (subject + " " + body).lower()
        return any(kw in text for kw in MEETING_KEYWORDS)

    def find_available_slots(
        self,
        duration_minutes: int = 60,
        count: int = 3,
        days_ahead: int = 7,
        work_start_hour: int = 9,
        work_end_hour: int = 17,
    ) -> list[datetime]:
        """Find free calendar slots in the next `days_ahead` working days."""
        if self.config.dev_mode:
            now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
            return [
                now + timedelta(days=1, hours=10),
                now + timedelta(days=2, hours=14),
                now + timedelta(days=3, hours=11),
            ]

        try:
            calendar = self._get_calendar()
            events = calendar.list_upcoming_events(max_results=50)
        except Exception:
            log.exception("Failed to fetch calendar events for slot finding")
            return []

        # Build busy intervals
        busy: list[tuple[datetime, datetime]] = []
        for e in events:
            try:
                start = datetime.fromisoformat(e["start"])
                end = datetime.fromisoformat(e["end"])
                busy.append((start, end))
            except (KeyError, ValueError, TypeError):
                pass

        slots: list[datetime] = []
        now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
        candidate = now + timedelta(hours=2)

        while len(slots) < count and candidate < now + timedelta(days=days_ahead):
            # Skip weekends
            if candidate.weekday() >= 5:
                candidate = (candidate + timedelta(days=1)).replace(
                    hour=work_start_hour, minute=0
                )
                continue
            # Enforce working hours
            if candidate.hour < work_start_hour:
                candidate = candidate.replace(hour=work_start_hour)
                continue
            if candidate.hour >= work_end_hour:
                candidate = (candidate + timedelta(days=1)).replace(
                    hour=work_start_hour, minute=0
                )
                continue
            # Check slot fits in working hours
            slot_end = candidate + timedelta(minutes=duration_minutes)
            if slot_end.hour >= work_end_hour:
                candidate = candidate.replace(hour=work_start_hour) + timedelta(days=1)
                continue
            # Check against busy times
            conflict = False
            for b_start, b_end in busy:
                if candidate < b_end and slot_end > b_start:
                    conflict = True
                    candidate = b_end.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
                    break
            if not conflict:
                slots.append(candidate)
                candidate += timedelta(hours=2)

        return slots

    def draft_reply(
        self,
        sender_name: str,
        slots: list[datetime],
        duration_minutes: int = 60,
        sender_email: str = "",
    ) -> str:
        """Draft a reply email proposing time slots."""
        # Use contact memory preferred name if available
        if sender_email:
            try:
                from src.orchestrator.contact_memory import ContactMemory
                mem = ContactMemory(self.config.vault_path)
                contact = mem.recall(sender_email)
                first_name = contact.get("preferred_name") or sender_name.split()[0] if sender_name else "there"
            except Exception:
                first_name = sender_name.split()[0] if sender_name else "there"
        else:
            first_name = sender_name.split()[0] if sender_name else "there"

        if not slots:
            return (
                f"Hi {first_name},\n\n"
                f"Thank you for reaching out! I'd love to connect.\n"
                f"Could you please share your availability and I'll do my best to find a time that works?\n\n"
                f"Best regards"
            )

        slot_lines = []
        for i, slot in enumerate(slots[:3], 1):
            day = slot.strftime("%A, %B %d")
            time_str = slot.strftime("%I:%M %p UTC")
            slot_lines.append(f"  {i}. {day} at {time_str} ({duration_minutes} min)")

        return (
            f"Hi {first_name},\n\n"
            f"Great to hear from you! I'd love to connect.\n\n"
            f"Here are some times that work for me:\n\n"
            + "\n".join(slot_lines) +
            f"\n\nPlease let me know which works best, or suggest an alternative time.\n\n"
            f"Looking forward to speaking with you!\n\nBest regards"
        )

    def create_approval_request(
        self,
        email_file: Path,
        sender: str,
        sender_name: str,
        subject: str,
        duration_minutes: int = 60,
    ) -> Path:
        """Write a Pending_Approval file with the meeting reply draft."""
        slots = self.find_available_slots(duration_minutes=duration_minutes)
        reply = self.draft_reply(sender_name, slots, duration_minutes)

        vault = self.config.vault_path
        pending_dir = vault / "Pending_Approval"
        pending_dir.mkdir(parents=True, exist_ok=True)

        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M")
        filename = f"APPROVAL_meeting_{ts}.md"
        path = pending_dir / filename

        slots_text = "\n".join(
            f"  - {s.isoformat()}" for s in slots
        ) if slots else "  []"

        content = (
            f"---\n"
            f"type: meeting_request\n"
            f"action: email_send\n"
            f"requested_by: meeting_scheduler\n"
            f"requested_at: {datetime.now(timezone.utc).isoformat()}\n"
            f"to: {sender}\n"
            f"subject: Re: {subject}\n"
            f"source_email: {email_file.name}\n"
            f"duration_minutes: {duration_minutes}\n"
            f"proposed_slots:\n{slots_text}\n"
            f"---\n\n"
            f"## Meeting Request\n\n"
            f"**From**: {sender_name} <{sender}>\n"
            f"**Subject**: {subject}\n\n"
            f"**Proposed Slots** ({duration_minutes} min each):\n"
        )
        for i, slot in enumerate(slots[:3], 1):
            content += f"{i}. {slot.strftime('%A, %B %d at %I:%M %p UTC')}\n"

        content += f"\n## Reply Body\n\n{reply}\n"

        path.write_text(content, encoding="utf-8")
        log.info("Meeting approval created: %s (%d slots)", filename, len(slots))

        self.audit.log(
            action_type="meeting_scheduled",
            actor="meeting_scheduler",
            target=sender,
            parameters={"subject": subject, "slots": len(slots), "file": filename},
        )
        return path

    def scan_email_file(self, email_file: Path) -> Path | None:
        """Check an EMAIL_*.md file and create approval if it's a meeting request."""
        try:
            text = email_file.read_text(encoding="utf-8")
        except Exception:
            return None

        # Parse frontmatter
        fm: dict[str, str] = {}
        m = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
        if m:
            for line in m.group(1).splitlines():
                if ":" in line:
                    k, _, v = line.partition(":")
                    fm[k.strip()] = v.strip()

        subject = fm.get("subject", "")
        sender = fm.get("from", "")
        # Extract name from "Name <email>" format
        name_match = re.match(r"(.+?)\s*<", sender)
        sender_name = name_match.group(1).strip() if name_match else sender

        # Get body from content section
        body_match = re.search(r"## Content\s*\n([\s\S]+?)(?:##|$)", text)
        body = body_match.group(1).strip() if body_match else ""

        if not self.is_meeting_request(subject, body):
            return None

        log.info("Meeting request detected in %s from %s", email_file.name, sender)
        return self.create_approval_request(
            email_file=email_file,
            sender=sender,
            sender_name=sender_name,
            subject=subject,
        )
