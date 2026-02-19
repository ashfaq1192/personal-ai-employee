"""Gmail API service wrapper — shared between email_mcp and gmail_watcher."""

from __future__ import annotations

import base64
import logging
import mimetypes
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any

from src.core.retry import with_retry

log = logging.getLogger(__name__)


class GmailService:
    """Encapsulates Gmail API operations."""

    def __init__(self, credentials_path: Path) -> None:
        self._creds_path = credentials_path
        self._service = None

    def _get_service(self):
        if self._service is not None:
            return self._service

        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build

        creds = Credentials.from_authorized_user_file(str(self._creds_path))
        if creds.expired and creds.refresh_token:
            from google.auth.transport.requests import Request
            creds.refresh(Request())
            self._creds_path.write_text(creds.to_json(), encoding="utf-8")

        self._service = build("gmail", "v1", credentials=creds)
        return self._service

    @with_retry(max_attempts=3, base_delay=2.0, max_delay=30.0)
    def send_email(
        self,
        to: str,
        subject: str,
        body: str,
        *,
        attachment: str | None = None,
        reply_to_id: str | None = None,
    ) -> dict[str, Any]:
        """Send an email via Gmail API."""
        service = self._get_service()

        if attachment:
            msg = MIMEMultipart()
            msg.attach(MIMEText(body, "plain"))
            att_path = Path(attachment)
            if att_path.exists():
                content_type, _ = mimetypes.guess_type(str(att_path))
                main_type, sub_type = (content_type or "application/octet-stream").split("/", 1)
                part = MIMEBase(main_type, sub_type)
                part.set_payload(att_path.read_bytes())
                part.add_header("Content-Disposition", "attachment", filename=att_path.name)
                msg.attach(part)
        else:
            msg = MIMEText(body)

        msg["to"] = to
        msg["subject"] = subject

        if reply_to_id:
            msg["In-Reply-To"] = reply_to_id
            msg["References"] = reply_to_id

        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        result = service.users().messages().send(userId="me", body={"raw": raw}).execute()
        return {"message_id": result.get("id", ""), "status": "sent"}

    def draft_email(self, to: str, subject: str, body: str, *, attachment: str | None = None) -> dict[str, Any]:
        """Create a draft email."""
        service = self._get_service()
        msg = MIMEText(body)
        msg["to"] = to
        msg["subject"] = subject
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        result = service.users().drafts().create(userId="me", body={"message": {"raw": raw}}).execute()
        return {"draft_id": result.get("id", ""), "status": "drafted"}

    @with_retry(max_attempts=2, base_delay=1.0, max_delay=10.0)
    def search_email(self, query: str, max_results: int = 10) -> list[dict[str, Any]]:
        """Search Gmail inbox."""
        service = self._get_service()
        results = service.users().messages().list(
            userId="me", q=query, maxResults=min(max_results, 50)
        ).execute()

        messages = []
        for msg in results.get("messages", []):
            full = service.users().messages().get(userId="me", id=msg["id"], format="metadata").execute()
            headers = {h["name"]: h["value"] for h in full.get("payload", {}).get("headers", [])}
            messages.append({
                "id": msg["id"],
                "from": headers.get("From", ""),
                "subject": headers.get("Subject", ""),
                "date": headers.get("Date", ""),
                "snippet": full.get("snippet", ""),
            })

        return messages
