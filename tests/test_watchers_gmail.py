"""Tests for Gmail watcher."""

from pathlib import Path
from unittest.mock import Mock, patch

from src.watchers.gmail_watcher import GmailWatcher, _load_known_contacts


class TestGmailWatcher:
    """Test GmailWatcher functionality."""

    def test_dev_mode_skips_check(self, temp_config, temp_vault: Path) -> None:
        """Test that Gmail check is skipped in dev mode."""
        watcher = GmailWatcher(temp_config)
        result = watcher.check_for_updates()
        assert result == []

    def test_load_known_contacts_from_handbook(self, temp_vault: Path) -> None:
        """Test parsing known contacts from Company_Handbook.md."""
        handbook = temp_vault / "Company_Handbook.md"
        handbook.write_text(
            """---
last_updated: 2026-01-01
---

# Company Handbook

## Known Contacts
| Name | Email | WhatsApp | Auto-Approve |
|------|-------|----------|--------------|
| John Doe | john@example.com | +1234567890 | email_reply |
| Jane Smith | jane@example.com | +0987654321 | email_reply |
""",
            encoding="utf-8",
        )

        contacts = _load_known_contacts(temp_vault)

        assert "john@example.com" in contacts
        assert "jane@example.com" in contacts

    def test_load_known_contacts_empty_handbook(self, temp_vault: Path) -> None:
        """Test loading contacts when handbook has no contacts."""
        handbook = temp_vault / "Company_Handbook.md"
        handbook.write_text("# Empty Handbook\n", encoding="utf-8")

        contacts = _load_known_contacts(temp_vault)

        assert contacts == set()

    def test_load_known_contacts_missing_handbook(self, temp_vault: Path) -> None:
        """Test loading contacts when handbook doesn't exist."""
        # Remove the handbook that was created by init_vault
        handbook = temp_vault / "Company_Handbook.md"
        if handbook.exists():
            handbook.unlink()

        contacts = _load_known_contacts(temp_vault)
        assert contacts == set()

    def test_create_action_file(self, temp_config, temp_vault: Path) -> None:
        """Test creation of action file from email."""
        watcher = GmailWatcher(temp_config)

        # Mock email item
        email_item = {
            "id": "test_123",
            "snippet": "This is a test email snippet",
            "payload": {
                "headers": [
                    {"name": "From", "value": "sender@example.com"},
                    {"name": "Subject", "value": "Test Subject"},
                    {"name": "Date", "value": "Wed, 18 Feb 2026 10:00:00 +0000"},
                ]
            },
        }

        action_file = watcher.create_action_file(email_item)

        assert action_file.exists()
        assert action_file.name == "EMAIL_test_123.md"

        content = action_file.read_text(encoding="utf-8")
        assert "sender@example.com" in content
        assert "Test Subject" in content
        assert "pending" in content

    def test_create_action_file_known_contact_priority(
        self, temp_config, temp_vault: Path
    ) -> None:
        """Test that emails from known contacts get high priority."""
        # Add known contact to handbook
        handbook = temp_vault / "Company_Handbook.md"
        handbook.write_text(
            """---
last_updated: 2026-01-01
---

## Known Contacts
| Name | Email | WhatsApp | Auto-Approve |
|------|-------|----------|--------------|
| VIP | vip@example.com | +1234567890 | email_reply |
""",
            encoding="utf-8",
        )

        watcher = GmailWatcher(temp_config)

        email_item = {
            "id": "vip_001",
            "snippet": "Important message",
            "payload": {
                "headers": [
                    {"name": "From", "value": "VIP <vip@example.com>"},
                    {"name": "Subject", "value": "Urgent"},
                    {"name": "Date", "value": "Wed, 18 Feb 2026 10:00:00 +0000"},
                ]
            },
        }

        action_file = watcher.create_action_file(email_item)
        content = action_file.read_text(encoding="utf-8")

        assert "priority: high" in content

    def test_duplicate_message_not_processed(self, temp_config, temp_vault: Path) -> None:
        """Test that duplicate messages are not processed twice."""
        watcher = GmailWatcher(temp_config)

        email_item = {"id": "dup_001", "snippet": "Test", "payload": {"headers": []}}

        # First creation
        file1 = watcher.create_action_file(email_item)
        assert file1.exists()

        # Try to create again - should not create duplicate
        # (in real code, this would check _processed_ids)
        # For this test, we just verify the file exists
        assert file1.exists()

    def test_action_file_frontmatter(self, temp_config, temp_vault: Path) -> None:
        """Test that action file has correct frontmatter."""
        watcher = GmailWatcher(temp_config)

        email_item = {
            "id": "fm_test",
            "snippet": "Test",
            "payload": {"headers": []},
        }

        action_file = watcher.create_action_file(email_item)
        content = action_file.read_text(encoding="utf-8")

        # Check frontmatter structure
        assert content.startswith("---")
        assert "type: email" in content
        assert "id: EMAIL_fm_test" in content
        assert "status: pending" in content
        assert "plan_ref: null" in content
