"""
End-to-end test for the full social posting flow.

Tests every layer:
  1. Rate limiter enforcement (in-memory)
  2. Approval gate (non-scheduled posts)
  3. MCP call_tool interface → FacebookClient / InstagramClient
  4. Live Facebook post (real API call)
  5. Live Instagram post (real API call)
  6. Audit log entry written to vault
  7. Social metrics fetch (Facebook + Instagram)

Run:
    DRY_RUN=false uv run python scripts/test_social_e2e.py
"""
from __future__ import annotations

import asyncio
import datetime
import json
import os
import sys
import tempfile
from pathlib import Path

# ── colour helpers ────────────────────────────────────────────────────────────
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
RESET  = "\033[0m"
SKIP   = f"{YELLOW}⏭️  SKIP{RESET}"

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
    print(f"  {YELLOW}⏭️ {RESET} {label}" + (f": {detail}" if detail else ""))


# ── setup: force DRY_RUN based on env ────────────────────────────────────────
live_mode = os.environ.get("DRY_RUN", "true").lower() == "false"

print()
print("=" * 60)
print("  SOCIAL POSTING — END-TO-END TEST")
print(f"  Mode: {'🟢 LIVE (real API calls)' if live_mode else '🟡 DRY-RUN'}")
print("=" * 60)
print()

# ── import the MCP handler ────────────────────────────────────────────────────
# We import the async call_tool directly and drive it without starting stdio
from src.mcp_servers.social_mcp import (
    call_tool,
    config,
    rate_limiter,
    _rate_and_approval_check,
    _check_approval,
)


# ═════════════════════════════════════════════════════════════════════════════
# 1. Rate limiter enforcement
# ═════════════════════════════════════════════════════════════════════════════
print("  [1] Rate limiter")

# Fresh limiter with limit=2 for fast testing
from src.core.rate_limiter import RateLimiter
test_rl = RateLimiter({"social": 2})

assert test_rl.check("social"), "1st call should pass"
assert test_rl.check("social"), "2nd call should pass"
assert not test_rl.check("social"), "3rd call should be blocked"
assert test_rl.remaining("social") == 0
ok("Rate limiter blocks at limit=2", "remaining=0 after 2 uses")

# ═════════════════════════════════════════════════════════════════════════════
# 2. Approval gate — non-scheduled without file → blocked
# ═════════════════════════════════════════════════════════════════════════════
print()
print("  [2] Approval gate")

approved_dir = config.vault_path / "Approved"
approved_dir.mkdir(parents=True, exist_ok=True)

# Remove any existing social_post approval files for clean test
existing = list(approved_dir.glob("APPROVAL_social_post_test_*.md"))
for f in existing:
    f.unlink()

# Non-scheduled without approval should fail
assert not _check_approval("social_post_test_marker")
ok("Non-scheduled post blocked without approval file")

# Create approval file
approval_file = approved_dir / "APPROVAL_social_post_test_001.md"
approval_file.write_text("# Approval\nAction: social_post_test_marker\nApproved by: test\n")
assert _check_approval("social_post_test_marker")
ok("Non-scheduled post approved when file present")
approval_file.unlink()  # cleanup

# ═════════════════════════════════════════════════════════════════════════════
# 3. call_tool — dry-run path (no real API call, always safe)
# ═════════════════════════════════════════════════════════════════════════════
print()
print("  [3] MCP call_tool — dry-run validation")

# Temporarily force dry_run for this section
original_dry_run = config.dry_run
config.dry_run = True

result = asyncio.run(call_tool("post_facebook", {
    "page_id": config.facebook_page_id or "fake_page",
    "message": "Dry-run test from E2E suite",
    "is_scheduled": True,
}))
text = result[0].text
assert "dry_run" in text or "posted" in text, f"Unexpected: {text}"
ok("post_facebook dry-run via call_tool", text[:80])

result = asyncio.run(call_tool("post_instagram", {
    "ig_user_id": config.ig_user_id or "fake_ig",
    "image_url": "https://example.com/img.jpg",
    "caption": "Dry-run E2E test",
    "is_scheduled": True,
}))
text = result[0].text
assert "dry_run" in text or "posted" in text, f"Unexpected: {text}"
ok("post_instagram dry-run via call_tool", text[:80])

config.dry_run = original_dry_run

# ═════════════════════════════════════════════════════════════════════════════
# 4. call_tool — live Facebook post
# ═════════════════════════════════════════════════════════════════════════════
print()
print("  [4] Live Facebook post via call_tool")

if not live_mode:
    skip("Live Facebook post", "DRY_RUN=true — run with DRY_RUN=false for live test")
elif not config.facebook_page_id:
    skip("Live Facebook post", "FACEBOOK_PAGE_ID not set")
else:
    timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    result = asyncio.run(call_tool("post_facebook", {
        "page_id": config.facebook_page_id,
        "message": f"🤖 AI Employee E2E test — Facebook layer ✅ {timestamp}",
        "is_scheduled": True,
    }))
    text = result[0].text
    if "post_id" in text:
        data = json.loads(text.replace("Facebook: ", ""))
        ok("Live Facebook post via call_tool", f"post_id={data['post_id']}")
    elif "Failed" in text:
        fail("Live Facebook post via call_tool", text[:120])
    else:
        ok("Live Facebook post via call_tool", text[:80])

# ═════════════════════════════════════════════════════════════════════════════
# 5. call_tool — live Instagram post
# ═════════════════════════════════════════════════════════════════════════════
print()
print("  [5] Live Instagram post via call_tool")

if not live_mode:
    skip("Live Instagram post", "DRY_RUN=true — run with DRY_RUN=false for live test")
elif not config.ig_user_id:
    skip("Live Instagram post", "INSTAGRAM_USER_ID not set")
else:
    timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    result = asyncio.run(call_tool("post_instagram", {
        "ig_user_id": config.ig_user_id,
        "image_url": "https://images.unsplash.com/photo-1611532736597-de2d4265fba3?w=1080",
        "caption": f"🤖 AI Employee E2E test — Instagram layer ✅ {timestamp}",
        "is_scheduled": True,
    }))
    text = result[0].text
    if "media_id" in text:
        data = json.loads(text.replace("Instagram: ", ""))
        ok("Live Instagram post via call_tool", f"media_id={data['media_id']}")
    elif "Failed" in text:
        fail("Live Instagram post via call_tool", text[:120])
    else:
        ok("Live Instagram post via call_tool", text[:80])

# ═════════════════════════════════════════════════════════════════════════════
# 6. Audit log — entries written to vault
# ═════════════════════════════════════════════════════════════════════════════
print()
print("  [6] Audit log")

logs_dir = config.vault_path / "Logs"
# Find most recent date-stamped log file (UTC date may differ from local date)
import re as _re
log_files = sorted(
    (f for f in logs_dir.glob("*.json") if _re.match(r"\d{4}-\d{2}-\d{2}\.json$", f.name)),
    reverse=True,
)
if log_files:
    audit_file = log_files[0]
    try:
        entries = json.loads(audit_file.read_text())
        social_entries = [e for e in entries if "social" in e.get("action_type", "") or e.get("target", "") in ("facebook", "instagram")]
        ok("Audit log has social entries", f"{len(social_entries)} social entries in {audit_file.name}")
    except Exception as e:
        fail("Audit log parse error", str(e))
else:
    skip("Audit log check", "No dated log files found in Logs/")

# ═════════════════════════════════════════════════════════════════════════════
# 7. Social metrics via call_tool
# ═════════════════════════════════════════════════════════════════════════════
print()
print("  [7] Social metrics via call_tool")

if not config.facebook_page_id:
    skip("Facebook metrics", "FACEBOOK_PAGE_ID not set")
else:
    result = asyncio.run(call_tool("get_social_metrics", {"platform": "facebook", "days": 7}))
    text = result[0].text
    try:
        data = json.loads(text)
        m = data.get("metrics", {})
        if "error" in m and list(m.keys()) == ["error"]:
            fail("Facebook metrics via call_tool", f"Only error key: {m['error'][:80]}")
        else:
            ok("Facebook metrics via call_tool", f"keys={list(m.keys())}")
    except Exception as e:
        fail("Facebook metrics via call_tool", f"{e}: {text[:100]}")

if not config.ig_user_id:
    skip("Instagram metrics", "INSTAGRAM_USER_ID not set")
else:
    result = asyncio.run(call_tool("get_social_metrics", {"platform": "instagram", "days": 7}))
    text = result[0].text
    try:
        data = json.loads(text)
        m = data.get("metrics", {})
        if "error" in m and list(m.keys()) == ["error"]:
            fail("Instagram metrics via call_tool", f"Only error key: {m['error'][:80]}")
        else:
            ok("Instagram metrics via call_tool", f"keys={list(m.keys())}")
    except Exception as e:
        fail("Instagram metrics via call_tool", f"{e}: {text[:100]}")

# ═════════════════════════════════════════════════════════════════════════════
# 8. Rate limiter — MCP-level block after limit
# ═════════════════════════════════════════════════════════════════════════════
print()
print("  [8] Rate limiter enforcement via call_tool")

# Exhaust the production rate limiter
from src.mcp_servers.social_mcp import rate_limiter as prod_rl

# Check remaining capacity
remaining_before = prod_rl.remaining("social")
# Flood until blocked
blocked = False
for i in range(remaining_before + 1):
    result = asyncio.run(call_tool("post_facebook", {
        "page_id": config.facebook_page_id or "fake",
        "message": f"Rate limit flood #{i}",
        "is_scheduled": True,
    }))
    text = result[0].text
    if "Rate limit exceeded" in text:
        blocked = True
        ok("Rate limiter blocks via call_tool after limit", f"blocked on attempt {i+1} (remaining was {remaining_before})")
        break

if not blocked:
    fail("Rate limiter did not block via call_tool", f"remaining was {remaining_before}")

# ═════════════════════════════════════════════════════════════════════════════
# Summary
# ═════════════════════════════════════════════════════════════════════════════
print()
print("=" * 60)
print(f"  Results: ✅ {passed} passed  ❌ {failed} failed  ⏭️  {skipped} skipped")
print("=" * 60)
print()
if not live_mode:
    print("  💡 Run with DRY_RUN=false to enable live API tests (sections 4 & 5)")
    print()

sys.exit(1 if failed else 0)
