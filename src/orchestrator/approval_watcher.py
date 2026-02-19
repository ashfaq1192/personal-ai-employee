"""Approval Watcher — monitors /Approved/ and /Rejected/ for processed approvals."""

from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import Any, Callable

from watchdog.events import FileCreatedEvent, FileSystemEventHandler
from watchdog.observers import Observer

from src.core.logger import AuditLogger
from src.orchestrator.approval_manager import ApprovalManager, _parse_frontmatter

log = logging.getLogger(__name__)


class _ApprovalHandler(FileSystemEventHandler):
    """Handles files appearing in Approved/ or Rejected/."""

    def __init__(self, callback: Callable[[Path, str], None]) -> None:
        self._callback = callback

    def on_created(self, event: FileCreatedEvent) -> None:  # type: ignore[override]
        if event.is_directory:
            return
        path = Path(event.src_path)
        if not path.name.startswith("APPROVAL_"):
            return

        # Determine if approved or rejected based on parent dir name
        parent = path.parent.name
        if parent in ("Approved", "Rejected"):
            self._callback(path, parent.lower())


class ApprovalWatcher:
    """Watches /Approved/ and /Rejected/ folders for approval decisions."""

    def __init__(
        self,
        vault_path: Path,
        *,
        action_dispatcher: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        self.vault_path = vault_path
        self.approval_mgr = ApprovalManager(vault_path)
        self.audit = AuditLogger(vault_path)
        self._action_dispatcher = action_dispatcher
        self._observer = Observer()

        handler = _ApprovalHandler(self._on_approval_decision)
        approved_dir = vault_path / "Approved"
        rejected_dir = vault_path / "Rejected"
        approved_dir.mkdir(parents=True, exist_ok=True)
        rejected_dir.mkdir(parents=True, exist_ok=True)

        self._observer.schedule(handler, str(approved_dir), recursive=False)
        self._observer.schedule(handler, str(rejected_dir), recursive=False)

    def _on_approval_decision(self, path: Path, decision: str) -> None:
        """Handle an approval decision."""
        log.info("Approval decision: %s → %s", path.name, decision)

        if decision == "approved":
            fm = _parse_frontmatter(path)
            action = fm.get("action", "unknown")

            self.audit.log(
                action_type="approval",
                actor="human",
                target=str(path),
                parameters={"action": action},
                approval_status="approved",
                approved_by="human",
            )

            # Dispatch the action
            if self._action_dispatcher:
                try:
                    self._action_dispatcher(fm)
                    # Ensure all values are JSON-serializable (YAML can parse datetime objects)
                    safe_params = {k: str(v) for k, v in fm.items()}
                    self.audit.log(
                        action_type=action,
                        actor="orchestrator",
                        target=fm.get("recipient", ""),
                        parameters=safe_params,
                        approval_status="approved",
                        approved_by="human",
                        result="success",
                    )
                except Exception as exc:
                    log.exception("Action dispatch failed for %s", path.name)
                    self.audit.log(
                        action_type=action,
                        actor="orchestrator",
                        target=fm.get("recipient", ""),
                        result="failure",
                        error=str(exc)[:200],
                    )

            # Move to Done
            done_path = self.vault_path / "Done" / path.name
            shutil.move(str(path), str(done_path))

        elif decision == "rejected":
            self.approval_mgr.process_rejected(path)

    def start(self) -> None:
        """Start watching approval folders."""
        self._observer.start()
        log.info("Approval watcher started")

    def stop(self) -> None:
        """Stop watching."""
        self._observer.stop()
        self._observer.join(timeout=5)
        log.info("Approval watcher stopped")
