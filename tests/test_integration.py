"""Integration tests for AI Employee system."""

import time
from pathlib import Path

from src.core.config import Config
from src.core.logger import AuditLogger
from src.orchestrator.approval_manager import ApprovalManager
from src.orchestrator.claim_manager import ClaimManager
from src.orchestrator.dashboard_updater import update_dashboard
from src.vault.init_vault import init_vault


class TestVaultInitialization:
    """Test vault initialization end-to-end."""

    def test_init_vault_creates_structure(self, temp_vault: Path) -> None:
        """Test that init_vault creates all required folders."""
        # Temp vault is already initialized by fixture
        # Verify structure
        required_folders = [
            "Inbox",
            "Needs_Action",
            "Plans",
            "Pending_Approval",
            "Approved",
            "Rejected",
            "In_Progress",
            "Done",
            "Accounting",
            "Invoices",
            "Briefings",
            "Logs",
            "Active_Project",
        ]
        
        for folder in required_folders:
            assert (temp_vault / folder).exists(), f"Missing folder: {folder}"

    def test_init_vault_creates_templates(self, temp_vault: Path) -> None:
        """Test that init_vault creates template files."""
        required_files = [
            "Dashboard.md",
            "Company_Handbook.md",
            "Business_Goals.md",
        ]
        
        for file in required_files:
            assert (temp_vault / file).exists(), f"Missing template: {file}"


class TestApprovalWorkflow:
    """Test complete approval workflow end-to-end."""

    def test_full_approval_lifecycle(self, temp_vault: Path) -> None:
        """Test complete lifecycle: create → approve → execute → done."""
        # Create approval request
        mgr = ApprovalManager(temp_vault)
        approval = mgr.create_approval(
            action="email_send",
            recipient="client@example.com",
            reason="Test workflow",
        )
        
        assert approval.parent.name == "Pending_Approval"
        
        # Simulate human approval (move to Approved)
        approved_file = temp_vault / "Approved" / approval.name
        approval.rename(approved_file)
        
        assert approved_file.exists()
        assert not approval.exists()
        
        # Process approval (would trigger MCP action in real system)
        fm = mgr.process_approved(approved_file)
        assert fm["action"] == "email_send"
        assert fm["recipient"] == "client@example.com"
        
        # Move to Done
        done_file = temp_vault / "Done" / approval.name
        approved_file.rename(done_file)
        
        assert done_file.exists()
        assert not approved_file.exists()


class TestClaimAndRelease:
    """Test claim and release workflow."""

    def test_claim_process_release(self, temp_vault: Path) -> None:
        """Test complete claim → process → release cycle."""
        claim_mgr = ClaimManager(temp_vault)
        
        # Create item
        needs_action = temp_vault / "Needs_Action"
        needs_action.mkdir(parents=True, exist_ok=True)
        item = needs_action / "process_test.md"
        item.write_text("Process this item", encoding="utf-8")
        
        # Claim
        assert claim_mgr.claim(item, "test_agent") is True
        assert not item.exists()
        
        # Process (simulate)
        in_progress = temp_vault / "In_Progress" / "test_agent" / "process_test.md"
        assert in_progress.exists()
        
        # Release to Done
        assert claim_mgr.release("process_test.md", "test_agent", "Done") is True
        assert not in_progress.exists()
        
        done = temp_vault / "Done" / "process_test.md"
        assert done.exists()


class TestAuditTrail:
    """Test audit logging throughout system."""

    def test_complete_audit_trail(self, temp_vault: Path) -> None:
        """Test that all actions are logged."""
        audit = AuditLogger(temp_vault)
        
        # Log various actions
        audit.log("system", "orchestrator", "startup")
        audit.log("email_send", "email_mcp", "client@example.com", result="success")
        audit.log(
            "approval",
            "human",
            "APPROVAL_001",
            approval_status="approved",
            approved_by="human",
        )
        
        # Retrieve and verify
        recent = audit.get_recent(10)
        
        assert len(recent) >= 3
        
        # Most recent first
        assert recent[0]["action_type"] == "approval"
        assert recent[1]["action_type"] == "email_send"
        assert recent[2]["action_type"] == "system"


class TestDashboardUpdates:
    """Test dashboard reflects system state."""

    def test_dashboard_reflects_state_changes(self, temp_vault: Path) -> None:
        """Test that dashboard updates with state changes."""
        # Initial state
        update_dashboard(temp_vault)
        dashboard1 = temp_vault / "Dashboard.md"
        content1 = dashboard1.read_text(encoding="utf-8")
        
        # Add items
        needs_action = temp_vault / "Needs_Action"
        for i in range(5):
            (needs_action / f"item_{i}.md").write_text("test", encoding="utf-8")
        
        # Update again
        update_dashboard(temp_vault)
        content2 = dashboard1.read_text(encoding="utf-8")
        
        # Should reflect new count
        assert "/Needs_Action/ | 5" in content2


class TestConfigIntegration:
    """Test configuration integration."""

    def test_config_with_temp_vault(self, temp_config: Config) -> None:
        """Test that config works with temp vault."""
        assert temp_config.vault_path.exists()
        assert temp_config.dev_mode is True
        assert temp_config.dry_run is True

    def test_rate_limits_enforced(self, temp_config: Config) -> None:
        """Test that rate limits are configured."""
        from src.core.rate_limiter import RateLimiter
        
        limiter = RateLimiter({
            "email": temp_config.rate_limit_emails,
            "payment": temp_config.rate_limit_payments,
            "social": temp_config.rate_limit_social,
        })
        
        # Should allow up to limit
        for _ in range(temp_config.rate_limit_emails):
            assert limiter.check("email") is True
        
        # Should reject over limit
        assert limiter.check("email") is False


class TestWatcherIntegration:
    """Test watcher integration with vault."""

    def test_gmail_watcher_creates_action_file(
        self, temp_config: Config, temp_vault: Path
    ) -> None:
        """Test Gmail watcher creates action files in dev mode."""
        from src.watchers.gmail_watcher import GmailWatcher
        
        watcher = GmailWatcher(temp_config)
        
        # In dev mode, check should return empty
        items = watcher.check_for_updates()
        assert items == []
        
        # But create_action_file should still work
        mock_email = {
            "id": "integration_test",
            "snippet": "Test snippet",
            "payload": {"headers": []},
        }
        
        action_file = watcher.create_action_file(mock_email)
        
        assert action_file.exists()
        assert action_file.parent.name == "Needs_Action"

    def test_filesystem_watcher_integration(
        self, temp_config: Config, temp_vault: Path
    ) -> None:
        """Test filesystem watcher creates action files."""
        from src.watchers.filesystem_watcher import FileSystemWatcher
        
        drop_folder = temp_vault.parent / "integration_drop"
        watcher = FileSystemWatcher(temp_config, drop_folder=drop_folder)
        
        # Create file in drop folder
        test_file = drop_folder / "integration_test.txt"
        test_file.write_text("integration test content", encoding="utf-8")
        
        # Create action file
        action_file = watcher.create_action_file(test_file)
        
        # Verify companion .md file
        md_file = watcher.needs_action_dir / "FILE_integration_test.txt.md"
        assert md_file.exists()
        
        watcher.stop()
