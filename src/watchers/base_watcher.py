"""Abstract base class for all watchers."""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from src.core.config import Config
from src.core.logger import AuditLogger

log = logging.getLogger(__name__)


class BaseWatcher(ABC):
    """ABC for perception-layer watchers.

    Subclasses implement:
        check_for_updates() -> list of items detected
        create_action_file(item) -> Path of created .md file
    """

    def __init__(
        self,
        config: Config,
        *,
        check_interval: int = 60,
        watcher_name: str = "base",
    ) -> None:
        self.config = config
        self.check_interval = check_interval
        self.watcher_name = watcher_name
        self.vault_path = config.vault_path
        self.needs_action_dir = self.vault_path / "Needs_Action"
        self.needs_action_dir.mkdir(parents=True, exist_ok=True)
        self.audit = AuditLogger(self.vault_path)
        self._running = False

    @abstractmethod
    def check_for_updates(self) -> list[Any]:
        """Check the external source for new items. Return list of raw items."""

    @abstractmethod
    def create_action_file(self, item: Any) -> Path:
        """Create an action .md file in /Needs_Action/. Return file path."""

    def run(self) -> None:
        """Main loop — poll at check_interval seconds."""
        self._running = True
        log.info(
            "%s watcher starting (interval=%ds, dev_mode=%s)",
            self.watcher_name,
            self.check_interval,
            self.config.dev_mode,
        )
        self.audit.log(
            action_type="watcher_event",
            actor=f"{self.watcher_name}_watcher",
            target="system",
            parameters={"event": "started", "interval": self.check_interval},
        )

        while self._running:
            try:
                items = self.check_for_updates()
                for item in items:
                    try:
                        path = self.create_action_file(item)
                        log.info(
                            "%s: created action file %s", self.watcher_name, path.name
                        )
                        self.audit.log(
                            action_type="watcher_event",
                            actor=f"{self.watcher_name}_watcher",
                            target=str(path),
                            parameters={"event": "action_file_created"},
                        )
                    except Exception:
                        log.exception(
                            "%s: failed to create action file", self.watcher_name
                        )
            except Exception:
                log.exception("%s: error during check_for_updates", self.watcher_name)

            time.sleep(self.check_interval)

    def stop(self) -> None:
        """Signal the run loop to stop."""
        self._running = False
        log.info("%s watcher stopping", self.watcher_name)
