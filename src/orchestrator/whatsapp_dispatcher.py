"""WhatsApp Dispatcher — polls Approved/APPROVAL_wa_reply_*.md and sends messages.

Runs as a background loop every 30 seconds. This is the missing link that
wires the HITL approval to an actual WhatsApp send via the Business Cloud API.

Usage:
    uv run python src/orchestrator/whatsapp_dispatcher.py
"""

from __future__ import annotations

import logging
import re
import time
from pathlib import Path

from src.core.config import Config
from src.core.logger import AuditLogger
from src.mcp_servers.whatsapp_client import WhatsAppClient

log = logging.getLogger(__name__)

POLL_INTERVAL = 30  # seconds


def _parse_frontmatter(text: str) -> dict[str, str]:
    """Extract YAML front-matter key/value pairs."""
    m = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
    if not m:
        return {}
    result: dict[str, str] = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            result[k.strip()] = v.strip().strip('"').strip("'")
    return result


def _parse_reply_body(text: str) -> str:
    """Extract the ## Reply Body section."""
    m = re.search(r"## Reply Body\s*\n\n([\s\S]+)", text)
    return m.group(1).strip() if m else ""


def _update_source_status(vault_path: Path, source_filename: str, status: str) -> None:
    """Update the status field in the source WHATSAPP_*.md file."""
    for folder in ("Needs_Action", "Done"):
        src = vault_path / folder / source_filename
        if src.exists():
            try:
                content = src.read_text(encoding="utf-8")
                content = re.sub(
                    r"^(status:\s*).*$",
                    f"\\g<1>{status}",
                    content,
                    flags=re.MULTILINE,
                )
                src.write_text(content, encoding="utf-8")
            except Exception as exc:
                log.warning("Could not update source status for %s: %s", source_filename, exc)
            return


class WhatsAppDispatcher:
    """Polls Approved/ for WhatsApp reply approvals and dispatches sends."""

    def __init__(self, config: Config, client: WhatsAppClient | None = None) -> None:
        self._config = config
        self._vault = config.vault_path
        self._audit = AuditLogger(config.vault_path)
        self._client = client or WhatsAppClient(
            access_token=config.whatsapp_access_token,
            phone_number_id=config.whatsapp_phone_number_id,
            dry_run=config.dry_run,
        )

    def process_pending(self) -> list[str]:
        """Process all pending APPROVAL_wa_reply_*.md files. Returns list of processed filenames."""
        approved_dir = self._vault / "Approved"
        done_dir = self._vault / "Done"
        done_dir.mkdir(parents=True, exist_ok=True)

        processed: list[str] = []
        for approval_file in sorted(approved_dir.glob("APPROVAL_wa_reply_*.md")):
            try:
                text = approval_file.read_text(encoding="utf-8")
                fm = _parse_frontmatter(text)

                # Only process whatsapp_reply actions
                if fm.get("action", "") != "whatsapp_reply":
                    continue

                to = fm.get("to", "")
                if not to:
                    log.warning("APPROVAL file %s has no 'to' field, skipping", approval_file.name)
                    continue

                body = _parse_reply_body(text)
                if not body:
                    log.warning("APPROVAL file %s has no reply body, skipping", approval_file.name)
                    continue

                log.info("Dispatching WhatsApp reply to %s from %s", to, approval_file.name)
                result = self._client.send_message(to, body)

                # Move approval file to Done/
                dest = done_dir / approval_file.name
                approval_file.rename(dest)

                # Update source WHATSAPP_*.md status
                source_fn = fm.get("source_whatsapp", "")
                if source_fn:
                    _update_source_status(self._vault, source_fn, "replied")

                self._audit.log(
                    action_type="whatsapp_reply_sent",
                    actor="whatsapp_dispatcher",
                    target=to,
                    parameters={
                        "approval_file": approval_file.name,
                        "message_id": result.get("message_id", ""),
                        "preview": body[:80],
                    },
                    approval_status="approved",
                    result="success",
                )
                processed.append(approval_file.name)
                log.info("Sent WhatsApp reply to %s (msg_id=%s)", to, result.get("message_id", ""))

            except Exception as exc:
                log.exception("Failed to process %s: %s", approval_file.name, exc)
                self._audit.log(
                    action_type="whatsapp_reply_sent",
                    actor="whatsapp_dispatcher",
                    target=approval_file.name,
                    result="failure",
                    error=str(exc)[:200],
                )

        return processed

    def run_forever(self) -> None:
        """Poll loop — runs until KeyboardInterrupt."""
        log.info("WhatsApp dispatcher started (poll every %ds)", POLL_INTERVAL)
        while True:
            try:
                processed = self.process_pending()
                if processed:
                    log.info("Processed %d approval(s): %s", len(processed), processed)
            except Exception as exc:
                log.exception("Dispatcher loop error: %s", exc)
            time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    import logging as _logging
    _logging.basicConfig(
        level=_logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    cfg = Config()
    dispatcher = WhatsAppDispatcher(cfg)
    dispatcher.run_forever()
