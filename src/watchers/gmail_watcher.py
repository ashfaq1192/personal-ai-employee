"""Gmail Watcher — polls Gmail API for important/urgent emails."""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.core.config import Config
from src.watchers.base_watcher import BaseWatcher

log = logging.getLogger(__name__)


def _load_known_contacts(vault_path: Path) -> set[str]:
    """Parse known contacts from Company_Handbook.md."""
    handbook = vault_path / "Company_Handbook.md"
    contacts: set[str] = set()
    if not handbook.exists():
        return contacts

    in_table = False
    for line in handbook.read_text(encoding="utf-8").splitlines():
        if "| Name" in line and "Email" in line:
            in_table = True
            continue
        if in_table and line.startswith("|"):
            parts = [p.strip() for p in line.split("|")]
            # parts: ['', name, email, whatsapp, auto_approve, '']
            if len(parts) >= 4 and "@" in parts[2]:
                contacts.add(parts[2].lower())
        elif in_table and not line.startswith("|"):
            in_table = False
    return contacts


class GmailWatcher(BaseWatcher):
    """Polls Gmail for unread important emails and emails from known contacts."""

    def __init__(self, config: Config) -> None:
        super().__init__(config, check_interval=120, watcher_name="gmail")
        self._processed_ids: set[str] = set()
        self._service = None  # Lazy-loaded Gmail API service
        self._known_contacts: set[str] = _load_known_contacts(config.vault_path)

    def _get_service(self):
        """Lazy-load Gmail API service."""
        if self._service is not None:
            return self._service

        if self.config.dev_mode:
            log.info("DEV_MODE: Gmail service not initialized (mock mode)")
            return None

        try:
            from google.oauth2.credentials import Credentials
            from googleapiclient.discovery import build

            creds_path = self.config.gmail_credentials_path
            if not creds_path.exists():
                log.error("Gmail credentials not found at %s", creds_path)
                self._create_alert("auth_missing", "Gmail credentials file not found")
                return None

            creds = Credentials.from_authorized_user_file(str(creds_path))
            if creds.expired and creds.refresh_token:
                from google.auth.transport.requests import Request
                creds.refresh(Request())
                creds_path.write_text(creds.to_json(), encoding="utf-8")

            self._service = build("gmail", "v1", credentials=creds)
            return self._service
        except Exception as exc:
            log.error("Failed to initialize Gmail service: %s", exc)
            self._create_alert("auth_expired", f"Gmail auth failed: {exc}")
            return None

    def _create_alert(self, alert_type: str, message: str) -> None:
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M")
        alert_path = self.needs_action_dir / f"ALERT_{alert_type}_{ts}.md"
        if not alert_path.exists():
            alert_path.write_text(
                f"---\ntype: alert\nid: ALERT_{alert_type}_{ts}\n"
                f"from: system\nsubject: {message}\n"
                f"received: {datetime.now(timezone.utc).isoformat()}\n"
                f"priority: high\nstatus: pending\nplan_ref: null\n---\n\n"
                f"## Alert\n{message}\n",
                encoding="utf-8",
            )

    def check_for_updates(self) -> list[Any]:
        if self.config.dev_mode:
            log.debug("DEV_MODE: skipping Gmail check")
            return []

        service = self._get_service()
        if service is None:
            return []

        try:
            # Query important unread emails
            results = (
                service.users()
                .messages()
                .list(
                    userId="me",
                    q="is:unread is:important",
                    maxResults=20,
                )
                .execute()
            )
            messages = results.get("messages", [])

            # Also query known contacts (unread)
            for contact in self._known_contacts:
                contact_results = (
                    service.users()
                    .messages()
                    .list(
                        userId="me",
                        q=f"is:unread from:{contact}",
                        maxResults=10,
                    )
                    .execute()
                )
                messages.extend(contact_results.get("messages", []))

            # Deduplicate
            seen_ids: set[str] = set()
            unique: list[dict] = []
            for msg in messages:
                msg_id = msg["id"]
                if msg_id not in seen_ids and msg_id not in self._processed_ids:
                    seen_ids.add(msg_id)
                    unique.append(msg)

            # Fetch full message details
            items = []
            for msg in unique:
                try:
                    full = (
                        service.users()
                        .messages()
                        .get(userId="me", id=msg["id"], format="metadata")
                        .execute()
                    )
                    items.append(full)
                except Exception:
                    log.exception("Failed to fetch message %s", msg["id"])

            return items
        except Exception as exc:
            if "401" in str(exc):
                self._create_alert("auth_expired", "Gmail credentials expired")
            log.exception("Gmail check_for_updates failed")
            return []

    def create_action_file(self, item: Any) -> Path:
        msg_id = item["id"]
        headers = {h["name"]: h["value"] for h in item.get("payload", {}).get("headers", [])}
        sender = headers.get("From", "unknown")
        subject = headers.get("Subject", "(no subject)")
        date_str = headers.get("Date", "")

        # Determine priority
        sender_email = ""
        match = re.search(r"<(.+?)>", sender)
        if match:
            sender_email = match.group(1).lower()
        elif "@" in sender:
            sender_email = sender.strip().lower()

        priority = "high" if sender_email in self._known_contacts else "low"
        now = datetime.now(timezone.utc)

        md_path = self.needs_action_dir / f"EMAIL_{msg_id}.md"
        if md_path.exists():
            self._processed_ids.add(msg_id)
            return md_path

        snippet = item.get("snippet", "")
        md_content = (
            f"---\n"
            f"type: email\n"
            f"id: EMAIL_{msg_id}\n"
            f"from: {sender}\n"
            f"subject: {subject}\n"
            f"received: {now.isoformat()}\n"
            f"priority: {priority}\n"
            f"status: pending\n"
            f"plan_ref: null\n"
            f"---\n\n"
            f"## Content\n"
            f"**From**: {sender}\n"
            f"**Subject**: {subject}\n"
            f"**Date**: {date_str}\n\n"
            f"{snippet}\n\n"
            f"## Suggested Actions\n"
            f"- [ ] Read and classify email\n"
            f"- [ ] Determine response action\n"
        )
        md_path.write_text(md_content, encoding="utf-8")
        self._processed_ids.add(msg_id)
        return md_path
