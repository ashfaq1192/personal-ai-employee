"""WhatsApp Business Cloud API — Inbound webhook receiver.

Handles Meta's webhook verification (GET) and inbound message events (POST).
Creates WHATSAPP_*.md files in Needs_Action/ for each inbound message, and
sends a read receipt back to Meta.

Start alongside the dashboard:
    uv run python src/cli/whatsapp_webhook.py

Port: 8081 (dashboard runs on 8080)
Meta webhook URL: https://<your-domain>/whatsapp/webhook
Verify token: WHATSAPP_WEBHOOK_VERIFY_TOKEN from .env
"""

from __future__ import annotations

import json
import logging
import urllib.parse
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv()

from src.core.config import Config
from src.core.logger import AuditLogger
from src.mcp_servers.whatsapp_client import WhatsAppClient

log = logging.getLogger(__name__)

config = Config()
vault = config.vault_path
audit = AuditLogger(vault)
wa_client = WhatsAppClient(
    access_token=config.whatsapp_access_token,
    phone_number_id=config.whatsapp_phone_number_id,
    dry_run=config.dry_run,
)

WEBHOOK_PORT = 8081


def _json_response(h: BaseHTTPRequestHandler, data: Any, status: int = 200) -> None:
    body = json.dumps(data, ensure_ascii=False).encode()
    h.send_response(status)
    h.send_header("Content-Type", "application/json")
    h.send_header("Content-Length", str(len(body)))
    h.end_headers()
    h.wfile.write(body)


def _text_response(h: BaseHTTPRequestHandler, text: str, status: int = 200) -> None:
    body = text.encode()
    h.send_response(status)
    h.send_header("Content-Type", "text/plain")
    h.send_header("Content-Length", str(len(body)))
    h.end_headers()
    h.wfile.write(body)


def _create_whatsapp_file(
    message_id: str,
    from_number: str,
    body: str,
    timestamp: str,
) -> Path:
    """Write a WHATSAPP_*.md action file to Needs_Action/."""
    needs_action = vault / "Needs_Action"
    needs_action.mkdir(parents=True, exist_ok=True)

    ts_safe = timestamp.replace(":", "").replace("-", "")
    filename = f"WHATSAPP_{from_number}_{ts_safe}.md"
    dest = needs_action / filename

    now = datetime.now(timezone.utc)
    content = (
        f"---\n"
        f"type: inbound_whatsapp\n"
        f"from: {from_number}\n"
        f"chat: {from_number}\n"
        f"message_id: {message_id}\n"
        f"received: {now.isoformat()}\n"
        f"timestamp: {timestamp}\n"
        f"priority: normal\n"
        f"status: pending\n"
        f"source: whatsapp_business_api\n"
        f"---\n\n"
        f"# WhatsApp Message from {from_number}\n\n"
        f"{body}\n"
    )
    dest.write_text(content, encoding="utf-8")
    log.info("Created %s", filename)
    return dest


def _handle_inbound(payload: dict) -> dict:
    """Parse Meta webhook payload and create action files."""
    created: list[str] = []
    errors: list[str] = []

    entries = payload.get("entry", [])
    for entry in entries:
        for change in entry.get("changes", []):
            value = change.get("value", {})
            messages = value.get("messages", [])
            for msg in messages:
                msg_id = msg.get("id", "")
                from_number = msg.get("from", "")
                timestamp = msg.get("timestamp", "")
                msg_type = msg.get("type", "")

                if msg_type != "text":
                    log.info("Skipping non-text message type: %s", msg_type)
                    continue

                body = msg.get("text", {}).get("body", "")
                if not from_number or not body:
                    continue

                try:
                    dest = _create_whatsapp_file(msg_id, from_number, body, timestamp)
                    created.append(dest.name)
                    audit.log(
                        action_type="whatsapp_inbound",
                        actor="whatsapp_webhook",
                        target=from_number,
                        parameters={"message_id": msg_id, "preview": body[:80]},
                        result="success",
                    )
                    # Send read receipt
                    if msg_id and not config.dry_run:
                        try:
                            wa_client.mark_as_read(msg_id)
                        except Exception as exc:
                            log.warning("Failed to send read receipt for %s: %s", msg_id, exc)
                except Exception as exc:
                    log.exception("Failed to create action file for message %s: %s", msg_id, exc)
                    errors.append(str(exc)[:100])

    return {"created": created, "errors": errors}


class WebhookHandler(BaseHTTPRequestHandler):
    def log_message(self, *args: Any) -> None:
        pass  # suppress default access log

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        qs = dict(urllib.parse.parse_qsl(parsed.query))

        if parsed.path.rstrip("/") == "/whatsapp/webhook":
            # Meta webhook verification challenge
            mode = qs.get("hub.mode", "")
            token = qs.get("hub.verify_token", "")
            challenge = qs.get("hub.challenge", "")

            if mode == "subscribe" and token == config.whatsapp_webhook_verify_token:
                log.info("Webhook verified by Meta")
                _text_response(self, challenge, 200)
            else:
                log.warning("Webhook verification failed: mode=%s token=%s", mode, token)
                _text_response(self, "Forbidden", 403)
        else:
            _text_response(self, "Not Found", 404)

    def do_POST(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path.rstrip("/") != "/whatsapp/webhook":
            _text_response(self, "Not Found", 404)
            return

        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length else b""
        try:
            payload = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            _json_response(self, {"error": "Invalid JSON"}, 400)
            return

        result = _handle_inbound(payload)
        _json_response(self, result, 200)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    server = HTTPServer(("0.0.0.0", WEBHOOK_PORT), WebhookHandler)
    log.info("WhatsApp webhook listening on port %d", WEBHOOK_PORT)
    log.info("Verify token: %s", config.whatsapp_webhook_verify_token)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log.info("Webhook server stopped")


if __name__ == "__main__":
    main()
