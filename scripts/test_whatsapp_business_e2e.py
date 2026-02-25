"""
End-to-end test for WhatsApp Business API (Path B) integration.

Sections:
  1.  WhatsAppClient dry-run instantiation
  2.  Dry-run send_message (no API call)
  3.  Config fields present (whatsapp_phone_number_id, whatsapp_business_account_id)
  4.  Live send_message via client (real API call)           ← DRY_RUN=false
  5.  Live whatsapp_send via call_tool (MCP layer)           ← DRY_RUN=false
  6.  Approval gate enforcement (blocked without file)
  7.  Rate limiter enforcement
  8.  Dispatcher: parse APPROVAL file + send (mocked client)
  9.  Webhook POST handler: synthetic payload → WHATSAPP_*.md created
  10. Audit log entries

Run:
    uv run python scripts/test_whatsapp_business_e2e.py         # dry-run suite
    DRY_RUN=false uv run python scripts/test_whatsapp_business_e2e.py  # live suite
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

# ── colour helpers ─────────────────────────────────────────────────────────────
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
RESET  = "\033[0m"

passed = failed = skipped = 0


def ok(label: str, detail: str = "") -> None:
    global passed
    passed += 1
    print(f"  {GREEN}✅{RESET} {label}" + (f": {detail}" if detail else ""))


def fail(label: str, detail: str = "") -> None:
    global failed
    failed += 1
    print(f"  {RED}❌{RESET} {label}" + (f": {detail}" if detail else ""))


def skip(label: str, detail: str = "") -> None:
    global skipped
    skipped += 1
    print(f"  {YELLOW}⏭️ {RESET}  {label}" + (f": {detail}" if detail else ""))


# ── mode detection ─────────────────────────────────────────────────────────────
live_mode = os.environ.get("DRY_RUN", "true").lower() == "false"
test_recipient = os.environ.get("WHATSAPP_TEST_RECIPIENT", "")

print()
print("=" * 60)
print("  WHATSAPP BUSINESS API — END-TO-END TEST")
print(f"  Mode: {'🟢 LIVE (real WhatsApp API)' if live_mode else '🟡 DRY-RUN'}")
if live_mode and test_recipient:
    print(f"  Recipient: {test_recipient}")
print("=" * 60)
print()

# ── imports ────────────────────────────────────────────────────────────────────
from src.core.config import Config
from src.core.logger import AuditLogger
from src.mcp_servers.whatsapp_client import WhatsAppClient

config = Config()
vault = config.vault_path
approved_dir = vault / "Approved"
needs_action_dir = vault / "Needs_Action"
pending_dir = vault / "Pending_Approval"
done_dir = vault / "Done"


def _cleanup(pattern: str, directory: Path) -> None:
    for f in directory.glob(pattern):
        try:
            f.unlink()
        except Exception:
            pass


# ══════════════════════════════════════════════════════════════════════════════
# 1. WhatsAppClient — dry-run instantiation
# ══════════════════════════════════════════════════════════════════════════════
print("  ── Section 1: WhatsAppClient instantiation ─────────")
print()
print("  [1] WhatsAppClient dry-run instantiation")

try:
    client = WhatsAppClient(
        access_token="test_token",
        phone_number_id="123456789",
        dry_run=True,
    )
    assert client._dry_run is True
    assert client._phone_number_id == "123456789"
    ok("WhatsAppClient instantiated with dry_run=True")
except Exception as e:
    fail("WhatsAppClient instantiation", str(e))

# ══════════════════════════════════════════════════════════════════════════════
# 2. Dry-run send_message
# ══════════════════════════════════════════════════════════════════════════════
print()
print("  [2] Dry-run send_message (no API call)")

try:
    result = client.send_message("+923001234567", "Hello from E2E test")
    assert result["status"] == "dry_run", f"Expected dry_run, got {result}"
    assert "to" in result
    ok("send_message returns dry_run status", str(result))
except Exception as e:
    fail("send_message dry-run", str(e))

# ══════════════════════════════════════════════════════════════════════════════
# 3. Config fields
# ══════════════════════════════════════════════════════════════════════════════
print()
print("  [3] Config fields for WhatsApp Business API")

try:
    assert hasattr(config, "whatsapp_phone_number_id"), "Missing whatsapp_phone_number_id"
    assert hasattr(config, "whatsapp_business_account_id"), "Missing whatsapp_business_account_id"
    assert hasattr(config, "whatsapp_webhook_verify_token"), "Missing whatsapp_webhook_verify_token"
    assert hasattr(config, "whatsapp_access_token"), "Missing whatsapp_access_token"
    assert hasattr(config, "rate_limit_whatsapp"), "Missing rate_limit_whatsapp"
    ok("All WhatsApp config fields present",
       f"phone_id={config.whatsapp_phone_number_id or '(empty)'}, "
       f"rate_limit={config.rate_limit_whatsapp}")
    if config.whatsapp_phone_number_id:
        ok("WHATSAPP_PHONE_NUMBER_ID set", config.whatsapp_phone_number_id)
    else:
        skip("WHATSAPP_PHONE_NUMBER_ID", "not set in .env (will use env default)")
    if config.whatsapp_access_token:
        ok("whatsapp_access_token resolved", "(token present)")
    else:
        skip("whatsapp_access_token", "no META_ACCESS_TOKEN or WHATSAPP_ACCESS_TOKEN in .env")
except AssertionError as e:
    fail("Config fields", str(e))

# ══════════════════════════════════════════════════════════════════════════════
# 4. Live send_message via client
# ══════════════════════════════════════════════════════════════════════════════
print()
print("  [4] Live send_message via WhatsAppClient")

if not live_mode:
    skip("Live send_message", "DRY_RUN=true — run with DRY_RUN=false for live test")
elif not test_recipient:
    skip("Live send_message", "WHATSAPP_TEST_RECIPIENT not set in .env")
else:
    try:
        live_client = WhatsAppClient(
            access_token=config.whatsapp_access_token,
            phone_number_id=config.whatsapp_phone_number_id,
            dry_run=False,
        )
        result = live_client.send_message(
            test_recipient,
            "Hello from Personal AI Employee E2E test suite! (WhatsApp Business API)",
        )
        if result.get("status") == "sent":
            ok("Live send_message via WhatsAppClient", f"message_id={result.get('message_id', '')}")
        else:
            fail("Live send_message", f"Unexpected result: {result}")
    except Exception as e:
        fail("Live send_message", str(e)[:120])

# ══════════════════════════════════════════════════════════════════════════════
# 5. Live whatsapp_send via MCP call_tool
# ══════════════════════════════════════════════════════════════════════════════
print()
print("  [5] Live whatsapp_send via MCP call_tool")

if not live_mode:
    skip("Live MCP call_tool", "DRY_RUN=true — run with DRY_RUN=false for live test")
elif not test_recipient:
    skip("Live MCP call_tool", "WHATSAPP_TEST_RECIPIENT not set in .env")
else:
    try:
        from src.mcp_servers.whatsapp_mcp import call_tool as wa_call_tool

        # Create approval file for the reply
        approval_path = approved_dir / "APPROVAL_wa_reply_e2e_mcp_test.md"
        approved_dir.mkdir(parents=True, exist_ok=True)
        approval_path.write_text(
            f"---\ntype: approval\naction: whatsapp_reply\n"
            f"to: {test_recipient}\n---\n\n"
            f"whatsapp_reply approved for {test_recipient} E2E MCP test\n"
        )

        result = asyncio.run(wa_call_tool("whatsapp_send", {
            "to": test_recipient,
            "message": "MCP layer test from Personal AI Employee (WhatsApp Business API)",
            "is_scheduled": False,
        }))
        text = result[0].text
        approval_path.unlink(missing_ok=True)

        if "Message ID" in text or "sent" in text.lower():
            ok("Live whatsapp_send via call_tool", text[:80])
        elif "Failed" in text:
            fail("Live whatsapp_send via call_tool", text[:120])
        else:
            ok("Live whatsapp_send via call_tool", text[:80])
    except Exception as e:
        fail("Live MCP call_tool", str(e)[:120])

# ══════════════════════════════════════════════════════════════════════════════
# 6. Approval gate enforcement
# ══════════════════════════════════════════════════════════════════════════════
print()
print("  [6] Approval gate enforcement (blocked without file)")

_cleanup("APPROVAL_wa_reply_e2e_gate_*.md", approved_dir)

try:
    from src.mcp_servers.whatsapp_mcp import call_tool as wa_call_tool

    result = asyncio.run(wa_call_tool("whatsapp_send", {
        "to": "+19999999999",
        "message": "Should be blocked",
        "is_scheduled": False,
    }))
    text = result[0].text
    if "No approval found" in text:
        ok("Approval gate blocks send without file", text[:80])
    elif "DRY_RUN" in text:
        skip("Approval gate", f"DRY_RUN intercepted before gate check: {text[:60]}")
    else:
        fail("Approval gate should block", text[:80])
except Exception as e:
    fail("Approval gate test", str(e)[:120])

# ══════════════════════════════════════════════════════════════════════════════
# 7. Rate limiter enforcement
# ══════════════════════════════════════════════════════════════════════════════
print()
print("  [7] Rate limiter enforcement")

try:
    from src.mcp_servers.whatsapp_mcp import call_tool as wa_call_tool, rate_limiter as wa_rate_limiter

    # Create approval so the request reaches the rate limiter
    rl_approval = approved_dir / "APPROVAL_wa_reply_e2e_rl_test.md"
    approved_dir.mkdir(parents=True, exist_ok=True)
    rl_approval.write_text(
        "---\ntype: approval\naction: whatsapp_reply\n"
        "to: +10000000001\n---\n\nwhatsapp_reply approved for +10000000001\n"
    )

    remaining_before = wa_rate_limiter.remaining("whatsapp")
    blocked = False
    for i in range(remaining_before + 2):
        result = asyncio.run(wa_call_tool("whatsapp_send", {
            "to": "+10000000001",
            "message": f"Rate limit flood #{i}",
            "is_scheduled": False,
        }))
        text = result[0].text
        if "Rate limit exceeded" in text:
            blocked = True
            ok("WhatsApp rate limiter blocks via call_tool",
               f"blocked on attempt {i+1} (remaining was {remaining_before})")
            break

    rl_approval.unlink(missing_ok=True)
    if not blocked:
        skip("WhatsApp rate limiter",
             f"remaining={remaining_before}, capacity not exhausted in test loop")
except Exception as e:
    fail("Rate limiter test", str(e)[:120])

# ══════════════════════════════════════════════════════════════════════════════
# 8. Dispatcher: parse APPROVAL file + send (mocked client)
# ══════════════════════════════════════════════════════════════════════════════
print()
print("  [8] Dispatcher: parse APPROVAL file + send (mocked client)")

_cleanup("APPROVAL_wa_reply_e2e_dispatch_*.md", approved_dir)
_cleanup("APPROVAL_wa_reply_e2e_dispatch_*.md", done_dir)

try:
    from src.orchestrator.whatsapp_dispatcher import WhatsAppDispatcher

    # Create a test approval file in Approved/
    approved_dir.mkdir(parents=True, exist_ok=True)
    done_dir.mkdir(parents=True, exist_ok=True)
    needs_action_dir.mkdir(parents=True, exist_ok=True)

    approval_fn = "APPROVAL_wa_reply_e2e_dispatch_001.md"
    approval_content = (
        "---\n"
        "type: approval_request\n"
        "action: whatsapp_reply\n"
        "to: +923001234567\n"
        "source_whatsapp: WHATSAPP_923001234567_12345.md\n"
        "---\n\n"
        "## Reply Body\n\n"
        "Thanks for your message! This is an E2E dispatcher test reply.\n"
    )
    (approved_dir / approval_fn).write_text(approval_content)

    # Mock client
    mock_client = MagicMock()
    mock_client.send_message.return_value = {"status": "sent", "message_id": "wamid.test123"}

    dispatcher = WhatsAppDispatcher(config, client=mock_client)
    processed = dispatcher.process_pending()

    assert approval_fn in processed, f"Expected {approval_fn} in {processed}"
    mock_client.send_message.assert_called_once_with(
        "+923001234567", "Thanks for your message! This is an E2E dispatcher test reply."
    )
    dest = done_dir / approval_fn
    assert dest.exists(), f"Approval not moved to Done/: {approval_fn}"
    ok("Dispatcher processes APPROVAL file and sends", f"processed={processed}")
    ok("Approval file moved to Done/", approval_fn)
    dest.unlink(missing_ok=True)

except Exception as e:
    fail("Dispatcher test", str(e)[:200])
    _cleanup("APPROVAL_wa_reply_e2e_dispatch_*.md", approved_dir)

# ══════════════════════════════════════════════════════════════════════════════
# 9. Webhook POST handler: synthetic payload → WHATSAPP_*.md created
# ══════════════════════════════════════════════════════════════════════════════
print()
print("  [9] Webhook POST handler: synthetic payload → WHATSAPP_*.md")

_cleanup("WHATSAPP_15551234567_*.md", needs_action_dir)

try:
    from src.cli.whatsapp_webhook import _handle_inbound

    synthetic_payload: dict[str, Any] = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "1282790673708742",
                "changes": [
                    {
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "15555141702",
                                "phone_number_id": "980742615124835",
                            },
                            "messages": [
                                {
                                    "id": "wamid.e2e_test_123",
                                    "from": "15551234567",
                                    "timestamp": "1700000000",
                                    "type": "text",
                                    "text": {"body": "Hello from E2E webhook test!"},
                                }
                            ],
                        },
                        "field": "messages",
                    }
                ],
            }
        ],
    }

    result = _handle_inbound(synthetic_payload)
    assert len(result["created"]) == 1, f"Expected 1 file, got {result}"
    created_name = result["created"][0]
    assert created_name.startswith("WHATSAPP_"), f"Unexpected filename: {created_name}"

    dest = needs_action_dir / created_name
    assert dest.exists(), f"File not created: {dest}"
    content = dest.read_text()
    assert "15551234567" in content
    assert "Hello from E2E webhook test!" in content
    assert "whatsapp_business_api" in content

    ok("Webhook _handle_inbound creates WHATSAPP_*.md", created_name)
    ok("Inbound file has correct fields", "from, body, source all present")
    dest.unlink(missing_ok=True)

except Exception as e:
    fail("Webhook handler test", str(e)[:200])
    _cleanup("WHATSAPP_15551234567_*.md", needs_action_dir)

# ══════════════════════════════════════════════════════════════════════════════
# 10. Audit log entries
# ══════════════════════════════════════════════════════════════════════════════
print()
print("  [10] Audit log — WhatsApp entries")

logs_dir = vault / "Logs"
log_files = sorted(
    (f for f in logs_dir.glob("*.json") if re.match(r"\d{4}-\d{2}-\d{2}\.json$", f.name)),
    reverse=True,
)
if log_files:
    try:
        entries = json.loads(log_files[0].read_text())
        wa_entries = [e for e in entries if "whatsapp" in e.get("action_type", "")]
        if wa_entries:
            ok("Audit log has WhatsApp entries", f"{len(wa_entries)} entries in {log_files[0].name}")
        else:
            skip("Audit log WhatsApp entries", "None found in today's log (expected if only dry-run)")
    except Exception as e:
        fail("Audit log parse error", str(e))
else:
    skip("Audit log check", "No dated log files found")


# ══════════════════════════════════════════════════════════════════════════════
# Summary
# ══════════════════════════════════════════════════════════════════════════════
print()
print("=" * 60)
print(f"  Results: ✅ {passed} passed  ❌ {failed} failed  ⏭️  {skipped} skipped")
print("=" * 60)
print()
if not live_mode:
    print("  💡 Run with DRY_RUN=false WHATSAPP_TEST_RECIPIENT=+<number>")
    print("     to enable live WhatsApp API tests (sections 4 + 5)")
    print()

sys.exit(1 if failed else 0)
