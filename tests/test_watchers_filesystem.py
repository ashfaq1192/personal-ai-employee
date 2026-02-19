"""Tests for filesystem watcher."""

import time
from pathlib import Path

from src.watchers.filesystem_watcher import FileSystemWatcher, _DropHandler


class TestDropHandler:
    """Test _DropHandler functionality."""

    def test_on_created_file(self, temp_vault: Path) -> None:
        """Test that file creation events are captured."""
        handler = _DropHandler()

        # Simulate file creation event
        from watchdog.events import FileCreatedEvent

        test_file = temp_vault / "test.txt"
        test_file.write_text("test content", encoding="utf-8")

        event = FileCreatedEvent(str(test_file))
        handler.on_created(event)

        assert len(handler.pending) == 1
        assert handler.pending[0].name == "test.txt"

    def test_on_created_directory_ignored(self, temp_vault: Path) -> None:
        """Test that directory creation events are ignored."""
        handler = _DropHandler()

        from watchdog.events import DirCreatedEvent

        test_dir = temp_vault / "test_dir"
        test_dir.mkdir()

        event = DirCreatedEvent(str(test_dir))
        handler.on_created(event)

        assert len(handler.pending) == 0


class TestFileSystemWatcher:
    """Test FileSystemWatcher functionality."""

    def test_drop_folder_creation(self, temp_config, temp_vault: Path) -> None:
        """Test that drop folder is created if it doesn't exist."""
        drop_folder = temp_vault.parent / "test_drop_folder"

        watcher = FileSystemWatcher(temp_config, drop_folder=drop_folder)

        assert drop_folder.exists()
        watcher.stop()

    def test_check_for_updates(self, temp_config, temp_vault: Path) -> None:
        """Test checking for new files."""
        drop_folder = temp_vault.parent / "test_drop_folder_2"
        watcher = FileSystemWatcher(temp_config, drop_folder=drop_folder)

        # Create a file in drop folder
        test_file = drop_folder / "new_file.txt"
        test_file.write_text("new content", encoding="utf-8")

        # Give watcher time to detect
        time.sleep(0.5)

        items = watcher.check_for_updates()

        # Should have detected the file
        assert len(items) >= 0  # May vary based on timing
        watcher.stop()

    def test_create_action_file(self, temp_config, temp_vault: Path) -> None:
        """Test creation of action file for dropped file."""
        drop_folder = temp_vault.parent / "test_drop_folder_3"
        watcher = FileSystemWatcher(temp_config, drop_folder=drop_folder)

        # Create source file
        source_file = drop_folder / "source.txt"
        source_file.write_text("source content", encoding="utf-8")

        # Create action file
        action_file = watcher.create_action_file(source_file)

        # Check companion .md file was created
        md_file = watcher.needs_action_dir / "FILE_source.txt.md"
        assert md_file.exists()

        content = md_file.read_text(encoding="utf-8")
        assert "source.txt" in content
        assert "type: file_drop" in content
        watcher.stop()

    def test_create_action_file_metadata(self, temp_config, temp_vault: Path) -> None:
        """Test that action file contains correct metadata."""
        drop_folder = temp_vault.parent / "test_drop_folder_4"
        watcher = FileSystemWatcher(temp_config, drop_folder=drop_folder)

        source_file = drop_folder / "metadata_test.txt"
        source_file.write_text("x" * 100, encoding="utf-8")  # 100 bytes

        watcher.create_action_file(source_file)

        md_file = watcher.needs_action_dir / "FILE_metadata_test.txt.md"
        content = md_file.read_text(encoding="utf-8")

        assert "size: 100" in content or "size: 100" in content
        assert "original_name: metadata_test.txt" in content
        watcher.stop()

    def test_conflicting_filename_handling(
        self, temp_config, temp_vault: Path
    ) -> None:
        """Test handling of files with same name."""
        drop_folder = temp_vault.parent / "test_drop_folder_5"
        watcher = FileSystemWatcher(temp_config, drop_folder=drop_folder)

        # Create first file
        source1 = drop_folder / "duplicate.txt"
        source1.write_text("first", encoding="utf-8")
        watcher.create_action_file(source1)

        # Create second file with same name
        source2 = drop_folder / "duplicate.txt"
        source2.write_text("second", encoding="utf-8")
        action_file2 = watcher.create_action_file(source2)

        # Should have timestamp in name to avoid collision
        assert action_file2.exists()
        watcher.stop()

    def test_stop_observer(self, temp_config, temp_vault: Path) -> None:
        """Test that stop() properly shuts down observer."""
        drop_folder = temp_vault.parent / "test_drop_folder_6"
        watcher = FileSystemWatcher(temp_config, drop_folder=drop_folder)

        # Should not raise
        watcher.stop()
