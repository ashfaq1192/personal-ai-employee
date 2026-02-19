"""Cloud Agent — stripped-down orchestrator for GCP VM.

Runs Gmail Watcher only (no WhatsApp — local owns session).
Creates only drafts and approval requests — never executes send actions.
Uses claim-by-move rule for multi-agent coordination.
"""

from __future__ import annotations

import logging
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

from watchdog.events import FileCreatedEvent, FileSystemEventHandler
from watchdog.observers import Observer

from src.core.config import Config
from src.core.logger import AuditLogger
from src.orchestrator.approval_manager import ApprovalManager
from src.orchestrator.claim_manager import ClaimManager
from src.orchestrator.scheduler import Scheduler

log = logging.getLogger(__name__)

AGENT_NAME = "cloud"


class _CloudNeedsActionHandler(FileSystemEventHandler):
    """Process new Needs_Action items as drafts only."""

    def __init__(self, agent: CloudAgent) -> None:
        self._agent = agent

    def on_created(self, event: FileCreatedEvent) -> None:  # type: ignore[override]
        if event.is_directory:
            return
        path = Path(event.src_path)
        if path.suffix == ".md":
            self._agent.process_item_as_draft(path)


class CloudAgent:
    """Cloud-side orchestrator: Gmail watcher, draft-only processing, claim-by-move."""

    def __init__(self, config: Config | None = None) -> None:
        self.config = config or Config()
        self.vault_path = self.config.vault_path
        self.audit = AuditLogger(self.vault_path)
        self.scheduler = Scheduler()
        self.claim_mgr = ClaimManager(self.vault_path)
        self.approval_mgr = ApprovalManager(self.vault_path)
        self._observer = Observer()
        self._running = False

    def process_item_as_draft(self, item_path: Path) -> None:
        """Process a Needs_Action item — claim it, create draft, request approval."""
        if not self.claim_mgr.claim(item_path, AGENT_NAME):
            log.info("Item already claimed: %s", item_path.name)
            return

        log.info("Cloud agent processing: %s (draft-only)", item_path.name)

        try:
            # Trigger Claude reasoning in draft-only mode
            cmd = [
                sys.executable,
                "src/cli/trigger_reasoning.py",
                "--skill", "process-inbox",
                "--file", item_path.name,
            ]
            subprocess.Popen(
                cmd,
                cwd=str(Path(__file__).parent.parent.parent),
            )

            self.audit.log(
                action_type="cloud_process",
                actor=AGENT_NAME,
                target=item_path.name,
                parameters={"mode": "draft_only"},
            )
        except Exception:
            log.exception("Failed to process %s", item_path.name)
            # Release claim on failure
            self.claim_mgr.release(item_path.name, AGENT_NAME, "Needs_Action")

    def _write_cloud_update(self) -> None:
        """Write status update to /Updates/ for local agent to merge into Dashboard."""
        updates_dir = self.vault_path / "Updates"
        updates_dir.mkdir(parents=True, exist_ok=True)

        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)

        claims = self.claim_mgr.list_claims(AGENT_NAME)
        needs_action = list((self.vault_path / "Needs_Action").glob("*.md"))

        update_file = updates_dir / f"cloud_status_{now.strftime('%Y%m%d_%H%M')}.md"
        update_file.write_text(
            f"---\n"
            f"source: cloud_agent\n"
            f"timestamp: {now.isoformat()}\n"
            f"---\n\n"
            f"# Cloud Agent Status\n\n"
            f"- Active claims: {len(claims)}\n"
            f"- Needs_Action items: {len(needs_action)}\n"
            f"- Agent: {AGENT_NAME}\n",
            encoding="utf-8",
        )

    def start(self) -> None:
        """Start the cloud agent."""
        self._running = True
        log.info("Cloud agent starting (vault: %s)", self.vault_path)

        self.audit.log(
            action_type="system",
            actor=AGENT_NAME,
            target="system",
            parameters={"event": "cloud_agent_started", "dev_mode": self.config.dev_mode},
        )

        # Scheduled tasks
        self.scheduler.add_interval_task(
            "check_expired_approvals",
            self.approval_mgr.check_expired,
            300,
        )
        self.scheduler.add_interval_task(
            "cloud_status_update",
            self._write_cloud_update,
            600,
        )
        self.scheduler.start()

        # Watch Needs_Action
        needs_action = self.vault_path / "Needs_Action"
        needs_action.mkdir(parents=True, exist_ok=True)
        handler = _CloudNeedsActionHandler(self)
        self._observer.schedule(handler, str(needs_action), recursive=False)
        self._observer.start()

        log.info("Cloud agent ready (draft-only mode)")

        # Graceful shutdown (only works in main thread)
        if threading.current_thread() is threading.main_thread():
            def _shutdown(signum, frame):
                log.info("Cloud agent received signal %d", signum)
                self.stop()

            signal.signal(signal.SIGTERM, _shutdown)
            signal.signal(signal.SIGINT, _shutdown)

        try:
            while self._running:
                time.sleep(1)
        except KeyboardInterrupt:
            self.stop()

    def stop(self) -> None:
        """Stop the cloud agent."""
        self._running = False
        self._observer.stop()
        self._observer.join(timeout=5)
        self.scheduler.stop()
        self.audit.log(
            action_type="system",
            actor=AGENT_NAME,
            target="system",
            parameters={"event": "cloud_agent_stopped"},
        )
        log.info("Cloud agent stopped")


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )
    config = Config()
    errors = config.validate()
    if errors:
        for err in errors:
            log.error("Config error: %s", err)
        sys.exit(1)

    agent = CloudAgent(config)
    agent.start()


if __name__ == "__main__":
    main()
