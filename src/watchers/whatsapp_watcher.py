"""WhatsApp Watcher — monitors WhatsApp Web via Playwright for keyword messages."""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.core.config import Config
from src.watchers.base_watcher import BaseWatcher

log = logging.getLogger(__name__)


def _load_keywords(vault_path: Path) -> list[str]:
    """Parse WhatsApp keywords from Company_Handbook.md."""
    handbook = vault_path / "Company_Handbook.md"
    keywords: list[str] = []
    if not handbook.exists():
        return ["urgent", "asap", "invoice", "payment", "help", "deadline", "contract"]

    in_keywords = False
    for line in handbook.read_text(encoding="utf-8").splitlines():
        if "## WhatsApp Keywords" in line:
            in_keywords = True
            continue
        if in_keywords:
            if line.startswith("## "):
                break
            stripped = line.strip().lstrip("- ").strip()
            if stripped:
                keywords.append(stripped.lower())
    return keywords or ["urgent", "asap", "invoice", "payment", "help"]


class WhatsAppWatcher(BaseWatcher):
    """Monitors WhatsApp Web for keyword-containing messages."""

    def __init__(self, config: Config) -> None:
        super().__init__(config, check_interval=30, watcher_name="whatsapp")
        self._keywords = _load_keywords(config.vault_path)
        self._processed: set[str] = set()
        self._browser = None
        self._page = None

    def _ensure_browser(self):
        """Lazy-load Playwright browser with persistent context."""
        if self._page is not None:
            return self._page

        if self.config.dev_mode:
            log.info("DEV_MODE: WhatsApp browser not initialized")
            return None

        try:
            from playwright.sync_api import sync_playwright

            pw = sync_playwright().start()
            session_path = str(self.config.whatsapp_session_path)
            self._browser = pw.chromium.launch_persistent_context(
                session_path,
                headless=False,
                args=["--no-sandbox"],
            )
            self._page = self._browser.pages[0] if self._browser.pages else self._browser.new_page()
            self._page.goto("https://web.whatsapp.com", timeout=60000)
            self._page.wait_for_timeout(5000)
            return self._page
        except Exception as exc:
            log.error("Failed to launch WhatsApp browser: %s", exc)
            return None

    def _check_qr_screen(self, page) -> bool:
        """Detect if WhatsApp is showing QR code login screen."""
        try:
            qr = page.query_selector("[data-testid='qrcode']")
            return qr is not None
        except Exception:
            return False

    def check_for_updates(self) -> list[Any]:
        if self.config.dev_mode:
            log.debug("DEV_MODE: skipping WhatsApp check")
            return []

        page = self._ensure_browser()
        if page is None:
            return []

        # Check for QR code screen (session expired)
        if self._check_qr_screen(page):
            ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M")
            alert_path = self.needs_action_dir / f"ALERT_whatsapp_auth_{ts}.md"
            if not alert_path.exists():
                alert_path.write_text(
                    f"---\ntype: alert\nid: ALERT_whatsapp_auth_{ts}\n"
                    f"from: system\nsubject: WhatsApp session expired\n"
                    f"received: {datetime.now(timezone.utc).isoformat()}\n"
                    f"priority: high\nstatus: pending\nplan_ref: null\n---\n\n"
                    f"## Alert\nWhatsApp Web session expired. Please scan QR code.\n",
                    encoding="utf-8",
                )
                self.audit.log(
                    action_type="watcher_event",
                    actor="whatsapp_watcher",
                    target="system",
                    parameters={"event": "auth_expired"},
                    result="failure",
                    error="QR code screen detected",
                )
            return []

        items = []
        try:
            # Find unread chat indicators
            unread_chats = page.query_selector_all("[aria-label*='unread']")
            for chat in unread_chats:
                try:
                    chat.click()
                    page.wait_for_timeout(1000)

                    # Get contact name
                    header = page.query_selector("header span[title]")
                    contact = header.get_attribute("title") if header else "unknown"

                    # Get recent messages
                    msg_elements = page.query_selector_all("[data-pre-plain-text]")
                    for msg_el in msg_elements[-5:]:  # Last 5 messages
                        text = msg_el.inner_text().lower()
                        pre_text = msg_el.get_attribute("data-pre-plain-text") or ""

                        # Check for keyword match
                        if any(kw in text for kw in self._keywords):
                            msg_key = f"{contact}_{hash(text)}"
                            if msg_key not in self._processed:
                                items.append({
                                    "contact": contact,
                                    "text": msg_el.inner_text(),
                                    "pre_text": pre_text,
                                    "key": msg_key,
                                })
                except Exception:
                    log.exception("Error processing WhatsApp chat")
        except Exception:
            log.exception("WhatsApp check_for_updates failed")

        return items

    def create_action_file(self, item: Any) -> Path:
        contact = re.sub(r"[^\w\s-]", "", item["contact"]).strip().replace(" ", "_")
        now = datetime.now(timezone.utc)
        ts = now.strftime("%Y-%m-%dT%H-%M-%S")

        md_path = self.needs_action_dir / f"WHATSAPP_{contact}_{ts}.md"
        md_content = (
            f"---\n"
            f"type: whatsapp\n"
            f"id: WHATSAPP_{contact}_{ts}\n"
            f"from: {item['contact']}\n"
            f"subject: WhatsApp message from {item['contact']}\n"
            f"received: {now.isoformat()}\n"
            f"priority: high\n"
            f"status: pending\n"
            f"plan_ref: null\n"
            f"---\n\n"
            f"## Content\n"
            f"**From**: {item['contact']}\n"
            f"**Time**: {item['pre_text']}\n\n"
            f"{item['text']}\n\n"
            f"## Suggested Actions\n"
            f"- [ ] Review message and determine response\n"
            f"- [ ] Draft reply if needed\n"
        )
        md_path.write_text(md_content, encoding="utf-8")
        self._processed.add(item["key"])
        return md_path

    def stop(self) -> None:
        super().stop()
        if self._browser:
            try:
                self._browser.close()
            except Exception:
                pass
