"""Contact Memory — persistent per-contact preferences and interaction history.

Stored at: vault/contacts_memory.json

Schema per contact (keyed by lowercase email):
{
  "email": "alice@example.com",
  "name": "Alice Johnson",
  "preferred_name": "Alice",
  "company": "Acme Corp",
  "communication_style": "formal | casual | technical",
  "topics": ["product demo", "pricing"],
  "last_interaction": "2026-03-06T10:00:00Z",
  "interaction_count": 3,
  "history": [
    {"date": "...", "type": "email_received", "summary": "Asked about pricing"}
  ]
}

Usage:
  mem = ContactMemory(vault_path)
  mem.note_interaction("alice@example.com", "Alice Johnson", "email_received", "Asked about pricing")
  prefs = mem.recall("alice@example.com")
  greeting = mem.preferred_greeting("alice@example.com")  # → "Hi Alice,"
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger(__name__)

_MEMORY_FILE = "contacts_memory.json"
_MAX_HISTORY = 20  # max interactions stored per contact


class ContactMemory:
    """Reads and writes the contacts memory JSON file in the vault."""

    def __init__(self, vault_path: Path) -> None:
        self._path = vault_path / _MEMORY_FILE
        self._data: dict[str, dict] = {}
        self._load()

    def _load(self) -> None:
        if self._path.exists():
            try:
                self._data = json.loads(self._path.read_text(encoding="utf-8"))
            except Exception:
                log.warning("Could not parse contacts_memory.json — starting fresh")
                self._data = {}

    def _save(self) -> None:
        try:
            self._path.write_text(
                json.dumps(self._data, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception:
            log.warning("Could not save contacts_memory.json", exc_info=True)

    def recall(self, email: str) -> dict:
        """Return memory for a contact, or an empty dict if unknown."""
        return self._data.get(email.lower(), {})

    def preferred_greeting(self, email: str, fallback_name: str = "") -> str:
        """Return 'Hi {preferred_name},' for use in email/WhatsApp replies."""
        contact = self.recall(email)
        name = (
            contact.get("preferred_name")
            or (fallback_name.split()[0] if fallback_name else "")
            or contact.get("name", "").split()[0]
            or "there"
        )
        return f"Hi {name},"

    def note_interaction(
        self,
        email: str,
        full_name: str = "",
        interaction_type: str = "unknown",
        summary: str = "",
        company: str = "",
    ) -> None:
        """Record an interaction and update contact metadata."""
        key = email.lower()
        contact = self._data.setdefault(key, {
            "email": key,
            "name": full_name,
            "preferred_name": full_name.split()[0] if full_name else "",
            "company": company,
            "communication_style": "casual",
            "topics": [],
            "interaction_count": 0,
            "last_interaction": "",
            "history": [],
        })

        # Update fields if we have new info
        if full_name and not contact.get("name"):
            contact["name"] = full_name
            contact["preferred_name"] = full_name.split()[0]
        if company and not contact.get("company"):
            contact["company"] = company

        now = datetime.now(timezone.utc).isoformat()
        contact["last_interaction"] = now
        contact["interaction_count"] = contact.get("interaction_count", 0) + 1

        history = contact.setdefault("history", [])
        history.append({"date": now, "type": interaction_type, "summary": summary[:200]})
        # Trim to max
        if len(history) > _MAX_HISTORY:
            contact["history"] = history[-_MAX_HISTORY:]

        self._save()
        log.debug("Contact memory updated: %s (%s)", email, interaction_type)

    def set_preference(self, email: str, key: str, value) -> None:
        """Set a specific preference field for a contact."""
        key_norm = email.lower()
        if key_norm not in self._data:
            self._data[key_norm] = {"email": key_norm}
        self._data[key_norm][key] = value
        self._save()

    def all_contacts(self) -> list[dict]:
        """Return all known contacts sorted by last interaction."""
        contacts = list(self._data.values())
        contacts.sort(key=lambda c: c.get("last_interaction", ""), reverse=True)
        return contacts
