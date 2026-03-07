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
    """Polls Gmail for new emails using incremental history-based fetching.

    Instead of re-scanning all unread emails every cycle, we track the Gmail
    historyId and only fetch changes since the last check — much more efficient
    and behaves like push notifications without requiring a public endpoint.
    """

    def __init__(self, config: Config) -> None:
        super().__init__(config, check_interval=30, watcher_name="gmail")  # 30s instead of 120s
        self._processed_ids: set[str] = set()
        self._service = None  # Lazy-loaded Gmail API service
        self._known_contacts: set[str] = _load_known_contacts(config.vault_path)
        self._last_history_id: str | None = None  # tracks incremental position

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

    def _get_start_history_id(self, service) -> str | None:
        """Get the current historyId from the profile to begin incremental tracking."""
        try:
            profile = service.users().getProfile(userId="me").execute()
            return profile.get("historyId")
        except Exception:
            return None

    def check_for_updates(self) -> list[Any]:
        if self.config.dev_mode:
            log.debug("DEV_MODE: skipping Gmail check")
            return []

        service = self._get_service()
        if service is None:
            return []

        try:
            # On first run, seed the history cursor and fall back to full scan
            if self._last_history_id is None:
                self._last_history_id = self._get_start_history_id(service)
                log.info("Gmail watcher seeded at historyId=%s — running initial full scan", self._last_history_id)
                return self._full_scan(service)

            # Incremental: only messages added since last historyId
            return self._incremental_scan(service)

        except Exception as exc:
            if "401" in str(exc):
                self._create_alert("auth_expired", "Gmail credentials expired")
            log.exception("Gmail check_for_updates failed")
            return []

    def _incremental_scan(self, service) -> list[Any]:
        """Fetch only messages added since _last_history_id (efficient, push-like)."""
        try:
            history_result = (
                service.users()
                .history()
                .list(
                    userId="me",
                    startHistoryId=self._last_history_id,
                    historyTypes=["messageAdded"],
                    labelId="INBOX",
                )
                .execute()
            )
        except Exception as exc:
            # historyId too old or invalid — reset to full scan immediately
            if "404" in str(exc) or "invalid" in str(exc).lower():
                log.warning("History cursor expired — resetting and running full scan now")
                self._last_history_id = self._get_start_history_id(service)
                return self._full_scan(service)
            raise

        # Advance cursor
        new_history_id = history_result.get("historyId")
        if new_history_id:
            self._last_history_id = new_history_id

        # Collect new message IDs
        message_ids: list[str] = []
        for record in history_result.get("history", []):
            for added in record.get("messagesAdded", []):
                msg_id = added.get("message", {}).get("id")
                if msg_id and msg_id not in self._processed_ids:
                    message_ids.append(msg_id)

        if not message_ids:
            return []

        log.info("Gmail incremental scan: %d new message(s)", len(message_ids))
        return self._fetch_messages(service, message_ids)

    def _full_scan(self, service) -> list[Any]:
        """Fallback full scan used only on first run."""
        results = (
            service.users()
            .messages()
            .list(userId="me", q="is:unread is:important", maxResults=20)
            .execute()
        )
        messages = results.get("messages", [])

        for contact in self._known_contacts:
            contact_results = (
                service.users()
                .messages()
                .list(userId="me", q=f"is:unread from:{contact}", maxResults=10)
                .execute()
            )
            messages.extend(contact_results.get("messages", []))

        unique_ids = list({
            m["id"] for m in messages if m["id"] not in self._processed_ids
        })
        return self._fetch_messages(service, unique_ids)

    def _fetch_messages(self, service, message_ids: list[str]) -> list[Any]:
        """Fetch full message payload (headers + body) for a list of message IDs."""
        items = []
        for msg_id in message_ids:
            try:
                full = (
                    service.users()
                    .messages()
                    .get(userId="me", id=msg_id, format="full")
                    .execute()
                )
                items.append(full)
            except Exception:
                log.exception("Failed to fetch message %s", msg_id)
        return items

    @staticmethod
    def _extract_body(payload: dict) -> str:
        """Recursively extract plain-text body from a Gmail message payload."""
        mime_type = payload.get("mimeType", "")
        body_data = payload.get("body", {}).get("data", "")

        if mime_type == "text/plain" and body_data:
            return base64.urlsafe_b64decode(body_data + "==").decode("utf-8", errors="replace")

        for part in payload.get("parts", []):
            text = GmailWatcher._extract_body(part)
            if text:
                return text

        # Fallback: try text/html parts if no plain text found
        for part in payload.get("parts", []):
            if part.get("mimeType") == "text/html":
                data = part.get("body", {}).get("data", "")
                if data:
                    html = base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="replace")
                    # Strip tags crudely — just remove angle-bracket content
                    return re.sub(r"<[^>]+>", " ", html).strip()
        return ""

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

        # Extract full body text (falls back to snippet if empty)
        body_text = self._extract_body(item.get("payload", {})).strip()
        if not body_text:
            body_text = item.get("snippet", "")

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
            f"{body_text}\n\n"
            f"## Suggested Actions\n"
            f"- [ ] Read and classify email\n"
            f"- [ ] Determine response action\n"
        )
        md_path.write_text(md_content, encoding="utf-8")
        self._processed_ids.add(msg_id)

        # Record in contact memory for personalization
        try:
            from src.orchestrator.contact_memory import ContactMemory
            mem = ContactMemory(self.config.vault_path)
            name_match = re.match(r"([^<]+?)\s*<", sender)
            full_name = name_match.group(1).strip() if name_match else ""
            mem.note_interaction(
                email=sender_email or sender,
                full_name=full_name,
                interaction_type="email_received",
                summary=f"Subject: {subject} | {snippet[:120]}",
            )
        except Exception:
            log.debug("Contact memory update failed (non-fatal)", exc_info=True)

        # Tag the email in Gmail so the inbox is self-organizing
        try:
            from src.mcp_servers.gmail_service import GmailService
            svc = GmailService(self.config.gmail_credentials_path)
            svc.apply_label(msg_id, "AI/processed")
            if priority == "high":
                svc.apply_label(msg_id, "AI/high-priority")

            # Check for PDF attachments and append extracted content
            from src.watchers.pdf_processor import PdfProcessor
            processor = PdfProcessor(gmail_service=svc)
            pdf_results = processor.process_email_attachments(msg_id, md_path)
            if pdf_results:
                svc.apply_label(msg_id, "AI/has-attachment")
                log.info(
                    "Processed %d PDF attachment(s) for %s",
                    len(pdf_results), md_path.name,
                )

            # Auto-draft a reply so the user has a starting point in Gmail
            if not self.config.dev_mode:
                self._create_auto_draft(svc, msg_id, sender, subject, md_path)
        except Exception:
            log.debug("Could not apply Gmail label or process attachments (non-fatal)", exc_info=True)

        return md_path


    def _create_auto_draft(
        self,
        svc,
        msg_id: str,
        sender: str,
        subject: str,
        md_path,
    ) -> None:
        """Create a Gmail Draft reply for an inbound email and tag it."""
        try:
            # Extract first name from "Full Name <email>" or bare email
            name_match = re.match(r"([^<]+?)\s*<", sender)
            first_name = name_match.group(1).strip().split()[0] if name_match else "there"

            draft_body = (
                f"Hi {first_name},\n\n"
                f"Thank you for your email. I've received your message and will get back to you shortly.\n\n"
                f"Best regards"
            )
            reply_subject = subject if subject.lower().startswith("re:") else f"Re: {subject}"

            svc.draft_email(to=sender, subject=reply_subject, body=draft_body)
            svc.apply_label(msg_id, "AI/drafted")

            # Note the draft in the action file
            note = "\n> **Auto-draft created** — a reply draft is waiting in your Gmail Drafts folder.\n"
            existing = md_path.read_text(encoding="utf-8")
            md_path.write_text(existing + note, encoding="utf-8")
            log.info("Auto-draft created for %s", md_path.name)
        except Exception:
            log.debug("Auto-draft creation failed (non-fatal)", exc_info=True)


if __name__ == "__main__":
    import sys
    sys.path.insert(0, ".")
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )
    from src.core.config import Config
    watcher = GmailWatcher(Config())
    watcher.run()
