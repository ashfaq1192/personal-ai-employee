"""Tests for dashboard updater."""

from pathlib import Path

from src.orchestrator.dashboard_updater import (
    _count_files,
    update_dashboard,
    _merge_cloud_updates,
)


class TestCountFiles:
    """Test _count_files helper function."""

    def test_count_empty_directory(self, temp_vault: Path) -> None:
        """Test counting files in empty directory."""
        empty_dir = temp_vault / "empty"
        empty_dir.mkdir(parents=True, exist_ok=True)
        
        count = _count_files(empty_dir)
        
        assert count == 0

    def test_count_files(self, temp_vault: Path) -> None:
        """Test counting files in directory."""
        test_dir = temp_vault / "test_dir"
        test_dir.mkdir(parents=True, exist_ok=True)
        
        for i in range(5):
            (test_dir / f"file_{i}.md").write_text(f"content {i}", encoding="utf-8")
        
        count = _count_files(test_dir)
        
        assert count == 5

    def test_count_nonexistent_directory(self, temp_vault: Path) -> None:
        """Test counting files in nonexistent directory."""
        nonexistent = temp_vault / "nonexistent"
        
        count = _count_files(nonexistent)
        
        assert count == 0

    def test_count_ignores_subdirectories(self, temp_vault: Path) -> None:
        """Test that subdirectories are not counted."""
        test_dir = temp_vault / "test_dir"
        test_dir.mkdir(parents=True, exist_ok=True)
        
        # Create files
        for i in range(3):
            (test_dir / f"file_{i}.md").write_text("content", encoding="utf-8")
        
        # Create subdirectory
        (test_dir / "subdir").mkdir()
        (test_dir / "subdir" / "nested.md").write_text("nested", encoding="utf-8")
        
        count = _count_files(test_dir)
        
        # Should only count direct children (3 files, not subdir)
        assert count == 3


class TestDashboardUpdater:
    """Test update_dashboard functionality."""

    def test_update_dashboard(self, temp_vault: Path) -> None:
        """Test updating dashboard with current counts."""
        # Create some test files
        needs_action = temp_vault / "Needs_Action"
        needs_action.mkdir(parents=True, exist_ok=True)
        for i in range(3):
            (needs_action / f"item_{i}.md").write_text("test", encoding="utf-8")
        
        pending = temp_vault / "Pending_Approval"
        pending.mkdir(parents=True, exist_ok=True)
        (pending / "approval.md").write_text("test", encoding="utf-8")
        
        # Update dashboard
        update_dashboard(temp_vault)
        
        dashboard = temp_vault / "Dashboard.md"
        content = dashboard.read_text(encoding="utf-8")
        
        assert "/Needs_Action/ | 3" in content
        assert "/Pending_Approval/ | 1" in content

    def test_update_dashboard_missing_file(self, temp_vault: Path) -> None:
        """Test updating when Dashboard.md doesn't exist."""
        dashboard = temp_vault / "Dashboard.md"
        dashboard.unlink()
        
        # Should not raise
        update_dashboard(temp_vault)
        
        # Dashboard should still not exist (function returns early)
        assert not dashboard.exists()

    def test_update_dashboard_includes_activity(self, temp_vault: Path) -> None:
        """Test that dashboard includes recent activity."""
        # Create some audit log entries
        from src.core.logger import AuditLogger
        
        audit = AuditLogger(temp_vault)
        audit.log("test_action", "test_actor", "test_target", result="success")
        
        update_dashboard(temp_vault)
        
        dashboard = temp_vault / "Dashboard.md"
        content = dashboard.read_text(encoding="utf-8")
        
        assert "Recent Activity" in content
        assert "test_action" in content

    def test_update_dashboard_updates_timestamp(self, temp_vault: Path) -> None:
        """Test that dashboard timestamp is updated."""
        update_dashboard(temp_vault)
        
        dashboard = temp_vault / "Dashboard.md"
        content = dashboard.read_text(encoding="utf-8")
        
        assert "last_updated:" in content


class TestMergeCloudUpdates:
    """Test _merge_cloud_updates functionality."""

    def test_merge_with_no_updates(self, temp_vault: Path) -> None:
        """Test merging when no updates directory exists."""
        # Should not raise
        _merge_cloud_updates(temp_vault)

    def test_merge_cleanup_old_updates(self, temp_vault: Path) -> None:
        """Test that old update files are cleaned up."""
        updates_dir = temp_vault / "Updates"
        updates_dir.mkdir(parents=True, exist_ok=True)
        
        # Create multiple update files
        for i in range(5):
            update_file = updates_dir / f"cloud_status_20260218_100{i}.md"
            update_file.write_text(f"update {i}", encoding="utf-8")
        
        _merge_cloud_updates(temp_vault)
        
        # Should keep only the latest
        remaining = list(updates_dir.glob("cloud_status_*.md"))
        assert len(remaining) == 1
        assert "1004" in remaining[0].name
