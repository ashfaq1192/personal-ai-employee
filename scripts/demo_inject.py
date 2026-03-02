#!/usr/bin/env python3
"""
AI Employee Demo Injector
Simulates the full pipeline: incoming email + WhatsApp → approval → done

Usage:
    uv run python scripts/demo_inject.py
    uv run python scripts/demo_inject.py --fast   # no delays (CI / quick show)
"""

from __future__ import annotations

import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from src.core.config import Config

FAST = "--fast" in sys.argv
DELAY = 0.5 if FAST else 2.5

config = Config()
vault = config.vault_path

GREEN  = "\033[1;32m"
YELLOW = "\033[1;33m"
CYAN   = "\033[1;36m"
BLUE   = "\033[1;34m"
RED    = "\033[1;31m"
BOLD   = "\033[1m"
DIM    = "\033[2m"
RESET  = "\033[0m"


def banner(text: str, color: str = CYAN) -> None:
    print(f"\n{color}{'─' * 54}{RESET}")
    print(f"{color}{BOLD}  {text}{RESET}")
    print(f"{color}{'─' * 54}{RESET}")


def step(icon: str, msg: str, color: str = GREEN) -> None:
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"  {DIM}{ts}{RESET}  {icon}  {color}{msg}{RESET}")
    if not FAST:
        time.sleep(DELAY)


def pause(msg: str = "") -> None:
    if not FAST:
        input(f"\n  {YELLOW}▶  {msg or 'Press Enter to continue...'}{RESET}\n")


def ensure_dirs() -> None:
    for d in ["Needs_Action", "Pending_Approval", "Approved", "Rejected", "Done", "Logs"]:
        (vault / d).mkdir(parents=True, exist_ok=True)


def drop_email() -> Path:
    now = datetime.now(timezone.utc)
    slug = now.strftime("%Y%m%d_%H%M%S")
    path = vault / "Needs_Action" / f"EMAIL_{slug}.md"
    path.write_text(
        f"---\n"
        f"type: email\n"
        f"from: sarah.jones@acmecorp.com\n"
        f"subject: Q1 Invoice — Please Send ASAP\n"
        f"received: {now.isoformat()}\n"
        f"priority: high\n"
        f"status: pending\n"
        f"---\n\n"
        f"Hi,\n\n"
        f"Could you please send over the Q1 invoice for the consulting work?\n"
        f"Our accounts payable needs it by end of day.\n\n"
        f"Amount should be $4,500 as agreed.\n\n"
        f"Thanks,\n"
        f"Sarah Jones\n"
        f"ACME Corp\n",
        encoding="utf-8",
    )
    return path


def drop_whatsapp() -> Path:
    now = datetime.now(timezone.utc)
    slug = now.strftime("%Y%m%d_%H%M%S")
    path = vault / "Needs_Action" / f"WHATSAPP_{slug}.md"
    path.write_text(
        f"---\n"
        f"type: whatsapp\n"
        f"from: +923001234567\n"
        f"chat: Ahmed (Partner)\n"
        f"received: {now.isoformat()}\n"
        f"priority: normal\n"
        f"keywords_matched: meeting,project\n"
        f"---\n\n"
        f"Hey! Are we still on for the project kickoff meeting tomorrow at 10am?\n"
        f"Let me know if anything changed.\n",
        encoding="utf-8",
    )
    return path


def create_approval(source_path: Path, action: str, to: str, subject: str, body: str) -> Path:
    now = datetime.now(timezone.utc)
    slug = source_path.stem
    path = vault / "Pending_Approval" / f"APPROVAL_{slug}.md"
    path.write_text(
        f"---\n"
        f"type: approval_request\n"
        f"action: {action}\n"
        f"requested_by: orchestrator\n"
        f"requested_at: {now.isoformat()}\n"
        f"to: {to}\n"
        f"subject: {subject}\n"
        f"source: {source_path.name}\n"
        f"expires: {now.replace(hour=(now.hour + 24) % 24).isoformat()}\n"
        f"---\n\n"
        f"## Reply Body\n\n"
        f"{body}\n",
        encoding="utf-8",
    )
    return path


def approve(approval_path: Path) -> Path:
    dst = vault / "Approved" / approval_path.name
    if not approval_path.exists():
        # Already moved (e.g. approved via dashboard UI) — just return dst
        print(f"  {YELLOW}  ℹ  Already approved via dashboard: {approval_path.name}{RESET}")
        return dst
    shutil.move(str(approval_path), str(dst))
    return dst


def move_done(path: Path) -> Path:
    dst = vault / "Done" / path.name
    # Check both source and approved folder (dashboard may have moved it)
    approved = vault / "Approved" / path.name
    if path.exists():
        shutil.move(str(path), str(dst))
    elif approved.exists():
        shutil.move(str(approved), str(dst))
    # Already in Done or elsewhere — skip silently
    return dst


def count(folder: str) -> int:
    d = vault / folder
    return sum(1 for f in d.glob("*.md")) if d.exists() else 0


# ── Main demo ────────────────────────────────────────────────────────────────

def main() -> None:
    ensure_dirs()

    print(f"\n{BOLD}{'═' * 54}")
    print(f"  🤖  AI Employee — Full Pipeline Demo")
    print(f"  Vault: {vault}")
    print(f"  Mode:  {'FAST' if FAST else 'INTERACTIVE'}")
    print(f"{'═' * 54}{RESET}\n")

    if not FAST:
        print(f"  {DIM}Open the dashboard at http://localhost:8080 and")
        print(f"  run scripts/demo_monitor.sh in another terminal{RESET}")
        pause("Press Enter to start the demo...")

    # ── Stage 1: Incoming email ──────────────────────────────────────────────
    banner("STAGE 1 — Incoming Email", BLUE)
    step("📬", "Gmail watcher detects new email from sarah.jones@acmecorp.com")
    email_path = drop_email()
    step("📄", f"Created: {email_path.name}", GREEN)
    step("👁 ", f"Needs_Action now has {count('Needs_Action')} file(s)")

    if not FAST:
        pause("Check dashboard Inbox tab — email is now visible. Press Enter to continue...")

    # ── Stage 2: Incoming WhatsApp ───────────────────────────────────────────
    banner("STAGE 2 — Incoming WhatsApp", BLUE)
    step("💬", "WhatsApp webhook fires — message from Ahmed (Partner)")
    wa_path = drop_whatsapp()
    step("📄", f"Created: {wa_path.name}", GREEN)
    step("👁 ", f"Needs_Action now has {count('Needs_Action')} file(s)")

    if not FAST:
        pause("Switch to WhatsApp tab in dashboard. Press Enter to continue...")

    # ── Stage 3: Claude reasoning ────────────────────────────────────────────
    banner("STAGE 3 — Claude Reasoning", CYAN)
    step("🧠", "Orchestrator triggers Claude Code reasoning on Needs_Action items")
    step("📋", "Claude reads email — identifies action: send Q1 invoice reply")
    step("📋", "Claude reads WhatsApp — identifies action: confirm meeting")
    if not FAST:
        time.sleep(DELAY)

    # ── Stage 4: Approval requests created ───────────────────────────────────
    banner("STAGE 4 — Approval Requests Created (HITL Gate)", YELLOW)

    email_approval = create_approval(
        email_path,
        action="email_send",
        to="sarah.jones@acmecorp.com",
        subject="Re: Q1 Invoice — Please Send ASAP",
        body=(
            "Dear Sarah,\n\n"
            "Thank you for reaching out. I'll have the Q1 invoice ($4,500) sent to you shortly.\n\n"
            "Best regards,\n"
            "AI Employee"
        ),
    )
    step("⏳", f"Email approval created: {email_approval.name}", YELLOW)

    wa_approval = create_approval(
        wa_path,
        action="whatsapp_reply",
        to="+923001234567",
        subject="WhatsApp reply to Ahmed",
        body="Yes, we're confirmed for tomorrow at 10am! See you then. 👍",
    )
    step("⏳", f"WhatsApp approval created: {wa_approval.name}", YELLOW)
    step("👁 ", f"Pending_Approval now has {count('Pending_Approval')} file(s)")

    if not FAST:
        pause("Check Approvals tab in dashboard — two cards should appear. Press Enter to approve both...")

    # ── Stage 5: Human approves ───────────────────────────────────────────────
    banner("STAGE 5 — Human Approves (File Move)", GREEN)
    step("✅", "Human clicks APPROVE on email reply card")
    approved_email = approve(email_approval)
    step("📂", f"Moved to Approved/: {approved_email.name}", GREEN)

    step("✅", "Human clicks APPROVE on WhatsApp reply card")
    approved_wa = approve(wa_approval)
    step("📂", f"Moved to Approved/: {approved_wa.name}", GREEN)
    step("👁 ", f"Approved/ now has {count('Approved')} file(s)")

    if not FAST:
        time.sleep(DELAY)

    # ── Stage 6: Dispatch ─────────────────────────────────────────────────────
    banner("STAGE 6 — Action Dispatch", CYAN)
    mode = config.dev_mode
    if mode:
        step("🔒", "[DEV_MODE] Email send logged — no real send (set DEV_MODE=false for live)", DIM)
        step("🔒", "[DEV_MODE] WhatsApp reply logged — no real send", DIM)
    else:
        step("📧", "GmailService.send_email() → sent to sarah.jones@acmecorp.com", GREEN)
        step("💬", "WhatsAppClient.send_message() → sent to +923001234567", GREEN)

    # ── Stage 7: Move to Done ─────────────────────────────────────────────────
    banner("STAGE 7 — Cleanup → Done", GREEN)
    move_done(email_path)
    step("✅", f"EMAIL file moved to Done/", GREEN)
    move_done(wa_path)
    step("✅", f"WHATSAPP file moved to Done/", GREEN)
    move_done(approved_email)
    step("✅", f"Email approval moved to Done/", GREEN)
    move_done(approved_wa)
    step("✅", f"WhatsApp approval moved to Done/", GREEN)

    # ── Summary ───────────────────────────────────────────────────────────────
    print(f"\n{BOLD}{'═' * 54}")
    print(f"  📊  Pipeline Complete — Final Vault State")
    print(f"{'═' * 54}{RESET}")
    for folder in ["Needs_Action", "Pending_Approval", "Approved", "Done"]:
        n = count(folder)
        color = GREEN if n == 0 or folder == "Done" else YELLOW
        print(f"  {color}{folder:<22} {n} file(s){RESET}")
    print(f"\n  {GREEN}✓ Full pipeline demonstrated successfully!{RESET}")
    print(f"  {DIM}Audit log updated at: {vault}/Logs/{RESET}\n")


if __name__ == "__main__":
    main()
