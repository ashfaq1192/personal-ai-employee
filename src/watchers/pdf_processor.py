"""PDF Attachment Processor — extracts text and action items from email PDFs.

When Gmail delivers an email with a PDF attachment:
1. GmailWatcher detects the attachment via gmail_service.list_attachments()
2. PdfProcessor.process_email_attachments() downloads + parses each PDF
3. Returns a structured summary appended to the EMAIL_*.md action file

This lets Claude read email files and already have PDF content summarised,
without needing a separate download step.
"""

from __future__ import annotations

import io
import logging
import re
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

# Keywords that signal action items in document text
_ACTION_PATTERNS = [
    r"(?:action required|action item|next step|todo|to do|please|kindly|you need to|we need you)[^\n]*",
    r"(?:deadline|due date|by [a-z]+ \d{1,2})[^\n]*",
    r"(?:approve|review|sign|respond|confirm|complete|submit|provide)[^\n]{0,80}",
]
_ACTION_RE = re.compile("|".join(_ACTION_PATTERNS), re.IGNORECASE)


class PdfProcessor:
    """Downloads and parses PDF attachments from Gmail messages."""

    def __init__(self, gmail_service=None) -> None:
        self._svc = gmail_service

    def _parse_pdf_bytes(self, data: bytes) -> str:
        """Extract all text from PDF bytes using pypdf."""
        try:
            import pypdf
        except ImportError:
            log.warning("pypdf not installed — PDF text extraction unavailable")
            return ""

        try:
            reader = pypdf.PdfReader(io.BytesIO(data))
            pages = []
            for page in reader.pages:
                text = page.extract_text() or ""
                pages.append(text)
            return "\n\n".join(pages)
        except Exception as exc:
            log.warning("PDF parse failed: %s", exc)
            return ""

    def _extract_action_items(self, text: str) -> list[str]:
        """Return up to 5 action-item sentences found in the text."""
        items: list[str] = []
        seen: set[str] = set()
        for match in _ACTION_RE.finditer(text):
            sentence = match.group(0).strip()
            key = sentence.lower()[:60]
            if key not in seen:
                seen.add(key)
                items.append(sentence)
            if len(items) >= 5:
                break
        return items

    def _summarise(self, text: str, max_chars: int = 600) -> str:
        """Return first max_chars of non-whitespace-collapsed text."""
        collapsed = re.sub(r"\s{3,}", "\n\n", text).strip()
        if len(collapsed) <= max_chars:
            return collapsed
        return collapsed[:max_chars].rsplit(" ", 1)[0] + " …"

    def process_attachment(self, message_id: str, attachment: dict[str, Any]) -> dict[str, Any]:
        """Download and parse a single PDF attachment.

        Returns:
            {filename, page_count, summary, action_items, char_count}
        """
        filename = attachment["filename"]
        att_id = attachment["attachment_id"]

        try:
            raw = self._svc.download_attachment(message_id, att_id)
        except Exception as exc:
            log.warning("Failed to download attachment %s: %s", filename, exc)
            return {"filename": filename, "error": str(exc)}

        text = self._parse_pdf_bytes(raw)
        if not text:
            return {"filename": filename, "error": "no text extracted"}

        import pypdf
        try:
            reader = pypdf.PdfReader(io.BytesIO(raw))
            page_count = len(reader.pages)
        except Exception:
            page_count = 0

        return {
            "filename": filename,
            "page_count": page_count,
            "char_count": len(text),
            "summary": self._summarise(text),
            "action_items": self._extract_action_items(text),
        }

    def process_email_attachments(
        self, message_id: str, email_file: Path
    ) -> list[dict[str, Any]]:
        """Find all PDF attachments on an email, process them, and append to the action file.

        Returns list of result dicts (one per PDF found).
        """
        if self._svc is None:
            return []

        try:
            attachments = self._svc.list_attachments(message_id)
        except Exception as exc:
            log.debug("list_attachments failed for %s: %s", message_id, exc)
            return []

        pdfs = [a for a in attachments if "pdf" in a.get("mime_type", "").lower()
                or a["filename"].lower().endswith(".pdf")]

        if not pdfs:
            return []

        results: list[dict[str, Any]] = []
        sections: list[str] = []

        for att in pdfs:
            result = self.process_attachment(message_id, att)
            results.append(result)

            if "error" in result:
                sections.append(
                    f"\n### Attachment: {result['filename']}\n"
                    f"*Could not extract text: {result['error']}*\n"
                )
                continue

            action_block = ""
            if result["action_items"]:
                action_block = "\n**Detected Action Items:**\n" + "".join(
                    f"- {item}\n" for item in result["action_items"]
                )

            sections.append(
                f"\n### Attachment: {result['filename']}\n"
                f"*{result['page_count']} page(s) | {result['char_count']:,} chars extracted*\n\n"
                f"**Summary:**\n{result['summary']}\n"
                f"{action_block}"
            )

        if sections:
            attachment_block = "\n## PDF Attachments\n" + "".join(sections) + "\n"
            try:
                existing = email_file.read_text(encoding="utf-8")
                email_file.write_text(existing + attachment_block, encoding="utf-8")
                log.info(
                    "Appended %d PDF attachment(s) to %s",
                    len(results), email_file.name,
                )
            except Exception as exc:
                log.warning("Failed to update email file with PDF content: %s", exc)

        return results
