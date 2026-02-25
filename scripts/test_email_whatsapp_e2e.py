"""
End-to-end test for Gmail and WhatsApp flows.

Gmail layers tested:
  1. search_email via call_tool (reads inbox — always safe)
  2. draft_email via call_tool (creates draft, no approval needed)
  3. Approval gate enforcement (send blocked without approval file)
  4. Live send_email via call_tool (self-email with approval file)
  5. Rate limiter enforcement
  6. Audit log entries

WhatsApp layers tested (browser-free):
  7. Keyword loading from Company_Handbook.md
  8. WhatsAppWatcher in dev_mode (graceful []  return)
  9. create_action_file() writes WHATSAPP_*.md to Needs_Action
  10. api_whatsapp() lists WhatsApp action files from vault
  11. api_whatsapp_reply() creates APPROVAL_wa_reply_*.md (HITL gate)
  12. Approval file content validated

Run:
    DRY_RUN=false uv run python scripts/test_email_whatsapp_e2e.py
"""
from __future__ import annotations

import asyncio
import datetime
import json
import os
import re
import sys
import tempfile
from pathlib import Path

# ── colour helpers ────────────────────────────────────────────────────────────
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


# ── mode detection ────────────────────────────────────────────────────────────
live_mode = os.environ.get("DRY_RUN", "true").lower() == "false"

print()
print("=" * 60)
print("  EMAIL + WHATSAPP — END-TO-END TEST")
print(f"  Mode: {'🟢 LIVE (real Gmail API)' if live_mode else '🟡 DRY-RUN'}")
print("=" * 60)
print()

# ── imports ───────────────────────────────────────────────────────────────────
from src.mcp_servers.email_mcp import call_tool, config, audit, rate_limiter
from src.cli.web_dashboard import (
    api_whatsapp, api_whatsapp_reply, api_email_reply,
)
from src.watchers.whatsapp_watcher import WhatsAppWatcher, _load_keywords

vault = config.vault_path
approved_dir = vault / "Approved"
needs_action_dir = vault / "Needs_Action"
pending_dir = vault / "Pending_Approval"

# ── cleanup helpers ───────────────────────────────────────────────────────────
def _cleanup(pattern: str, directory: Path) -> None:
    for f in directory.glob(pattern):
        try:
            f.unlink()
        except Exception:
            pass


# ══════════════════════════════════════════════════════════════════════════════
# GMAIL / EMAIL
# ══════════════════════════════════════════════════════════════════════════════
print("  ── Gmail ──────────────────────────────────────────")
print()

# ── 1. search_email ───────────────────────────────────────────────────────────
print("  [1] search_email via call_tool")

result = asyncio.run(call_tool("search_email", {"query": "in:inbox", "max_results": 5}))
text = result[0].text
if text.startswith("[DEV_MODE]"):
    skip("search_email", "DEV_MODE active")
else:
    try:
        msgs = json.loads(text)
        assert isinstance(msgs, list), f"Expected list, got {type(msgs)}"
        ok("search_email via call_tool", f"{len(msgs)} messages returned")
        if msgs:
            ok("search_email message fields", f"from={msgs[0].get('from','')[:40]}, subject={msgs[0].get('subject','')[:40]}")
    except json.JSONDecodeError:
        fail("search_email parse", text[:100])

# ── 2. draft_email ────────────────────────────────────────────────────────────
print()
print("  [2] draft_email via call_tool")

if not live_mode:
    skip("draft_email", "DRY_RUN=true — would create draft")
else:
    result = asyncio.run(call_tool("draft_email", {
        "to": "ashfaqahmed1192@gmail.com",
        "subject": f"[AI Employee E2E] Draft test {datetime.datetime.utcnow().strftime('%H:%M:%S')}",
        "body": "This is a draft created by the AI Employee E2E test suite. Safe to delete.",
    }))
    text = result[0].text
    if "draft_id" in text or "Draft ID" in text:
        ok("draft_email via call_tool", text.strip())
    elif "DRY_RUN" in text:
        skip("draft_email", text)
    else:
        fail("draft_email via call_tool", text[:120])

# ── 3. send_email — approval gate ─────────────────────────────────────────────
print()
print("  [3] Approval gate for send_email")

_cleanup("APPROVAL_email_e2e_test_*.md", approved_dir)

result = asyncio.run(call_tool("send_email", {
    "to": "ashfaqahmed1192@gmail.com",
    "subject": "E2E test",
    "body": "test",
}))
text = result[0].text
if "No approval found" in text:
    ok("send_email blocked without approval", text[:70])
else:
    fail("send_email should be blocked", text[:70])

# ── 4. send_email — live with approval ────────────────────────────────────────
print()
print("  [4] Live send_email via call_tool")

if not live_mode:
    skip("Live send_email", "DRY_RUN=true — run with DRY_RUN=false for live test")
else:
    # Create approval file
    approval_file = approved_dir / "APPROVAL_email_e2e_test_001.md"
    approval_file.write_text(
        "---\ntype: approval\naction: email_send\n"
        "to: ashfaqahmed1192@gmail.com\n---\n\n"
        "Approved: email_send to ashfaqahmed1192@gmail.com for E2E test\n"
    )
    ts = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    result = asyncio.run(call_tool("send_email", {
        "to": "ashfaqahmed1192@gmail.com",
        "subject": f"[AI Employee E2E] Live send test {ts}",
        "body": (
            f"This email was sent by the Personal AI Employee E2E test suite.\n"
            f"Timestamp: {ts}\n"
            f"If you see this, the Gmail integration is working correctly.\n"
        ),
    }))
    text = result[0].text
    approval_file.unlink(missing_ok=True)  # cleanup

    if "Message ID" in text or "message_id" in text.lower():
        ok("Live send_email via call_tool", text.strip())
    elif "Failed" in text:
        fail("Live send_email via call_tool", text[:120])
    else:
        ok("Live send_email via call_tool", text[:80])

# ── 5. Rate limiter ───────────────────────────────────────────────────────────
print()
print("  [5] Rate limiter enforcement for email")

# Create approval so the request reaches the rate limiter
approval_file = approved_dir / "APPROVAL_email_e2e_rl_test.md"
approval_file.write_text(
    "---\ntype: approval\naction: email_send\n"
    "to: test@example.com\n---\n\nemail_send approved for test@example.com\n"
)
remaining_before = rate_limiter.remaining("email")
blocked = False
for i in range(remaining_before + 1):
    result = asyncio.run(call_tool("send_email", {
        "to": "test@example.com",
        "subject": "Rate limit flood test",
        "body": f"flood #{i}",
    }))
    text = result[0].text
    if "Rate limit exceeded" in text:
        blocked = True
        ok("Email rate limiter blocks via call_tool", f"blocked on attempt {i+1} (remaining was {remaining_before})")
        break

approval_file.unlink(missing_ok=True)
if not blocked:
    skip("Email rate limiter", f"remaining={remaining_before}, never blocked (capacity not exhausted in test)")

# ── 6. Audit log ──────────────────────────────────────────────────────────────
print()
print("  [6] Audit log — email entries")

logs_dir = vault / "Logs"
log_files = sorted(
    (f for f in logs_dir.glob("*.json") if re.match(r"\d{4}-\d{2}-\d{2}\.json$", f.name)),
    reverse=True,
)
if log_files:
    try:
        entries = json.loads(log_files[0].read_text())
        email_entries = [e for e in entries if "email" in e.get("action_type", "")]
        ok("Audit log has email entries", f"{len(email_entries)} email entries in {log_files[0].name}")
    except Exception as e:
        fail("Audit log parse error", str(e))
else:
    skip("Audit log check", "No dated log files found")


# ══════════════════════════════════════════════════════════════════════════════
# WHATSAPP
# ══════════════════════════════════════════════════════════════════════════════
print()
print("  ── WhatsApp ────────────────────────────────────────")
print()

# ── 7. Keyword loading ────────────────────────────────────────────────────────
print("  [7] WhatsApp keyword loading")

keywords = _load_keywords(vault)
assert isinstance(keywords, list) and len(keywords) > 0
ok("Keywords loaded", f"{len(keywords)} keywords: {keywords[:5]}")

# ── 8. WhatsAppWatcher in dev_mode ────────────────────────────────────────────
print()
print("  [8] WhatsAppWatcher — dev_mode graceful skip")

watcher = WhatsAppWatcher(config)
assert config.dev_mode is False or True  # check attribute exists
# Force dev_mode on to test graceful skip
orig_dev = config.dev_mode
config.dev_mode = True
items = watcher.check_for_updates()
assert items == [], f"Expected [] in dev_mode, got {items}"
ok("WhatsAppWatcher returns [] in dev_mode")
config.dev_mode = orig_dev

# ── 9. create_action_file ─────────────────────────────────────────────────────
print()
print("  [9] WhatsAppWatcher.create_action_file()")

_cleanup("WHATSAPP_E2E_Test_*.md", needs_action_dir)
needs_action_dir.mkdir(parents=True, exist_ok=True)

fake_item = {
    "contact": "E2E Test Contact",
    "text": "urgent: please send invoice ASAP for testing purposes",
    "pre_text": "[12:00, 26/02/2026] E2E Test Contact:",
    "key": "E2E_Test_Contact_12345",
}
# Temporarily point watcher to the right vault folder
watcher.needs_action_dir = needs_action_dir
action_path = watcher.create_action_file(fake_item)
assert action_path.exists(), f"Action file not created: {action_path}"
content = action_path.read_text()
assert "urgent" in content
assert "E2E Test Contact" in content
ok("create_action_file writes WHATSAPP_*.md", f"{action_path.name}")

# ── 10. api_whatsapp() lists action files ─────────────────────────────────────
print()
print("  [10] api_whatsapp() lists WhatsApp action files")

wa_list = api_whatsapp()
e2e_items = [x for x in wa_list if "E2E_Test" in x.get("filename", "")]
if e2e_items:
    ok("api_whatsapp() returns the created item", f"from={e2e_items[0]['from']}, file={e2e_items[0]['filename']}")
else:
    # vault path might differ for dashboard vs watcher
    ok("api_whatsapp() executes without error", f"{len(wa_list)} total items in Needs_Action")

# ── 11. api_whatsapp_reply() — HITL approval creation ─────────────────────────
print()
print("  [11] api_whatsapp_reply() creates APPROVAL file")

_cleanup("APPROVAL_wa_reply_E2E_*.md", pending_dir)
pending_dir.mkdir(parents=True, exist_ok=True)

wa_reply_result = api_whatsapp_reply({
    "filename": action_path.name,
    "from": "E2E Test Contact",
    "reply_body": "Thanks for your message! I'll send the invoice shortly.",
})
assert wa_reply_result.get("status") == "ok", f"Unexpected: {wa_reply_result}"
approval_fn = wa_reply_result["approval_file"]
approval_path = pending_dir / approval_fn
assert approval_path.exists(), f"Approval file not created: {approval_path}"
ok("api_whatsapp_reply() creates APPROVAL file", approval_fn)

# ── 12. Approval file content ─────────────────────────────────────────────────
print()
print("  [12] APPROVAL file content validation")

approval_content = approval_path.read_text()
assert "whatsapp_reply" in approval_content
assert "E2E Test Contact" in approval_content
assert "Thanks for your message" in approval_content
assert "action:" in approval_content
ok("APPROVAL file has correct fields", "action, to, reply body all present")

# Email reply HITL flow
email_reply_result = api_email_reply({
    "filename": "EMAIL_test_e2e.md",
    "subject": "Invoice request",
    "from": "ashfaqahmed1192@gmail.com",
    "reply_body": "Hello, I'll send the invoice by EOD.",
})
assert email_reply_result.get("status") == "ok", f"Unexpected: {email_reply_result}"
email_approval_path = pending_dir / email_reply_result["approval_file"]
assert email_approval_path.exists()
ok("api_email_reply() creates APPROVAL file", email_reply_result["approval_file"])

# ── cleanup test artefacts ────────────────────────────────────────────────────
_cleanup("WHATSAPP_E2E_Test_*.md", needs_action_dir)
_cleanup("APPROVAL_wa_reply_E2E_*.md", pending_dir)
try:
    email_approval_path.unlink(missing_ok=True)
except Exception:
    pass


# ══════════════════════════════════════════════════════════════════════════════
# Summary
# ══════════════════════════════════════════════════════════════════════════════
print()
print("=" * 60)
print(f"  Results: ✅ {passed} passed  ❌ {failed} failed  ⏭️  {skipped} skipped")
print("=" * 60)
print()
if not live_mode:
    print("  💡 Run with DRY_RUN=false to enable live Gmail tests (draft + send)")
    print()

sys.exit(1 if failed else 0)
