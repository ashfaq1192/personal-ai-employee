#!/usr/bin/env python3
"""Send a WhatsApp message via Playwright (persistent session).

Usage:
    uv run python scripts/whatsapp_send.py <contact_name_or_phone> <message>

Outputs SENT_OK on success, ERROR: <reason> on failure.
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path


_STATUS_WORDS = {"online", "typing...", "recording...", "unknown", ""}


def _find_msg_box(page):
    for sel in [
        "[data-testid='conversation-compose-box-input']",
        "div[title='Type a message']",
        "[aria-label='Type a message']",
        "div.copyable-text[contenteditable='true']",
        "footer div[contenteditable='true']",
        "#main footer div[contenteditable]",
    ]:
        el = page.query_selector(sel)
        if el:
            return el
    return None


def send_message(contact: str, message: str, session_path: str) -> bool:
    from playwright.sync_api import sync_playwright

    # Normalise — strip underscores that watcher adds to filenames
    contact_clean = contact.replace("_", " ").strip()
    use_fallback = contact_clean.lower() in _STATUS_WORDS

    with sync_playwright() as pw:
        browser = pw.chromium.launch_persistent_context(
            session_path,
            headless=False,
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-infobars",
            ],
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
        )
        page = browser.pages[0] if browser.pages else browser.new_page()
        try:
            page.goto("https://web.whatsapp.com", timeout=60000)
            time.sleep(7)

            if use_fallback:
                # ── Fallback: open the most-recent chat (top of list) ─────────
                print(f"INFO: Contact name '{contact}' is a status placeholder; "
                      "opening most-recent chat instead")
                for sel in [
                    "[data-testid='cell-frame-container']",
                    "div[role='listitem']",
                    "#pane-side div[tabindex='-1']",
                ]:
                    items = page.query_selector_all(sel)
                    if items:
                        items[0].click()
                        time.sleep(2)
                        break
            else:
                # ── Search by contact name ────────────────────────────────────
                search = None
                for sel in [
                    "[data-testid='chat-list-search']",
                    "div[title='Search input textbox']",
                    "[aria-label='Search input textbox']",
                    "div[data-tab='3']",
                ]:
                    search = page.query_selector(sel)
                    if search:
                        break

                if not search:
                    print("ERROR: Could not find WhatsApp search box")
                    return False

                search.click()
                time.sleep(0.5)
                page.keyboard.type(contact_clean, delay=80)
                time.sleep(3)

                # Click first result
                chat_clicked = False
                for sel in [
                    "[data-testid='cell-frame-container']",
                    "div[role='listitem']",
                ]:
                    items = page.query_selector_all(sel)
                    if items:
                        items[0].click()
                        chat_clicked = True
                        break

                if not chat_clicked:
                    page.keyboard.press("Enter")
                time.sleep(2)

            # ── Find message input ────────────────────────────────────────────
            msg_box = _find_msg_box(page)
            if not msg_box:
                print("ERROR: Could not find WhatsApp message input box")
                return False

            msg_box.click()
            time.sleep(0.3)
            page.keyboard.type(message, delay=40)
            time.sleep(0.5)

            # ── Send ──────────────────────────────────────────────────────────
            send_btn = page.query_selector("[data-testid='send']")
            if send_btn:
                send_btn.click()
            else:
                page.keyboard.press("Enter")

            time.sleep(3)
            print("SENT_OK")
            return True

        except Exception as exc:
            print(f"ERROR: {exc}")
            return False
        finally:
            browser.close()


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: whatsapp_send.py <contact> <message>")
        sys.exit(1)

    contact_arg = sys.argv[1]
    message_arg = sys.argv[2]
    session = os.environ.get(
        "WHATSAPP_SESSION_PATH",
        str(Path.home() / ".config" / "ai-employee" / "whatsapp-session"),
    )

    ok = send_message(contact_arg, message_arg, session)
    sys.exit(0 if ok else 1)
