"""Tests for audit logger."""

import json
from datetime import datetime, timezone
from pathlib import Path

from src.core.logger import AuditLogger


class TestAuditLogger:
    """Test AuditLogger functionality."""

    def test_log_creation(self, temp_vault: Path) -> None:
        """Test that log entries are created correctly."""
        logger = AuditLogger(temp_vault)
        entry = logger.log(
            action_type="email_send",
            actor="test",
            target="recipient@example.com",
            parameters={"subject": "Test"},
            result="success",
        )
        
        assert entry["action_type"] == "email_send"
        assert entry["actor"] == "test"
        assert entry["target"] == "recipient@example.com"
        assert entry["result"] == "success"
        assert "timestamp" in entry

    def test_log_file_creation(self, temp_vault: Path) -> None:
        """Test that log files are created with correct naming."""
        logger = AuditLogger(temp_vault)
        logger.log("test_action", "test_actor", "test_target")
        
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        log_file = temp_vault / "Logs" / f"{today}.json"
        assert log_file.exists()

    def test_log_file_is_json(self, temp_vault: Path) -> None:
        """Test that log file contains valid JSON."""
        logger = AuditLogger(temp_vault)
        logger.log("test_action", "test_actor", "test_target")
        
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        log_file = temp_vault / "Logs" / f"{today}.json"
        content = log_file.read_text(encoding="utf-8")
        
        # Should not raise
        data = json.loads(content)
        assert isinstance(data, list)
        assert len(data) >= 1

    def test_get_recent(self, temp_vault: Path) -> None:
        """Test retrieving recent log entries."""
        logger = AuditLogger(temp_vault)
        
        # Create multiple log entries
        for i in range(15):
            logger.log(f"action_{i}", f"actor_{i}", f"target_{i}")
        
        recent = logger.get_recent(10)
        assert len(recent) == 10
        
        # Most recent should be last one created
        assert recent[0]["action_type"] == "action_14"

    def test_cleanup_old_logs(self, temp_vault: Path) -> None:
        """Test cleanup of old log files."""
        logger = AuditLogger(temp_vault)
        
        # Create a fake old log file
        old_date = "2020-01-01"
        old_log = temp_vault / "Logs" / f"{old_date}.json"
        old_log.write_text("[]", encoding="utf-8")
        
        # Create today's log
        logger.log("test", "actor", "target")
        
        # Cleanup logs older than 30 days
        deleted = logger.cleanup_old_logs(retention_days=30)
        
        assert deleted >= 1
        assert not old_log.exists()

    def test_log_with_approval_status(self, temp_vault: Path) -> None:
        """Test logging with approval status."""
        logger = AuditLogger(temp_vault)
        entry = logger.log(
            action_type="payment",
            actor="orchestrator",
            target="vendor@example.com",
            approval_status="approved",
            approved_by="human",
            parameters={"amount": 100.00},
        )
        
        assert entry["approval_status"] == "approved"
        assert entry["approved_by"] == "human"
        assert entry["parameters"]["amount"] == 100.00

    def test_log_with_error(self, temp_vault: Path) -> None:
        """Test logging with error information."""
        logger = AuditLogger(temp_vault)
        entry = logger.log(
            action_type="email_send",
            actor="email_mcp",
            target="test@example.com",
            result="failure",
            error="Connection timeout",
        )
        
        assert entry["result"] == "failure"
        assert entry["error"] == "Connection timeout"

    def test_path_serialization(self, temp_vault: Path) -> None:
        """Test that Path objects are properly serialized."""
        logger = AuditLogger(temp_vault)
        entry = logger.log(
            action_type="file_operation",
            actor="filesystem_watcher",
            target=temp_vault / "test.md",
            parameters={"source": Path("/some/path")},
        )
        
        # Should not raise - Path objects converted to strings
        assert isinstance(entry["target"], str)
