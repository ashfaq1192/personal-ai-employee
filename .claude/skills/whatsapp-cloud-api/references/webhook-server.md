# WhatsApp Webhook Server (Full Implementation)

Runs on port 8081. Uses only stdlib `http.server` — no Flask/FastAPI needed.

```python
# src/cli/whatsapp_webhook.py

from http.server import BaseHTTPRequestHandler, HTTPServer
import json, urllib.parse

WEBHOOK_PORT = 8081

class WebhookHandler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass  # suppress default access log — use your own logger

    def do_GET(self):
        """Meta webhook verification challenge."""
        parsed = urllib.parse.urlparse(self.path)
        qs = dict(urllib.parse.parse_qsl(parsed.query))

        if parsed.path.rstrip("/") == "/whatsapp/webhook":
            mode      = qs.get("hub.mode", "")
            token     = qs.get("hub.verify_token", "")
            challenge = qs.get("hub.challenge", "")

            if mode == "subscribe" and token == config.whatsapp_webhook_verify_token:
                # Respond with plain text challenge — NOT JSON
                body = challenge.encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/plain")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            else:
                self._text_response("Forbidden", 403)
        else:
            self._text_response("Not Found", 404)

    def do_POST(self):
        """Inbound message event."""
        if self.path.rstrip("/") != "/whatsapp/webhook":
            self._text_response("Not Found", 404)
            return

        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length else b""
        payload = json.loads(raw) if raw else {}

        result = _handle_inbound(payload)  # parse + create action files
        self._json_response(result, 200)

    def _json_response(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _text_response(self, text, status=200):
        body = text.encode()
        self.send_response(status)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def _handle_inbound(payload: dict) -> dict:
    """Parse Meta webhook payload. Returns {created: [...], errors: [...]}."""
    created, errors = [], []
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            for msg in change.get("value", {}).get("messages", []):
                if msg.get("type") != "text":
                    continue  # skip images, audio, etc.
                from_number = msg.get("from", "")   # no '+' prefix
                body        = msg.get("text", {}).get("body", "")
                msg_id      = msg.get("id", "")
                timestamp   = msg.get("timestamp", "")
                if not from_number or not body:
                    continue
                try:
                    _create_action_file(msg_id, from_number, body, timestamp)
                    created.append(f"WHATSAPP_{from_number}.md")
                    if msg_id and not config.dry_run:
                        wa_client.mark_as_read(msg_id)
                except Exception as exc:
                    errors.append(str(exc)[:100])
    return {"created": created, "errors": errors}


def main():
    server = HTTPServer(("0.0.0.0", WEBHOOK_PORT), WebhookHandler)
    server.serve_forever()
```

## Action File Created Per Inbound Message

```markdown
---
type: inbound_whatsapp
from: 923001234567
chat: 923001234567
message_id: wamid.xxx
received: 2024-01-15T10:30:00+00:00
timestamp: 1705315800
priority: normal
status: pending
source: whatsapp_business_api
---

# WhatsApp Message from 923001234567

The actual message body text goes here.
```

Written to `{vault}/Needs_Action/WHATSAPP_{from}_{timestamp}.md`. The orchestrator watchdog picks this up and routes it for processing.

## Running Alongside Dashboard

```bash
# Dashboard on 8080, webhook on 8081
uv run web-dashboard &
uv run python src/cli/whatsapp_webhook.py
```

## Exposing to Meta (for local dev)

```bash
# ngrok for local testing
ngrok http 8081
# Copy the https URL → Meta App Dashboard → WhatsApp → Configuration → Webhook URL
# URL: https://abc123.ngrok.io/whatsapp/webhook
```
