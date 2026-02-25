"""File System Watcher — monitors a drop folder for new files."""

from __future__ import annotations

import logging
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from watchdog.events import FileCreatedEvent, FileSystemEventHandler
from watchdog.observers import Observer

from src.core.config import Config
from src.watchers.base_watcher import BaseWatcher

log = logging.getLogger(__name__)


class _DropHandler(FileSystemEventHandler):
    """Collects newly created files."""

    def __init__(self) -> None:
        self.pending: list[Path] = []

    def on_created(self, event: FileCreatedEvent) -> None:  # type: ignore[override]
        if event.is_directory:
            return
        self.pending.append(Path(event.src_path))


class FileSystemWatcher(BaseWatcher):
    """Watches a drop folder; copies new files + creates companion .md in /Needs_Action/."""

    def __init__(self, config: Config, *, drop_folder: Path | None = None) -> None:
        super().__init__(config, check_interval=5, watcher_name="filesystem")
        self.drop_folder = drop_folder or (config.vault_path.parent / "drop_folder")
        self.drop_folder.mkdir(parents=True, exist_ok=True)
        self._handler = _DropHandler()
        self._observer = Observer()
        self._observer.schedule(self._handler, str(self.drop_folder), recursive=False)
        self._observer.start()

    def check_for_updates(self) -> list[Any]:
        items = list(self._handler.pending)
        self._handler.pending.clear()
        return items

    def create_action_file(self, item: Any) -> Path:
        src_path: Path = item
        if not src_path.exists():
            return src_path

        now = datetime.now(timezone.utc)
        dest_name = f"FILE_{src_path.name}"
        dest = self.needs_action_dir / dest_name

        # Handle same-name conflicts
        if dest.exists():
            ts = now.strftime("%Y%m%d%H%M%S")
            stem = src_path.stem
            suffix = src_path.suffix
            dest_name = f"FILE_{stem}_{ts}{suffix}"
            dest = self.needs_action_dir / dest_name

        # Copy file
        shutil.copy2(src_path, dest)

        # Create companion metadata .md
        file_size = src_path.stat().st_size
        md_path = self.needs_action_dir / f"{dest_name}.md"
        md_content = (
            f"---\n"
            f"type: file_drop\n"
            f"id: {dest_name}\n"
            f"original_name: {src_path.name}\n"
            f"size: {file_size}\n"
            f"received: {now.isoformat()}\n"
            f"priority: high\n"
            f"status: pending\n"
            f"plan_ref: null\n"
            f"---\n\n"
            f"## Content\n"
            f"File dropped: `{src_path.name}` ({file_size} bytes)\n\n"
            f"## Suggested Actions\n"
            f"- [ ] Review file contents\n"
            f"- [ ] Determine required action\n"
        )
        md_path.write_text(md_content, encoding="utf-8")
        return md_path

    def stop(self) -> None:
        super().stop()
        self._observer.stop()
        self._observer.join(timeout=5)


if __name__ == "__main__":
    import sys
    sys.path.insert(0, ".")
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )
    from src.core.config import Config
    watcher = FileSystemWatcher(Config())
    watcher.run()
