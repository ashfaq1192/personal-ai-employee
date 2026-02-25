"""WhatsApp Business Cloud API client — send messages via Meta Graph API."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from src.core.retry import with_retry

log = logging.getLogger(__name__)

GRAPH_API_BASE = "https://graph.facebook.com/v21.0"


class WhatsAppClient:
    """Sends WhatsApp messages via the official Business Cloud API.

    No page token exchange needed — WhatsApp uses Bearer token directly.
    """

    def __init__(
        self,
        access_token: str,
        phone_number_id: str,
        *,
        dry_run: bool = True,
    ) -> None:
        self._access_token = access_token
        self._phone_number_id = phone_number_id
        self._dry_run = dry_run

    @with_retry(max_attempts=2, base_delay=3.0, max_delay=30.0)
    def send_message(self, to: str, body: str) -> dict[str, Any]:
        """Send a text message to a WhatsApp number.

        Args:
            to: Recipient phone number in E.164 format (e.g. "+923001234567").
            body: Plain-text message body.

        Returns:
            {"status": "sent", "message_id": "..."} or {"status": "dry_run"}.
        """
        if self._dry_run:
            log.info("[DRY_RUN] Would send WhatsApp to %s: %s", to, body[:80])
            return {"status": "dry_run", "to": to}

        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "text",
            "text": {"body": body},
        }
        headers = {"Authorization": f"Bearer {self._access_token}"}
        with httpx.Client() as client:
            resp = client.post(
                f"{GRAPH_API_BASE}/{self._phone_number_id}/messages",
                json=payload,
                headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()
            message_id = (
                data.get("messages", [{}])[0].get("id", "")
                if data.get("messages")
                else ""
            )
            return {"status": "sent", "message_id": message_id}

    @with_retry(max_attempts=2, base_delay=3.0, max_delay=30.0)
    def mark_as_read(self, message_id: str) -> dict[str, Any]:
        """Send a read receipt for an inbound message."""
        if self._dry_run:
            log.info("[DRY_RUN] Would mark as read: %s", message_id)
            return {"status": "dry_run"}

        payload = {
            "messaging_product": "whatsapp",
            "status": "read",
            "message_id": message_id,
        }
        headers = {"Authorization": f"Bearer {self._access_token}"}
        with httpx.Client() as client:
            resp = client.post(
                f"{GRAPH_API_BASE}/{self._phone_number_id}/messages",
                json=payload,
                headers=headers,
            )
            resp.raise_for_status()
            return {"status": "read_receipt_sent"}
