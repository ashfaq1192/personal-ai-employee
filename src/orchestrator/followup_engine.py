"""Proactive Follow-Up Engine — scans Done/ for stale tasks and drafts follow-ups.

Workflow (runs daily at 09:00):
1. Scan vault/Done/ for tasks completed 3+ days ago
2. Identify tasks that had outbound communication (email_send, whatsapp_reply)
   OR emails where we replied but haven't heard back
3. For each stale task, write a FOLLOWUP_*.md to Needs_Action/
4. Orchestrator picks it up and triggers reasoning → agent decides whether to send

Stale criteria:
  - File mtime > FOLLOWUP_AFTER_DAYS days ago
  - Frontmatter has action: email_send OR type: email with status: done
  - No corresponding reply in Done/ (check for reply threads)
  - Not already followed up (no FOLLOWUP_* for same target in last 7 days)
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

from src.core.config import Config
from src.core.logger import AuditLogger

log = logging.getLogger(__name__)

FOLLOWUP_AFTER_DAYS = 3   # days since task completed before follow-up check
FOLLOWUP_COOLDOWN_DAYS = 7  # don't follow up again within this window


class FollowUpEngine:
    """Scans Done/ and Approved/ for stale outbound tasks and queues follow-ups."""

    def __init__(self, config: Config | None = None) -> None:
        self.config = config or Config()
        self.audit = AuditLogger(self.config.vault_path)
        self.vault = self.config.vault_path

    def _parse_fm(self, text: str) -> dict[str, str]:
        fm: dict[str, str] = {}
        m = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
        if not m:
            return fm
        for line in m.group(1).splitlines():
            if ":" in line:
                k, _, v = line.partition(":")
                fm[k.strip()] = v.strip().strip('"').strip("'")
        return fm

    def _already_followed_up(self, target: str) -> bool:
        """Check if a follow-up for `target` was created in the last cooldown window."""
        na = self.vault / "Needs_Action"
        if not na.exists():
            return False
        cutoff = datetime.now(timezone.utc) - timedelta(days=FOLLOWUP_COOLDOWN_DAYS)
        for f in na.glob("FOLLOWUP_*.md"):
            if target.lower() in f.read_text(encoding="utf-8", errors="ignore").lower():
                try:
                    mtime = datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc)
                    if mtime > cutoff:
                        return True
                except Exception:
                    pass
        return False

    def _scan_folder(self, folder: Path) -> list[Path]:
        """Return .md files older than FOLLOWUP_AFTER_DAYS."""
        if not folder.exists():
            return []
        cutoff = datetime.now(timezone.utc) - timedelta(days=FOLLOWUP_AFTER_DAYS)
        stale = []
        for f in folder.glob("*.md"):
            try:
                mtime = datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc)
                if mtime < cutoff:
                    stale.append(f)
            except Exception:
                pass
        return stale

    def _is_outbound_task(self, fm: dict[str, str]) -> bool:
        """Return True if this task involved sending an email or WhatsApp."""
        action = fm.get("action", "").lower()
        task_type = fm.get("type", "").lower()
        return action in ("email_send", "send_email", "whatsapp_reply", "whatsapp_send") \
            or task_type in ("meeting_request", "outbound_email")

    def _create_followup_file(
        self, source_file: Path, fm: dict[str, str], recipient: str
    ) -> Path:
        na = self.vault / "Needs_Action"
        na.mkdir(parents=True, exist_ok=True)

        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M")
        filename = f"FOLLOWUP_{ts}_{source_file.stem[:30]}.md"
        dest = na / filename

        subject = fm.get("subject", "").removeprefix("Re: ")
        original_type = fm.get("type", "email")
        days_elapsed = FOLLOWUP_AFTER_DAYS  # conservative

        content = (
            f"---\n"
            f"type: followup\n"
            f"action: email_send\n"
            f"to: {recipient}\n"
            f"subject: Re: {subject or 'our previous conversation'}\n"
            f"source_task: {source_file.name}\n"
            f"original_type: {original_type}\n"
            f"created: {datetime.now(timezone.utc).isoformat()}\n"
            f"priority: normal\n"
            f"status: pending\n"
            f"---\n\n"
            f"## Proactive Follow-Up\n\n"
            f"It has been {days_elapsed}+ days since we last communicated with **{recipient}** "
            f"regarding: *{subject or 'a previous task'}*.\n\n"
            f"**Source task**: `{source_file.name}`\n\n"
            f"## Suggested Follow-Up\n\n"
            f"Decide whether to send a follow-up. Suggested message:\n\n"
            f"---\n"
            f"Hi,\n\n"
            f"I wanted to follow up on my previous message regarding {subject or 'our recent conversation'}. "
            f"Please let me know if you have any questions or if there's anything I can help with.\n\n"
            f"Looking forward to hearing from you.\n\n"
            f"Best regards\n"
            f"---\n\n"
            f"## Actions\n"
            f"- [ ] Review and personalise the follow-up message\n"
            f"- [ ] Send or skip (move to Done/ to suppress)\n"
        )
        dest.write_text(content, encoding="utf-8")
        log.info("Follow-up queued: %s → %s", source_file.name, filename)
        return dest

    def run(self) -> list[Path]:
        """Scan Done/ and Approved/ and create follow-up files for stale outbound tasks."""
        if self.config.dev_mode:
            log.info("[DEV_MODE] Follow-up engine scan skipped")
            return []

        created: list[Path] = []

        for folder in [self.vault / "Done", self.vault / "Approved"]:
            for stale_file in self._scan_folder(folder):
                try:
                    text = stale_file.read_text(encoding="utf-8", errors="ignore")
                    fm = self._parse_fm(text)

                    if not self._is_outbound_task(fm):
                        continue

                    recipient = fm.get("to", fm.get("recipient", "")).strip()
                    if not recipient or "@" not in recipient:
                        continue

                    if self._already_followed_up(recipient):
                        log.debug("Follow-up cooldown active for %s", recipient)
                        continue

                    path = self._create_followup_file(stale_file, fm, recipient)
                    created.append(path)

                    self.audit.log(
                        action_type="followup_queued",
                        actor="followup_engine",
                        target=recipient,
                        parameters={"source": stale_file.name, "file": path.name},
                    )
                except Exception:
                    log.exception("Follow-up check failed for %s", stale_file.name)

        if created:
            log.info("Follow-up engine: queued %d follow-up(s)", len(created))
        return created
