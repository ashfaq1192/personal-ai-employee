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


_TASK_PREFIXES = ("task:", "todo:", "do:", "create task:", "add task:")
_REMIND_PREFIXES = ("remind:", "reminder:", "remind me:")
_MEETING_KEYWORDS = ("let's meet", "lets meet", "schedule a call", "schedule a meeting",
                     "book a call", "can we meet", "availability", "free for a call")


def _detect_intent(body: str) -> tuple[str, str]:
    """Detect message intent. Returns (intent, priority)."""
    lower = body.lower().strip()
    if any(lower.startswith(p) for p in _TASK_PREFIXES):
        return "task", "high"
    if any(lower.startswith(p) for p in _REMIND_PREFIXES):
        return "reminder", "normal"
    if any(kw in lower for kw in _MEETING_KEYWORDS):
        return "meeting_request", "high"
    return "general", "normal"


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
    intent, priority = _detect_intent(body)

    content = (
        f"---\n"
        f"type: inbound_whatsapp\n"
        f"intent: {intent}\n"
        f"from: {from_number}\n"
        f"chat: {from_number}\n"
        f"message_id: {message_id}\n"
        f"received: {now.isoformat()}\n"
        f"timestamp: {timestamp}\n"
        f"priority: {priority}\n"
        f"status: pending\n"
        f"source: whatsapp_business_api\n"
        f"---\n\n"
        f"# WhatsApp Message from {from_number}\n\n"
        f"**Intent**: {intent}\n\n"
        f"{body}\n\n"
        f"## Suggested Actions\n"
        f"- [ ] Process {intent} request\n"
        f"- [ ] Send reply to {from_number}\n"
    )
    dest.write_text(content, encoding="utf-8")
    log.info("Created %s (intent=%s)", filename, intent)
    return dest


def _send_acknowledgement(from_number: str, intent: str) -> None:
    """Send an immediate acknowledgement reply via WhatsApp."""
    if config.dry_run:
        log.info("[DRY_RUN] Would ack %s (intent=%s)", from_number, intent)
        return
    ack_messages = {
        "task": "Got it! I've added that to my task list and will get it done. I'll update you when complete.",
        "reminder": "Reminder noted! I'll remind you at the right time.",
        "meeting_request": "Sure! Let me check my calendar and I'll send you some available time slots shortly.",
        "general": "Message received! I'm on it and will get back to you shortly.",
    }
    msg = ack_messages.get(intent, ack_messages["general"])
    try:
        wa_client.send_message(to=from_number, body=msg)
        log.info("Acknowledgement sent to %s", from_number)
    except Exception as exc:
        log.warning("Failed to send ack to %s: %s", from_number, exc)


def _transcribe_audio(audio_bytes: bytes, mime_type: str) -> str:
    """Transcribe audio bytes using OpenAI Whisper. Returns transcription or empty string."""
    api_key = config.openai_api_key
    if not api_key:
        log.info("OPENAI_API_KEY not set — skipping Whisper transcription")
        return ""
    try:
        import openai
        import io
        ext = "ogg"
        if "mpeg" in mime_type or "mp3" in mime_type:
            ext = "mp3"
        elif "mp4" in mime_type or "m4a" in mime_type:
            ext = "mp4"
        client = openai.OpenAI(api_key=api_key)
        audio_file = io.BytesIO(audio_bytes)
        audio_file.name = f"voice.{ext}"
        result = client.audio.transcriptions.create(model="whisper-1", file=audio_file)
        return result.text.strip()
    except ImportError:
        log.warning("openai package not installed — Whisper unavailable")
        return ""
    except Exception as exc:
        log.warning("Whisper transcription failed: %s", exc)
        return ""


def _handle_voice_message(
    msg_id: str, from_number: str, msg: dict, timestamp: str
) -> None:
    """Download, (optionally) transcribe, and create an action file for a voice note."""
    needs_action = vault / "Needs_Action"
    needs_action.mkdir(parents=True, exist_ok=True)
    media_dir = vault / "media"
    media_dir.mkdir(parents=True, exist_ok=True)

    audio_info = msg.get("audio", {})
    media_id   = audio_info.get("id", "")
    mime_type  = audio_info.get("mime_type", "audio/ogg")
    now        = datetime.now(timezone.utc)

    # Download audio
    audio_bytes = b""
    audio_path  = None
    if media_id and not config.dry_run:
        try:
            audio_bytes = wa_client.download_media(media_id)
            ext = "ogg" if "ogg" in mime_type else "mp3"
            audio_path = media_dir / f"VOICE_{msg_id[:12]}.{ext}"
            audio_path.write_bytes(audio_bytes)
            log.info("Voice note saved: %s (%d bytes)", audio_path.name, len(audio_bytes))
        except Exception as exc:
            log.warning("Failed to download voice note %s: %s", media_id, exc)

    # Transcribe
    transcription = ""
    if audio_bytes:
        transcription = _transcribe_audio(audio_bytes, mime_type)

    # Determine body for intent detection
    body = transcription if transcription else "[voice message — transcription unavailable]"
    intent, priority = _detect_intent(transcription or "")
    if not transcription:
        intent, priority = "voice_note", "normal"

    ts_safe = timestamp.replace(":", "").replace("-", "")
    filename = f"WHATSAPP_{from_number}_{ts_safe}_voice.md"
    dest = needs_action / filename

    transcription_block = (
        f"**Transcription:**\n{transcription}\n"
        if transcription
        else "*Transcription unavailable — OPENAI_API_KEY not configured or Whisper failed.*\n"
        f"Audio file: `{audio_path.name if audio_path else 'not saved'}`\n"
    )

    content = (
        f"---\n"
        f"type: inbound_whatsapp\n"
        f"subtype: voice_note\n"
        f"intent: {intent}\n"
        f"from: {from_number}\n"
        f"message_id: {msg_id}\n"
        f"received: {now.isoformat()}\n"
        f"timestamp: {timestamp}\n"
        f"priority: {priority}\n"
        f"status: pending\n"
        f"audio_file: {audio_path.name if audio_path else ''}\n"
        f"transcribed: {'yes' if transcription else 'no'}\n"
        f"source: whatsapp_business_api\n"
        f"---\n\n"
        f"# Voice Note from {from_number}\n\n"
        f"{transcription_block}\n"
        f"## Suggested Actions\n"
        f"- [ ] {'Review transcription and act on request' if transcription else 'Listen to audio and transcribe manually'}\n"
        f"- [ ] Reply to {from_number}\n"
    )
    dest.write_text(content, encoding="utf-8")
    log.info("Voice note action file created: %s (transcribed=%s)", filename, bool(transcription))

    audit.log(
        action_type="whatsapp_voice_inbound",
        actor="whatsapp_webhook",
        target=from_number,
        parameters={
            "message_id": msg_id,
            "transcribed": bool(transcription),
            "audio_bytes": len(audio_bytes),
        },
        result="success",
    )

    # Ack and read receipt
    ack = (
        "Voice note received! I've transcribed it and will action it shortly."
        if transcription else
        "Voice note received! Processing your voice message now."
    )
    _send_acknowledgement(from_number, intent)
    if msg_id and not config.dry_run:
        try:
            wa_client.mark_as_read(msg_id)
        except Exception as exc:
            log.warning("Failed to send read receipt for voice %s: %s", msg_id, exc)


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

                if msg_type == "audio":
                    try:
                        _handle_voice_message(msg_id, from_number, msg, timestamp)
                        created.append(f"VOICE_{msg_id[:12]}.md")
                    except Exception as exc:
                        log.exception("Voice message handling failed: %s", exc)
                        errors.append(str(exc)[:100])
                    continue

                if msg_type != "text":
                    log.info("Skipping non-text message type: %s", msg_type)
                    continue

                body = msg.get("text", {}).get("body", "")
                if not from_number or not body:
                    continue

                try:
                    dest = _create_whatsapp_file(msg_id, from_number, body, timestamp)
                    intent, _ = _detect_intent(body)
                    created.append(dest.name)
                    audit.log(
                        action_type="whatsapp_inbound",
                        actor="whatsapp_webhook",
                        target=from_number,
                        parameters={"message_id": msg_id, "intent": intent, "preview": body[:80]},
                        result="success",
                    )
                    # Send read receipt
                    if msg_id and not config.dry_run:
                        try:
                            wa_client.mark_as_read(msg_id)
                        except Exception as exc:
                            log.warning("Failed to send read receipt for %s: %s", msg_id, exc)
                    # Auto-reply acknowledgement
                    _send_acknowledgement(from_number, intent)
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
