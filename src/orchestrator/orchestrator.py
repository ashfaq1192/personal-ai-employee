"""Master Orchestrator — coordinates watchers, scheduling, and file-based workflow."""

from __future__ import annotations

import logging
import re
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
from src.orchestrator.approval_watcher import ApprovalWatcher
from src.orchestrator.health_monitor import HealthMonitor
from src.orchestrator.scheduler import Scheduler

log = logging.getLogger(__name__)


class _NeedsActionHandler(FileSystemEventHandler):
    """Triggers Claude reasoning when new files appear in /Needs_Action/."""

    def __init__(self, orchestrator: Orchestrator) -> None:
        self._orch = orchestrator

    def on_created(self, event: FileCreatedEvent) -> None:  # type: ignore[override]
        if event.is_directory:
            return
        path = Path(event.src_path)
        if path.suffix == ".md":
            log.info("New item in Needs_Action: %s", path.name)
            self._orch.trigger_reasoning(path.name)


class Orchestrator:
    """Master process: launches watchers, scheduling, health checks, approval workflow."""

    def __init__(self, config: Config | None = None) -> None:
        self.config = config or Config()
        self.vault_path = self.config.vault_path
        self.audit = AuditLogger(self.vault_path)
        self.scheduler = Scheduler()
        self.health_monitor = HealthMonitor(self.vault_path)
        self.approval_mgr = ApprovalManager(self.vault_path)
        self.approval_watcher = ApprovalWatcher(
            self.vault_path, action_dispatcher=self._dispatch_action
        )
        self._observer = Observer()
        self._running = False

    def _dispatch_action(self, path: Path, action_params: dict) -> None:
        """Dispatch an approved action to the appropriate MCP server."""
        action = action_params.get("action", "")
        log.info("Dispatching approved action: %s", action)

        # Extract body text from the approval file (## Reply Body section)
        body_text = ""
        try:
            raw = path.read_text(encoding="utf-8", errors="replace")
            m = re.search(r"## Reply Body\s*\n\n([\s\S]+)", raw)
            body_text = m.group(1).strip() if m else ""
        except Exception:
            pass

        if self.config.dev_mode:
            log.info("[DEV_MODE] Skipping real dispatch for action=%s", action)
            return

        try:
            if action in ("email_send", "send_email"):
                from src.mcp_servers.gmail_service import GmailService
                svc = GmailService(self.config.gmail_credentials_path)
                svc.send_email(
                    to=action_params.get("recipient", action_params.get("to", "")),
                    subject=action_params.get("subject", "Re: Your message"),
                    body=body_text or action_params.get("body", "(no body)"),
                )

            elif action in ("whatsapp_reply", "whatsapp_send"):
                from src.mcp_servers.whatsapp_client import WhatsAppClient
                client = WhatsAppClient(self.config)
                client.send_message(
                    to=action_params.get("to", action_params.get("recipient", "")),
                    body=body_text or action_params.get("body", ""),
                )

            elif action in ("linkedin_post", "social_post"):
                from src.mcp_servers.linkedin_client import LinkedInClient
                client = LinkedInClient(self.config)
                client.post(text=body_text or action_params.get("text", ""))

            elif action == "facebook_post":
                from src.mcp_servers.facebook_client import FacebookClient
                client = FacebookClient(self.config)
                client.post_to_page(
                    page_id=self.config.facebook_page_id,
                    message=body_text or action_params.get("text", ""),
                )

            elif action == "instagram_post":
                from src.mcp_servers.instagram_client import InstagramClient
                client = InstagramClient(self.config)
                client.post(
                    ig_user_id=self.config.instagram_user_id,
                    image_url=action_params.get("image_url", ""),
                    caption=body_text or action_params.get("caption", ""),
                )

            elif action == "twitter_post":
                from src.mcp_servers.twitter_client import TwitterClient
                client = TwitterClient(self.config)
                client.post(text=body_text or action_params.get("text", ""))

            elif action in ("invoice", "create_invoice"):
                from src.mcp_servers.odoo_client import OdooClient
                client = OdooClient(self.config)
                client.create_invoice(
                    partner_name=action_params.get("recipient", ""),
                    invoice_lines=[{"name": "Service", "quantity": 1,
                                    "price_unit": float(action_params.get("amount", 0) or 0)}],
                )

            elif action == "payment":
                log.warning(
                    "Payment action requires manual processing — no payment MCP. Amount: %s",
                    action_params.get("amount", "?"),
                )

            else:
                log.warning("Unknown action type: %s — no dispatch performed", action)

        except Exception as exc:
            log.exception("Dispatch failed for action=%s", action)
            self.audit.log(
                action_type=action,
                actor="orchestrator",
                target=action_params.get("recipient", ""),
                result="failure",
                error=str(exc)[:200],
            )
            return

        self.audit.log(
            action_type=action,
            actor="orchestrator",
            target=action_params.get("recipient", action_params.get("to", "")),
            parameters={k: str(v) for k, v in action_params.items()},
            approval_status="approved",
            approved_by="human",
            result="success",
        )

    def _start_watcher_process(self, watcher_module: str, watcher_name: str) -> subprocess.Popen:
        """Start a watcher as a subprocess."""
        cmd = [sys.executable, "-m", watcher_module]
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        log.info("Started %s watcher (PID %d)", watcher_name, proc.pid)
        return proc

    def trigger_reasoning(self, filename: str | None = None) -> None:
        """Trigger Claude Code reasoning on vault items."""
        try:
            cmd = [sys.executable, "src/cli/trigger_reasoning.py"]
            if filename:
                cmd.extend(["--file", filename])
            subprocess.Popen(cmd, cwd=str(Path(__file__).parent.parent.parent))
        except Exception:
            log.exception("Failed to trigger reasoning")

    def start(self) -> None:
        """Start the orchestrator and all components."""
        self._running = True
        log.info("Orchestrator starting (vault: %s)", self.vault_path)

        self.audit.log(
            action_type="system",
            actor="orchestrator",
            target="system",
            parameters={"event": "started", "dev_mode": self.config.dev_mode},
        )

        # Set up scheduled tasks
        self.scheduler.add_interval_task(
            "check_expired_approvals",
            self.approval_mgr.check_expired,
            300,  # every 5 minutes
        )
        self.scheduler.add_interval_task(
            "update_dashboard",
            self._update_dashboard,
            600,  # every 10 minutes
        )
        self.scheduler.add_scheduled_task(
            "log_cleanup",
            lambda: self.audit.cleanup_old_logs(90),
            "0 2 *",  # daily at 2 AM
        )
        self.scheduler.add_scheduled_task(
            "weekly_briefing",
            self._trigger_weekly_briefing,
            "0 23 sun",  # Sunday 23:00 → Monday briefing
        )
        self.scheduler.add_interval_task(
            "ralph_batch_check",
            self._check_ralph_batch,
            120,  # every 2 minutes
        )
        self.scheduler.start()

        # Start approval watcher
        self.approval_watcher.start()

        # Watch /Needs_Action/ for new files
        needs_action_dir = self.vault_path / "Needs_Action"
        needs_action_dir.mkdir(parents=True, exist_ok=True)
        handler = _NeedsActionHandler(self)
        self._observer.schedule(handler, str(needs_action_dir), recursive=False)
        self._observer.start()

        log.info("Orchestrator ready. Waiting for events...")

        # Set up graceful shutdown (only works in main thread)
        if threading.current_thread() is threading.main_thread():
            def _shutdown(signum, frame):
                log.info("Received signal %d, shutting down...", signum)
                self.stop()

            signal.signal(signal.SIGTERM, _shutdown)
            signal.signal(signal.SIGINT, _shutdown)

        # Main loop
        try:
            while self._running:
                time.sleep(1)
        except KeyboardInterrupt:
            self.stop()

    def _trigger_weekly_briefing(self) -> None:
        """Trigger Claude Code to generate the weekly CEO briefing."""
        try:
            log.info("Triggering weekly CEO briefing generation")
            cmd = [
                sys.executable,
                "src/cli/trigger_reasoning.py",
                "--skill", "generate-briefing",
            ]
            subprocess.Popen(cmd, cwd=str(Path(__file__).parent.parent.parent))
            self.audit.log(
                action_type="system",
                actor="orchestrator",
                target="weekly_briefing",
                parameters={"skill": "generate-briefing"},
            )
        except Exception:
            log.exception("Failed to trigger weekly briefing")

    def _check_ralph_batch(self) -> None:
        """If Needs_Action has more items than threshold, use Ralph loop for batch processing."""
        try:
            from src.orchestrator.ralph_integration import RalphIntegration

            needs_action = self.vault_path / "Needs_Action"
            items = list(needs_action.glob("*.md")) if needs_action.exists() else []
            threshold = self.config.ralph_batch_threshold
            if len(items) > threshold:
                log.info(
                    "Needs_Action has %d items (threshold %d) — starting Ralph loop",
                    len(items), threshold,
                )
                ralph = RalphIntegration(self.config)
                ralph.trigger_vault_processing()
        except Exception:
            log.exception("Ralph batch check failed")

    def _update_dashboard(self) -> None:
        """Update Dashboard.md with current counts."""
        try:
            from src.orchestrator.dashboard_updater import update_dashboard
            update_dashboard(self.vault_path)
        except Exception:
            log.exception("Dashboard update failed")

    def stop(self) -> None:
        """Gracefully stop all components."""
        self._running = False
        self._observer.stop()
        self._observer.join(timeout=5)
        self.approval_watcher.stop()
        self.scheduler.stop()
        self.health_monitor.stop_all()
        self.audit.log(
            action_type="system",
            actor="orchestrator",
            target="system",
            parameters={"event": "stopped"},
        )
        log.info("Orchestrator stopped")


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
        log.info("Creating vault at %s...", config.vault_path)
        from src.vault.init_vault import init_vault
        init_vault(config.vault_path)

    orchestrator = Orchestrator(config)
    orchestrator.start()


if __name__ == "__main__":
    main()
