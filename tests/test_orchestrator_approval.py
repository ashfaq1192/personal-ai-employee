"""Tests for approval manager."""

import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from src.orchestrator.approval_manager import (
    ApprovalManager,
    _load_expiry_overrides,
    _parse_frontmatter,
)


class TestParseFrontmatter:
    """Test YAML frontmatter parsing."""

    def test_parse_valid_frontmatter(self, temp_vault: Path) -> None:
        """Test parsing valid YAML frontmatter."""
        content = """---
type: approval_request
action: email_send
amount: 100.50
---

# Content here
"""
        test_file = temp_vault / "test.md"
        test_file.write_text(content, encoding="utf-8")

        fm = _parse_frontmatter(test_file)

        assert fm["type"] == "approval_request"
        assert fm["action"] == "email_send"
        assert fm["amount"] == 100.50

    def test_parse_missing_frontmatter(self, temp_vault: Path) -> None:
        """Test parsing file without frontmatter."""
        content = "# Just content, no frontmatter\n"
        test_file = temp_vault / "test.md"
        test_file.write_text(content, encoding="utf-8")

        fm = _parse_frontmatter(test_file)

        assert fm == {}

    def test_parse_invalid_yaml(self, temp_vault: Path) -> None:
        """Test parsing invalid YAML returns empty dict."""
        content = """---
type: [invalid yaml
action: test
---
"""
        test_file = temp_vault / "test.md"
        test_file.write_text(content, encoding="utf-8")

        fm = _parse_frontmatter(test_file)

        assert fm == {}


class TestLoadExpiryOverrides:
    """Test loading approval expiry overrides from handbook."""

    def test_load_default_expiry(self, temp_vault: Path) -> None:
        """Test loading default expiry from handbook."""
        handbook = temp_vault / "Company_Handbook.md"
        handbook.write_text(
            """---
last_updated: 2026-01-01
---

## Approval Expiry
- Default: 24 hours
- Payment: 4 hours
- Social post: 48 hours
""",
            encoding="utf-8",
        )

        overrides = _load_expiry_overrides(temp_vault)

        assert overrides["default"] == 24
        assert overrides["payment"] == 4
        assert overrides["social_post"] == 48

    def test_load_missing_handbook(self, temp_vault: Path) -> None:
        """Test loading when handbook doesn't exist."""
        # Remove the handbook that was created by init_vault
        handbook = temp_vault / "Company_Handbook.md"
        if handbook.exists():
            handbook.unlink()

        overrides = _load_expiry_overrides(temp_vault)
        assert overrides == {}

    def test_load_missing_section(self, temp_vault: Path) -> None:
        """Test loading when handbook has no expiry section."""
        handbook = temp_vault / "Company_Handbook.md"
        handbook.write_text("# No expiry section here\n", encoding="utf-8")

        overrides = _load_expiry_overrides(temp_vault)
        assert overrides == {}


class TestApprovalManager:
    """Test ApprovalManager functionality."""

    def test_create_approval_request(self, temp_vault: Path) -> None:
        """Test creating an approval request."""
        mgr = ApprovalManager(temp_vault)

        approval_file = mgr.create_approval(
            action="email_send",
            amount=100.00,
            recipient="client@example.com",
            reason="Test approval",
        )

        assert approval_file.exists()
        assert approval_file.parent.name == "Pending_Approval"
        assert approval_file.name.startswith("APPROVAL_")

    def test_approval_file_content(self, temp_vault: Path) -> None:
        """Test approval file has correct content."""
        mgr = ApprovalManager(temp_vault)

        approval_file = mgr.create_approval(
            action="payment",
            amount=500.00,
            recipient="vendor@example.com",
            reason="Invoice payment",
        )

        content = approval_file.read_text(encoding="utf-8")

        assert "action: payment" in content
        assert "amount: 500.0" in content
        assert "recipient: vendor@example.com" in content
        assert "status: pending" in content
        assert "To Approve" in content
        assert "Move this file to /Approved/" in content

    def test_approval_expiry_check(self, temp_vault: Path) -> None:
        """Test checking for expired approvals."""
        mgr = ApprovalManager(temp_vault)

        # Create approval that expires in the past
        past_expiry = datetime.now(timezone.utc) - timedelta(hours=1)

        approval_file = mgr.pending_dir / "APPROVAL_test_expired.md"
        approval_file.write_text(
            f"""---
type: approval_request
action: test
status: pending
expires: {past_expiry.isoformat()}
---

## Test
""",
            encoding="utf-8",
        )

        expired = mgr.check_expired()

        assert len(expired) == 1
        assert expired[0].parent.name == "Rejected"

    def test_approval_not_expired_yet(self, temp_vault: Path) -> None:
        """Test that future expiry is not marked expired."""
        mgr = ApprovalManager(temp_vault)

        future_expiry = datetime.now(timezone.utc) + timedelta(hours=1)

        approval_file = mgr.pending_dir / "APPROVAL_test_future.md"
        approval_file.write_text(
            f"""---
type: approval_request
action: test
status: pending
expires: {future_expiry.isoformat()}
---

## Test
""",
            encoding="utf-8",
        )

        expired = mgr.check_expired()

        assert len(expired) == 0

    def test_process_rejected_approval(self, temp_vault: Path) -> None:
        """Test processing rejected approval."""
        mgr = ApprovalManager(temp_vault)

        # Create approval in rejected folder
        rejected_file = mgr.rejected_dir / "APPROVAL_test_rejected.md"
        rejected_file.write_text(
            """---
type: approval_request
action: test
status: rejected
---

## Test
""",
            encoding="utf-8",
        )

        # Should move to Done
        mgr.process_rejected(rejected_file)

        done_file = temp_vault / "Done" / "APPROVAL_test_rejected.md"
        assert done_file.exists()
        assert not rejected_file.exists()

    def test_get_expiry_hours_with_override(self, temp_vault: Path) -> None:
        """Test getting expiry hours with handbook override."""
        handbook = temp_vault / "Company_Handbook.md"
        handbook.write_text(
            """---
last_updated: 2026-01-01
---

## Approval Expiry
- Default: 12 hours
- Payment: 2 hours
""",
            encoding="utf-8",
        )

        mgr = ApprovalManager(temp_vault)

        assert mgr._get_expiry_hours("payment") == 2
        assert mgr._get_expiry_hours("email_send") == 12  # default

    def test_approval_file_collision_handling(self, temp_vault: Path) -> None:
        """Test handling of approval file name collisions."""
        mgr = ApprovalManager(temp_vault)

        # Create first approval
        file1 = mgr.create_approval(
            action="email_send",
            recipient="test@example.com",
            reason="First",
        )

        # Create second with same parameters
        file2 = mgr.create_approval(
            action="email_send",
            recipient="test@example.com",
            reason="Second",
        )

        # Both should exist with different names
        assert file1.exists()
        assert file2.exists()
        assert file1.name != file2.name
