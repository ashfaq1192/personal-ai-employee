---
name: whatsapp-cloud-api
description: "Setup and integration guide for WhatsApp Business Cloud API (Meta Graph API). Use when setting up WhatsApp Business credentials, sending messages via the Cloud API, handling inbound webhook events, or debugging WhatsApp API errors. Covers the two paths (Path A: Playwright/browser automation — legacy/avoid; Path B: Cloud API — correct approach), required env vars, sending messages, read receipts, and the inbound webhook server pattern."
---

# WhatsApp Business Cloud API

## Path A vs Path B — Critical Decision

**Path A (Playwright browser automation):** Fragile, breaks on WhatsApp Web UI changes, requires active browser session. **Do not use** for production.

**Path B (Business Cloud API):** Official Meta API, stable, token-based. **Always use this.**

This skill covers Path B only.

## Required .env Keys

```
WHATSAPP_PHONE_NUMBER_ID=<numeric ID from Meta developer dashboard>
WHATSAPP_BUSINESS_ACCOUNT_ID=<numeric WABA ID>
WHATSAPP_ACCESS_TOKEN=<token — can reuse META_ACCESS_TOKEN>
WHATSAPP_WEBHOOK_VERIFY_TOKEN=<any string you choose, e.g. "my_verify_token">
```

`WHATSAPP_ACCESS_TOKEN` falls back to `META_ACCESS_TOKEN` automatically in Config.

## Where to Find the IDs

In [Meta for Developers](https://developers.facebook.com):
- App Dashboard → WhatsApp → API Setup
- `Phone number ID` → `WHATSAPP_PHONE_NUMBER_ID`
- `WhatsApp Business Account ID` → `WHATSAPP_BUSINESS_ACCOUNT_ID`
- The access token shown here is a temporary test token (24h) — extend it using the same Extend Token flow from meta-setup skill for a 60-day token

## Sending a Message

```python
# Uses Bearer token directly — no page token exchange needed (unlike FB/IG)
GRAPH_API_BASE = "https://graph.facebook.com/v21.0"

payload = {
    "messaging_product": "whatsapp",
    "to": "+923001234567",          # E.164 format — must include country code
    "type": "text",
    "text": {"body": "Hello!"},
}
headers = {"Authorization": f"Bearer {access_token}"}
resp = httpx.post(
    f"{GRAPH_API_BASE}/{phone_number_id}/messages",
    json=payload,
    headers=headers,
)
resp.raise_for_status()
message_id = resp.json()["messages"][0]["id"]
```

**Key difference from Facebook/Instagram:** WhatsApp uses `Bearer {token}` header directly, NOT a page token exchange.

## Sending a Read Receipt

```python
payload = {
    "messaging_product": "whatsapp",
    "status": "read",
    "message_id": inbound_message_id,
}
httpx.post(f"{GRAPH_API_BASE}/{phone_number_id}/messages",
           json=payload, headers=headers)
```

## Inbound Webhook Setup

### 1. Register the webhook in Meta Dashboard
- App → WhatsApp → Configuration → Webhook URL: `https://your-domain.com/whatsapp/webhook`
- Verify Token: must match `WHATSAPP_WEBHOOK_VERIFY_TOKEN` in your .env
- Subscribe to: `messages`

### 2. Webhook verification (GET)
Meta sends a GET with `hub.mode=subscribe`, `hub.verify_token`, `hub.challenge`. Return the `hub.challenge` value as plain text with HTTP 200.

```python
if mode == "subscribe" and token == config.whatsapp_webhook_verify_token:
    respond_with(challenge, 200)  # plain text, not JSON
```

### 3. Inbound message payload (POST)
```json
{
  "entry": [{
    "changes": [{
      "value": {
        "messages": [{
          "id": "wamid.xxx",
          "from": "923001234567",
          "type": "text",
          "text": {"body": "Hello"},
          "timestamp": "1700000000"
        }]
      }
    }]
  }]
}
```

Parse path: `entry[0].changes[0].value.messages[0]`

Only `type == "text"` messages have a `.text.body`. Skip other types (image, audio, etc.) or handle separately.

## Webhook Server (stdlib, no framework needed)

The working codebase runs the webhook on port 8081 using `http.server.HTTPServer` — no Flask/FastAPI dependency needed for simple cases. See `references/webhook-server.md` for the full annotated implementation.

## Common Errors

| Error | Cause | Fix |
|-------|-------|-----|
| `131030` | Recipient phone not on WhatsApp | Verify number, use E.164 format with `+` |
| `131047` | Outside 24h messaging window | Use template messages for cold outreach |
| `100` - Invalid parameter | Wrong `phone_number_id` | Double-check the ID from App Dashboard, not from the WABA |
| `190` - Token expired | Access token expired | Re-generate (same flow as meta-setup) |
| Webhook `403` on verification | Verify token mismatch | `WHATSAPP_WEBHOOK_VERIFY_TOKEN` must exactly match what's in Meta Dashboard |

## Testing Without a Real Device

In Meta App Dashboard → WhatsApp → API Setup, there's a test number you can use to send messages to your own WhatsApp for free during development. No real phone number needed for initial testing.
